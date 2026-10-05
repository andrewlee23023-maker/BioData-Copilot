import React from 'react';
import { Dna, ShieldCheck, Cpu } from 'lucide-react';

export default function Header() {
  return (
    <header className="header-container" style={{ marginBottom: '2.5rem', borderBottom: '1px solid rgba(51, 65, 85, 0.4)', paddingBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.4rem' }}>
            <div style={{ 
              width: '38px', 
              height: '38px', 
              borderRadius: '10px', 
              background: 'linear-gradient(135deg, #10b981, #06b6d4)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              boxShadow: '0 0 20px rgba(16, 185, 129, 0.4)'
            }}>
              <Dna size={22} color="#042f2e" strokeWidth={2.5} />
            </div>
            <h1 style={{ fontSize: '1.85rem', margin: 0, background: 'linear-gradient(to right, #ffffff, #cbd5e1)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              BioData Copilot
            </h1>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', margin: 0 }}>
            Ask questions about your experimental data.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
          <div style={{ 
            display: 'inline-flex', 
            alignItems: 'center', 
            gap: '0.4rem', 
            padding: '0.35rem 0.85rem', 
            borderRadius: '9999px', 
            fontSize: '0.78rem', 
            fontWeight: 600,
            background: 'rgba(6, 182, 212, 0.1)', 
            border: '1px solid rgba(6, 182, 212, 0.3)',
            color: '#38bdf8'
          }}>
            <Cpu size={14} />
            <span>LLM Reasons • Python Computes</span>
          </div>

          <div style={{ 
            display: 'inline-flex', 
            alignItems: 'center', 
            gap: '0.4rem', 
            padding: '0.35rem 0.85rem', 
            borderRadius: '9999px', 
            fontSize: '0.78rem', 
            fontWeight: 600,
            background: 'rgba(16, 185, 129, 0.1)', 
            border: '1px solid rgba(16, 185, 129, 0.3)',
            color: '#10b981'
          }}>
            <ShieldCheck size={14} />
            <span>Scientifically Verified</span>
          </div>
        </div>
      </div>
    </header>
  );
}
