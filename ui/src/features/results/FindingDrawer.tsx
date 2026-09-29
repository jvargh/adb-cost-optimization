import { Badge, ConfidenceBadge, Drawer, KeyValue, Meter } from '@/components';
import { useResultsStore } from '@/state';
import { FINDING_CATEGORY_LABELS } from '@/types';
import { formatPercent, humanizeKey } from '@/lib/format';

export function FindingDrawer() {
  const { selectedFinding, selectFinding } = useResultsStore();
  if (!selectedFinding) return null;
  const finding = selectedFinding;
  const evidenceKeys = finding.evidence.length > 0 ? Object.keys(finding.evidence[0]) : [];

  return (
    <Drawer
      open
      title={finding.title}
      subtitle={`${finding.detectorId} \u00b7 ${FINDING_CATEGORY_LABELS[finding.category] ?? finding.category}`}
      onClose={() => selectFinding(null)}
      footer={
        <div className="row-between">
          <span className="muted">
            Human validation required before any action. Savings are not estimated.
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => selectFinding(null)}>
            Close
          </button>
        </div>
      }
    >
      <div className="stack-lg">
        <div className="row-wrap">
          <Badge tone={finding.status === 'candidate' ? 'warn' : 'neutral'}>
            {finding.status === 'candidate' ? 'candidate' : 'insufficient evidence'}
          </Badge>
          <ConfidenceBadge level={finding.confidence.level} score={finding.confidence.score} />
          <Badge tone="neutral">human validation required</Badge>
        </div>

        <section className="stack-sm">
          <span className="field-label">What was observed</span>
          <p>{finding.explanation}</p>
        </section>

        <section className="stack-sm">
          <span className="field-label">Recommended next step</span>
          <p>{finding.recommendedAction}</p>
        </section>

        <section className="stack-sm">
          <span className="field-label">Scope</span>
          <KeyValue
            items={[
              { label: 'Subscription', value: <span className="mono">{finding.scope.subscriptionId ?? 'Estate-wide'}</span> },
              { label: 'Resource group', value: finding.scope.resourceGroup ?? '\u2014' },
              { label: 'Workspace', value: finding.scope.workspaceName ?? '\u2014' },
              { label: 'Workload', value: finding.scope.workload ?? '\u2014' },
            ]}
          />
        </section>

        <section className="stack-sm">
          <span className="field-label">Confidence breakdown</span>
          {Object.entries(finding.confidence.metrics).map(([metric, value]) => (
            <div className="stack-sm" key={metric}>
              <div className="row-between">
                <span className="muted">{humanizeKey(metric)}</span>
                <span className="numeric">{formatPercent(value as number)}</span>
              </div>
              <Meter value={value as number} />
            </div>
          ))}
          {finding.confidence.missingRequiredMetrics.length > 0 && (
            <span className="muted">
              Missing required metrics: {finding.confidence.missingRequiredMetrics.join(', ')}
            </span>
          )}
        </section>

        {finding.limitations.length > 0 && (
          <section className="stack-sm">
            <span className="field-label">Limitations</span>
            {finding.limitations.map((limitation, index) => (
              <span className="muted" key={index}>
                &bull; {limitation}
              </span>
            ))}
          </section>
        )}

        <section className="stack-sm">
          <span className="field-label">Evidence ({finding.evidence.length} record(s))</span>
          {finding.evidence.length === 0 ? (
            <span className="muted">
              No evidence rows were retained for this finding, which is why it is reported as
              insufficient evidence.
            </span>
          ) : (
            <div className="table-wrap" style={{ maxHeight: 300 }}>
              <table className="data">
                <thead>
                  <tr>
                    {evidenceKeys.map((key) => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {finding.evidence.map((row, index) => (
                    <tr key={index}>
                      {evidenceKeys.map((key) => (
                        <td key={key}>
                          {row[key] === null ? (
                            <span className="muted">null</span>
                          ) : (
                            String(row[key])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {finding.evidenceFiles.length > 0 && (
          <section className="stack-sm">
            <span className="field-label">Backing artifacts</span>
            {finding.evidenceFiles.map((file) => (
              <span className="mono muted" key={file}>
                {file}
              </span>
            ))}
          </section>
        )}
      </div>
    </Drawer>
  );
}
