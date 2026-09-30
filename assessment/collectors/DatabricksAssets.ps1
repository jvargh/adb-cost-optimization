function Invoke-DatabricksAssetsCollector {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Config, [Parameter(Mandatory)][object]$RunContext)

    $options = Get-DatabricksProperty -InputObject $Config -Name 'capabilities' -Default ([pscustomobject]@{})
    $profile = Get-DatabricksProperty -InputObject $options -Name 'profile' -Default 'standard'
    $selected = @(Get-DatabricksProperty -InputObject $options -Name 'assets' -Default $(if ($profile -eq 'extended') {
        @('repos', 'notebooks', 'experiments', 'serving-endpoints', 'sql-alerts', 'genie-spaces', 'uc-volumes')
    } else { @() }) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($selected.Count -eq 0) {
        return New-CollectorResult -Name 'Databricks optional assets' -Status skipped -StartedAt (Get-Date) -Limitations @('Asset collection was not selected.')
    }
    $definitions = @{
        'repos' = @{ Path = '/api/2.0/repos'; Items = 'repos' }
        'serving-endpoints' = @{ Path = '/api/2.0/serving-endpoints'; Items = 'endpoints' }
        'sql-alerts' = @{ Path = '/api/2.0/sql/alerts'; Items = 'results' }
        'genie-spaces' = @{ Path = '/api/2.0/genie/spaces'; Items = 'spaces' }
    }
    foreach ($workspace in @($Config.databricks.workspaces | Where-Object include)) {
        $started = Get-Date
        $sources = [Collections.Generic.List[object]]::new()
        $outputs = [Collections.Generic.List[string]]::new()
        foreach ($kind in $selected) {
            try {
                $items = [Collections.Generic.List[object]]::new()
                $truncated = $false
                $limit = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'maxPages' -Default 100)
                if ($kind -eq 'experiments') {
                    $page = Invoke-DatabricksPagedPost -Config $Config -HostName $workspace.workspaceUrl -Path '/api/2.0/mlflow/experiments/search' -Body @{ max_results = 100; view_type = 'ACTIVE_ONLY' } -ItemsProperty experiments -ContinuationProperty next_page_token -TokenParameter page_token
                    foreach ($item in @($page.items)) { $items.Add($item) }
                    $truncated = $page.truncated
                }
                elseif ($definitions.ContainsKey($kind)) {
                    $definition = $definitions[$kind]
                    $page = Invoke-DatabricksPagedGet -Config $Config -HostName $workspace.workspaceUrl -Path $definition.Path -ItemsProperty $definition.Items
                    foreach ($item in @($page.items)) { $items.Add($item) }
                    $truncated = $page.truncated
                }
                elseif ($kind -eq 'notebooks') {
                    $queue = [Collections.Generic.Queue[string]]::new()
                    $queue.Enqueue('/')
                    $pages = 0
                    while ($queue.Count -gt 0 -and $pages -lt $limit) {
                        $folder = $queue.Dequeue()
                        $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $workspace.workspaceUrl -Method GET -Path "/api/2.0/workspace/list?path=$([Uri]::EscapeDataString($folder))"
                        foreach ($item in @(Get-DatabricksProperty -InputObject $response -Name 'objects' -Default @())) {
                            if ($item.object_type -eq 'DIRECTORY') { $queue.Enqueue($item.path) }
                            elseif ($item.object_type -eq 'NOTEBOOK') { $items.Add($item) }
                        }
                        $pages++
                    }
                    $truncated = $queue.Count -gt 0
                }
                elseif ($kind -eq 'uc-volumes') {
                    $catalogs = Invoke-DatabricksPagedGet -Config $Config -HostName $workspace.workspaceUrl -Path '/api/2.1/unity-catalog/catalogs' -ItemsProperty catalogs
                    $truncated = $catalogs.truncated
                    $requests = 0
                    foreach ($catalog in @($catalogs.items)) {
                        if ($requests -ge $limit) { $truncated = $true; break }
                        $schemas = Invoke-DatabricksPagedGet -Config $Config -HostName $workspace.workspaceUrl -Path "/api/2.1/unity-catalog/schemas?catalog_name=$([Uri]::EscapeDataString($catalog.name))" -ItemsProperty schemas
                        $requests++
                        $truncated = $truncated -or $schemas.truncated
                        foreach ($schema in @($schemas.items)) {
                            if ($requests -ge $limit) { $truncated = $true; break }
                            $volumes = Invoke-DatabricksPagedGet -Config $Config -HostName $workspace.workspaceUrl -Path "/api/2.1/unity-catalog/volumes?catalog_name=$([Uri]::EscapeDataString($catalog.name))&schema_name=$([Uri]::EscapeDataString($schema.name))" -ItemsProperty volumes
                            $requests++
                            foreach ($item in @($volumes.items)) { $items.Add($item) }
                            $truncated = $truncated -or $volumes.truncated
                        }
                    }
                }
                else { throw "Unsupported asset collection: $kind" }
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name $kind -Items @($items)
                $outputs.Add($output)
                $sources.Add((New-DatabricksSourceStatus -Source $kind -Status $(if ($truncated) { 'partial' } else { 'passed' }) -ItemCount $items.Count -Output $output -Message $(if ($truncated) { 'Collection bound reached; inventory is incomplete.' } else { '' })))
            }
            catch {
                $sources.Add((New-DatabricksSourceStatus -Source $kind -Status failed -Message $_.Exception.Message))
            }
        }
        $outputs.Add((Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'assets' -Sources @($sources)))
        New-CollectorResult -Name "Databricks assets [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $started -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs @($outputs) -Limitations @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
    }
}
