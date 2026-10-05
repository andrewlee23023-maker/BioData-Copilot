# BioData Copilot 🧬

> **"LLM reasons; Python computes."** — A polished, scientifically grounded web app for biology and biotechnology researchers that turns plain-English questions about experimental datasets into reproducible statistical analyses, publication-ready Plotly visualizations, and verified interpretations.

---

## 1. What BioData Copilot Is
BioData Copilot bridges the gap between laboratory bench science and computational data analysis. Instead of manually writing boilerplate Pandas and SciPy scripts or guessing which statistical comparison to run, researchers can upload tabular assay data, ask a hypothesis in natural language, and receive verified answers with interactive charts.

## 2. Who It Is For
- **Target User:** Biology and biotechnology researchers, bench scientists, and translational medicine teams working with experimental assay data (e.g. cell viability, dose-response, plate reader readouts).
- **Core Problem Solved:** Reduces the time spent translating experimental questions into statistical code, while eliminating the hallucination risks of generic LLMs by strictly isolating mathematical computation to deterministic Python code.

## 3. The Core Workflow
```
Upload CSV or 1-Click Demo
         ↓
Inspect Dataset (Observations, Treatments, Doses, Replicates)
         ↓
Ask a Scientific Question in Plain English
         ↓
AI Selects Appropriate Analysis (Structured JSON Plan)
         ↓
Deterministic Python Computes Statistics (SciPy / Pandas)
         ↓
Interactive Plotly Visualization Generated
         ↓
AI Synthesizes Grounded Scientific Interpretation (Zero Hallucinated Metrics)
```

## 4. Architecture
- **Frontend:** React 18, Vite, Tailwind CSS, Lucide Icons, Plotly.js (`react-plotly.js`).
- **Backend API:** Python 3.10+, FastAPI, Uvicorn, Pydantic.
- **Computation Engine:** Pandas, NumPy, SciPy (`scipy.stats` for ANOVA, Welch's t-test, Mann-Whitney U, Pearson correlation).
- **AI Agent:** Google Gemini API (`gemini-2.5-flash`), with an automated deterministic rule-based fallback ensuring 100% offline grading and demo reliability.
- **Zero Database:** Lightweight, session-based in-memory processing.

## 5. The AI / Computation Boundary (Core Scientific Principle)
| Layer | Responsibility | What It NEVER Does |
|---|---|---|
| **AI (Gemini Flash)** | Intent parsing, mapping questions to columns, selecting test type, formulating natural language interpretation. | **Never computes, estimates, or invents numbers or p-values.** |
| **Python (SciPy / Pandas)** | Data filtering, sample size ($n$) checks, group means, standard deviations, exact $p$-values, effect sizes, Plotly chart generation. | Never hallucinates; 100% mathematically deterministic. |

Every numerical claim in the UI is traced directly to the backend Python computation output.

## 6. How to Run Locally

### Prerequisites
- Python 3.10+
- Node.js 18+

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/your-username/biodata-copilot.git
cd biodata-copilot

# (Optional) Set your Gemini API key in .env
cp .env.example .env
# Edit .env and insert your GEMINI_API_KEY
```
*(Note: If no API key is provided, BioData Copilot automatically activates its built-in deterministic planning engine, allowing full offline operation!)*

### Step 2: Install Python Dependencies & Run Tests
```bash
pip install -r requirements.txt
python -m pytest backend/tests/ -v
```

### Step 3: Start the Backend Server
```bash
uvicorn backend.main:app --reload --port 8000
```
Backend will be live at `http://127.0.0.1:8000`.

### Step 4: Start the Frontend Application
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at **`http://localhost:5173`**.

---

## 7. Using the Synthetic Demo Dataset
A pre-packaged cell-viability assay is included in [`data/synthetic_viability.csv`](data/synthetic_viability.csv):
- **127 observations**, 4 treatments (`Control`, `Drug A`, `Drug B`, `Drug C`), 3 doses (`10`, `50`, `100` µM), 3 replicates across timepoints.
- Click **"Try Example Dataset"** in the app to mount it instantly.

### Supported Example Questions:
1. *"Which treatment produced the highest cell viability compared with control?"* → Selects One-way ANOVA, identifies Drug B (+3.6 pp, $p < 0.05$), and renders a publication-grade box plot.
2. *"Is Drug B significantly different from Control?"* → Selects Welch's Two-Sample t-test / Mann-Whitney U and plots mean comparison with error bars.
3. *"How does viability change with dose?"* → Identifies dose concentration and renders a dose-response scatter/trend plot with Pearson correlation.
4. *"Can you predict patient survival from this dataset?"* → Refuses gracefully with a clear message explaining supported comparative modes.

---

## 8. Known Limitations & Scientific Guardrails
- **Descriptive & Comparative Scope:** Currently focused on group summaries, two-group tests, one-way ANOVA, and linear dose trends. Longitudinal mixed-effects models and 4-parameter logistic (4PL) IC50 fitting are slated for post-hackathon versions.
- **Sample Size Safeguard:** Requires $n \ge 2$ per condition for inferential statistics.
- **Causality & Demonstration Disclaimers:** All outputs persistently display:
  > *This describes the observed experiment and does not establish causality.*  
  > *Notice: Synthetic demonstration data — not real experimental results.*

---

## 9. Hackathon Planning Documents
All planning and specification documents generated during the Devpost Learn workflow are preserved in the repository root:
- [`scope.md`](scope.md) — Scope definition, core loop, and POC boundaries.
- [`prd.md`](prd.md) — Screen walkthroughs, behavioral requirements, and acceptance criteria.
- [`spec.md`](spec.md) — Technical architecture, API schemas, and component design.
- [`devpost/checklist.md`](devpost/checklist.md) — Build slices progress tracker.
