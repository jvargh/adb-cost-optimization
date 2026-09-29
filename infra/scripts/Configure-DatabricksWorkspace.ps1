[CmdletBinding()]
param(
    [string]$DeploymentOutputsPath = (Join-Path $PSScriptRoot '..\reports\deployment-outputs.json'),
    [string]$ExpectedSubscriptionId = '463a82d4-1896-4332-aeeb-618ee5a5aa93',
    [string]$CatalogName = 'main',
    [string]$SchemaName = 'adb_cost_workshop',
    [string]$ClassicNodeTypeId = 'Standard_D4s_v5'
)

. (Join-Path $PSScriptRoot 'Workshop.Common.ps1')

Assert-ExpectedSubscription -ExpectedSubscriptionId $ExpectedSubscriptionId | Out-Null
$outputs = Read-DeploymentOutputs -Path $DeploymentOutputsPath
$workspaceUrl = $outputs.workspaceUrl
$workspaceId = $outputs.workspaceId
$tags = @{
    environment      = 'workshop'
    workload_purpose = 'cost-optimization'
    cost_center      = 'Engineering'
    workshop_id      = 'L300'
    workload_owner   = 'Platform-Team'
}

Write-Host '[1/9] Validating workspace API connectivity and caller identity...'
Write-Host "Workspace: https://$workspaceUrl"
$currentUser = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.0/preview/scim/v2/Me'

Write-Host '[2/9] Resolving Unity Catalog and sample-catalog readiness...'
$catalogs = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.1/unity-catalog/catalogs?max_results=100'
if ('samples' -notin @($catalogs.catalogs.name)) {
    throw 'The samples catalog is unavailable. Unity Catalog/serverless prerequisites are not satisfied.'
}
$catalogAlreadyExists = $CatalogName -in @($catalogs.catalogs.name)
if (-not $catalogAlreadyExists -and $CatalogName -eq 'main') {
    $managedCatalog = @($catalogs.catalogs | Where-Object catalog_type -eq 'MANAGED_CATALOG' | Select-Object -First 1)
    if (-not $managedCatalog) {
        throw "Catalog '$CatalogName' is unavailable and the workspace has no managed catalog."
    }
    $CatalogName = $managedCatalog.name
    $catalogAlreadyExists = $true
    Write-Warning "Catalog 'main' is unavailable. Using workspace managed catalog '$CatalogName'."
}

Write-Host '[3/9] Evaluating optional workshop storage integration...'
$storagePublicNetworkAccess = az storage account show --ids $outputs.storageAccountId --query publicNetworkAccess --output tsv
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to inspect the workshop storage account network configuration.'
}

$externalLocationName = $null
if ($storagePublicNetworkAccess -eq 'Enabled') {
    $credentialName = 'adb_cost_workshop_credential'
    $credentials = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.1/unity-catalog/storage-credentials?max_results=100'
    if ($credentialName -notin @($credentials.storage_credentials.name)) {
        Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.1/unity-catalog/storage-credentials' -Body @{
            name = $credentialName
            azure_managed_identity = @{
                access_connector_id = $outputs.accessConnectorId
            }
            comment = 'Managed identity for workshop ADLS Gen2 data.'
            read_only = $false
        } | Out-Null
    }

    $externalLocationName = 'adb_cost_workshop_source'
    $externalLocations = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.1/unity-catalog/external-locations?max_results=100'
    if ($externalLocationName -notin @($externalLocations.external_locations.name)) {
        Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.1/unity-catalog/external-locations' -Body @{
            name            = $externalLocationName
            url             = "abfss://source@$($outputs.storageAccountName).dfs.core.windows.net/"
            credential_name = $credentialName
            comment         = 'Workshop source and export location.'
            read_only       = $false
        } | Out-Null
    }
}
else {
    Write-Warning "Storage public network access is '$storagePublicNetworkAccess'. Skipping the optional external location and using managed catalog storage."
}

Write-Host '[4/9] Selecting a bounded Classic runtime and node type...'
$sparkVersions = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.0/clusters/spark-versions'
$sparkVersion = @(
    $sparkVersions.versions |
        Where-Object { $_.name -match '\bLTS\b' -and $_.name -notmatch '\bML\b|GPU|aarch64|Photon' } |
        Select-Object -First 1
).key
if ([string]::IsNullOrWhiteSpace($sparkVersion)) {
    throw 'No long-term-support Databricks Runtime was returned by the workspace.'
}

