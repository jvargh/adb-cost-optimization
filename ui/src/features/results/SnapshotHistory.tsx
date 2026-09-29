import { useRef, useState } from 'react';
import { Callout, Drawer, Spinner, StatusBadge } from '@/components';
import { getBackend } from '@/api';
import { formatDateTime } from '@/lib/format';
import { useConfigStore, useRunStore } from '@/state';
import type { RunSummary } from '@/types';

export function SnapshotHistory({ onDeleted }: { onDeleted: (runIds: string[]) => void }) {
  const { runs, loadingRuns, refreshRuns, runsError, phase } = useRunStore();
  const validating = useConfigStore((state) => state.validating);
  const [open, setOpen] = useState(false);
  const [targets, setTargets] = useState<RunSummary[]>([]);
  const [deleting, setDeleting] = useState(false);
  const inFlight = useRef(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const active = validating || !['idle', 'completed', 'failed', 'canceled'].includes(phase);
  const blocked = deleting || loadingRuns || active;
  const sorted = [...runs].sort((a, b) => Date.parse(b.startedAtUtc) - Date.parse(a.startedAtUtc));
  const close = () => {
    if (inFlight.current) return;
    setOpen(false);
    setTargets([]);
  };
  const confirmDeletion = async () => {
    if (blocked || inFlight.current || targets.length === 0) return;
    inFlight.current = true;
    setDeleting(true);
    setError('');
    setMessage('');
    try {
      const result = await getBackend().deleteSnapshots(targets.map((run) => run.runId));
      onDeleted(result.deletedRunIds);
      useRunStore.setState((state) => ({
        runs: state.runs.filter((run) => !result.deletedRunIds.includes(run.runId)),
      }));
      setTargets([]);
      if (result.deletedRunIds.length) setMessage(`${result.deletedRunIds.length} snapshot(s) permanently deleted.`);
      if (result.failures.length) setError(result.failures.map((failure) => `${failure.runId}: ${failure.message}`).join('\n'));
      await refreshRuns();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      inFlight.current = false;
      setDeleting(false);
    }
  };

  return (
    <>
      <button type="button" className="btn btn-sm" onClick={() => { setOpen(true); setError(''); setMessage(''); void refreshRuns(); }}>Manage snapshots</button>
      <Drawer open={open} title="Manage saved snapshots" onClose={close}
        subtitle="Delete individual snapshots or clear the recorded history.">
        {error && <Callout tone="danger" title="Snapshot deletion did not fully complete"><span className="break-anywhere" style={{ whiteSpace: 'pre-wrap' }}>{error}</span></Callout>}
        {message && <div role="status">{message}</div>}
        {runsError && <Callout tone="danger" title="Could not refresh snapshots">{runsError}<button type="button" className="btn btn-sm" onClick={() => void refreshRuns()}>Retry history</button></Callout>}
        {active && <Callout tone="info" title="Deletion is unavailable during live work">Wait for the current validation or assessment to finish. Saved results can still be viewed.</Callout>}
        {targets.length > 0 ? (
          <div className="stack">
            <Callout tone="danger" title={`Permanently delete ${targets.length} snapshot(s)?`}>
              This removes each listed run folder, including raw evidence, reports, exports, and review decisions.
              It cannot be undone. Azure and Databricks resources are not changed.
              Snapshots created after this confirmation was opened will not be deleted.
            </Callout>
            <ul>{targets.map((run) => <li key={run.runId} className="break-anywhere">{formatDateTime(run.startedAtUtc)} | {run.customerId} | {run.runId}</li>)}</ul>
            <div className="row">
              <button type="button" className="btn" disabled={deleting} onClick={() => setTargets([])}>Keep snapshots</button>
              <button type="button" className="btn btn-danger" disabled={blocked} onClick={() => void confirmDeletion()}>Permanently delete</button>
            </div>
            {deleting && <Spinner label="Deleting saved run folders..." />}
          </div>
        ) : (
          <div className="stack">
            <div className="row-between">
              <span>{runs.length} recorded snapshot(s)</span>
              <button type="button" className="btn btn-danger btn-sm" disabled={blocked || runs.length === 0 || Boolean(runsError)}
                onClick={() => { setTargets(sorted); setError(''); setMessage(''); }}>Delete all snapshots</button>
            </div>
            {sorted.map((run) => (
              <div className="panel stack-sm" key={run.runId}>
                <div className="row-between"><span>{formatDateTime(run.startedAtUtc)}</span><StatusBadge status={run.status} /></div>
                <span className="break-anywhere">{run.customerId} | {run.runId}</span>
                <div><button type="button" className="btn btn-danger btn-sm" disabled={blocked}
                  aria-label={`Delete snapshot ${run.runId}`}
                  onClick={() => { setTargets([run]); setError(''); setMessage(''); }}>Delete snapshot</button></div>
              </div>
            ))}
            {!runs.length && !loadingRuns && <p>No saved snapshots.</p>}
          </div>
        )}
      </Drawer>
    </>
  );
}
