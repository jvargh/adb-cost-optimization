import { Badge, Callout, Panel } from '@/components';
import type { AssessmentResults, RoadmapItem } from '@/types';

const HORIZONS: { id: RoadmapItem['horizon']; label: string; hint: string }[] = [
  { id: '0-30', label: 'Days 0\u201330', hint: 'Close evidence gaps and land low-risk governance changes.' },
  { id: '31-60', label: 'Days 31\u201360', hint: 'Validate candidates against business context, then pilot.' },
  { id: '61-90', label: 'Days 61\u201390', hint: 'Roll out validated changes and measure against the baseline.' },
];

export function RoadmapTab({ results }: { results: AssessmentResults }) {
  const findingTitles = new Map(
    results.candidates.findings.map((f) => [f.detectorId, f.title] as const),
  );

  return (
    <div className="stack-lg">
      <Callout tone="info" title="Sequenced, not prescribed">
        The roadmap orders work by evidence readiness and risk. Items that depend on a finding cannot
        start until that finding has been validated by a human owner, which is why validation work
        appears before any change.
      </Callout>

      <div className="grid-3">
        {HORIZONS.map((horizon) => {
          const items = results.roadmap.filter((i) => i.horizon === horizon.id);
          return (
            <Panel key={horizon.id} title={horizon.label} subtitle={horizon.hint}>
              <div className="stack">
                {items.length === 0 && <span className="muted">Nothing scheduled in this horizon.</span>}
                {items.map((item, index) => (
                  <div className="stack-sm" key={index}>
                    <strong>{item.title}</strong>
                    <span className="muted">{item.detail}</span>
                    <div className="row-wrap">
                      <Badge tone="neutral">{item.owner}</Badge>
                      {item.dependsOnFindingIds.map((id) => (
                        <Badge key={id} tone="accent" title={findingTitles.get(id) ?? id}>
                          {id}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          );
        })}
      </div>

      <Panel
        title="Measurement plan"
        subtitle="How benefit will be proven rather than claimed."
      >
        <div className="stack-sm">
          <span>
            Baseline <span className="mono">{results.benefits.baselineId}</span> locks the
            authoritative cost for the analysis window on the{' '}
            {results.benefits.reportingBasis} basis. Any future claim of savings is measured as the
            difference between a post-change window and this baseline, normalized by{' '}
            {results.benefits.workloadNormalization.method}.
          </span>
          <span className="muted">{results.benefits.workloadNormalization.reason}</span>
          <span className="muted">
            Realized savings are reported as not yet measurable until a post-change window exists.
            The toolkit will not project a number it cannot observe.
          </span>
        </div>
      </Panel>
    </div>
  );
}
