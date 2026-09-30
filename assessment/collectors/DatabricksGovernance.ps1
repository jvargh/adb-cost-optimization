function Invoke-DatabricksGovernanceCollector {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

    foreach ($workspace in @($Config.databricks.workspaces | Where-Object include)) {
        $startedAt = Get-Date
        $sources = [Collections.Generic.List[object]]::new()
        $outputs = [Collections.Generic.List[string]]::new()
        $hostName = [string]$workspace.workspaceUrl
        $pageSize = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'pageSize' -Default 100)

        try {
            $policies = Invoke-DatabricksPagedGet -Config $Config -HostName $hostName -Path "/api/2.0/policies/clusters/list?max_results=$pageSize" -ItemsProperty policies
            $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'governance-compute-policies' -Items @($policies.items)
            $outputs.Add($output)
            $sources.Add((New-DatabricksSourceStatus -Source 'compute policies' -Status $(if ($policies.truncated) { 'partial' } else { 'passed' }) -ItemCount @($policies.items).Count -Output $output))
        }
        catch {
            $sources.Add((New-DatabricksSourceStatus -Source 'compute policies' -Status partial -Message $_.Exception.Message))
        }

        $timeParameters = New-DatabricksTimeParameters -Config $Config
        foreach ($source in @(
            Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'billing attribution tags' -FileName 'DatabricksGovernanceTags.sql' -OutputName 'governance-tags' -Parameters $timeParameters
            Invoke-DatabricksSqlDatasetCollection -Config $Config -RunContext $RunContext -Workspace $workspace -Source 'system.access.audit governance events' -FileName 'DatabricksGovernanceAudit.sql' -OutputName 'governance-audit' -Parameters $timeParameters -SplitOversizedWindow
        )) {
            $sources.Add($source)
            if ($source.output) { $outputs.Add($source.output) }
        }

        $accountId = [string](Get-DatabricksProperty -InputObject $Config.databricks -Name 'accountId')
        $accountHost = [string](Get-DatabricksProperty -InputObject $Config.databricks -Name 'accountHost')
        if ([string]::IsNullOrWhiteSpace($accountId) -or [string]::IsNullOrWhiteSpace($accountHost)) {
            $sources.Add((New-DatabricksSourceStatus -Source 'account budgets' -Status 'pending telemetry' -Message 'accountId and accountHost are required for account budget inventory.'))
        }
        else {
            try {
                $budgets = Invoke-DatabricksPagedGet -Config $Config -HostName $accountHost -Path "/api/2.1/accounts/$([Uri]::EscapeDataString($accountId))/budgets?page_size=$pageSize" -ItemsProperty budgets -TokenParameter page_token
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'account-budgets' -Items @($budgets.items)
                $outputs.Add($output)
                $sources.Add((New-DatabricksSourceStatus -Source 'account budgets' -Status $(if ($budgets.truncated) { 'partial' } else { 'passed' }) -ItemCount @($budgets.items).Count -Output $output))
            }
            catch {
                $sources.Add((New-DatabricksSourceStatus -Source 'account budgets' -Status partial -Message $_.Exception.Message))
            }
        }

        $sources.Add((New-DatabricksSourceStatus -Source 'Azure budgets and policy state' -Status skipped -Message 'Azure governance is outside this Databricks-only collector set.'))
        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'governance' -Sources @($sources)
        $outputs.Add($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks governance [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $startedAt -ItemCount (($sources | Measure-Object itemCount -Sum).Sum) -Outputs @($outputs) -Limitations $limitations
    }
}
