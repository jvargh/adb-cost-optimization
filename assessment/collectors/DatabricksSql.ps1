function Invoke-DatabricksSqlCollector {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

    foreach ($workspace in @($Config.databricks.workspaces | Where-Object include)) {
        $startedAt = Get-Date
        $sources = [Collections.Generic.List[object]]::new()
        $outputs = [Collections.Generic.List[string]]::new()
        $hostName = [string]$workspace.workspaceUrl
        try {
            $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path '/api/2.0/sql/warehouses'
            $warehouses = @((Get-DatabricksProperty -InputObject $response -Name 'warehouses' -Default @()))
            $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'sql-warehouses' -Items $warehouses
            $outputs.Add($output)
            $sources.Add((New-DatabricksSourceStatus -Source 'SQL Warehouses' -Status passed -ItemCount $warehouses.Count -Output $output))
        }
        catch {
            $sources.Add((New-DatabricksSourceStatus -Source 'SQL Warehouses' -Status partial -Message $_.Exception.Message))
        }

        $querySource = Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.query.history' -FileName 'DatabricksQueryHistory.sql' -OutputName 'query-history' -Parameters (New-DatabricksTimeParameters -Config $Config)
        $sources.Add($querySource)
        if ($querySource.output) { $outputs.Add($querySource.output) }

        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'sql' -Sources @($sources)
        $outputs.Add($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks SQL [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $startedAt -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs @($outputs) -Limitations $limitations
    }
}
