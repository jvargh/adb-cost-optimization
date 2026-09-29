[CmdletBinding()]
param(
    [ValidateSet('Initialize', 'Run', 'Readiness', 'Reports', 'Open', 'Validate')]
    [string]$Action = 'Run',

    [string]$ConfigPath,
    [string]$RunRoot,
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'output'),

    [switch]$SelectScope,
    [ValidateNotNullOrEmpty()][string[]]$SubscriptionIds = @(),
    [ValidateNotNullOrEmpty()][string[]]$ResourceGroups = @(),
    [switch]$ApproveSqlWarehouseAutoStart,
    [switch]$ContinueOnCollectorError,
    [switch]$FailOnCollectorError,
    [switch]$Force,
    [switch]$OpenReport,
    [switch]$NoOpenReport
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$exampleConfig = Join-Path $PSScriptRoot 'config\assessment-scope.example.json'
$workshopConfig = Join-Path $PSScriptRoot 'config\workshop-scope.json'
$localConfig = Join-Path $PSScriptRoot 'config\assessment-scope.local.json'
$collector = Join-Path $PSScriptRoot 'Collect-CostOptimizationAssessment.ps1'
$pipeline = Join-Path $PSScriptRoot 'pipeline\run_assessment.py'
$safetyCheck = Join-Path $PSScriptRoot 'scripts\Test-AssessmentReadOnly.ps1'
$invocationDirectory = (Get-Location).Path
$hasScopeSelection = $SelectScope -or $SubscriptionIds.Count -gt 0 -or $ResourceGroups.Count -gt 0
if ($hasScopeSelection -and $Action -notin @('Run', 'Readiness')) {
    throw 'Scope selection is supported only for Run and Readiness. Reports uses the scope saved with the run.'
}
if ($SelectScope -and ($SubscriptionIds.Count -gt 0 -or $ResourceGroups.Count -gt 0)) {
    throw 'Use -SelectScope or explicit -SubscriptionIds/-ResourceGroups, not both.'
}
if ($PSBoundParameters.ContainsKey('OutputRoot')) {
    $OutputRoot = [IO.Path]::GetFullPath($OutputRoot, $invocationDirectory)
}
$temporaryConfig = $null

function Resolve-AssessmentConfigPath {
    if ($ConfigPath) {
        $path = [IO.Path]::GetFullPath($ConfigPath, $invocationDirectory)
        return (Resolve-Path -LiteralPath $path).Path
    }
    if (Test-Path -LiteralPath $localConfig) {
        return $localConfig
    }
    if (Test-Path -LiteralPath $workshopConfig) {
        return $workshopConfig
    }
    return $exampleConfig
}

function Get-LatestAssessmentRun {
    if (-not (Test-Path -LiteralPath $OutputRoot)) {
        return $null
    }
    return Get-ChildItem -LiteralPath $OutputRoot -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'assessment-manifest.json') } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

function Resolve-AssessmentRunRoot {
    param([Parameter(Mandatory)][string]$Path)

    if ([IO.Path]::IsPathRooted($Path)) {
        return (Get-Item -LiteralPath $Path).FullName
    }
    $fromInvocationDirectory = Join-Path $invocationDirectory $Path
    if (Test-Path -LiteralPath $fromInvocationDirectory) {
        return (Get-Item -LiteralPath $fromInvocationDirectory).FullName
    }
    $fromAssessmentDirectory = Join-Path $PSScriptRoot $Path
    if (Test-Path -LiteralPath $fromAssessmentDirectory) {
        return (Get-Item -LiteralPath $fromAssessmentDirectory).FullName
    }
    throw "Assessment run root '$Path' does not exist relative to '$invocationDirectory' or '$PSScriptRoot'."
}

function Assert-SqlWarehouseApproval {
    param([Parameter(Mandatory)][string]$ResolvedConfigPath)

    $config = Get-Content -Raw -LiteralPath $ResolvedConfigPath | ConvertFrom-Json -Depth 100
    $globalWarehouse = if ($config.databricks.PSObject.Properties.Name -contains 'sqlWarehouseId') {
        [string]$config.databricks.sqlWarehouseId
    }
    else {
        ''
    }
    $workspaceWarehouses = @(
        $config.databricks.workspaces |
            Where-Object { $_.PSObject.Properties.Name -contains 'sqlWarehouseId' -and -not [string]::IsNullOrWhiteSpace([string]$_.sqlWarehouseId) }
    )
    $persistedApproval = if ($config.databricks.PSObject.Properties.Name -contains 'allowSqlWarehouseAutoStart') {
        [bool]$config.databricks.allowSqlWarehouseAutoStart
    }
    else {
        $false
    }
    if ((-not [string]::IsNullOrWhiteSpace($globalWarehouse) -or $workspaceWarehouses.Count -gt 0) -and -not $ApproveSqlWarehouseAutoStart -and -not $persistedApproval) {
        throw 'The selected scope config contains a SQL Warehouse ID but has not approved auto-start. Set databricks.allowSqlWarehouseAutoStart=true once in the scope, pass -ApproveSqlWarehouseAutoStart, or remove sqlWarehouseId.'
    }
    if ($persistedApproval -and -not $ApproveSqlWarehouseAutoStart) {
        Write-Host 'SQL Warehouse auto-start approval is recorded in the selected scope.'
    }
}

