Describe 'Databricks assessment collector contracts' {
    BeforeAll {
        $assessmentRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
        $collectorRoot = Join-Path $assessmentRoot 'collectors'
        . (Join-Path $assessmentRoot 'scripts\Assessment.Common.ps1')
        Get-ChildItem -LiteralPath $collectorRoot -Filter 'Databricks*.ps1' |
            Sort-Object Name |
            ForEach-Object { . $_.FullName }
    }

    It 'supports legacy deep-dive lists only for one included workspace' -ForEach @(
        @{ Name = 'deepDiveJobRunIds'; Value = '101' },
        @{ Name = 'deepDiveTableNames'; Value = 'catalog.schema.table' }
    ) {
        $workspace = [pscustomobject]@{ include = $true; workspaceId = 'one' }
        $config = [pscustomobject]@{ databricks = @{ workspaces = @($workspace); $Name = @($Value) } }
        @(Get-DatabricksDeepDiveTargets -Config $config -Workspace $workspace -Name $Name) | Should -Be @($Value)
        $config.databricks.workspaces += [pscustomobject]@{ include = $false; workspaceId = 'two' }
        @(Get-DatabricksDeepDiveTargets -Config $config -Workspace $workspace -Name $Name) | Should -Be @($Value)
        $config.databricks.workspaces[1].include = $true
        { Get-DatabricksDeepDiveTargets -Config $config -Workspace $workspace -Name $Name } | Should -Throw '*ambiguous*'
    }

    It 'honors explicit empty workspace targets instead of inheriting global lists' -ForEach @(
        @{ Name = 'deepDiveJobRunIds' }, @{ Name = 'deepDiveTableNames' }
    ) {
        foreach ($workspace in @(@{ include = $true; $Name = @() }, [pscustomobject]@{ include = $true; $Name = @() })) {
            $config = [pscustomobject]@{ databricks = @{ workspaces = @($workspace); $Name = @('legacy-target') } }
            @(Get-DatabricksDeepDiveTargets -Config $config -Workspace $workspace -Name $Name).Count | Should -Be 0
        }
    }

    It 'queries Spark run IDs only in their assigned workspace and preserves the real metrics gap' {
        Mock Invoke-DatabricksCollectorRequest { [pscustomobject]@{ run_id = 101 } }
        $config = [pscustomobject]@{
            analysis = @{ startUtc = '2026-01-01T00:00:00Z'; endUtc = '2026-02-01T00:00:00Z' }
            databricks = @{
                deepDiveJobRunIds = @()
                workspaces = @(
                    @{ include = $true; workspaceId = 'one'; workspaceUrl = 'one.azuredatabricks.net'; deepDiveJobRunIds = @('101') },
                    @{ include = $true; workspaceId = 'two'; workspaceUrl = 'two.azuredatabricks.net' }
                )
            }
        }
        $results = @(Invoke-DatabricksSparkDeepDiveCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive }))
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 1 -Exactly -ParameterFilter {
            $HostName -eq 'one.azuredatabricks.net' -and $Path -eq '/api/2.1/jobs/runs/get?run_id=101&include_history=true'
        }
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 0 -Exactly -ParameterFilter { $HostName -eq 'two.azuredatabricks.net' }
        $results[0].status | Should -Be 'partial'
        $results[0].limitations -join ' ' | Should -Match 'do not expose full Spark UI metrics'
        $results[1].status | Should -Be 'skipped'
    }

    It 'does not issue Spark requests for ambiguous global multi-workspace targets' {
        Mock Invoke-DatabricksCollectorRequest { throw 'No request should be made.' }
        $config = [pscustomobject]@{ databricks = @{
            deepDiveJobRunIds = @('101')
            workspaces = @(@{ include = $true; workspaceId = 'one' }, @{ include = $true; workspaceId = 'two' })
        } }
        { Invoke-DatabricksSparkDeepDiveCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive }) } | Should -Throw '*ambiguous*'
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 0 -Exactly
    }

    It 'queries selected table detail and history only in the workspace that owns the targets' {
        Mock Invoke-DatabricksPagedGet { [pscustomobject]@{ items = @(); truncated = $false } }
        Mock Invoke-DatabricksSqlDatasetCollection { New-DatabricksSourceStatus -Source $Source -Status passed }
        $config = [pscustomobject]@{
            customerId = 'fixture-customer'; assessmentId = 'fixture-assessment'
            redaction = @{ saltEnvironmentVariable = 'ADB_TEST_UNUSED_SALT' }
            databricks = @{
                deepDiveTableNames = @()
                workspaces = @(
                    @{ include = $true; workspaceId = 'one'; workspaceUrl = 'one.azuredatabricks.net'; deepDiveTableNames = @('catalog.schema.table') },
                    @{ include = $true; workspaceId = 'two'; workspaceUrl = 'two.azuredatabricks.net' }
                )
            }
        }
        $null = Invoke-DatabricksUnityCatalogCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        Assert-MockCalled Invoke-DatabricksSqlDatasetCollection -Times 2 -Exactly -ParameterFilter {
            $Workspace.workspaceId -eq 'one' -and $FileName -in @('DatabricksTableDetail.sql', 'DatabricksTableHistory.sql')
        }
        Assert-MockCalled Invoke-DatabricksSqlDatasetCollection -Times 0 -Exactly -ParameterFilter {
            $Workspace.workspaceId -eq 'two' -and $FileName -in @('DatabricksTableDetail.sql', 'DatabricksTableHistory.sql')
        }
    }

    It 'exposes the orchestrator and domain entry points' {
        @(
            'Invoke-DatabricksAssessmentCollectors',
            'Invoke-DatabricksWorkspaceCollector',
            'Invoke-DatabricksBillingCollector',
            'Invoke-DatabricksComputeCollector',
            'Invoke-DatabricksWorkloadsCollector',
            'Invoke-DatabricksSqlCollector',
            'Invoke-DatabricksUnityCatalogCollector',
            'Invoke-DatabricksGovernanceCollector',
            'Invoke-DatabricksSparkDeepDiveCollector'
        ) | ForEach-Object {
            Get-Command $_ -CommandType Function -ErrorAction Stop | Should -Not -BeNullOrEmpty
        }
    }

    It 'uses the orchestrator integration signature and result contract' {
        $command = Get-Command Invoke-DatabricksAssessmentCollectors -CommandType Function
        $command.Parameters.Keys | Should -Contain 'Config'
        $command.Parameters.Keys | Should -Contain 'RunContext'

        $script = Get-Content -Raw -LiteralPath (Join-Path $collectorRoot 'Databricks.ps1')
        $script | Should -Match '\[Parameter\(Mandatory\)\]\[object\]\$Config'
        $script | Should -Match '\[Parameter\(Mandatory\)\]\[object\]\$RunContext'
        $script | Should -Match 'New-CollectorResult'
        $script | Should -Match 'return \$results\.ToArray\(\)'
    }

    It 'reads SQL request fields from hashtable bodies' {
        $body = @{
            warehouse_id = 'warehouse-1'
            statement = 'SELECT 1'
        }

        Get-DatabricksProperty -InputObject $body -Name 'statement' | Should -Be 'SELECT 1'
        Get-DatabricksProperty -InputObject $body -Name 'warehouse_id' | Should -Be 'warehouse-1'
    }

    It 'accepts a read-only SQL hashtable body before HTTP submission' {
        Mock Get-DatabricksAssessmentToken { 'token' }
        Mock Invoke-WebRequest {
            [pscustomobject]@{
                StatusCode = 200
                Content = '{"statement_id":"statement-1","status":{"state":"SUCCEEDED"}}'
            }
        }

        $result = Invoke-DatabricksCollectorApi `
            -HostName 'adb.example.azuredatabricks.net' `
            -Method POST `
            -Path '/api/2.0/sql/statements' `
            -Body @{
                warehouse_id = 'warehouse-1'
                statement = 'SELECT 1'
            }

        $result.statement_id | Should -Be 'statement-1'
        Should -Invoke Invoke-WebRequest -Times 1
    }

    It 'formats SQL timestamp parameters as culture-independent ISO-8601 UTC' {
        $config = '{"analysis":{"startUtc":"2026-08-26T00:00:00Z","endUtc":"2026-09-26T00:00:00Z"}}' |
            ConvertFrom-Json

        $parameters = New-DatabricksTimeParameters -Config $config

        $parameters[0].value | Should -Be '2026-08-26T00:00:00.000Z'
        $parameters[1].value | Should -Be '2026-09-26T00:00:00.000Z'
        $parameters[0].value | Should -Not -Match '/'
    }

    It 'reports SQL execution errors as failed rather than pending telemetry' {
        Mock Get-DatabricksSqlWarehouseId { 'warehouse-1' }
        Mock Invoke-DatabricksSqlFile { throw 'invalid parameter mapping' }

        $result = Invoke-DatabricksSqlDatasetCollection `
            -Config ([pscustomobject]@{}) `
            -RunContext ([pscustomobject]@{ Root = $TestDrive }) `
            -Workspace ([pscustomobject]@{ workspaceId = 'workspace-1' }) `
            -Source 'system.billing.usage' `
            -FileName 'DatabricksBillingUsage.sql' `
            -OutputName 'billing-usage'

        $result.status | Should -Be 'failed'
        $result.message | Should -Match 'invalid parameter mapping'
    }

    It 'quotes SQL table identifier components without treating SQL as an identifier' -ForEach @(
        @{ Name = 'catalog.schema.table'; Expected = '`catalog`.`schema`.`table`' },
        @{ Name = '`catalog-name`.`schema.name`.`a``b`'; Expected = '`catalog-name`.`schema.name`.`a``b`' },
        @{ Name = 'table'; Expected = '`table`' },
        @{ Name = ' schema . table '; Expected = '`schema`.`table`' }
    ) {
        ConvertTo-DatabricksTableIdentifier -Name $Name | Should -Be $Expected
    }

    It 'rejects SQL expressions, paths, comments and statement separators as table names' -ForEach @(
        "catalog.schema.table; SELECT 1",
        "IDENTIFIER('catalog.schema.table')",
        'catalog.schema.table -- comment',
        '/some/path',
        'a..b',
        'a.b.c.d',
        "a`nb",
        'a.`unclosed'
    ) {
        { ConvertTo-DatabricksTableIdentifier -Name $_ } | Should -Throw '*SQL identifier*'
    }

    It 'submits DESCRIBE DETAIL with an escaped identifier and no unused table parameter' {
        Mock Invoke-DatabricksSqlQuery { [pscustomobject]@{ rows = @(); truncated = $false } }
        Invoke-DatabricksSqlFile -Config ([pscustomobject]@{}) -Workspace ([pscustomobject]@{}) `
            -FileName 'DatabricksTableDetail.sql' -Parameters @(@{ name = 'table_name'; value = 'catalog.schema.table'; type = 'STRING' })
        Assert-MockCalled Invoke-DatabricksSqlQuery -Times 1 -Exactly -ParameterFilter {
            $Statement.Trim() -eq 'DESCRIBE DETAIL `catalog`.`schema`.`table`' -and $Parameters.Count -eq 0
        }
    }

    It 'does not request bindings for OPEN catalogs and never skips isolated or unknown modes' -ForEach @(
        @{ Mode = 'OPEN'; Expected = 'passed'; Calls = 0 },
        @{ Mode = 'ISOLATED'; Expected = 'partial'; Calls = 1 },
        @{ Mode = ''; Expected = 'partial'; Calls = 1 }
    ) {
        $script:mode = $Mode
        Mock Invoke-DatabricksPagedGet {
            if ($Path -like '*/catalogs?*') {
                return [pscustomobject]@{ items = @(@{ name = 'catalog'; isolation_mode = $script:mode }); truncated = $false }
            }
            [pscustomobject]@{ items = @(); truncated = $false }
        }
        Mock Invoke-DatabricksCollectorRequest { throw 'HTTP 403: binding permission denied' }
        Mock Invoke-DatabricksSqlDatasetCollection { New-DatabricksSourceStatus -Source 'table metadata' -Status passed }
        $config = [pscustomobject]@{ databricks = @{ workspaces = @(@{ include = $true; workspaceId = '42'; workspaceUrl = 'workspace.azuredatabricks.net' }) } }
        $result = Invoke-DatabricksUnityCatalogCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        $result.status | Should -Be $Expected
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times $Calls -Exactly
    }

    It 'uses the supported v2.1 account budgets endpoint with pagination' {
        Mock Invoke-DatabricksPagedGet { [pscustomobject]@{ items = @(); truncated = $false } }
        Mock Invoke-DatabricksSqlDatasetCollection { New-DatabricksSourceStatus -Source 'sql' -Status passed }
        $config = [pscustomobject]@{
            analysis = @{ startUtc = '2026-01-01T00:00:00Z'; endUtc = '2026-02-01T00:00:00Z' }
            databricks = @{
                accountId = 'account'; accountHost = 'accounts.azuredatabricks.net'
                workspaces = @(@{ include = $true; workspaceId = '42'; workspaceUrl = 'workspace.azuredatabricks.net' })
            }
        }
        $result = Invoke-DatabricksGovernanceCollector -Config $config -RunContext ([pscustomobject]@{ Root = $TestDrive })
        $result.status | Should -Be 'passed'
        Assert-MockCalled Invoke-DatabricksPagedGet -Times 1 -Exactly -ParameterFilter {
            $Path -eq '/api/2.1/accounts/account/budgets?page_size=100' -and $TokenParameter -eq 'page_token'
        }
    }

    It 'contains only approved Databricks HTTP methods and SQL POST path' {
        $content = (Get-ChildItem -LiteralPath $collectorRoot -Filter 'Databricks*.ps1' |
            ForEach-Object { Get-Content -Raw -LiteralPath $_.FullName }) -join "`n"
        $content | Should -Not -Match '(?i)-Method\s+(PUT|PATCH|DELETE)'
        $content | Should -Match "ValidateSet\('GET', 'POST'\)"
        $content | Should -Match '\$Path -notin \$script:AllowedDatabricksPostPaths'
        $content | Should -Not -Match '/(create|edit|delete|run-now|cancel|start|stop|restart)(\?|[''"])'
    }

    It 'implements bounded API and SQL chunk pagination' {
        $common = Get-Content -Raw -LiteralPath (Join-Path $collectorRoot 'Databricks.Common.ps1')
        $common | Should -Match 'function Invoke-DatabricksPagedGet'
        $common | Should -Match 'maxPages'
        $common | Should -Match 'next_page_token'
        $common | Should -Match 'next_chunk_internal_link'
        $common | Should -Match 'truncated'
    }

    It 'redacts restricted values without erasing approved metadata' {
        $config = [pscustomobject]@{
            customerId = 'customer'
            assessmentId = 'assessment'
            redaction = [pscustomobject]@{
                saltEnvironmentVariable = 'DATABRICKS_TEST_SALT'
                hashIdentities = $true
                hashNotebookPaths = $true
                hashTableNames = $false
                omitQueryText = $true
            }
        }
        $value = [pscustomobject]@{
            owner = 'owner@example.com'
            query_text = 'select sensitive_value'
            notebook_path = '/Users/owner/notebook'
            table_name = 'approved_table'
            access_token = 'secret-value'
            job_parameters = @{ apiKey = 'restricted-value' }
        }
        $protected = Protect-DatabricksAssessmentValue -Value $value -Config $config
        $protected.owner | Should -Match '^[a-f0-9]{64}$'
        $protected.query_text | Should -Be '[omitted]'
        $protected.notebook_path | Should -Match '^[a-f0-9]{64}$'
        $protected.table_name | Should -Be 'approved_table'
        $protected.access_token | Should -Be '[redacted]'
        $protected.job_parameters | Should -Be '[redacted]'
    }

    It 'represents pending telemetry and partial source combinations explicitly' {
        $pending = New-DatabricksSourceStatus -Source 'system table' -Status 'pending telemetry' -Message 'not enabled'
        (Get-DatabricksCollectorStatus -Sources @($pending)) | Should -Be 'pending telemetry'
        $passed = New-DatabricksSourceStatus -Source 'inventory' -Status passed -ItemCount 1
        (Get-DatabricksCollectorStatus -Sources @($passed, $pending)) | Should -Be 'partial'
    }

    It 'follows encoded page tokens and reports configured truncation' {
        $script:page = 0
        Mock Invoke-DatabricksCollectorRequest {
            $script:page++
            if ($script:page -eq 1) {
                return [pscustomobject]@{ jobs = @([pscustomobject]@{ job_id = 1 }); next_page_token = 'a+b/c' }
            }
            return [pscustomobject]@{ jobs = @([pscustomobject]@{ job_id = 2 }); next_page_token = 'still-more' }
        }
        $config = [pscustomobject]@{ analysis = [pscustomobject]@{ maxPages = 2 } }

        $result = Invoke-DatabricksPagedGet -Config $config -HostName host -Path '/api/2.1/jobs/list?limit=1' -ItemsProperty jobs

        @($result.items).Count | Should -Be 2
        $result.pages | Should -Be 2
        $result.truncated | Should -BeTrue
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 1 -ParameterFilter { $Path -match 'page_token=a%2Bb%2Fc' }
    }

    It 'paginates the read-only cluster-events POST contract' {
        $script:page = 0
        Mock Invoke-DatabricksCollectorRequest {
            $script:page++
            if ($script:page -eq 1) {
                return [pscustomobject]@{
                    events = @([pscustomobject]@{ type = 'TERMINATING' })
                    next_page = [pscustomobject]@{ offset = 1; start_time = 10; end_time = 20 }
                }
            }
            return [pscustomobject]@{ events = @([pscustomobject]@{ type = 'TERMINATED' }) }
        }
        $config = [pscustomobject]@{ analysis = [pscustomobject]@{ maxPages = 3 } }

        $result = Invoke-DatabricksPagedPost -Config $config -HostName host -Path '/api/2.0/clusters/events' `
            -Body @{ cluster_id = 'cluster'; start_time = 1; end_time = 2; limit = 1 } -ItemsProperty events

        @($result.items).type | Should -Be @('TERMINATING', 'TERMINATED')
        $result.pages | Should -Be 2
        $result.truncated | Should -BeFalse
        Assert-MockCalled Invoke-DatabricksCollectorRequest -Times 1 -ParameterFilter {
            $Method -eq 'POST' -and $Body.offset -eq 1 -and $Body.start_time -eq 10
        }
    }

    It 'writes a valid empty dataset for a missing optional list property' {
        $root = Join-Path $TestDrive 'empty'
        $config = [pscustomobject]@{ redaction = [pscustomobject]@{} }
        $context = [pscustomobject]@{ Root = $root }
        $workspace = [pscustomobject]@{ workspaceId = '1' }

        $path = Write-DatabricksDataset -Config $config -RunContext $context -Workspace $workspace -Name empty -Items $null

        Test-Path -LiteralPath $path | Should -BeTrue
        (Get-Content -Raw -LiteralPath $path) | Should -BeNullOrEmpty
    }

    It 'uses only supported workspace-conf keys and counts scalar API responses' {
        $content = Get-Content -Raw -LiteralPath (Join-Path $collectorRoot 'DatabricksWorkspace.ps1')
        $content | Should -Match 'enableIpAccessLists,enableTokensConfig'
        $content | Should -Not -Match 'enableServerlessCompute'
        $content | Should -Match 'ItemCount @\(\$items\)\.Count'
    }

    It 'maps SQL rows across delayed completion and result chunks' {
        $script:request = 0
        Mock Start-Sleep {}
        Mock Invoke-DatabricksCollectorRequest {
            $script:request++
            switch ($script:request) {
                1 {
                    return [pscustomobject]@{
                        statement_id = 's1'
                        status = [pscustomobject]@{ state = 'PENDING' }
                        manifest = [pscustomobject]@{ schema = [pscustomobject]@{ columns = @([pscustomobject]@{ name = 'id' }) } }
                        result = [pscustomobject]@{ data_array = @() }
                    }
                }
                2 {
                    return [pscustomobject]@{
                        statement_id = 's1'
                        status = [pscustomobject]@{ state = 'SUCCEEDED' }
                        manifest = [pscustomobject]@{ schema = [pscustomobject]@{ columns = @([pscustomobject]@{ name = 'id' }, [pscustomobject]@{ name = 'value' }) } }
                        result = [pscustomobject]@{ data_array = @(,@('one', '10')); next_chunk_internal_link = '/api/2.0/sql/statements/s1/result/chunks/1' }
                    }
                }
                default {
                    return [pscustomobject]@{ result = [pscustomobject]@{ data_array = @(,@('two', '20')) } }
                }
            }
        }
        $config = [pscustomobject]@{
            analysis = [pscustomobject]@{ collectorTimeoutSeconds = 30; maxPages = 3 }
            databricks = [pscustomobject]@{ sqlWarehouseId = 'wh' }
        }
        $workspace = [pscustomobject]@{ workspaceUrl = 'host' }

        $result = Invoke-DatabricksSqlQuery -Config $config -Workspace $workspace -Statement 'SELECT 1'

        @($result.rows).id | Should -Be @('one', 'two')
        @($result.rows).value | Should -Be @('10', '20')
        $result.pages | Should -Be 2
        $result.truncated | Should -BeFalse
        Assert-MockCalled Start-Sleep -Times 1
    }

    It 'preserves a single SQL row with multiple columns and a null cell' {
        $response = '{"manifest":{"schema":{"columns":[{"name":"format"},{"name":"description"},{"name":"numFiles"}]}},"result":{"data_array":[["delta",null,"12"]]}}' | ConvertFrom-Json
        $rows = @(ConvertFrom-DatabricksSqlRows -Response $response)
        $rows.Count | Should -Be 1
        $rows[0].format | Should -Be 'delta'
        $rows[0].description | Should -BeNullOrEmpty
        $rows[0].numFiles | Should -Be '12'
    }

    It 'preserves multiple SQL rows without flattening or shifting values' {
        $response = '{"result":{"data_array":[["first","12"],["second","34"]]}}' | ConvertFrom-Json
        $rows = @(ConvertFrom-DatabricksSqlRows -Response $response -Columns @('name', 'numFiles'))
        $rows.Count | Should -Be 2
        $rows.name | Should -Be @('first', 'second')
        $rows.numFiles | Should -Be @('12', '34')
    }

    It 'rejects malformed SQL row widths instead of manufacturing null fields' {
        $response = '{"result":{"data_array":[["one"]]}}' | ConvertFrom-Json
        { ConvertFrom-DatabricksSqlRows -Response $response -Columns @('name', 'numFiles') } |
            Should -Throw '*1 cells for 2 columns*'
    }

    It 'surfaces a SQL collector timeout instead of returning empty success' {
        Mock Invoke-DatabricksCollectorRequest {
            [pscustomobject]@{
                statement_id = 'slow'
                status = [pscustomobject]@{ state = 'PENDING' }
                manifest = [pscustomobject]@{ schema = [pscustomobject]@{ columns = @() } }
                result = [pscustomobject]@{ data_array = @() }
            }
        }
        $config = [pscustomobject]@{
            analysis = [pscustomobject]@{ collectorTimeoutSeconds = 0; maxPages = 1 }
            databricks = [pscustomobject]@{ sqlWarehouseId = 'wh' }
        }
        $workspace = [pscustomobject]@{ workspaceUrl = 'host' }

        { Invoke-DatabricksSqlQuery -Config $config -Workspace $workspace -Statement 'SELECT 1' } |
            Should -Throw '*exceeded the collector timeout*'
    }

    It 'preserves successes when another domain collector fails' {
        Mock Invoke-DatabricksWorkspaceCollector { New-CollectorResult -Name workspace -Status passed -StartedAt (Get-Date) }
        Mock Invoke-DatabricksBillingCollector { throw 'permission denied' }
        Mock Invoke-DatabricksComputeCollector { New-CollectorResult -Name compute -Status passed -StartedAt (Get-Date) }
        Mock Invoke-DatabricksWorkloadsCollector { @() }
        Mock Invoke-DatabricksSqlCollector { @() }
        Mock Invoke-DatabricksUnityCatalogCollector { @() }
        Mock Invoke-DatabricksGovernanceCollector { @() }
        Mock Invoke-DatabricksSparkDeepDiveCollector { @() }

        $results = @(Invoke-DatabricksAssessmentCollectors -Config ([pscustomobject]@{}) -RunContext ([pscustomobject]@{}))

        @($results | Where-Object status -eq passed).Count | Should -Be 2
        $failed = @($results | Where-Object status -eq failed)
        $failed.Count | Should -Be 1
        $failed[0].error | Should -Match 'permission denied'
    }
}

Describe 'Databricks SQL assets' {
    BeforeAll {
        $sqlRoot = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'collectors\sql'
        $sqlFiles = @(Get-ChildItem -LiteralPath $sqlRoot -Filter 'Databricks*.sql')
    }

    It 'provides the required system and metadata query assets' {
        $sqlFiles.Count | Should -BeGreaterOrEqual 10
        ($sqlFiles.Name -join ',') | Should -Match 'DatabricksBillingUsage.sql'
        ($sqlFiles.Name -join ',') | Should -Match 'DatabricksNodeTimeline.sql'
        ($sqlFiles.Name -join ',') | Should -Match 'DatabricksQueryHistory.sql'
        ($sqlFiles.Name -join ',') | Should -Match 'DatabricksTableDetail.sql'
    }

    It 'contains only read-only statement forms' {
        foreach ($file in $sqlFiles) {
            $content = Get-Content -Raw -LiteralPath $file.FullName
            $content.TrimStart() | Should -Match '^(?i)(SELECT|WITH|SHOW|DESCRIBE)\b'
            $content | Should -Not -Match '(?im)\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|MERGE|OPTIMIZE|VACUUM|RESTORE|TRUNCATE|GRANT|REVOKE|COPY\s+INTO|CALL)\b'
        }
    }

    It 'parameterizes time windows and uses an escaped identifier placeholder for table detail' {
        (Get-Content -Raw -LiteralPath (Join-Path $sqlRoot 'DatabricksBillingUsage.sql')) | Should -Match ':start_utc'
        (Get-Content -Raw -LiteralPath (Join-Path $sqlRoot 'DatabricksBillingUsage.sql')) | Should -Match ':end_utc'
        (Get-Content -Raw -LiteralPath (Join-Path $sqlRoot 'DatabricksTableDetail.sql')) | Should -Match 'DESCRIBE DETAIL \{\{table_identifier\}\}'
        (Get-Content -Raw -LiteralPath (Join-Path $sqlRoot 'DatabricksTableHistory.sql')) | Should -Match 'IDENTIFIER\(:table_name\)'
    }
}
