import type { ReactNode } from 'react';

export interface TabDef {
  id: string;
  label: ReactNode;
  badge?: ReactNode;
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          className={active === tab.id ? 'tab active' : 'tab'}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.badge !== undefined && <span className="muted"> {tab.badge}</span>}
        </button>
      ))}
    </div>
  );
}

export function ChipGroup({
  label,
  options,
  selected,
  onToggle,
}: {
  label: ReactNode;
  options: { value: string; label: ReactNode }[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  if (options.length === 0) return null;
  return (
    <div className="stack-sm">
      <span className="field-label">{label}</span>
      <div className="row-wrap">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={selected.includes(option.value) ? 'chip active' : 'chip'}
            onClick={() => onToggle(option.value)}
            aria-pressed={selected.includes(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="row">
      <span className="spinner" aria-hidden="true" />
      {label && <span className="muted">{label}</span>}
    </span>
  );
}
