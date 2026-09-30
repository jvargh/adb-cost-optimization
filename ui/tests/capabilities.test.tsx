import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '@/app/App';
import { CapabilityOptionsEditor } from '@/components/CapabilityOptionsEditor';
import { ExportPage } from '@/features/export/ExportPage';
import { getBackend } from '@/api';
import { isReviewComplete, useConfigStore, useResultsStore, useRunStore } from '@/state';
import { defaultOptions } from '@/types/capabilities';
import type { AssessmentResults } from '@/types';
import fixture from '../mock/fixtures/contoso-clean.results.json';

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  window.history.replaceState(null, '', '/');
  useConfigStore.getState().reset(); useResultsStore.getState().clear(); useRunStore.getState().reset();
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });

describe('capability integration guards', () => {
  it('opens import mode without loading cloud configuration or discovering estate', () => {
    window.history.replaceState(null, '', '/?import=1');
    const discover = vi.spyOn(getBackend(), 'discoverEstate');
    const defaults = vi.spyOn(getBackend(), 'loadDefaultConfig');
    render(<App />);
    expect(screen.getByText('Import scanner evidence without cloud access')).toBeVisible();
    expect(discover).not.toHaveBeenCalled(); expect(defaults).not.toHaveBeenCalled();
  });

  it('canceling new assessment keeps the current setup', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    await useConfigStore.getState().bootstrap();
    const original = useConfigStore.getState().config;
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'New assessment' }));
    expect(confirm).toHaveBeenCalled();
    expect(useConfigStore.getState().config).toBe(original);
  });

  it('does not accept another resource finding when the detector is the same', () => {
    const results = structuredClone(fixture) as AssessmentResults;
    const original = results.candidates.findings[0];
    results.candidates.findings = [{ ...original, findingId: 'one' }, { ...original, findingId: 'two' }];
    results.review = [{ ...results.review[0], findingId: 'one', decision: 'accepted', reviewer: 'Reviewer' }];
    expect(isReviewComplete(results)).toBe(false);
    results.review.push({ ...results.review[0], findingId: 'two' });
    expect(isReviewComplete(results)).toBe(true);
  });

  it('extended profile resolves asset types but makes no backend request', () => {
    const update = vi.fn();
    const operation = vi.spyOn(getBackend(), 'capabilityOperation');
    render(<CapabilityOptionsEditor value={defaultOptions()} onChange={update} />);
    fireEvent.change(screen.getByLabelText('Collection profile'), { target: { value: 'extended' } });
    expect(update.mock.calls[0][0].assets).toHaveLength(7);
    expect(operation).not.toHaveBeenCalled();
  });

  it('validation continuation is uniquely placed after the permission panel', async () => {
    await useConfigStore.getState().bootstrap();
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /2 Validate/ }));
    const next = screen.getAllByRole('button', { name: 'Continue to run' });
    expect(next).toHaveLength(1);
    expect(next[0]).toBeDisabled();
    const permission = screen.getByText('Pipeline timeline permission setup');
    expect(permission.compareDocumentPosition(next[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('decodes binary workbook payload and does not offer a text preview', async () => {
    const results = structuredClone(fixture) as AssessmentResults;
    results.exports = [{ name: 'Workbook', kind: 'xlsx', relativePath: 'reports/test.xlsx', sizeBytes: 4, sensitivity: 'redacted', description: 'Test' }];
    act(() => useResultsStore.setState({ runId: 'test', results }));
    vi.spyOn(getBackend(), 'readArtifact').mockResolvedValue({ relativePath: 'reports/test.xlsx', encoding: 'base64', content: 'UEsDBA==', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const create = vi.fn((_blob: Blob) => 'blob:test'); vi.stubGlobal('URL', class extends URL { static createObjectURL = create; static revokeObjectURL = vi.fn(); });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    render(<ExportPage />);
    expect(screen.getByRole('button', { name: 'Preview' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0].size).toBe(4);
  });
});
