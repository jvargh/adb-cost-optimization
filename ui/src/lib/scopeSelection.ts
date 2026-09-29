import type { AssessmentConfig, DiscoveredWarehouse, ResourceGroupOption, SubscriptionOption } from '@/types';

const WAREHOUSE_SIZES = ['2X-Small', 'X-Small', 'Small', 'Medium', 'Large', 'X-Large', '2X-Large', '3X-Large', '4X-Large'];

export function defaultWarehouse(warehouses: DiscoveredWarehouse[]): DiscoveredWarehouse | undefined {
  const eligible = warehouses.filter((warehouse) =>
    ['RUNNING', 'STOPPED'].includes(warehouse.state) && WAREHOUSE_SIZES.includes(warehouse.size),
  );
  return eligible.sort((left, right) =>
    Number(right.state === 'RUNNING') - Number(left.state === 'RUNNING')
    || WAREHOUSE_SIZES.indexOf(left.size) - WAREHOUSE_SIZES.indexOf(right.size)
    || left.name.localeCompare(right.name) || left.id.localeCompare(right.id),
  )[0];
}

export function applyWarehouseDefaults(config: AssessmentConfig, estate: SubscriptionOption[]): void {
  const discovered = estate.flatMap((sub) => sub.resourceGroups).flatMap((group) => group.workspaces);
  for (const workspace of config.databricks.workspaces) {
    if (!workspace.include || workspace.sqlWarehouseId !== undefined) continue;
    const metadata = discovered.find((item) => item.workspaceId === workspace.workspaceId);
    const warehouse = defaultWarehouse(metadata?.sqlWarehouses ?? []);
    if (warehouse) {
      workspace.sqlWarehouseId = warehouse.id;
      config.databricks.allowSqlWarehouseAutoStart = false;
    }
  }
}

export function warehouseScopeKey(config: AssessmentConfig): string {
  return config.databricks.workspaces.filter((workspace) => workspace.include && workspace.sqlWarehouseId)
    .map((workspace) => `${workspace.workspaceId}:${workspace.sqlWarehouseId}`).sort().join('|');
}

export const DEEP_DIVE_FIELDS = ['deepDiveJobRunIds', 'deepDiveTableNames'] as const;

export function migrateLegacyDeepDiveTargets(config: AssessmentConfig): void {
  const included = config.databricks.workspaces.filter((workspace) => workspace.include);
  if (included.length !== 1) return;
  for (const field of DEEP_DIVE_FIELDS) {
    if (!config.databricks[field].length) continue;
    included[0][field] ??= config.databricks[field].map(String);
    config.databricks[field] = [];
  }
}

export function assignLegacyDeepDiveTargets(config: AssessmentConfig, workspaceId: string): void {
  const workspace = config.databricks.workspaces.find((item) => item.include && item.workspaceId === workspaceId);
  if (!workspace) throw new Error('Select an included workspace before assigning legacy deep-dive targets.');
  for (const field of DEEP_DIVE_FIELDS) {
    workspace[field] = [...new Set([...(workspace[field] ?? []), ...config.databricks[field]].map(String))];
    config.databricks[field] = [];
  }
}

export function workspaceResourceGroupIds(subscriptions: SubscriptionOption[]): string[] {
  return subscriptions.flatMap((subscription) => subscription.resourceGroups)
    .filter((group) => group.workspaces.length > 0)
    .map((group) => group.resourceGroupId);
}

export function isResourceGroupSelected(config: AssessmentConfig, group: ResourceGroupOption): boolean {
  if (!config.azure.subscriptions.includes(group.subscriptionId)) return false;
  return config.azure.resourceGroupIds !== undefined
    ? config.azure.resourceGroupIds.some((id) => id.toLowerCase() === group.resourceGroupId.toLowerCase())
    : config.azure.resourceGroups.includes(group.name);
}

export function selectedResourceGroupIds(config: AssessmentConfig, estate: SubscriptionOption[]): string[] {
  return config.azure.resourceGroupIds !== undefined
    ? [...config.azure.resourceGroupIds]
    : estate.flatMap((sub) => sub.resourceGroups)
      .filter((group) => isResourceGroupSelected(config, group))
      .map((group) => group.resourceGroupId);
}

export function setSelectedResourceGroups(
  config: AssessmentConfig, estate: SubscriptionOption[], ids: string[],
): void {
  migrateLegacyDeepDiveTargets(config);
  const selected = new Set(ids.map((id) => id.toLowerCase()));
  const groups = estate.flatMap((sub) => sub.resourceGroups)
    .filter((group) => config.azure.subscriptions.includes(group.subscriptionId) && selected.has(group.resourceGroupId.toLowerCase()));
  // A legacy global warehouse belongs only to already configured workspaces.
  const globalWarehouseId = config.databricks.sqlWarehouseId;
  if (globalWarehouseId) {
    config.databricks.workspaces.forEach((workspace) => { workspace.sqlWarehouseId ??= globalWarehouseId; });
  }
  delete config.databricks.sqlWarehouseId;
  const previous = new Map(config.databricks.workspaces.map((workspace) => [workspace.workspaceId, workspace]));
  config.azure.resourceGroupIds = [...selected];
  config.azure.resourceGroups = [...new Set(ids.map((id) => id.slice(id.lastIndexOf('/') + 1)))];
  config.databricks.workspaces = groups.flatMap((group) => group.workspaces.map((workspace) => ({
    name: workspace.name,
    resourceGroup: workspace.resourceGroup,
    workspaceUrl: workspace.workspaceUrl,
    workspaceId: workspace.workspaceId,
    include: true,
    ...previous.get(workspace.workspaceId),
    subscriptionId: group.subscriptionId,
  })));
  applyWarehouseDefaults(config, estate);
}
