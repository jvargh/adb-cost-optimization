BeforeAll {
    $assessmentRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    . (Join-Path $assessmentRoot 'scripts\Assessment.Common.ps1')
    . (Join-Path $assessmentRoot 'collectors\Azure.AssessmentCollectors.ps1')
}

Describe 'Cost Management cooldowns' {
    BeforeEach {
        $script:costUri = 'https://management.azure.com/subscriptions/test/providers/Microsoft.CostManagement/query?api-version=2023-11-01'
        $script:AzureCostNextRequestUtc = [DateTimeOffset]::MinValue
        Mock Start-Sleep {}
        Mock Get-Random { 1 }
        Mock Invoke-AzureAssessmentCliJson { [pscustomobject]@{ accessToken = 'test-only' } }
    }

    It 'uses the largest cooldown across standard and Cost Management headers' {
        Get-AzureCostRetryAfter -Headers @{
            'Retry-After' = @('10')
            'x-ms-ratelimit-microsoft.costmanagement-qpu-retry-after' = @('75')
            'x-ms-ratelimit-microsoft.costmanagement-clienttype-retry-after' = @('120')
            'x-ms-ratelimit-microsoft.costmanagement-entity-retry-after' = @('90')
        } | Should -Be 120
    }

    It 'understands HTTP-date cooldowns and ignores invalid header values' {
        $delay = Get-AzureCostRetryAfter -Headers @{
            'Retry-After' = [DateTimeOffset]::UtcNow.AddSeconds(90).ToString('r')
            'x-ms-ratelimit-microsoft.costmanagement-entity-retry-after' = 'not-a-delay'
        }
        $delay | Should -BeGreaterThan 87
        $delay | Should -BeLessOrEqual 90
        Get-AzureCostRetryAfter -Headers @{ 'Retry-After' = '-5' } | Should -Be 0
    }

    It 'paces consecutive requests rather than bursting through pages' {
        Wait-AzureCostRequest
        Wait-AzureCostRequest
        Assert-MockCalled Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -ge 19 -and $Seconds -le 20 }
    }

    It 'honors server cooldown before retrying a throttled page with the same body' {
        $script:attempt = 0
        Mock Wait-AzureCostRequest {}
        Mock Invoke-WebRequest {
            $script:attempt++
            if ($script:attempt -eq 1) {
                return [pscustomobject]@{ StatusCode = 429; Content = '{"error":{"code":"429"}}'; Headers = @{ 'Retry-After' = '90' } }
            }
            [pscustomobject]@{ StatusCode = 200; Content = '{"properties":{"rows":[]}}'; Headers = @{} }
        }
        $result = Invoke-AzureAssessmentRest -Method POST -Uri $script:costUri -Body @{ type = 'ActualCost' }
        $result.properties.rows.Count | Should -Be 0
        Assert-MockCalled Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 91 }
        Assert-MockCalled Invoke-WebRequest -Times 2 -Exactly -ParameterFilter {
            $Method -eq 'POST' -and $Uri -eq $script:costUri -and
            ($Body | ConvertFrom-Json).type -eq 'ActualCost' -and
            $Headers.ClientType -eq 'AzureDatabricksCostAssessmentToolkit' -and $MaximumRedirection -eq 0
        }
    }

    It 'backs off 60 then 120 seconds when 429 contains no retry header' {
        Mock Wait-AzureCostRequest {}
        Mock Invoke-WebRequest { [pscustomobject]@{ StatusCode = 429; Content = 'throttled'; Headers = @{} } }
        { Invoke-AzureAssessmentRest -Method POST -Uri $script:costUri -Body @{} -RetryCount 2 } | Should -Throw '*429*'
        Assert-MockCalled Invoke-WebRequest -Times 3 -Exactly
        Assert-MockCalled Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 61 }
        Assert-MockCalled Start-Sleep -Times 1 -Exactly -ParameterFilter { $Seconds -eq 121 }
    }

    It 'does not retry permanent authorization errors' {
        Mock Invoke-WebRequest { [pscustomobject]@{ StatusCode = 403; Content = 'denied'; Headers = @{} } }
        { Invoke-AzureAssessmentRest -Method POST -Uri $script:costUri -Body @{} } | Should -Throw '*403*'
        Assert-MockCalled Invoke-WebRequest -Times 1 -Exactly
        Assert-MockCalled Start-Sleep -Times 0 -Exactly
    }

    It 'stops instead of shortening a server cooldown longer than ten minutes' {
        Mock Invoke-WebRequest { [pscustomobject]@{ StatusCode = 429; Content = 'throttled'; Headers = @{ 'Retry-After' = '900' } } }
        { Invoke-AzureAssessmentRest -Method POST -Uri $script:costUri -Body @{} } | Should -Throw '*900s cooldown*'
        Assert-MockCalled Invoke-WebRequest -Times 1 -Exactly
        Assert-MockCalled Start-Sleep -Times 0 -Exactly
    }

    It 'accepts a legitimate empty 204 response' {
        Mock Invoke-WebRequest { [pscustomobject]@{ StatusCode = 204; Content = ''; Headers = @{} } }
        Invoke-AzureAssessmentRest -Method POST -Uri $script:costUri -Body @{} | Should -BeNullOrEmpty
    }
}

