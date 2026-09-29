Describe 'Workshop workload controls' {
    BeforeAll {
        $infraRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    }

    It 'sets Classic and serverless job timeouts and zero retries' {
        $script = Get-Content -Raw (Join-Path $infraRoot 'scripts\Configure-DatabricksWorkspace.ps1')
        $script | Should -Match 'timeout_seconds = 1200'
        $script | Should -Match 'max_retries = 0'
        $script | Should -Match "environment_key = 'serverless'"
        $script | Should -Match 'worker_node_type_flexibility'
        $script | Should -Match 'driver_node_type_flexibility'
        $script | Should -Match 'alternate_node_type_ids'
    }

    It 'configures aggressive SQL Warehouse autostop' {
        $script = Get-Content -Raw (Join-Path $infraRoot 'scripts\Configure-DatabricksWorkspace.ps1')
        $script | Should -Match 'auto_stop_mins\s*=\s*5'
        $script | Should -Match 'max_num_clusters\s*=\s*1'
        $script | Should -Match 'enable_serverless_compute\s*=\s*\$true'
    }

    It 'guards deployment with explicit cost acknowledgement' {
        $script = Get-Content -Raw (Join-Path $infraRoot 'scripts\Deploy-WorkshopEnvironment.ps1')
        $script | Should -Match 'AcknowledgeCostRisk'
        $script | Should -Match 'deployment sub what-if'
        $script | Should -Match 'deployment sub create'
    }

    It 'guards teardown by subscription, name, tags, deployment ID, and explicit acknowledgement' {
        $script = Get-Content -Raw (Join-Path $infraRoot 'scripts\Remove-WorkshopEnvironment.ps1')
        $script | Should -Match 'ExpectedSubscriptionId'
        $script | Should -Match '\^rg-adb-cost-workshop-'
        $script | Should -Match 'Workshop'
        $script | Should -Match 'ExpectedDeploymentId'
        $script | Should -Match 'AcknowledgePermanentDeletion'
    }

    It 'prints polling progress and bounds every wait' {
        $common = Get-Content -Raw (Join-Path $infraRoot 'scripts\Workshop.Common.ps1')
        $common | Should -Match 'elapsed:'
        $common | Should -Match 'Timed out waiting'
        $common | Should -Match 'PollSeconds'
        $common | Should -Match 'status details are not available yet'
    }

    It 'fails fast after a recent Classic capacity stockout unless explicitly forced' {
        $script = Get-Content -Raw (Join-Path $infraRoot 'scripts\Invoke-WorkshopWorkloads.ps1')
        $script | Should -Match 'ForceClassicRetry'
        $script | Should -Match 'CLOUD_PROVIDER_RESOURCE_STOCKOUT'
        $script | Should -Match 'runs/cancel'
        $script | Should -Match "Properties.Name -contains 'result_state'"
        $script | Should -Match 'ClassicStartupTimeoutSeconds'
        $script | Should -Match 'did not start within'
    }
}
