import { useState } from 'react';
import { getBackend } from '@/api';
import { Callout, Panel } from '@/components';
import { CapabilityOptionsEditor } from '@/components/CapabilityOptionsEditor';
import { useResultsStore, useRunStore } from '@/state';
import { defaultOptions } from '@/types/capabilities';

export function ReanalysisPanel() {
  const { runId, results, load } = useResultsStore();
  const [options, setOptions] = useState(results?.capabilities?.options ?? defaultOptions());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <Panel title="Re-analyze saved evidence" subtitle="Creates a child snapshot. No cloud reads, grants, or changes to the original evidence or review. Missing raw inputs cannot be recovered.">
    <details><summary>Inspect effective rules / create another analysis</summary>
      <CapabilityOptionsEditor value={options} onChange={setOptions} />
      {error && <Callout tone="danger" title="Re-analysis failed">{error}</Callout>}
      <button className="btn" disabled={!runId || busy} onClick={async () => {
        if (!window.confirm('Create a new local analysis from this snapshot using the displayed rules? The original remains unchanged.')) return;
        setBusy(true); setError(null);
        try {
          const response = await getBackend().capabilityOperation<{ runId: string }>(runId, 'reanalyze', { options });
          await load(response.runId);
          const url = new URL(window.location.href); url.searchParams.set('run', response.runId); window.history.replaceState(null, '', url);
          await useRunStore.getState().refreshRuns();
        } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
        finally { setBusy(false); }
      }}>{busy ? 'Analyzing saved evidence...' : 'Create child analysis'}</button>
    </details>
  </Panel>;
}
