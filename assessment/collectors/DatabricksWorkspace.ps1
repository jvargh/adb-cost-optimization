function Invoke-DatabricksWorkspaceCollector {
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

        $inventory = [pscustomobject]@{
            accountId = Get-DatabricksProperty -InputObject $Config.databricks -Name 'accountId'
            workspaceId = Get-DatabricksProperty -InputObject $workspace -Name 'workspaceId'
            workspaceName = Get-DatabricksProperty -InputObject $workspace -Name 'name'
            workspaceUrl = $hostName
            resourceGroup = Get-DatabricksProperty -InputObject $workspace -Name 'resourceGroup'
            region = Get-DatabricksProperty -InputObject $workspace -Name 'region'
            tier = Get-DatabricksProperty -InputObject $workspace -Name 'tier'
            deploymentType = Get-DatabricksProperty -InputObject $workspace -Name 'deploymentType'
            status = Get-DatabricksProperty -InputObject $workspace -Name 'status'
            extractedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
        }
        $inventoryOutput = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'workspace-inventory' -Items @($inventory)
        $outputs.Add($inventoryOutput)
        $sources.Add((New-DatabricksSourceStatus -Source 'configured workspace scope' -Status passed -ItemCount 1 -Output $inventoryOutput))

        $accountId = [string](Get-DatabricksProperty -InputObject $Config.databricks -Name 'accountId')
        $accountHost = [string](Get-DatabricksProperty -InputObject $Config.databricks -Name 'accountHost')
        if ([string]::IsNullOrWhiteSpace($accountId) -or [string]::IsNullOrWhiteSpace($accountHost)) {
            $sources.Add((New-DatabricksSourceStatus -Source 'account workspace inventory' -Status 'pending telemetry' -Message 'accountId and accountHost are required for Account API inventory.'))
        }
        else {
            try {
                $accountResponse = Invoke-DatabricksCollectorRequest -Config $Config -HostName $accountHost -Method GET -Path "/api/2.0/accounts/$([Uri]::EscapeDataString($accountId))/workspaces"
                $accountWorkspaces = if ($accountResponse -is [Collections.IEnumerable] -and $accountResponse -isnot [string] -and $accountResponse -isnot [pscustomobject]) {
                    @($accountResponse)
                }
                else {
                    @((Get-DatabricksProperty -InputObject $accountResponse -Name 'workspaces' -Default @($accountResponse)))
                }
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'account-workspaces' -Items $accountWorkspaces
                $outputs.Add($output)
                $sources.Add((New-DatabricksSourceStatus -Source 'account workspace inventory' -Status passed -ItemCount $accountWorkspaces.Count -Output $output))
            }
            catch {
                $sources.Add((New-DatabricksSourceStatus -Source 'account workspace inventory' -Status partial -Message $_.Exception.Message))
            }
        }

        $requests = @(
            @{ Source = 'workspace settings'; Path = '/api/2.0/workspace-conf?keys=enableIpAccessLists,enableTokensConfig'; Output = 'workspace-settings'; Items = $null },
            @{ Source = 'metastore assignment'; Path = '/api/2.1/unity-catalog/current-metastore-assignment'; Output = 'metastore-assignment'; Items = $null },
            @{ Source = 'IP access lists'; Path = '/api/2.0/ip-access-lists'; Output = 'ip-access-lists'; Items = 'ip_access_lists' }
        )
        foreach ($request in $requests) {
            try {
                $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path $request.Path
                $items = if ($null -eq $request.Items) { @($response) } else { @((Get-DatabricksProperty -InputObject $response -Name $request.Items -Default @())) }
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name $request.Output -Items $items
                $outputs.Add($output)
                $sources.Add((New-DatabricksSourceStatus -Source $request.Source -Status passed -ItemCount @($items).Count -Output $output))
            }
            catch {
                $sources.Add((New-DatabricksSourceStatus -Source $request.Source -Status partial -Message $_.Exception.Message))
            }
        }

        if ([bool](Get-DatabricksProperty -InputObject $Config.databricks -Name 'includeIdentities' -Default $false)) {
            try {
                $groups = Invoke-DatabricksScimPagedGet -Config $Config -HostName $hostName -Path '/api/2.0/preview/scim/v2/Groups'
                $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $workspace -Name 'groups' -Items @($groups.items)
                $outputs.Add($output)
                $sources.Add((New-DatabricksSourceStatus -Source 'approved groups and entitlements' -Status $(if ($groups.truncated) { 'partial' } else { 'passed' }) -ItemCount @($groups.items).Count -Output $output))
            }
            catch {
                $sources.Add((New-DatabricksSourceStatus -Source 'approved groups and entitlements' -Status partial -Message $_.Exception.Message))
            }
        }
        else {
            $sources.Add((New-DatabricksSourceStatus -Source 'groups and identities' -Status skipped -Message 'Identity collection is disabled by scope.'))
        }

        $statusOutput = Write-DatabricksSourceStatus -RunContext $RunContext -Workspace $workspace -CollectorName 'workspace' -Sources @($sources)
        $outputs.Add($statusOutput)
        $limitations = @($sources | Where-Object status -ne 'passed' | ForEach-Object { "$($_.source): $($_.message)" })
        New-CollectorResult -Name "Databricks workspace [$((Get-DatabricksWorkspaceKey -Workspace $workspace))]" -Status (Get-DatabricksCollectorStatus -Sources @($sources)) -StartedAt $startedAt -ItemCount 1 -Outputs @($outputs) -Limitations $limitations
    }
}
