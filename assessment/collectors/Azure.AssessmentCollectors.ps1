Set-StrictMode -Version Latest

$script:AzureCostNextRequestUtc = [DateTimeOffset]::MinValue

function Get-AzureAssessmentProperty {
    param(
        [AllowNull()][object]$InputObject,
        [Parameter(Mandatory)][string]$Name,
        [AllowNull()][object]$Default = $null
    )

    if ($null -eq $InputObject) {
        return $Default
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }
    return $property.Value
}

function Write-AzureAssessmentNdjson {
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Value,
        [Parameter(Mandatory)][string]$Path
    )

    if ($Value.Count -gt 0) {
        Write-NdjsonFile -Value $Value -Path $Path
        return
    }
    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -LiteralPath $Path -Value $null -Encoding utf8
}

function Invoke-AzureAssessmentCliJson {
    param([Parameter(Mandatory)][string[]]$Arguments)

    $output = & az @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI failed (az $($Arguments -join ' ')): $($output -join "`n")"
    }
    $text = $output -join "`n"
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }
    return $text | ConvertFrom-Json -Depth 100
}

function Invoke-AzureAssessmentRest {
    param(
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Uri,
        [AllowNull()][object]$Body,
        [int]$RetryCount = 3,
        [int]$RetryBaseSeconds = 2
    )

    if (-not $Uri.StartsWith('https://management.azure.com/', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Azure assessment REST URI must target management.azure.com: '$Uri'."
    }
    if ($Method -eq 'POST' -and
        $Uri -notmatch '/providers/Microsoft\.ResourceGraph/resources\?' -and
        $Uri -notmatch '/providers/Microsoft\.CostManagement/(query|forecast)\?') {
        throw "POST is not approved for the read-only Azure assessment endpoint '$Uri'."
    }
    if ($Uri -match '/providers/Microsoft\.CostManagement/(query|forecast)\?') {
        return Invoke-AzureAssessmentCostRequest -Method $Method -Uri $Uri -Body $Body `
            -RetryCount $RetryCount -RetryBaseSeconds $RetryBaseSeconds
    }

    $bodyPath = $null
    try {
        if ($null -ne $Body) {
            $bodyPath = Join-Path ([IO.Path]::GetTempPath()) "adb-assessment-$([Guid]::NewGuid().ToString('N')).json"
            [IO.File]::WriteAllText($bodyPath, ($Body | ConvertTo-Json -Depth 100 -Compress), [Text.UTF8Encoding]::new($false))
        }
        return Invoke-WithAssessmentRetry `
            -Description "$Method $Uri" `
            -RetryCount $RetryCount `
            -BaseSeconds $RetryBaseSeconds `
            -ShouldRetry {
                param($errorRecord)
                $message = [string]$errorRecord.Exception.Message
                $message -notmatch 'ResourceTypeNotSupported|AuthorizationFailed|InvalidAuthenticationToken|Bad Request' -or $message -match '429|Too Many Requests'
            } `
            -Operation {
                $arguments = @('rest', '--only-show-errors', '--method', $Method, "--url=`"$Uri`"", '--output', 'json')
                if ($bodyPath) {
                    $arguments += @('--headers', 'Content-Type=application/json', '--body', "@$bodyPath")
                }
                Invoke-AzureAssessmentCliJson -Arguments $arguments
            }
    }
    finally {
        if ($bodyPath -and (Test-Path -LiteralPath $bodyPath)) {
            Remove-Item -LiteralPath $bodyPath -Force
        }
    }
}

function Get-AzureCostRetryAfter {
    param([Parameter(Mandatory)][System.Collections.IDictionary]$Headers)

    $delay = 0.0
    foreach ($name in $Headers.Keys) {
        if ($name -notmatch '^(Retry-After|x-ms-ratelimit-microsoft\.costmanagement-(.+-)?retry-after)$') {
            continue
        }
        foreach ($value in @($Headers[$name])) {
            $seconds = 0.0
            $date = [DateTimeOffset]::MinValue
            if ([double]::TryParse([string]$value, [Globalization.NumberStyles]::Float,
                    [Globalization.CultureInfo]::InvariantCulture, [ref]$seconds) -and
                [double]::IsFinite($seconds) -and $seconds -ge 0) {
                $delay = [Math]::Max($delay, $seconds)
            }
            elseif ([DateTimeOffset]::TryParse([string]$value, [ref]$date)) {
                $delay = [Math]::Max($delay, ($date - [DateTimeOffset]::UtcNow).TotalSeconds)
            }
        }
    }
    return [Math]::Ceiling($delay)
}

function Wait-AzureCostRequest {
    $seconds = [Math]::Ceiling(($script:AzureCostNextRequestUtc - [DateTimeOffset]::UtcNow).TotalSeconds)
    if ($seconds -gt 0) {
        Write-Host "Cost Management request pacing: waiting ${seconds}s before the next request."
        Start-Sleep -Seconds $seconds
    }
    $script:AzureCostNextRequestUtc = [DateTimeOffset]::UtcNow.AddSeconds(20)
}

function Invoke-AzureAssessmentCostRequest {
    param(
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Uri,
        [AllowNull()][object]$Body,
        [int]$RetryCount = 3,
        [int]$RetryBaseSeconds = 2
    )

    if ($Uri -notmatch '^https://management\.azure\.com/.*?/providers/Microsoft\.CostManagement/(query|forecast)\?') {
        throw 'Cost requests must target the approved ARM Cost Management query or forecast endpoint.'
    }
    $arguments = @('account', 'get-access-token', '--resource', 'https://management.azure.com/', '--output', 'json', '--only-show-errors')
    if ($Uri -match '^https://management\.azure\.com/subscriptions/([^/]+)/') {
        $arguments += @('--subscription', $Matches[1])
    }
    $token = Invoke-AzureAssessmentCliJson -Arguments $arguments
    $headers = @{
        Authorization = "Bearer $($token.accessToken)"
        ClientType = 'AzureDatabricksCostAssessmentToolkit'
    }
    $payload = if ($null -ne $Body) { $Body | ConvertTo-Json -Depth 100 -Compress } else { $null }
    for ($attempt = 0; $attempt -le $RetryCount; $attempt++) {
        Wait-AzureCostRequest
        # Keep response headers: az rest's JSON output discards the server's cooldown.
        $response = Invoke-WebRequest -Method $Method -Uri $Uri -Headers $headers -Body $payload `
            -ContentType 'application/json' -SkipHttpErrorCheck -TimeoutSec 120 -MaximumRedirection 0
        $status = [int]$response.StatusCode
        if ($status -ge 200 -and $status -lt 300) {
            if ($status -eq 204) { return $null }
            return $response.Content | ConvertFrom-Json -Depth 100
        }
        $error = [InvalidOperationException]::new("Cost Management HTTP ${status}: $($response.Content)")
        $error.Data['StatusCode'] = $status
        $retryAfter = Get-AzureCostRetryAfter -Headers $response.Headers
        if ($status -notin @(408, 429, 500, 502, 503, 504) -or $attempt -ge $RetryCount) {
            if ($status -eq 429) {
                $error.Data['RetryAfterSeconds'] = $retryAfter
            }
            throw $error
        }
        $base = if ($status -eq 429) { [Math]::Max(60, $RetryBaseSeconds) } else { $RetryBaseSeconds }
        $delay = [Math]::Max($retryAfter, [Math]::Min(240, $base * [Math]::Pow(2, $attempt)))
        if ($delay -gt 600) {
            $error.Data['RetryAfterSeconds'] = $delay
            throw [InvalidOperationException]::new("Cost Management requires a ${delay}s cooldown. Stop collecting costs and retry later.", $error)
        }
        $delay += Get-Random -Minimum 1 -Maximum 6
        Write-Warning "Cost Management HTTP $status on attempt $($attempt + 1). Waiting ${delay}s before retry $($attempt + 1)/$RetryCount; respecting server cooldown."
        Start-Sleep -Seconds $delay
    }
}

function Get-AzureAssessmentSettings {
    param([Parameter(Mandatory)][object]$Config)

    $analysis = Get-AzureAssessmentProperty -InputObject $Config -Name analysis
    return @{
        MaxPages = [Math]::Max(1, [int](Get-AzureAssessmentProperty -InputObject $analysis -Name maxPages -Default 100))
        PageSize = [Math]::Max(1, [int](Get-AzureAssessmentProperty -InputObject $analysis -Name pageSize -Default 1000))
        RetryCount = [Math]::Max(0, [int](Get-AzureAssessmentProperty -InputObject $analysis -Name retryCount -Default 3))
        RetryBaseSeconds = [Math]::Max(1, [int](Get-AzureAssessmentProperty -InputObject $analysis -Name retryBaseSeconds -Default 2))
    }
}

function Invoke-AzureAssessmentResourceGraph {
    param(
        [Parameter(Mandatory)][string]$Query,
        [Parameter(Mandatory)][string[]]$Subscriptions,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    if ($Subscriptions.Count -eq 0) {
        return @()
    }

    $items = [Collections.Generic.List[object]]::new()
    $skipToken = $null
    for ($page = 1; $page -le $Settings.MaxPages; $page++) {
        $options = @{
            '$top' = $Settings.PageSize
            resultFormat = 'objectArray'
        }
        if ($skipToken) {
            $options['$skipToken'] = $skipToken
        }
        $body = @{
            subscriptions = @($Subscriptions)
            query = $Query
            options = $options
        }
        $response = Invoke-AzureAssessmentRest `
            -Method POST `
            -Uri 'https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01' `
            -Body $body `
            -RetryCount $Settings.RetryCount `
            -RetryBaseSeconds $Settings.RetryBaseSeconds
        foreach ($item in @(Get-AzureAssessmentProperty -InputObject $response -Name data -Default @())) {
            $items.Add($item)
        }
        $skipToken = [string](Get-AzureAssessmentProperty -InputObject $response -Name '$skipToken')
        if ([string]::IsNullOrWhiteSpace($skipToken)) {
            return @($items)
        }
    }
    throw "Azure Resource Graph exceeded the configured maximum of $($Settings.MaxPages) pages."
}

function Get-AzureAssessmentPagedValues {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    $values = [Collections.Generic.List[object]]::new()
    $nextLink = $Uri
    for ($page = 1; $page -le $Settings.MaxPages -and $nextLink; $page++) {
        $response = Invoke-AzureAssessmentRest `
            -Method GET `
            -Uri $nextLink `
            -RetryCount $Settings.RetryCount `
            -RetryBaseSeconds $Settings.RetryBaseSeconds
        foreach ($value in @(Get-AzureAssessmentProperty -InputObject $response -Name value -Default @())) {
            $values.Add($value)
        }
        $nextLink = [string](Get-AzureAssessmentProperty -InputObject $response -Name nextLink)
        if (-not $nextLink) {
            return @($values)
        }
    }
    if ($nextLink) {
        throw "Azure ARM request exceeded the configured maximum of $($Settings.MaxPages) pages."
    }
    return @($values)
}

function Get-AzureAssessmentCostPages {
    param(
        [Parameter(Mandatory)][string]$Scope,
        [Parameter(Mandatory)][ValidateSet('ActualCost', 'AmortizedCost')][string]$CostBasis,
        [Parameter(Mandatory)][DateTimeOffset]$Start,
        [Parameter(Mandatory)][DateTimeOffset]$End,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    $body = @{
        type = $CostBasis
        timeframe = 'Custom'
        timePeriod = @{
            from = $Start.ToUniversalTime().ToString('o')
            to = $End.AddTicks(-1).ToUniversalTime().ToString('o')
        }
        dataset = @{
            granularity = 'Daily'
            aggregation = @{
                cost = @{ name = 'PreTaxCost'; function = 'Sum' }
                usage = @{ name = 'UsageQuantity'; function = 'Sum' }
            }
            grouping = @(
                @{ type = 'Dimension'; name = 'ResourceId' }
                @{ type = 'Dimension'; name = 'Meter' }
            )
        }
    }
    $uri = "https://management.azure.com$($Scope.TrimEnd('/'))/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    $rows = [Collections.Generic.List[object]]::new()

    for ($page = 1; $page -le $Settings.MaxPages; $page++) {
        $response = Invoke-AzureAssessmentRest `
            -Method POST `
            -Uri $uri `
            -Body $body `
            -RetryCount $Settings.RetryCount `
            -RetryBaseSeconds $Settings.RetryBaseSeconds
        $properties = Get-AzureAssessmentProperty -InputObject $response -Name properties
        $columns = @(Get-AzureAssessmentProperty -InputObject $properties -Name columns -Default @())
        foreach ($sourceRow in @(Get-AzureAssessmentProperty -InputObject $properties -Name rows -Default @())) {
            $mapped = [ordered]@{
                costBasis = $CostBasis
                scope = $Scope
                windowStartUtc = $Start.ToUniversalTime().ToString('o')
                windowEndUtc = $End.ToUniversalTime().ToString('o')
            }
            for ($index = 0; $index -lt $columns.Count; $index++) {
                $mapped[[string]$columns[$index].name] = if ($index -lt $sourceRow.Count) { $sourceRow[$index] } else { $null }
            }
            $rows.Add([pscustomobject]$mapped)
        }
        $nextLink = [string](Get-AzureAssessmentProperty -InputObject $properties -Name nextLink)
        if (-not $nextLink) {
            return @($rows)
        }
        $uri = $nextLink
    }
    throw "Azure Cost Management query exceeded the configured maximum of $($Settings.MaxPages) pages."
}

function Split-AzureAssessmentTimeWindow {
    param(
        [Parameter(Mandatory)][DateTimeOffset]$Start,
        [Parameter(Mandatory)][DateTimeOffset]$End,
        [ValidateRange(1, 93)][int]$Days = 31
    )

    $windows = [Collections.Generic.List[object]]::new()
    $cursor = $Start
    while ($cursor -lt $End) {
        $next = $cursor.AddDays($Days)
        if ($next -gt $End) {
            $next = $End
        }
        $windows.Add([pscustomobject]@{ Start = $cursor; End = $next })
        $cursor = $next
    }
    return @($windows)
}

function Write-AzureAssessmentSourceStatus {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][object[]]$Results
    )

    $status = @($Results | ForEach-Object {
        [pscustomobject]@{
            source = $_.name
            status = $_.status
            itemCount = $_.itemCount
            outputs = $_.outputs
            limitations = $_.limitations
            error = $_.error
            startedAtUtc = $_.startedAtUtc
            completedAtUtc = $_.completedAtUtc
        }
    })
    Write-JsonFile -Value $status -Path $Path
}

function Get-AzureAssessmentResourceGroupId {
    param([AllowNull()][string]$ResourceId)

    if ($ResourceId -match '^(/subscriptions/[^/]+/resourceGroups/[^/]+)(?:/|$)') {
        return $Matches[1].ToLowerInvariant()
    }
}

function Get-AzureAssessmentSelectedGroupIds {
    param([Parameter(Mandatory)][object]$AzureConfig)

    if ($null -ne $AzureConfig.PSObject.Properties['resourceGroupIds']) {
        foreach ($id in @($AzureConfig.resourceGroupIds)) {
            $groupId = Get-AzureAssessmentResourceGroupId -ResourceId ([string]$id)
            if (-not $groupId -or $groupId -ine ([string]$id).TrimEnd('/')) {
                throw "Invalid Azure resource group ID '$id'. Expected /subscriptions/<id>/resourceGroups/<name>."
            }
            $subscription = $groupId.Split('/')[2]
            if ($subscription -notin @($AzureConfig.subscriptions)) {
                throw "Resource group '$id' is outside the selected subscriptions."
            }
            $groupId
        }
    }
    else {
        foreach ($subscription in @($AzureConfig.subscriptions)) {
            foreach ($name in @(Get-AzureAssessmentProperty -InputObject $AzureConfig -Name resourceGroups -Default @())) {
                if ($name) {
                    "/subscriptions/$subscription/resourcegroups/$name".ToLowerInvariant()
                }
            }
        }
    }
}

function Test-AzureAssessmentWorkspaceSelected {
    param(
        [Parameter(Mandatory)][object]$Workspace,
        [Parameter(Mandatory)][object]$Config
    )

    $databricks = Get-AzureAssessmentProperty -InputObject $Config -Name databricks
    if ($null -eq $databricks -or $null -eq $databricks.PSObject.Properties['workspaces']) { return $true }
    $configured = @(Get-AzureAssessmentProperty -InputObject $databricks -Name workspaces -Default @())
    if ($configured.Count -eq 0) { return $false }
    $id = [string]$Workspace.id
    $groupId = Get-AzureAssessmentResourceGroupId -ResourceId $id
    foreach ($entry in $configured) {
        if (-not (Get-AzureAssessmentProperty -InputObject $entry -Name include -Default $true)) { continue }
        $configuredId = [string](Get-AzureAssessmentProperty -InputObject $entry -Name workspaceResourceId)
        if (-not $configuredId) {
            $configuredId = [string](Get-AzureAssessmentProperty -InputObject $entry -Name resourceId)
        }
        if ($configuredId) {
            if ($configuredId.TrimEnd('/') -ieq $id.TrimEnd('/')) { return $true }
            continue
        }
        $properties = Get-AzureAssessmentProperty -InputObject $Workspace -Name properties
        $configuredWorkspaceId = [string](Get-AzureAssessmentProperty -InputObject $entry -Name workspaceId)
        $workspaceId = [string](Get-AzureAssessmentProperty -InputObject $properties -Name workspaceId)
        if ($configuredWorkspaceId -and $workspaceId) {
            if ($configuredWorkspaceId -eq $workspaceId) { return $true }
            continue
        }
        $name = [string](Get-AzureAssessmentProperty -InputObject $entry -Name name)
        $group = [string](Get-AzureAssessmentProperty -InputObject $entry -Name resourceGroup)
        $subscription = [string](Get-AzureAssessmentProperty -InputObject $entry -Name subscriptionId)
        if ($name -ine [string]$Workspace.name) { continue }
        if ($group -and $groupId -and $group -ine $groupId.Split('/')[-1]) { continue }
        if ($subscription -and $groupId -and $subscription -ine $groupId.Split('/')[2]) { continue }
        return $true
    }
    return $false
}

function Invoke-AzureInventoryAssessmentCollector {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    $started = Get-Date
    $outputRoot = Join-Path $RunContext.Root 'raw\azure'
    $inventoryPath = Join-Path $outputRoot 'resource-inventory.ndjson'
    $workspacePath = Join-Path $outputRoot 'databricks-workspaces.json'
    $managedPath = Join-Path $outputRoot 'managed-resource-inventory.ndjson'
    $ownershipPath = Join-Path $outputRoot 'tags-ownership-inputs.ndjson'
    try {
        $subscriptions = @($Config.azure.subscriptions | ForEach-Object { [string]$_ })
        $includedGroupIds = @(Get-AzureAssessmentSelectedGroupIds -AzureConfig $Config.azure)
        $resourceQuery = @'
resourcecontainers
| where type =~ 'microsoft.resources/subscriptions' or type =~ 'microsoft.resources/subscriptions/resourcegroups'
| project id, name, type, subscriptionId, resourceGroup, location, tags, properties
| union (
    resources
    | project id, name, type, subscriptionId, resourceGroup, location, tags, sku, kind, identity, properties
)
'@
        $allResources = @(Invoke-AzureAssessmentResourceGraph -Query $resourceQuery -Subscriptions $subscriptions -Settings $Settings)
        if ($includedGroupIds.Count -gt 0) {
            $resources = @($allResources | Where-Object {
                $_.type -match '/subscriptions$' -or
                (Get-AzureAssessmentResourceGroupId -ResourceId $_.id) -in $includedGroupIds
            })
        }
        else {
            $resources = $allResources
        }

        $workspaces = [Collections.Generic.List[object]]::new()
        $limitations = [Collections.Generic.List[string]]::new()
        foreach ($workspace in @($resources | Where-Object type -ieq 'microsoft.databricks/workspaces')) {
            if (-not (Test-AzureAssessmentWorkspaceSelected -Workspace $workspace -Config $Config)) { continue }
            try {
                $detail = Invoke-AzureAssessmentRest `
                    -Method GET `
                    -Uri "https://management.azure.com$($workspace.id)?api-version=2023-02-01" `
                    -RetryCount $Settings.RetryCount `
                    -RetryBaseSeconds $Settings.RetryBaseSeconds
                $workspaces.Add($detail)
            }
            catch {
                $limitations.Add("Workspace ARM configuration unavailable for '$($workspace.id)': $($_.Exception.Message)")
                $workspaces.Add($workspace)
            }
        }
        # Keep the array as one pipeline item so an empty inventory is persisted as [].
        Write-JsonFile -Value (, @($workspaces)) -Path $workspacePath

        $managedGroupIds = @($workspaces | ForEach-Object {
            Get-AzureAssessmentResourceGroupId -ResourceId (
                Get-AzureAssessmentProperty -InputObject $_.properties -Name managedResourceGroupId)
        } | Where-Object { $_ })
        $managedResources = @($allResources | Where-Object {
            (Get-AzureAssessmentResourceGroupId -ResourceId $_.id) -in $managedGroupIds
        })
        $resourceById = [ordered]@{}
        foreach ($resource in @($resources) + @($managedResources)) {
            $resourceById[[string]$resource.id] = $resource
        }
        $resources = @($resourceById.Values)
        Write-AzureAssessmentNdjson -Value $resources -Path $inventoryPath
        Write-AzureAssessmentNdjson -Value $managedResources -Path $managedPath

        $ownershipKeys = @('Owner', 'Team', 'BusinessUnit', 'Project', 'Environment', 'Product', 'Service', 'CostCenter', 'DataProduct')
        $ownership = @($resources | Where-Object tags | ForEach-Object {
            $resource = $_
            $values = [ordered]@{ resourceId = $resource.id; resourceType = $resource.type; resourceGroup = $resource.resourceGroup }
            foreach ($key in $ownershipKeys) {
                $match = $resource.tags.PSObject.Properties | Where-Object Name -ieq $key | Select-Object -First 1
                $values[$key] = if ($match) { $match.Value } else { $null }
            }
            [pscustomobject]$values
        })
        Write-AzureAssessmentNdjson -Value $ownership -Path $ownershipPath

        $status = if ($limitations.Count) { 'partial' } else { 'passed' }
        return New-CollectorResult -Name 'Azure inventory' -Status $status -StartedAt $started `
            -ItemCount $resources.Count -Outputs @($inventoryPath, $workspacePath, $managedPath, $ownershipPath) `
            -Limitations @($limitations)
    }
    catch {
        return New-CollectorResult -Name 'Azure inventory' -Status failed -StartedAt $started -ErrorMessage $_.Exception.Message
    }
}

function Invoke-AzureGovernanceAssessmentCollector {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    $started = Get-Date
    $outputRoot = Join-Path $RunContext.Root 'raw\azure'
    $policyPath = Join-Path $outputRoot 'policy-inventory.ndjson'
    $diagnosticsPath = Join-Path $outputRoot 'diagnostic-settings.ndjson'
    $limitations = [Collections.Generic.List[string]]::new()
    $notApplicable = [Collections.Generic.List[string]]::new()
    try {
        $subscriptions = @($Config.azure.subscriptions | ForEach-Object { [string]$_ })
        $policyQuery = @'
policyresources
| where type in~ (
    'microsoft.authorization/policyassignments',
    'microsoft.policyinsights/policystates',
    'microsoft.policyinsights/policytrackedresources'
)
| project id, name, type, subscriptionId, resourceGroup, properties
'@
        try {
            $policies = @(Invoke-AzureAssessmentResourceGraph -Query $policyQuery -Subscriptions $subscriptions -Settings $Settings)
        }
        catch {
            $policies = @()
            $limitations.Add("Azure Policy data unavailable: $($_.Exception.Message)")
        }
        Write-AzureAssessmentNdjson -Value $policies -Path $policyPath

        $inventoryPath = Join-Path $outputRoot 'resource-inventory.ndjson'
        $diagnostics = [Collections.Generic.List[object]]::new()
        if (Test-Path -LiteralPath $inventoryPath) {
            foreach ($line in @(Get-Content -LiteralPath $inventoryPath | Where-Object { $_ })) {
                $resource = $line | ConvertFrom-Json -Depth 100
                if ($resource.type -match '/subscriptions$|/resourcegroups$') {
                    continue
                }
                try {
                    $values = Get-AzureAssessmentPagedValues `
                        -Uri "https://management.azure.com$($resource.id)/providers/Microsoft.Insights/diagnosticSettings?api-version=2021-05-01-preview" `
                        -Settings $Settings
                    foreach ($value in $values) {
                        $diagnostics.Add([pscustomobject]@{ resourceId = $resource.id; setting = $value })
                    }
                }
                catch {
                    if ($_.Exception.Message -match "resource type '[^']+' does not support diagnostic settings") {
                        $notApplicable.Add("Diagnostic settings not applicable for '$($resource.id)': $($_.Exception.Message)")
                    }
                    else {
                        $limitations.Add("Diagnostic settings unavailable for '$($resource.id)': $($_.Exception.Message)")
                    }
                }
            }
        }
        else {
            $limitations.Add('Diagnostic collection skipped because Azure resource inventory is unavailable.')
        }
        Write-AzureAssessmentNdjson -Value @($diagnostics) -Path $diagnosticsPath
        $status = if ($policies.Count -eq 0 -and $diagnostics.Count -eq 0 -and $limitations.Count) { 'failed' }
            elseif ($limitations.Count) { 'partial' } else { 'passed' }
        return New-CollectorResult -Name 'Azure policy and diagnostics' -Status $status -StartedAt $started `
            -ItemCount ($policies.Count + $diagnostics.Count) -Outputs @($policyPath, $diagnosticsPath) `
            -Limitations (@($limitations) + @($notApplicable)) -ErrorMessage $(if ($status -eq 'failed') { $limitations -join '; ' } else { $null })
    }
    catch {
        return New-CollectorResult -Name 'Azure policy and diagnostics' -Status failed -StartedAt $started -ErrorMessage $_.Exception.Message
    }
}

function Invoke-AzureCostAssessmentCollector {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    $started = Get-Date
    $outputPath = Join-Path $RunContext.Root 'raw\azure\cost-management.ndjson'
    $filterPath = Join-Path $RunContext.Root 'raw\azure\cost-scope-filter.json'
    $limitations = [Collections.Generic.List[string]]::new()
    $rows = [Collections.Generic.List[object]]::new()
    $excludedRows = 0
    try {
        $start = [DateTimeOffset]::Parse([string]$Config.analysis.startUtc)
        $end = [DateTimeOffset]::Parse([string]$Config.analysis.endUtc)
        $scopes = @(Get-AzureAssessmentProperty -InputObject $Config.azure -Name costScopes -Default @())
        if ($scopes.Count -eq 0) {
            $legacyScope = [string](Get-AzureAssessmentProperty -InputObject $Config.azure -Name costScope)
            $scopes = if ($legacyScope) { @($legacyScope) }
                else { @($Config.azure.subscriptions | ForEach-Object { "/subscriptions/$_" }) }
        }
        $scopes = @($scopes | ForEach-Object { ([string]$_).TrimEnd('/') } | Sort-Object -Unique)
        $bases = @((Get-AzureAssessmentProperty -InputObject $Config.azure -Name costBasis -Default @('ActualCost', 'AmortizedCost')))
        $selectedGroupIds = @(Get-AzureAssessmentSelectedGroupIds -AzureConfig $Config.azure)
        $allowedGroupIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($groupId in $selectedGroupIds) {
            [void]$allowedGroupIds.Add($groupId)
        }
        $workspacePath = Join-Path $RunContext.Root 'raw\azure\databricks-workspaces.json'
        if (Test-Path -LiteralPath $workspacePath) {
            foreach ($workspace in @((Get-Content -Raw -LiteralPath $workspacePath | ConvertFrom-Json -Depth 100))) {
                $workspaceGroupId = Get-AzureAssessmentResourceGroupId -ResourceId ([string]$workspace.id)
                if (-not $workspaceGroupId -or
                    $workspaceGroupId.Split('/')[2] -notin @($Config.azure.subscriptions) -or
                    ($selectedGroupIds.Count -gt 0 -and $workspaceGroupId -notin $selectedGroupIds) -or
                    -not (Test-AzureAssessmentWorkspaceSelected -Workspace $workspace -Config $Config)) {
                    continue
                }
                [void]$allowedGroupIds.Add($workspaceGroupId)
                $managedId = Get-AzureAssessmentResourceGroupId -ResourceId (
                    Get-AzureAssessmentProperty -InputObject $workspace.properties -Name managedResourceGroupId)
                if ($managedId -and $managedId.Split('/')[2] -in @($Config.azure.subscriptions)) {
                    [void]$allowedGroupIds.Add($managedId)
                }
            }
        }
        if ($allowedGroupIds.Count -eq 0) {
            $limitations.Add('No selected resource groups or in-scope Databricks workspace inventory were available; subscription-wide cost collection was not attempted.')
        }
        else {
            if (Get-AzureAssessmentProperty -InputObject $RunContext -Name CostReadinessOnly -Default $false) {
                $probePath = Join-Path $RunContext.Root 'raw\azure\cost-readiness.json'
                $probes = [Collections.Generic.List[object]]::new()
                $probeStart = if ($end.AddDays(-1) -gt $start) { $end.AddDays(-1) } else { $start }
                foreach ($scope in $scopes) {
                    $probeBody = @{
                        type = 'ActualCost'
                        timeframe = 'Custom'
                        timePeriod = @{ from = $probeStart.ToString('o'); to = $end.AddTicks(-1).ToString('o') }
                        dataset = @{ aggregation = @{ cost = @{ name = 'PreTaxCost'; function = 'Sum' } } }
                    }
                    $probeUri = "https://management.azure.com$($scope.TrimEnd('/'))/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
                    $null = Invoke-AzureAssessmentRest -Method POST -Uri $probeUri -Body $probeBody `
                        -RetryCount $Settings.RetryCount -RetryBaseSeconds $Settings.RetryBaseSeconds
                    $probes.Add([pscustomobject]@{ scope = $scope; accessProbe = 'passed'; startUtc = $probeStart; endUtc = $end })
                }
                Write-JsonFile -Value @($probes) -Path $probePath
                return New-CollectorResult -Name 'Azure Cost Management' -Status partial -StartedAt $started `
                    -Outputs @($probePath) -Limitations @('Cost access probe succeeded. Readiness checks only a one-day aggregate per scope; full cost coverage is not validated until Run.')
            }
            :costScopes foreach ($scope in $scopes) {
                foreach ($basis in $bases) {
                    if ($basis -notin @('ActualCost', 'AmortizedCost')) {
                        $limitations.Add("Unsupported cost basis '$basis' was skipped.")
                        continue
                    }
                    foreach ($window in @(Split-AzureAssessmentTimeWindow -Start $start -End $end)) {
                        try {
                            $windowRows = Get-AzureAssessmentCostPages `
                                -Scope $scope -CostBasis $basis -Start $window.Start -End $window.End -Settings $Settings
                            foreach ($row in $windowRows) {
                                $resourceId = [string](Get-AzureAssessmentProperty -InputObject $row -Name ResourceId)
                                $groupId = Get-AzureAssessmentResourceGroupId -ResourceId $resourceId
                                if ($groupId -and $allowedGroupIds.Contains($groupId)) {
                                    $rows.Add($row)
                                }
                                else {
                                    $excludedRows++
                                }
                            }
                        }
                        catch {
                            $limitations.Add("$basis cost unavailable at '$scope' for $($window.Start.ToString('o')) through $($window.End.ToString('o')): $($_.Exception.Message)")
                            if ($_.Exception.Data['StatusCode'] -eq 429 -or
                                ($null -ne $_.Exception.InnerException -and $_.Exception.InnerException.Data['StatusCode'] -eq 429)) {
                                $limitations.Add('Cost Management remained throttled after bounded retries. Remaining cost windows, bases, and scopes were not queried; reopen this snapshot rather than immediately repeating the assessment.')
                                break costScopes
                            }
                        }
                    }
                }
            }
        }
        Write-AzureAssessmentNdjson -Value @($rows) -Path $outputPath
        Write-JsonFile -Value ([ordered]@{
            costScopes = $scopes
            allowedResourceGroupIds = @($allowedGroupIds | Sort-Object)
            allowedResourceGroups = @($allowedGroupIds | ForEach-Object { $_.Split('/')[-1] } | Sort-Object -Unique)
            includedRows = $rows.Count
            excludedRows = $excludedRows
        }) -Path $filterPath
        $status = if ($rows.Count -eq 0 -and $limitations.Count) { 'failed' }
            elseif ($limitations.Count) { 'partial' } else { 'passed' }
        return New-CollectorResult -Name 'Azure Cost Management' -Status $status -StartedAt $started `
            -ItemCount $rows.Count -Outputs @($outputPath, $filterPath) -Limitations @($limitations) `
            -ErrorMessage $(if ($status -eq 'failed') { $limitations -join '; ' } else { $null })
    }
    catch {
        return New-CollectorResult -Name 'Azure Cost Management' -Status failed -StartedAt $started -ErrorMessage $_.Exception.Message
    }
}

function Invoke-AzureFinancialGovernanceAssessmentCollector {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    $started = Get-Date
    $outputPath = Join-Path $RunContext.Root 'raw\azure\budgets-commitments.json'
    $limitations = [Collections.Generic.List[string]]::new()
    $payload = [ordered]@{ budgets = @(); reservations = @(); savingsPlans = @() }
    foreach ($subscription in @($Config.azure.subscriptions)) {
        try {
            $payload.budgets += @(Get-AzureAssessmentPagedValues `
                -Uri "https://management.azure.com/subscriptions/$subscription/providers/Microsoft.Consumption/budgets?api-version=2023-05-01" `
                -Settings $Settings)
        }
        catch {
            $limitations.Add("Budgets unavailable for subscription '$subscription': $($_.Exception.Message)")
        }
    }
    try {
        $payload.reservations = @(Get-AzureAssessmentPagedValues `
            -Uri 'https://management.azure.com/providers/Microsoft.Capacity/reservationOrders?api-version=2022-11-01' `
            -Settings $Settings)
    }
    catch {
        $limitations.Add("Reservation inventory unavailable with the current identity: $($_.Exception.Message)")
    }
    try {
        $payload.savingsPlans = @(Get-AzureAssessmentPagedValues `
            -Uri 'https://management.azure.com/providers/Microsoft.BillingBenefits/savingsPlans?api-version=2022-11-01' `
            -Settings $Settings)
    }
    catch {
        $limitations.Add("Savings Plan inventory unavailable with the current identity: $($_.Exception.Message)")
    }
    Write-JsonFile -Value $payload -Path $outputPath
    $count = @($payload.budgets).Count + @($payload.reservations).Count + @($payload.savingsPlans).Count
    $status = if ($count -eq 0 -and $limitations.Count) { 'failed' }
        elseif ($limitations.Count) { 'partial' } else { 'passed' }
    return New-CollectorResult -Name 'Azure budgets and commitments' -Status $status -StartedAt $started `
        -ItemCount $count -Outputs @($outputPath) -Limitations @($limitations) `
        -ErrorMessage $(if ($status -eq 'failed') { $limitations -join '; ' } else { $null })
}

function Invoke-AzureQuotaAssessmentCollector {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][hashtable]$Settings
    )

    $started = Get-Date
    $outputPath = Join-Path $RunContext.Root 'raw\azure\compute-quotas.ndjson'
    $limitations = [Collections.Generic.List[string]]::new()
    $quotas = [Collections.Generic.List[object]]::new()
    $regions = @((Get-AzureAssessmentProperty -InputObject $Config.azure -Name includedRegions -Default @()))
    $workspacePath = Join-Path $RunContext.Root 'raw\azure\databricks-workspaces.json'
    if (Test-Path -LiteralPath $workspacePath) {
        $regions += @((Get-Content -Raw -LiteralPath $workspacePath | ConvertFrom-Json -Depth 100) | ForEach-Object location)
    }
    $regions = @($regions | Where-Object { $_ } | Sort-Object -Unique)
    if ($regions.Count -eq 0) {
        $limitations.Add('No in-scope Azure region was available for compute quota collection.')
    }
    foreach ($subscription in @($Config.azure.subscriptions)) {
        foreach ($region in $regions) {
            try {
                $values = Get-AzureAssessmentPagedValues `
                    -Uri "https://management.azure.com/subscriptions/$subscription/providers/Microsoft.Compute/locations/$region/usages?api-version=2023-07-01" `
                    -Settings $Settings
                foreach ($value in $values) {
                    $quotas.Add([pscustomobject]@{ subscriptionId = $subscription; region = $region; quota = $value })
                }
            }
            catch {
                $limitations.Add("Compute quotas unavailable for subscription '$subscription' in '$region': $($_.Exception.Message)")
            }
        }
    }
    Write-AzureAssessmentNdjson -Value @($quotas) -Path $outputPath
    $status = if ($quotas.Count -eq 0 -and $limitations.Count) { 'failed' }
        elseif ($limitations.Count) { 'partial' } else { 'passed' }
    return New-CollectorResult -Name 'Azure compute quotas' -Status $status -StartedAt $started `
        -ItemCount $quotas.Count -Outputs @($outputPath) -Limitations @($limitations) `
        -ErrorMessage $(if ($status -eq 'failed') { $limitations -join '; ' } else { $null })
}

function Invoke-AzureAssessmentCollectors {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

    Assert-ReadOnlyAssessment -Config $Config
    $azureRoot = Join-Path $RunContext.Root 'raw\azure'
    New-Item -ItemType Directory -Path $azureRoot -Force | Out-Null
    $settings = Get-AzureAssessmentSettings -Config $Config

    $results = @(
        foreach ($check in @(Get-AssessmentCollectorPlan | Where-Object domain -eq 'Azure')) {
            Write-AssessmentProgress -Event @{ id = $check.id; status = 'running'; detail = "Checking $($check.title)." }
            $sourceResults = @(& $check.command -Config $Config -RunContext $RunContext -Settings $settings)
            Write-AssessmentCollectorProgress -Id $check.id -Results $sourceResults
            $sourceResults
        }
    )
    Write-AzureAssessmentSourceStatus -Path (Join-Path $azureRoot 'source-status.json') -Results $results
    return @($results)
}
