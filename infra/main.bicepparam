using './main.bicep'

param expectedSubscriptionId = '463a82d4-1896-4332-aeeb-618ee5a5aa93'
param location = 'eastus'
param deploymentSuffix = 'l300c01'
param owner = 'admin@MngEnvMCAP993834.onmicrosoft.com'
param costCenter = 'Engineering'
param reviewAfter = '2026-12-31'
param enableBudget = false
param monthlyBudgetAmount = 250
param budgetContactEmails = []
param budgetStartDate = '2026-09-01'
param budgetEndDate = '2036-09-01'
