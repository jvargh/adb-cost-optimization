[CmdletBinding()]
param(
    [string]$StatePath = (Join-Path $PSScriptRoot '..\reports\databricks-state.json'),
    [ValidateSet('Classic', 'Serverless', 'All')][string]$Mode = 'All',
    [int]$TimeoutSeconds = 2400,
    [ValidateRange(5, 300)][int]$PollSeconds = 15,
    [ValidateRange(30, 3600)][int]$ClassicStartupTimeoutSeconds = 600,
    [switch]$ForceClassicRetry
)

. (Join-Path $PSScriptRoot 'Workshop.Common.ps1')

Assert-ExpectedSubscription | Out-Null
$state = Read-DeploymentOutputs -Path $StatePath

if ($Mode -in @('Classic', 'All') -and -not $ForceClassicRetry) {
    $recentRuns = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.2/jobs/runs/list?job_id=$($state.classicJobId)&limit=10"
    $recentStockout = @(
        $recentRuns.runs |
            Where-Object {
                $_.start_time -ge [DateTimeOffset]::UtcNow.AddHours(-6).ToUnixTimeMilliseconds() -and
                $_.state.state_message -match 'CLOUD_PROVIDER_RESOURCE_STOCKOUT|SkuNotAvailable'
            } |
            Select-Object -First 1
    )
    if ($recentStockout) {
        throw "Classic execution was blocked by an Azure VM capacity stockout in the last 6 hours (run $($recentStockout[0].run_id)). No new run was started. Retry later with -ForceClassicRetry to override this guard, or run -Mode Serverless."
    }
}
$jobs = if ($Mode -eq 'Classic') {
    @(@{ name = 'Classic'; id = $state.classicJobId })
}
elseif ($Mode -eq 'Serverless') {
    @(@{ name = 'Serverless'; id = $state.serverlessJobId })
}
else {
    @(
        @{ name = 'Classic'; id = $state.classicJobId },
        @{ name = 'Serverless'; id = $state.serverlessJobId }
    )
}

$results = [Collections.Generic.List[object]]::new()
$activeRunId = $null
$activeRunCompleted = $false
try {
    foreach ($job in $jobs) {
        Write-Host "Starting $($job.name) job $($job.id)..."
        $started = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path '/api/2.2/jobs/run-now' -Body @{ job_id = $job.id }
        $activeRunId = $started.run_id
        $activeRunCompleted = $false
        Write-Host "Run ID: $activeRunId"
        Write-Host "Run URL: https://$($state.workspaceUrl)/jobs/$($job.id)/runs/$activeRunId"
        $waitStartedAt = Get-Date

        $run = Wait-DatabricksState `
            -Description "$($job.name) job run $activeRunId" `
            -TimeoutSeconds $TimeoutSeconds `
            -PollSeconds $PollSeconds `
            -Probe { Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.2/jobs/runs/get?run_id=$activeRunId" } `
            -GetStatusText {
                param($value)
                $lifeCycleState = if ($value.state.PSObject.Properties.Name -contains 'life_cycle_state') {
                    $value.state.life_cycle_state
                }
                else {
                    'UNKNOWN'
                }
                $resultState = if ($value.state.PSObject.Properties.Name -contains 'result_state') {
                    $value.state.result_state
                }
                else {
                    'PENDING'
                }
                $taskStates = if ($value.PSObject.Properties.Name -contains 'tasks') {
                    @(
                        $value.tasks | ForEach-Object {
                            $taskLifeCycleState = if ($_.state.PSObject.Properties.Name -contains 'life_cycle_state') {
                                $_.state.life_cycle_state
                            }
                            else {
                                'UNKNOWN'
                            }
                            "$($_.task_key)=$taskLifeCycleState"
                        }
                    )
                }
                else {
                    @()
                }
                "$lifeCycleState/$resultState $($taskStates -join ', ')"
            } `
            -GetAbortReason {
                param($value)
                $messages = [Collections.Generic.List[string]]::new()
                if ($value.state.PSObject.Properties.Name -contains 'state_message') {
                    $messages.Add([string]$value.state.state_message)
                }
                if ($value.PSObject.Properties.Name -contains 'tasks') {
                    foreach ($task in $value.tasks) {
                        if ($task.state.PSObject.Properties.Name -contains 'state_message') {
                            $messages.Add([string]$task.state.state_message)
                        }
                    }
                }
                $stockout = $messages | Where-Object { $_ -match 'CLOUD_PROVIDER_RESOURCE_STOCKOUT|SkuNotAvailable' } | Select-Object -First 1
                if ($stockout) {
                    'Azure reported a VM capacity stockout. Retry later or use an available SKU/region.'
                }
                elseif ($job.name -eq 'Classic') {
                    $taskStates = if ($value.PSObject.Properties.Name -contains 'tasks') {
                        @($value.tasks | ForEach-Object { $_.state.life_cycle_state })
                    }
                    else {
                        @()
                    }
                    $taskHasStarted = @($taskStates | Where-Object { $_ -in @('RUNNING', 'TERMINATING', 'TERMINATED', 'INTERNAL_ERROR') }).Count -gt 0
                    $startupElapsed = [int]((Get-Date) - $waitStartedAt).TotalSeconds
                    if (-not $taskHasStarted -and $startupElapsed -ge $ClassicStartupTimeoutSeconds) {
                        "Classic compute did not start within $ClassicStartupTimeoutSeconds seconds. The run will be canceled to avoid waiting for the full execution timeout."
                    }
                }
            } `
            -IsComplete { param($value) $value.state.life_cycle_state -in @('TERMINATED', 'SKIPPED', 'INTERNAL_ERROR') }

        $activeRunCompleted = $true
        $results.Add([pscustomobject]@{
            mode = $job.name
            jobId = $job.id
            runId = $activeRunId
            lifeCycleState = $run.state.life_cycle_state
            resultState = $run.state.result_state
            stateMessage = $run.state.state_message
        })
        $activeRunId = $null
    }
}
finally {
    if ($activeRunId -and -not $activeRunCompleted) {
        Write-Warning "Canceling unfinished run $activeRunId..."
        try {
            Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path '/api/2.2/jobs/runs/cancel' -Body @{ run_id = $activeRunId } | Out-Null
            Write-Host "Cancellation requested for run $activeRunId."
        }
        catch {
            Write-Warning "Could not cancel run ${activeRunId}: $($_.Exception.Message)"
        }
    }
}

Write-SanitizedJson -Value $results -Path (Join-Path $PSScriptRoot '..\reports\workload-runs.json')
$failed = @($results | Where-Object resultState -ne 'SUCCESS')
if ($failed.Count) {
    throw "$($failed.Count) workload run(s) failed. See infra\reports\workload-runs.json."
}
$results | Format-Table -AutoSize
