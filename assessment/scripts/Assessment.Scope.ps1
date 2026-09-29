Set-StrictMode -Version Latest

function Select-AssessmentScopeItems {
    param(
        [Parameter(Mandatory)][object[]]$Items,
        [Parameter(Mandatory)][string]$Description
    )

    if ($Items.Count -eq 0) {
        throw "No accessible $Description were found. No assessment was started."
    }
    Write-Host "`nSelect $Description (comma-separated numbers; * for all displayed; q to cancel):"
    for ($index = 0; $index -lt $Items.Count; $index++) {
        Write-Host ("  {0}. {1}" -f ($index + 1), $Items[$index].label)
    }
    $answer = (Read-Host $Description).Trim()
    if ($answer -ieq 'q') {
        throw 'Scope selection canceled. No assessment was started.'
    }
    if ($answer -eq '*') {
        return $Items
    }
    $indexes = [Collections.Generic.List[int]]::new()
    foreach ($part in $answer.Split(',')) {
        $number = 0
        if (-not [int]::TryParse($part.Trim(), [ref]$number) -or $number -lt 1 -or $number -gt $Items.Count) {
            throw "Invalid $Description selection '$answer'. Use the displayed numbers, * or q. No assessment was started."
        }
        if (-not $indexes.Contains($number - 1)) {
            $indexes.Add($number - 1)
        }
    }
    return @($indexes | ForEach-Object { $Items[$_] })
}