$nodeTypes = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.0/clusters/list-node-types'
$preferredNodeTypes = @($ClassicNodeTypeId, 'Standard_D4s_v5', 'Standard_D4ds_v5', 'Standard_D4as_v5') | Select-Object -Unique
$nodeType = $preferredNodeTypes | Where-Object { $_ -in @($nodeTypes.node_types.node_type_id) } | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($nodeType)) {
    $nodeType = @($nodeTypes.node_types | Where-Object { $_.num_cores -ge 4 -and $_.num_cores -le 8 } | Sort-Object memory_mb | Select-Object -First 1).node_type_id
}
if ([string]::IsNullOrWhiteSpace($nodeType)) {
    throw 'No bounded Classic Compute node type is available.'
}
Write-Host "Selected Classic node type: $nodeType. Live Azure capacity is checked when the job starts."

$compatibleFallbacks = @{
    'Standard_D4s_v5' = @(
        'Standard_D4ads_v5',
        'Standard_D4as_v5',
        'Standard_D4ds_v5',
        'Standard_D4ds_v6',
        'Standard_D4ds_v4'
    )
    'Standard_D4ds_v5' = @(
        'Standard_D4ads_v5',
        'Standard_D4ds_v4'
    )
}
$availableNodeTypeIds = @($nodeTypes.node_types.node_type_id)
$alternateNodeTypeIds = if ($compatibleFallbacks.ContainsKey($nodeType)) {
    @($compatibleFallbacks[$nodeType] | Where-Object { $_ -in $availableNodeTypeIds } | Select-Object -First 5)
}
else {
    @()
}
Write-Host "Flexible node fallbacks: $(if ($alternateNodeTypeIds.Count) { $alternateNodeTypeIds -join ', ' } else { 'none' })"

$policyName = 'L300 Cost Optimization Workshop Policy'
Write-Host "[5/9] Creating or updating cluster policy (runtime=$sparkVersion, node=$nodeType)..."
$policies = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.0/policies/clusters/list'
$policy = @($policies.policies | Where-Object name -eq $policyName | Select-Object -First 1)
$policyDefinition = @{
    'autoscale.min_workers'   = @{ type = 'fixed'; value = 1; hidden = $false }
    'autoscale.max_workers'   = @{ type = 'fixed'; value = 2; hidden = $false }
    'spark_version'           = @{ type = 'fixed'; value = $sparkVersion; hidden = $false }
    'node_type_id'            = @{ type = 'fixed'; value = $nodeType; hidden = $false }
    'data_security_mode'      = @{ type = 'fixed'; value = 'USER_ISOLATION'; hidden = $false }
    'custom_tags.workshop_id'      = @{ type = 'fixed'; value = 'L300'; hidden = $false }
    'custom_tags.cost_center'      = @{ type = 'fixed'; value = 'Engineering'; hidden = $false }
    'custom_tags.workload_purpose' = @{ type = 'fixed'; value = 'cost-optimization'; hidden = $false }
}
$policyPayload = @{
    name       = $policyName
    definition = $policyDefinition | ConvertTo-Json -Depth 20 -Compress
}
if ($policy) {
    $policyPayload.policy_id = $policy.policy_id
    Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/policies/clusters/edit' -Body $policyPayload | Out-Null
    $policyId = $policy.policy_id
}
else {
    $createdPolicy = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/policies/clusters/create' -Body $policyPayload
    $policyId = $createdPolicy.policy_id
}

Write-Host '[6/9] Uploading workshop notebooks...'
$notebookRoot = '/Shared/adb-cost-workshop'
Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/workspace/mkdirs' -Body @{ path = $notebookRoot } | Out-Null
$notebookDirectory = Resolve-Path (Join-Path $PSScriptRoot '..\notebooks')
Get-ChildItem -LiteralPath $notebookDirectory -Filter '*.py' | ForEach-Object {
    $content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw -LiteralPath $_.FullName)))
    Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/workspace/import' -Body @{
        path      = "$notebookRoot/$($_.BaseName)"
        format    = 'SOURCE'
        language  = 'PYTHON'
        overwrite = $true
        content   = $content
    } | Out-Null
}

Write-Host '[7/9] Creating or locating bounded Classic interactive compute...'
$clusters = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.0/clusters/list'
$clusterName = 'l300-cost-workshop-interactive'
$clusterPropertyNames = @($clusters.PSObject.Properties | ForEach-Object Name)
$clusterList = if ($clusterPropertyNames -contains 'clusters') { @($clusters.clusters) } else { @() }
$interactiveCluster = @($clusterList | Where-Object cluster_name -eq $clusterName | Select-Object -First 1)
$clusterPayload = @{
    cluster_name             = $clusterName
    spark_version            = $sparkVersion
    node_type_id             = $nodeType
    policy_id                = $policyId
    autotermination_minutes  = 15
    autoscale                = @{ min_workers = 1; max_workers = 2 }
    data_security_mode       = 'USER_ISOLATION'
    runtime_engine           = 'PHOTON'
    custom_tags             = $tags
    worker_node_type_flexibility = @{ alternate_node_type_ids = $alternateNodeTypeIds }
    driver_node_type_flexibility = @{ alternate_node_type_ids = $alternateNodeTypeIds }
}
if ($interactiveCluster) {
    $clusterId = $interactiveCluster.cluster_id
    Write-Host "Preserving existing interactive cluster $clusterId in state $($interactiveCluster.state)."
}
else {
    $createdCluster = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/clusters/create' -Body $clusterPayload
    $clusterId = $createdCluster.cluster_id
}

