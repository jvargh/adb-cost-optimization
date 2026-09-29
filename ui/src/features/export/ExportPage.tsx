import { useState } from 'react';
import { Badge, Callout, DataTable, EmptyState, Panel, type Column } from '@/components';
import { useResultsStore } from '@/state';
import { getBackend } from '@/api';
import { formatBytes } from '@/lib/format';
import type { ExportArtifact } from '@/types';

export function ExportPage() {
  const { results, runId, exportedArtifactPaths, markArtifactExported } = useResultsStore();
  const [preview, setPreview] = useState<{ path: string; content: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!results || !runId) {
    return (
      <EmptyState
        title="No assessment run is open"
        detail="Open a run on the Visualize Results step to export its artifacts."
      />
    );
  }

  const download = async (artifact: ExportArtifact) => {
    setBusy(artifact.relativePath);
    setError(null);
    try {
      const payload = await getBackend().readArtifact(runId, artifact.relativePath);
      const blob = new Blob([payload.content], { type: payload.mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = artifact.relativePath.split('/').pop() ?? artifact.name;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      markArtifactExported(artifact.relativePath);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const open = async (artifact: ExportArtifact) => {
    setBusy(artifact.relativePath);
    setError(null);
    try {
      const payload = await getBackend().readArtifact(runId, artifact.relativePath);
      setPreview({ path: payload.relativePath, content: payload.content });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const columns: Column<ExportArtifact>[] = [
    {
      key: 'name',
      header: 'Artifact',
      render: (r) => (
        <div className="stack-sm">
          <span>{r.name}</span>
          <span className="muted mono truncate">{r.relativePath}</span>
        </div>
      ),
      sortValue: (r) => r.name,
    },
    {
      key: 'kind',
      header: 'Format',
      render: (r) => <Badge tone="neutral">{r.kind}</Badge>,
      sortValue: (r) => r.kind,
    },
    {
      key: 'desc',
      header: 'Contents',
      render: (r) => <span className="muted">{r.description}</span>,
    },
    {
      key: 'sensitivity',
      header: 'Sensitivity',
      render: (r) => (
        <Badge tone={r.sensitivity === 'sensitive' ? 'danger' : 'ok'}>
          {r.sensitivity === 'sensitive' ? 'sensitive' : 'redacted'}
        </Badge>
      ),
      sortValue: (r) => r.sensitivity,
    },
    {
      key: 'size',
      header: 'Size',
      align: 'right',
      render: (r) => <span className="numeric">{formatBytes(r.sizeBytes)}</span>,
      sortValue: (r) => r.sizeBytes,
    },
    {
      key: 'actions',
      header: '',
      render: (r) => (
        <div className="row">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => void open(r)}
            disabled={busy === r.relativePath}
          >
            Preview
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => void download(r)}
            disabled={busy === r.relativePath}
          >
            Download
          </button>
        </div>
      ),
    },
  ];

  const sensitiveCount = results.exports.filter((a) => a.sensitivity === 'sensitive').length;

  return (
    <div className="stack-lg">
      <Callout
        tone={exportedArtifactPaths.length > 0 ? 'ok' : 'info'}
        title={exportedArtifactPaths.length > 0 ? 'Export complete' : 'Download a file to complete this step'}
      >
        {exportedArtifactPaths.length > 0
          ? `${exportedArtifactPaths.length} ${exportedArtifactPaths.length === 1 ? 'file has' : 'files have'} been downloaded in this session.`
          : 'Previewing lets you inspect a file. Download at least one file to mark Export as complete.'}
      </Callout>

      <Callout tone="warn" title="Handle exported evidence as customer data">
        {sensitiveCount} of {results.exports.length} artifacts contain raw or lightly processed
        evidence. Identities, notebook paths, and table names are salted-hashed unless you explicitly
        relaxed redaction, and query text is omitted by default. Nothing here contains credentials or
        tokens.
      </Callout>

      {error && (
        <Callout tone="danger" title="Export failed">
          {error}
        </Callout>
      )}

      <Panel
        title="Run artifacts"
        subtitle={`Everything written under ${results.manifest.outputRoot}`}
      >
        <DataTable columns={columns} rows={results.exports} rowKey={(r) => r.relativePath} />
      </Panel>

      {preview && (
        <Panel
          title="Preview"
          subtitle={<span className="mono">{preview.path}</span>}
          actions={
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPreview(null)}>
              Close
            </button>
          }
        >
          <pre className="markdown-preview">{preview.content}</pre>
        </Panel>
      )}
    </div>
  );
}
