function Invoke-DatabricksAssessmentCollectors {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

    $options = Get-DatabricksProperty -InputObject $Config -Name 'capabilities' -Default ([pscustomobject]@{})
    $concurrency = [int](Get-DatabricksProperty -InputObject $options -Name 'concurrency' -Default 1)
    if ($concurrency -lt 1 -or $concurrency -gt 4) { throw 'Collector concurrency must be between 1 and 4.' }
    if ($concurrency -gt 1) {
        $collectorRoot = $PSScriptRoot
        $common = Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\Assessment.Common.ps1'
        return @(Get-AssessmentCollectorPlan | Where-Object domain -eq 'Databricks' | ForEach-Object -Parallel {
            . $using:common
            Get-ChildItem -LiteralPath $using:collectorRoot -Filter '*.ps1' | Sort-Object Name | ForEach-Object { . $_.FullName }
            $check = $_
            Write-AssessmentProgress -Event @{ id = $check.id; status = 'running'; detail = 'Reading selected workspace evidence with bounded concurrency.' }
            try {
                $results = @(& $check.command -Config $using:Config -RunContext $using:RunContext)
            }
            catch {
                $results = @(New-CollectorResult -Name $check.command -Status failed -StartedAt (Get-Date) -ErrorMessage $_.Exception.Message)
            }
            Write-AssessmentCollectorProgress -Id $check.id -Results $results
            $results
        } -ThrottleLimit $concurrency)
    }
    $results = [Collections.Generic.List[object]]::new()
    foreach ($check in @(Get-AssessmentCollectorPlan | Where-Object domain -eq 'Databricks')) {
        $commandName = $check.command
        Write-AssessmentProgress -Event @{ id = $check.id; status = 'running'; detail = "Checking $($check.title) across selected workspaces." }
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($null -eq $command) {
            $missing = New-CollectorResult -Name $commandName -Status failed -StartedAt (Get-Date) -ErrorMessage "Collector function '$commandName' is unavailable."
            $results.Add($missing)
            Write-AssessmentCollectorProgress -Id $check.id -Results @($missing)
            continue
        }
        $sourceResults = [Collections.Generic.List[object]]::new()
        try {
            foreach ($result in @(& $command -Config $Config -RunContext $RunContext)) {
                if ($null -ne $result) {
                    $results.Add($result)
                    $sourceResults.Add($result)
                }
            }
        }
        catch {
            $failure = New-CollectorResult -Name $commandName -Status failed -StartedAt (Get-Date) -ErrorMessage $_.Exception.Message
            $results.Add($failure)
            $sourceResults.Add($failure)
        }
        Write-AssessmentCollectorProgress -Id $check.id -Results $sourceResults.ToArray()
    }

    return $results.ToArray()
}
