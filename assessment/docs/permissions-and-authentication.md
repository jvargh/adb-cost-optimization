# Permissions and authentication

Use one customer-controlled identity and grant access only at the configured scope. Permissions are cumulative: enable only the collector surfaces required for the engagement.

## Authentication

### Azure and workspace APIs

The implementation uses the active Azure CLI context:

```powershell
az login
az account set --subscription '<subscription-id>'
az account show
```

Azure ARM calls use `az rest`. Databricks workspace calls request a Microsoft Entra access token from:

```powershell
az account get-access-token `
  --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d `
  --query accessToken `
  --output tsv
```

The token is held in process memory, placed in the request authorization header, and cleared after the request. It is not written to the manifest or output files. Personal access tokens are not accepted by the current implementation.

### Databricks account APIs

When `databricks.accountId` and `databricks.accountHost` are configured, the same token acquisition helper is used against the account host. The identity must also be an account user with permission to view workspaces or budgets. Without both settings, those sources are `pending telemetry`.

These fields are available under **Databricks account settings** in Configure. Supply an account UUID and an accounts hostname without scheme or path. Account workspace inventory uses v2.0; budget inventory uses `GET /api/2.1/accounts/{accountId}/budgets`. Valid configuration alone does not establish account permissions.

### SQL Warehouse

System-table and metadata SQL uses a configured `databricks.sqlWarehouseId` or per-workspace `sqlWarehouseId`. The caller needs `CAN USE` on that warehouse. The UI selects the smallest running warehouse, otherwise the smallest stopped warehouse, only when no prior choice exists. Existing choices and explicit None are preserved. Listing/selection does not start compute. A SQL statement can auto-start an eligible stopped warehouse, so execution requires separate explicit warehouse approval in Validate.

### Separate confirmed pipeline timeline setup

Readiness and assessment collection never issue grants. The live UI provides an optional
**Pipeline timeline permission setup** action with its own security-change confirmation:

1. Approve SQL Warehouse use, then select **Check access and preview grants**.
   Both identity and access queries can incur DBU charges.
2. The tool verifies `current_user()` and executes a read-only
   `SELECT 1 FROM system.lakeflow.pipeline_update_timeline LIMIT 1`.
3. If access works, it shows **Already accessible - no grants needed**, even if there are
   no rows. No grants are offered or submitted. Read access does not require authority to grant it.
4. Only a confirmed permission denial offers the exact statements below for the verified
   identity. Confirm separately or cancel without granting. Other failures, such as a
   missing table or timeout, require diagnosis rather than an automatic grant recommendation.

```sql
GRANT USE CATALOG ON CATALOG system TO `<verified-assessment-identity>`;
GRANT USE SCHEMA ON SCHEMA system.lakeflow TO `<verified-assessment-identity>`;
GRANT SELECT ON TABLE system.lakeflow.pipeline_update_timeline TO `<verified-assessment-identity>`;
```

These are not automatic grants or instructions to grant to the literal placeholder above.
Only the current identity is eligible. Its existing Unity Catalog authority must allow the
grants; otherwise ask an authorized administrator. The tool does not acquire administrator
credentials, elevate roles, or grant broader privileges. Grants are metastore-scoped and can
affect other workspaces sharing that metastore.

Previews expire after five minutes. Apply checks identity again before granting; an identity
change aborts. Statements are submitted once, and execution stops at the first failure.
Earlier grants are not rolled back or retried automatically. A read-only SELECT must succeed
before access is reported verified. Re-run validation explicitly afterward; other evidence
gaps, retention limits, and detailed Spark metrics are not resolved by these grants.

Use **Check setup status** if a response is lost. After restart, saved terminal results can
be read from audits without resubmitting SQL. Unused previews are invalidated, while an
interrupted application with submitted steps is explicitly unknown. Inspect actual permissions and the output root's
`.ui-server/permission-setup/<setupId>.json` before dismissing an unknown outcome or retrying.
Audits contain principal, target, exact SQL, and step outcomes but no tokens; protect them
as security-sensitive operational records.

`PERMISSION_DENIED` / missing `MANAGE` on `system` means the current identity lacks the
authority for that grant. A username containing "admin", workspace access, or Azure
subscription administration does not establish Unity Catalog grant authority. Ask an
authorized Unity Catalog administrator to apply the exact required access; do not broaden
the assessment identity's administrative privileges merely to make this setup action pass.
An explicitly rejected statement is **failed**, not indefinitely "submitted"; later grants
are not attempted. Unknown transport outcomes remain distinct and require inspection.

### Manual repair commands in the UI

Expand **Manual permission repair commands** under pipeline timeline setup after checking
the selected workspace. It supplies copyable SQL grants for the verified assessment identity
and a verification query. Run grants in that workspace's SQL Editor as an authorized
administrator, then verify as the assessment identity; a successful administrator query
does not verify a different recipient's access.

The optional **resolve missing MANAGE with an Account Admin** section includes the
PowerShell 7/Azure CLI method used for an account-managed metastore administrator assignment.
It discovers the selected workspace's current metastore instead of hardcoding a previous
customer's ID. Valid Databricks Account ID and Account host settings are required. The
script checks that the Azure CLI identity matches the verified identity and has the
Databricks `account_admin` role. It only offers to replace `System user`, displays the
metastore/owner, and requires typing its ID before one account-level PUT with the nested
`metastore_info.owner` body. It verifies ownership afterward, never automatically retries,
and keeps the access token in memory.

This optional assignment is **broad and persistent**, applying to all catalogs and
workspaces attached to that metastore. Prefer an existing authorized administrator to
grant read access, or a designated administrator group for ongoing administration. It
is not a required permission for assessment collection. Opening or copying this guide
does not execute commands, alter permissions, or start validation. Active/unknown work
and non-permission failures must be resolved first. After manual repair, use **Check access
and preview grants**, then explicitly re-run validation. Green pipeline access alone does
not establish full readiness; **Continue to run** opens the separate assessment start step.

## Exact Azure permission matrix

The following matrix reflects calls made by the current collectors. Built-in roles are deployment guidance; custom roles can grant the listed read actions more narrowly.

| Collector/source | ARM operation or data action | Recommended least built-in role and scope | If absent |
| --- | --- | --- | --- |
| Resource Graph inventory and policy query | Resource Graph `resources` query across selected subscriptions; reads resources, resource groups, subscriptions, and policy resources | **Reader** on each included subscription; add **Policy Reader** if the organization's policy visibility requires it | Inventory or policy source is partial/failed. |
| Workspace ARM details | `Microsoft.Databricks/workspaces/read` | **Reader** on included workspace/resource group/subscription | Workspace detail limitation. |
| Managed resource inventory | Resource Graph reads against managed resource groups discovered from workspace ARM data | **Reader** on the workspace-managed resource group or containing subscription | Managed resources are incomplete. |
| Diagnostic settings | `Microsoft.Insights/diagnosticSettings/read` on every observed resource | **Monitoring Reader** or a custom role with that action at the included resource groups | Permission failures remain partial. Explicitly unsupported resource types are retained as not-applicable notes and do not by themselves fail applicable checks. |
| Cost query | `Microsoft.CostManagement/query/read` at `azure.costScope` for Actual/Amortized queries | **Cost Management Reader** at the exact cost scope | Azure Cost Management is failed if no cost basis succeeds, otherwise partial. |
| Azure budgets | `Microsoft.Consumption/budgets/read` on each included subscription | **Cost Management Reader** at subscription | Budget limitation. |
| Reservation orders | `Microsoft.Capacity/reservationOrders/read` at tenant/billing context | **Reservations Reader** or organization-approved equivalent at the applicable reservation scope | Reservation limitation. |
| Savings Plans | `Microsoft.BillingBenefits/savingsPlans/read` at tenant/billing context | **Savings plan reader** or organization-approved equivalent at the applicable billing scope | Savings Plan limitation. |
| Compute quotas | `Microsoft.Compute/locations/usages/read` by included subscription and observed region | **Reader** on included subscription | Quota limitation. |

Do not grant Contributor, Owner, User Access Administrator, or any mutation action for assessment collection.

## Exact Databricks permission matrix

Databricks list APIs return only objects visible to the caller unless the identity has broader administrative visibility. A successful call therefore proves visibility of returned objects, not completeness of the estate.

| Source/API | Required access | Notes |
| --- | --- | --- |
| Configured workspace scope | Workspace access only | One record is built from the scope file; it is not discovered. |
| Account workspaces `GET /api/2.0/accounts/{accountId}/workspaces` | Databricks account user with account workspace-view permission | Requires `accountId` and `accountHost`. |
| Workspace configuration `GET /api/2.0/workspace-conf` | Workspace admin or delegated configuration read visibility | Reads only `enableIpAccessLists` and `enableTokensConfig`. |
| Current metastore assignment | Workspace access with metastore assignment visibility | Missing access is partial. |
| IP access lists | Workspace admin or delegated IP access-list read visibility | Empty list and permission failure are distinct in source status. |
| SCIM groups | Workspace admin or SCIM group-read entitlement | Called only when `includeIdentities` is true; identities are hashed by default. |
| Clusters and events | Permission to view each cluster; broader completeness normally requires workspace admin | Cluster events use a read-only POST and do not start clusters. |
| Cluster policies and permissions | Permission to view policies and their ACLs; broader completeness normally requires workspace admin | ACL errors are retained as partial. |
| Instance pools | Permission to view pools; broader completeness normally requires workspace admin | No pool record does not prove no inaccessible pool exists. |
| Jobs/runs and pipelines/events | `CAN VIEW` (or stronger) on in-scope objects; broader completeness normally requires workspace admin | No job or pipeline is run by the collector. |
| SQL Warehouses list | Permission to view in-scope warehouses | Listing does not start a warehouse. |
| SQL Statements API | `CAN USE` on the configured warehouse | May auto-start the warehouse. Only guarded read-only SQL assets are submitted. |
| Unity Catalog catalogs/schemas/tables | `BROWSE` or metadata visibility on in-scope securables; `READ METADATA` is required for workspace binding reads where enforced | Binding calls are skipped only for catalogs explicitly marked OPEN. ISOLATED and unknown modes still require the binding read; failures remain partial. |
| `system.billing.*` | `USE CATALOG` on `system`, `USE SCHEMA` and `SELECT` on `system.billing` tables | Also requires configured SQL warehouse access. |
| `system.compute.node_timeline` | `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the table | Account/system-table availability and retention still apply. |
| `system.lakeflow.*` | `USE CATALOG`, `USE SCHEMA`, and `SELECT` on selected tables | Jobs, run timeline, and pipeline timeline are separate sources. |
| `system.query.history` | `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the table | Query text is omitted by default after collection. |
| `system.access.audit` | `USE CATALOG`, `USE SCHEMA`, and `SELECT` on the table | Audit table availability and retention apply. |
| `system.information_schema.tables` | `USE CATALOG`, `USE SCHEMA`, and `SELECT`/metadata visibility for returned objects | Used for table metadata inventory. |
| Selected `DESCRIBE DETAIL/HISTORY` | `USE CATALOG`, `USE SCHEMA`, and `SELECT`/metadata access on each approved table | Runs only for `deepDiveTableNames`. |
| Databricks account budgets | Account user with budget-view permission | Requires account host and account ID. |

Missing `SELECT` on `system.lakeflow.pipeline_update_timeline` remains a workloads warning.
Use the separately confirmed setup above if the signed-in identity already has the required
grant authority; otherwise an authorized administrator must arrange those privileges.
An empty current pipeline list is not proof that historical evidence is irrelevant.
For job-run deep dives, detailed Spark stage/task/executor metrics require separate Spark UI
or event-log review; the collector only reads run metadata and cluster events, and the app
does not provide an event-log importer.

## Pre-run verification

```powershell
az account show --output table
az account get-access-token --resource 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d --query expiresOn --output tsv

.\assessment\scripts\Test-AssessmentReadOnly.ps1 -Path .\assessment
```

Use a short `-SkipAnalysis -ContinueOnCollectorError` run to test real access. Review source statuses instead of assuming that authentication success implies authorization or complete visibility.
