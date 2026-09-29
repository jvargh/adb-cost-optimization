targetScope = 'resourceGroup'

@description('Existing Azure Databricks workspace name.')
param databricksWorkspaceName string

@description('Destination Log Analytics workspace resource ID.')
param logAnalyticsWorkspaceId string

resource databricksWorkspace 'Microsoft.Databricks/workspaces@2024-05-01' existing = {
  name: databricksWorkspaceName
}

resource diagnosticSetting 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-adb-cost-workshop'
  scope: databricksWorkspace
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
  }
}

output diagnosticSettingName string = diagnosticSetting.name
