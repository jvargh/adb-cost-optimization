BeforeAll {
    $assessmentRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    . (Join-Path $assessmentRoot 'scripts\Assessment.Common.ps1')
    . (Join-Path $assessmentRoot 'collectors\Azure.AssessmentCollectors.ps1')
    . (Join-Path $assessmentRoot 'scripts\Assessment.Scope.ps1')

    function New-ScopeTestWorkspace {
        param([string]$Subscription, [string]$Group, [string]$Name, [string]$WorkspaceId)

        [pscustomobject]@{
            id = "/subscriptions/$Subscription/resourceGroups/$Group/providers/Microsoft.Databricks/workspaces/$Name"
            name = $Name
            properties = [pscustomobject]@{
                workspaceId = $WorkspaceId
                workspaceUrl = "adb-$WorkspaceId.1.azuredatabricks.net"
            }
        }
    }

    function Set-ScopeTestAnswers {
        param([string[]]$Answers)

        $script:scopeAnswers = [Collections.Generic.Queue[string]]::new()
        foreach ($answer in $Answers) {
            $script:scopeAnswers.Enqueue($answer)
        }
    }
}

Describe 'Resolved assessment scope behavior' {
    BeforeEach {
        $script:subA = '11111111-1111-1111-1111-111111111111'
        $script:subB = '22222222-2222-2222-2222-222222222222'
        $script:disabledSub = '33333333-3333-3333-3333-333333333333'
        $script:foreignSub = '44444444-4444-4444-4444-444444444444'
        $script:tenant = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        $script:account = [pscustomobject]@{ id = $subA; tenantId = $tenant }
        $script:accounts = @(
            [pscustomobject]@{ id = $subB; name = 'Beta'; state = 'Enabled'; tenantId = $tenant },
            [pscustomobject]@{ id = $disabledSub; name = 'Disabled'; state = 'Disabled'; tenantId = $tenant },
            [pscustomobject]@{ id = $subA; name = 'Alpha'; state = 'Enabled'; tenantId = $tenant },
            [pscustomobject]@{ id = $foreignSub; name = 'Other tenant'; state = 'Enabled'; tenantId = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb' }
        )
        $script:groupsBySubscription = @{
            $subA = @(
                [pscustomobject]@{ id = "/subscriptions/$subA/resourceGroups/shared"; name = 'shared' },
                [pscustomobject]@{ id = "/subscriptions/$subA/resourceGroups/a-only"; name = 'a-only' },
                [pscustomobject]@{ id = "/subscriptions/$subA/resourceGroups/empty"; name = 'empty' }
            )
            $subB = @(
                [pscustomobject]@{ id = "/subscriptions/$subB/resourceGroups/shared"; name = 'shared' },
                [pscustomobject]@{ id = "/subscriptions/$subB/resourceGroups/b-only"; name = 'b-only' }
            )
        }
        $script:workspacesBySubscription = @{
            $subA = @(
                (New-ScopeTestWorkspace -Subscription $subA -Group shared -Name a-shared -WorkspaceId 101),
                (New-ScopeTestWorkspace -Subscription $subA -Group a-only -Name a-extra -WorkspaceId 102)
            )
            $subB = @(
                (New-ScopeTestWorkspace -Subscription $subB -Group shared -Name b-shared -WorkspaceId 201),
                (New-ScopeTestWorkspace -Subscription $subB -Group b-only -Name b-extra -WorkspaceId 202)
            )
        }
        $script:config = [pscustomobject]@{
            customerId = 'test-customer'
            assessmentId = 'scope-test'
            azure = [pscustomobject]@{
                tenantId = 'old-tenant'
                subscriptions = @($subA)
                resourceGroups = @('old-group')
                resourceGroupIds = @("/subscriptions/$subA/resourceGroups/old-group")
                costScope = "/subscriptions/$subA/resourceGroups/old-group"
                costBasis = @('ActualCost', 'AmortizedCost')
                currency = 'USD'
            }
            databricks = [pscustomobject]@{
                workspaces = @(
                    [pscustomobject]@{
                        name = 'old-workspace'
                        include = $true
                        resourceId = "/subscriptions/$subA/resourceGroups/old-group/providers/Microsoft.Databricks/workspaces/old-workspace"
                        workspaceUrl = 'old.azuredatabricks.net'
                        sqlWarehouseId = 'old-per-workspace-warehouse'
                    }
                )
                sqlWarehouseId = 'global-must-not-bleed'
                deepDiveJobRunIds = @('old-job-run')
                deepDiveTableNames = @('old.catalog.table')
                includeQueryText = $false
            }
            analysis = [pscustomobject]@{
                startUtc = '2026-08-01T00:00:00Z'
                endUtc = '2026-09-01T00:00:00Z'
                timeZone = 'UTC'
                maxPages = 7
                pageSize = 23
                retryCount = 0
                retryBaseSeconds = 1
            }
            outputs = [pscustomobject]@{ root = (Join-Path $TestDrive 'runs'); writeJson = $true }
            thresholds = [pscustomobject]@{ materialMonthlyCost = 123 }
        }
        Set-ScopeTestAnswers -Answers @()
        Mock Read-Host {
            if ($script:scopeAnswers.Count -eq 0) {
                throw 'Unexpected interactive prompt.'
            }
            $script:scopeAnswers.Dequeue()
        }
        Mock Write-Host {}
        Mock Write-Warning {}
        Mock Invoke-WebRequest { throw 'Network calls are forbidden in scope tests.' }
        Mock Invoke-RestMethod { throw 'Network calls are forbidden in scope tests.' }
        Mock Invoke-AzureAssessmentRest { throw 'Only mocked ARM pagination may be used in scope tests.' }
        Mock Write-JsonFile { throw 'Scope resolution must not persist configuration.' }
        Mock Set-Content { throw 'Scope resolution must not write files.' }
        Mock Invoke-AzureAssessmentCliJson {
            switch ($Arguments -join ' ') {
                'account show --output json --only-show-errors' { return $script:account }
                'account list --output json --only-show-errors' { return $script:accounts }
                default { throw "Unexpected Azure CLI command: $($Arguments -join ' ')" }
            }
        }
        Mock Get-AzureAssessmentPagedValues {
            if ($Settings.MaxPages -ne 7 -or $Settings.PageSize -ne 23 -or $Settings.RetryCount -ne 0) {
                throw 'Scope discovery did not use the configured Azure settings.'
            }
            foreach ($subscription in @($script:subA, $script:subB)) {
                if ($Uri -eq "https://management.azure.com/subscriptions/$subscription/resourcegroups?api-version=2021-04-01") {
                    return $script:groupsBySubscription[$subscription]
                }
                if ($Uri -eq "https://management.azure.com/subscriptions/$subscription/providers/Microsoft.Databricks/workspaces?api-version=2024-05-01") {
                    return $script:workspacesBySubscription[$subscription]
                }
            }
            throw "Unexpected ARM discovery URI: $Uri"
        }
    }

    It 'resolves one subscription and one uniquely named group to a complete workspace record' {
        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('a-only')

        @($result.azure.subscriptions).Count | Should -Be 1
        $result.azure.subscriptions | Should -Contain $subA
        $result.azure.tenantId | Should -Be $tenant
        @($result.azure.resourceGroupIds).Count | Should -Be 1
        $result.azure.resourceGroupIds | Should -Contain "/subscriptions/$subA/resourceGroups/a-only"
        $result.azure.resourceGroups | Should -Contain 'a-only'
        $result.azure.costScopes | Should -Contain "/subscriptions/$subA"
        $result.azure.PSObject.Properties.Name | Should -Not -Contain 'costScope'
        @($result.databricks.workspaces).Count | Should -Be 1
        $workspace = @($result.databricks.workspaces)[0]
        $expected = $workspacesBySubscription[$subA][1]
        $workspace.name | Should -Be 'a-extra'
        $workspace.resourceId | Should -Be $expected.id
        $workspace.workspaceResourceId | Should -Be $expected.id
        $workspace.subscriptionId | Should -Be $subA
        $workspace.resourceGroup | Should -Be 'a-only'
        $workspace.workspaceId | Should -Be '102'
        $workspace.workspaceUrl | Should -Be 'adb-102.1.azuredatabricks.net'
        $workspace.include | Should -BeTrue
        Assert-MockCalled Invoke-AzureAssessmentCliJson -Times 1 -Exactly -ParameterFilter {
            ($Arguments -join ' ') -eq 'account show --output json --only-show-errors'
        }
        Assert-MockCalled Invoke-AzureAssessmentCliJson -Times 1 -Exactly -ParameterFilter {
            ($Arguments -join ' ') -eq 'account list --output json --only-show-errors'
        }
        Assert-MockCalled Get-AzureAssessmentPagedValues -Times 2 -Exactly
        Assert-MockCalled Read-Host -Times 0
    }

    It 'selects multiple unique groups across subscriptions and scopes cost to both subscriptions' {
        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA, $subB) -ResourceGroups @('a-only', 'b-only')

        @($result.azure.subscriptions).Count | Should -Be 2
        @($result.azure.resourceGroupIds).Count | Should -Be 2
        @($result.azure.costScopes).Count | Should -Be 2
        $result.azure.costScopes | Should -Contain "/subscriptions/$subA"
        $result.azure.costScopes | Should -Contain "/subscriptions/$subB"
        @($result.databricks.workspaces).Count | Should -Be 2
        $result.databricks.workspaces.name | Should -Contain 'a-extra'
        $result.databricks.workspaces.name | Should -Contain 'b-extra'
        $result.databricks.workspaces.name | Should -Not -Contain 'a-shared'
        $result.databricks.workspaces.name | Should -Not -Contain 'b-shared'
    }

    It 'discovers all workspace groups when only subscriptions are supplied, ignoring stale base filters' {
        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA, $subB)

        @($result.databricks.workspaces).Count | Should -Be 4
        @($result.azure.resourceGroupIds).Count | Should -Be 4
        $result.azure.resourceGroupIds | Should -Contain "/subscriptions/$subA/resourceGroups/shared"
        $result.azure.resourceGroupIds | Should -Contain "/subscriptions/$subB/resourceGroups/shared"
        $result.azure.resourceGroupIds | Should -Not -Contain "/subscriptions/$subA/resourceGroups/empty"
        $result.azure.resourceGroups | Should -Not -Contain 'old-group'
        $result.databricks.workspaces.name | Should -Not -Contain 'old-workspace'
    }

    It 'uses base subscriptions, but not base group filters, when only ResourceGroups is supplied' {
        $result = New-AssessmentScopeConfig -Config $config -ResourceGroups @('shared')

        @($result.azure.subscriptions).Count | Should -Be 1
        $result.azure.subscriptions | Should -Contain $subA
        @($result.databricks.workspaces).Count | Should -Be 1
        $result.databricks.workspaces[0].name | Should -Be 'a-shared'
        Assert-MockCalled Get-AzureAssessmentPagedValues -Times 0 -ParameterFilter { $Uri.Contains($script:subB) }
    }

    It 'rejects ambiguous group names instead of including the same name in every subscription' {
        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA, $subB) -ResourceGroups @('shared') } |
            Should -Throw '*ambiguous*'
    }

    It 'uses qualified IDs to distinguish identically named groups in different subscriptions' {
        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA, $subB) `
            -ResourceGroups @("/subscriptions/$subB/resourceGroups/shared")

        @($result.azure.resourceGroupIds).Count | Should -Be 1
        $result.azure.resourceGroupIds | Should -Contain "/subscriptions/$subB/resourceGroups/shared"
        @($result.databricks.workspaces).Count | Should -Be 1
        $result.databricks.workspaces[0].subscriptionId | Should -Be $subB
        $result.databricks.workspaces[0].name | Should -Be 'b-shared'
        @($result.azure.costScopes).Count | Should -Be 2
    }

    It 'accepts both qualified IDs without collapsing different groups sharing one name' {
        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA, $subB) `
            -ResourceGroups @("/subscriptions/$subA/resourceGroups/shared", "/subscriptions/$subB/resourceGroups/shared")

        @($result.azure.resourceGroupIds).Count | Should -Be 2
        @($result.databricks.workspaces).Count | Should -Be 2
        $result.databricks.workspaces.name | Should -Contain 'a-shared'
        $result.databricks.workspaces.name | Should -Contain 'b-shared'
    }

    It 'rejects <Label> subscription input rather than falling back to the base scope' -ForEach @(
        @{ Label = 'malformed'; Id = 'not-a-guid' },
        @{ Label = 'unknown'; Id = '55555555-5555-5555-5555-555555555555' },
        @{ Label = 'disabled'; Id = '33333333-3333-3333-3333-333333333333' },
        @{ Label = 'cross-tenant'; Id = '44444444-4444-4444-4444-444444444444' }
    ) {
        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($Id) -ResourceGroups @('shared') } |
            Should -Throw '*Subscription*'
        Assert-MockCalled Get-AzureAssessmentPagedValues -Times 0
    }

    It 'rejects a group outside the selected subscription even if another account can access it' {
        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) `
                -ResourceGroups @("/subscriptions/$subB/resourceGroups/shared") } |
            Should -Throw '*not accessible*'
    }

    It 'rejects an unknown group rather than collecting all groups' {
        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('missing') } |
            Should -Throw '*not accessible*'
    }

    It 'propagates denied ARM discovery without reusing old workspaces' {
        Mock Get-AzureAssessmentPagedValues { throw 'AuthorizationFailed: resource group listing denied' }

        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('a-only') } |
            Should -Throw '*AuthorizationFailed*'
    }

    It 'rejects a selected group containing no Databricks workspaces without broadening scope' {
        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('empty') } |
            Should -Throw '*No Azure Databricks workspaces*'
    }

    It 'rejects an empty workspace inventory even when the base config contains a workspace' {
        $script:workspacesBySubscription[$subA] = @()

        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('a-only') } |
            Should -Throw '*No Azure Databricks workspaces*'
    }

    It 'rejects missing current tenant and makes no ARM discovery calls' {
        $script:account = [pscustomobject]@{}

        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('a-only') } |
            Should -Throw '*tenant*'
        Assert-MockCalled Get-AzureAssessmentPagedValues -Times 0
    }

    It 'rejects a tenant with no eligible subscriptions' {
        $script:accounts = @($accounts | Where-Object { $_.id -in @($disabledSub, $foreignSub) })

        { New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('a-only') } |
            Should -Throw '*No enabled subscriptions*'
        Assert-MockCalled Get-AzureAssessmentPagedValues -Times 0
    }

    It 'never transfers global SQL or unrelated workspace warehouse IDs to newly discovered workspaces' {
        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA, $subB)

        $result.databricks.PSObject.Properties.Name | Should -Not -Contain 'sqlWarehouseId'
        foreach ($workspace in $result.databricks.workspaces) {
            $workspace.PSObject.Properties.Name | Should -Not -Contain 'sqlWarehouseId'
        }
        @(Get-AzureAssessmentProperty -InputObject $result.databricks -Name deepDiveJobRunIds -Default @()).Count | Should -Be 0
        @(Get-AzureAssessmentProperty -InputObject $result.databricks -Name deepDiveTableNames -Default @()).Count | Should -Be 0
    }

    It 'preserves per-workspace SQL and settings when matching by resource ID or normalized hostname' {
        $config.databricks.workspaces = @(
            [pscustomobject]@{
                include = $true
                resourceId = $workspacesBySubscription[$subA][0].id.ToUpperInvariant()
                workspaceUrl = 'outdated.azuredatabricks.net'
                sqlWarehouseId = 'warehouse-by-resource-id'
                allowSqlWarehouseAutoStart = $false
            },
            [pscustomobject]@{
                include = $true
                workspaceUrl = 'https://ADB-201.1.azuredatabricks.net/'
                sqlWarehouseId = 'warehouse-by-host'
                allowSqlWarehouseAutoStart = $true
            }
        )

        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA, $subB)

        $matchedById = @($result.databricks.workspaces | Where-Object name -EQ 'a-shared')[0]
        $matchedByHost = @($result.databricks.workspaces | Where-Object name -EQ 'b-shared')[0]
        $matchedById.sqlWarehouseId | Should -Be 'warehouse-by-resource-id'
        $matchedById.allowSqlWarehouseAutoStart | Should -BeFalse
        $matchedById.workspaceUrl | Should -Be 'adb-101.1.azuredatabricks.net'
        $matchedByHost.sqlWarehouseId | Should -Be 'warehouse-by-host'
        $matchedByHost.allowSqlWarehouseAutoStart | Should -BeTrue
        foreach ($workspace in @($result.databricks.workspaces | Where-Object { $_.name -in @('a-extra', 'b-extra') })) {
            $workspace.PSObject.Properties.Name | Should -Not -Contain 'sqlWarehouseId'
        }
    }

    It 'deep clones configuration, preserves unrelated settings, and performs no writes' {
        $before = $config | ConvertTo-Json -Depth 100 -Compress

        $result = New-AssessmentScopeConfig -Config $config -SubscriptionIds @($subA) -ResourceGroups @('a-only')

        ($config | ConvertTo-Json -Depth 100 -Compress) | Should -BeExactly $before
        [object]::ReferenceEquals($config, $result) | Should -BeFalse
        [object]::ReferenceEquals($config.analysis, $result.analysis) | Should -BeFalse
        $result.analysis.maxPages | Should -Be 7
        $result.thresholds.materialMonthlyCost | Should -Be 123
        $result.azure.costBasis | Should -Contain 'AmortizedCost'
        $result.outputs.root | Should -Be $config.outputs.root
        $result.analysis.maxPages = 99
        $result.outputs.root = 'changed-only-on-clone'
        $config.analysis.maxPages | Should -Be 7
        $config.outputs.root | Should -Not -Be 'changed-only-on-clone'
        Assert-MockCalled Write-JsonFile -Times 0
        Assert-MockCalled Set-Content -Times 0
        Assert-MockCalled Invoke-WebRequest -Times 0
        Assert-MockCalled Invoke-RestMethod -Times 0
    }

    It 'selects comma-separated subscriptions and same-named groups with subscription context' {
        $script:groupsBySubscription[$subA] = @($groupsBySubscription[$subA] | Where-Object name -EQ 'shared')
        $script:groupsBySubscription[$subB] = @($groupsBySubscription[$subB] | Where-Object name -EQ 'shared')
        Set-ScopeTestAnswers -Answers @('1,2', '1,2')

        $result = New-AssessmentScopeConfig -Config $config -SelectScope

        @($result.azure.subscriptions).Count | Should -Be 2
        @($result.azure.resourceGroupIds).Count | Should -Be 2
        @($result.databricks.workspaces).Count | Should -Be 2
        Assert-MockCalled Read-Host -Times 2 -Exactly
        Assert-MockCalled Write-Host -Times 1 -ParameterFilter {
            ($Object -join ' ').Contains('shared') -and ($Object -join ' ').Contains($script:subA) -and
                -not ($Object -join ' ').Contains('/providers/')
        }
        Assert-MockCalled Write-Host -Times 1 -ParameterFilter {
            ($Object -join ' ').Contains('shared') -and ($Object -join ' ').Contains($script:subB) -and
                -not ($Object -join ' ').Contains('/providers/')
        }
    }

    It 'selects only the picked subscription and group rather than the whole displayed list' {
        Set-ScopeTestAnswers -Answers @('2', '1')

        $result = New-AssessmentScopeConfig -Config $config -SelectScope

        @($result.azure.subscriptions).Count | Should -Be 1
        $result.azure.subscriptions | Should -Contain $subB
        @($result.azure.resourceGroupIds).Count | Should -Be 1
        $result.azure.resourceGroupIds | Should -Contain "/subscriptions/$subB/resourceGroups/b-only"
        @($result.databricks.workspaces).Count | Should -Be 1
        $result.databricks.workspaces[0].name | Should -Be 'b-extra'
    }

    It 'allows star only for displayed eligible subscriptions and their displayed groups' {
        Set-ScopeTestAnswers -Answers @('*', '*')

        $result = New-AssessmentScopeConfig -Config $config -SelectScope

        @($result.azure.subscriptions).Count | Should -Be 2
        $result.azure.subscriptions | Should -Not -Contain $disabledSub
        $result.azure.subscriptions | Should -Not -Contain $foreignSub
        @($result.databricks.workspaces).Count | Should -Be 4
        Assert-MockCalled Write-Host -Times 0 -ParameterFilter {
            ($Object -join ' ').Contains($script:disabledSub) -or ($Object -join ' ').Contains($script:foreignSub)
        }
    }

    It 'cancels at the <Stage> prompt without returning a fallback config' -ForEach @(
        @{ Stage = 'subscription'; Answers = @('q'); Prompts = 1 },
        @{ Stage = 'resource group'; Answers = @('1', 'q'); Prompts = 2 }
    ) {
        Set-ScopeTestAnswers -Answers $Answers

        { New-AssessmentScopeConfig -Config $config -SelectScope } | Should -Throw '*Scope selection canceled*'
        Assert-MockCalled Read-Host -Times $Prompts -Exactly
    }

    It 'rejects invalid subscription picker input <Label>' -ForEach @(
        @{ Label = 'empty'; Answer = '' },
        @{ Label = 'zero'; Answer = '0' },
        @{ Label = 'out of range'; Answer = '3' },
        @{ Label = 'non-numeric'; Answer = 'Alpha' },
        @{ Label = 'partial list'; Answer = '1,' },
        @{ Label = 'mixed star'; Answer = '1,*' }
    ) {
        Set-ScopeTestAnswers -Answers @($Answer)

        { New-AssessmentScopeConfig -Config $config -SelectScope } | Should -Throw '*Invalid*selection*'
        Assert-MockCalled Get-AzureAssessmentPagedValues -Times 0
    }

    It 'rejects empty group selection rather than treating it as all groups' {
        Set-ScopeTestAnswers -Answers @('1', '')

        { New-AssessmentScopeConfig -Config $config -SelectScope } | Should -Throw '*Invalid*selection*'
    }
}

Describe 'Resolved scope run snapshot' {
    It 'writes the complete effective configuration into its own run without mutating the caller' {
        $config = [pscustomobject]@{
            customerId = 'customer'
            assessmentId = 'scoped-run'
            azure = [pscustomobject]@{
                subscriptions = @('11111111-1111-1111-1111-111111111111')
                resourceGroups = @('selected')
                resourceGroupIds = @('/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/selected')
                costScopes = @('/subscriptions/11111111-1111-1111-1111-111111111111')
            }
            databricks = [pscustomobject]@{
                workspaces = @([pscustomobject]@{
                    include = $true
                    workspaceUrl = 'adb-101.1.azuredatabricks.net'
                    workspaceId = '101'
                    sqlWarehouseId = 'selected-warehouse'
                })
            }
            analysis = [pscustomobject]@{
                startUtc = '2026-08-01T00:00:00Z'
                endUtc = '2026-09-01T00:00:00Z'
                timeZone = 'UTC'
            }
            outputs = [pscustomobject]@{ root = (Join-Path $TestDrive 'snapshot-runs') }
        }
        $before = $config | ConvertTo-Json -Depth 100 -Compress

        $context = New-AssessmentRun -Config $config -ToolkitVersion 'test'

        $snapshot = Join-Path $context.Root 'assessment-config.json'
        Test-Path -LiteralPath $snapshot | Should -BeTrue
        $saved = Get-Content -Raw -LiteralPath $snapshot | ConvertFrom-Json -Depth 100
        ($saved | ConvertTo-Json -Depth 100 -Compress) | Should -BeExactly $before
        ($config | ConvertTo-Json -Depth 100 -Compress) | Should -BeExactly $before
    }
}
