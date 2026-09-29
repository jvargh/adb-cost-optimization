targetScope = 'subscription'

@description('Azure subscription that is allowed to host the workshop environment.')
param expectedSubscriptionId string = '463a82d4-1896-4332-aeeb-618ee5a5aa93'

@description('Azure region for all regional workshop resources.')
param location string = 'eastus'

@description('Short lowercase alphanumeric suffix used to make resource names unique.')
@minLength(4)
@maxLength(8)
param deploymentSuffix string

@description('Resource owner recorded on Azure tags.')
param owner string

@description('Cost center recorded on Azure tags.')
param costCenter string

@description('ISO-8601 review date for the retained workshop environment.')
param reviewAfter string

@description('Whether to create an Azure Cost Management budget for the workshop resource group.')
param enableBudget bool = false

@description('Monthly budget amount in the billing currency. Used only when enableBudget is true.')
@minValue(1)
param monthlyBudgetAmount int = 250

@description('Approved email recipients for budget alerts. Required when enableBudget is true.')
param budgetContactEmails array = []

@description('Budget start date, aligned to the first day of a month.')
param budgetStartDate string = '2026-09-01'

@description('Budget end date.')
param budgetEndDate string = '2036-09-01'

var resourceGroupName = 'rg-adb-cost-workshop-${deploymentSuffix}'
var managedResourceGroupName = 'mrg-adb-cost-${deploymentSuffix}'
var workspaceName = 'dbw-adb-cost-${deploymentSuffix}'
var storageAccountName = 'stadbcost${deploymentSuffix}'
var accessConnectorName = 'ac-adb-cost-${deploymentSuffix}'
var logAnalyticsName = 'log-adb-cost-${deploymentSuffix}'
var deploymentId = 'adb-cost-${deploymentSuffix}'
var commonTags = {
  Environment: 'workshop'
  Purpose: 'Azure Databricks cost optimization validation'
  Owner: owner
  CostCenter: costCenter
  Workshop: 'L300-Azure-Databricks-Cost-Optimization'
  ManagedBy: 'Bicep'
  DeploymentId: deploymentId
  ReviewAfter: reviewAfter
}

resource workshopResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: commonTags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring-${deploymentSuffix}'
  scope: workshopResourceGroup
  params: {
    location: location
    logAnalyticsName: logAnalyticsName
    tags: commonTags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage-${deploymentSuffix}'
  scope: workshopResourceGroup
  params: {
    location: location
    storageAccountName: storageAccountName
    tags: commonTags
  }
}

module identityRbac 'modules/identity-rbac.bicep' = {
  name: 'identity-rbac-${deploymentSuffix}'
  scope: workshopResourceGroup
  params: {
    location: location
    accessConnectorName: accessConnectorName
    storageAccountName: storage.outputs.storageAccountName
    tags: commonTags
  }
}

module databricks 'modules/databricks-workspace.bicep' = {
  name: 'databricks-${deploymentSuffix}'
  scope: workshopResourceGroup
  params: {
    location: location
    workspaceName: workspaceName
    managedResourceGroupName: managedResourceGroupName
    tags: commonTags
  }
}

module diagnostics 'modules/diagnostics.bicep' = {
  name: 'diagnostics-${deploymentSuffix}'
  scope: workshopResourceGroup
  params: {
    databricksWorkspaceName: databricks.outputs.workspaceName
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
  }
}

module budget 'modules/budget.bicep' = if (enableBudget) {
  name: 'budget-${deploymentSuffix}'
  scope: workshopResourceGroup
  params: {
    budgetName: 'budget-adb-cost-${deploymentSuffix}'
    amount: monthlyBudgetAmount
    contactEmails: budgetContactEmails
    startDate: budgetStartDate
    endDate: budgetEndDate
  }
}

output expectedSubscriptionMatches bool = subscription().subscriptionId == expectedSubscriptionId
output resourceGroupName string = workshopResourceGroup.name
output resourceGroupId string = workshopResourceGroup.id
output workspaceName string = databricks.outputs.workspaceName
output workspaceId string = databricks.outputs.workspaceId
output workspaceUrl string = databricks.outputs.workspaceUrl
output managedResourceGroupName string = managedResourceGroupName
output storageAccountName string = storage.outputs.storageAccountName
output storageAccountId string = storage.outputs.storageAccountId
output accessConnectorName string = identityRbac.outputs.accessConnectorName
output accessConnectorId string = identityRbac.outputs.accessConnectorId
output accessConnectorPrincipalId string = identityRbac.outputs.accessConnectorPrincipalId
output logAnalyticsWorkspaceId string = monitoring.outputs.logAnalyticsWorkspaceId
output deploymentId string = deploymentId
