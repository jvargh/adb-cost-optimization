[CmdletBinding()]
param(
    [string]$StatePath = (Join-Path $PSScriptRoot '..\reports\databricks-state.json'),
    [int]$TimeoutSeconds = 1800,
    [ValidateRange(5, 300)][int]$PollSeconds = 15
)

. (Join-Path $PSScriptRoot 'Workshop.Common.ps1')

Assert-ExpectedSubscription | Out-Null
$state = Read-DeploymentOutputs -Path $StatePath
$submit = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path '/api/2.2/jobs/runs/submit' -Body @{
    run_name = "l300-sample-setup-$((Get-Date).ToString('yyyyMMdd-HHmmss'))"
    timeout_seconds = $TimeoutSeconds
    environments = @(@{ environment_key = 'serverless'; spec = @{ client = '1' } })
    tasks = @(
        @{
            task_key = 'setup_sample_data'
            environment_key = 'serverless'
            timeout_seconds = $TimeoutSeconds
            max_retries = 0
            notebook_task = @{
                notebook_path = '/Shared/adb-cost-workshop/00_setup_data'
                source = 'WORKSPACE'
                base_parameters = @{
                    catalog = $state.catalogName
                    schema = $state.schemaName
                    max_rows = '250000'
                }
            }
        }
    )
}

$run = Wait-DatabricksState `
    -Description "sample data run $($submit.run_id)" `
    -TimeoutSeconds $TimeoutSeconds `
    -PollSeconds $PollSeconds `
    -Probe { Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.2/jobs/runs/get?run_id=$($submit.run_id)" } `
    -GetStatusText {
        param($value)
        "$($value.state.life_cycle_state)/$($value.state.result_state)"
    } `
    -IsComplete { param($value) $value.state.life_cycle_state -in @('TERMINATED', 'SKIPPED', 'INTERNAL_ERROR') }

if ($run.state.result_state -ne 'SUCCESS') {
    throw "Sample-data setup failed: $($run.state.state_message)"
}
Write-Host "Sample data initialized successfully in run $($submit.run_id)."
