Describe 'Partial collector recovery' {
    BeforeAll {
        $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
        . (Join-Path $root 'scripts\Assessment.Common.ps1')
        . (Join-Path $root 'collectors\Databricks.Common.ps1')
        . (Join-Path $root 'collectors\DatabricksWorkloads.ps1')
        $config = [pscustomobject]@{
            customerId = 'test'; assessmentId = 'recovery'
            analysis = @{ startUtc = '2026-09-01T00:00:00Z'; endUtc = '2026-09-01T02:00:00Z'; maxPages = 8 }
            redaction = @{ hashIdentities = $true; saltEnvironmentVariable = 'ADB_TEST_UNUSED_SALT' }
            databricks = @{ workspaces = @(@{ include = $true; workspaceId = '42'; workspaceUrl = 'fake'; sqlWarehouseId = 'warehouse' }) }
        }
        $workspace = $config.databricks.workspaces[0]
    }
    It 'preserves empty notification objects from actual JSON without a Name-property exception' {
        $job = '{"job_id":1,"settings":{"tasks":[{"task_key":"one","email_notifications":{}}],"email_notifications":{}}}' | ConvertFrom-Json
        $safe = Protect-DatabricksAssessmentValue -Value $job -Config $config
        @($safe.settings.email_notifications.PSObject.Properties).Count | Should -Be 0
        @($safe.settings.tasks[0].email_notifications.PSObject.Properties).Count | Should -Be 0
    }
    It 'completes the jobs collector when jobs contain empty notification objects' {
        Mock Invoke-DatabricksPagedGet {
            $items = if ($Path -like '/api/2.1/jobs/list*') { @('{"job_id":1,"settings":{"email_notifications":{}}}' | ConvertFrom-Json) } else { @() }
            [pscustomobject]@{ items = $items; truncated = $false }
        }
        Mock Invoke-DatabricksSqlDatasetCollection { New-DatabricksSourceStatus -Source $Source -Status passed }
        $result = Invoke-DatabricksWorkloadsCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        $result.status | Should -Be passed
        $result.limitations | Should -HaveCount 0
    }
    It 'preserves empty recipient arrays and hashes recipients in JSON-derived notifications' {
        $job = '{"settings":{"tasks":[{"email_notifications":{"on_failure":[],"on_success":["person@example.test"],"no_alert_for_skipped_runs":true}}]}}' | ConvertFrom-Json
        $safe = Protect-DatabricksAssessmentValue -Value $job -Config $config
        $roundTrip = $safe | ConvertTo-Json -Depth 20 | ConvertFrom-Json
        $roundTrip.settings.tasks | Should -HaveCount 1
        $roundTrip.settings.tasks[0].email_notifications.on_failure | Should -HaveCount 0
        $roundTrip.settings.tasks[0].email_notifications.on_success | Should -HaveCount 1
        $roundTrip.settings.tasks[0].email_notifications.on_success[0] | Should -Not -Be 'person@example.test'
        $roundTrip.settings.tasks[0].email_notifications.no_alert_for_skipped_runs | Should -BeTrue
    }
    It 'does not mark a server-truncated SQL manifest complete when there is no next chunk' {
        Mock Invoke-DatabricksCollectorRequest {
            [pscustomobject]@{
                statement_id = 's1'; status = @{ state = 'SUCCEEDED' }
                manifest = @{ truncated = $true; schema = @{ columns = @(@{ name = 'id' }) } }
                result = @{ data_array = @(,@('one')) }
            }
        }
        $result = Invoke-DatabricksSqlQuery -Config $config -Workspace $workspace -Statement 'SELECT 1'
        $result.truncated | Should -BeTrue
        $result.rows | Should -HaveCount 1
    }
    It 'splits oversized audit results without losing or duplicating boundary events' {
        Mock Invoke-DatabricksSqlFile {
            $start = [DateTimeOffset]::Parse(($Parameters | Where-Object name -eq 'start_utc').value)
            $end = [DateTimeOffset]::Parse(($Parameters | Where-Object name -eq 'end_utc').value)
            if (($end - $start).TotalHours -gt 1) { throw 'Inline byte limit exceeded.' }
            $events = @('2026-09-01T00:30:00Z', '2026-09-01T01:00:00Z', '2026-09-01T01:30:00Z')
            [pscustomobject]@{ rows = @($events | Where-Object { [DateTimeOffset]::Parse($_) -ge $start -and [DateTimeOffset]::Parse($_) -lt $end } | ForEach-Object { @{ event_time = $_ } }); truncated = $false }
        }
        $result = Invoke-DatabricksWindowedSqlFile -Config $config -Workspace $workspace -FileName 'DatabricksGovernanceAudit.sql' -Parameters (New-DatabricksTimeParameters -Config $config)
        $result.truncated | Should -BeFalse
        $result.rows.event_time | Should -Be @('2026-09-01T00:30:00Z', '2026-09-01T01:00:00Z', '2026-09-01T01:30:00Z')
        Assert-MockCalled Invoke-DatabricksSqlFile -Times 3 -Exactly
    }
    It 'keeps audit coverage partial when its request budget is exhausted' {
        Mock Invoke-DatabricksSqlFile { throw 'Inline byte limit exceeded.' }
        $bounded = [pscustomobject]@{ analysis = @{ maxPages = 1 }; databricks = $config.databricks; redaction = $config.redaction }
        $result = Invoke-DatabricksSqlDatasetCollection -Config $bounded -RunContext ([pscustomobject]@{ Root = $TestDrive }) -Workspace $workspace -Source 'audit' -FileName 'DatabricksGovernanceAudit.sql' -OutputName 'audit' -Parameters (New-DatabricksTimeParameters -Config $config) -SplitOversizedWindow
        $result.status | Should -Be partial
        $result.message | Should -Match 'time ranges remain uncollected'
        Assert-MockCalled Invoke-DatabricksSqlFile -Times 1 -Exactly
    }
    It 'does not split or retry a permission error' {
        Mock Invoke-DatabricksSqlFile { throw 'PERMISSION_DENIED' }
        { Invoke-DatabricksWindowedSqlFile -Config $config -Workspace $workspace -FileName 'DatabricksGovernanceAudit.sql' -Parameters (New-DatabricksTimeParameters -Config $config) } | Should -Throw '*PERMISSION_DENIED*'
        Assert-MockCalled Invoke-DatabricksSqlFile -Times 1 -Exactly
    }
    It 'recovers the real SQL FAILED response through dataset persistence' {
        Mock Invoke-DatabricksCollectorRequest {
            $start = [DateTimeOffset]::Parse(($Body.parameters | Where-Object name -eq 'start_utc').value)
            $end = [DateTimeOffset]::Parse(($Body.parameters | Where-Object name -eq 'end_utc').value)
            if (($end - $start).TotalHours -gt 1) {
                return [pscustomobject]@{ statement_id = 'oversized'; status = @{ state = 'FAILED'; error = @{ error_code = 'BAD_REQUEST'; message = 'Inline byte limit exceeded.' } } }
            }
            [pscustomobject]@{
                statement_id = 'bounded'; status = @{ state = 'SUCCEEDED' }
                manifest = @{ schema = @{ columns = @(@{ name = 'event_time' }) } }
                result = @{ data_array = @(,@($start.ToString('o'))) }
            }
        }
        $result = Invoke-DatabricksSqlDatasetCollection -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive }) -Workspace $workspace -Source 'audit' -FileName 'DatabricksGovernanceAudit.sql' -OutputName 'recovered-audit' -Parameters (New-DatabricksTimeParameters -Config $config) -SplitOversizedWindow
        $result.status | Should -Be passed
        $result.itemCount | Should -Be 2
        @(Get-Content -LiteralPath $result.output | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json }) | Should -HaveCount 2
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 3 -Exactly
    }
    It 'allows intentional skips without degrading a completed run but retains actual partials' {
        Get-AssessmentRunStatus -CollectorResults @(@{ status = 'passed' }, @{ status = 'skipped' }) | Should -Be completed
        Get-AssessmentRunStatus -CollectorResults @(@{ status = 'passed' }, @{ status = 'partial' }, @{ status = 'skipped' }) | Should -Be partial
    }
    It 'refuses to split a saturated one-millisecond interval' {
        Mock Invoke-DatabricksSqlFile { throw 'Inline byte limit exceeded.' }
        $parameters = @(@{ name = 'start_utc'; value = '2026-09-01T00:00:00.000Z' }, @{ name = 'end_utc'; value = '2026-09-01T00:00:00.001Z' })
        { Invoke-DatabricksWindowedSqlFile -Config $config -Workspace $workspace -FileName 'DatabricksGovernanceAudit.sql' -Parameters $parameters } | Should -Throw '*one-millisecond*'
    }
    It 'retains truncation reported by a successful partition' {
        Mock Invoke-DatabricksSqlFile { [pscustomobject]@{ rows = @(@{ event_time = 'sample' }); truncated = $true } }
        $result = Invoke-DatabricksWindowedSqlFile -Config $config -Workspace $workspace -FileName 'DatabricksGovernanceAudit.sql' -Parameters (New-DatabricksTimeParameters -Config $config)
        $result.truncated | Should -BeTrue
        $result.rows | Should -HaveCount 1
    }
}
