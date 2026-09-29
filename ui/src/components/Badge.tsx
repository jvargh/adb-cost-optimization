import type { ReactNode } from 'react';
import type { CollectionStatus, RunStatus, ConfidenceLevel } from '@/types';
import {
  collectionStatusTone,
  runStatusTone,
  confidenceTone,
  type Tone,
} from '@/lib/format';

export function Badge({
  tone = 'neutral',
  children,
  title,
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {children}
    </span>
  );
}

export function StatusBadge({ status, title }: { status: CollectionStatus; title?: string }) {
  return (
    <Badge tone={collectionStatusTone(status)} title={title}>
      {status}
    </Badge>
  );
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return <Badge tone={runStatusTone(status)}>{status}</Badge>;
}

export function ConfidenceBadge({ level, score }: { level: ConfidenceLevel; score?: number }) {
  return (
    <Badge tone={confidenceTone(level)} title={score !== undefined ? `Score ${score.toFixed(2)}` : undefined}>
      {level}
      {score !== undefined ? ` · ${score.toFixed(2)}` : ''}
    </Badge>
  );
}
