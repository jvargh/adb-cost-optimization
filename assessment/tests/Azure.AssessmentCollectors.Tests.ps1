BeforeAll {
    $assessmentRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    . (Join-Path $assessmentRoot 'scripts\Assessment.Common.ps1')
    . (Join-Path $assessmentRoot 'collectors\Azure.AssessmentCollectors.ps1')
}

Describe 'Azure assessment collector contract' {
    It 'exposes the orchestrator entry point with the required parameters' {
        $command = Get-Command Invoke-AzureAssessmentCollectors
        $command.Parameters.Keys | Should -Contain 'Config'
        $command.Parameters.Keys | Should -Contain 'RunContext'
    }

    It 'allows only read-only REST operations' {
        Mock Invoke-WithAssessmentRetry { throw 'should not execute' }
        {
            Invoke-AzureAssessmentRest -Method POST `
                -Uri 'https://management.azure.com/subscriptions/example/providers/Microsoft.Compute/virtualMachines?api-version=2024-03-01' `
                -Body @{}
        } | Should -Throw '*POST is not approved*'
    }

    It 'rejects non-ARM endpoints' {
        {
            Invoke-AzureAssessmentRest -Method GET -Uri 'https://example.test/resources'
        } | Should -Throw '*management.azure.com*'
    }

    It 'passes POST JSON through a temporary file and removes it afterward' {
        $script:bodyPath = $null
        $script:bodyValue = $null
        $script:urlArgument = $null
        Mock Invoke-AzureAssessmentCliJson {
            $bodyIndex = [Array]::IndexOf($Arguments, '--body')
            $script:bodyPath = $Arguments[$bodyIndex + 1].Substring(1)
            $script:bodyValue = Get-Content -Raw -LiteralPath $script:bodyPath | ConvertFrom-Json
            $script:urlArgument = @($Arguments | Where-Object { $_ -like '--url=*' })[0]
            [pscustomobject]@{ data = @() }
        }

        Invoke-AzureAssessmentRest -Method POST `
            -Uri 'https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01' `
            -Body @{ options = @{ resultFormat = 'objectArray' } } | Out-Null

        $script:bodyValue.options.resultFormat | Should -Be 'objectArray'
        $script:urlArgument | Should -Be '--url="https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01"'
        Test-Path -LiteralPath $script:bodyPath | Should -BeFalse
    }

    It 'returns all source results and writes explicit source status' {
        $testRoot = Join-Path $TestDrive 'contract-run'
        $config = [pscustomobject]@{
            customerId = 'customer'
            assessmentId = 'assessment'
            azure = [pscustomobject]@{ subscriptions = @('sub') }
            analysis = [pscustomobject]@{}
            redaction = [pscustomobject]@{}
        }
        $context = [pscustomobject]@{ Root = $testRoot }
        Mock Assert-ReadOnlyAssessment {}
        Mock Invoke-AzureInventoryAssessmentCollector {
            New-CollectorResult -Name inventory -Status passed -StartedAt (Get-Date)
        }
        Mock Invoke-AzureGovernanceAssessmentCollector {
            New-CollectorResult -Name governance -Status partial -StartedAt (Get-Date) -Limitations @('restricted')
        }
        Mock Invoke-AzureCostAssessmentCollector {
            New-CollectorResult -Name cost -Status passed -StartedAt (Get-Date)
        }
        Mock Invoke-AzureFinancialGovernanceAssessmentCollector {
            New-CollectorResult -Name commitments -Status skipped -StartedAt (Get-Date)
        }
        Mock Invoke-AzureQuotaAssessmentCollector {
            New-CollectorResult -Name quotas -Status passed -StartedAt (Get-Date)
        }

        $results = @(Invoke-AzureAssessmentCollectors -Config $config -RunContext $context)

        $results.Count | Should -Be 5
        $statusPath = Join-Path $testRoot 'raw\azure\source-status.json'
        Test-Path -LiteralPath $statusPath | Should -BeTrue
        @(Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json).Count | Should -Be 5
    }
}

