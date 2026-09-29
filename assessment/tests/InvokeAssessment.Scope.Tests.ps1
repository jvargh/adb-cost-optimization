BeforeAll {
    $assessmentRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $entryPoint = Join-Path $assessmentRoot 'Invoke-Assessment.ps1'
    $collectorPath = 'Invoke-ScopeTestCollector'
    $safetyPath = 'Invoke-ScopeTestSafety'

    function az { throw 'Unmocked Azure CLI invocation is forbidden in wrapper tests.' }
    function python { throw 'Unmocked report pipeline invocation is forbidden in wrapper tests.' }
    function Invoke-ScopeTestCollector {
        param([string]$ConfigPath, [switch]$PassThru, [switch]$SkipAnalysis, [switch]$ContinueOnCollectorError)
        throw 'Unmocked collector invocation is forbidden in wrapper tests.'
    }
    function Invoke-ScopeTestSafety {
        param([string]$Path)
        throw 'Unmocked safety-check invocation is forbidden in wrapper tests.'
    }
}

AfterAll {
    Remove-Variable -Name AssessmentScopeWrapperTestState -Scope Global -ErrorAction SilentlyContinue
}

Describe 'Scope-aware wrapper execution' {
    BeforeEach {
        $script:wrapperSub = '11111111-1111-1111-1111-111111111111'
        $script:wrapperTenant = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        $script:wrapperGroup = "/subscriptions/$wrapperSub/resourceGroups/selected-group"
        $script:invocationRoot = Join-Path $TestDrive 'caller'
        $script:outputRoot = Join-Path $invocationRoot 'relative-output'
        $script:returnedRoot = Join-Path $outputRoot 'run-returned-by-collector'
        $script:newerRoot = Join-Path $outputRoot 'unrelated-newer-run'
        foreach ($root in @($returnedRoot, $newerRoot)) {
            New-Item -ItemType Directory -Path (Join-Path $root 'reports') -Force | Out-Null
            '{"status":"completed"}' | Set-Content -LiteralPath (Join-Path $root 'assessment-manifest.json')
            'Test report' | Set-Content -LiteralPath (Join-Path $root 'reports\assessment-report.md')
        }
        (Get-Item -LiteralPath $returnedRoot).LastWriteTimeUtc = [datetime]::UtcNow.AddHours(-2)
        (Get-Item -LiteralPath $newerRoot).LastWriteTimeUtc = [datetime]::UtcNow.AddHours(2)
        $script:sourceConfig = [pscustomobject]@{
            customerId = 'wrapper-customer'
            assessmentId = 'wrapper-assessment'
            azure = [pscustomobject]@{
                subscriptions = @($wrapperSub)
                resourceGroups = @('original-group')
                costScope = "/subscriptions/$wrapperSub"
            }
            databricks = [pscustomobject]@{
                workspaces = @([pscustomobject]@{
                    name = 'original-workspace'
                    workspaceUrl = 'original.azuredatabricks.net'
                    workspaceId = '999'
                    include = $true
                })
                deepDiveJobRunIds = @()
                deepDiveTableNames = @()
            }
            analysis = [pscustomobject]@{
                startUtc = '2026-08-01T00:00:00Z'
                endUtc = '2026-09-01T00:00:00Z'
                timeZone = 'UTC'
                retryCount = 0
            }
            outputs = [pscustomobject]@{ root = $outputRoot }
        }
        $script:sourcePath = Join-Path $invocationRoot 'scope.json'
        $sourceConfig | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $sourcePath
        $script:sourceText = Get-Content -Raw -LiteralPath $sourcePath
        $script:wrapperAnswers = [Collections.Generic.Queue[string]]::new()
        # External script calls have their own script scope; share only this test-owned state with mocks.
        $global:AssessmentScopeWrapperTestState = @{
            Subscription = $wrapperSub
            Tenant = $wrapperTenant
            Group = $wrapperGroup
            ReturnedRoot = $returnedRoot
            NewerRoot = $newerRoot
            Config = $null
            ConfigPath = $null
            PipelineArguments = @()
            Answers = $wrapperAnswers
        }
        $script:wrapperState = $global:AssessmentScopeWrapperTestState
        Mock Join-Path { 'Invoke-ScopeTestCollector' } -ParameterFilter {
            $ChildPath -eq 'Collect-CostOptimizationAssessment.ps1'
        }
        Mock Join-Path { 'Invoke-ScopeTestSafety' } -ParameterFilter {
            $ChildPath -eq 'scripts\Test-AssessmentReadOnly.ps1'
        }
        Mock Write-Host {}
        Mock Write-Warning {}
        Mock Invoke-Item {}
        Mock Copy-Item { throw 'Unexpected configuration initialization.' }
        Mock Invoke-WebRequest { throw 'Network calls are forbidden in wrapper tests.' }
        Mock Invoke-RestMethod { throw 'Network calls are forbidden in wrapper tests.' }
        Mock Invoke-Pester { throw 'Unexpected nested validation.' }
        Mock -CommandName $safetyPath -MockWith { throw 'Unexpected safety-check action.' }
        Mock Read-Host {
            if ($global:AssessmentScopeWrapperTestState.Answers.Count -eq 0) {
                throw 'Unexpected interactive scope prompt.'
            }
            $global:AssessmentScopeWrapperTestState.Answers.Dequeue()
        }
        Mock az {
            $global:LASTEXITCODE = 0
            if (($args -join ' ') -eq 'account show --output json --only-show-errors') {
                return (@{
                    id = $global:AssessmentScopeWrapperTestState.Subscription
                    tenantId = $global:AssessmentScopeWrapperTestState.Tenant
                } | ConvertTo-Json -Compress)
            }
            if (($args -join ' ') -eq 'account list --output json --only-show-errors') {
                return (ConvertTo-Json -InputObject @(
                    @{
                        id = $global:AssessmentScopeWrapperTestState.Subscription
                        tenantId = $global:AssessmentScopeWrapperTestState.Tenant
                        state = 'Enabled'
                        name = 'Test subscription'
                    }
                ) -Compress)
            }
            if ($args[0] -eq 'rest' -and $args -contains 'GET') {
                $url = @($args | Where-Object { $_ -like '--url=*' })[0].Substring(6).Trim('"')
                if ($url -eq "https://management.azure.com/subscriptions/$($global:AssessmentScopeWrapperTestState.Subscription)/resourcegroups?api-version=2021-04-01") {
                    return (@{ value = @(@{ id = $global:AssessmentScopeWrapperTestState.Group; name = 'selected-group' }) } |
                        ConvertTo-Json -Depth 10 -Compress)
                }
                if ($url -eq "https://management.azure.com/subscriptions/$($global:AssessmentScopeWrapperTestState.Subscription)/providers/Microsoft.Databricks/workspaces?api-version=2024-05-01") {
                    return (@{ value = @(@{
                        id = "$($global:AssessmentScopeWrapperTestState.Group)/providers/Microsoft.Databricks/workspaces/selected-workspace"
                        name = 'selected-workspace'
                        properties = @{ workspaceId = '101'; workspaceUrl = 'adb-101.1.azuredatabricks.net' }
                    }) } | ConvertTo-Json -Depth 10 -Compress)
                }
            }
            throw "Unexpected Azure CLI arguments: $($args -join ' ')"
        }
        Mock -CommandName $collectorPath -MockWith {
            $global:AssessmentScopeWrapperTestState.ConfigPath = $ConfigPath
            $global:AssessmentScopeWrapperTestState.Config = Get-Content -Raw -LiteralPath $ConfigPath | ConvertFrom-Json -Depth 100
            if ($PassThru) {
                [pscustomobject]@{ RunId = 'run-returned-by-collector'; Root = $global:AssessmentScopeWrapperTestState.ReturnedRoot }
            }
        }
        Mock python {
            $global:AssessmentScopeWrapperTestState.PipelineArguments = @($args)
            $global:LASTEXITCODE = 0
        }
        Push-Location $invocationRoot
    }

    AfterEach {
        Pop-Location
    }

    It 'resolves ConfigPath and OutputRoot relative to invocation cwd and forwards the effective config' {
        & $entryPoint -Action Run -ConfigPath '.\scope.json' -OutputRoot '.\relative-output' -NoOpenReport

        $wrapperState.Config.customerId | Should -Be 'wrapper-customer'
        $wrapperState.Config.outputs.root | Should -Be $outputRoot
        $wrapperState.Config.databricks.workspaces[0].name | Should -Be 'original-workspace'
        Assert-MockCalled -CommandName $collectorPath -Times 1 -Exactly -ParameterFilter { $PassThru }
        Assert-MockCalled Invoke-Item -Times 0
        Assert-MockCalled az -Times 0
        (Get-Location).Path | Should -Be $invocationRoot
        (Get-Content -Raw -LiteralPath $sourcePath) | Should -BeExactly $sourceText
        Test-Path -LiteralPath $wrapperState.ConfigPath | Should -BeFalse
    }

    It 'opens the collector-returned run rather than a newer unrelated run' {
        & $entryPoint -Action Run -ConfigPath $sourcePath

        Assert-MockCalled Invoke-Item -Times 1 -Exactly -ParameterFilter {
            $LiteralPath -eq (Join-Path $global:AssessmentScopeWrapperTestState.ReturnedRoot 'reports\assessment-report.md')
        }
        Assert-MockCalled Invoke-Item -Times 0 -ParameterFilter {
            $LiteralPath -eq (Join-Path $global:AssessmentScopeWrapperTestState.NewerRoot 'reports\assessment-report.md')
        }
        Assert-MockCalled -CommandName $collectorPath -Times 1 -Exactly -ParameterFilter { $PassThru }
    }

    It 'does not open any report when NoOpenReport is supplied' {
        & $entryPoint -Action Run -ConfigPath $sourcePath -NoOpenReport

        Assert-MockCalled -CommandName $collectorPath -Times 1 -Exactly
        Assert-MockCalled Invoke-Item -Times 0
    }

    It 'executes the real scope resolver before collection for <Action>' -ForEach @(
        @{ Action = 'Run' },
        @{ Action = 'Readiness' }
    ) {
        & $entryPoint -Action $Action -ConfigPath '.\scope.json' -SubscriptionIds @($wrapperSub) `
            -ResourceGroups @('selected-group') -OutputRoot '.\relative-output' -NoOpenReport

        $wrapperState.Config.azure.subscriptions | Should -Contain $wrapperSub
        $wrapperState.Config.azure.resourceGroupIds | Should -Contain $wrapperGroup
        $wrapperState.Config.azure.resourceGroups | Should -Not -Contain 'original-group'
        $wrapperState.Config.azure.costScopes | Should -Contain "/subscriptions/$wrapperSub"
        $wrapperState.Config.azure.PSObject.Properties.Name | Should -Not -Contain 'costScope'
        @($wrapperState.Config.databricks.workspaces).Count | Should -Be 1
        $wrapperState.Config.databricks.workspaces[0].name | Should -Be 'selected-workspace'
        $wrapperState.Config.outputs.root | Should -Be $outputRoot
        Assert-MockCalled az -Times 4 -Exactly
        Assert-MockCalled -CommandName $collectorPath -Times 1 -Exactly
        Assert-MockCalled Invoke-Item -Times 0
        Test-Path -LiteralPath $wrapperState.ConfigPath | Should -BeFalse
        (Get-Content -Raw -LiteralPath $sourcePath) | Should -BeExactly $sourceText
        if ($Action -eq 'Readiness') {
            Assert-MockCalled -CommandName $collectorPath -Times 1 -ParameterFilter {
                $SkipAnalysis -and $ContinueOnCollectorError
            }
        }
    }

    It 'allows an empty base scope for <Action> with <Selection> selection' -ForEach @(
        @{ Action = 'Run'; Selection = 'explicit' },
        @{ Action = 'Run'; Selection = 'interactive' },
        @{ Action = 'Readiness'; Selection = 'explicit' },
        @{ Action = 'Readiness'; Selection = 'interactive' }
    ) {
        $sourceConfig.azure.subscriptions = @()
        $sourceConfig.azure.resourceGroups = @()
        $sourceConfig.databricks.workspaces = @()
        $sourceConfig | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $sourcePath
        $emptySourceText = Get-Content -Raw -LiteralPath $sourcePath
        $parameters = @{ Action = $Action; ConfigPath = '.\scope.json'; NoOpenReport = $true }
        if ($Selection -eq 'interactive') {
            $parameters.SelectScope = $true
            $wrapperAnswers.Enqueue('1')
            $wrapperAnswers.Enqueue('1')
        }
        else {
            $parameters.SubscriptionIds = @($wrapperSub)
        }

        & $entryPoint @parameters

        @($wrapperState.Config.azure.subscriptions).Count | Should -Be 1
        $wrapperState.Config.azure.subscriptions | Should -Contain $wrapperSub
        $wrapperState.Config.azure.resourceGroupIds | Should -Contain $wrapperGroup
        @($wrapperState.Config.databricks.workspaces).Count | Should -Be 1
        $wrapperState.Config.databricks.workspaces[0].name | Should -Be 'selected-workspace'
        Assert-MockCalled -CommandName $collectorPath -Times 1 -Exactly
        Assert-MockCalled Invoke-Item -Times 0
        (Get-Content -Raw -LiteralPath $sourcePath) | Should -BeExactly $emptySourceText
        Test-Path -LiteralPath $wrapperState.ConfigPath | Should -BeFalse
    }

    It 'still rejects an empty base scope for <Action> without a selector' -ForEach @(
        @{ Action = 'Run' },
        @{ Action = 'Readiness' }
    ) {
        $sourceConfig.azure.subscriptions = @()
        $sourceConfig.databricks.workspaces = @()
        $sourceConfig | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $sourcePath

        { & $entryPoint -Action $Action -ConfigPath '.\scope.json' -NoOpenReport } |
            Should -Throw '*selects no Azure subscriptions or Databricks workspaces*'

        Assert-MockCalled az -Times 0
        Assert-MockCalled -CommandName $collectorPath -Times 0
        Assert-MockCalled Invoke-Item -Times 0
        (Get-Location).Path | Should -Be $invocationRoot
    }

    It 'supports ResourceGroups alone using subscriptions from the provided config' {
        & $entryPoint -Action Run -ConfigPath '.\scope.json' -ResourceGroups @('selected-group') -NoOpenReport

        $wrapperState.Config.azure.subscriptions | Should -Contain $wrapperSub
        $wrapperState.Config.databricks.workspaces[0].name | Should -Be 'selected-workspace'
        Assert-MockCalled Read-Host -Times 0
    }

    It 'supports subscription-only selection without stale group filtering' {
        & $entryPoint -Action Run -ConfigPath '.\scope.json' -SubscriptionIds @($wrapperSub) -NoOpenReport

        $wrapperState.Config.azure.resourceGroupIds | Should -Contain $wrapperGroup
        $wrapperState.Config.databricks.workspaces[0].name | Should -Be 'selected-workspace'
        Assert-MockCalled Read-Host -Times 0
    }

    It 'runs the interactive scope picker through the real entrypoint' {
        $script:wrapperAnswers.Enqueue('1')
        $script:wrapperAnswers.Enqueue('1')

        & $entryPoint -Action Run -ConfigPath '.\scope.json' -SelectScope -NoOpenReport

        $wrapperState.Config.azure.resourceGroupIds | Should -Contain $wrapperGroup
        $wrapperState.Config.databricks.workspaces[0].name | Should -Be 'selected-workspace'
        Assert-MockCalled Read-Host -Times 2 -Exactly
        Assert-MockCalled -CommandName $collectorPath -Times 1 -Exactly
    }

    It 'does not collect or open a report after interactive cancellation' {
        $script:wrapperAnswers.Enqueue('q')

        { & $entryPoint -Action Run -ConfigPath '.\scope.json' -SelectScope -NoOpenReport } |
            Should -Throw '*Scope selection canceled*'

        Assert-MockCalled -CommandName $collectorPath -Times 0
        Assert-MockCalled Invoke-Item -Times 0
        (Get-Location).Path | Should -Be $invocationRoot
        (Get-Content -Raw -LiteralPath $sourcePath) | Should -BeExactly $sourceText
    }

    It 'cleans the effective config and restores cwd when collection fails' {
        Mock -CommandName $collectorPath -MockWith {
            $global:AssessmentScopeWrapperTestState.ConfigPath = $ConfigPath
            throw 'collector failure for cleanup test'
        }

        { & $entryPoint -Action Run -ConfigPath '.\scope.json' -OutputRoot '.\relative-output' -NoOpenReport } |
            Should -Throw '*collector failure for cleanup test*'

        $wrapperState.ConfigPath | Should -Not -BeNullOrEmpty
        Test-Path -LiteralPath $wrapperState.ConfigPath | Should -BeFalse
        (Get-Location).Path | Should -Be $invocationRoot
        Assert-MockCalled Invoke-Item -Times 0
        (Get-Content -Raw -LiteralPath $sourcePath) | Should -BeExactly $sourceText
    }

    It 'removes SQL warehouse IDs for readiness while preserving the original config' {
        $sourceConfig.databricks | Add-Member -NotePropertyName sqlWarehouseId -NotePropertyValue 'global-warehouse'
        $sourceConfig.databricks.workspaces[0] | Add-Member -NotePropertyName sqlWarehouseId -NotePropertyValue 'workspace-warehouse'
        $sourceConfig | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $sourcePath
        $sourceText = Get-Content -Raw -LiteralPath $sourcePath

        & $entryPoint -Action Readiness -ConfigPath '.\scope.json' -NoOpenReport

        $wrapperState.Config.databricks.PSObject.Properties.Name | Should -Not -Contain 'sqlWarehouseId'
        $wrapperState.Config.databricks.workspaces[0].PSObject.Properties.Name | Should -Not -Contain 'sqlWarehouseId'
        Assert-MockCalled -CommandName $collectorPath -Times 1 -ParameterFilter {
            $SkipAnalysis -and $ContinueOnCollectorError
        }
        Test-Path -LiteralPath $wrapperState.ConfigPath | Should -BeFalse
        (Get-Content -Raw -LiteralPath $sourcePath) | Should -BeExactly $sourceText
        Assert-MockCalled Invoke-Item -Times 0
    }

    It 'rejects <ScopeParameter> with Action <Action> before any external action' -ForEach @(
        foreach ($action in @('Initialize', 'Reports', 'Open', 'Validate')) {
            foreach ($scopeParameter in @('SelectScope', 'SubscriptionIds', 'ResourceGroups')) {
                @{ Action = $action; ScopeParameter = $scopeParameter }
            }
        }
    ) {
        $parameters = @{ Action = $Action; ConfigPath = '.\scope.json'; NoOpenReport = $true }
        $parameters[$ScopeParameter] = switch ($ScopeParameter) {
            'SelectScope' { $true }
            'SubscriptionIds' { @($wrapperSub) }
            'ResourceGroups' { @('selected-group') }
        }

        { & $entryPoint @parameters } | Should -Throw '*only*Run*Readiness*'

        Assert-MockCalled -CommandName $collectorPath -Times 0
        Assert-MockCalled Invoke-Item -Times 0
        Assert-MockCalled Copy-Item -Times 0
        Assert-MockCalled Invoke-Pester -Times 0
        Assert-MockCalled python -Times 0
        Assert-MockCalled az -Times 0
    }

    It 'rejects mixing interactive and explicit selectors before discovery or collection' {
        { & $entryPoint -Action Run -ConfigPath '.\scope.json' -SelectScope -SubscriptionIds @($wrapperSub) -NoOpenReport } |
            Should -Throw '*not both*'

        Assert-MockCalled az -Times 0
        Assert-MockCalled -CommandName $collectorPath -Times 0
    }

    It 'recreates reports using the selected run snapshot by default without recollecting' {
        $snapshotPath = Join-Path $returnedRoot 'assessment-config.json'
        $sourceConfig | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $snapshotPath

        & $entryPoint -Action Reports -RunRoot $returnedRoot -NoOpenReport

        $configIndex = [array]::IndexOf($wrapperState.PipelineArguments, '--config')
        $rootIndex = [array]::IndexOf($wrapperState.PipelineArguments, '--run-root')
        $configIndex | Should -BeGreaterThan -1
        $wrapperState.PipelineArguments[$configIndex + 1] | Should -Be $snapshotPath
        $wrapperState.PipelineArguments[$rootIndex + 1] | Should -Be $returnedRoot
        Assert-MockCalled python -Times 1 -Exactly
        Assert-MockCalled -CommandName $collectorPath -Times 0
        Assert-MockCalled az -Times 0
        Assert-MockCalled Invoke-Item -Times 0
    }

    It 'honors an explicit report config resolved relative to invocation cwd rather than the run snapshot' {
        $sourceConfig | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath (Join-Path $returnedRoot 'assessment-config.json')

        & $entryPoint -Action Reports -RunRoot $returnedRoot -ConfigPath '.\scope.json' -NoOpenReport

        $configIndex = [array]::IndexOf($wrapperState.PipelineArguments, '--config')
        $wrapperState.PipelineArguments[$configIndex + 1] | Should -Be $sourcePath
        Assert-MockCalled -CommandName $collectorPath -Times 0
    }
}