function New-AssessmentScopeConfig {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [switch]$SelectScope,
        [string[]]$SubscriptionIds = @(),
        [string[]]$ResourceGroups = @()
    )

    if ($SelectScope -and ($SubscriptionIds.Count -gt 0 -or $ResourceGroups.Count -gt 0)) {
        throw 'Use -SelectScope or explicit -SubscriptionIds/-ResourceGroups, not both.'
    }
    $resolved = $Config | ConvertTo-Json -Depth 100 | ConvertFrom-Json -Depth 100
    $settings = Get-AzureAssessmentSettings -Config $resolved
    $account = Invoke-AzureAssessmentCliJson -Arguments @('account', 'show', '--output', 'json', '--only-show-errors')
    $tenantId = [string](Get-AzureAssessmentProperty -InputObject $account -Name tenantId)
    if (-not $tenantId) {
        throw 'Azure CLI has no active tenant. Run az login before selecting scope.'
    }
    $accounts = @(Invoke-AzureAssessmentCliJson -Arguments @('account', 'list', '--output', 'json', '--only-show-errors'))
    $eligible = @($accounts | Where-Object { $_.state -eq 'Enabled' -and $_.tenantId -eq $tenantId } |
        Sort-Object name, id)
    if ($eligible.Count -eq 0) {
        throw "No enabled subscriptions are accessible in the active tenant '$tenantId'."
    }

    if ($SelectScope) {
        $choices = @($eligible | ForEach-Object {
            [pscustomobject]@{ label = "$($_.name) [$($_.id)]"; id = [string]$_.id }
        })
        $SubscriptionIds = @(Select-AssessmentScopeItems -Items $choices -Description 'subscriptions' | ForEach-Object id)
    }
    elseif ($SubscriptionIds.Count -eq 0) {
        $SubscriptionIds = @($resolved.azure.subscriptions)
    }
    if ($SubscriptionIds.Count -eq 0) {
        throw 'Select at least one subscription. No assessment was started.'
    }
    $selectedSubscriptions = @($SubscriptionIds | ForEach-Object {
        $id = $_.Trim()
        if ($id -notmatch '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' -or $id -notin $eligible.id) {
            throw "Subscription '$id' is invalid, inaccessible, disabled, or outside the active tenant. No assessment was started."
        }
        $id.ToLowerInvariant()
    } | Select-Object -Unique)

    $groups = @(
        foreach ($subscription in $selectedSubscriptions) {
            foreach ($group in @(Get-AzureAssessmentPagedValues `
                -Uri "https://management.azure.com/subscriptions/$subscription/resourcegroups?api-version=2021-04-01" -Settings $settings)) {
                [pscustomobject]@{
                    id = ([string]$group.id).TrimEnd('/').ToLowerInvariant()
                    name = [string]$group.name
                    subscriptionId = $subscription
                    label = "$($group.name) [$subscription]"
                }
            }
        }
    )
    $groups = @($groups | Sort-Object subscriptionId, name)
    if ($groups.Count -eq 0) {
        throw 'No accessible resource groups were found in the selected subscriptions. No assessment was started.'
    }
    if ($SelectScope) {
        $selectedGroups = @(Select-AssessmentScopeItems -Items $groups -Description 'resource groups')
    }
    elseif ($ResourceGroups.Count -gt 0) {
        $selectedGroups = @(
            foreach ($requestedGroup in $ResourceGroups) {
                $requestedGroup = $requestedGroup.Trim().TrimEnd('/')
                $matches = @($groups | Where-Object { $_.id -ieq $requestedGroup -or $_.name -ieq $requestedGroup })
                if ($matches.Count -eq 0) {
                    throw "Resource group '$requestedGroup' is not accessible in the selected subscriptions. No assessment was started."
                }
                if ($matches.Count -gt 1) {
                    throw "Resource group '$requestedGroup' is ambiguous across subscriptions. Use its full ARM resource group ID or -SelectScope."
                }
                $matches[0]
            }
        )
    }
    else {
        $selectedGroups = $groups
    }
    $groupIds = @($selectedGroups.id | Select-Object -Unique)
    $previousWorkspaces = @($resolved.databricks.workspaces | Where-Object include)
    $globalWarehouse = [string](Get-AzureAssessmentProperty -InputObject $resolved.databricks -Name sqlWarehouseId)
    $workspaces = @(
        foreach ($subscription in $selectedSubscriptions) {
            foreach ($workspace in @(Get-AzureAssessmentPagedValues `
                -Uri "https://management.azure.com/subscriptions/$subscription/providers/Microsoft.Databricks/workspaces?api-version=2024-05-01" -Settings $settings)) {
                $resourceId = ([string]$workspace.id).TrimEnd('/')
                if ($resourceId -notmatch '(?i)^(/subscriptions/[^/]+/resourceGroups/([^/]+))/providers/Microsoft.Databricks/workspaces/[^/]+$') {
                    throw "Workspace discovery returned an invalid resource ID '$resourceId'."
                }
                $groupId = $Matches[1]
                $groupName = $Matches[2]
                if ($groupId -notin $groupIds) { continue }
                $hostName = [string](Get-AzureAssessmentProperty -InputObject $workspace.properties -Name workspaceUrl)
                $workspaceId = [string](Get-AzureAssessmentProperty -InputObject $workspace.properties -Name workspaceId)
                if (-not $hostName -or -not $workspaceId) {
                    throw "Workspace '$resourceId' has no usable URL or workspace ID. Check provisioning and permissions before assessment."
                }
                $hostName = ($hostName -replace '^https://', '').TrimEnd('/')
                $existing = @($previousWorkspaces | Where-Object {
                    $oldId = [string](Get-AzureAssessmentProperty -InputObject $_ -Name resourceId)
                    $oldWorkspaceId = [string](Get-AzureAssessmentProperty -InputObject $_ -Name workspaceResourceId)
                    $oldHost = ([string](Get-AzureAssessmentProperty -InputObject $_ -Name workspaceUrl) -replace '^https://', '').TrimEnd('/')
                    $oldId -ieq $resourceId -or $oldWorkspaceId -ieq $resourceId -or $oldHost -ieq $hostName
                })
                if ($existing.Count -gt 1) {
                    throw "The base config contains duplicate entries for workspace '$resourceId'."
                }
                $entry = if ($existing.Count -eq 1) { $existing[0] } else { [pscustomobject]@{} }
                $properties = @{
                    name = [string]$workspace.name
                    subscriptionId = $subscription
                    resourceGroup = $groupName
                    resourceId = $resourceId
                    workspaceResourceId = $resourceId
                    workspaceUrl = $hostName
                    workspaceId = $workspaceId
                    include = $true
                }
                foreach ($key in $properties.Keys) {
                    $entry | Add-Member -NotePropertyName $key -NotePropertyValue $properties[$key] -Force
                }
                if ($existing.Count -eq 1 -and $globalWarehouse -and -not (Get-AzureAssessmentProperty -InputObject $entry -Name sqlWarehouseId)) {
                    $entry | Add-Member -NotePropertyName sqlWarehouseId -NotePropertyValue $globalWarehouse -Force
                }
                $entry
            }
        }
    )
    if ($workspaces.Count -eq 0) {
        throw 'No Azure Databricks workspaces were found in the selected scope. No assessment was started; scope was not broadened.'
    }
    if (-not $SelectScope -and $ResourceGroups.Count -eq 0) {
        $groupIds = @($workspaces | ForEach-Object {
            $_.resourceId -replace '(?i)/providers/Microsoft.Databricks/workspaces/[^/]+$', ''
        } | ForEach-Object { $_.ToLowerInvariant() } | Select-Object -Unique)
        $selectedGroups = @($groups | Where-Object { $_.id -in $groupIds })
    }
    $azureProperties = @{
        tenantId = $tenantId
        subscriptions = $selectedSubscriptions
        resourceGroups = @($selectedGroups.name | Select-Object -Unique)
        resourceGroupIds = $groupIds
        costScopes = @($selectedSubscriptions | ForEach-Object { "/subscriptions/$_" })
    }
    foreach ($key in $azureProperties.Keys) {
        $resolved.azure | Add-Member -NotePropertyName $key -NotePropertyValue $azureProperties[$key] -Force
    }
    $resolved.azure.PSObject.Properties.Remove('costScope')
    $resolved.databricks.workspaces = $workspaces
    $resolved.databricks.PSObject.Properties.Remove('sqlWarehouseId')
    foreach ($name in @('deepDiveJobRunIds', 'deepDiveTableNames')) {
        if (@(Get-AzureAssessmentProperty -InputObject $resolved.databricks -Name $name -Default @()).Count -gt 0) {
            Write-Warning "Global $name were cleared for the newly selected scope; configure deep dives separately in a reviewed scope file."
        }
        $resolved.databricks | Add-Member -NotePropertyName $name -NotePropertyValue @() -Force
    }
    Write-Host "`nAssessment scope: $($selectedSubscriptions.Count) subscription(s), $($groupIds.Count) selected resource group(s), $($workspaces.Count) Databricks workspace(s)."
    Write-Host 'Associated Databricks managed resource groups are included automatically; unrelated resources remain excluded.'
    foreach ($workspace in $workspaces) {
        Write-Host "  $($workspace.resourceId)"
    }
    $sqlWorkspaces = @($workspaces | Where-Object { Get-AzureAssessmentProperty -InputObject $_ -Name sqlWarehouseId })
    if ($sqlWorkspaces.Count -lt $workspaces.Count) {
        Write-Warning 'Some selected workspaces have no configured SQL Warehouse. SQL-backed evidence will be unavailable for them; no Warehouse is chosen or started automatically.'
    }
    return $resolved
}