Describe 'Azure Resource Graph pagination' {
    It 'follows skip tokens and returns every object' {
        $script:page = 0
        Mock Invoke-AzureAssessmentRest {
            $script:page++
            if ($script:page -eq 1) {
                return [pscustomobject]@{
                    data = @([pscustomobject]@{ id = 'one' })
                    '$skipToken' = 'next-page'
                }

                Describe 'Azure ARM list contract' {
                    It 'follows next links and tolerates missing value properties as empty pages' {
                        $script:page = 0
                        Mock Invoke-AzureAssessmentRest {
                            $script:page++
                            if ($script:page -eq 1) {
                                return [pscustomobject]@{
                                    value = @([pscustomobject]@{ id = 'one' })
                                    nextLink = 'https://management.azure.com/next?api-version=1'
                                }
                            }
                            return [pscustomobject]@{}
                        }
                        $settings = @{ MaxPages = 3; PageSize = 1; RetryCount = 0; RetryBaseSeconds = 1 }

                        $result = @(Get-AzureAssessmentPagedValues -Uri 'https://management.azure.com/first?api-version=1' -Settings $settings)

                        $result.Count | Should -Be 1
                        $result[0].id | Should -Be 'one'
                        Assert-MockCalled Invoke-AzureAssessmentRest -Times 2
                    }

                    It 'fails explicitly rather than discarding a continuation at the page limit' {
                        Mock Invoke-AzureAssessmentRest {
                            [pscustomobject]@{ value = @(); nextLink = 'https://management.azure.com/more?api-version=1' }
                        }
                        $settings = @{ MaxPages = 1; PageSize = 1; RetryCount = 0; RetryBaseSeconds = 1 }

                        { Get-AzureAssessmentPagedValues -Uri 'https://management.azure.com/first?api-version=1' -Settings $settings } |
                            Should -Throw '*maximum of 1 pages*'
                    }
                }
            }
            return [pscustomobject]@{
                data = @([pscustomobject]@{ id = 'two' })
            }
        }

        $settings = @{ MaxPages = 3; PageSize = 1; RetryCount = 0; RetryBaseSeconds = 1 }
        $result = @(Invoke-AzureAssessmentResourceGraph -Query 'resources' -Subscriptions @('sub') -Settings $settings)

        $result.Count | Should -Be 2
        $result[1].id | Should -Be 'two'
        Assert-MockCalled Invoke-AzureAssessmentRest -Times 2
    }

    It 'fails explicitly when the page limit is reached' {
        Mock Invoke-AzureAssessmentRest {
            [pscustomobject]@{ data = @(); '$skipToken' = 'still-more' }
        }
        $settings = @{ MaxPages = 1; PageSize = 1; RetryCount = 0; RetryBaseSeconds = 1 }

        {
            Invoke-AzureAssessmentResourceGraph -Query 'resources' -Subscriptions @('sub') -Settings $settings
        } | Should -Throw '*maximum of 1 pages*'
    }
}

