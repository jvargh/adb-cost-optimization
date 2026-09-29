[CmdletBinding()]
param(
    [string]$StatePath = (Join-Path $PSScriptRoot '..\reports\databricks-state.json'),
    [int]$TimeoutSeconds = 1200
)

. (Join-Path $PSScriptRoot 'Workshop.Common.ps1')

Assert-ExpectedSubscription | Out-Null
$state = Read-DeploymentOutputs -Path $StatePath

function Submit-Sql {
    param([Parameter(Mandatory)][string]$Statement)

    return Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path '/api/2.0/sql/statements' -Body @{
        warehouse_id = $state.sqlWarehouseId
        statement = $Statement
        wait_timeout = '0s'
        on_wait_timeout = 'CONTINUE'
        disposition = 'INLINE'
        format = 'JSON_ARRAY'
    }
}

function Wait-Sql {
    param([Parameter(Mandatory)][string]$StatementId)

    $result = Wait-DatabricksState `
        -Description "SQL statement $StatementId" `
        -TimeoutSeconds $TimeoutSeconds `
        -Probe { Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method GET -Path "/api/2.0/sql/statements/$StatementId" } `
        -IsComplete { param($value) $value.status.state -in @('SUCCEEDED', 'FAILED', 'CANCELED', 'CLOSED') }
    if ($result.status.state -ne 'SUCCEEDED') {
        throw "SQL statement $StatementId failed: $($result.status.error.message)"
    }
    return $result
}

function Get-SqlCommands {
    param([Parameter(Mandatory)][string]$Path)

    $text = Get-Content -Raw -LiteralPath $Path
    $text = $text.Replace('{{CATALOG}}', $state.catalogName).Replace('{{SCHEMA}}', $state.schemaName)
    return @($text -split '(?m)^\s*--\s*COMMAND\s*-+\s*$' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

$sqlRoot = Resolve-Path (Join-Path $PSScriptRoot '..\sql')
$results = [Collections.Generic.List[object]]::new()

try {
    foreach ($command in Get-SqlCommands -Path (Join-Path $sqlRoot '00_setup.sql')) {
        $submission = Submit-Sql -Statement $command
        $result = Wait-Sql -StatementId $submission.statement_id
        $results.Add([pscustomobject]@{ scenario = 'setup'; statementId = $submission.statement_id; state = $result.status.state })
    }

    $comparisonSql = (Get-Content -Raw (Join-Path $sqlRoot '01_baseline_optimized.sql')).Replace('{{CATALOG}}', $state.catalogName).Replace('{{SCHEMA}}', $state.schemaName)
    $comparisonSubmission = Submit-Sql -Statement $comparisonSql
    $comparison = Wait-Sql -StatementId $comparisonSubmission.statement_id
    $differenceCounts = @($comparison.result.data_array | ForEach-Object { [int64]$_[1] })
    if (@($differenceCounts | Where-Object { $_ -ne 0 }).Count) {
        throw 'SQL baseline and optimized result sets are not equivalent.'
    }
    $results.Add([pscustomobject]@{ scenario = 'baseline-optimized'; statementId = $comparisonSubmission.statement_id; state = $comparison.status.state })

    $concurrencyCommands = Get-SqlCommands -Path (Join-Path $sqlRoot '02_bounded_concurrency.sql')
    if ($concurrencyCommands.Count -gt 4) {
        throw "Concurrency script contains $($concurrencyCommands.Count) commands; maximum is 4."
    }
    $submissions = @($concurrencyCommands | ForEach-Object { Submit-Sql -Statement $_ })
    foreach ($submission in $submissions) {
        $result = Wait-Sql -StatementId $submission.statement_id
        $results.Add([pscustomobject]@{ scenario = 'bounded-concurrency'; statementId = $submission.statement_id; state = $result.status.state })
    }

    $validationSql = (Get-Content -Raw (Join-Path $sqlRoot '03_validation.sql')).Replace('{{CATALOG}}', $state.catalogName).Replace('{{SCHEMA}}', $state.schemaName)
    $validationSubmission = Submit-Sql -Statement $validationSql
    $validation = Wait-Sql -StatementId $validationSubmission.statement_id
    $failedRows = @($validation.result.data_array | Where-Object { $_[2] -ne 'PASS' })
    if ($failedRows.Count) {
        throw "$($failedRows.Count) SQL table validation row(s) failed."
    }
    $results.Add([pscustomobject]@{ scenario = 'validation'; statementId = $validationSubmission.statement_id; state = $validation.status.state })
}
finally {
    try {
        Invoke-DatabricksApi -WorkspaceUrl $state.workspaceUrl -Method POST -Path "/api/2.0/sql/warehouses/$($state.sqlWarehouseId)/stop" -ExpectedStatusCodes @(200) | Out-Null
    }
    catch {
        Write-Warning "Unable to request warehouse stop: $($_.Exception.Message)"
    }
    Write-SanitizedJson -Value $results -Path (Join-Path $PSScriptRoot '..\reports\sql-workload-runs.json')
}

$results | Format-Table -AutoSize
