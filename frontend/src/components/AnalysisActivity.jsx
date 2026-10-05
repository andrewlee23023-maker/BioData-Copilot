import React from 'react';
import { Activity, CheckCircle2, Circle, Loader2, XCircle, Cpu } from 'lucide-react';

export default function AnalysisActivity({ steps, isAnalyzing }) {
  if (isAnalyzing) {
    return (
      <section className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem', border: '1px solid rgba(6, 182, 212, 0.4)' }}>
        <h3 style={{ fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: '#f8fafc' }}>
          <Loader2 size={18} color="#06b6d4" className="animate-spin-slow" />
          <span>AI AGENT WORKING</span>
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.9rem', color: '#38bdf8' }}>
            <Loader2 size={16} color="#06b6d4" className="animate-spin-slow" />
            <span>Inspecting dataset schema & selecting variables...</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.9rem', color: '#94a3b8' }}>
            <Circle size={16} color="#475569" />
            <span>Checking sample sizes and variance characteristics...</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.9rem', color: '#64748b' }}>
            <Circle size={16} color="#334155" />
            <span>Executing deterministic hypothesis tests & post-hoc corrections...</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.9rem', color: '#64748b' }}>
            <Circle size={16} color="#334155" />
            <span>Generating interactive Plotly visualization & synthesizing results...</span>
          </div>
        </div>
      </section>
    );
  }

  if (!steps || steps.length === 0) return null;

  return (
    <section className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
      <h3 style={{ fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: '#f8fafc' }}>
        <Activity size={18} color="#06b6d4" />
        <span>ANALYSIS ACTIVITY</span>
      </h3>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
        {steps.map((step, idx) => {
          const isDone = step.status === 'done';
          const isRefused = step.status === 'refused' || step.status === 'error';

          return (
            <div 
              key={idx} 
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.75rem', 
                fontSize: '0.9rem',
                color: isDone ? '#cbd5e1' : isRefused ? '#f87171' : '#64748b'
              }}
            >
              {isDone ? (
                <CheckCircle2 size={18} color="#10b981" />
              ) : isRefused ? (
                <XCircle size={18} color="#ef4444" />
              ) : (
                <Circle size={18} color="#475569" />
              )}
              
              <span style={{ fontWeight: isDone ? 500 : 400 }}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
