# BioData Copilot 🧬

> **BioData Copilot is an AI agent that plans and adapts reproducible analysis workflows for experimental biotech datasets.**  
> *"LLM reasons; Python computes."*

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Tests: Pytest](https://img.shields.io/badge/Tests-23%2F23%20Passing-brightgreen.svg)](backend/tests/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2F%20SciPy-009688.svg)](backend/)
[![React 18](https://img.shields.io/badge/Frontend-React%2018%20%2F%20Plotly-61DAFB.svg)](frontend/)

---

## 90-Second Demo & Pitch
When bench scientists analyze cell-viability or dose-response assays, traditional chatbots often hallucinate numbers or invent $p$-values. BioData Copilot eliminates this by enforcing a hard architectural boundary:
- **LLM acts as the planner and reasoner:** Decides what information is needed, selects structured tools, adapts based on evidence, and synthesizes grounded explanations.
- **Python acts as the verified computer:** SciPy and NumPy deterministically calculate all statistics ($p$-values, effect sizes, Tukey HSD contrasts, Pearson correlations), while Plotly renders publication-grade charts.

---

## Why It Matters
- **Zero Hallucinated Numbers:** Every statistic displayed originates directly from verified Python tools.
- **Adaptive Workflows:** Unlike fixed scripts, the agent dynamically adapts its tool execution plan depending on whether the user asks a pairwise question, a descriptive summary question, or a filtered dose-response question.
- **Rigorous Scientific Semantics:** Pairwise comparisons strictly contrast target treatments against reference controls (e.g. `Drug B vs Control`), preventing "top performer" ranking conflation.

---

## How It Works

```
                     ┌──────────────────┐
                     │   User Question  │
                     └────────┬─────────┘
                              ↓
                     ┌──────────────────┐
                     │   Gemini Agent   │
                     │  Planner/Router  │
                     └────────┬─────────┘
                              ↓
                     ┌──────────────────┐
                     │    Validation    │
                     │ Python Arguments │
                     └────────┬─────────┘
                              ↓
      ┌───────────────────────┼───────────────────────┐
      ↓                       ↓                       ↓
inspect_dataset         filter_dataset          compare_groups
(Schema & dimensions)   (Treatment subset)     (SciPy t-test/ANOVA)
      │                       │                       │
      └───────────────────────┼───────────────────────┘
                              ↓
                     ┌──────────────────┐
                     │  Python / SciPy  │
                     │  Deterministic   │
                     │   Computation    │
                     └────────┬─────────┘
                              ↓
                     ┌──────────────────┐
                     │ Structured Facts │
                     │  + Exact Stats   │
                     └────────┬─────────┘
                              ↓
                     ┌──────────────────┐
                     │ Agent Evaluates  │
                     │ Evidence Suffic. │
                     └────────┬─────────┘
                              ↓
                    ┌───────────────────┐
                    │  Verified Result  │
                    │   + Plotly Spec   │
                    └───────────────────┘
```

---

## Agent Architecture: LLM → Tool → Python → Result → LLM

1. **Inspect State:** Agent evaluates dataset columns, sample sizes, and user intent.
2. **Select Tool:** Proposes a structured tool call (`inspect_dataset`, `filter_dataset`, `check_assumptions`, `summarize_groups`, `compare_groups`, `create_visualization`).
3. **Python Execution Authority:** Python verifies that columns exist, treatment names match, and sample sizes meet criteria before executing.
4. **Evaluate Evidence:** Agent inspects computed numerical outputs and determines if additional analysis or visualization is required.
5. **Entity Validation Safeguard:** Verbalized explanations are validated by the backend to ensure only target entities are discussed; if entity mismatch occurs, the system automatically falls back to deterministic phrasing.

---

## Workflow Examples

### Example 1 — Pairwise Inferential Question
**User:** *"Is Drug B significantly different from Control?"*
- **Agent Trace:**
  1. `inspect_dataset` → 127 observations, 4 treatments, 3 doses
  2. `check_assumptions` → Sample sizes verified ($n \ge 3$); variance checked
  3. `compare_groups` → Welch's Two-Sample t-test ($p = 0.0003$)
  4. `create_visualization` → Publication bar chart with SEM
- **Verified Result:** `Drug B vs Control` (+4.04 percentage points, $p < 0.001$).

### Example 2 — Descriptive Question
**User:** *"Which treatment has the highest mean viability?"*
- **Adaptive Workflow:**
  1. `inspect_dataset` → Schema mapped
  2. `summarize_groups` → Mean, SD, SEM, median across treatments
  3. `create_visualization` → Bar distribution
  - *(Notice: No unnecessary hypothesis test executed!)*
- **Verified Result:** Drug B produced highest mean viability at 95.09%.

### Example 3 — Filtered Dose-Response Question
**User:** *"How does Drug B respond to dose?"*
- **Adaptive Workflow:**
  1. `inspect_dataset` → Schema mapped
  2. `filter_dataset` → Restricts rows strictly to `{"treatment": ["Drug B"]}`
  3. `compare_groups` → Pearson correlation & linear regression slope on filtered subset
  4. `create_visualization` → Scatter plot with trendline
- **Verified Result:** Negative dose correlation ($r = -0.584, p < 0.001$).

---

## Tech Stack
- **AI Planning Layer:** Google Gemini API (`gemini-3.5-flash-lite`) with native Structured Outputs (`responseSchema`).
- **Deterministic Python Fallback:** Built-in state machine provides full functionality even if API is offline.
- **Scientific Computing Engine:** SciPy (`scipy.stats` for Welch's t-test, One-way ANOVA, Tukey HSD post-hoc contrasts, Pearson correlation, linear regression), Pandas, NumPy.
- **Backend API:** FastAPI, Uvicorn, Pydantic, HTTPX.
- **Frontend User Interface:** React 18, Vite, Plotly.js (`react-plotly.js`), Lucide Icons.

---

## Scientific Guardrails

| Guardrail | Purpose | Implementation |
|---|---|---|
| **Entity Validation** | Eliminates drug hallucination (e.g. discussing Drug A when Drug B was analyzed). | Explanation entity check rejects invalid drug mentions and falls back to deterministic template. |
| **Defensible Assumption Language** | Avoids overclaiming parametric validity. | Reports: *"No large variance imbalance detected; normality was not formally assessed."* |
| **ANOVA vs Pairwise Distinction** | Avoids falsely inferring pairwise significance from overall ANOVA. | Runs post-hoc Tukey HSD and reports contrasts adjusted for family-wise error rate ($p_{\text{adj}}$). |
| **Causality & Demonstration Notice** | Research transparency. | Persistent banner: *"This describes the observed experiment and does not establish causality. Synthetic demonstration data."* |

---

## Running Locally

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/andrewlee23023-maker/BioData-Copilot.git
cd BioData-Copilot

# Optional: Add your Gemini API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key
```
*(Deterministic Python analysis provides a reliable fallback when the LLM is unavailable).*

### 2. Run Test Suite (23 Passing Tests)
```bash
pip install -r requirements.txt
python -m pytest backend/tests/ -v
```

### 3. Start Backend Server
```bash
python -m uvicorn backend.main:app --reload --port 8000
```
API running at `http://127.0.0.1:8000`.

### 4. Start Frontend
```bash
cd frontend
npm install
npm run dev
```
Open your browser at **`http://localhost:5173`**.

---

## Project Structure
```
biodata-copilot/
├── backend/
│   ├── main.py              # FastAPI endpoints (/api/load-demo, /api/analyze)
│   ├── agent.py             # Agent reasoning loop, tool registry & entity validation
│   ├── tools/
│   │   ├── inspect.py       # Generalized dataset schema inspection
│   │   ├── filter.py        # Dataset filtering tool
│   │   ├── stats.py         # SciPy hypothesis tests & descriptive stats
│   │   └── viz.py           # Plotly interactive chart specifications
│   └── tests/               # 23 comprehensive pytest regression tests
├── frontend/
│   ├── src/
│   │   ├── components/      # ResultDeck, AnalysisActivity, DatasetWorkbench
│   │   ├── App.jsx          # Main application container
│   │   └── index.css        # Scientific biotech styling & design system
├── data/
│   └── synthetic_viability.csv # 127-row cell viability assay dataset
├── LICENSE                  # MIT License
└── README.md                # Project documentation
```

---

## License
BioData Copilot is open-source under the [MIT License](LICENSE).
