[CmdletBinding()]
param(
    [string]$StatePath = (Join-Path $PSScriptRoot '..\reports\databricks-state.json'),
    [int]$TimeoutSeconds = 1200,
    [switch]$SkipSql
)

. (Join-Path $PSScriptRoot 'Workshop.Common.ps1')

Assert-ExpectedSubscription | Out-Null
$state = Read-DeploymentOutputs -Path $StatePath
$results = [Collections.Generic.List[object]]::new()

function Add-ValidationResult {
    param(
        [string]$Name,
        [string]$Scope,
        [ValidateSet('passed', 'failed', 'blocked', 'pending telemetry')][string]$Status,
        [string]$Evidence,
        [string]$Remediation = '',
        [string]$CleanupStatus = 'not applicable'
    )
    $results.Add([pscustomobject]@{
        test = $Name
        scope = $Scope
        status = $Status
        evidence = $Evidence
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        remediation = $Remediation
        cleanupStatus = $CleanupStatus
    })
}

function Invoke-SqlStatement {
    param([string]$Statement)

    $submission = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path '/api/2.0/sql/statements' -Body @{
        warehouse_id = $state.sqlWarehouseId
        statement = $Statement
        wait_timeout = '0s'
        on_wait_timeout = 'CONTINUE'
        disposition = 'INLINE'
        format = 'JSON_ARRAY'
    }
    return Wait-DatabricksState `
        -Description "SQL statement $($submission.statement_id)" `
        -TimeoutSeconds $TimeoutSeconds `
        -Probe { Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.0/sql/statements/$($submission.statement_id)" } `
        -IsComplete { param($value) $value.status.state -in @('SUCCEEDED', 'FAILED', 'CANCELED', 'CLOSED') }
}

