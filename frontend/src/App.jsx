import React, { useState } from 'react';
import Header from './components/Header';
import DatasetWorkbench from './components/DatasetWorkbench';
import { AlertCircle } from 'lucide-react';

export default function App() {
  const [dataset, setDataset] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleLoadDemo = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/load-demo', { method: 'POST' });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to load synthetic demonstration dataset.');
      }
      const data = await response.json();
      setDataset(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUploadFile = async (file) => {
    setIsLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to process CSV file.');
      }
      const data = await response.json();
      setDataset(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '1060px', margin: '0 auto', padding: '2.5rem 1.5rem' }}>
      <Header />

      {error && (
        <div style={{ 
          background: 'rgba(239, 68, 68, 0.1)', 
          border: '1px solid rgba(239, 68, 68, 0.3)', 
          borderRadius: '10px', 
          padding: '0.85rem 1rem', 
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          color: '#fca5a5'
        }}>
          <AlertCircle size={18} color="#ef4444" />
          <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>{error}</span>
        </div>
      )}

      <DatasetWorkbench 
        dataset={dataset}
        onLoadDemo={handleLoadDemo}
        onUploadFile={handleUploadFile}
        isLoading={isLoading}
      />
    </div>
  );
}
