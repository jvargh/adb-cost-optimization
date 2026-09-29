import type { ReactNode } from 'react';

export function Panel({
  title,
  subtitle,
  actions,
  children,
  footer,
  bodyClassName,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  bodyClassName?: string;
}) {
  return (
    <section className="panel">
      {(title || actions) && (
        <header className="panel-header">
          <div className="panel-header-text">
            {title && <h3>{title}</h3>}
            {subtitle && <span className="panel-subtitle">{subtitle}</span>}
          </div>
          {actions && <div className="row">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName ? `panel-body ${bodyClassName}` : 'panel-body'}>{children}</div>
      {footer && <footer className="panel-footer">{footer}</footer>}
    </section>
  );
}

const CALLOUT_ICONS: Record<string, string> = {
  info: 'i',
  ok: '\u2713',
  warn: '!',
  danger: '\u00d7',
};

export function Callout({
  tone = 'info',
  title,
  children,
}: {
  tone?: 'info' | 'ok' | 'warn' | 'danger';
  title?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={`callout callout-${tone}`}>
      <span className="callout-icon" aria-hidden="true">
        {CALLOUT_ICONS[tone]}
      </span>
      <div className="callout-body">
        {title && <span className="callout-title">{title}</span>}
        {children}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-title">{title}</span>
      {detail && <span className="muted">{detail}</span>}
      {action}
    </div>
  );
}

export function Meter({ value, color }: { value: number; color?: string }) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div className="meter" role="img" aria-label={`${Math.round(clamped * 100)} percent`}>
      <span
        className="meter-fill"
        style={{ width: `${clamped * 100}%`, background: color ?? 'var(--accent)' }}
      />
    </div>
  );
}

export function KeyValue({ items }: { items: { label: ReactNode; value: ReactNode }[] }) {
  return (
    <dl className="kv">
      {items.map((item, index) => (
        <div key={index} style={{ display: 'contents' }}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
