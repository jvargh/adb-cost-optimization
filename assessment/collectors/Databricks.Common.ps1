Set-StrictMode -Version Latest

function Get-DatabricksProperty {
    param(
        [AllowNull()][object]$InputObject,
        [Parameter(Mandatory)][string]$Name,
        [AllowNull()][object]$Default = $null
    )

    if ($null -eq $InputObject) {
        return $Default
    }
    if ($InputObject -is [Collections.IDictionary]) {
        if ($InputObject.Contains($Name) -and $null -ne $InputObject[$Name]) {
            return $InputObject[$Name]
        }
        return $Default
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) {
        return $Default
    }
    return $property.Value
}

function Get-DatabricksDeepDiveTargets {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$Workspace,
        [Parameter(Mandatory)][ValidateSet('deepDiveJobRunIds', 'deepDiveTableNames')][string]$Name
    )

    $hasWorkspaceTargets = if ($Workspace -is [Collections.IDictionary]) {
        $Workspace.Contains($Name)
    } else {
        $null -ne $Workspace.PSObject.Properties[$Name]
    }
    if ($hasWorkspaceTargets) {
        return Get-DatabricksProperty -InputObject $Workspace -Name $Name -Default @()
    }
    $legacyTargets = @(Get-DatabricksProperty -InputObject $Config.databricks -Name $Name -Default @())
    if ($legacyTargets.Count -gt 0 -and @($Config.databricks.workspaces | Where-Object include).Count -gt 1) {
        throw "Global $Name targets are ambiguous across multiple included workspaces. Assign targets to the intended workspace or clear the global list."
    }
    return $legacyTargets
}

function Get-DatabricksAnalysisSetting {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][string]$Name,
        [AllowNull()][object]$Default = $null
    )

    return Get-DatabricksProperty -InputObject (Get-DatabricksProperty -InputObject $Config -Name 'analysis') -Name $Name -Default $Default
}

function Get-DatabricksWorkspaceKey {
    param([Parameter(Mandatory)][object]$Workspace)

    $workspaceId = [string](Get-DatabricksProperty -InputObject $Workspace -Name 'workspaceId')
    if (-not [string]::IsNullOrWhiteSpace($workspaceId)) {
        return $workspaceId
    }
    $name = [string](Get-DatabricksProperty -InputObject $Workspace -Name 'name' -Default 'workspace')
    return ($name -replace '[^A-Za-z0-9._-]', '_')
}

function Get-DatabricksOutputDirectory {
    param(
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][object]$Workspace
    )

    $path = Join-Path $RunContext.Root (Join-Path 'raw\databricks' (Get-DatabricksWorkspaceKey -Workspace $Workspace))
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
}

function Add-DatabricksQueryParameter {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Value
    )

    $separator = if ($Path.Contains('?')) { '&' } else { '?' }
    return "$Path$separator$([Uri]::EscapeDataString($Name))=$([Uri]::EscapeDataString($Value))"
}

