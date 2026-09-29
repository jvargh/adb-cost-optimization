targetScope = 'resourceGroup'

@description('Azure region for Log Analytics.')
param location string

@description('Log Analytics workspace name.')
param logAnalyticsName string

@description('Tags applied to monitoring resources.')
param tags object

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
  #disable-next-line BCP187
  sku: {
    name: 'PerGB2018'
  }
}

output logAnalyticsWorkspaceId string = logAnalytics.id
output logAnalyticsWorkspaceName string = logAnalytics.name
