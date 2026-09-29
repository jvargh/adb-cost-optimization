BeforeAll {
    . (Join-Path $PSScriptRoot '..\scripts\Assessment.Common.ps1')
    . (Join-Path $PSScriptRoot '..\collectors\Azure.AssessmentCollectors.ps1')
}

Describe 'Applicable Azure governance checks' {
    It 'retains unsupported diagnostics as notes but keeps real failures partial' -ForEach @(
        @{ ErrorText = "The resource type 'microsoft.databricks/accessconnectors' does not support diagnostic settings."; Expected = 'passed' },
        @{ ErrorText = 'HTTP 403 AuthorizationFailed'; Expected = 'partial' }
    ) {
        $root = Join-Path $TestDrive ([guid]::NewGuid().ToString('N'))
        $raw = Join-Path $root 'raw\azure'
        New-Item -ItemType Directory -Path $raw -Force | Out-Null
        '{"id":"/subscriptions/s/resourceGroups/r/providers/Microsoft.Databricks/accessConnectors/c","type":"Microsoft.Databricks/accessConnectors"}' |
            Set-Content -LiteralPath (Join-Path $raw 'resource-inventory.ndjson')
        $script:failure = $ErrorText
        Mock Invoke-AzureAssessmentResourceGraph { @(@{ id = 'policy' }) }
        Mock Get-AzureAssessmentPagedValues { throw $script:failure }
        $result = Invoke-AzureGovernanceAssessmentCollector -Config ([pscustomobject]@{ azure = @{ subscriptions = @('s') } }) `
            -RunContext ([pscustomobject]@{ Root = $root }) -Settings @{}
        $result.status | Should -Be $Expected
        $result.itemCount | Should -Be 1
        $result.limitations.Count | Should -Be 1
        $result.limitations[0] | Should -Match ([regex]::Escape($ErrorText))
    }
}
