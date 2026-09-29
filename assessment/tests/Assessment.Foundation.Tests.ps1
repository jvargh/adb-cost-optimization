BeforeAll {
    $assessmentRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    . (Join-Path $assessmentRoot 'scripts\Assessment.Common.ps1')
    . (Join-Path $assessmentRoot 'collectors\Databricks.Common.ps1')
    $exampleConfig = Join-Path $assessmentRoot 'config\assessment-scope.example.json'
}

Describe 'Assessment configuration' {
    It 'loads the example scope with selected Azure and Databricks targets' {
        $config = Read-AssessmentConfig -Path $exampleConfig

        $config.customerId | Should -Not -BeNullOrEmpty
        $config.assessmentId | Should -Not -BeNullOrEmpty
        @($config.azure.subscriptions).Count | Should -BeGreaterThan 0
        @($config.databricks.workspaces | Where-Object include).Count | Should -BeGreaterThan 0
        ([DateTimeOffset]$config.analysis.startUtc) | Should -BeLessThan ([DateTimeOffset]$config.analysis.endUtc)
    }

    It 'rejects missing identifiers, invalid windows, empty scope, and invalid limits' -ForEach @(
        @{
            Case = 'missing-identifiers'
            Config = @{
                analysis = @{ startUtc = '2026-01-01T00:00:00Z'; endUtc = '2026-02-01T00:00:00Z' }
                azure = @{ subscriptions = @('sub') }
                databricks = @{ workspaces = @() }
            }
            Error = '*customerId and assessmentId*'
        },
        @{
            Case = 'invalid-window'
            Config = @{
                customerId = 'c'; assessmentId = 'a'
                analysis = @{ startUtc = '2026-02-01T00:00:00Z'; endUtc = '2026-01-01T00:00:00Z' }
                azure = @{ subscriptions = @('sub') }
                databricks = @{ workspaces = @() }
            }
            Error = '*startUtc must be before*'
        },
        @{
            Case = 'empty-scope'
            Config = @{
                customerId = 'c'; assessmentId = 'a'
                analysis = @{ startUtc = '2026-01-01T00:00:00Z'; endUtc = '2026-02-01T00:00:00Z' }
                azure = @{ subscriptions = @() }
                databricks = @{ workspaces = @() }
            }
            Error = '*selects no Azure subscriptions*'
        },
        @{
            Case = 'invalid-timeout'
            Config = @{
                customerId = 'c'; assessmentId = 'a'
                analysis = @{ startUtc = '2026-01-01T00:00:00Z'; endUtc = '2026-02-01T00:00:00Z'; collectorTimeoutSeconds = 0 }
                azure = @{ subscriptions = @('sub') }
                databricks = @{ workspaces = @() }
            }
            Error = '*collectorTimeoutSeconds must be greater than zero*'
        }
    ) {
        $path = Join-Path $TestDrive "$Case.json"
        $Config | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $path
        { Read-AssessmentConfig -Path $path } | Should -Throw $Error
    }

    It 'rejects every mutation opt-in regardless of casing' -ForEach @(
        'allowCreate', 'allowUpdate', 'allowDelete', 'allowResize', 'allowRestart',
        'allowTerminate', 'allowOptimize', 'allowVacuum', 'allowAlter', 'allowMerge'
    ) {
        $config = [pscustomobject]@{ safety = [pscustomobject]@{ $_ = $true } }
        { Assert-ReadOnlyAssessment -Config $config } | Should -Throw '*Read-only*'
    }
}

Describe 'Run manifests and repeated execution' {
    It 'creates schema-complete, distinct run roots for immediate repeated runs' {
        $config = [pscustomobject]@{
            customerId = 'customer'
            assessmentId = 'assessment'
            azure = [pscustomobject]@{ subscriptions = @('sub'); resourceGroups = @('rg') }
            databricks = [pscustomobject]@{
                workspaces = @([pscustomobject]@{ include = $true; workspaceUrl = 'example.azuredatabricks.net' })
            }
            analysis = [pscustomobject]@{
                startUtc = '2026-01-01T00:00:00Z'
                endUtc = '2026-02-01T00:00:00Z'
                timeZone = 'UTC'
            }
            outputs = [pscustomobject]@{ root = (Join-Path $TestDrive 'runs') }
        }

        $first = New-AssessmentRun -Config $config -ToolkitVersion 'test'
        $second = New-AssessmentRun -Config $config -ToolkitVersion 'test'

        $first.RunId | Should -Not -Be $second.RunId
        $first.Root | Should -Not -Be $second.Root
        foreach ($run in @($first, $second)) {
            $manifest = Get-Content -Raw -LiteralPath (Join-Path $run.Root 'assessment-manifest.json') | ConvertFrom-Json
            $manifest.schemaVersion | Should -Be '1.0'
            $manifest.status | Should -Be 'running'
            $manifest.scope.subscriptions | Should -Contain 'sub'
            foreach ($directory in @('raw', 'normalized', 'reports', 'logs')) {
                Test-Path -LiteralPath (Join-Path $run.Root $directory) | Should -BeTrue
            }
        }
    }

    It 'marks partial and pending telemetry runs as partial without treating skips as failure' {
        (Get-AssessmentRunStatus -CollectorResults @(
            [pscustomobject]@{ status = 'passed' },
            [pscustomobject]@{ status = 'skipped' }
        )) | Should -Be 'completed'
        (Get-AssessmentRunStatus -CollectorResults @(
            [pscustomobject]@{ status = 'passed' },
            [pscustomobject]@{ status = 'partial' }
        )) | Should -Be 'partial'
        (Get-AssessmentRunStatus -CollectorResults @(
            [pscustomobject]@{ status = 'pending telemetry' }
        )) | Should -Be 'partial'
    }
}

