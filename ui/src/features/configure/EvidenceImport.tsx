import { useState } from 'react';
import { getBackend } from '@/api';
import { Callout, Panel } from '@/components';
import { CapabilityOptionsEditor } from '@/components/CapabilityOptionsEditor';
import { defaultOptions } from '@/types/capabilities';

const DATASETS = ['clusters', 'node-timeline', 'jobs', 'job-runs', 'query-history', 'sql-warehouses', 'workspace-settings', 'metastore-assignment', 'commitment-demand', 'repos', 'notebooks', 'experiments', 'serving-endpoints', 'sql-alerts', 'genie-spaces', 'uc-volumes'];
export function EvidenceImport({ onOpen, onCancel }: { onOpen: (runId: string) => void; onCancel: () => void }) {
  const [files, setFiles] = useState<{ name: string; dataset: string; content: string }[]>([]);
  const [workspaceId, setWorkspace] = useState('');
  const [startUtc, setStart] = useState('');
  const [endUtc, setEnd] = useState('');
  const [options, setOptions] = useState(defaultOptions);
  const [preview, setPreview] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const invalidate = () => { setPreview(null); setConfirmed(false); };
  const submit = async (previewOnly: boolean) => {
    setBusy(true); setError(null);
    try {
      const response = await getBackend().capabilityOperation<{ runId?: string }>(null, 'import', {
        files, workspaceId, startUtc, endUtc, capabilities: options, preview: previewOnly, confirmed,
      });
      if (previewOnly) setPreview(JSON.stringify(response, null, 2));
      else if (response.runId) onOpen(response.runId);
      else throw new Error('Import returned no persisted run ID.');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return <div className="stack-lg">
    <Callout tone="info" title="Import scanner evidence without cloud access">
      Supported JSON arrays and CSV datasets are normalized locally. Scope/window are your declarations, not proof of completeness. Query text is omitted and identities/paths protected. Unsupported aggregate-only scanner exports are not silently treated as raw timelines.
    </Callout>
    <Panel title="Evidence files and declared scope"><fieldset disabled={busy}><div className="stack">
      <label className="field"><span className="field-label">Workspace ID</span><input className="input" value={workspaceId} onChange={e => { setWorkspace(e.target.value); invalidate(); }} /></label>
      <div className="grid-2">
        <label className="field"><span className="field-label">Declared start UTC</span><input className="input" type="datetime-local" value={startUtc.replace('Z', '')} onChange={e => { setStart(e.target.value ? `${e.target.value}Z` : ''); invalidate(); }} /></label>
        <label className="field"><span className="field-label">Declared end UTC</span><input className="input" type="datetime-local" value={endUtc.replace('Z', '')} onChange={e => { setEnd(e.target.value ? `${e.target.value}Z` : ''); invalidate(); }} /></label>
      </div>
      <label className="field"><span className="field-label">Select CSV / JSON evidence (maximum combined 8 MiB)</span><input type="file" multiple accept=".json,.csv" onChange={async e => {
        try {
          const selected = Array.from(e.target.files ?? []);
          if (selected.reduce((sum, f) => sum + f.size, 0) > 8 * 1024 * 1024) throw new Error('Selected files exceed 8 MiB. Import a bounded evidence set.');
          setFiles(await Promise.all(selected.map(async file => ({ name: file.name, dataset: DATASETS.find(d => file.name.startsWith(d)) ?? 'clusters', content: await file.text() }))));
          invalidate(); setError(null);
        } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
      }} /></label>
      {files.map((file, index) => <label className="field" key={`${file.name}:${index}`}><span className="field-label">{file.name}: dataset mapping</span><select className="select" value={file.dataset} onChange={e => { setFiles(values => values.map((v, i) => i === index ? { ...v, dataset: e.target.value } : v)); invalidate(); }}>{DATASETS.map(d => <option key={d}>{d}</option>)}</select></label>)}
    </div></fieldset></Panel>
    <CapabilityOptionsEditor value={options} onChange={o => { setOptions(o); invalidate(); }} />
    {error && <Callout tone="danger" title="Import failed">{error}</Callout>}
    {preview && <Panel title="Validated import preview"><pre className="markdown-preview">{preview}</pre><label className="checkbox"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Confirm declared scope, limitations and redaction</label></Panel>}
    <div className="row-wrap">
      <button className="btn" disabled={busy} onClick={onCancel}>Return to native setup</button>
      <button className="btn" disabled={busy || !files.length} onClick={() => void submit(true)}>Validate import</button>
      <button className="btn btn-primary" disabled={busy || !preview || !confirmed} onClick={() => void submit(false)}>{busy ? 'Processing evidence...' : 'Analyze imported evidence'}</button>
    </div>
  </div>;
}