Describe 'Cost readiness and exhausted throttling' {
    BeforeEach {
        $script:config = [pscustomobject]@{
            azure = [pscustomobject]@{
                subscriptions = @('sub'); resourceGroups = @('rg')
                costBasis = @('ActualCost', 'AmortizedCost')
            }
            analysis = [pscustomobject]@{ startUtc = '2026-01-01T00:00:00Z'; endUtc = '2026-03-01T00:00:00Z' }
        }
        $script:context = [pscustomobject]@{ Root = (Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))) }
        $script:settings = @{ MaxPages = 100; PageSize = 1000; RetryCount = 3; RetryBaseSeconds = 2 }
    }

    It 'probes only one aggregate day per scope during readiness and never full cost pages' {
        $script:context | Add-Member -NotePropertyName CostReadinessOnly -NotePropertyValue $true
        Mock Invoke-AzureAssessmentRest { [pscustomobject]@{ properties = @{ rows = @() } } }
        Mock Get-AzureAssessmentCostPages { throw 'Full query must not run' }
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'partial'
        $result.limitations | Should -Match 'full cost coverage is not validated'
        Test-Path -LiteralPath $result.outputs[0] | Should -BeTrue
        Assert-MockCalled Invoke-AzureAssessmentRest -Times 1 -Exactly -ParameterFilter {
            -not $Body.dataset.ContainsKey('grouping') -and
            ([DateTimeOffset]::Parse($Body.timePeriod.to) - [DateTimeOffset]::Parse($Body.timePeriod.from)).TotalDays -le 1
        }
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 0 -Exactly
    }

    It 'stops remaining windows and bases when throttling is exhausted, retaining earlier complete windows' {
        $script:windowCount = 0
        Mock Get-AzureAssessmentCostPages {
            $script:windowCount++
            if ($script:windowCount -eq 1) {
                return [pscustomobject]@{ ResourceId = '/subscriptions/sub/resourceGroups/rg/providers/test/resource'; PreTaxCost = 10; costBasis = $CostBasis }
            }
            $error = [InvalidOperationException]::new('Cost Management HTTP 429')
            $error.Data['StatusCode'] = 429
            throw $error
        }
        $result = Invoke-AzureCostAssessmentCollector -Config $script:config -RunContext $script:context -Settings $script:settings
        $result.status | Should -Be 'partial'
        $result.itemCount | Should -Be 1
        $result.limitations -join ';' | Should -Match 'Remaining cost windows'
        Assert-MockCalled Get-AzureAssessmentCostPages -Times 2 -Exactly
    }
}