function New-ReadinessConfig {
    param(
        [Parameter(Mandatory)][string]$ResolvedConfigPath,
        [Parameter(Mandatory)][bool]$IncludeSqlWarehouse
    )

    if ($IncludeSqlWarehouse) {
        return [pscustomobject]@{
            Path = $ResolvedConfigPath
            IsTemporary = $false
        }
    }

    $config = Get-Content -Raw -LiteralPath $ResolvedConfigPath | ConvertFrom-Json -Depth 100
    $removedWarehouse = $false
    if ($config.databricks.PSObject.Properties.Name -contains 'sqlWarehouseId') {
        $config.databricks.PSObject.Properties.Remove('sqlWarehouseId')
        $removedWarehouse = $true
    }
    foreach ($workspace in @($config.databricks.workspaces)) {
        if ($workspace.PSObject.Properties.Name -contains 'sqlWarehouseId') {
            $workspace.PSObject.Properties.Remove('sqlWarehouseId')
            $removedWarehouse = $true
        }
    }

    if (-not $removedWarehouse) {
        return [pscustomobject]@{
            Path = $ResolvedConfigPath
            IsTemporary = $false
        }
    }

    $temporaryPath = Join-Path ([IO.Path]::GetTempPath()) ("adb-assessment-readiness-{0}.json" -f [guid]::NewGuid().ToString('N'))
    $config | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $temporaryPath -Encoding utf8
    Write-Host 'Readiness mode: SQL Warehouse IDs were omitted, so system-table SQL will be reported as unavailable and no Warehouse auto-start is requested.'
    Write-Host 'Use -ApproveSqlWarehouseAutoStart only when readiness must test SQL-backed sources.'
    return [pscustomobject]@{
        Path = $temporaryPath
        IsTemporary = $true
    }
}

function Open-AssessmentReport {
    param([Parameter(Mandatory)][string]$AssessmentRunRoot)

    $report = Join-Path $AssessmentRunRoot 'reports\assessment-report.md'
    if (-not (Test-Path -LiteralPath $report)) {
        throw "Report index '$report' does not exist."
    }
    Write-Host "Report index: $report"
    Invoke-Item -LiteralPath $report
}

