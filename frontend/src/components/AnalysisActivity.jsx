import React from 'react';
import { Activity, CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';

export default function AnalysisActivity({ steps, isAnalyzing }) {
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
          const isCurrent = step.status === 'active' || (isAnalyzing && idx === steps.length - 1 && !isDone);

          return (
            <div 
              key={idx} 
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.75rem', 
                fontSize: '0.9rem',
                color: isDone ? '#cbd5e1' : isRefused ? '#f87171' : isCurrent ? '#38bdf8' : '#64748b'
              }}
            >
              {isDone ? (
                <CheckCircle2 size={18} color="#10b981" />
              ) : isRefused ? (
                <XCircle size={18} color="#ef4444" />
              ) : isCurrent ? (
                <Loader2 size={18} color="#06b6d4" className="animate-spin-slow" />
              ) : (
                <Circle size={18} color="#475569" />
              )}
              
              <span style={{ fontWeight: isCurrent ? 600 : 400 }}>
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
