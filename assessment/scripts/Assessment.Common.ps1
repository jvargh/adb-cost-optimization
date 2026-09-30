Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:DatabricksApplicationId = '2ff814a6-3304-4ab8-85cb-cd0e6f879c1d'
$script:AllowedDatabricksMethods = @('GET', 'POST')
$script:AllowedDatabricksPostPaths = @(
    '/api/2.0/sql/statements',
    '/api/2.0/clusters/events',
    '/api/2.0/mlflow/experiments/search'
)

function Get-AssessmentCollectorPlan {
    @(
        @{ id = 'azure-inventory'; title = 'Azure resources and scope'; domain = 'Azure'; command = 'Invoke-AzureInventoryAssessmentCollector' }
        @{ id = 'azure-governance'; title = 'Azure policies and diagnostic settings'; domain = 'Azure'; command = 'Invoke-AzureGovernanceAssessmentCollector' }
        @{ id = 'azure-cost'; title = 'Azure costs (including any API retries)'; domain = 'Azure'; command = 'Invoke-AzureCostAssessmentCollector' }
        @{ id = 'azure-financial'; title = 'Azure budgets and financial controls'; domain = 'Azure'; command = 'Invoke-AzureFinancialGovernanceAssessmentCollector' }
        @{ id = 'azure-quota'; title = 'Azure quotas'; domain = 'Azure'; command = 'Invoke-AzureQuotaAssessmentCollector' }
        @{ id = 'db-workspace'; title = 'Databricks workspace access'; domain = 'Databricks'; command = 'Invoke-DatabricksWorkspaceCollector' }
        @{ id = 'db-billing'; title = 'Databricks billing evidence'; domain = 'Databricks'; command = 'Invoke-DatabricksBillingCollector' }
        @{ id = 'db-compute'; title = 'Databricks compute'; domain = 'Databricks'; command = 'Invoke-DatabricksComputeCollector' }
        @{ id = 'db-workloads'; title = 'Databricks jobs and pipelines'; domain = 'Databricks'; command = 'Invoke-DatabricksWorkloadsCollector' }
        @{ id = 'db-sql'; title = 'Databricks SQL evidence'; domain = 'Databricks'; command = 'Invoke-DatabricksSqlCollector' }
        @{ id = 'db-catalog'; title = 'Unity Catalog'; domain = 'Databricks'; command = 'Invoke-DatabricksUnityCatalogCollector' }
        @{ id = 'db-governance'; title = 'Databricks governance'; domain = 'Databricks'; command = 'Invoke-DatabricksGovernanceCollector' }
        @{ id = 'db-spark'; title = 'Spark performance evidence'; domain = 'Databricks'; command = 'Invoke-DatabricksSparkDeepDiveCollector' }
        @{ id = 'db-assets'; title = 'Optional Databricks assets'; domain = 'Databricks'; command = 'Invoke-DatabricksAssetsCollector' }
    )
}

function Write-AssessmentProgress {
    param([Parameter(Mandatory)][hashtable]$Event)

    if ($env:ASSESSMENT_UI_PROGRESS -eq '1') {
        Write-Host ('AssessmentProgress:' + ($Event | ConvertTo-Json -Depth 10 -Compress))
    }
}

function Write-AssessmentCollectorProgress {
    param(
        [Parameter(Mandatory)][string]$Id,
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Results
    )

    $status = if ($Results.Count -eq 0) { 'skipped' }
        elseif (@($Results | Where-Object status -eq 'failed').Count) { 'fail' }
        elseif (@($Results | Where-Object { $_.status -in @('partial', 'pending telemetry') }).Count) { 'warn' }
        elseif (@($Results | Where-Object status -eq 'passed').Count) { 'pass' }
        else { 'skipped' }
    $detail = if ($Results.Count) {
        ($Results | ForEach-Object { "$($_.name): $($_.status)" }) -join '; '
    } else { 'No workspace or evidence was available for this check.' }
    $sourceResults = @()
    if ($env:ASSESSMENT_UI_PROGRESS -eq '1') {
        $sourceResults = @($Results | ForEach-Object {
            $result = $_
            $sources = @($result.outputs | Where-Object { $_ -like '*.source-status.json' } | ForEach-Object {
                Get-Content -Raw -LiteralPath $_ | ConvertFrom-Json -Depth 100
            })
            @{
                name = $result.name
                status = $result.status
                itemCount = $result.itemCount
                limitations = @($result.limitations)
                error = $result.error
                sources = $sources
            }
        })
    }
    Write-AssessmentProgress -Event @{ id = $Id; status = $status; detail = $detail; results = $sourceResults }
}

