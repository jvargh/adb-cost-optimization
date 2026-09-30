import { useState } from 'react';
import { Callout, Panel } from '@/components';
import { useResultsStore } from '@/state';
import { formatDateTime } from '@/lib/format';
import type { ReviewDecision, ReviewEntry } from '@/types';

const DECISIONS: ReviewDecision[] = ['pending', 'accepted', 'rejected', 'deferred'];

export function ReviewPage({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { results, saveReview } = useResultsStore();
  const [draft, setDraft] = useState<ReviewEntry[] | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!results) return null;

  const entries = draft ?? results.review;
  const entry = entries.find((item) => item.findingId === selectedId) ?? entries[0];
  const progress = getReviewProgress(entries);
  const update = (patch: Partial<ReviewEntry>) => {
    setDraft(entries.map((item) => item.findingId === entry.findingId
      ? { ...item, ...patch, reviewedAtUtc: new Date().toISOString() } : item));
    onDirtyChange(true);
    setSavedAt(null);
    setError(null);
  };
  const save = async () => {
    if (entries.some((item) => item !== results.review.find((saved) => saved.findingId === item.findingId)
      && item.decision !== 'pending' && !item.reviewer.trim())) {
      setError('Enter a reviewer name for each edited decision before saving.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await saveReview(entries);
      setDraft(null);
      onDirtyChange(false);
      setSavedAt(new Date().toISOString());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel title="Optional review" subtitle="Export now, or record a decision for selected findings. Nothing applies a production change.">
      <p className="muted">
        {progress.decisionCount} of {entries.length} findings have a decision.
        {progress.missingReviewerCount > 0 && ` ${progress.missingReviewerCount} still need a reviewer.`}
        {' '}Pending findings remain unapproved; downloading is not sign-off.
      </p>
      {entry && <details>
        <summary>Record a decision</summary>
        <div className="stack">
          <label className="field"><span className="field-label">Finding</span>
            <select className="select" value={entry.findingId} disabled={saving} onChange={(event) => setSelectedId(event.target.value)}>
              {entries.map((item) => <option key={item.findingId} value={item.findingId}>{item.finding} ({item.decision})</option>)}
            </select>
          </label>
          <div className="grid-2">
            <label className="field"><span className="field-label">Decision</span>
              <select className="select" value={entry.decision} disabled={saving}
                onChange={(event) => update({ decision: event.target.value as ReviewDecision })}>
                {DECISIONS.map((decision) => <option key={decision} value={decision}>{decision}</option>)}
              </select>
            </label>
            <label className="field"><span className="field-label">Reviewer</span>
              <input className="input" value={entry.reviewer} disabled={saving} placeholder="Name of the person accountable"
                onChange={(event) => update({ reviewer: event.target.value })} />
            </label>
          </div>
          <label className="field"><span className="field-label">Note (optional)</span>
            <textarea className="textarea" rows={2} value={entry.rationale} disabled={saving}
              onChange={(event) => update({ rationale: event.target.value })} />
          </label>
          <div className="row-wrap">
            <button type="button" className="btn" onClick={() => void save()} disabled={saving || !draft}>
              {saving ? 'Saving...' : 'Save review decisions'}
            </button>
            {draft && <button type="button" className="btn btn-ghost" disabled={saving} onClick={() => {
              if (!window.confirm('Discard unsaved review changes?')) return;
              setDraft(null); onDirtyChange(false); setError(null);
            }}>Discard changes</button>}
            <span className="muted">{savedAt ? `Review saved ${formatDateTime(savedAt)}.` : draft ? 'Unsaved changes. Exports use saved decisions only.' : ''}</span>
          </div>
        </div>
      </details>}
      {error && <Callout tone="danger" title="Review was not saved">{error}</Callout>}
    </Panel>
  );
}

export function getReviewProgress(entries: ReviewEntry[]) {
  const decisionCount = entries.filter((entry) => entry.decision !== 'pending').length;
  const pendingDecisionCount = entries.length - decisionCount;
  const missingReviewerCount = entries.filter(
    (entry) => entry.decision !== 'pending' && !entry.reviewer.trim(),
  ).length;
  return {
    decisionCount, pendingDecisionCount, missingReviewerCount,
    complete: entries.length > 0 && pendingDecisionCount === 0 && missingReviewerCount === 0,
  };
}