function Set-WorkshopJob {
    param([string]$Name, [hashtable]$Settings)

    $jobs = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.2/jobs/list?limit=100&expand_tasks=true'
    $jobPropertyNames = @($jobs.PSObject.Properties | ForEach-Object Name)
    $jobList = if ($jobPropertyNames -contains 'jobs') { @($jobs.jobs) } else { @() }
    $existing = @($jobList | Where-Object { $_.settings.name -eq $Name } | Select-Object -First 1)
    $Settings.name = $Name
    if ($existing) {
        Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.2/jobs/reset' -Body @{
            job_id       = $existing.job_id
            new_settings = $Settings
        } | Out-Null
        return $existing.job_id
    }
    return (Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.2/jobs/create' -Body $Settings).job_id
}

$classicJobSettings = @{
    timeout_seconds = 7200
    max_concurrent_runs = 1
    tags = $tags
    job_clusters = @(
        @{
            job_cluster_key = 'bounded_classic'
            new_cluster = @{
                spark_version = $sparkVersion
                node_type_id = $nodeType
                autoscale = @{ min_workers = 1; max_workers = 2 }
                policy_id = $policyId
                data_security_mode = 'USER_ISOLATION'
                runtime_engine = 'PHOTON'
                custom_tags = $tags
                worker_node_type_flexibility = @{ alternate_node_type_ids = $alternateNodeTypeIds }
                driver_node_type_flexibility = @{ alternate_node_type_ids = $alternateNodeTypeIds }
            }
        }
    )
    tasks = @(
        @{
            task_key = 'classic_comparison'
            timeout_seconds = 2400
            max_retries = 0
            job_cluster_key = 'bounded_classic'
            notebook_task = @{
                notebook_path = "$notebookRoot/01_classic_baseline_optimized"
                source = 'WORKSPACE'
                base_parameters = @{ catalog = $CatalogName; schema = $SchemaName; shuffle_partitions = '32' }
            }
        },
        @{
            task_key = 'shuffle_skew_spill'
            depends_on = @(@{ task_key = 'classic_comparison' })
            timeout_seconds = 2400
            max_retries = 0
            job_cluster_key = 'bounded_classic'
            notebook_task = @{
                notebook_path = "$notebookRoot/03_shuffle_skew_spill"
                source = 'WORKSPACE'
                base_parameters = @{ catalog = $CatalogName; schema = $SchemaName; shuffle_partitions = '32' }
            }
        },
        @{
            task_key = 'udf_vs_native'
            depends_on = @(@{ task_key = 'shuffle_skew_spill' })
            timeout_seconds = 2400
            max_retries = 0
            job_cluster_key = 'bounded_classic'
            notebook_task = @{
                notebook_path = "$notebookRoot/04_udf_vs_native"
                source = 'WORKSPACE'
                base_parameters = @{ catalog = $CatalogName; schema = $SchemaName }
            }
        }
    )
}
Write-Host '[8/9] Creating or updating Classic and serverless jobs...'
$classicJobId = Set-WorkshopJob -Name 'l300-cost-workshop-classic' -Settings $classicJobSettings

$serverlessJobSettings = @{
    timeout_seconds = 1800
    max_concurrent_runs = 1
    tags = $tags
    environments = @(@{ environment_key = 'serverless'; spec = @{ client = '1' } })
    tasks = @(
        @{
            task_key = 'serverless_comparison'
            environment_key = 'serverless'
            timeout_seconds = 1200
            max_retries = 0
            notebook_task = @{
                notebook_path = "$notebookRoot/02_serverless_baseline_optimized"
                source = 'WORKSPACE'
                base_parameters = @{ catalog = $CatalogName; schema = $SchemaName }
            }
        },
        @{
            task_key = 'incremental_cdc'
            depends_on = @(@{ task_key = 'serverless_comparison' })
            environment_key = 'serverless'
            timeout_seconds = 1200
            max_retries = 0
            notebook_task = @{
                notebook_path = "$notebookRoot/05_full_vs_incremental_cdc"
                source = 'WORKSPACE'
                base_parameters = @{ catalog = $CatalogName; schema = $SchemaName; change_rows = '5000' }
            }
        },
        @{
            task_key = 'delta_maintenance'
            depends_on = @(@{ task_key = 'incremental_cdc' })
            environment_key = 'serverless'
            timeout_seconds = 1200
            max_retries = 0
            notebook_task = @{
                notebook_path = "$notebookRoot/06_delta_layout_maintenance"
                source = 'WORKSPACE'
                base_parameters = @{ catalog = $CatalogName; schema = $SchemaName }
            }
        }
    )
}
$serverlessJobId = Set-WorkshopJob -Name 'l300-cost-workshop-serverless' -Settings $serverlessJobSettings