function Invoke-DatabricksCollectorApi {
    param(
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [AllowNull()][object]$Body,
        [int[]]$ExpectedStatusCodes = @(200),
        [int]$TimeoutSeconds = 120
    )

    if ($Method -eq 'POST' -and $Path -notin $script:AllowedDatabricksPostPaths) {
        throw "POST '$Path' is not approved for Databricks assessment collection."
    }
    if ($Method -eq 'POST' -and $Path -eq '/api/2.0/sql/statements') {
        $statement = [string](Get-DatabricksProperty -InputObject $Body -Name 'statement')
        if ([string]::IsNullOrWhiteSpace($statement)) {
            throw 'SQL statement POST requires a statement.'
        }
        if ($statement -match '(?im)\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|MERGE|OPTIMIZE|VACUUM|RESTORE|TRUNCATE|GRANT|REVOKE|COPY\s+INTO|CALL)\b') {
            throw 'Assessment SQL must be read-only.'
        }
    }

    $token = Get-DatabricksAssessmentToken
    try {
        $headers = @{ Authorization = "Bearer $token" }
        $parameters = @{
            Uri = "https://$($HostName.TrimEnd('/'))$Path"
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
        $message = [string]$response.Content
        if ($message.Length -gt 2000) {
            $message = $message.Substring(0, 2000)
        }
        throw "Databricks API $Method $Path returned HTTP $($response.StatusCode): $message"
    }
    if ([string]::IsNullOrWhiteSpace($response.Content)) {
        return $null
    }
    return $response.Content | ConvertFrom-Json -Depth 100
}

function Invoke-DatabricksCollectorRequest {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][ValidateSet('GET', 'POST')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [AllowNull()][object]$Body
    )

    $retryCount = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'retryCount' -Default 3)
    $retryBaseSeconds = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'retryBaseSeconds' -Default 2)
    $timeoutSeconds = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'requestTimeoutSeconds' -Default 120)
    return Invoke-WithAssessmentRetry `
        -Description "$Method $Path" `
        -RetryCount $retryCount `
        -BaseSeconds $retryBaseSeconds `
        -ShouldRetry {
            param($errorRecord)
            $message = [string]$errorRecord.Exception.Message
            $message -notmatch 'HTTP (400|401|403|404)\b|requires a statement|must be read-only|not approved'
        } `
        -Operation {
            Invoke-DatabricksCollectorApi -HostName $HostName -Method $Method -Path $Path -Body $Body -TimeoutSeconds $timeoutSeconds
        }
}

function Invoke-DatabricksPagedGet {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ItemsProperty,
        [string]$TokenProperty = 'next_page_token',
        [string]$TokenParameter = 'page_token'
    )

    $maxPages = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'maxPages' -Default 100)
    $items = [Collections.Generic.List[object]]::new()
    $token = $null
    $page = 0
    do {
        $page++
        $requestPath = $Path
        if (-not [string]::IsNullOrWhiteSpace([string]$token)) {
            $requestPath = Add-DatabricksQueryParameter -Path $requestPath -Name $TokenParameter -Value ([string]$token)
        }

        $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $HostName -Method GET -Path $requestPath
        foreach ($item in @((Get-DatabricksProperty -InputObject $response -Name $ItemsProperty -Default @()))) {
            if ($null -ne $item) {
                $items.Add($item)
            }
        }

        $token = Get-DatabricksProperty -InputObject $response -Name $TokenProperty
    } while (-not [string]::IsNullOrWhiteSpace([string]$token) -and $page -lt $maxPages)

    return [pscustomobject]@{
        items = @($items)
        pages = $page
        truncated = -not [string]::IsNullOrWhiteSpace([string]$token)
        nextPageToken = $token
    }
}

function Invoke-DatabricksPagedPost {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][hashtable]$Body,
        [Parameter(Mandatory)][string]$ItemsProperty,
        [string]$ContinuationProperty = 'next_page'
    )

    $maxPages = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'maxPages' -Default 100)
    $items = [Collections.Generic.List[object]]::new()
    $requestBody = $Body.Clone()
    $continuation = $null
    $page = 0
    do {
        $page++
        $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $HostName -Method POST -Path $Path -Body $requestBody
        foreach ($item in @((Get-DatabricksProperty -InputObject $response -Name $ItemsProperty -Default @()))) {
            if ($null -ne $item) {
                $items.Add($item)
            }
        }
        $continuation = Get-DatabricksProperty -InputObject $response -Name $ContinuationProperty
        if ($null -ne $continuation) {
            foreach ($property in $continuation.PSObject.Properties) {
                $requestBody[$property.Name] = $property.Value
            }
        }
    } while ($null -ne $continuation -and $page -lt $maxPages)

    return [pscustomobject]@{
        items = @($items)
        pages = $page
        truncated = $null -ne $continuation
        continuation = $continuation
    }
}

function Invoke-DatabricksScimPagedGet {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][string]$HostName,
        [Parameter(Mandatory)][string]$Path
    )

    $maxPages = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'maxPages' -Default 100)
    $pageSize = [Math]::Min(1000, [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'pageSize' -Default 100))
    $items = [Collections.Generic.List[object]]::new()
    $startIndex = 1
    $page = 0
    $totalResults = 0
    do {
        $page++
        $requestPath = Add-DatabricksQueryParameter -Path $Path -Name count -Value ([string]$pageSize)
        $requestPath = Add-DatabricksQueryParameter -Path $requestPath -Name startIndex -Value ([string]$startIndex)
        $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $HostName -Method GET -Path $requestPath
        $resources = @((Get-DatabricksProperty -InputObject $response -Name 'Resources' -Default @()))
        foreach ($resource in $resources) { $items.Add($resource) }
        $totalResults = [int](Get-DatabricksProperty -InputObject $response -Name 'totalResults' -Default $items.Count)
        $startIndex += $resources.Count
    } while ($resources.Count -gt 0 -and $startIndex -le $totalResults -and $page -lt $maxPages)

    return [pscustomobject]@{
        items = @($items)
        pages = $page
        truncated = $startIndex -le $totalResults
        nextStartIndex = $startIndex
    }
}

function Protect-DatabricksAssessmentValue {
    param(
        [AllowNull()][object]$Value,
        [Parameter(Mandatory)][object]$Config,
        [string]$PropertyName = ''
    )

    if ($null -eq $Value) {
        return $null
    }
    $redaction = Get-DatabricksProperty -InputObject $Config -Name 'redaction'
    if ($PropertyName -match '(?i)(secret|password|credential|access.?token|private.?key)') {
        return '[redacted]'
    }
    if ($PropertyName -match '(?i)(spark_env_vars|base_parameters|notebook_params|python_params|spark_submit_params|jar_params|job_parameters)$') {
        return '[redacted]'
    }
    if ([bool](Get-DatabricksProperty -InputObject $redaction -Name 'omitQueryText' -Default $true) -and
        $PropertyName -match '(?i)^(query_text|statement_text|queryText|statement)$') {
        return '[omitted]'
    }
    if ([bool](Get-DatabricksProperty -InputObject $redaction -Name 'hashIdentities' -Default $true) -and
        $PropertyName -match '(?i)(owner|creator|user_name|userName|executed_by|run_as|service_principal|email|identity)') {
        return Get-AssessmentHash -Value ([string]$Value) -Config $Config
    }
    if ([bool](Get-DatabricksProperty -InputObject $redaction -Name 'hashNotebookPaths' -Default $true) -and
        $PropertyName -match '(?i)(notebook_path|notebookPath)') {
        return Get-AssessmentHash -Value ([string]$Value) -Config $Config
    }
    if ([bool](Get-DatabricksProperty -InputObject $redaction -Name 'hashTableNames' -Default $false) -and
        $PropertyName -match '(?i)^(catalog_name|schema_name|table_name|full_name)$') {
        return Get-AssessmentHash -Value ([string]$Value) -Config $Config
    }
    if ($Value -is [Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $copy[[string]$key] = Protect-DatabricksAssessmentValue -Value $Value[$key] -Config $Config -PropertyName ([string]$key)
        }
        return [pscustomobject]$copy
    }
    if ($Value -is [pscustomobject]) {
        $copy = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $copy[$property.Name] = Protect-DatabricksAssessmentValue -Value $property.Value -Config $Config -PropertyName $property.Name
        }
        return [pscustomobject]$copy
    }
    if ($Value -is [Collections.IEnumerable] -and $Value -isnot [string]) {
        return @($Value | ForEach-Object { Protect-DatabricksAssessmentValue -Value $_ -Config $Config -PropertyName $PropertyName })
    }
    return $Value
}

function Write-DatabricksDataset {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][object]$Workspace,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][AllowNull()][AllowEmptyCollection()][object[]]$Items
    )

    $directory = Get-DatabricksOutputDirectory -RunContext $RunContext -Workspace $Workspace
    $path = Join-Path $directory "$Name.ndjson"
    $protected = @($Items | Where-Object { $null -ne $_ } | ForEach-Object {
        Protect-DatabricksAssessmentValue -Value $_ -Config $Config
    })
    Write-NdjsonFile -Value $protected -Path $path
    return $path
}

function Write-DatabricksSourceStatus {
    param(
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][object]$Workspace,
        [Parameter(Mandatory)][string]$CollectorName,
        [Parameter(Mandatory)][object[]]$Sources
    )

    $directory = Get-DatabricksOutputDirectory -RunContext $RunContext -Workspace $Workspace
    $path = Join-Path $directory "$CollectorName.source-status.json"
    Write-JsonFile -Value @($Sources) -Path $path
    return $path
}

function New-DatabricksSourceStatus {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][ValidateSet('passed', 'partial', 'failed', 'skipped', 'pending telemetry')][string]$Status,
        [int]$ItemCount = 0,
        [string]$Output,
        [string]$Message
    )

    return [pscustomobject]@{
        source = $Source
        status = $Status
        itemCount = $ItemCount
        output = $Output
        message = $Message
        extractedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    }
}

function Get-DatabricksCollectorStatus {
    param([Parameter(Mandatory)][object[]]$Sources)

    $statuses = @($Sources | ForEach-Object status)
    if ($statuses -contains 'failed' -or $statuses -contains 'partial') {
        return 'partial'
    }
    if ($statuses.Count -gt 0 -and @($statuses | Where-Object { $_ -eq 'pending telemetry' }).Count -eq $statuses.Count) {
        return 'pending telemetry'
    }
    if ($statuses -contains 'pending telemetry') {
        return 'partial'
    }
    if ($statuses.Count -gt 0 -and @($statuses | Where-Object { $_ -in @('skipped', 'pending telemetry') }).Count -eq $statuses.Count) {
        return 'skipped'
    }
    return 'passed'
}

function Get-DatabricksSqlWarehouseId {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$Workspace
    )

    $workspaceWarehouse = [string](Get-DatabricksProperty -InputObject $Workspace -Name 'sqlWarehouseId')
    if (-not [string]::IsNullOrWhiteSpace($workspaceWarehouse)) {
        return $workspaceWarehouse
    }
    $databricks = Get-DatabricksProperty -InputObject $Config -Name 'databricks'
    return [string](Get-DatabricksProperty -InputObject $databricks -Name 'sqlWarehouseId')
}

function ConvertFrom-DatabricksSqlRows {
    param(
        [Parameter(Mandatory)][object]$Response,
        [string[]]$Columns = @()
    )

    if ($Columns.Count -eq 0) {
        $manifest = Get-DatabricksProperty -InputObject $Response -Name 'manifest'
        $schema = Get-DatabricksProperty -InputObject $manifest -Name 'schema'
        $Columns = @((Get-DatabricksProperty -InputObject $schema -Name 'columns' -Default @()) | ForEach-Object name)
    }
    $result = Get-DatabricksProperty -InputObject $Response -Name 'result'
    $rows = @(Get-DatabricksProperty -InputObject $result -Name 'data_array' -Default @())
    $objects = [Collections.Generic.List[object]]::new()
    foreach ($row in $rows) {
        $cells = @($row)
        if ($cells.Count -ne $Columns.Count) {
            throw "Databricks SQL result row has $($cells.Count) cells for $($Columns.Count) columns."
        }
        $record = [ordered]@{}
        for ($index = 0; $index -lt $Columns.Count; $index++) {
            $record[$Columns[$index]] = $cells[$index]
        }
        $objects.Add([pscustomobject]$record)
    }
    return @($objects)
}

function Invoke-DatabricksSqlQuery {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$Workspace,
        [Parameter(Mandatory)][string]$Statement,
        [object[]]$Parameters = @()
    )

    $warehouseId = Get-DatabricksSqlWarehouseId -Config $Config -Workspace $Workspace
    if ([string]::IsNullOrWhiteSpace($warehouseId)) {
        throw 'No SQL Warehouse ID is configured for read-only metadata queries.'
    }
    $hostName = [string](Get-DatabricksProperty -InputObject $Workspace -Name 'workspaceUrl')
    $body = [ordered]@{
        warehouse_id = $warehouseId
        statement = $Statement
        wait_timeout = '10s'
        on_wait_timeout = 'CONTINUE'
        disposition = 'INLINE'
        format = 'JSON_ARRAY'
        parameters = @($Parameters)
    }
    $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method POST -Path '/api/2.0/sql/statements' -Body $body
    $statementId = [string](Get-DatabricksProperty -InputObject $response -Name 'statement_id')
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds([int](Get-DatabricksAnalysisSetting -Config $Config -Name 'collectorTimeoutSeconds' -Default 1800))
    while ((Get-DatabricksProperty -InputObject (Get-DatabricksProperty -InputObject $response -Name 'status') -Name 'state') -in @('PENDING', 'RUNNING')) {
        if ([DateTimeOffset]::UtcNow -ge $deadline) {
            throw "SQL statement '$statementId' exceeded the collector timeout and remains pending."
        }
        Start-Sleep -Seconds 2
        $response = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path "/api/2.0/sql/statements/$statementId"
    }
    $state = [string](Get-DatabricksProperty -InputObject (Get-DatabricksProperty -InputObject $response -Name 'status') -Name 'state')
    if ($state -ne 'SUCCEEDED') {
        $errorValue = Get-DatabricksProperty -InputObject (Get-DatabricksProperty -InputObject $response -Name 'status') -Name 'error'
        throw "SQL statement '$statementId' ended in state '$state': $($errorValue | ConvertTo-Json -Depth 10 -Compress)"
    }

    $rows = [Collections.Generic.List[object]]::new()
    $manifest = Get-DatabricksProperty -InputObject $response -Name 'manifest'
    $schema = Get-DatabricksProperty -InputObject $manifest -Name 'schema'
    $columns = @((Get-DatabricksProperty -InputObject $schema -Name 'columns' -Default @()) | ForEach-Object name)
    foreach ($row in @(ConvertFrom-DatabricksSqlRows -Response $response -Columns $columns)) {
        $rows.Add($row)
    }
    $nextChunk = [string](Get-DatabricksProperty -InputObject (Get-DatabricksProperty -InputObject $response -Name 'result') -Name 'next_chunk_internal_link')
    $pages = 1
    $maxPages = [int](Get-DatabricksAnalysisSetting -Config $Config -Name 'maxPages' -Default 100)
    while (-not [string]::IsNullOrWhiteSpace($nextChunk) -and $pages -lt $maxPages) {
        $pages++
        $chunk = Invoke-DatabricksCollectorRequest -Config $Config -HostName $hostName -Method GET -Path $nextChunk
        foreach ($row in @(ConvertFrom-DatabricksSqlRows -Response $chunk -Columns $columns)) {
            $rows.Add($row)
        }
        $nextChunk = [string](Get-DatabricksProperty -InputObject (Get-DatabricksProperty -InputObject $chunk -Name 'result') -Name 'next_chunk_internal_link')
    }
    return [pscustomobject]@{
        statementId = $statementId
        rows = @($rows)
        pages = $pages
        truncated = -not [string]::IsNullOrWhiteSpace($nextChunk)
    }
}

function ConvertTo-DatabricksTableIdentifier {
    param([Parameter(Mandatory)][string]$Name)

    $part = '(?:`(?:[^`\r\n]|``)+`|[A-Za-z_][A-Za-z0-9_]*)'
    if ($Name -notmatch "^\s*$part(?:\s*\.\s*$part){0,2}\s*$") {
        throw 'Table name must contain one to three SQL identifier components; quote special names with backticks.'
    }
    return (([regex]::Matches($Name, $part) | ForEach-Object {
        $value = $_.Value
        if ($value.StartsWith('`')) {
            $value = $value.Substring(1, $value.Length - 2).Replace('``', '`')
        }
        '`' + $value.Replace('`', '``') + '`'
    }) -join '.')
}

