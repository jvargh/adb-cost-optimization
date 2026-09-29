Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:ExpectedSubscriptionId = '463a82d4-1896-4332-aeeb-618ee5a5aa93'
$script:DatabricksApplicationId = '2ff814a6-3304-4ab8-85cb-cd0e6f879c1d'

function Assert-Command {
    param([Parameter(Mandatory)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not installed or is not available on PATH."
    }
}

function Assert-ExpectedSubscription {
    param([string]$ExpectedSubscriptionId = $script:ExpectedSubscriptionId)

    Assert-Command -Name 'az'
    $account = az account show --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to read the current Azure CLI account.'
    }
    if ($account.id -ne $ExpectedSubscriptionId) {
        throw "Azure CLI subscription '$($account.id)' does not match expected subscription '$ExpectedSubscriptionId'."
    }
    if ($account.state -ne 'Enabled') {
        throw "Azure subscription '$ExpectedSubscriptionId' is not enabled."
    }
    return $account
}

function Get-DatabricksAccessToken {
    $token = az account get-access-token --resource $script:DatabricksApplicationId --query accessToken --output tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($token)) {
        throw 'Unable to acquire an Azure Databricks access token through Azure CLI.'
    }
    return $token
}

function Invoke-DatabricksApi {
    param(
        [Parameter(Mandatory)][string]$WorkspaceUrl,
        [Parameter(Mandatory)][ValidateSet('GET', 'POST', 'PUT', 'PATCH', 'DELETE')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [object]$Body,
        [int[]]$ExpectedStatusCodes = @(200)
    )

    $token = Get-DatabricksAccessToken
    $headers = @{ Authorization = "Bearer $token" }
    $uri = "https://$($WorkspaceUrl.TrimEnd('/'))$Path"

    try {
        $parameters = @{
            Uri                = $uri
            Method             = $Method
            Headers            = $headers
            UseBasicParsing    = $true
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

function Wait-DatabricksState {
    param(
        [Parameter(Mandatory)][scriptblock]$Probe,
        [Parameter(Mandatory)][scriptblock]$IsComplete,
        [Parameter(Mandatory)][string]$Description,
        [scriptblock]$GetStatusText,
        [scriptblock]$GetAbortReason,
        [int]$TimeoutSeconds = 1200,
        [int]$PollSeconds = 15
    )

    $startedAt = Get-Date
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastStatus = $null
    Write-Host "Waiting for $Description (timeout: $TimeoutSeconds seconds; poll: $PollSeconds seconds)..."
    do {
        $value = & $Probe
        $elapsedSeconds = [int]((Get-Date) - $startedAt).TotalSeconds
        $status = if ($GetStatusText) {
            try {
                [string](& $GetStatusText $value)
            }
            catch {
                "In progress (status details are not available yet: $($_.Exception.Message))"
            }
        }
        else {
            'In progress'
        }
        if ($status -ne $lastStatus -or $elapsedSeconds % 60 -lt $PollSeconds) {
            Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] ${Description}: $status (elapsed: ${elapsedSeconds}s)"
            $lastStatus = $status
        }

        if ($GetAbortReason) {
            try {
                $abortReason = [string](& $GetAbortReason $value)
            }
            catch {
                $abortReason = $null
            }
            if (-not [string]::IsNullOrWhiteSpace($abortReason)) {
                throw "$Description cannot continue: $abortReason"
            }
        }
        if (& $IsComplete $value) {
            Write-Host "$Description completed after ${elapsedSeconds}s."
            return $value
        }
        Start-Sleep -Seconds $PollSeconds
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for $Description after $TimeoutSeconds seconds. Last status: $lastStatus"
}

function Read-DeploymentOutputs {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Deployment output file '$Path' does not exist."
    }
    return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json -Depth 100
}

function Write-SanitizedJson {
    param(
        [Parameter(Mandatory)][object]$Value,
        [Parameter(Mandatory)][string]$Path
    )

    $directory = Split-Path -Parent $Path
    if ($directory) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    $Value | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $Path -Encoding utf8
}
