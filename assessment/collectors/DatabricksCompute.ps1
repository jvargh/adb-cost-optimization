function Invoke-DatabricksComputeCollector {
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
        $pageSize = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'pageSize' -Default 100)
        $clusterItems = @()
        $policyItems = @()

        $requests = @(
            @{ Source = 'clusters'; Path = '/api/2.0/clusters/list'; Items = 'clusters'; Output = 'clusters'; Paged = $false },
            @{ Source = 'cluster policies'; Path = "/api/2.0/policies/clusters/list?max_results=$pageSize"; Items = 'policies'; Output = 'cluster-policies'; Paged = $true },
            @{ Source = 'instance pools'; Path = '/api/2.0/instance-pools/list'; Items = 'instance_pools'; Output = 'instance-pools'; Paged = $false }
        )
        foreach ($request in $requests) {
            try {
                if ($request.Paged) {
                    $result = Invoke-DatabricksPagedGet -Config $Config -HostName $hostName -Path $request.Path -ItemsProperty $request.Items
                    $items = @($result.items)
                    $truncated = $result.truncated
                }
                else {
                    $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path $request.Path
                    $items = @((Get-DatabricksProperty -InputObject $response -Name $request.Items -Default @()))
                    $truncated = $false
                }
                if ($request.Source -eq 'clusters') {
                    $clusterItems = $items
                }
                if ($request.Source -eq 'cluster policies') {
                    $policyItems = $items
                }
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name $request.Output -Items $items
                $outputs.Add($output)
                $sources.Add((New-DatabricksSourceStatus -Source $request.Source -Status $(if ($truncated) { 'partial' } else { 'passed' }) -ItemCount $items.Count -Output $output -Message $(if ($truncated) { 'The configured page limit was reached.' })))
            }
            catch {
                $sources.Add((New-DatabricksSourceStatus -Source $request.Source -Status partial -Message $_.Exception.Message))
            }
        }

        $policyPermissions = [Collections.Generic.List[object]]::new()
        $policyErrors = [Collections.Generic.List[string]]::new()
        foreach ($policy in $policyItems) {
            $policyId = [string](Get-DatabricksProperty -InputObject $policy -Name 'policy_id')
            if ([string]::IsNullOrWhiteSpace($policyId)) { continue }
            try {
                $permissions = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path "/api/2.0/permissions/cluster-policies/$([Uri]::EscapeDataString($policyId))"
                $policyPermissions.Add($permissions)
            }
            catch {
                $policyErrors.Add("${policyId}: $($_.Exception.Message)")
            }
        }
        $policyPermissionsOutput = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'cluster-policy-permissions' -Items @($policyPermissions)
        $outputs.Add($policyPermissionsOutput)
        $sources.Add((New-DatabricksSourceStatus -Source 'cluster policy assignments' -Status $(if ($policyErrors.Count) { 'partial' } else { 'passed' }) -ItemCount $policyPermissions.Count -Output $policyPermissionsOutput -Message ($policyErrors -join '; ')))

        $events = [Collections.Generic.List[object]]::new()
        $eventErrors = [Collections.Generic.List[string]]::new()
        $startMillis = [DateTimeOffset]::Parse([string]$Config.analysis.startUtc).ToUnixTimeMilliseconds()
        $endMillis = [DateTimeOffset]::Parse([string]$Config.analysis.endUtc).ToUnixTimeMilliseconds()
        foreach ($cluster in $clusterItems) {
            $clusterId = [string](Get-DatabricksProperty -InputObject $cluster -Name 'cluster_id')
            if ([string]::IsNullOrWhiteSpace($clusterId)) { continue }
            try {
                $body = @{
                    cluster_id = $clusterId
                    start_time = $startMillis
                    end_time = $endMillis
                    limit = $pageSize
                }
                $result = Invoke-DatabricksPagedPost -Config $Config -HostName $hostName -Path '/api/2.0/clusters/events' -Body $body -ItemsProperty events
                foreach ($event in @($result.items)) { $events.Add($event) }
                if ($result.truncated) { $eventErrors.Add("$clusterId reached the configured page limit.") }
            }
            catch {
                $eventErrors.Add("${clusterId}: $($_.Exception.Message)")
            }
        }
        $eventOutput = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'cluster-events' -Items @($events)
        $outputs.Add($eventOutput)
        $eventStatus = if ($eventErrors.Count) { 'partial' } else { 'passed' }
        $sources.Add((New-DatabricksSourceStatus -Source 'cluster events' -Status $eventStatus -ItemCount $events.Count -Output $eventOutput -Message ($eventErrors -join '; ')))

        $nodeSource = Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.compute.node_timeline' -FileName 'DatabricksNodeTimeline.sql' -OutputName 'node-timeline' -Parameters (New-DatabricksTimeParameters -Config $Config)
        $sources.Add($nodeSource)
        if ($nodeSource.output) { $outputs.Add($nodeSource.output) }

        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'compute' -Sources @($sources)
        $outputs.Add($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks compute [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $startedAt -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs @($outputs) -Limitations $limitations
    }
}
