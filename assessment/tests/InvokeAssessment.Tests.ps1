Describe 'Simplified assessment entry point' {
    BeforeAll {
        $assessmentRoot = Split-Path -Parent $PSScriptRoot
        $entryPoint = Join-Path $assessmentRoot 'Invoke-Assessment.ps1'
    }

    It 'exists with all documented actions' {
        Test-Path -LiteralPath $entryPoint | Should -BeTrue
        $content = Get-Content -Raw -LiteralPath $entryPoint
        foreach ($action in @('Initialize', 'Run', 'Readiness', 'Reports', 'Open', 'Validate')) {
            $content | Should -Match ([regex]::Escape("'$action'"))
        }
    }

    It 'requires explicit SQL Warehouse auto-start approval' {
        $content = Get-Content -Raw -LiteralPath $entryPoint
        $content | Should -Match 'ApproveSqlWarehouseAutoStart'
        $content | Should -Match 'allowSqlWarehouseAutoStart'
        $content | Should -Match 'approval is recorded in the selected scope'
    }

    It 'removes SQL Warehouse IDs for readiness unless explicitly approved' {
        $content = Get-Content -Raw -LiteralPath $entryPoint
        $content | Should -Match 'New-ReadinessConfig'
        $content | Should -Match ([regex]::Escape("PSObject.Properties.Remove('sqlWarehouseId')"))
        $content | Should -Match 'no Warehouse auto-start is requested'
        $content | Should -Match 'ApproveSqlWarehouseAutoStart.IsPresent'
    }

    It 'uses the documented config precedence' {
        $content = Get-Content -Raw -LiteralPath $entryPoint
        $localIndex = $content.IndexOf('Test-Path -LiteralPath $localConfig')
        $workshopIndex = $content.IndexOf('Test-Path -LiteralPath $workshopConfig')
        $localIndex | Should -BeGreaterThan -1
        $workshopIndex | Should -BeGreaterThan $localIndex
    }

    It 'supports report recreation without collector invocation' {
        $content = Get-Content -Raw -LiteralPath $entryPoint
        $reportsStart = $content.IndexOf("'Reports' {")
        $openStart = $content.IndexOf("'Open' {", $reportsStart + 1)
        $reportsStart | Should -BeGreaterThan -1
        $openStart | Should -BeGreaterThan $reportsStart
        $reportsBlock = $content.Substring($reportsStart, $openStart - $reportsStart)
        $reportsBlock | Should -Match ([regex]::Escape('python $pipeline'))
        $reportsBlock | Should -Not -Match 'Collect-CostOptimizationAssessment'
    }

    It 'documents the front-door command in the user guide' {
        $guide = Get-Content -Raw -LiteralPath (Join-Path $assessmentRoot 'USER-GUIDE.md')
        $guide | Should -Match 'Invoke-Assessment\.ps1'
        $guide | Should -Match 'Action Reports'
        $guide | Should -Match 'Action Open'
        $guide | Should -Match 'run one command'
    }

    It 'opens one consolidated report by default' {
        $content = Get-Content -Raw -LiteralPath $entryPoint
        $content | Should -Match 'assessment-report\.md'
        $content | Should -Match 'NoOpenReport'
        $content | Should -Match ([regex]::Escape('-not $NoOpenReport'))
    }

    It 'resolves relative run roots from the invocation or assessment directory' {
        $content = Get-Content -Raw -LiteralPath $entryPoint
        $content | Should -Match 'Resolve-AssessmentRunRoot'
        $content | Should -Match 'invocationDirectory'
        $content | Should -Match 'fromAssessmentDirectory'
    }
}
