import type { ReactNode } from 'react';
import type { Tone } from '@/lib/format';

/**
 * KPI card. When `value` is null the card renders the absent treatment rather
 * than a zero, because the assessment contract distinguishes "no evidence"
 * from "measured zero".
 */
export function KpiCard({
  label,
  value,
  note,
  accent = 'neutral',
  absentText = 'Not available',
}: {
  label: ReactNode;
  value: ReactNode | null;
  note?: ReactNode;
  accent?: Tone;
  absentText?: string;
}) {
  const absent = value === null || value === undefined || value === '';
  return (
    <div className={`kpi kpi-accent-${accent}`}>
      <span className="kpi-label">{label}</span>
      <span className={absent ? 'kpi-value absent' : 'kpi-value'}>
        {absent ? absentText : value}
      </span>
      {note && <span className="kpi-note">{note}</span>}
    </div>
  );
}
