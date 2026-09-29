[CmdletBinding()]
param(
    [ValidateSet('127.0.0.1', '::1', 'localhost')]
    [string]$HostAddress = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,
    [string]$OutputRoot = (Join-Path $PSScriptRoot '..\assessment\output'),
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$server = Join-Path $PSScriptRoot 'server\assessment_server.py'
$index = Join-Path $PSScriptRoot 'dist\index.html'
if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
    throw "Assessment UI server not found: $server"
}
if (-not (Test-Path -LiteralPath $index -PathType Leaf)) {
    throw "Production UI bundle not found: $index. Build the UI before starting the host."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw 'Python 3 is required and was not found on PATH.'
}

$resolvedOutputRoot = [IO.Path]::GetFullPath($OutputRoot, $PSScriptRoot)
New-Item -ItemType Directory -Path $resolvedOutputRoot -Force | Out-Null
$urlHost = if ($HostAddress -eq '::1') { '[::1]' } else { $HostAddress }
$url = "http://${urlHost}:$Port"

if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        param($Target)
        Start-Sleep -Milliseconds 750
        Start-Process $Target
    } -ArgumentList $url | Out-Null
}

Write-Host "Starting Azure Databricks Cost Assessment UI at $url"
Write-Host 'Press Ctrl+C to stop.'
& $python.Source $server `
    --host $HostAddress `
    --port $Port `
    --output-root $resolvedOutputRoot `
    --dist-index ([IO.Path]::GetFullPath($index))
exit $LASTEXITCODE
