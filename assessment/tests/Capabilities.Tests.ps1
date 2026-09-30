Describe 'Optional capability collection' {
    BeforeAll {
        $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
        . (Join-Path $root 'scripts\Assessment.Common.ps1')
        . (Join-Path $root 'collectors\Databricks.Common.ps1')
        . (Join-Path $root 'collectors\DatabricksAssets.ps1')
        . (Join-Path $root 'collectors\Databricks.ps1')
    }
    It 'skips assets by default without needing workspace configuration' {
        $result = Invoke-DatabricksAssetsCollector -Config ([pscustomobject]@{}) -RunContext ([pscustomobject]@{})
        $result.status | Should -Be skipped
    }
    It 'protects notification recipients while preserving task arrays and failure routing' {
        $config = [pscustomobject]@{ customerId = 'test'; assessmentId = 'privacy'; redaction = @{ hashIdentities = $true; saltEnvironmentVariable = 'CAPABILITY_TEST_REDACTION_SALT' } }
        $value = @{ tasks = @(@{ task_key = 'one'; email_notifications = @{ on_failure = @('person@example.test'); on_success = @() } }) }
        $safe = Protect-DatabricksAssessmentValue -Value $value -Config $config
        $json = $safe | ConvertTo-Json -Depth 10
        $json | Should -Not -Match 'person@example'
        $safe.tasks | Should -HaveCount 1
        $safe.tasks[0].email_notifications.on_failure | Should -HaveCount 1
        $safe.tasks[0].email_notifications.on_success | Should -HaveCount 0
        $json | Should -Match '"tasks":\s*\['
    }
    It 'retains failure status rather than claiming an empty successful inventory' {
        Mock Invoke-DatabricksPagedGet { throw 'access denied' }
        $config = [pscustomobject]@{ capabilities = @{ assets = @('repos') }; databricks = @{ workspaces = @(@{ include = $true; workspaceId = '42'; workspaceUrl = 'fake' }) } }
        $result = Invoke-DatabricksAssetsCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        $result.status | Should -Be partial
        (Get-Content -LiteralPath $result.outputs[0] -Raw | ConvertFrom-Json)[0].status | Should -Be failed
        $result.limitations | Should -Match 'access denied'
        Assert-MockCalled Invoke-DatabricksPagedGet -Times 1 -Exactly
    }
    It 'collects selected metadata and exposes pagination limits' {
        Mock Invoke-DatabricksPagedGet { [pscustomobject]@{ items = @(@{ id = 'repo1'; name = 'repo' }); truncated = $true } }
        $config = [pscustomobject]@{ capabilities = @{ assets = @('repos') }; databricks = @{ workspaces = @(@{ include = $true; workspaceId = '42'; workspaceUrl = 'fake' }) } }
        $result = Invoke-DatabricksAssetsCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        $result.status | Should -Be partial
        $result.limitations | Should -Match 'incomplete'
    }
    It 'rejects out-of-range native concurrency before collectors execute' {
        $config = [pscustomobject]@{ capabilities = @{ concurrency = 5 } }
        { Invoke-DatabricksAssessmentCollectors -Config $config -RunContext ([pscustomobject]@{}) } | Should -Throw '*between 1 and 4*'
    }
    It 'initializes bounded parallel collectors without cloud targets' {
        $config = [pscustomobject]@{ capabilities = @{ concurrency = 2 }; databricks = @{ workspaces = @() } }
        $results = @(Invoke-DatabricksAssessmentCollectors -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive }))
        @($results | Where-Object status -eq 'failed').Count | Should -Be 0
        @($results | Where-Object name -eq 'Databricks optional assets').Count | Should -Be 1
    }
    It 'pages MLflow experiment search tokens through the read-only POST allowlist' {
        Mock Invoke-DatabricksCollectorRequest {
            if ($Body.ContainsKey('page_token')) { return [pscustomobject]@{ experiments = @(@{ experiment_id = '2' }); next_page_token = '' } }
            [pscustomobject]@{ experiments = @(@{ experiment_id = '1' }); next_page_token = 'second' }
        }
        $config = [pscustomobject]@{ capabilities = @{ assets = @('experiments') }; databricks = @{ workspaces = @(@{ include = $true; workspaceId = '42'; workspaceUrl = 'fake' }) } }
        $result = Invoke-DatabricksAssetsCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        $result.status | Should -Be passed
        @(Get-Content -LiteralPath $result.outputs[0] | ConvertFrom-Json).Count | Should -Be 2
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 2 -Exactly -ParameterFilter { $Method -eq 'POST' -and $Path -eq '/api/2.0/mlflow/experiments/search' }
    }
    It 'bounds notebook recursion and never requests notebook source' {
        Mock Invoke-DatabricksCollectorRequest { [pscustomobject]@{ objects = @(@{ object_type = 'DIRECTORY'; path = '/nested' }, @{ object_type = 'NOTEBOOK'; path = '/sample' }) } }
        $config = [pscustomobject]@{ analysis = @{ maxPages = 1 }; capabilities = @{ assets = @('notebooks') };
            redaction = @{ hashNotebookPaths = $true }; databricks = @{ workspaces = @(@{ include = $true; workspaceId = '42'; workspaceUrl = 'fake' }) } }
        $result = Invoke-DatabricksAssetsCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        $result.status | Should -Be partial
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 1 -Exactly -ParameterFilter { $Method -eq 'GET' -and $Path -like '/api/2.0/workspace/list*' }
    }
}
