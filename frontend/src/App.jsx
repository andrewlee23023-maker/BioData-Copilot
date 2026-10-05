import React, { useState } from 'react';
import Header from './components/Header';
import DatasetWorkbench from './components/DatasetWorkbench';
import QuestionConsole from './components/QuestionConsole';
import AnalysisActivity from './components/AnalysisActivity';
import ResultDeck from './components/ResultDeck';
import { AlertCircle } from 'lucide-react';

export default function App() {
  const [dataset, setDataset] = useState(null);
  const [question, setQuestion] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisSteps, setAnalysisSteps] = useState([]);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);

  const handleLoadDemo = async () => {
    setError(null);
    setAnalysisResult(null);
    setAnalysisSteps([]);
    try {
      const response = await fetch('/api/load-demo', { method: 'POST' });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to load synthetic demonstration dataset.');
      }
      const data = await response.json();
      setDataset(data);
      // Pre-fill question with the classic playbook prompt
      setQuestion('Which treatment produced the highest cell viability compared with control?');
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUploadFile = async (file) => {
    setError(null);
    setAnalysisResult(null);
    setAnalysisSteps([]);
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
    }
  };

  const handleAnalyze = async (queryToAnalyze) => {
    if (!dataset?.session_id) {
      setError("Please load a dataset before analyzing.");
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    setAnalysisResult(null);

    // Initial progressive stepper states
    setAnalysisSteps([
      { label: "Inspecting dataset & verifying schema", status: "done" },
      { label: "Identifying experimental groups", status: "active" },
      { label: "Checking sample sizes & distributions", status: "pending" },
      { label: "Running statistical hypothesis testing", status: "pending" },
      { label: "Generating Plotly interactive visualization", status: "pending" },
      { label: "Synthesizing verified scientific interpretation", status: "pending" }
    ]);

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: dataset.session_id,
          question: queryToAnalyze
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Analysis request failed.');
      }

      const data = await response.json();
      setAnalysisSteps(data.steps || []);
      setAnalysisResult(data);
    } catch (err) {
      setError(err.message);
      setAnalysisSteps((prev) => [
        ...prev.map(s => s.status === 'active' ? { ...s, status: 'error' } : s)
      ]);
    } finally {
      setIsAnalyzing(false);
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

      {/* Screen A: Dataset Ingestion */}
      <DatasetWorkbench 
        dataset={dataset}
        onLoadDemo={handleLoadDemo}
        onUploadFile={handleUploadFile}
        isLoading={isAnalyzing}
      />

      {/* Screen B: Ask Question */}
      <QuestionConsole 
        question={question}
        setQuestion={setQuestion}
        onAnalyze={handleAnalyze}
        isAnalyzing={isAnalyzing}
        hasDataset={Boolean(dataset)}
      />

      {/* Screen C: Analysis Activity Stepper */}
      <AnalysisActivity 
        steps={analysisSteps}
        isAnalyzing={isAnalyzing}
      />

      {/* Screen D: Verified Results Deck */}
      <ResultDeck 
        result={analysisResult}
      />
    </div>
  );
}
