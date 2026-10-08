# BioData Copilot 🧬

> **Ask plain-English questions about your experimental data. Get verified statistics, not hallucinated ones.**  
> *"Gemini reasons; Python computes."*

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Tests: pytest](https://img.shields.io/badge/Tests-pytest-brightgreen.svg)](backend/tests/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2F%20SciPy-009688.svg)](backend/)
[![React 18](https://img.shields.io/badge/Frontend-React%2018%20%2F%20Plotly-61DAFB.svg)](frontend/)

---

## 90-Second Demo

1. **Click "Try Example Dataset"**: a synthetic cell-viability assay (127 observations, 4 treatments, 3 doses).
2. **Ask:** *"Is Drug B significantly different from Control?"*
3. **Read the result:**
   - **Analysis Trace**: what the backend did: dataset inspected → groups identified → sample sizes checked → assumptions checked → test executed → result validated.
   - **Statistical Audit**: test, groups, n, means, difference, p-value, and who computed / interpreted what.
   - An interactive Plotly chart and a short, grounded explanation.
4. **Try to break it.** Upload a CSV where one group has only 2 replicates and ask the same question. The test is **blocked**, the audit says why, and you still get descriptive statistics.

More questions to try: *"Which treatment has the highest mean viability?"* · *"How does Drug B respond to dose?"* · *"Are treatments significantly different overall?"* · *"Can you predict patient survival?"* (politely refused)

---

## Gemini reasons; Python computes

Chatbots invent p-values. BioData Copilot draws a hard line between what the LLM may do and what only Python may do:

1. **Gemini interprets the scientific question** and proposes a structured analysis plan (which tool, which columns, which test).
2. **Python validates the plan.** Unknown tools, missing columns, unsupported tests, or malformed plans are rejected; the deterministic planner takes over.
3. **Python performs every calculation** (SciPy / pandas / NumPy) after enforcing the scientific guardrails.
4. **Gemini explains the verified result.** Its text is checked against the computed entities and falls back to a fixed template if it drifts.
5. **Gemini cannot override the guardrails.** The statistical gate lives inside the Python stats code, so no plan, tool order, or prompt can run a test whose conditions failed.

No `GEMINI_API_KEY`? The deterministic fallback planner and explanation templates keep the whole demo working offline.

---

## How It Works

```
 User question
      ↓
 Gemini (planner)         → proposes a structured plan
      ↓
 Python plan validation   → rejects unknown tools / columns / tests / malformed plans
      ↓
 Python statistical gate  → n ≥ 3 per group, numeric data, valid groups & comparison
      │                       FAIL → inferential test blocked (descriptive stats still returned)
      ↓ PASS
 SciPy computation        → Welch t-test · ANOVA + Tukey · dose trend · descriptive stats
      ↓
 Gemini (explainer)       → explains ONLY the verified numbers; Python entity-checks the text
      ↓
 Result + Plotly spec + Analysis Trace + Statistical Audit
```

---

## Supported Analyses

| Analysis | Method |
|---|---|
| Descriptive group summaries | n, mean, SD, SEM, median, min, max |
| Two-group comparison | Welch's two-sample t-test; Mann-Whitney U (selectable by the Gemini planner) |
| Multi-group comparison | One-way ANOVA with Tukey HSD post-hoc |
| Dose / trend | Pearson correlation + linear regression (numeric dose column) |

Not supported (by design, for this MVP): Student's t-test, Spearman correlation, two-way ANOVA, IC50 / 4PL curve fitting, survival or predictive modeling. Unsupported questions get a clear refusal.

---

## Scientific Guardrails

| Guardrail | What it does |
|---|---|
| **Statistical gate** | Before any inferential test: columns exist, measurement is numeric, ≥ 2 valid groups, valid comparison (no unknown or identical groups), non-zero variance, and **n ≥ 3 in every compared group**. If anything fails, the test does not run; the result carries structured `blocked_reasons` and descriptive statistics only. |
| **Plan validation** | Every Gemini-proposed tool call is validated by Python. Invalid plans are rejected, logged in the trace, and replaced by the deterministic planner. |
| **Entity validation** | Explanations may only discuss the groups actually compared; mismatches fall back to a template. Blocked analyses are always explained by a fixed template. |
| **ANOVA vs pairwise** | Post-hoc Tukey HSD is reported, so overall ANOVA significance is never mistaken for a specific drug-vs-control effect. |
| **Honest assumption language** | Variance imbalance is reported as a warning (it does not block). Normality is *not* formally assessed, and the app says so. |
| **Causality & demo notice** | Every interpretation states that it does not establish causality and that the demo data is synthetic. |

---

## Workflow Examples

### 1. Pairwise question
**"Is Drug B significantly different from Control?"** → `inspect_dataset` → `check_assumptions` → `compare_groups` (Welch's t-test) → `create_visualization`  
**Verified result:** Drug B vs Control, +4.04 percentage points, p < 0.001.

### 2. Descriptive question (no unnecessary hypothesis test)
**"Which treatment has the highest mean viability?"** → `inspect_dataset` → `summarize_groups` → `create_visualization`  
**Verified result:** Drug B, mean viability 95.09.

### 3. Filtered dose-response question
**"How does Drug B respond to dose?"** → `inspect_dataset` → `filter_dataset` (Drug B only) → `compare_groups` (dose trend) → `create_visualization`  
**Verified result:** slight positive dose correlation (r = 0.483, p = 0.004).

### 4. Blocked analysis
Group with n = 2, then **"Is Drug C significantly different from Control?"** → `check_assumptions` flags the group → `compare_groups` refuses to run the test.  
**Result:** no p-value; reason shown (*"Every compared group needs n >= 3; too small: Drug C (n = 2)"*); descriptive means and n still displayed.

---

## Running Locally

**Prerequisites:** Python 3.10+, Node.js 18+

```bash
git clone https://github.com/andrewlee23023-maker/BioData-Copilot.git
cd BioData-Copilot

# Backend
pip install -r requirements.txt
cp .env.example .env          # optional: add GEMINI_API_KEY for Gemini planning/explanations
python -m pytest backend/tests/ -v
python -m uvicorn backend.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                   # open http://localhost:5173
```

### Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | Enables Gemini. Without it, the deterministic fallback is used. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model used for planning and explanations. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed CORS origin(s); comma-separate several. |
| `MAX_SESSIONS` | `50` | In-memory dataset sessions kept (oldest-used evicted first). |
| `SESSION_TTL_SECONDS` | `3600` | Idle time before a session expires. |

CSV uploads are limited to **25 MB** (larger files get HTTP 413).

---

## Tech Stack
- **AI layer:** Google Gemini API with structured outputs (`responseSchema`), model set by `GEMINI_MODEL`
- **Deterministic fallback:** built-in planner + explanation templates (works fully offline)
- **Computation:** SciPy (`ttest_ind` Welch, `f_oneway`, `tukey_hsd`, `mannwhitneyu`, `pearsonr`, `linregress`), pandas, NumPy
- **Backend:** FastAPI, Uvicorn, Pydantic, HTTPX
- **Frontend:** React 18, Vite, Plotly.js (`react-plotly.js`), Lucide icons

---

## Known Limitations
- The **Analysis Trace is a record returned with the finished result**, not a live stream.
- Normality is not formally tested; variance imbalance is a warning, not a block.
- Sessions live in memory only (capped and expiring); restarting the server clears them.
- The example dataset is synthetic and for demonstration only.

---

## Project Structure
```
├── backend/
│   ├── main.py              # FastAPI: upload (25 MB cap), CORS, bounded sessions, /api/analyze
│   ├── agent.py             # Planner, plan/tool validation, explanation grounding, trace & audit
│   ├── tools/
│   │   ├── inspect.py       # Dataset schema inspection
│   │   ├── filter.py        # Dataset filtering
│   │   ├── stats.py         # Statistical gate + SciPy tests + descriptive stats
│   │   └── viz.py           # Plotly chart specifications
│   └── tests/               # pytest: guardrails, agent validation, API
├── frontend/src/
│   ├── App.jsx
│   └── components/          # …, AnalysisTraceAudit.jsx (trace + statistical audit)
├── data/synthetic_viability.csv   # 127-row synthetic viability assay
└── generate_data.py         # Regenerates the example dataset (seed 42)
```

---

## License
BioData Copilot is open-source under the [MIT License](LICENSE).
