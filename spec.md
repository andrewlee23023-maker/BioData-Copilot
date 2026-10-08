---
doc: spec
status: approved
---

# BioData Copilot — Technical Specification

## How This Works, In Plain Language
BioData Copilot consists of two coordinated parts:
1. **A Frontend Workbench (React + Vite + Tailwind CSS + Plotly):** A responsive, single-page interface where researchers upload their experimental CSV, see their data summary, type their scientific question, watch real-time analysis steps, and inspect interactive charts.
2. **A Deterministic Analytical Backend (Python + FastAPI + SciPy/Pandas):** The computational engine. It inspects datasets, validates parameters, computes descriptive statistics and hypothesis tests (t-test, ANOVA, Mann-Whitney U), and generates Plotly visualization payloads.

**The AI Boundary ("LLM reasons; Python computes"):**
When a question is asked, the Gemini API is called with the dataset column metadata and the question. The LLM does *not* do math; it returns the next tool call as strict JSON (e.g. `{"tool": "compare_groups", "arguments": {"group_column": "treatment", "value_column": "viability", "test_type": "one_way_anova"}}`). The Python backend **validates every plan** (known tool, existing columns, supported test, no repeated tools, well-formed arguments) and rejects invalid ones in favor of the deterministic planner. The **statistical gate** inside `compare_groups` then re-checks the data (n ≥ 3 per compared group, numeric measurement, valid groups) and blocks the test if anything fails, regardless of what the plan said. Only then does Python run the exact SciPy calculations, package the verified numbers into a structured dictionary, and ask Gemini to formulate a 2-3 sentence grounded explanation citing *only* those verified numbers (entity-validated; blocked analyses always use a fixed template).

## The Core Journey Through the System
1. **Upload / Example Dataset:** User drags a CSV or clicks "Try Example Dataset".
   - *Flow:* Frontend sends CSV to `POST /api/upload` (or requests `POST /api/load-demo`). Backend parses CSV with Pandas, computes row count, column types, and missing values via `inspect_dataset()`, and returns JSON metadata.
2. **User Submits Question:** User types *"Which treatment produced the highest cell viability compared with control?"* and clicks "Analyze →".
   - *Flow:* Frontend sends `{question, session_id}` to `POST /api/analyze`.
3. **AI Planning:** Backend queries Gemini Flash with dataset schema and question. Gemini returns a structured JSON analysis plan.
4. **Backend Validation & Execution:**
   - Backend validates the plan, then `compare_groups()` enforces the statistical gate (columns exist, numeric data, valid groups, non-zero variance, $n \ge 3$ per compared group).
   - Backend calls `compare_groups()` or `summarize_groups()` using SciPy/NumPy. If the gate fails, no test runs and descriptive statistics are returned with structured `blocked_reasons`.
   - Backend calls `create_visualization()` to build an interactive Plotly figure specification.
5. **Grounded Interpretation:**
   - Backend sends the exact numerical results to Gemini Flash with a constrained prompt: "Summarize this biological finding. Use only the provided statistics. Do not calculate new numbers. Include synthetic and non-causality notices."
   - Gemini returns the concise text explanation.
6. **Results Display:** Frontend receives `{stats, plotly_spec, interpretation, steps, analysis_trace, statistical_audit, explanation_source}` and updates the UI with cards, chart, text, the Analysis Trace and the Statistical Audit. The trace is a record returned with the finished result, not a live stream.

