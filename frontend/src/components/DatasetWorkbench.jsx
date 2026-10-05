import React, { useRef } from 'react';
import { Upload, FlaskConical, CheckCircle2, AlertCircle, FileSpreadsheet, Layers, Grid } from 'lucide-react';

export default function DatasetWorkbench({ 
  dataset, 
  onLoadDemo, 
  onUploadFile, 
  isLoading 
}) {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onUploadFile(file);
    }
  };

  const inspection = dataset?.inspection;
  const summary = inspection?.summary;

  return (
    <section className="glass-panel" style={{ padding: '1.75rem', marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
            <FileSpreadsheet size={20} color="#10b981" />
            <span>Dataset Ingestion</span>
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
            Upload an experimental CSV or launch the pre-packaged viability assay.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            accept=".csv" 
            style={{ display: 'none' }} 
            id="csv-file-input"
          />
          <button 
            type="button"
            className="btn-secondary"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading}
            id="upload-csv-btn"
          >
            <Upload size={16} />
            <span>Upload CSV</span>
          </button>

          <button 
            type="button"
            className="btn-primary"
            onClick={onLoadDemo}
            disabled={isLoading}
            id="try-demo-btn"
          >
            <FlaskConical size={16} />
            <span>Try Example Dataset</span>
          </button>
        </div>
      </div>

      {dataset ? (
        <div className="animate-fade-in">
          {/* Status banner */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            background: 'rgba(16, 185, 129, 0.08)', 
            border: '1px solid rgba(16, 185, 129, 0.25)', 
            borderRadius: '10px', 
            padding: '0.75rem 1rem',
            marginBottom: '1.25rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <CheckCircle2 size={18} color="#10b981" />
              <span style={{ fontWeight: 600, color: '#f8fafc', fontSize: '0.92rem' }}>
                Dataset loaded: <span style={{ color: '#38bdf8' }}>{dataset.filename || 'experimental_data.csv'}</span>
              </span>
            </div>

            {dataset.is_synthetic && (
              <span style={{ 
                fontSize: '0.75rem', 
                background: 'rgba(245, 158, 11, 0.15)', 
                border: '1px solid rgba(245, 158, 11, 0.3)', 
                color: '#fbbf24', 
                padding: '0.2rem 0.6rem', 
                borderRadius: '6px',
                fontWeight: 600
              }}>
                Synthetic demonstration data — not real experimental results
              </span>
            )}
          </div>

          {/* Metadata Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.85rem', marginBottom: '1.25rem' }}>
            <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(51, 65, 85, 0.6)', borderRadius: '10px', padding: '0.85rem 1rem' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>Observations</div>
              <div className="num-tabular" style={{ fontSize: '1.65rem', fontWeight: 800, color: '#f8fafc', marginTop: '0.2rem' }}>
                {summary?.observations || inspection?.rows}
              </div>
            </div>

            <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(51, 65, 85, 0.6)', borderRadius: '10px', padding: '0.85rem 1rem' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>Treatments</div>
              <div className="num-tabular" style={{ fontSize: '1.65rem', fontWeight: 800, color: '#10b981', marginTop: '0.2rem' }}>
                {summary?.treatments_count ?? '-'}
              </div>
            </div>

            <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(51, 65, 85, 0.6)', borderRadius: '10px', padding: '0.85rem 1rem' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>Doses</div>
              <div className="num-tabular" style={{ fontSize: '1.65rem', fontWeight: 800, color: '#38bdf8', marginTop: '0.2rem' }}>
                {summary?.doses_count ?? '-'}
              </div>
            </div>

            <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(51, 65, 85, 0.6)', borderRadius: '10px', padding: '0.85rem 1rem' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600 }}>Replicates</div>
              <div className="num-tabular" style={{ fontSize: '1.65rem', fontWeight: 800, color: '#a78bfa', marginTop: '0.2rem' }}>
                {summary?.replicates_count ?? '-'}
              </div>
            </div>
          </div>

          {/* Column Chips */}
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>
              DETECTED COLUMNS ({inspection?.columns?.length || 0}):
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
              {inspection?.columns?.map((col) => {
                const isNumeric = inspection?.numeric_columns?.includes(col);
                return (
                  <span 
                    key={col} 
                    style={{ 
                      fontFamily: 'var(--font-mono)', 
                      fontSize: '0.78rem',
                      background: isNumeric ? 'rgba(56, 189, 248, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                      border: `1px solid ${isNumeric ? 'rgba(56, 189, 248, 0.25)' : 'rgba(16, 185, 129, 0.25)'}`,
                      color: isNumeric ? '#7dd3fc' : '#6ee7b7',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '6px'
                    }}
                  >
                    {col} {isNumeric ? '(num)' : '(cat)'}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        /* Empty State */
        <div 
          onClick={() => fileInputRef.current?.click()}
          style={{ 
            border: '2px dashed rgba(71, 85, 105, 0.4)', 
            borderRadius: '12px', 
            padding: '2.5rem 1.5rem', 
            textAlign: 'center',
            cursor: 'pointer',
            transition: 'border-color 0.2s',
            background: 'rgba(15, 23, 42, 0.3)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = '#10b981'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'rgba(71, 85, 105, 0.4)'}
        >
          <div style={{ width: '48px', height: '48px', margin: '0 auto 0.75rem', borderRadius: '50%', background: 'rgba(30, 41, 59, 0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Upload size={24} color="#94a3b8" />
          </div>
          <div style={{ fontWeight: 600, color: '#f1f5f9', marginBottom: '0.25rem' }}>
            Drag and drop your experimental CSV here, or click to browse
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
            Supports standard tabular CSV formats with treatments, doses, and numerical endpoints.
          </div>
        </div>
      )}
    </section>
  );
}
