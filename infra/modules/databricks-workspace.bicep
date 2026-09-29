targetScope = 'resourceGroup'

@description('Azure region for the Azure Databricks workspace.')
param location string

@description('Azure Databricks workspace name.')
param workspaceName string

@description('Dedicated managed resource group name created by Azure Databricks.')
param managedResourceGroupName string

@description('Tags applied to the Azure Databricks workspace.')
param tags object

//checkov:skip=CKV2_AZURE_48:Customer-managed keys are intentionally omitted for the isolated non-production workshop; platform-managed encryption is accepted in the approved plan.
//checkov:skip=CKV_AZURE_158:Private Link is intentionally omitted for this non-production workshop so serverless and facilitator administration remain reproducible without private DNS and egress infrastructure.
resource workspace 'Microsoft.Databricks/workspaces@2024-05-01' = {
  name: workspaceName
  location: location
  tags: tags
  sku: {
    name: 'premium'
  }
  properties: {
    managedResourceGroupId: subscriptionResourceId('Microsoft.Resources/resourceGroups', managedResourceGroupName)
    publicNetworkAccess: 'Enabled'
    requiredNsgRules: 'AllRules'
    parameters: {
      enableNoPublicIp: {
        value: true
      }
    }
  }
}

output workspaceName string = workspace.name
output workspaceId string = workspace.id
output workspaceUrl string = workspace.properties.workspaceUrl
