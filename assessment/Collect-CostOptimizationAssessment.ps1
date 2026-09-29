[CmdletBinding()]
param(
    [string]$ConfigPath = (Join-Path $PSScriptRoot 'config\assessment-scope.example.json'),
    [switch]$SkipAzure,
    [switch]$SkipDatabricks,
    [switch]$SkipAnalysis,
    [switch]$CostReadinessOnly,
    [switch]$ContinueOnCollectorError,
    [switch]$PassThru,
    [string]$ExistingRunRoot
)

. (Join-Path $PSScriptRoot 'scripts\Assessment.Common.ps1')

$toolkitVersion = '0.1.0'
if ($CostReadinessOnly -and -not $SkipAnalysis) {
    throw 'CostReadinessOnly requires SkipAnalysis; an access probe cannot be used as assessment cost evidence.'
}
$config = Read-AssessmentConfig -Path $ConfigPath
Assert-ReadOnlyAssessment -Config $config

$progressPlan = @(
    @{ id = 'scope'; title = 'Read configuration and check scope' }
    @{ id = 'safety'; title = 'Check scripts are read-only' }
    Get-AssessmentCollectorPlan | Where-Object {
        ($_.domain -eq 'Azure' -and -not $SkipAzure) -or
        ($_.domain -eq 'Databricks' -and -not $SkipDatabricks)
    } | ForEach-Object { @{ id = $_.id; title = $_.title } }
    @{ id = 'finish'; title = 'Save check results' }
)
Write-AssessmentProgress -Event @{ steps = $progressPlan }
Write-AssessmentProgress -Event @{ id = 'scope'; status = 'pass'; detail = 'Configuration and read-only settings checked.' }
Write-AssessmentProgress -Event @{ id = 'safety'; status = 'running'; detail = 'Scanning assessment scripts.' }
& (Join-Path $PSScriptRoot 'scripts\Test-AssessmentReadOnly.ps1') -Path $PSScriptRoot | Out-Host
Write-AssessmentProgress -Event @{ id = 'safety'; status = 'pass'; detail = 'Read-only script scan completed.' }

if ($ExistingRunRoot) {
    $runRoot = [IO.Path]::GetFullPath($ExistingRunRoot)
    $manifestPath = Join-Path $runRoot 'assessment-manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Existing run root '$runRoot' does not contain assessment-manifest.json."
    }
    $runContext = [pscustomobject]@{
        RunId = Split-Path -Leaf $runRoot
        Root = $runRoot
        Manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -Depth 100
    }
}
else {
    $runContext = New-AssessmentRun -Config $config -ToolkitVersion $toolkitVersion
}

$logPath = Join-Path $runContext.Root 'logs\assessment.log'
$runContext | Add-Member -NotePropertyName CostReadinessOnly -NotePropertyValue $CostReadinessOnly.IsPresent
Start-Transcript -Path $logPath -Append | Out-Null
$collectorResults = [Collections.Generic.List[object]]::new()
$runFailed = $false

try {
    Write-Host "Assessment run: $($runContext.RunId)"
    Write-Host "Output root: $($runContext.Root)"
    Write-Host "Analysis window: $($config.analysis.startUtc) through $($config.analysis.endUtc)"

    Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'collectors') -Filter '*.ps1' -ErrorAction SilentlyContinue |
        Sort-Object Name |
        ForEach-Object { . $_.FullName }

    $domains = @()
    if (-not $SkipAzure) {
        $domains += @{
            Name = 'Azure'
            Command = 'Invoke-AzureAssessmentCollectors'
        }
    }
    if (-not $SkipDatabricks) {
        $domains += @{
            Name = 'Databricks'
            Command = 'Invoke-DatabricksAssessmentCollectors'
        }
    }

    foreach ($domain in $domains) {
        Write-Host "Collecting $($domain.Name) evidence..."
        $command = Get-Command $domain.Command -ErrorAction SilentlyContinue
        if (-not $command) {
            $result = New-CollectorResult -Name $domain.Name -Status failed -StartedAt (Get-Date) -ErrorMessage "Collector entry point '$($domain.Command)' is unavailable."
            $collectorResults.Add($result)
            $runFailed = $true
            if (-not $ContinueOnCollectorError) {
                throw $result.error
            }
            continue
        }
        try {
            $domainResults = & $command -Config $config -RunContext $runContext
            foreach ($result in @($domainResults)) {
                $collectorResults.Add($result)
                Write-Host "  $($result.name): $($result.status) ($($result.itemCount) items)"
                if ($result.status -eq 'failed') {
                    $runFailed = $true
                }
            }
        }
        catch {
            $runFailed = $true
            $collectorResults.Add((New-CollectorResult -Name $domain.Name -Status failed -StartedAt (Get-Date) -ErrorMessage $_.Exception.Message))
            if (-not $ContinueOnCollectorError) {
                throw
            }
        }
    }

    Write-AssessmentProgress -Event @{ id = 'finish'; status = 'running'; detail = 'Saving check results.' }
    Write-JsonFile -Value $collectorResults -Path (Join-Path $runContext.Root 'collection-status.json')

    if (-not $SkipAnalysis) {
        $python = Get-Command python -ErrorAction SilentlyContinue
        $pipeline = Join-Path $PSScriptRoot 'pipeline\run_assessment.py'
        if ($python -and (Test-Path -LiteralPath $pipeline)) {
            Write-Host 'Normalizing, detecting, reconciling, and rendering reports...'
            & $python.Source $pipeline --config $ConfigPath --run-root $runContext.Root | Out-Host
            if ($LASTEXITCODE -ne 0) {
                throw "Assessment analysis pipeline exited with code $LASTEXITCODE."
            }
        }
        else {
            Write-Warning 'Analysis pipeline is unavailable; collection outputs were preserved.'
            $runFailed = $true
        }
    }
}
catch {
    $runFailed = $true
    Write-Error $_
}
finally {
    $manifestPath = Join-Path $runContext.Root 'assessment-manifest.json'
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json -Depth 100
    $manifest.status = Get-AssessmentRunStatus -CollectorResults @($collectorResults)
    $manifest.completedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    $manifest.collectors = @($collectorResults)
    Write-JsonFile -Value $manifest -Path $manifestPath
    Stop-Transcript | Out-Null
}

if ($runFailed -and -not $ContinueOnCollectorError) {
    throw "Assessment run '$($runContext.RunId)' did not complete successfully. Review collection-status.json and logs."
}

Write-Host "Assessment run completed with status: $(Get-AssessmentRunStatus -CollectorResults @($collectorResults))"
Write-AssessmentProgress -Event @{ id = 'finish'; status = 'pass'; detail = 'Check results saved.' }
if ($SkipAnalysis) {
    Write-Host "Collection status: $(Join-Path $runContext.Root 'collection-status.json')"
    Write-Host 'Analysis and report generation were skipped for this readiness run.'
}
else {
    Write-Host "Reports: $(Join-Path $runContext.Root 'reports')"
}
if ($PassThru) {
    $runContext
}