Describe 'Structured readiness evidence' {
    BeforeEach {
        $script:previousProgress = $env:ASSESSMENT_UI_PROGRESS
        $env:ASSESSMENT_UI_PROGRESS = '1'
        Mock Write-AssessmentProgress { $script:progressEvent = $Event }
    }

    AfterEach {
        $env:ASSESSMENT_UI_PROGRESS = $script:previousProgress
    }

    It 'preserves source-level causes and skipped statuses in collector progress' {
        $path = Join-Path $TestDrive 'billing.source-status.json'
        @(
            @{ source = 'billing'; status = 'pending telemetry'; message = 'A SQL Warehouse ID is required to read this source.' },
            @{ source = 'identities'; status = 'skipped'; message = 'Disabled by scope.' }
        ) | ConvertTo-Json | Set-Content -LiteralPath $path
        $result = New-CollectorResult -Name 'Databricks billing [42]' -Status partial -StartedAt (Get-Date) -Outputs @($path)
        Write-AssessmentCollectorProgress -Id 'db-billing' -Results @($result)
        $event = $script:progressEvent | ConvertTo-Json -Depth 10 | ConvertFrom-Json
        @($event.results).Count | Should -Be 1
        @($event.results[0].sources).Count | Should -Be 2
        $event.results[0].sources[0].message | Should -Be 'A SQL Warehouse ID is required to read this source.'
        $event.results[0].sources[1].status | Should -Be 'skipped'
        $result.status | Should -Be 'partial'
    }

    It 'preserves Azure limitations without inventing source details' {
        $result = New-CollectorResult -Name 'Azure Cost Management' -Status partial -StartedAt (Get-Date) -Limitations @('Access probe only.')
        Write-AssessmentCollectorProgress -Id 'azure-cost' -Results @($result)
        $script:progressEvent.results[0].limitations | Should -Contain 'Access probe only.'
        @($script:progressEvent.results[0].sources).Count | Should -Be 0
    }

    It 'does not read source files when progress is disabled' {
        $env:ASSESSMENT_UI_PROGRESS = ''
        $result = New-CollectorResult -Name 'test' -Status partial -StartedAt (Get-Date) -Outputs @('missing.source-status.json')
        { Write-AssessmentCollectorProgress -Id 'test' -Results @($result) } | Should -Not -Throw
    }
}

Describe 'Retry behavior' {
    It 'uses bounded exponential delays and returns the eventual value' {
        $script:attempts = 0
        Mock Start-Sleep {}
        $result = Invoke-WithAssessmentRetry -Description test -RetryCount 3 -BaseSeconds 2 -Operation {
            $script:attempts++
            if ($script:attempts -lt 3) { throw 'throttled' }
            'ok'
        }

        $result | Should -Be 'ok'
        $script:attempts | Should -Be 3
        Assert-MockCalled Start-Sleep -Times 1 -ParameterFilter { $Seconds -eq 2 }
        Assert-MockCalled Start-Sleep -Times 1 -ParameterFilter { $Seconds -eq 4 }
    }

    It 'stops after the configured retry count and preserves the final error' {
        Mock Start-Sleep {}
        { Invoke-WithAssessmentRetry -Description test -RetryCount 1 -BaseSeconds 1 -Operation { throw 'still throttled' } } |
            Should -Throw '*still throttled*'
        Assert-MockCalled Start-Sleep -Times 1
    }
}

Describe 'Databricks request authentication and timeout' {
    It 'uses a bearer token and propagates the request timeout without returning the token' {
        Mock Get-DatabricksAssessmentToken { 'sensitive-token' }
        Mock Invoke-WebRequest {
            [pscustomobject]@{ StatusCode = 200; Content = '{"ok":true}' }
        } -ParameterFilter {
            $Headers.Authorization -eq 'Bearer sensitive-token' -and $TimeoutSec -eq 17
        }

        $result = Invoke-DatabricksCollectorApi -HostName 'example.azuredatabricks.net' -Method GET -Path '/api/2.0/clusters/list' -TimeoutSeconds 17

        $result.ok | Should -BeTrue
        Assert-MockCalled Invoke-WebRequest -Times 1 -ParameterFilter {
            $Headers.Authorization -eq 'Bearer sensitive-token' -and $TimeoutSec -eq 17
        }
        ($result | ConvertTo-Json) | Should -Not -Match 'sensitive-token'
    }
}
