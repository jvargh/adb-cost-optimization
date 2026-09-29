[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory)][ValidatePattern('^rg-adb-cost-workshop-[a-z0-9]{4,8}$')][string]$ResourceGroupName,
    [string]$ExpectedSubscriptionId = '463a82d4-1896-4332-aeeb-618ee5a5aa93',
    [Parameter(Mandatory)][string]$ExpectedDeploymentId,
    [switch]$AcknowledgePermanentDeletion
)

. (Join-Path $PSScriptRoot 'Workshop.Common.ps1')

Assert-ExpectedSubscription -ExpectedSubscriptionId $ExpectedSubscriptionId | Out-Null
if (-not $AcknowledgePermanentDeletion) {
    throw 'Pass -AcknowledgePermanentDeletion only after reviewing the exact resource-group scope.'
}

$resourceGroup = az group show --name $ResourceGroupName --subscription $ExpectedSubscriptionId --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $null -eq $resourceGroup) {
    throw "Resource group '$ResourceGroupName' does not exist."
}
if ($resourceGroup.tags.Workshop -ne 'L300-Azure-Databricks-Cost-Optimization') {
    throw "Resource group '$ResourceGroupName' does not have the required workshop tag."
}
if ($resourceGroup.tags.ManagedBy -ne 'Bicep') {
    throw "Resource group '$ResourceGroupName' is not marked as Bicep-managed."
}
if ($resourceGroup.tags.DeploymentId -ne $ExpectedDeploymentId) {
    throw "DeploymentId '$($resourceGroup.tags.DeploymentId)' does not match '$ExpectedDeploymentId'."
}

$resources = az resource list --resource-group $ResourceGroupName --subscription $ExpectedSubscriptionId --output json | ConvertFrom-Json
Write-Host "Deletion preview for ${ResourceGroupName}:"
$resources | Select-Object name, type, location | Format-Table -AutoSize

if ($PSCmdlet.ShouldProcess(
        "/subscriptions/$ExpectedSubscriptionId/resourceGroups/$ResourceGroupName",
        'Permanently delete the isolated workshop resource group and its resources'
    )) {
    az group delete `
        --name $ResourceGroupName `
        --subscription $ExpectedSubscriptionId `
        --yes `
        --no-wait
    if ($LASTEXITCODE -ne 0) {
        throw 'Resource-group deletion request failed.'
    }
    Write-Host 'Deletion request accepted. The Databricks-managed resource group is removed by the workspace provider.'
}