## Stack
- **Frontend Framework:** React 18 + Vite (fast developer server, modular component architecture). [Vite Docs](https://vitejs.dev/)
- **Frontend Styling:** Tailwind CSS (rapid utility-first styling for a sleek dark laboratory theme). [Tailwind CSS Docs](https://tailwindcss.com/)
- **Visualization:** Plotly.js / `react-plotly.js` (interactive web-native scientific charts with hover inspection, zoom, and SVG export). [Plotly Docs](https://plotly.com/javascript/)
- **Backend API:** Python 3.10+ with FastAPI + Uvicorn (lightweight, asynchronous, auto-validating JSON schemas with Pydantic). [FastAPI Docs](https://fastapi.tiangolo.com/)
- **Data & Computation:** Pandas (tabular manipulation), NumPy (array operations), SciPy (inferential statistics: `f_oneway`, `ttest_ind`, `mannwhitneyu`). [SciPy Docs](https://docs.scipy.org/)
- **AI Model:** Gemini Flash-tier model over the REST API, configured in one place via `GEMINI_MODEL` (default `gemini-3.5-flash-lite`). [Gemini API Docs](https://ai.google.dev/)

## Where It Runs and How Someone Tries It
- **Runtime:** Runs locally on the user's computer (Windows, macOS, or Linux).
- **Requirements:** Python 3.10+ and Node.js 18+.
- **Environment Variables:** `GEMINI_API_KEY`, `GEMINI_MODEL`, `FRONTEND_ORIGIN` (CORS), `MAX_SESSIONS`, `SESSION_TTL_SECONDS` in a local `.env` file (see `.env.example`). (If no API key is provided, the backend falls back to a deterministic rule-based intent planner so the demo works 100% offline).
- **Start Commands:**
  - Backend: `uvicorn backend.main:app --reload --port 8000`
  - Frontend: `npm run dev` (opens `http://localhost:5173`)
- **Demo Recording:** A 90–120 second video recorded directly from the local browser walkthrough, showing upload → question → live stepper → verified plot + explanation.

## Look and Feel
- **Theme:** Dark laboratory workbench.
- **Colors:** Slate/dark navy background (`#090d16` / `#111827`), emerald green accents (`#10b981`) for statistical confidence and verified deltas, cyan (`#06b6d4`) for AI steps.
- **Typography:** Inter / system sans-serif; tabular numbers (`font-variant-numeric: tabular-nums`) for exact alignment; monospace font for column names.
- **Copy Tone:** Objective, scientific, cautious, transparent.

## Components

### Frontend Components (`frontend/src/components/`)
1. **`Header.jsx`**: App branding, tagline, synthetic dataset badge, and environment indicator.
   - Implements: `prd.md > Screens and Layout`
2. **`DatasetWorkbench.jsx`**: File drag-and-drop upload zone, "Try Example Dataset" button, and summary metric cards (observations, treatments, doses, columns).
   - Implements: `prd.md > 1. Dataset Upload & Inspection`
3. **`QuestionConsole.jsx`**: Query text area, clickable prompt chips, and "Analyze →" action button.
   - Implements: `prd.md > 2. Natural Language Question Processing`
4. **`AnalysisActivity.jsx`**: Visual stepper showing real execution states (Inspecting, Selecting, Computing, Plotting, Interpreting).
   - Implements: `prd.md > 3. Analysis Activity Stream`
5. **`ResultDeck.jsx`**: Summary metric cards, interactive Plotly visualization, structured scientific interpretation, and scientific disclaimers.
   - Implements: `prd.md > 4. Grounded Scientific Interpretation`

### Backend Modules (`backend/`)
1. **`main.py`**: FastAPI server exposing endpoints `/api/upload` (25 MB limit, HTTP 413), `/api/load-demo`, `/api/dataset/{id}`, `/api/analyze`, `/api/health`. CORS is restricted to `FRONTEND_ORIGIN`; sessions are held in a bounded, expiring in-memory store.
2. **`tools/inspect.py`**: `inspect_dataset(df)` returning row count, columns, types, unique groups, and missing values.
3. **`tools/stats.py`**: `validate_inferential_request(...)` (the statistical gate), `check_assumptions(...)`, `summarize_groups(df, group_col, val_col)` and `compare_groups(df, group_col, val_col, test_type, ref_group, target_group)`. `compare_groups` always runs the gate first.
4. **`tools/viz.py`**: `generate_plotly_spec(df, plan, stats_result)` returning complete Plotly figure JSON (box, bar with error bars, scatter).
5. **`agent.py`**: Tool registry, tool/plan validation, Gemini planning and explanation with fallbacks, entity validation, and construction of `analysis_trace` and `statistical_audit`.
6. **`tools/filter.py`**: `filter_dataset(df, filters)` for subsetting before analysis.

## Data Model
- **In-Memory Session Store:** DataFrames stored in an in-memory dictionary keyed by `session_id`. No permanent database.
- **Synthetic Dataset (`data/synthetic_viability.csv`):** 127 observations of a cell viability experiment with columns:
  - `sample_id`: unique string ID
  - `cell_line`: categorical (e.g. "HeLa", "A549")
  - `treatment`: categorical ("Control", "Drug A", "Drug B", "Drug C")
  - `dose`: numeric (µM: 0 for Control, 10, 50, 100 for drugs)
  - `timepoint`: numeric (hours: 24, 48, 72)
  - `replicate`: integer (1, 2, 3)
  - `viability`: float percentage (0 - 100%)

## File Structure
```
biodata-copilot/
├── scope.md                       # Public planning doc: Scope
├── prd.md                         # Public planning doc: Product Requirements
├── spec.md                        # Public planning doc: Technical Architecture
├── README.md                      # Architecture, setup, demo guide
├── .gitignore                     # Ignores .env, node_modules, learner profile
├── requirements.txt               # Python dependencies
├── package.json                   # Root package / tooling
├── backend/
│   ├── main.py                    # FastAPI application
│   ├── agent.py                   # Gemini AI planner & grounded explainer
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── inspect.py             # Dataset inspector tool
│   │   ├── filter.py              # Dataset filtering tool
│   │   ├── stats.py               # Statistical computations (ANOVA, t-test, etc.)
│   │   └── viz.py                 # Plotly specification generator
│   └── tests/
│       ├── test_stats.py          # Pytest unit tests for statistical tools
│       └── test_api.py            # FastAPI endpoint tests
├── frontend/
│   ├── package.json               # Frontend dependencies (React, Vite, Plotly)
│   ├── vite.config.js             # Vite configuration with proxy to :8000
│   ├── tailwind.config.js         # Tailwind configuration
│   ├── index.html                 # App shell
│   └── src/
│       ├── main.jsx               # Entry point
│       ├── App.jsx                # Core workbench layout & state machine
│       ├── index.css              # Styling & theme variables
│       └── components/
│           ├── Header.jsx         # App header & badges
│           ├── DatasetWorkbench.jsx # CSV upload & metadata cards
│           ├── QuestionConsole.jsx  # Question input & suggested chips
│           ├── AnalysisActivity.jsx # Real-time analysis progress stepper
│           ├── AnalysisTraceAudit.jsx # Analysis Trace + Statistical Audit
│           └── ResultDeck.jsx       # Stat cards, Plotly canvas, grounded interpretation
└── data/
    └── synthetic_viability.csv    # 127-observation synthetic viability assay
```

## External Services and Dependencies
- **Google Gemini API:**
  - Endpoint: `generateContent` via `google-genai` SDK or Google AI Studio REST endpoint.
  - Model: set by `GEMINI_MODEL` (default `gemini-3.5-flash-lite`).
  - Key: `GEMINI_API_KEY` loaded from `.env`.
  - Rate Limits & Cost: Generous free tier for hackathon / proof-of-concept testing.
  - Fallback: If `GEMINI_API_KEY` is not present, backend automatically activates a deterministic rule-based planner matching keyword intents, guaranteeing uninterrupted local testing and grading.

## Important Failure Modes
1. **Unsupported Question (e.g. "Predict survival rates"):**
   - *Detection:* AI intent planner returns `{"supported": false, "reason": "Survival modeling is not supported"}`.
   - *UI Behavior:* Displays clear info banner: *"This demo currently supports descriptive analyses, group comparisons, correlations, and basic experimental trends."*
2. **Missing Column in Query:**
   - *Detection:* AI requests a column not present in the active dataset schema.
   - *UI Behavior:* Displays friendly warning: *"Could not find requested column in this dataset. Available columns are: [list]"*.
3. **Small Sample Size ($n < 3$ in a compared group):**
   - *Detection:* The statistical gate in `compare_groups` validates sample counts before any test executes (it cannot be skipped by the planner).
   - *UI Behavior:* The test is blocked; the audit shows no p-value, lists the blocking reasons (e.g. *"Every compared group needs n >= 3; too small: Drug C (n = 2)."*), and descriptive statistics are still shown.
4. **Invalid Plan from the LLM:**
   - *Detection:* Python plan validation rejects unknown tools, missing columns, unsupported tests, or malformed JSON.
   - *Behavior:* The rejection is recorded in the steps/trace and the deterministic planner continues the analysis.
5. **Oversized Upload (> 25 MB):**
   - *Detection:* Content-Length pre-check plus a bounded chunked read.
   - *UI Behavior:* HTTP 413 with a friendly message.
6. **Invalid CSV / Parse Error:**
   - *Detection:* Pandas fails to parse uploaded file.
   - *UI Behavior:* Displays error alert: *"Invalid CSV format. Please ensure your file has valid tabular headers."*

## What Was Simplified and Why
- **In-Memory Session Store instead of PostgreSQL:** An experimental proof-of-concept operates on single datasets per session; avoiding a database eliminates Docker/DB setup for judges. The store is capped (`MAX_SESSIONS`) and expires idle sessions (`SESSION_TTL_SECONDS`) so memory stays bounded.
- **Predefined Tools instead of LLM Code Generation:** Allowing the LLM to write arbitrary Python code is prone to execution errors, timeouts, and hallucinations. Predefined validated functions guarantee 100% computational integrity.
- **Plotly JSON generation in Python instead of Frontend D3:** Python formats the exact Plotly figure dictionary, ensuring axis labels, error bars, and group colors match the verified calculation.

## Decisions and Open Issues
- **Learner Clarification on AI/Scientific Boundary:**
  - *Learner question/uncertainty:* How AI can be used reliably in daily scientific work without fabricating data.
  - *Resolution:* Strict separation of concerns ("LLM reasons; Python computes"). LLM outputs a constrained JSON intent plan, deterministic Python SciPy executes the math, and the LLM produces a summary citing only the computed numbers.
- **Offline / Zero-Config Grading Fallback:** We decided to include a deterministic keyword-based rule fallback for the AI agent in case the user or hackathon judge tests without setting a `GEMINI_API_KEY`.
