import { Callout } from '@/components';
import type { AssessmentResults, CollectionSource, RunStatus } from '@/types';

export function getCollectionOutcome({ manifest, collection }: { manifest: { status: RunStatus }; collection: CollectionSource[] }) {
  const counts = {
    passed: collection.filter((source) => source.status === 'passed').length,
    partial: collection.filter((source) => source.status === 'partial').length,
    failed: collection.filter((source) => source.status === 'failed').length,
    pending: collection.filter((source) => source.status === 'pending telemetry').length,
    skipped: collection.filter((source) => source.status === 'skipped').length,
  };
  const needsAttention = manifest.status !== 'passed' || counts.passed === 0
    || collection.some((source) => source.error || !['passed', 'skipped'].includes(source.status));
  const title = manifest.status === 'failed' ? 'Assessment failed - action required'
    : counts.passed === 0 && collection.every((source) => source.status === 'skipped')
      ? 'Assessment completed - no collected checks to verify'
      : needsAttention ? 'Assessment completed - evidence needs attention' : 'Assessment completed - collected checks passed';
  return { ...counts, needsAttention, title };
}

export function CollectionOutcome({ results }: { results: AssessmentResults }) {
  const outcome = getCollectionOutcome(results);
  return (
    <Callout tone={outcome.needsAttention ? 'danger' : 'ok'} title={outcome.title}>
      <p>
        {outcome.passed} passed; {outcome.partial} partial; {outcome.failed} failed;
        {' '}{outcome.pending} pending telemetry; {outcome.skipped} skipped.
      </p>
      <p>
        {outcome.needsAttention
          ? 'Collection has finished, but its recorded outcome needs attention. Review the source limitations below before relying on affected findings.'
          : 'All collected sources passed. You can review the saved findings.'}
        {' '}Skipped sources were not collected: they are not passes, but intentional exclusions do not fail the run.
      </p>
      <p>
        This is the saved collection outcome, not a new permission check or proof of an earlier pre-run validation.
        {' '}Opening this snapshot does not start checks. Choose New assessment to collect updated evidence.
      </p>
    </Callout>
  );
}