Describe 'Azure Cost Management mapping' {
    It 'maps response columns and follows nextLink with POST' {
        $script:costPage = 0
        Mock Invoke-AzureAssessmentRest {
            $script:costPage++
            if ($script:costPage -eq 1) {
                return [pscustomobject]@{
                    properties = [pscustomobject]@{
                        columns = @(
                            [pscustomobject]@{ name = 'PreTaxCost' },
                            [pscustomobject]@{ name = 'ResourceId' }
                        )
                        rows = @(
                            ,@(12.5, '/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Databricks/workspaces/dbw')
                        )
                        nextLink = 'https://management.azure.com/next?api-version=2023-11-01'
                    }
                }
            }
            return [pscustomobject]@{
                properties = [pscustomobject]@{
                    columns = @(
                        [pscustomobject]@{ name = 'PreTaxCost' },
                        [pscustomobject]@{ name = 'ResourceId' }
                    )
                    rows = @(
                        ,@(3.0, '/subscriptions/sub/resourceGroups/managed-rg/providers/Microsoft.Compute/virtualMachines/vm')
                    )
                }
            }
        }

        $settings = @{ MaxPages = 3; PageSize = 1000; RetryCount = 0; RetryBaseSeconds = 1 }
        $rows = @(Get-AzureAssessmentCostPages -Scope '/subscriptions/sub' -CostBasis ActualCost `
            -Start ([DateTimeOffset]'2026-01-01T00:00:00Z') -End ([DateTimeOffset]'2026-02-01T00:00:00Z') `
            -Settings $settings)

        $rows.Count | Should -Be 2
        $rows[0].PreTaxCost | Should -Be 12.5
        $rows[1].costBasis | Should -Be 'ActualCost'
        Assert-MockCalled Invoke-AzureAssessmentRest -Times 2 -ParameterFilter { $Method -eq 'POST' }
    }

    It 'splits long analysis ranges without gaps' {
        $windows = @(Split-AzureAssessmentTimeWindow `
            -Start ([DateTimeOffset]'2026-01-01T00:00:00Z') `
            -End ([DateTimeOffset]'2026-03-15T00:00:00Z') `
            -Days 31)

        $windows.Count | Should -Be 3
        $windows[0].End | Should -Be $windows[1].Start
        $windows[-1].End | Should -Be ([DateTimeOffset]'2026-03-15T00:00:00Z')
    }
}

Describe 'Azure partial failure behavior' {
    It 'returns a failed result instead of success-shaped empty cost data' {
        $testRoot = Join-Path $TestDrive 'run'
        New-Item -ItemType Directory -Path $testRoot | Out-Null
        $config = [pscustomobject]@{
            azure = [pscustomobject]@{
                subscriptions = @('sub')
                costScope = '/subscriptions/sub'
                costBasis = @('ActualCost')
                resourceGroups = @('rg')
            }
            analysis = [pscustomobject]@{
                startUtc = '2026-01-01T00:00:00Z'
                endUtc = '2026-01-02T00:00:00Z'
            }
        }
        $context = [pscustomobject]@{ Root = $testRoot }
        $settings = @{ MaxPages = 1; PageSize = 1000; RetryCount = 0; RetryBaseSeconds = 1 }
        Mock Get-AzureAssessmentCostPages { throw 'forbidden' }

        $result = Invoke-AzureCostAssessmentCollector -Config $config -RunContext $context -Settings $settings

        $result.status | Should -Be 'failed'
        $result.itemCount | Should -Be 0
        $result.error | Should -Match 'forbidden'
        Test-Path -LiteralPath $result.outputs[0] | Should -BeTrue
    }
}

Describe 'Azure subscription-qualified assessment scope' {
    BeforeEach {
        $script:subA = '11111111-1111-1111-1111-111111111111'
        $script:subB = '22222222-2222-2222-2222-222222222222'
        $script:groupA = "/subscriptions/$script:subA/resourceGroups/shared"
        $script:groupB = "/subscriptions/$script:subB/resourceGroups/other"
        $script:collision = "/subscriptions/$script:subB/resourceGroups/shared"
        $script:managedA = "/subscriptions/$script:subA/resourceGroups/managed"
        $script:managedB = "/subscriptions/$script:subB/resourceGroups/managed-other"
        $script:managedCollision = "/subscriptions/$script:subB/resourceGroups/managed"
        $script:workspaceA = "$script:groupA/providers/Microsoft.Databricks/workspaces/dbw"
        $script:workspaceB = "$script:groupB/providers/Microsoft.Databricks/workspaces/dbw"
        $script:workspaceCollision = "$script:collision/providers/Microsoft.Databricks/workspaces/dbw"
        $script:inventory = @(
            foreach ($pair in @(
                @($script:groupA, $script:managedA),
                @($script:groupB, $script:managedB),
                @($script:collision, $script:managedCollision)
            )) {
                $group = $pair[0]
                $managed = $pair[1]
                foreach ($groupId in @($group, $managed)) {
                    [pscustomobject]@{
                        id = $groupId; name = $groupId.Split('/')[-1]
                        type = 'microsoft.resources/subscriptions/resourcegroups'
                        subscriptionId = $groupId.Split('/')[2]; resourceGroup = ''; tags = $null
                    }
                }
                [pscustomobject]@{
                    id = "$group/providers/Microsoft.Databricks/workspaces/dbw"; name = 'dbw'
                    type = 'microsoft.databricks/workspaces'; subscriptionId = $group.Split('/')[2]
                    resourceGroup = $group.Split('/')[-1]; tags = $null
                    properties = [pscustomobject]@{ managedResourceGroupId = $managed }
                }
                [pscustomobject]@{
                    id = "$managed/providers/Microsoft.Compute/virtualMachines/worker"; name = 'worker'
                    type = 'microsoft.compute/virtualmachines'; subscriptionId = $group.Split('/')[2]
                    resourceGroup = $managed.Split('/')[-1]; tags = $null
                }
            }
        )
        $script:config = [pscustomobject]@{
            azure = [pscustomobject]@{
                subscriptions = @($script:subA, $script:subB)
                resourceGroupIds = @($script:groupA.ToUpperInvariant(), $script:groupB)
                resourceGroups = @('shared', 'other')
                costScopes = @("/subscriptions/$script:subA", "/subscriptions/$script:subB")
                costScope = '/subscriptions/legacy-ignored'
                costBasis = @('ActualCost', 'AmortizedCost')
            }
            analysis = [pscustomobject]@{
                startUtc = '2026-01-01T00:00:00Z'; endUtc = '2026-03-01T00:00:00Z'
            }
        }
        $script:context = [pscustomobject]@{ Root = (Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))) }
        $script:settings = @{ MaxPages = 2; PageSize = 1000; RetryCount = 0; RetryBaseSeconds = 1 }
        Mock Invoke-AzureAssessmentResourceGraph { $script:inventory }
        Mock Invoke-AzureAssessmentRest {
            $script:inventory | Where-Object { $Uri -eq "https://management.azure.com$($_.id)?api-version=2023-02-01" }
        }
        Mock Get-AzureAssessmentCostPages {
            foreach ($resource in $script:inventory | Where-Object {
                $_.type -notmatch '/resourcegroups$' -and $_.id.StartsWith("$Scope/", [StringComparison]::OrdinalIgnoreCase)
            }) {
                [pscustomobject]@{ ResourceId = $resource.id; PreTaxCost = 10; costBasis = $CostBasis; scope = $Scope }
            }
            [pscustomobject]@{ ResourceId = ''; PreTaxCost = 100; costBasis = $CostBasis; scope = $Scope }
        }
    }

    It 'uses exact selected groups and preserves only their associated managed groups including containers' {
        $result = Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        $resources = @(Get-Content -LiteralPath $result.outputs[0] | ConvertFrom-Json)
        $resources.Count | Should -Be 8
        $resources.id | Should -Contain $script:workspaceA
        $resources.id | Should -Contain $script:workspaceB
        $resources.id | Should -Contain $script:managedA
        $resources.id | Should -Contain $script:managedB
        $resources.id | Should -Not -Contain $script:workspaceCollision
        $resources.id | Should -Not -Contain $script:managedCollision
        Assert-MockCalled Invoke-AzureAssessmentResourceGraph -Times 1 -Exactly -ParameterFilter { $Subscriptions.Count -eq 2 }
        Assert-MockCalled Invoke-AzureAssessmentRest -Times 2 -Exactly
    }

    It 'queries every scope basis and window without admitting same-named groups in other subscriptions' {
        Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings | Out-Null
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        $rows = @(Get-Content -LiteralPath $result.outputs[0] | ConvertFrom-Json)
        $rows.Count | Should -Be 16
        @($rows | Where-Object { $_.ResourceId -like "$script:collision/*" -or $_.ResourceId -like "$script:managedCollision/*" }).Count | Should -Be 0
        $rows.ResourceId | Should -Contain "$script:managedA/providers/Microsoft.Compute/virtualMachines/worker"
        $rows.ResourceId | Should -Contain "$script:managedB/providers/Microsoft.Compute/virtualMachines/worker"
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 8 -Exactly
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 4 -Exactly -ParameterFilter { $Scope -eq "/subscriptions/$script:subA" }
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 4 -Exactly -ParameterFilter { $Scope -eq "/subscriptions/$script:subB" }
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 0 -Exactly -ParameterFilter { $Scope -eq '/subscriptions/legacy-ignored' }
        $audit = Get-Content -Raw -LiteralPath $result.outputs[1] | ConvertFrom-Json
        $audit.allowedResourceGroupIds.Count | Should -Be 4
        $audit.excludedRows | Should -Be 16
    }

    It 'applies legacy group names across selected subscriptions and supports a single legacy cost scope' {
        $script:config.azure.PSObject.Properties.Remove('resourceGroupIds')
        $script:config.azure.PSObject.Properties.Remove('costScopes')
        $script:config.azure.resourceGroups = @('shared')
        $script:config.azure.costScope = "/subscriptions/$script:subB"
        $inventoryResult = Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $resources = @(Get-Content -LiteralPath $inventoryResult.outputs[0] | ConvertFrom-Json)
        $resources.id | Should -Contain $script:workspaceA
        $resources.id | Should -Contain $script:workspaceCollision
        $resources.id | Should -Not -Contain $script:workspaceB
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        $rows = @(Get-Content -LiteralPath $result.outputs[0] | ConvertFrom-Json)
        $rows.Count | Should -Be 8
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 4 -Exactly -ParameterFilter { $Scope -eq "/subscriptions/$script:subB" }
    }

    It 'treats explicit empty group IDs as no group limit rather than using compatibility names' {
        $script:config.azure.resourceGroupIds = @()
        $script:config.azure.resourceGroups = @('not-selected')
        $inventoryResult = Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $inventoryResult.status | Should -Be 'passed'
        $resources = @(Get-Content -LiteralPath $inventoryResult.outputs[0] | ConvertFrom-Json)
        $resources.Count | Should -Be 12
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        $rows = @(Get-Content -LiteralPath $result.outputs[0] | ConvertFrom-Json)
        $rows.Count | Should -Be 24
    }

    It 'does not extend costs to managed groups of excluded configured workspaces' {
        $script:config | Add-Member databricks ([pscustomobject]@{ workspaces = @(
            [pscustomobject]@{ workspaceResourceId = $script:workspaceA; include = $true },
            [pscustomobject]@{ resourceId = $script:workspaceB; include = $false }
        ) })
        Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings | Out-Null
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        $audit = Get-Content -Raw -LiteralPath $result.outputs[1] | ConvertFrom-Json
        $audit.allowedResourceGroupIds | Should -Contain $script:managedA.ToLowerInvariant()
        $audit.allowedResourceGroupIds | Should -Not -Contain $script:managedB.ToLowerInvariant()
    }

    It 'never falls back to subscription costs when workspace inventory is <Inventory>' -TestCases @(
        @{ Inventory = 'missing' }, @{ Inventory = 'empty' }
    ) {
        param($Inventory)
        $script:config.azure.resourceGroupIds = @()
        if ($Inventory -eq 'empty') {
            Write-JsonFile -Value (, @()) -Path (Join-Path $script:context.Root 'raw\azure\databricks-workspaces.json')
        }
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'failed'
        $result.itemCount | Should -Be 0
        $result.error | Should -Match 'subscription-wide cost collection was not attempted'
        Test-Path -LiteralPath $result.outputs[0] | Should -BeTrue
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 0 -Exactly
    }

    It 'derives all subscription cost scopes when neither cost scope setting is supplied' {
        $script:config.azure.PSObject.Properties.Remove('costScope')
        $script:config.azure.PSObject.Properties.Remove('costScopes')
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 4 -Exactly -ParameterFilter { $Scope -eq "/subscriptions/$script:subA" }
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 4 -Exactly -ParameterFilter { $Scope -eq "/subscriptions/$script:subB" }
    }

    It 'retains managed group evidence from Resource Graph when ARM detail is unavailable' {
        Mock Invoke-AzureAssessmentRest { throw 'forbidden' }
        $inventoryResult = Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $inventoryResult.status | Should -Be 'partial'
        $inventoryResult.limitations.Count | Should -Be 2
        $resources = @(Get-Content -LiteralPath $inventoryResult.outputs[0] | ConvertFrom-Json)
        $resources.id | Should -Contain $script:managedA
        $resources.id | Should -Contain $script:managedB
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        $audit = Get-Content -Raw -LiteralPath $result.outputs[1] | ConvertFrom-Json
        $audit.allowedResourceGroupIds | Should -Contain $script:managedA.ToLowerInvariant()
        $audit.allowedResourceGroupIds | Should -Contain $script:managedB.ToLowerInvariant()
    }

    It 'keeps successful subscription costs and reports the failed scope explicitly' {
        Mock Get-AzureAssessmentCostPages { throw 'forbidden' } -ParameterFilter { $Scope -eq "/subscriptions/$script:subB" }
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'partial'
        $result.itemCount | Should -Be 4
        $result.limitations.Count | Should -Be 4
        $result.limitations[0] | Should -Match $script:subB
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 4 -Exactly -ParameterFilter { $Scope -eq "/subscriptions/$script:subA" }
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 4 -Exactly -ParameterFilter { $Scope -eq "/subscriptions/$script:subB" }
    }

    It 'rejects a qualified group outside the selected subscriptions before collection' {
        $script:config.azure.resourceGroupIds = @('/subscriptions/third/resourceGroups/shared')
        $result = Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'failed'
        $result.error | Should -Match 'outside the selected subscriptions'
        Assert-MockCalled Invoke-AzureAssessmentResourceGraph -Times 0 -Exactly
    }

    It 'does not rediscover workspaces or managed groups after an explicit empty workspace selection' {
        $script:config | Add-Member databricks ([pscustomobject]@{ workspaces = @() })
        $result = Invoke-AzureInventoryAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'passed'
        $resources = @(Get-Content -LiteralPath $result.outputs[0] | ConvertFrom-Json)
        $resources.id | Should -Not -Contain $script:managedA
        $resources.id | Should -Not -Contain $script:managedB
        @(Get-Content -Raw -LiteralPath $result.outputs[1] | ConvertFrom-Json).Count | Should -Be 0
        Assert-MockCalled Invoke-AzureAssessmentRest -Times 0 -Exactly
    }
}
