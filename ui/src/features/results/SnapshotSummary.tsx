import { Callout, KeyValue, Panel, Spinner, StatusBadge } from '@/components';
import { formatDateTime } from '@/lib/format';
import { useResultsStore } from '@/state';
import { CollectionOutcome } from './CollectionOutcome';

export function SnapshotSummary({ onResults }: { onResults: () => void }) {
  const { results, loading, error } = useResultsStore();
  if (loading) return <Spinner label="Reading saved snapshot..." />;
  if (error) return <Callout tone="danger" title="Could not load the snapshot">{error}</Callout>;
  if (!results) return null;
  const { manifest, collection } = results;

  return (
    <div className="stack-lg">
      <CollectionOutcome results={results} />
      <Panel title="Saved assessment" actions={<StatusBadge status={manifest.status} />}>
        <KeyValue items={[
          { label: 'Run', value: manifest.runId },
          { label: 'Collected', value: formatDateTime(manifest.startedAtUtc) },
          { label: 'Completed', value: manifest.completedAtUtc ? formatDateTime(manifest.completedAtUtc) : 'Not recorded' },
          { label: 'Customer', value: manifest.customerId },
          { label: 'Resource groups', value: manifest.scope.resourceGroups.join(', ') || 'None recorded' },
          { label: 'Workspaces', value: manifest.scope.workspaces.map((workspace) => workspace.name).join(', ') || 'None recorded' },
          { label: 'Analysis window', value: `${manifest.analysisWindow.startUtc} to ${manifest.analysisWindow.endUtc}` },
        ]} />
      </Panel>
      <Panel title="Saved collection checks" subtitle="Historical evidence from collection-status.json. Opening this page does not call Azure or Databricks.">
        <div className="stack">
          {collection.length === 0 && <p>No collection checks were recorded in this snapshot.</p>}
          {collection.map((source, index) => (
            <div className="stack-sm" key={`${source.name}-${index}`}>
              <div className="row-between"><span className="break-anywhere">{source.name}</span><StatusBadge status={source.status} /></div>
              {(source.error || source.limitations.length > 0) && (
                <details className="break-anywhere" open={source.status !== 'passed'}>
                  <summary>Saved limitations and errors</summary>
                  {source.error && <p>{source.error}</p>}
                  {source.limitations.length > 0 && <ul>{source.limitations.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}</ul>}
                </details>
              )}
            </div>
          ))}
        </div>
      </Panel>
      <div><button type="button" className="btn btn-primary" onClick={onResults}>View saved results</button></div>
    </div>
  );
}
