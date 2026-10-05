import React from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';
import { Award, BarChart3, TrendingUp, Info, AlertTriangle, Cpu, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';

const Plot = createPlotlyComponent(Plotly);

export default function ResultDeck({ result }) {
  if (!result) return null;

  if (!result.supported) {
    return (
      <section className="glass-panel animate-fade-in" style={{ padding: '2rem', marginBottom: '2rem', borderColor: 'rgba(239, 68, 68, 0.4)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
          <AlertTriangle size={24} color="#f87171" style={{ flexShrink: 0, marginTop: '0.2rem' }} />
          <div>
            <h3 style={{ color: '#f87171', fontSize: '1.15rem', marginBottom: '0.5rem' }}>
              Query Not Supported
            </h3>
            <p style={{ color: '#cbd5e1', fontSize: '0.95rem', lineHeight: 1.6 }}>
              {result.reason}
            </p>
          </div>
        </div>
      </section>
    );
  }

  const { stats, plotly_spec, interpretation } = result;
  const isANOVA = stats?.test_name?.includes("ANOVA");
  const isTTest = stats?.test_name?.includes("t-test") || stats?.test_name?.includes("Mann-Whitney");
  const isTrend = stats?.test_name?.includes("Correlation") || stats?.test_name?.includes("Trend");

  return (
    <section className="animate-fade-in" style={{ marginBottom: '2.5rem' }}>
      {/* High-Impact Stat Summary Card */}
      <div className="glass-panel glass-panel-highlight" style={{ padding: '2rem', marginBottom: '1.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          <Award size={22} color="#10b981" />
          <span style={{ fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.06em', color: '#10b981', textTransform: 'uppercase' }}>
            VERIFIED RESULT SUMMARY
          </span>
        </div>

        <h2 style={{ fontSize: '1.5rem', marginBottom: '1.5rem', color: '#fff' }}>
          {isTrend ? (
            <>Dose Concentration Trend for <span style={{ color: '#38bdf8' }}>{stats.value_column}</span></>
          ) : isTTest ? (
            <><span style={{ color: '#10b981' }}>{stats.top_performer}</span> pairwise comparison with {stats.reference_group}</>
          ) : (
            <><span style={{ color: '#10b981' }}>{stats.top_performer}</span> produced the highest mean {stats.value_column}.</>
          )}
        </h2>

        {/* 4 Metric Columns */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1.25rem' }}>
          {isTrend ? (
            <>
              <div style={{ background: 'rgba(15, 23, 42, 0.75)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(51, 65, 85, 0.6)' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Correlation (Pearson r)</div>
                <div className="num-tabular" style={{ fontSize: '1.8rem', fontWeight: 800, color: '#38bdf8', marginTop: '0.2rem' }}>
                  {stats.correlation_r ?? '-'}
                </div>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.75)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(51, 65, 85, 0.6)' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Regression Slope</div>
                <div className="num-tabular" style={{ fontSize: '1.8rem', fontWeight: 800, color: stats.slope < 0 ? '#f43f5e' : '#10b981', marginTop: '0.2rem' }}>
                  {stats.slope ?? '-'}
                </div>
              </div>
            </>
          ) : (
            <>
              <div style={{ background: 'rgba(15, 23, 42, 0.75)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(51, 65, 85, 0.6)' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Top Mean Viability</div>
                <div className="num-tabular" style={{ fontSize: '1.8rem', fontWeight: 800, color: '#10b981', marginTop: '0.2rem' }}>
                  {stats.top_mean}%
                </div>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.75)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(51, 65, 85, 0.6)' }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Compared with {stats.reference_group}</div>
                <div className="num-tabular" style={{ fontSize: '1.8rem', fontWeight: 800, color: stats.delta_vs_reference >= 0 ? '#10b981' : '#f43f5e', marginTop: '0.2rem' }}>
                  {stats.delta_vs_reference >= 0 ? `+${stats.delta_vs_reference}` : stats.delta_vs_reference} pp
                </div>
              </div>
            </>
          )}

          <div style={{ background: 'rgba(15, 23, 42, 0.75)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(51, 65, 85, 0.6)' }}>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Statistical Test</div>
            <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.4rem' }}>
              {stats.test_name}
            </div>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.75)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(51, 65, 85, 0.6)' }}>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Significance (p-value)</div>
            <div className="num-tabular" style={{ fontSize: '1.8rem', fontWeight: 800, color: stats.is_significant ? '#10b981' : '#f59e0b', marginTop: '0.2rem' }}>
              p {stats.formatted_p_value}
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Plotly Chart Canvas */}
      {plotly_spec && (
        <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.75rem', overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <BarChart3 size={18} color="#06b6d4" />
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              INTERACTIVE VISUALIZATION
            </span>
          </div>

          <div style={{ width: '100%', minHeight: '380px' }} id="plotly-chart-canvas">
            <Plot
              data={plotly_spec.data}
              layout={{
                ...plotly_spec.layout,
                autosize: true,
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(15, 23, 42, 0.5)',
              }}
              useResizeHandler={true}
              style={{ width: '100%', height: '100%', minHeight: '380px' }}
              config={{ responsive: true, displayModeBar: false }}
            />
          </div>
        </div>
      )}

      {/* Grounded Interpretation Card */}
      <div className="glass-panel" style={{ padding: '1.75rem', marginBottom: '1rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem', color: '#fff' }}>
          Scientific Interpretation
        </h3>
        
        <p style={{ color: '#cbd5e1', fontSize: '0.96rem', lineHeight: 1.7, marginBottom: '1.25rem' }}>
          {interpretation}
        </p>

        {/* Mandatory Guardrail Disclaimers */}
        <div style={{ 
          borderTop: '1px solid rgba(51, 65, 85, 0.5)', 
          paddingTop: '0.85rem', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '0.4rem',
          fontSize: '0.8rem',
          color: 'var(--text-muted)'
        }}>
          <div>• This describes the observed experiment and does not establish causality.</div>
          <div>• Synthetic demonstration data — not real experimental results.</div>
        </div>
      </div>

      {/* Agent Reasoning & State Trace Inspector */}
      {result.agent_state && (
        <AgentReasoningTrace agentState={result.agent_state} />
      )}
    </section>
  );
}

function AgentReasoningTrace({ agentState }) {
  const [isOpen, setIsOpen] = React.useState(true);
  const [activeTab, setActiveTab] = React.useState('trace'); // 'trace' or 'state'

  const history = agentState.tool_history || [];

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1rem', border: '1px solid rgba(14, 165, 233, 0.3)' }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          cursor: 'pointer',
          userSelect: 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <Cpu size={18} color="#38bdf8" />
          <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', letterSpacing: '0.04em' }}>
            AGENT REASONING & STATE TRACE
          </span>
          <span style={{ 
            fontSize: '0.72rem', 
            background: 'rgba(16, 185, 129, 0.15)', 
            color: '#10b981', 
            padding: '0.2rem 0.6rem', 
            borderRadius: '999px',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '0.3rem'
          }}>
            <ShieldCheck size={13} />
            Deterministic Python Engine
          </span>
        </div>
        <div style={{ color: '#94a3b8' }}>
          {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </div>

      {isOpen && (
        <div style={{ marginTop: '1.25rem' }}>
          {/* Tab Selector */}
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid rgba(51, 65, 85, 0.5)', paddingBottom: '0.5rem' }}>
            <button
              onClick={() => setActiveTab('trace')}
              style={{
                background: activeTab === 'trace' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                color: activeTab === 'trace' ? '#38bdf8' : '#94a3b8',
                border: activeTab === 'trace' ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid transparent',
                borderRadius: '6px',
                padding: '0.35rem 0.85rem',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              Step-by-Step Reasoning ({history.length} tools)
            </button>
            <button
              onClick={() => setActiveTab('state')}
              style={{
                background: activeTab === 'state' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                color: activeTab === 'state' ? '#38bdf8' : '#94a3b8',
                border: activeTab === 'state' ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid transparent',
                borderRadius: '6px',
                padding: '0.35rem 0.85rem',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              Explicit Agent State
            </button>
          </div>

          {activeTab === 'trace' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {history.map((step, idx) => (
                <div 
                  key={idx} 
                  style={{ 
                    background: 'rgba(15, 23, 42, 0.6)', 
                    border: '1px solid rgba(51, 65, 85, 0.6)', 
                    borderRadius: '8px', 
                    padding: '0.85rem 1rem' 
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ 
                        fontSize: '0.72rem', 
                        background: 'rgba(56, 189, 248, 0.2)', 
                        color: '#38bdf8', 
                        fontWeight: 700, 
                        padding: '0.15rem 0.5rem', 
                        borderRadius: '4px' 
                      }}>
                        STEP {step.step || idx + 1}
                      </span>
                      <code style={{ fontSize: '0.88rem', color: '#f1f5f9', fontWeight: 600 }}>
                        {step.tool}
                      </code>
                    </div>
                    <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 600 }}>
                      Deterministic Tool
                    </span>
                  </div>
                  
                  <div style={{ fontSize: '0.86rem', color: '#94a3b8', marginBottom: '0.5rem', lineHeight: 1.5 }}>
                    <strong style={{ color: '#cbd5e1' }}>Why chosen:</strong> {step.reason}
                  </div>

                  <div style={{ 
                    background: 'rgba(0, 0, 0, 0.35)', 
                    borderRadius: '6px', 
                    padding: '0.5rem 0.75rem', 
                    fontFamily: 'monospace', 
                    fontSize: '0.78rem',
                    color: '#a5f3fc'
                  }}>
                    <span style={{ color: '#64748b' }}>args: </span>
                    {JSON.stringify(step.arguments)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ 
              background: 'rgba(15, 23, 42, 0.7)', 
              borderRadius: '8px', 
              padding: '1rem', 
              fontFamily: 'monospace', 
              fontSize: '0.8rem',
              color: '#cbd5e1',
              maxHeight: '340px',
              overflowY: 'auto'
            }}>
              <div style={{ marginBottom: '0.6rem' }}><strong style={{ color: '#38bdf8' }}>Question:</strong> "{agentState.user_question}"</div>
              <div style={{ marginBottom: '0.6rem' }}><strong style={{ color: '#38bdf8' }}>Remaining Info Needed:</strong> {agentState.remaining_information_needed || 'None'}</div>
              <div style={{ marginBottom: '0.6rem' }}><strong style={{ color: '#38bdf8' }}>Completed Tools:</strong> {JSON.stringify(agentState.completed_analyses)}</div>
              <div><strong style={{ color: '#38bdf8' }}>Observations:</strong></div>
              <pre style={{ margin: '0.4rem 0 0 0', color: '#94a3b8', fontSize: '0.76rem', whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(agentState.observations || {}, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
