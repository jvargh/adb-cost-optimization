function Invoke-DatabricksUnityCatalogCollector {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

    foreach ($workspace in @($Config.databricks.workspaces | Where-Object include)) {
        $selectedTables = @(Get-DatabricksDeepDiveTargets -Config $Config -Workspace $workspace -Name 'deepDiveTableNames')
        $startedAt = Get-Date
        $sources = [Collections.Generic.List[object]]::new()
        $outputs = [Collections.Generic.List[string]]::new()
        $hostName = [string]$workspace.workspaceUrl
        $pageSize = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'pageSize' -Default 100)
        $catalogs = @()
        $schemas = [Collections.Generic.List[object]]::new()
        $tables = [Collections.Generic.List[object]]::new()
        $bindings = [Collections.Generic.List[object]]::new()
        try {
            $catalogResult = Invoke-DatabricksPagedGet -Config $Config -HostName $hostName -Path "/api/2.1/unity-catalog/catalogs?max_results=$pageSize" -ItemsProperty catalogs
            $catalogs = @($catalogResult.items)
            $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'uc-catalogs' -Items $catalogs
            $outputs.Add($output)
            $sources.Add((New-DatabricksSourceStatus -Source 'Unity Catalog catalogs' -Status $(if ($catalogResult.truncated) { 'partial' } else { 'passed' }) -ItemCount $catalogs.Count -Output $output))
        }
        catch {
            $sources.Add((New-DatabricksSourceStatus -Source 'Unity Catalog catalogs' -Status partial -Message $_.Exception.Message))
        }

        $metadataErrors = [Collections.Generic.List[string]]::new()
        foreach ($catalog in $catalogs) {
            $catalogName = [string](Get-DatabricksProperty -InputObject $catalog -Name 'name')
            if ([string]::IsNullOrWhiteSpace($catalogName)) { continue }
            $isolationMode = [string](Get-DatabricksProperty -InputObject $catalog -Name 'isolation_mode')
            if ($isolationMode -eq 'OPEN') {
                $bindings.Add([pscustomobject]@{
                    catalog_name = $catalogName
                    isolation_mode = 'OPEN'
                    bindings = $null
                    limitation = 'Workspace binding restrictions do not apply to an OPEN catalog; table privileges still apply.'
                })
            }
            else {
                try {
                    $binding = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path "/api/2.1/unity-catalog/workspace-bindings/catalogs/$([Uri]::EscapeDataString($catalogName))"
                    $bindings.Add([pscustomobject]@{ catalog_name = $catalogName; isolation_mode = $isolationMode; bindings = $binding })
                }
                catch {
                    $metadataErrors.Add("$catalogName bindings: $($_.Exception.Message)")
                }
            }
            try {
                $schemaPath = "/api/2.1/unity-catalog/schemas?catalog_name=$([Uri]::EscapeDataString($catalogName))&max_results=$pageSize"
                $schemaResult = Invoke-DatabricksPagedGet -Config $Config -HostName $hostName -Path $schemaPath -ItemsProperty schemas
                foreach ($schema in @($schemaResult.items)) { $schemas.Add($schema) }
                if ($schemaResult.truncated) { $metadataErrors.Add("$catalogName schema inventory reached the configured page limit.") }
            }
            catch {
                $metadataErrors.Add("$catalogName schemas: $($_.Exception.Message)")
            }
        }
        foreach ($schema in @($schemas)) {
            $catalogName = [string](Get-DatabricksProperty -InputObject $schema -Name 'catalog_name')
            $schemaName = [string](Get-DatabricksProperty -InputObject $schema -Name 'name')
            if ([string]::IsNullOrWhiteSpace($catalogName) -or [string]::IsNullOrWhiteSpace($schemaName)) { continue }
            try {
                $tablePath = "/api/2.1/unity-catalog/tables?catalog_name=$([Uri]::EscapeDataString($catalogName))&schema_name=$([Uri]::EscapeDataString($schemaName))&max_results=$pageSize"
                $tableResult = Invoke-DatabricksPagedGet -Config $Config -HostName $hostName -Path $tablePath -ItemsProperty tables
                foreach ($table in @($tableResult.items)) { $tables.Add($table) }
                if ($tableResult.truncated) { $metadataErrors.Add("$catalogName.$schemaName table inventory reached the configured page limit.") }
            }
            catch {
                $metadataErrors.Add("$catalogName.$schemaName tables: $($_.Exception.Message)")
            }
        }
        foreach ($dataset in @(
            @{ Name = 'uc-catalog-bindings'; Items = @($bindings) },
            @{ Name = 'uc-schemas'; Items = @($schemas) },
            @{ Name = 'uc-tables'; Items = @($tables) }
        )) {
            $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name $dataset.Name -Items $dataset.Items
            $outputs.Add($output)
        }
        $sources.Add((New-DatabricksSourceStatus -Source 'Unity Catalog bindings, schemas, and tables' -Status $(if ($metadataErrors.Count) { 'partial' } else { 'passed' }) -ItemCount ($bindings.Count + $schemas.Count + $tables.Count) -Output ($outputs[-1]) -Message ($metadataErrors -join '; ')))

        $informationSchema = Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.information_schema.tables' -FileName 'DatabricksTableMetadata.sql' -OutputName 'table-metadata'
        $sources.Add($informationSchema)
        if ($informationSchema.output) { $outputs.Add($informationSchema.output) }

        foreach ($tableName in $selectedTables) {
            $parameters = @(@{ name = 'table_name'; value = [string]$tableName; type = 'STRING' })
            $safeName = (Get-AssessmentHash -Value ([string]$tableName) -Config $Config).Substring(0, 16)
            foreach ($query in @(
                @{ Source = "table detail $safeName"; File = 'DatabricksTableDetail.sql'; Output = "table-detail-$safeName" },
                @{ Source = "table history $safeName"; File = 'DatabricksTableHistory.sql'; Output = "table-history-$safeName" }
            )) {
                $source = Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source $query.Source -FileName $query.File -OutputName $query.Output -Parameters $parameters
                $sources.Add($source)
                if ($source.output) { $outputs.Add($source.output) }
            }
        }
        if ($selectedTables.Count -eq 0) {
            $sources.Add((New-DatabricksSourceStatus -Source 'selected table detail and history' -Status skipped -Message 'No deep-dive tables are selected.'))
        }

        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'unity-catalog' -Sources @($sources)
        $outputs.Add($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks Unity Catalog [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $startedAt -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs @($outputs) -Limitations $limitations
    }
}