Write-Host '[9/9] Creating or updating the serverless SQL Warehouse and workshop schema...'
$warehouses = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path '/api/2.0/sql/warehouses'
$warehouseName = 'l300-cost-workshop-serverless-sql'
$warehousePropertyNames = @($warehouses.PSObject.Properties | ForEach-Object Name)
$warehouseList = if ($warehousePropertyNames -contains 'warehouses') { @($warehouses.warehouses) } else { @() }
$warehouse = @($warehouseList | Where-Object name -eq $warehouseName | Select-Object -First 1)
$warehousePayload = @{
    name                      = $warehouseName
    cluster_size              = '2X-Small'
    min_num_clusters          = 1
    max_num_clusters          = 1
    auto_stop_mins            = 5
    enable_serverless_compute = $true
    warehouse_type            = 'PRO'
    tags                      = @{ custom_tags = @($tags.GetEnumerator() | ForEach-Object { @{ key = $_.Key; value = $_.Value } }) }
}
if ($warehouse) {
    Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path "/api/2.0/sql/warehouses/$($warehouse.id)/edit" -Body $warehousePayload | Out-Null
    $warehouseId = $warehouse.id
}
else {
    $createdWarehouse = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/sql/warehouses' -Body $warehousePayload
    $warehouseId = $createdWarehouse.id
}

function Invoke-ConfigurationSql {
    param([Parameter(Mandatory)][string]$Statement)

    $submission = Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/sql/statements' -Body @{
        warehouse_id = $warehouseId
        statement = $Statement
        wait_timeout = '0s'
        on_wait_timeout = 'CONTINUE'
        disposition = 'INLINE'
        format = 'JSON_ARRAY'
    }
    $result = Wait-DatabricksState `
        -Description "configuration SQL statement $($submission.statement_id)" `
        -TimeoutSeconds 1200 `
        -Probe { Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method GET -Path "/api/2.0/sql/statements/$($submission.statement_id)" } `
        -GetStatusText { param($value) $value.status.state } `
        -IsComplete { param($value) $value.status.state -in @('SUCCEEDED', 'FAILED', 'CANCELED', 'CLOSED') }
    if ($result.status.state -ne 'SUCCEEDED') {
        throw "Configuration SQL failed: $($result.status.error.message)"
    }
}

if (-not $catalogAlreadyExists) {
    Invoke-ConfigurationSql -Statement "CREATE CATALOG IF NOT EXISTS ``$CatalogName`` COMMENT 'Managed catalog for the L300 Azure Databricks cost optimization workshop'"
}
Invoke-ConfigurationSql -Statement "CREATE SCHEMA IF NOT EXISTS ``$CatalogName``.``$SchemaName`` COMMENT 'Repeatable datasets and workload outputs for cost optimization labs'"

$state = @{
    configuredAt       = (Get-Date).ToUniversalTime().ToString('o')
    workspaceId        = $workspaceId
    workspaceUrl       = $workspaceUrl
    currentUser        = $currentUser.userName
    catalogName        = $CatalogName
    schemaName         = $SchemaName
    externalLocation   = $externalLocationName
    storagePublicNetworkAccess = $storagePublicNetworkAccess
    sparkVersion       = $sparkVersion
    nodeTypeId         = $nodeType
    policyId           = $policyId
    interactiveClusterId = $clusterId
    classicJobId       = $classicJobId
    serverlessJobId    = $serverlessJobId
    sqlWarehouseId     = $warehouseId
}
Write-SanitizedJson -Value $state -Path (Join-Path $PSScriptRoot '..\reports\databricks-state.json')
Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path '/api/2.0/clusters/delete' -ExpectedStatusCodes @(200) -Body @{ cluster_id = $clusterId } | Out-Null
Invoke-DatabricksApi -WorkspaceUrl $workspaceUrl -Method POST -Path "/api/2.0/sql/warehouses/$warehouseId/stop" -ExpectedStatusCodes @(200) | Out-Null
Write-Host 'Databricks configuration completed. Classic cluster termination and SQL Warehouse stop were requested.'