function Read-AssessmentConfig {
    param(
        [Parameter(Mandatory)][string]$Path,
        [switch]$AllowEmptyScope
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Assessment scope file '$Path' does not exist."
    }
    $config = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json -Depth 100
    $databricks = $config.PSObject.Properties['databricks']
    $accountId = if ($databricks -and $databricks.Value) { $databricks.Value.PSObject.Properties['accountId'] } else { $null }
    $accountHost = if ($databricks -and $databricks.Value) { $databricks.Value.PSObject.Properties['accountHost'] } else { $null }
    if (($accountId -and $accountId.Value) -or ($accountHost -and $accountHost.Value)) {
        if (-not $accountId -or [string]$accountId.Value -notmatch '^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$' -or
            -not $accountHost -or [string]$accountHost.Value -notmatch '^accounts(?:-[a-z0-9]+)?\.azuredatabricks\.(net|us)$') {
            throw 'Databricks account configuration requires a valid account UUID and an Azure Databricks account hostname (no scheme or path).'
        }
    }
    $customerId = $config.PSObject.Properties['customerId']
    $assessmentId = $config.PSObject.Properties['assessmentId']
    if ($null -eq $customerId -or -not $customerId.Value -or
        $null -eq $assessmentId -or -not $assessmentId.Value) {
        throw 'Assessment config requires customerId and assessmentId.'
    }
    $start = [DateTimeOffset]::Parse($config.analysis.startUtc)
    $end = [DateTimeOffset]::Parse($config.analysis.endUtc)
    if ($start -ge $end) {
        throw 'analysis.startUtc must be before analysis.endUtc.'
    }
    if (-not $AllowEmptyScope -and @($config.azure.subscriptions).Count -eq 0 -and @($config.databricks.workspaces | Where-Object include).Count -eq 0) {
        throw 'Assessment config selects no Azure subscriptions or Databricks workspaces.'
    }
    foreach ($setting in @('maxPages', 'pageSize', 'requestTimeoutSeconds', 'collectorTimeoutSeconds')) {
        $value = $config.analysis.PSObject.Properties[$setting]
        if ($null -ne $value -and [int]$value.Value -le 0) {
            throw "analysis.$setting must be greater than zero."
        }
    }
    foreach ($setting in @('retryCount', 'retryBaseSeconds')) {
        $value = $config.analysis.PSObject.Properties[$setting]
        if ($null -ne $value -and [int]$value.Value -lt 0) {
            throw "analysis.$setting must not be negative."
        }
    }
    return $config
}

function Assert-ReadOnlyAssessment {
    param([Parameter(Mandatory)][object]$Config)

    $mutatingTerms = @('create', 'update', 'delete', 'resize', 'restart', 'terminate', 'optimize', 'vacuum', 'alter', 'merge')
    $serialized = $Config | ConvertTo-Json -Depth 100
    foreach ($term in $mutatingTerms) {
        if ($serialized -match ('"allow' + $term + '"\s*:\s*true')) {
            throw "Read-only assessment config cannot enable '$term'."
        }
    }
}

function New-AssessmentRun {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][string]$ToolkitVersion
    )

    $runId = '{0}-{1}-{2}' -f $Config.assessmentId, (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ'), ([Guid]::NewGuid().ToString('N').Substring(0, 8))
    $configuredRoot = [string]$Config.outputs.root
    $root = if ([IO.Path]::IsPathRooted($configuredRoot)) {
        [IO.Path]::GetFullPath($configuredRoot)
    }
    else {
        [IO.Path]::GetFullPath((Join-Path (Get-Location) $configuredRoot))
    }
    $runRoot = Join-Path $root $runId
    foreach ($directory in @('raw', 'normalized', 'reports', 'logs')) {
        New-Item -ItemType Directory -Path (Join-Path $runRoot $directory) -Force | Out-Null
    }
    $manifest = [ordered]@{
        schemaVersion = '1.0'
        toolkitVersion = $ToolkitVersion
        runId = $runId
        customerId = $Config.customerId
        assessmentId = $Config.assessmentId
        startedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
        completedAtUtc = $null
        status = 'running'
        analysisWindow = @{
            startUtc = $Config.analysis.startUtc
            endUtc = $Config.analysis.endUtc
            timeZone = $Config.analysis.timeZone
        }
        scope = @{
            subscriptions = @($Config.azure.subscriptions)
            resourceGroups = @($Config.azure.resourceGroups)
            resourceGroupIds = @(
                if ($Config.azure.PSObject.Properties['resourceGroupIds']) {
                    $Config.azure.resourceGroupIds
                }
            )
            workspaces = @($Config.databricks.workspaces | Where-Object include | ForEach-Object workspaceUrl)
        }
        collectors = @()
        outputRoot = $runRoot
    }
    Write-JsonFile -Value $manifest -Path (Join-Path $runRoot 'assessment-manifest.json')
    Write-JsonFile -Value $Config -Path (Join-Path $runRoot 'assessment-config.json')
    return [pscustomobject]@{
        RunId = $runId
        Root = $runRoot
        Manifest = $manifest
    }
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory)][AllowNull()][object]$Value,
        [Parameter(Mandatory)][string]$Path
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $Value | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $Path -Encoding utf8
}

