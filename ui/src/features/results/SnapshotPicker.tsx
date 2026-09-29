import { useResultsStore, useRunStore } from '@/state';
import { formatDateTime } from '@/lib/format';

export function SnapshotPicker({ onOpen }: { onOpen: (runId: string) => void }) {
  const { runs, loadingRuns, refreshRuns, runsError } = useRunStore();
  const runId = useResultsStore((state) => state.runId);
  const timestamp = (value: string) => {
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const sorted = [...runs].sort((a, b) =>
    timestamp(b.startedAtUtc) - timestamp(a.startedAtUtc) || b.runId.localeCompare(a.runId),
  );
  const selected = sorted.find((run) => run.runId === runId);

  return (
    <div className="snapshot-picker">
      <label className="field">
        <span className="field-label">Saved snapshots</span>
        <select
          className="select"
          value={selected?.runId ?? ''}
          title={selected ? `${formatDateTime(selected.startedAtUtc)} | ${selected.runId}` : 'All saved snapshots, newest first. Opening one does not collect new evidence.'}
          aria-busy={loadingRuns}
          disabled={loadingRuns && runs.length === 0}
          onFocus={() => void refreshRuns()}
          onChange={(event) => onOpen(event.target.value)}
        >
          <option value="" disabled>
            {loadingRuns ? 'Loading snapshots...' : runsError ? 'Could not load snapshots' : sorted.length ? 'Select a saved snapshot' : 'No saved snapshots yet'}
          </option>
          {sorted.map((run) => (
            <option key={run.runId} value={run.runId}>
              {formatDateTime(run.startedAtUtc)} | {run.customerId} | {run.status} | {run.runId}
            </option>
          ))}
        </select>
      </label>
      {runsError && (
        <div className="field-error break-anywhere" role="alert">
          {runsError}
          <button type="button" className="btn btn-ghost btn-sm" disabled={loadingRuns} onClick={() => void refreshRuns()}>Retry snapshots</button>
        </div>
      )}
    </div>
  );
}
