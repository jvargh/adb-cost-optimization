Describe 'Workshop sample data assets' {
    BeforeAll {
        $notebookRoot = Join-Path $PSScriptRoot '..\notebooks'
        $sqlRoot = Join-Path $PSScriptRoot '..\sql'
    }

    It 'contains the required notebook scenarios' {
        $required = @(
            '00_setup_data.py',
            '01_classic_baseline_optimized.py',
            '02_serverless_baseline_optimized.py',
            '03_shuffle_skew_spill.py',
            '04_udf_vs_native.py',
            '05_full_vs_incremental_cdc.py',
            '06_delta_layout_maintenance.py'
        )
        foreach ($name in $required) {
            Test-Path (Join-Path $notebookRoot $name) | Should -BeTrue -Because "$name is required"
        }
    }

    It 'contains SQL setup, baseline, optimized, concurrency, and validation assets' {
        $required = @('00_setup.sql', '01_baseline_optimized.sql', '02_bounded_concurrency.sql', '03_validation.sql')
        foreach ($name in $required) {
            Test-Path (Join-Path $sqlRoot $name) | Should -BeTrue -Because "$name is required"
        }
    }

    It 'uses Databricks sample data and a dedicated workshop catalog' {
        $setup = Get-Content -Raw (Join-Path $notebookRoot '00_setup_data.py')
        $setup | Should -Match 'samples\.'
        $setup | Should -Match 'adb_cost_workshop'
    }
}