function Write-NdjsonFile {
    param(
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Value,
        [Parameter(Mandatory)][string]$Path
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if ($Value.Count -eq 0) {
        [IO.File]::WriteAllText($Path, '', [Text.UTF8Encoding]::new($false))
        return
    }
    $Value | ForEach-Object { $_ | ConvertTo-Json -Depth 100 -Compress } | Set-Content -LiteralPath $Path -Encoding utf8
}

function Get-AssessmentHash {
    param(
        [AllowNull()][string]$Value,
        [Parameter(Mandatory)][object]$Config
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }
    $saltName = [string]$Config.redaction.saltEnvironmentVariable
    $salt = [Environment]::GetEnvironmentVariable($saltName)
    if ([string]::IsNullOrWhiteSpace($salt)) {
        $salt = "$($Config.customerId):$($Config.assessmentId)"
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes("$salt|$Value")
    $digest = [Security.Cryptography.SHA256]::HashData($bytes)
    return [Convert]::ToHexString($digest).ToLowerInvariant()
}

function Get-DatabricksAssessmentToken {
    $token = az account get-access-token --resource $script:DatabricksApplicationId --query accessToken --output tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($token)) {
        throw 'Unable to acquire a Databricks OAuth token from Azure CLI.'
    }
    return $token
}

function Invoke-ReadOnlyDatabricksApi {
    param(
        [Parameter(Mandatory)][string]$WorkspaceUrl,
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [object]$Body,
        [int[]]$ExpectedStatusCodes = @(200),
        [int]$TimeoutSeconds = 120
    )

    if ($Method -eq 'POST' -and $Path -notin $script:AllowedDatabricksPostPaths) {
        throw "POST '$Path' is not approved for the read-only assessment toolkit."
    }
    if ($Method -eq 'POST' -and $Path -eq '/api/2.0/sql/statements') {
        $statement = [string]$Body.statement
        if ($statement -match '(?im)\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|MERGE|OPTIMIZE|VACUUM|RESTORE|TRUNCATE|GRANT|REVOKE|COPY\s+INTO)\b') {
            throw 'Assessment SQL must be read-only.'
        }
    }

    $token = Get-DatabricksAssessmentToken
    try {
        $headers = @{ Authorization = "Bearer $token" }
        $parameters = @{
            Uri = "https://$($WorkspaceUrl.TrimEnd('/'))$Path"
            Method = $Method
            Headers = $headers
            TimeoutSec = $TimeoutSeconds
            UseBasicParsing = $true
            SkipHttpErrorCheck = $true
        }
        if ($null -ne $Body) {
            $parameters.ContentType = 'application/json'
            $parameters.Body = $Body | ConvertTo-Json -Depth 100 -Compress
        }
        $response = Invoke-WebRequest @parameters
    }
    finally {
        $token = $null
        $headers = $null
    }
    if ($response.StatusCode -notin $ExpectedStatusCodes) {
        throw "Databricks API $Method $Path returned HTTP $($response.StatusCode): $($response.Content)"
    }
    if ([string]::IsNullOrWhiteSpace($response.Content)) {
        return $null
    }
    return $response.Content | ConvertFrom-Json -Depth 100
}

function Invoke-WithAssessmentRetry {
    param(
        [Parameter(Mandatory)][scriptblock]$Operation,
        [Parameter(Mandatory)][string]$Description,
        [int]$RetryCount = 3,
        [int]$BaseSeconds = 2,
        [scriptblock]$ShouldRetry
    )

    for ($attempt = 0; $attempt -le $RetryCount; $attempt++) {
        try {
            return & $Operation
        }
        catch {
            $retryAllowed = if ($ShouldRetry) {
                [bool](& $ShouldRetry $_)
            }
            else {
                $true
            }
            if (-not $retryAllowed -or $attempt -ge $RetryCount) {
                throw
            }
            $delay = [Math]::Min(60, $BaseSeconds * [Math]::Pow(2, $attempt))
            Write-Warning "$Description failed on attempt $($attempt + 1): $($_.Exception.Message). Retrying in ${delay}s."
            Start-Sleep -Seconds $delay
        }
    }
}

function New-CollectorResult {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][ValidateSet('passed', 'partial', 'failed', 'skipped', 'pending telemetry')][string]$Status,
        [datetime]$StartedAt,
        [int]$ItemCount = 0,
        [string[]]$Outputs = @(),
        [string[]]$Limitations = @(),
        [string]$ErrorMessage
    )

    return [pscustomobject]@{
        name = $Name
        status = $Status
        startedAtUtc = $StartedAt.ToUniversalTime().ToString('o')
        completedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
        itemCount = $ItemCount
        outputs = $Outputs
        limitations = $Limitations
        error = $ErrorMessage
    }
}

function Get-AssessmentRunStatus {
    param([Parameter(Mandatory)][AllowEmptyCollection()][object[]]$CollectorResults)

    $incomplete = @($CollectorResults | Where-Object {
        $_.status -in @('partial', 'failed', 'pending telemetry')
    })
    if ($incomplete.Count) {
        return 'partial'
    }
    return 'completed'
}
