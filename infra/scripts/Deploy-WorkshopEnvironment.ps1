[CmdletBinding()]
param(
    [string]$Location = 'eastus',
    [string]$ParameterFile = (Join-Path $PSScriptRoot '..\main.bicepparam'),
    [string]$ExpectedSubscriptionId = '463a82d4-1896-4332-aeeb-618ee5a5aa93',
    [switch]$Deploy,
    [switch]$AcknowledgeCostRisk
)

. (Join-Path $PSScriptRoot 'Workshop.Common.ps1')

$account = Assert-ExpectedSubscription -ExpectedSubscriptionId $ExpectedSubscriptionId
$mainBicep = (Resolve-Path (Join-Path $PSScriptRoot '..\main.bicep')).Path
$parameterFilePath = (Resolve-Path $ParameterFile).Path
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$deploymentName = "adb-cost-workshop-$timestamp"
$reportsDirectory = Join-Path $PSScriptRoot '..\reports'
New-Item -ItemType Directory -Path $reportsDirectory -Force | Out-Null

Write-Host "Validating Bicep for subscription $($account.name) ($($account.id))..."
az bicep build --file $mainBicep
if ($LASTEXITCODE -ne 0) {
    throw 'Bicep build failed.'
}

Write-Host 'Running subscription deployment what-if...'
$whatIfPath = Join-Path $reportsDirectory "what-if-$timestamp.json"
az deployment sub what-if `
    --name $deploymentName `
    --location $Location `
    --template-file $mainBicep `
    --parameters $parameterFilePath `
    --result-format FullResourcePayloads `
    --output json | Set-Content -LiteralPath $whatIfPath -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    throw 'Azure deployment what-if failed.'
}

Write-Host "What-if output: $whatIfPath"
if (-not $Deploy) {
    Write-Host 'Preview completed. Re-run with -Deploy -AcknowledgeCostRisk only after reviewing the what-if output.'
    return
}

if (-not $AcknowledgeCostRisk) {
    throw 'Deployment creates billable Azure and Databricks resources. Pass -AcknowledgeCostRisk after reviewing the preview.'
}

Write-Host 'Deploying in incremental mode...'
$deployment = az deployment sub create `
    --name $deploymentName `
    --location $Location `
    --template-file $mainBicep `
    --parameters $parameterFilePath `
    --output json | ConvertFrom-Json -Depth 100
if ($LASTEXITCODE -ne 0) {
    throw 'Azure deployment failed.'
}

$outputs = @{}
foreach ($property in $deployment.properties.outputs.PSObject.Properties) {
    $outputs[$property.Name] = $property.Value.value
}
if (-not $outputs.expectedSubscriptionMatches) {
    throw 'The deployed template reports a subscription mismatch.'
}

$outputsPath = Join-Path $reportsDirectory 'deployment-outputs.json'
Write-SanitizedJson -Value $outputs -Path $outputsPath
Write-Host "Deployment succeeded. Sanitized outputs: $outputsPath"
Write-Host 'Next: run Configure-DatabricksWorkspace.ps1 after verifying Unity Catalog and serverless eligibility.'
