function Invoke-DatabricksBillingCollector {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

    foreach ($workspace in @($Config.databricks.workspaces | Where-Object include)) {
        $startedAt = Get-Date
        $parameters = New-DatabricksTimeParameters -Config $Config
        $sources = @(
            Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.billing.usage' -FileName 'DatabricksBillingUsage.sql' -OutputName 'billing-usage' -Parameters $parameters
            Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.billing.list_prices' -FileName 'DatabricksListPrices.sql' -OutputName 'billing-list-prices' -Parameters $parameters
        )
        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'billing' -Sources $sources
        $outputs = @($sources | Where-Object output | ForEach-Object output) + @($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks billing [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources $sources) -StartedAt $startedAt -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs $outputs -Limitations $limitations
    }
}