function Invoke-DatabricksSqlFile {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$Workspace,
        [Parameter(Mandatory)][string]$FileName,
        [object[]]$Parameters = @()
    )

    $path = Join-Path $PSScriptRoot (Join-Path 'sql' $FileName)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Databricks SQL asset '$path' is unavailable."
    }
    $statement = Get-Content -Raw -LiteralPath $path
    if ($FileName -eq 'DatabricksTableDetail.sql') {
        $tableParameters = @($Parameters | Where-Object { (Get-DatabricksProperty -InputObject $_ -Name 'name') -eq 'table_name' })
        if ($tableParameters.Count -ne 1) {
            throw 'DESCRIBE DETAIL requires exactly one table_name parameter.'
        }
        # Some warehouses parse IDENTIFIER(...) as a literal table name in DESCRIBE DETAIL.
        $identifier = ConvertTo-DatabricksTableIdentifier -Name ([string](Get-DatabricksProperty -InputObject $tableParameters[0] -Name 'value'))
        $statement = $statement.Replace('{{table_identifier}}', $identifier)
        $Parameters = @($Parameters | Where-Object { (Get-DatabricksProperty -InputObject $_ -Name 'name') -ne 'table_name' })
    }
    return Invoke-DatabricksSqlQuery -Config $Config -Workspace $Workspace -Statement $statement -Parameters $Parameters
}

