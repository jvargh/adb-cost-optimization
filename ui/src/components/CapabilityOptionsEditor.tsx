import { useState } from 'react';
import { ASSET_TYPES, DEFAULT_RULES, MODULES, defaultOptions, type CapabilityOptions } from '@/types/capabilities';
import { Callout, Panel } from './Panel';

export function CapabilityOptionsEditor({ value, onChange }: { value?: CapabilityOptions; onChange: (options: CapabilityOptions) => void }) {
  const options = value ?? defaultOptions();
  const [error, setError] = useState<string | null>(null);
  const update = (patch: Partial<CapabilityOptions>) => onChange({ ...options, ...patch });
  return <Panel title="Analysis modules, rules and collection profile" subtitle="Rules apply to a new analysis only. Optional metadata requires explicit selection; no grants or resource changes are implied.">
    <div className="stack">
      <div className="grid-2">
        <label className="field"><span className="field-label">Collection profile</span><select className="select" value={options.profile} onChange={e => {
          const profile = e.target.value as CapabilityOptions['profile'];
          update({ profile, assets: profile === 'extended' ? [...ASSET_TYPES] : profile === 'standard' ? [] : options.assets });
        }}><option value="standard">Standard: existing core evidence</option><option value="extended">Extended: include asset metadata</option><option value="custom">Custom</option></select></label>
        <label className="field"><span className="field-label">Concurrent Databricks collectors (1-4)</span><input className="input" type="number" min="1" max="4" value={options.concurrency} onChange={e => update({ concurrency: e.target.valueAsNumber })} /></label>
      </div>
      <fieldset><legend>Enabled analyses</legend><div className="row-wrap">{MODULES.map(module => <label className="checkbox" key={module}><input type="checkbox" checked={options.modules.includes(module)} onChange={e => update({ modules: e.target.checked ? [...options.modules, module] : options.modules.filter(m => m !== module) })} />{module}</label>)}</div></fieldset>
      <details><summary>Optional asset collection and privacy</summary><div className="stack-sm">
        <p>Metadata only. No notebook source or secret values. APIs may be unavailable; denials and truncation remain explicit.</p>
        {ASSET_TYPES.map(type => <label className="checkbox" key={type}><input type="checkbox" checked={options.assets.includes(type)} onChange={e => update({ profile: 'custom', assets: e.target.checked ? [...options.assets, type] : options.assets.filter(t => t !== type) })} />{type}</label>)}
      </div></details>
      <details><summary>Versioned analysis thresholds</summary><div className="grid-2">
        {(Object.keys(DEFAULT_RULES) as (keyof typeof DEFAULT_RULES)[]).map(key => <label className="field" key={key}><span className="field-label">{key}</span><input className="input" type="number" min="1" value={options.rules[key]} onChange={e => update({ rules: { ...options.rules, [key]: e.target.valueAsNumber } })} /></label>)}
      </div>
        <div className="row-wrap">
          <button className="btn btn-sm" type="button" onClick={() => { if (window.confirm('Reset edited rules to defaults for this new analysis?')) update({ rules: { ...DEFAULT_RULES } }); }}>Reset rules</button>
          <button className="btn btn-sm" type="button" onClick={() => {
            const url = URL.createObjectURL(new Blob([JSON.stringify(options.rules, null, 2)], { type: 'application/json' }));
            const a = document.createElement('a'); a.href = url; a.download = 'analysis-rules.json'; a.click(); URL.revokeObjectURL(url);
          }}>Export rules JSON</button>
          <label className="field">Import rules JSON<input type="file" accept=".json" onChange={async e => {
            try {
              const file = e.target.files?.[0]; if (!file) return;
              const parsed: unknown = JSON.parse(await file.text());
              if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Rules must be a JSON object.');
              const rules = { ...DEFAULT_RULES };
              for (const [key, v] of Object.entries(parsed)) {
                if (!(key in DEFAULT_RULES) || typeof v !== 'number' || !Number.isFinite(v) || v <= 0) throw new Error(`Invalid rule: ${key}`);
                rules[key as keyof typeof rules] = v;
              }
              update({ rules }); setError(null);
            } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
          }} /></label>
        </div>
      </details>
      <p className="muted">Plan: {options.modules.length} analyses; {options.assets.length} optional asset types; concurrency {options.concurrency}. Collection may use approved warehouses and incur charges. Full-window coverage is never assumed.</p>
      {error && <Callout tone="danger" title="Rule import failed">{error}</Callout>}
    </div>
  </Panel>;
}
