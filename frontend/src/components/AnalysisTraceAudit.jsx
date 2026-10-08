import React from 'react';
import { CheckCircle2, XCircle, MinusCircle, ShieldAlert } from 'lucide-react';

// Renders the backend's `analysis_trace` and `statistical_audit` for a finished analysis.
// NOTE: this is a record returned AFTER the analysis completed, not a live stream.

const STATUS_STYLE = {
  passed:         { icon: CheckCircle2, color: '#10b981', text: 'Passed' },
  executed:       { icon: CheckCircle2, color: '#10b981', text: 'Executed' },
  failed:         { icon: XCircle,      color: '#ef4444', text: 'Failed' },
  blocked:        { icon: ShieldAlert,  color: '#f59e0b', text: 'Blocked' },
  not_applicable: { icon: MinusCircle,  color: '#9ca3af', text: 'Not applicable' },
};

const card = {
  background: 'rgba(17, 24, 39, 0.7)',
  border: '1px solid rgba(148, 163, 184, 0.18)',
  borderRadius: '12px',
  padding: '1.1rem 1.25rem',
  marginBottom: '1.25rem',
};
const heading = {
  fontSize: '0.72rem',
  letterSpacing: '0.12em',
  fontWeight: 700,
  color: '#9ca3af',
  margin: 0,
};
const mono = { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontVariantNumeric: 'tabular-nums' };

const fmt = (v) => (v === null || v === undefined ? '—' : typeof v === 'number' ? String(v) : v);

function TraceRow({ item }) {
  const style = STATUS_STYLE[item.status] || STATUS_STYLE.not_applicable;
  const Icon = style.icon;
  return (
    <li style={{ display: 'flex', gap: '0.65rem', padding: '0.45rem 0', alignItems: 'flex-start' }}>
      <Icon size={17} color={style.color} style={{ marginTop: 2, flexShrink: 0 }} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '0.9rem', color: '#e5e7eb', fontWeight: 500 }}>
          {item.label}{' '}
          <span style={{ color: style.color, fontSize: '0.72rem', fontWeight: 600 }}>· {style.text}</span>
        </div>
        {item.detail && (
          <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: 2, overflowWrap: 'anywhere' }}>{item.detail}</div>
        )}
      </div>
    </li>
  );
}

function Row({ label, children }) {
  return (
    <div style={{ display: 'flex', gap: '1rem', padding: '0.35rem 0', borderBottom: '1px solid rgba(148,163,184,0.1)' }}>
      <div style={{ width: '9.5rem', flexShrink: 0, color: '#9ca3af', fontSize: '0.82rem' }}>{label}</div>
      <div style={{ color: '#e5e7eb', fontSize: '0.88rem', minWidth: 0, overflowWrap: 'anywhere' }}>{children}</div>
    </div>
  );
}

export default function AnalysisTraceAudit({ result }) {
  if (!result || result.supported === false) return null;
  const trace = result.analysis_trace;
  const audit = result.statistical_audit;
  if (!trace && !audit) return null;

  const blocked = audit?.status === 'blocked';
  const effect = audit?.effect;

  return (
    <section aria-label="Analysis trace and statistical audit">
      {trace && (
        <div style={card}>
          <h3 style={heading}>ANALYSIS TRACE</h3>
          <p style={{ fontSize: '0.75rem', color: '#6b7280', margin: '0.25rem 0 0.4rem' }}>
            Recorded by the backend for this run (shown after the analysis finished).
          </p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {trace.map((item) => <TraceRow key={item.key} item={item} />)}
          </ul>
        </div>
      )}

      {audit && (
        <div style={{ ...card, borderColor: blocked ? 'rgba(245, 158, 11, 0.45)' : card.border }}>
          <h3 style={heading}>STATISTICAL AUDIT</h3>
          <div style={{ marginTop: '0.5rem' }}>
            <Row label="Selected test">{audit.selected_test}</Row>

            <Row label="Groups · n · mean">
              {audit.groups?.length ? (
                <table style={{ borderCollapse: 'collapse', ...mono, fontSize: '0.85rem' }}>
                  <tbody>
                    {audit.groups.map((g) => (
                      <tr key={g}>
                        <td style={{ paddingRight: '1.25rem' }}>{g}</td>
                        <td style={{ paddingRight: '1.25rem', color: '#9ca3af' }}>n = {fmt(audit.n_per_group?.[g])}</td>
                        <td>mean = {fmt(audit.means?.[g])}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : '—'}
            </Row>

            {!blocked && (
              <Row label={effect?.label || 'Effect / difference'}>
                {effect ? (
                  <span style={mono}>
                    {fmt(effect.value)}
                    {effect.comparison ? ` (${effect.comparison})` : ''}
                    {effect.r !== undefined && effect.r !== null ? `, r = ${effect.r}` : ''}
                    {effect.posthoc_p_adj ? `, Tukey p_adj ${effect.posthoc_p_adj}` : ''}
                  </span>
                ) : 'Not applicable for this analysis'}
              </Row>
            )}

            <Row label="p-value">
              {blocked ? (
                <span style={{ color: '#fbbf24' }}>None: the test was not run</span>
              ) : audit.formatted_p_value ? (
                <span style={mono}>p {audit.formatted_p_value}</span>
              ) : 'Not applicable (descriptive summary)'}
            </Row>

            {blocked && audit.blocked_reasons?.length > 0 && (
              <Row label="Blocked because">
                <ul style={{ margin: 0, paddingLeft: '1.1rem', color: '#fcd34d' }}>
                  {audit.blocked_reasons.map((r, i) => <li key={i}>{r.message}</li>)}
                </ul>
              </Row>
            )}
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.85rem' }}>
            <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem', borderRadius: 999, background: 'rgba(16,185,129,0.12)', color: '#34d399' }}>
              Computed by {audit.computed_by}
            </span>
            <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem', borderRadius: 999, background: 'rgba(6,182,212,0.12)', color: '#22d3ee' }}>
              Interpretation by {audit.interpreted_by}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