function New-DatabricksTimeParameters {
    param([Parameter(Mandatory)][object]$Config)

    function ConvertTo-AssessmentUtcTimestamp {
        param([Parameter(Mandatory)][object]$Value)

        $date = if ($Value -is [datetime]) {
            [DateTimeOffset]::new([DateTime]::SpecifyKind([datetime]$Value, [DateTimeKind]::Utc))
        }
        elseif ($Value -is [DateTimeOffset]) {
            ([DateTimeOffset]$Value).ToUniversalTime()
        }
        else {
            [DateTimeOffset]::Parse(
                [string]$Value,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal
            )
        }
        return $date.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ', [Globalization.CultureInfo]::InvariantCulture)
    }

    $startUtc = ConvertTo-AssessmentUtcTimestamp -Value $Config.analysis.startUtc
    $endUtc = ConvertTo-AssessmentUtcTimestamp -Value $Config.analysis.endUtc

    return @(
        @{ name = 'start_utc'; value = $startUtc; type = 'TIMESTAMP' },
        @{ name = 'end_utc'; value = $endUtc; type = 'TIMESTAMP' }
    )
}

function Invoke-DatabricksSqlDatasetCollection {
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext,
        [Parameter(Mandatory)][object]$Workspace,
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$FileName,
        [Parameter(Mandatory)][string]$OutputName,
        [object[]]$Parameters = @()
    )

    if ([string]::IsNullOrWhiteSpace((Get-DatabricksSqlWarehouseId -Config $Config -Workspace $Workspace))) {
        return New-DatabricksSourceStatus -Source $Source -Status 'pending telemetry' -Message 'A SQL Warehouse ID is required to read this source.'
    }
    try {
        $result = Invoke-DatabricksSqlFile -Config $Config -Workspace $Workspace -FileName $FileName -Parameters $Parameters
        $output = Write-DatabricksDataset -Config $Config -RunContext $RunContext -Workspace $Workspace -Name $OutputName -Items @($result.rows)
        $status = if ($result.truncated) { 'partial' } else { 'passed' }
        $message = if ($result.truncated) { 'The configured page limit was reached; the continuation was not discarded silently.' } else { $null }
        return New-DatabricksSourceStatus -Source $Source -Status $status -ItemCount @($result.rows).Count -Output $output -Message $message
    }
    catch {
        return New-DatabricksSourceStatus -Source $Source -Status failed -Message $_.Exception.Message
    }
}