Push-Location $repositoryRoot
try {
    if ($Action -in @('Run', 'Readiness')) {
        $resolvedConfig = Resolve-AssessmentConfigPath
        . (Join-Path $PSScriptRoot 'scripts\Assessment.Common.ps1')
        $effectiveConfig = Read-AssessmentConfig -Path $resolvedConfig -AllowEmptyScope:$hasScopeSelection
        if ($hasScopeSelection) {
            . (Join-Path $PSScriptRoot 'collectors\Azure.AssessmentCollectors.ps1')
            . (Join-Path $PSScriptRoot 'scripts\Assessment.Scope.ps1')
            $effectiveConfig = New-AssessmentScopeConfig -Config $effectiveConfig -SelectScope:$SelectScope `
                -SubscriptionIds $SubscriptionIds -ResourceGroups $ResourceGroups
        }
        if ($PSBoundParameters.ContainsKey('OutputRoot')) {
            $effectiveConfig.outputs.root = $OutputRoot
        }
        else {
            $OutputRoot = [IO.Path]::GetFullPath([string]$effectiveConfig.outputs.root, $repositoryRoot)
        }
        if ($hasScopeSelection -or $PSBoundParameters.ContainsKey('OutputRoot')) {
            $temporaryConfig = Join-Path ([IO.Path]::GetTempPath()) ("adb-assessment-scope-{0}.json" -f [guid]::NewGuid().ToString('N'))
            Write-JsonFile -Value $effectiveConfig -Path $temporaryConfig
            $resolvedConfig = $temporaryConfig
        }
    }
    switch ($Action) {
        'Initialize' {
            if ((Test-Path -LiteralPath $localConfig) -and -not $Force) {
                Write-Host "Local scope already exists: $localConfig"
                Write-Host 'Use -Force to replace it from the example.'
                break
            }
            Copy-Item -LiteralPath $exampleConfig -Destination $localConfig -Force
            Write-Host "Created: $localConfig"
            Write-Host 'Edit this file before collecting a customer estate.'
            Invoke-Item -LiteralPath $localConfig
        }

        'Validate' {
            $resolvedConfig = Resolve-AssessmentConfigPath
            Write-Host "Validating toolkit with config: $resolvedConfig"
            & $safetyCheck -Path $PSScriptRoot
            if ($LASTEXITCODE -ne 0) {
                throw 'Read-only safety validation failed.'
            }
            $pesterResult = Invoke-Pester -Path (Join-Path $PSScriptRoot 'tests') -Output Normal -PassThru
            if ($pesterResult.FailedCount -gt 0) {
                throw "Pester validation failed: $($pesterResult.FailedCount) test(s) failed."
            }
            python -m unittest -v `
                assessment.tests.test_assessment_contracts `
                assessment.tests.model.test_model_pipeline `
                assessment.tests.reports.test_reports
            if ($LASTEXITCODE -ne 0) {
                throw 'Python validation failed.'
            }
            Write-Host 'Toolkit validation passed.'
        }

        'Readiness' {
            $readinessConfig = New-ReadinessConfig `
                -ResolvedConfigPath $resolvedConfig `
                -IncludeSqlWarehouse $ApproveSqlWarehouseAutoStart.IsPresent
            try {
                Write-Host "Running read-only source readiness with: $resolvedConfig"
                & $collector `
                    -ConfigPath $readinessConfig.Path `
                    -SkipAnalysis `
                    -CostReadinessOnly `
                    -ContinueOnCollectorError
            }
            finally {
                if ($readinessConfig.IsTemporary -and (Test-Path -LiteralPath $readinessConfig.Path)) {
                    Remove-Item -LiteralPath $readinessConfig.Path -Force
                }
            }
        }

        'Run' {
            Assert-SqlWarehouseApproval -ResolvedConfigPath $resolvedConfig
            Write-Host "Running full read-only assessment with: $resolvedConfig"
            $collectorParameters = @{
                ConfigPath = $resolvedConfig
                PassThru = $true
            }
            if (-not $FailOnCollectorError -or $ContinueOnCollectorError) {
                $collectorParameters.ContinueOnCollectorError = $true
            }
            $run = & $collector @collectorParameters
            if (-not $run -or -not (Test-Path -LiteralPath (Join-Path $run.Root 'reports\assessment-report.md'))) {
                throw 'Assessment completed without producing a run directory.'
            }
            Write-Host ''
            Write-Host "Assessment run: $($run.RunId)"
            Write-Host "Report: $(Join-Path $run.Root 'reports\assessment-report.md')"
            if (-not $NoOpenReport -or $OpenReport) {
                Open-AssessmentReport -AssessmentRunRoot $run.Root
            }
        }

        'Reports' {
            $selectedRun = if ($RunRoot) {
                Get-Item -LiteralPath (Resolve-AssessmentRunRoot -Path $RunRoot)
            }
            else {
                Get-LatestAssessmentRun
            }
            if (-not $selectedRun) {
                throw 'No assessment run was found. Supply -RunRoot or run -Action Run first.'
            }
            $savedConfig = Join-Path $selectedRun.FullName 'assessment-config.json'
            $resolvedConfig = if (-not $ConfigPath -and (Test-Path -LiteralPath $savedConfig)) {
                $savedConfig
            }
            else {
                Resolve-AssessmentConfigPath
            }
            Write-Host "Recreating reports from: $($selectedRun.FullName)"
            python $pipeline --config $resolvedConfig --run-root $selectedRun.FullName
            if ($LASTEXITCODE -ne 0) {
                throw 'Report recreation failed.'
            }
            Write-Host "Report recreated: $(Join-Path $selectedRun.FullName 'reports\assessment-report.md')"
            if (-not $NoOpenReport -or $OpenReport) {
                Open-AssessmentReport -AssessmentRunRoot $selectedRun.FullName
            }
        }

        'Open' {
            $selectedRun = if ($RunRoot) {
                Get-Item -LiteralPath (Resolve-AssessmentRunRoot -Path $RunRoot)
            }
            else {
                Get-LatestAssessmentRun
            }
            if (-not $selectedRun) {
                throw 'No assessment run was found. Supply -RunRoot or run -Action Run first.'
            }
            Open-AssessmentReport -AssessmentRunRoot $selectedRun.FullName
        }
    }
}
finally {
    if ($temporaryConfig -and (Test-Path -LiteralPath $temporaryConfig)) {
        Remove-Item -LiteralPath $temporaryConfig -Force
    }
    Pop-Location
}
