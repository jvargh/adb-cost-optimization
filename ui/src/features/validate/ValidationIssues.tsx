import type { ValidationCheck } from '@/types';

type Issue = Pick<ValidationCheck, 'title' | 'detail' | 'remediation' | 'evidence'>;

export function ValidationIssueList({ checks }: { checks: Issue[] }) {
  return (
    <ul className="validation-issue-list">
      {checks.map((check, index) => (
        <li key={index}>
          <strong>{check.title}</strong>
          <span>{check.detail}</span>
          {check.remediation && <span><strong>What to do:</strong> {check.remediation}</span>}
          <SourceDetails check={check} />
        </li>
      ))}
    </ul>
  );
}

export function SourceDetails({ check }: { check: Pick<Issue, 'evidence'> }) {
  if (!check.evidence?.length) return null;
  return (
    <details>
      <summary>Source details ({check.evidence.length})</summary>
      <ul className="validation-issue-list">
        {check.evidence.map((item, index) => (
          <li key={index}>
            <strong>{item.source}</strong>
            <span style={{ overflowWrap: 'anywhere', whiteSpace: 'pre-wrap' }}>{item.detail}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
