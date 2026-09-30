import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ExportPage } from '@/features/export/ExportPage';
import { getBackend, setBackend } from '@/api';
import { useResultsStore } from '@/state';
import type { AssessmentResults } from '@/types';
import fixture from '../mock/fixtures/contoso-clean.results.json';

const reportPath = 'reports/assessment-report.md';
const sourcePath = 'reports/support.csv';
const markdown = `# Assessment report

## Contents

1. [Governance](#11-governance,-policies,-budgets,-and-finops)

## 11. Governance, policies, budgets, and FinOps

**Observed** evidence, not assumed savings.

| Source | Status |
| --- | --- |
| Jobs | Partial |

\`\`\`sql
SELECT 1;
\`\`\`

[Supporting data](support.csv)

[Documentation](https://learn.microsoft.com/)
`;
const payload = (content = markdown) => ({ relativePath: reportPath, mimeType: 'text/markdown', content });
const scroll = vi.fn();
const originalScroll = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollIntoView');

function pendingRead() {
  let resolve!: (value: ReturnType<typeof payload>) => void;
  const promise = new Promise<ReturnType<typeof payload>>(done => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => {
  setBackend(null);
  useResultsStore.getState().clear();
  const results = structuredClone(fixture) as AssessmentResults;
  results.exports.push({ name: 'Supporting data', relativePath: sourcePath, kind: 'csv',
    description: 'Supporting report evidence', sensitivity: 'redacted', sizeBytes: 20 });
  useResultsStore.setState({ runId: results.manifest.runId, results });
  scroll.mockClear();
  Object.defineProperty(Element.prototype, 'scrollIntoView', { value: scroll, configurable: true });
});
afterEach(() => {
  vi.restoreAllMocks();
  if (originalScroll) Object.defineProperty(Element.prototype, 'scrollIntoView', originalScroll);
  else Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
});

describe('report preview', () => {
  it('immediately focuses and scrolls to loading, then renders a report with headings, tables and code', async () => {
    const pending = pendingRead();
    vi.spyOn(getBackend(), 'readArtifact').mockReturnValue(pending.promise);
    render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    expect(screen.getByRole('status')).toHaveTextContent('Loading preview');
    const region = screen.getByRole('region', { name: 'Artifact preview' });
    expect(region).toHaveFocus();
    expect(scroll).toHaveBeenLastCalledWith({ block: 'start' });
    await act(async () => pending.resolve(payload()));
    expect(screen.getByRole('heading', { level: 1, name: 'Assessment report' })).toBeVisible();
    expect(screen.getByRole('cell', { name: 'Partial' })).toBeVisible();
    expect(screen.getByText('SELECT 1;').tagName).toBe('CODE');
    expect(screen.getByText('Observed').tagName).toBe('STRONG');
    expect(region).toHaveFocus();
    expect(useResultsStore.getState().exportedArtifactPaths).toEqual([]);
  });

  it('navigates a contents link with legacy punctuation without changing the app URL', async () => {
    vi.spyOn(getBackend(), 'readArtifact').mockResolvedValue(payload());
    render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    const link = await screen.findByRole('link', { name: 'Governance' });
    const url = window.location.href;
    fireEvent.click(link);
    expect(screen.getByRole('heading', { level: 2, name: '11. Governance, policies, budgets, and FinOps' })).toHaveFocus();
    expect(window.location.href).toBe(url);
    expect(scroll).toHaveBeenLastCalledWith({ block: 'start' });
    expect(screen.getByRole('link', { name: 'Documentation' })).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('scrolls again when the same report is previewed again, including from its artifact row', async () => {
    const read = vi.spyOn(getBackend(), 'readArtifact').mockResolvedValue(payload());
    render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    await screen.findByRole('heading', { name: 'Assessment report' });
    scroll.mockClear();
    fireEvent.click(within(screen.getByText(reportPath, { selector: '.truncate' }).closest('tr')!).getByRole('button', { name: 'Preview' }));
    await screen.findByRole('heading', { name: 'Assessment report' });
    expect(read).toHaveBeenCalledTimes(2);
    expect(scroll).toHaveBeenCalled();
    expect(screen.getByRole('region', { name: 'Artifact preview' })).toHaveFocus();
  });

  it('resolves older shortened contents labels to the actual numbered report headings', async () => {
    vi.spyOn(getBackend(), 'readArtifact').mockResolvedValue(payload(`# Report

1. [SQL Warehouse and query](#7-sql-warehouse-and-query)
2. [Prioritized backlog](#14-prioritized-backlog)

## 7. SQL Warehouse and query assessment

## 14. Prioritized optimization backlog
`));
    render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    const query = await screen.findByRole('link', { name: 'SQL Warehouse and query' });
    expect(query).toHaveAttribute('href', '#report-7-sql-warehouse-and-query-assessment');
    fireEvent.click(query);
    expect(screen.getByRole('heading', { name: '7. SQL Warehouse and query assessment' })).toHaveFocus();
    fireEvent.click(screen.getByRole('link', { name: 'Prioritized backlog' }));
    expect(screen.getByRole('heading', { name: '14. Prioritized optimization backlog' })).toHaveFocus();
  });

  it('opens relative supporting artifacts locally and preserves plain-text previews', async () => {
    const read = vi.spyOn(getBackend(), 'readArtifact').mockResolvedValueOnce(payload()).mockResolvedValueOnce({
      relativePath: sourcePath, mimeType: 'text/csv', content: 'source,status\nJobs,Partial',
    });
    render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Supporting data' }));
    expect(await screen.findByText('source,status Jobs,Partial')).toHaveClass('markdown-preview');
    expect(read).toHaveBeenLastCalledWith(useResultsStore.getState().runId, sourcePath);
    expect(screen.queryByRole('article', { name: 'Rendered report' })).not.toBeInTheDocument();
  });

  it('does not execute HTML, load remote images or enable unsafe URLs', async () => {
    vi.spyOn(getBackend(), 'readArtifact').mockResolvedValue(payload(`# Safe report

<script>alert('unsafe')</script>

<iframe src="https://example.com/track"></iframe>

![Tracker](https://example.com/track.png)

[Unsafe](javascript:alert%281%29)

[Broken](//%zz)
`));
    const { container } = render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    await screen.findByRole('heading', { name: 'Safe report' });
    expect(container.querySelector('script, iframe, img')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Unsafe' })).not.toBeInTheDocument();
    expect(screen.getByText('[Image omitted: Tracker]')).toBeVisible();
    expect(screen.getByText(/invalid artifact link/)).toBeVisible();
  });

  it('shows read failures inside the focused preview and allows retry', async () => {
    vi.spyOn(getBackend(), 'readArtifact').mockRejectedValueOnce(new Error('Report unavailable')).mockResolvedValueOnce(payload());
    render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    await screen.findByText('Report unavailable');
    expect(screen.getByRole('region', { name: 'Artifact preview' })).toHaveFocus();
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    await screen.findByRole('heading', { name: 'Assessment report' });
    expect(screen.queryByText('Preview failed')).not.toBeInTheDocument();
  });

  it.each(['closed', 'superseded', 'different snapshot'] as const)('ignores a late response when %s', async (change) => {
    const pending = pendingRead();
    vi.spyOn(getBackend(), 'readArtifact').mockReturnValueOnce(pending.promise).mockResolvedValueOnce(payload('# Latest report'));
    render(<ExportPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
    if (change === 'closed') fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    else if (change === 'superseded') {
      fireEvent.click(screen.getByRole('button', { name: 'Preview report' }));
      await screen.findByRole('heading', { name: 'Latest report' });
    } else {
      act(() => useResultsStore.setState({ runId: 'another-run' }));
      await waitFor(() => expect(screen.queryByRole('region', { name: 'Artifact preview' })).not.toBeInTheDocument());
    }
    await act(async () => pending.resolve(payload()));
    expect(screen.queryByRole('heading', { name: 'Assessment report' })).not.toBeInTheDocument();
    if (change === 'superseded') expect(screen.getByRole('heading', { name: 'Latest report' })).toBeVisible();
    else expect(screen.queryByRole('region', { name: 'Artifact preview' })).not.toBeInTheDocument();
  });
});
