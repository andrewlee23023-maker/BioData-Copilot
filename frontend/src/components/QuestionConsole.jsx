import React from 'react';
import { MessageSquareText, Sparkles, ArrowRight, Loader2 } from 'lucide-react';

export default function QuestionConsole({ 
  question, 
  setQuestion, 
  onAnalyze, 
  isAnalyzing, 
  hasDataset 
}) {
  const exampleQuestions = [
    "Which treatment has the highest mean viability?",
    "Which treatment produced the highest cell viability compared with control?",
    "Is Drug A significantly different from Control?",
    "How does viability change with dose?",
    "Can you predict patient survival from this dataset?"
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (question.trim() && !isAnalyzing && hasDataset) {
      onAnalyze(question.trim());
    }
  };

  return (
    <section className="glass-panel" style={{ padding: '1.75rem', marginBottom: '2rem' }}>
      <div style={{ marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
          <MessageSquareText size={20} color="#06b6d4" />
          <span>Ask a Scientific Question</span>
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
          Enter your hypothesis or select an experimental prompt below.
        </p>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ position: 'relative', marginBottom: '1rem' }}>
          <textarea
            id="question-input"
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={
              hasDataset 
                ? "e.g., Which treatment produced the highest cell viability compared with control?" 
                : "Please load or upload a dataset first..."
            }
            disabled={!hasDataset || isAnalyzing}
            style={{
              width: '100%',
              padding: '0.9rem 1.1rem',
              borderRadius: '12px',
              background: 'rgba(15, 23, 42, 0.85)',
              border: '1px solid rgba(71, 85, 105, 0.6)',
              color: '#f8fafc',
              fontSize: '1rem',
              fontFamily: 'var(--font-sans)',
              resize: 'none',
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={(e) => e.target.style.borderColor = '#06b6d4'}
            onBlur={(e) => e.target.style.borderColor = 'rgba(71, 85, 105, 0.6)'}
          />
        </div>

        {/* Suggested Prompts */}
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.45rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Sparkles size={13} color="#06b6d4" />
            <span>EXAMPLE QUESTIONS:</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
            {exampleQuestions.map((q, idx) => (
              <button
                type="button"
                key={idx}
                className="chip"
                onClick={() => setQuestion(q)}
                disabled={!hasDataset || isAnalyzing}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Submit Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="submit"
            className="btn-primary"
            disabled={!hasDataset || !question.trim() || isAnalyzing}
            id="analyze-submit-btn"
            style={{ minWidth: '150px', justifyContent: 'center' }}
          >
            {isAnalyzing ? (
              <>
                <Loader2 size={18} className="animate-spin-slow" />
                <span>Analyzing...</span>
              </>
            ) : (
              <>
                <span>Analyze</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
