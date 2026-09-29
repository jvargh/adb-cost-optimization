import { describe, expect, it } from 'vitest';
import { validateConfiguration } from '@/lib/validation';
import type { AssessmentConfig, SubscriptionOption } from '@/types';
import type { RunApprovals } from '@/api/backend';
import defaultConfig from '../mock/fixtures/default-config.json';
import estate from '../mock/fixtures/estate.json';

const BASE_CONFIG = defaultConfig as unknown as AssessmentConfig;
const ESTATE = estate as unknown as SubscriptionOption[];

const APPROVED: RunApprovals = {
  approveSqlWarehouseAutoStart: true,
  continueOnCollectorError: true,
  acknowledgedReadOnly: true,
};

function withConfig(mutate: (draft: AssessmentConfig) => void): AssessmentConfig {
  const draft = JSON.parse(JSON.stringify(BASE_CONFIG)) as AssessmentConfig;
  mutate(draft);
  return draft;
}

function run(config: AssessmentConfig, approvals: RunApprovals = APPROVED) {
  return validateConfiguration({ config, approvals, estate: ESTATE, environmentChecks: [] });
}

function check(config: AssessmentConfig, id: string, approvals?: RunApprovals) {
  const report = run(config, approvals);
  const found = report.checks.find((c) => c.id === id);
  expect(found, `expected check '${id}' to be evaluated`).toBeDefined();
  return found!;
}

