targetScope = 'resourceGroup'

@description('Budget resource name.')
param budgetName string

@description('Monthly budget amount.')
param amount int

@description('Approved budget-notification email recipients.')
param contactEmails array

@description('Budget start date aligned to the first day of a month.')
param startDate string

@description('Budget end date.')
param endDate string

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: budgetName
  properties: {
    amount: amount
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
      endDate: endDate
    }
    notifications: {
      Actual80Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: contactEmails
        contactGroups: []
        contactRoles: []
        locale: 'en-us'
      }
      Forecast100Percent: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: contactEmails
        contactGroups: []
        contactRoles: []
        locale: 'en-us'
      }
    }
  }
}

output budgetId string = budget.id
