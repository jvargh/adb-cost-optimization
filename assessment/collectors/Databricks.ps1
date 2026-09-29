function Invoke-DatabricksAssessmentCollectors {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Config,
        [Parameter(Mandatory)][object]$RunContext
    )

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
