function Invoke-DatabricksSparkDeepDiveCollector {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

    foreach ($workspace in @($Config.databricks.workspaces | Where-Object include)) {
        $runIds = @(Get-DatabricksDeepDiveTargets -Config $Config -Workspace $workspace -Name 'deepDiveJobRunIds')
        $startedAt = Get-Date
        $sources = [Collections.Generic.List[object]]::new()
        $outputs = [Collections.Generic.List[string]]::new()
        if ($runIds.Count -eq 0) {
            $sources.Add((New-DatabricksSourceStatus -Source 'selected Spark job runs' -Status skipped -Message 'No deep-dive job run IDs are selected.'))
        }
        else {
            $hostName = [string]$workspace.workspaceUrl
            $runs = [Collections.Generic.List[object]]::new()
            $events = [Collections.Generic.List[object]]::new()
            $errors = [Collections.Generic.List[string]]::new()
            $clusterIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
            foreach ($runId in $runIds) {
                if ([string]$runId -notmatch '^\d+$') {
                    $errors.Add("Run ID '$runId' is not numeric.")
                    continue
                }
                try {
                    $run = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path "/api/2.1/jobs/runs/get?run_id=$runId&include_history=true"
                    $runs.Add($run)
                    $clusterInstance = Get-DatabricksProperty -InputObject $run -Name 'cluster_instance'
                    $clusterId = [string](Get-DatabricksProperty -InputObject $clusterInstance -Name 'cluster_id')
                    if (-not [string]::IsNullOrWhiteSpace($clusterId)) { [void]$clusterIds.Add($clusterId) }
                    foreach ($task in @((Get-DatabricksProperty -InputObject $run -Name 'tasks' -Default @()))) {
                        $taskCluster = Get-DatabricksProperty -InputObject $task -Name 'cluster_instance'
                        $taskClusterId = [string](Get-DatabricksProperty -InputObject $taskCluster -Name 'cluster_id')
                        if (-not [string]::IsNullOrWhiteSpace($taskClusterId)) { [void]$clusterIds.Add($taskClusterId) }
                    }
                }
                catch {
                    $errors.Add("Run ${runId}: $($_.Exception.Message)")
                }
            }

            $startMillis = [DateTimeOffset]::Parse([string]$Config.analysis.startUtc).ToUnixTimeMilliseconds()
            $endMillis = [DateTimeOffset]::Parse([string]$Config.analysis.endUtc).ToUnixTimeMilliseconds()
            $pageSize = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'pageSize' -Default 100)
            foreach ($clusterId in $clusterIds) {
                try {
                    $body = @{
                        cluster_id = $clusterId
                        start_time = $startMillis
                        end_time = $endMillis
                        limit = $pageSize
                    }
                    $eventResult = Invoke-DatabricksPagedPost -Config $Config -HostName $hostName -Path '/api/2.0/clusters/events' -Body $body -ItemsProperty events
                    foreach ($event in @($eventResult.items)) { $events.Add($event) }
                    if ($eventResult.truncated) { $errors.Add("$clusterId event inventory reached the configured page limit.") }
                }
                catch {
                    $errors.Add("$clusterId events: $($_.Exception.Message)")
                }
            }

            foreach ($dataset in @(
                @{ Name = 'spark-selected-runs'; Items = @($runs) },
                @{ Name = 'spark-cluster-events'; Items = @($events) }
            )) {
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name $dataset.Name -Items $dataset.Items
                $outputs.Add($output)
            }
            $sources.Add((New-DatabricksSourceStatus -Source 'selected Spark job run metadata' -Status $(if ($errors.Count) { 'partial' } else { 'passed' }) -ItemCount ($runs.Count + $events.Count) -Output ($outputs[-1]) -Message ($errors -join '; ')))
            $sources.Add((New-DatabricksSourceStatus -Source 'Spark stage, task, executor, and SQL execution metrics' -Status 'pending telemetry' -Message 'The Jobs and cluster event APIs do not expose full Spark UI metrics. Supply an approved event-log export to satisfy detailed Spark evidence.'))
        }

        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'spark-deep-dive' -Sources @($sources)
        $outputs.Add($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks Spark deep dive [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $startedAt -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs @($outputs) -Limitations $limitations
    }
}
