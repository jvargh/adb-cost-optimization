Describe 'Workshop configuration safety' {
    BeforeAll {
        $infraRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    }

    It 'parses every JSON configuration file' {
        $files = @(Get-ChildItem (Join-Path $infraRoot 'config') -Filter '*.json')
        $files.Count | Should -BeGreaterThan 0
        foreach ($file in $files) {
            { Get-Content -Raw $file.FullName | ConvertFrom-Json -Depth 100 } | Should -Not -Throw
        }
    }

    It 'uses bounded Classic compute settings' {
        $config = Get-Content -Raw (Join-Path $infraRoot 'config\workshop.config.example.json') | ConvertFrom-Json
        $config.classic.autoterminationMinutes | Should -BeLessOrEqual 15
        $config.classic.maxWorkers | Should -BeLessOrEqual 2
        $config.classic.maxRetries | Should -Be 0
        $config.classic.timeoutSeconds | Should -BeLessOrEqual 1200
    }

    It 'uses a bounded serverless SQL Warehouse' {
        $config = Get-Content -Raw (Join-Path $infraRoot 'config\workshop.config.example.json') | ConvertFrom-Json
        $config.sqlWarehouse.enableServerlessCompute | Should -BeTrue
        $config.sqlWarehouse.maxClusters | Should -Be 1
        $config.sqlWarehouse.autoStopMinutes | Should -BeLessOrEqual 5
    }

    It 'contains no likely secret literals' {
        $files = Get-ChildItem $infraRoot -File -Recurse | Where-Object Extension -in @('.ps1', '.json', '.bicep', '.bicepparam', '.py', '.sql')
        foreach ($file in $files) {
            $content = Get-Content -Raw $file.FullName
            $content | Should -Not -Match '(?i)(client_secret|access_token|password)\s*[:=]\s*["''][^<][^"'']+'
        }
    }
}