try {
    $catalogs = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path '/api/2.1/unity-catalog/catalogs?max_results=100'
    if ($state.catalogName -in @($catalogs.catalogs.name) -and 'samples' -in @($catalogs.catalogs.name)) {
        Add-ValidationResult -Name 'Unity Catalog readiness' -Scope $state.workspaceUrl -Status passed -Evidence "Catalogs '$($state.catalogName)' and 'samples' are available."
    }
    else {
        Add-ValidationResult -Name 'Unity Catalog readiness' -Scope $state.workspaceUrl -Status failed -Evidence 'Required catalogs are missing.' -Remediation 'Attach the workspace to an East US metastore and rerun configuration.'
    }

    $cluster = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.0/clusters/get?cluster_id=$($state.interactiveClusterId)"
    $clusterSafe = $cluster.autotermination_minutes -le 15 -and $cluster.autoscale.max_workers -le 2
    Add-ValidationResult `
        -Name 'Classic compute cost controls' `
        -Scope $state.interactiveClusterId `
        -Status $(if ($clusterSafe) { 'passed' } else { 'failed' }) `
        -Evidence "autotermination=$($cluster.autotermination_minutes), min=$($cluster.autoscale.min_workers), max=$($cluster.autoscale.max_workers), state=$($cluster.state)" `
        -Remediation $(if ($clusterSafe) { '' } else { 'Set auto-termination to 15 minutes or less and maximum workers to 2 or less.' })

    $classicJob = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.2/jobs/get?job_id=$($state.classicJobId)"
    $classicBounded = @(
        $classicJob.settings.tasks |
            Where-Object {
                $retryCount = if ($_.PSObject.Properties.Name -contains 'max_retries') { $_.max_retries } else { 0 }
                $timeout = if ($_.PSObject.Properties.Name -contains 'timeout_seconds') { $_.timeout_seconds } else { 0 }
                $retryCount -gt 0 -or $timeout -gt 2400
            }
    ).Count -eq 0
    Add-ValidationResult -Name 'Classic job definition' -Scope $state.classicJobId -Status $(if ($classicBounded) { 'passed' } else { 'failed' }) -Evidence 'Classic job uses bounded retries/timeouts and ephemeral task compute.'

    $serverlessJob = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.2/jobs/get?job_id=$($state.serverlessJobId)"
    $serverlessTasks = @($serverlessJob.settings.tasks | Where-Object { -not [string]::IsNullOrWhiteSpace($_.environment_key) })
    Add-ValidationResult `
        -Name 'Serverless job definition' `
        -Scope $state.serverlessJobId `
        -Status $(if ($serverlessTasks.Count -eq $serverlessJob.settings.tasks.Count) { 'passed' } else { 'failed' }) `
        -Evidence "$($serverlessTasks.Count) of $($serverlessJob.settings.tasks.Count) tasks use a serverless environment."

    $warehouse = Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.0/sql/warehouses/$($state.sqlWarehouseId)"
    $warehouseSafe = $warehouse.enable_serverless_compute -and $warehouse.auto_stop_mins -le 5 -and $warehouse.max_num_clusters -eq 1
    Add-ValidationResult `
        -Name 'Serverless SQL Warehouse controls' `
        -Scope $state.sqlWarehouseId `
        -Status $(if ($warehouseSafe) { 'passed' } else { 'failed' }) `
        -Evidence "serverless=$($warehouse.enable_serverless_compute), size=$($warehouse.cluster_size), max_clusters=$($warehouse.max_num_clusters), autostop=$($warehouse.auto_stop_mins)"

    if (-not $SkipSql) {
        $validationSqlPath = Join-Path $PSScriptRoot '..\sql\03_validation.sql'
        if (-not (Test-Path -LiteralPath $validationSqlPath)) {
            Add-ValidationResult -Name 'SQL data validation' -Scope $state.sqlWarehouseId -Status blocked -Evidence 'Validation SQL file is missing.' -Remediation 'Create infra/sql/04_validation.sql.'
        }
        else {
            $sqlText = (Get-Content -Raw -LiteralPath $validationSqlPath).Replace('{{CATALOG}}', $state.catalogName).Replace('{{SCHEMA}}', $state.schemaName)
            $statements = @($sqlText -split '(?m)^\s*--\s*COMMAND\s*-+\s*$' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
            foreach ($statement in $statements) {
                $result = Invoke-SqlStatement -Statement $statement
                if ($result.status.state -ne 'SUCCEEDED') {
                    throw "SQL validation failed: $($result.status.error.message)"
                }
            }
            Add-ValidationResult -Name 'SQL data validation' -Scope $state.sqlWarehouseId -Status passed -Evidence "$($statements.Count) validation statement(s) succeeded."
        }

        try {
            $billing = Invoke-SqlStatement -Statement "SELECT COUNT(*) AS records FROM system.billing.usage WHERE usage_start_time >= current_timestamp() - INTERVAL 2 DAYS"
            $billingCount = [int64]$billing.result.data_array[0][0]
            if ($billingCount -gt 0) {
                Add-ValidationResult -Name 'Billing system-table readiness' -Scope 'system.billing.usage' -Status passed -Evidence "$billingCount recent billing records are visible."
            }
            else {
                Add-ValidationResult -Name 'Billing system-table readiness' -Scope 'system.billing.usage' -Status 'pending telemetry' -Evidence 'No recent records are visible yet.' -Remediation 'Rerun Test-WorkshopEnvironment.ps1 after the documented billing-ingestion delay.'
            }
        }
        catch {
            Add-ValidationResult -Name 'Billing system-table readiness' -Scope 'system.billing.usage' -Status 'pending telemetry' -Evidence $_.Exception.Message -Remediation 'Verify system-table permissions and rerun after telemetry ingestion.'
        }
    }
}
catch {
    Add-ValidationResult -Name 'Validation execution' -Scope $state.workspaceUrl -Status failed -Evidence $_.Exception.Message -Remediation 'Resolve the reported API or resource error and rerun validation.'
}
finally {
    try {
        Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path '/api/2.0/clusters/delete' -ExpectedStatusCodes @(200) -Body @{ cluster_id = $state.interactiveClusterId } | Out-Null
        $clusterCleanup = 'interactive cluster termination requested'
    }
    catch {
        $clusterCleanup = "failed: $($_.Exception.Message)"
    }

    try {
        Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path "/api/2.0/sql/warehouses/$($state.sqlWarehouseId)/stop" -ExpectedStatusCodes @(200) | Out-Null
        $warehouseCleanup = 'warehouse stop requested'
    }
    catch {
        $warehouseCleanup = "failed: $($_.Exception.Message)"
    }
    Add-ValidationResult -Name 'Post-test compute shutdown' -Scope $state.workspaceUrl -Status $(if ($clusterCleanup -notlike 'failed*' -and $warehouseCleanup -notlike 'failed*') { 'passed' } else { 'failed' }) -Evidence "Classic: $clusterCleanup; SQL: $warehouseCleanup" -CleanupStatus "$clusterCleanup; $warehouseCleanup"
}

$reportPath = Join-Path $PSScriptRoot '..\reports\validation-summary.json'
Write-SanitizedJson -Value $results -Path $reportPath
$results | Format-Table test, scope, status, evidence -AutoSize

$failures = @($results | Where-Object status -eq 'failed')
if ($failures.Count) {
    throw "$($failures.Count) validation check(s) failed. See $reportPath."
}
Write-Host "Validation completed. Pending telemetry is non-fatal and can be rechecked. Report: $reportPath"
