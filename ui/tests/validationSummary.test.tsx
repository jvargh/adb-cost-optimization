import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ValidationSummary } from '@/features/validate/ValidatePage';
import type { ValidationCheck } from '@/types';

const WARNINGS: ValidationCheck[] = [
  {
    id: 'rbac-reader',
    title: 'One resource group may not be readable',
    severity: 'warning',
    status: 'warn',
    group: 'permissions',
    detail: 'The signed-in account cannot read rg-analytics-archive.',
    remediation: 'Give the account Reader access.',
  },
  {
    id: 'system-tables-access',
    title: 'Some Databricks system tables may not be available',
    severity: 'warning',
    status: 'warn',
    group: 'permissions',
    detail: 'The signed-in account may not be able to read system tables in every workspace.',
    remediation: 'Give the account SELECT access.',
  },
];

describe('validation summary', () => {
  it('shows every warning as a separate list item', () => {
    render(<ValidationSummary blockers={[]} warnings={WARNINGS} />);

    expect(screen.getByText('Ready to run — 2 warnings')).toBeInTheDocument();
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText('One resource group may not be readable')).toBeInTheDocument();
    expect(
      within(items[1]).getByText('Some Databricks system tables may not be available'),
    ).toBeInTheDocument();
    expect(screen.getAllByText('What to do:')).toHaveLength(2);
  });

  it('keeps grouped source responses available without repeating the action', async () => {
    const user = userEvent.setup();
    render(<ValidationSummary blockers={[]} warnings={[{
      ...WARNINGS[1],
      title: 'SQL-backed evidence was not checked',
      evidence: [
        { source: 'Databricks billing [one]', detail: 'A SQL Warehouse ID is required to read this source.' },
        { source: 'Databricks compute [two]', detail: 'A SQL Warehouse ID is required to read this source.' },
      ],
    }]} />);
    expect(screen.getByText('Ready to run — 1 warning')).toBeInTheDocument();
    expect(screen.getAllByText('What to do:')).toHaveLength(1);
    expect(screen.getByText('Databricks billing [one]')).not.toBeVisible();
    await user.click(screen.getByText('Source details (2)'));
    expect(screen.getByText('Databricks billing [one]')).toBeVisible();
    expect(screen.getByText('Databricks compute [two]')).toBeVisible();
  });
});
