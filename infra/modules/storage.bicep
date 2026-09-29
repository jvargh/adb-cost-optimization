targetScope = 'resourceGroup'

@description('Azure region for the storage account.')
param location string

@description('Globally unique lowercase storage account name.')
param storageAccountName string

@description('Tags applied to storage resources.')
param tags object

//checkov:skip=CKV_AZURE_35:Public routing is required for both serverless and Classic workshop access; shared keys and anonymous blob access remain disabled.
//checkov:skip=CKV_AZURE_59:Public routing is an approved lab tradeoff; authentication is Entra-only and containers disallow public access.
//checkov:skip=CKV_AZURE_43:The globally unique name is supplied through a validated lowercase alphanumeric Bicep parameter.
//checkov:skip=CKV_AZURE_206:LRS is an approved cost optimization for reproducible non-production sample data that can be regenerated.
resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    isHnsEnabled: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = [for containerName in [
  'source'
  'checkpoints'
  'exports'
]: {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}]

output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output dfsEndpoint string = storageAccount.properties.primaryEndpoints.dfs
