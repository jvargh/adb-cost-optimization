Describe 'Workshop infrastructure' {
    BeforeAll {
        $infraRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    }

    It 'uses subscription scope for the isolated resource group' {
        (Get-Content -Raw (Join-Path $infraRoot 'main.bicep')) | Should -Match "targetScope = 'subscription'"
    }

    It 'pins the expected default subscription' {
        (Get-Content -Raw (Join-Path $infraRoot 'main.bicepparam')) | Should -Match '463a82d4-1896-4332-aeeb-618ee5a5aa93'
    }

    It 'uses Premium Databricks and secure cluster connectivity' {
        $content = Get-Content -Raw (Join-Path $infraRoot 'modules\databricks-workspace.bicep')
        $content | Should -Match "name: 'premium'"
        $content | Should -Match 'enableNoPublicIp'
        $content | Should -Match 'value: true'
    }

    It 'disables storage shared keys and anonymous blobs' {
        $content = Get-Content -Raw (Join-Path $infraRoot 'modules\storage.bicep')
        $content | Should -Match 'allowSharedKeyAccess: false'
        $content | Should -Match 'allowBlobPublicAccess: false'
        $content | Should -Match "minimumTlsVersion: 'TLS1_2'"
        $content | Should -Match 'isHnsEnabled: true'
    }

    It 'uses managed identity and scoped RBAC' {
        $content = Get-Content -Raw (Join-Path $infraRoot 'modules\identity-rbac.bicep')
        $content | Should -Match "type: 'SystemAssigned'"
        $content | Should -Match 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
        $content | Should -Match 'scope: storageAccount'
    }

    It 'does not reference existing Databricks workspace names' {
        $allBicep = Get-ChildItem $infraRoot -Filter '*.bicep' -Recurse | ForEach-Object { Get-Content -Raw $_.FullName }
        ($allBicep -join "`n") | Should -Not -Match 'databricks-serverless-ws|dbx-lab-test'
    }
}
