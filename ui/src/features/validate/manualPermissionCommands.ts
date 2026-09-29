import type { AssessmentConfig } from '@/types';
import type { PermissionSetup } from '@/api/backend';
import { hasValidDatabricksAccount } from '@/lib/validation';

export const VERIFY_PIPELINE_SQL = 'SELECT current_user() AS assessment_principal;\nSELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1;';

type ManualCommands = { error: string } | { sql: string; powershell?: string; adminIssue?: string };

export function manualPermissionCommands(job: PermissionSetup, account: AssessmentConfig['databricks']): ManualCommands {
  const principal = job.principal;
  if (!principal || principal.length > 256 || /[\u0000-\u001f\u007f]/.test(principal)) {
    return { error: 'Check access first to obtain a valid, verified assessment identity.' };
  }
  if (!/^adb-\d+\.\d+\.azuredatabricks\.(net|us)$/.test(job.workspaceUrl) || !/^\d+$/.test(job.workspaceId)) {
    return { error: 'The verified workspace target is invalid. Check the workspace configuration and access again.' };
  }
  const quoted = '`' + principal.replaceAll('`', '``') + '`';
  const sql = [
    `GRANT USE CATALOG ON CATALOG system TO ${quoted};`,
    `GRANT USE SCHEMA ON SCHEMA system.lakeflow TO ${quoted};`,
    `GRANT SELECT ON TABLE system.lakeflow.pipeline_update_timeline TO ${quoted};`,
  ].join('\n');
  if (!hasValidDatabricksAccount(account)) {
    return { sql, adminIssue: 'Configure a valid Databricks Account ID and Account host in Configure to populate the optional administrator command. These are not the Azure subscription ID or workspace host.' };
  }
  const powershell = `& {
    $ErrorActionPreference = 'Stop'
    $workspaceHost = '${job.workspaceUrl}'
    $expectedWorkspaceId = '${job.workspaceId}'
    $accountId = '${account.accountId}'
    $accountHost = '${(account.accountHost ?? '').toLowerCase()}'
    $principal = '${principal.replaceAll("'", "''")}'
    $token = az account get-access-token --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d --query accessToken --output tsv
    if ($LASTEXITCODE -ne 0 -or -not $token) { throw 'Azure CLI authentication failed. Sign in to the correct tenant first.' }
    $headers = @{ Authorization = "Bearer $token" }
    try {
        $me = Invoke-RestMethod -Uri "https://$workspaceHost/api/2.0/preview/scim/v2/Me" -Headers $headers -MaximumRedirection 0
        if ($me.userName -ne $principal) { throw 'The Azure CLI identity differs from the verified assessment identity. No changes made.' }
        $accountUser = Invoke-RestMethod -Uri "https://$accountHost/api/2.0/accounts/$accountId/scim/v2/Users/$($me.id)" -Headers $headers -MaximumRedirection 0
        if ($accountUser.userName -ne $principal -or 'account_admin' -notin @($accountUser.roles.value)) {
            throw 'The verified identity must be a Databricks Account Admin. Azure Owner or workspace admin is not sufficient.'
        }
        $assignment = Invoke-RestMethod -Uri "https://$workspaceHost/api/2.1/unity-catalog/current-metastore-assignment" -Headers $headers -MaximumRedirection 0
        if ([string]$assignment.workspace_id -ne $expectedWorkspaceId) { throw 'Workspace assignment does not match the selected target.' }
        $metastoreId = $assignment.metastore_id
        if ($metastoreId -notmatch '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$') { throw 'No valid metastore assignment was returned.' }
        $uri = "https://$accountHost/api/2.0/accounts/$accountId/metastores/$metastoreId"
        $metastore = (Invoke-RestMethod -Uri $uri -Headers $headers -MaximumRedirection 0).metastore_info
        if ($metastore.metastore_id -ne $metastoreId) { throw 'Account and workspace metastore details do not match.' }
        Write-Host "Workspace: $workspaceHost | Metastore: $($metastore.name) ($metastoreId) | Current owner: $($metastore.owner)"
        if ($metastore.owner -eq $principal) { Write-Host 'This identity is already the metastore administrator. No change needed.'; return }
        if ($metastore.owner -ne 'System user') { throw 'An administrator is already assigned, or ownership is unclear. Ask the existing administrator; this script will not replace them.' }
        Write-Warning "This grants $principal broad, persistent administrator privileges over ALL catalogs and attached workspaces in this metastore. It is NOT a table-only grant."
        $confirmation = Read-Host "Only if authorized, type the metastore ID $metastoreId to assign this identity as its administrator"
        if ($confirmation -cne $metastoreId) { throw 'Not confirmed. No changes made.' }
        $latest = (Invoke-RestMethod -Uri $uri -Headers $headers -MaximumRedirection 0).metastore_info
        if ($latest.owner -ne $metastore.owner) { throw 'Ownership changed while awaiting confirmation. No update submitted.' }
        $body = @{ metastore_info = @{ owner = $principal } } | ConvertTo-Json -Depth 3
        $null = Invoke-RestMethod -Method Put -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body -MaximumRedirection 0
        $verifiedOwner = (Invoke-RestMethod -Uri $uri -Headers $headers -MaximumRedirection 0).metastore_info.owner
        if ($verifiedOwner -ne $principal) { throw 'Assignment was submitted but not verified. Inspect the account console before retrying.' }
        Write-Host 'Administrator assignment verified. It remains assigned. Allow at least 30 seconds for role propagation before the SQL grants; some workspaces may take longer.'
    }
    finally {
        $headers.Clear()
        $token = $null
    }
}`;
  return { sql, powershell };
}