describe('configuration validation', () => {
  it('blocks ambiguous global deep-dive targets before checking multiple workspaces', () => {
    const config = withConfig((draft) => {
      draft.databricks.workspaces.push({ ...draft.databricks.workspaces[0], workspaceId: 'another', name: 'another' });
      draft.databricks.deepDiveJobRunIds = ['101'];
    });
    expect(check(config, 'deep-dive-targets')).toMatchObject({ status: 'fail', severity: 'blocker' });
    expect(run(config).canRun).toBe(false);
    config.databricks.deepDiveJobRunIds = [];
    config.databricks.deepDiveTableNames = ['catalog.schema.table'];
    expect(check(config, 'deep-dive-targets').status).toBe('fail');
    config.databricks.deepDiveTableNames = [];
    config.databricks.workspaces[0].deepDiveJobRunIds = ['101'];
    config.databricks.workspaces[0].deepDiveTableNames = ['catalog.schema.table'];
    expect(check(config, 'deep-dive-targets').status).toBe('pass');
  });

  it('honors empty workspace targets and validates numeric IDs without accepting URLs', () => {
    const config = withConfig((draft) => {
      draft.databricks.deepDiveJobRunIds = ['101'];
      draft.databricks.workspaces[0].deepDiveJobRunIds = [];
    });
    expect(check(config, 'deep-dive-targets').status).toBe('pass');
    config.databricks.workspaces[0].deepDiveJobRunIds = ['https://workspace/jobs/101'];
    expect(check(config, 'deep-dive-targets').status).toBe('fail');
  });

  it('validates optional account settings without treating configuration as verified access', () => {
    expect(check(BASE_CONFIG, 'databricks-account-config').status).toBe('skipped');
    const configured = withConfig((d) => {
      d.databricks.accountId = '00000000-0000-0000-0000-000000000000';
      d.databricks.accountHost = 'accounts.azuredatabricks.net';
    });
    expect(check(configured, 'databricks-account-config')).toMatchObject({
      status: 'pass', detail: 'Account settings are configured; live readiness still verifies access.',
    });
    configured.databricks.accountHost = 'accounts.azuredatabricks.net.example.com';
    expect(check(configured, 'databricks-account-config').status).toBe('fail');
    configured.databricks.accountHost = '';
    expect(check(configured, 'databricks-account-config').status).toBe('fail');
  });

  it('accepts the shipped default configuration once approvals are granted', () => {
    const report = run(BASE_CONFIG);
    expect(report.blockerCount).toBe(0);
    expect(report.canRun).toBe(true);
  });

  it.each(['', '   '])('reports both missing engagement IDs for %j', (value) => {
    const config = withConfig((d) => {
      d.customerId = value;
      d.assessmentId = value;
    });
    expect(check(config, 'customer-id').status).toBe('fail');
    expect(check(config, 'assessment-id').status).toBe('fail');
    expect(check(config, 'customer-id').remediation).toContain('Step 1: Configure');
    expect(run(config).canRun).toBe(false);
  });

  it('names both date inputs when the new-assessment window is blank', () => {
    const config = withConfig((d) => {
      d.analysis.startUtc = '';
      d.analysis.endUtc = '';
    });
    expect(check(config, 'analysis-window')).toMatchObject({
      status: 'fail',
      detail: 'Start (UTC) and End (UTC) must both contain valid dates.',
    });
  });

  it('blocks when no subscription is selected', () => {
    const config = withConfig((d) => {
      d.azure.subscriptions = [];
    });
    expect(check(config, 'subscription-selected').status).toBe('fail');
    expect(run(config).canRun).toBe(false);
  });

  it('blocks when no resource group is selected rather than widening to the subscription', () => {
    const config = withConfig((d) => {
      d.azure.resourceGroups = [];
    });
    const result = check(config, 'resource-group-selected');
    expect(result.status).toBe('fail');
    expect(result.detail).toMatch(/never broadens/i);
  });

  it('blocks a resource group that belongs to an unselected subscription', () => {
    const otherSub = ESTATE[1];
    const config = withConfig((d) => {
      d.azure.subscriptions = [ESTATE[0].subscriptionId];
      d.azure.resourceGroups = [otherSub.resourceGroups[0].name];
    });
    expect(check(config, 'scope-conflict').status).toBe('fail');
  });

  it('checks qualified resource groups against their owning subscriptions', () => {
    const config = withConfig((d) => {
      d.azure.subscriptions = [ESTATE[0].subscriptionId];
      d.azure.resourceGroups = [ESTATE[0].resourceGroups[0].name];
      d.azure.resourceGroupIds = [ESTATE[1].resourceGroups[0].resourceGroupId];
    });
    expect(check(config, 'scope-conflict').status).toBe('fail');
    config.azure.resourceGroupIds = [ESTATE[0].resourceGroups[0].resourceGroupId];
    expect(check(config, 'scope-conflict').status).toBe('pass');
  });

  it('treats an explicitly empty qualified selection as empty rather than restoring legacy names', () => {
    const config = withConfig((d) => { d.azure.resourceGroupIds = []; });
    expect(check(config, 'resource-group-selected').status).toBe('fail');
  });

  it('requires explicit approval before a SQL Warehouse can be auto-started', () => {
    const config = withConfig((d) => {
      d.databricks.allowSqlWarehouseAutoStart = false;
      d.databricks.workspaces.forEach((w) => {
        if (w.include) w.sqlWarehouseId = '19dfff78c4e639c4';
      });
    });
    const denied = run(config, { ...APPROVED, approveSqlWarehouseAutoStart: false });
    expect(denied.requiresSqlWarehouseApproval).toBe(true);
    expect(denied.canRun).toBe(false);

    const granted = run(config, APPROVED);
    expect(granted.requiresSqlWarehouseApproval).toBe(false);
    expect(granted.canRun).toBe(true);
  });

  it('skips the warehouse gate entirely when no warehouse is configured', () => {
    const config = withConfig((d) => {
      d.databricks.allowSqlWarehouseAutoStart = false;
      d.databricks.workspaces.forEach((w) => delete w.sqlWarehouseId);
    });
    const result = check(config, 'sql-warehouse-approval', {
      ...APPROVED,
      approveSqlWarehouseAutoStart: false,
    });
    expect(result.status).toBe('skipped');
  });

  it('does not add an artificial approval gate for the intrinsic read-only boundary', () => {
    const report = run(BASE_CONFIG, { ...APPROVED, acknowledgedReadOnly: false });
    expect(report.canRun).toBe(true);
    expect(report.checks.find((c) => c.id === 'read-only-scanner')?.status).toBe('pass');
  });

  it('rejects an inverted analysis window', () => {
    const config = withConfig((d) => {
      const start = d.analysis.startUtc;
      d.analysis.startUtc = d.analysis.endUtc;
      d.analysis.endUtc = start;
    });
    expect(check(config, 'analysis-window').status).toBe('fail');
  });

  it('warns, but does not block, on a very short window', () => {
    const config = withConfig((d) => {
      d.analysis.startUtc = '2026-09-20T00:00:00Z';
      d.analysis.endUtc = '2026-09-22T00:00:00Z';
    });
    const result = check(config, 'analysis-window');
    expect(result.status).toBe('warn');
    expect(run(config).canRun).toBe(true);
  });

  it('blocks when every output format is disabled', () => {
    const config = withConfig((d) => {
      d.outputs.writeMarkdown = false;
      d.outputs.writeCsv = false;
      d.outputs.writeJson = false;
    });
    expect(check(config, 'output-writable').status).toBe('fail');
  });

  it('warns when a selected resource group has a permission issue', () => {
    const blocked = ESTATE.flatMap((s) => s.resourceGroups).find((g) => g.permissionIssue);
    expect(blocked, 'fixture must contain a group with a permission issue').toBeDefined();
    const config = withConfig((d) => {
      if (!d.azure.subscriptions.includes(blocked!.subscriptionId)) {
        d.azure.subscriptions.push(blocked!.subscriptionId);
      }
      d.azure.resourceGroups.push(blocked!.name);
    });
    const result = check(config, 'resource-group-selected');
    expect(result.status).toBe('warn');
    expect(run(config).canRun).toBe(true);
  });
});
