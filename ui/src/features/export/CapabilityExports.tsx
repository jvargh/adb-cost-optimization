import { useState } from 'react';
import { getBackend } from '@/api';
import { Callout, Panel } from '@/components';
import { MODULES, type JsonValue } from '@/types/capabilities';
import { useResultsStore } from '@/state';

export function CapabilityExports({ reviewPending = false }: { reviewPending?: boolean }) {
  const { runId, results, load } = useResultsStore();
  const [sheets, setSheets] = useState<string[]>([...MODULES]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [host, setHost] = useState('');
  const [warehouse, setWarehouse] = useState('');
  const [plan, setPlan] = useState<{ plan: JsonValue; confirmation: string } | null>(null);
  const [approved, setApproved] = useState(false);
  const [publication, setPublication] = useState<{ status: string; url?: string } | null>(null);
  if (!runId || !results?.capabilities) return null;
  const execute = async (action: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await action(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  };
  return <div className="stack">
    <Panel title="Excel workbook" subtitle="Immutable workbook of the full saved run and current saved review. Detailed arrays remain in JSON evidence. No spreadsheet macros or untrusted formulas.">
      <div className="row-wrap">{MODULES.map(m => <label key={m} className="checkbox"><input type="checkbox" checked={sheets.includes(m)} onChange={e => setSheets(e.target.checked ? [...sheets, m] : sheets.filter(s => s !== m))} />{m}</label>)}</div>
      <button className="btn" disabled={busy || reviewPending || !sheets.length} onClick={() => void execute(async () => {
        await getBackend().capabilityOperation(runId, 'workbook', { sheets });
        await load(runId);
      })}>{busy ? 'Working...' : 'Generate workbook artifact'}</button>
      <p className="muted">The generated XLSX appears in the artifact table above. Its filename identifies the evidence/review revision.</p>
    </Panel>
    <Panel title="Optional dashboard publication" subtitle="Separate cloud write operation. Publishes capability coverage counts only; no tables are created or dropped, and no raw evidence is uploaded.">
      <details><summary>Preview an explicitly approved destination</summary><div className="stack">
        <Callout tone="warn" title="Not part of the read-only assessment">Creates a new Lakeview dashboard and publishes it with viewer credentials. Warehouse use can incur charges. No grants, credential embedding, overwrite, or automatic retries.</Callout>
        <label className="field"><span className="field-label">Destination workspace URL</span><input className="input" value={host} onChange={e => { setHost(e.target.value); setPlan(null); setApproved(false); }} /></label>
        <label className="field"><span className="field-label">Destination warehouse ID</span><input className="input" value={warehouse} onChange={e => { setWarehouse(e.target.value); setPlan(null); setApproved(false); }} /></label>
        <button className="btn" disabled={busy || reviewPending} onClick={() => void execute(async () => {
          setPlan(await getBackend().capabilityOperation(runId, 'publish', { workspaceUrl: host, warehouseId: warehouse, preview: true }));
        })}>Preview publication plan</button>
        {plan && <><pre className="markdown-preview">{JSON.stringify(plan.plan, null, 2)}</pre>
          <label className="checkbox"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />Approve this exact destination, new dashboard creation, publication and warehouse charges</label>
          <button className="btn" disabled={busy || reviewPending || !approved} onClick={() => void execute(async () => {
            if (!window.confirm('Create and publish this new dashboard in the displayed workspace? This is a cloud write, not a read-only assessment.')) return;
            setPublication(await getBackend().capabilityOperation(runId, 'publish', { workspaceUrl: host, warehouseId: warehouse, confirmation: plan.confirmation, confirmed: true, approveCompute: true }));
            await load(runId);
          })}>Publish approved dashboard</button></>}
        {publication && <Callout tone="ok" title={publication.status}>{publication.url && <a href={publication.url} target="_blank" rel="noreferrer">Open published dashboard</a>}</Callout>}
      </div></details>
    </Panel>
    {error && <Callout tone="danger" title="Capability operation failed">{error} Inspect any persisted publication audit before retrying uncertain writes.</Callout>}
  </div>;
}
