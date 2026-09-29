targetScope = 'resourceGroup'

@description('Azure region for the Access Connector.')
param location string

@description('Azure Databricks Access Connector name.')
param accessConnectorName string

@description('Existing workshop storage account name.')
param storageAccountName string

@description('Tags applied to the Access Connector.')
param tags object

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageAccountName
}

resource accessConnector 'Microsoft.Databricks/accessConnectors@2024-05-01' = {
  name: accessConnectorName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

var storageBlobDataContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, accessConnector.id, storageBlobDataContributorRoleId)
  properties: {
    principalId: accessConnector.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleId
    description: 'Allows the workshop Access Connector to read and write workshop ADLS Gen2 data.'
  }
}

output accessConnectorName string = accessConnector.name
output accessConnectorId string = accessConnector.id
output accessConnectorPrincipalId string = accessConnector.identity.principalId
