import { useEffect, useRef, useState } from 'react';
import { Badge, Callout, DataTable, EmptyState, Panel, type Column } from '@/components';
import { useResultsStore } from '@/state';
import { getBackend } from '@/api';
import { formatBytes } from '@/lib/format';
import type { ExportArtifact } from '@/types';
import { CapabilityExports } from './CapabilityExports';
import { ReviewPage } from '@/features/review/ReviewPage';
import { MarkdownPreview } from './MarkdownPreview';

interface ArtifactPreview {
  path: string;
  markdown: boolean;
  content: string | null;
  error: string | null;
}

export function ExportPage() {
  const { results, runId, exportedArtifactPaths, markArtifactExported } = useResultsStore();
  const [preview, setPreview] = useState<ArtifactPreview | null>(null);
  const previewRegion = useRef<HTMLDivElement>(null);
  const previewRequest = useRef(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewDirty, setReviewDirty] = useState(false);

  useEffect(() => {
    setPreview(null);
    return () => { previewRequest.current += 1; };
  }, [runId]);

  useEffect(() => {
    if (preview) {
      previewRegion.current?.focus({ preventScroll: true });
      previewRegion.current?.scrollIntoView({ block: 'start' });
    }
  }, [preview]);

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
      const content = payload.encoding === 'base64' ? Uint8Array.from(atob(payload.content), c => c.charCodeAt(0)) : payload.content;
      const blob = new Blob([content], { type: payload.mimeType });
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
    const request = ++previewRequest.current;
    const next: ArtifactPreview = {
      path: artifact.relativePath,
      markdown: artifact.kind === 'markdown' || /\.(md|markdown)$/i.test(artifact.relativePath),
      content: null,
      error: null,
    };
    setPreview(next);
    try {
      const payload = await getBackend().readArtifact(runId, artifact.relativePath);
      if (request !== previewRequest.current) return;
      if (payload.encoding === 'base64') throw new Error('Binary artifacts cannot be previewed. Download the file instead.');
      setPreview({ ...next, content: payload.content });
    } catch (e) {
      if (request === previewRequest.current) {
        setPreview({ ...next, error: e instanceof Error ? e.message : String(e) });
      }
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
            disabled={busy === r.relativePath || r.kind === 'xlsx'}
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
  const report = results.exports.find((artifact) => artifact.relativePath === 'reports/assessment-report.md');

  return (
    <div className="stack-lg">
      <Callout
        tone={exportedArtifactPaths.length > 0 ? 'ok' : 'info'}
        title={exportedArtifactPaths.length > 0 ? 'Export complete' : 'Download a file to complete this step'}
      >
        {exportedArtifactPaths.length > 0
          ? `${exportedArtifactPaths.length} ${exportedArtifactPaths.length === 1 ? 'file has' : 'files have'} been downloaded in this session.`
          : 'Preview a report or download the files you need. Review is optional; download a file to complete Review & export.'}
        {report && <div className="row-wrap">
          <button type="button" className="btn btn-primary" disabled={busy === report.relativePath} onClick={() => void download(report)}>Download report</button>
          <button type="button" className="btn" disabled={busy === report.relativePath} onClick={() => void open(report)}>Preview report</button>
        </div>}
      </Callout>

      <ReviewPage key={`review-${runId}`} onDirtyChange={setReviewDirty} />
      {reviewDirty && <Callout tone="warn" title="Unsaved review changes">
        Downloads contain saved decisions only. Save or discard edits before generating a workbook or publication plan.
      </Callout>}

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

      <CapabilityExports key={`capabilities-${runId}`} reviewPending={reviewDirty} />

      {preview && (
        <div ref={previewRegion} className="artifact-preview" role="region" aria-label="Artifact preview" tabIndex={-1}>
        <Panel
          title={preview.markdown ? 'Report preview' : 'Artifact preview'}
          subtitle={<span className="mono">{preview.path}</span>}
          actions={
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => {
              previewRequest.current += 1;
              setPreview(null);
            }}>
              Close
            </button>
          }
        >
          {preview.error
            ? <Callout tone="danger" title="Preview failed">{preview.error}</Callout>
            : preview.content === null
              ? <div role="status">Loading preview...</div>
              : preview.markdown
                ? <MarkdownPreview content={preview.content} path={preview.path} artifacts={results.exports} onPreview={artifact => void open(artifact)} />
                : <pre className="markdown-preview">{preview.content}</pre>}
        </Panel>
        </div>
      )}
    </div>
  );
}
