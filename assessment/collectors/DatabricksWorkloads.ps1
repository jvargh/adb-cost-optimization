function Invoke-DatabricksWorkloadsCollector {
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
        $pageSize = [Math]::Min(100, [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'pageSize' -Default 100))
        $startMillis = [DateTimeOffset]::Parse([string]$Config.analysis.startUtc).ToUnixTimeMilliseconds()
        $endMillis = [DateTimeOffset]::Parse([string]$Config.analysis.endUtc).ToUnixTimeMilliseconds()

        $requests = @(
            @{ Source = 'jobs and tasks'; Path = "/api/2.1/jobs/list?limit=$pageSize&expand_tasks=true"; Items = 'jobs'; Output = 'jobs' },
            @{ Source = 'job and task runs'; Path = "/api/2.1/jobs/runs/list?limit=25&expand_tasks=true&start_time_from=$startMillis&start_time_to=$endMillis"; Items = 'runs'; Output = 'job-runs' },
            @{ Source = 'pipelines'; Path = "/api/2.0/pipelines?max_results=$pageSize"; Items = 'statuses'; Output = 'pipelines' }
        )
        $pipelines = @()
        foreach ($request in $requests) {
            try {
                $result = Invoke-DatabricksPagedGet -Config $Config -HostName $hostName -Path $request.Path -ItemsProperty $request.Items
                $items = @($result.items)
                if ($request.Source -eq 'pipelines') { $pipelines = $items }
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name $request.Output -Items $items
                $outputs.Add($output)
                $sources.Add((New-DatabricksSourceStatus -Source $request.Source -Status $(if ($result.truncated) { 'partial' } else { 'passed' }) -ItemCount $items.Count -Output $output -Message $(if ($result.truncated) { 'The configured page limit was reached.' })))
            }
            catch {
                $sources.Add((New-DatabricksSourceStatus -Source $request.Source -Status partial -Message $_.Exception.Message))
            }
        }

        $pipelineDetails = [Collections.Generic.List[object]]::new()
        $pipelineEvents = [Collections.Generic.List[object]]::new()
        $pipelineErrors = [Collections.Generic.List[string]]::new()
        foreach ($pipeline in $pipelines) {
            $pipelineId = [string](Get-DatabricksProperty -InputObject $pipeline -Name 'pipeline_id')
            if ([string]::IsNullOrWhiteSpace($pipelineId)) { continue }
            try {
                $pipelineDetails.Add((Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path "/api/2.0/pipelines/$pipelineId"))
                $eventsPath = "/api/2.0/pipelines/$pipelineId/events?max_results=$pageSize&order_by=timestamp%20desc"
                $eventsResult = Invoke-DatabricksPagedGet -Config $Config -HostName $hostName -Path $eventsPath -ItemsProperty events
                foreach ($event in @($eventsResult.items)) { $pipelineEvents.Add($event) }
                if ($eventsResult.truncated) { $pipelineErrors.Add("$pipelineId reached the configured page limit.") }
            }
            catch {
                $pipelineErrors.Add("${pipelineId}: $($_.Exception.Message)")
            }
        }
        foreach ($dataset in @(
            @{ Name = 'pipeline-details'; Items = @($pipelineDetails) },
            @{ Name = 'pipeline-events'; Items = @($pipelineEvents) }
        )) {
            $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name $dataset.Name -Items $dataset.Items
            $outputs.Add($output)
        }
        $sources.Add((New-DatabricksSourceStatus -Source 'pipeline definitions and events' -Status $(if ($pipelineErrors.Count) { 'partial' } else { 'passed' }) -ItemCount ($pipelineDetails.Count + $pipelineEvents.Count) -Output ($outputs[-1]) -Message ($pipelineErrors -join '; ')))

        $timelineSources = @(
            Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.lakeflow.jobs' -FileName 'DatabricksJobs.sql' -OutputName 'system-jobs'
            Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.lakeflow.job_run_timeline' -FileName 'DatabricksJobRunTimeline.sql' -OutputName 'job-run-timeline' -Parameters (New-DatabricksTimeParameters -Config $Config)
            Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.lakeflow.pipeline_update_timeline' -FileName 'DatabricksPipelineTimeline.sql' -OutputName 'pipeline-update-timeline' -Parameters (New-DatabricksTimeParameters -Config $Config)
        )
        foreach ($source in $timelineSources) {
            $sources.Add($source)
            if ($source.output) { $outputs.Add($source.output) }
        }

        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'workloads' -Sources @($sources)
        $outputs.Add($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks workloads [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $startedAt -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs @($outputs) -Limitations $limitations
    }
}
