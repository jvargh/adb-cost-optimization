[CmdletBinding()]
param(
    [string]$Path = (Join-Path $PSScriptRoot '..')
)

$forbiddenCommandPatterns = @(
    '\baz\s+(group|resource|vm|storage|databricks|deployment)\s+(create|delete|update)\b',
    '/api/[^\s''"]+/(create|edit|delete|reset|run-now|cancel|start|stop|restart)',
    '\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|MERGE|OPTIMIZE|VACUUM|RESTORE|TRUNCATE)\s+'
)
$violations = [Collections.Generic.List[string]]::new()
$targets = @()
$collectorRoot = Join-Path $Path 'collectors'
if (Test-Path -LiteralPath $collectorRoot) {
    $targets += Get-ChildItem -LiteralPath $collectorRoot -File -Recurse | Where-Object Extension -in @('.ps1', '.py', '.sql')
}
$entryPoint = Join-Path $Path 'Collect-CostOptimizationAssessment.ps1'
if (Test-Path -LiteralPath $entryPoint) {
    $targets += Get-Item -LiteralPath $entryPoint
}
$targets | ForEach-Object {
    $content = Get-Content -Raw -LiteralPath $_.FullName
    foreach ($pattern in $forbiddenCommandPatterns) {
        if ($content -match $pattern) {
            $violations.Add("$($_.FullName): matches forbidden mutation pattern '$pattern'")
        }
    }
}
if ($violations.Count) {
    $violations
    throw 'Assessment toolkit read-only safety validation failed.'
}
Write-Output 'AssessmentReadOnlySafety=PASS'
