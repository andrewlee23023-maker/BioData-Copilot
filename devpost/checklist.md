---
doc: checklist
status: approved
---

# Build Checklist

Build mode: learn

## Slices

- [ ] **1. Synthetic Dataset & Deterministic Analytical Backend**
  Becomes usable: A runnable FastAPI backend (`:8000`) and the synthetic 127-row cell-viability assay dataset (`data/synthetic_viability.csv`). Endpoints `/api/health`, `/api/load-demo`, `/api/upload`, and core Python analytical tools (`inspect_dataset`, `summarize_groups`, `compare_groups` with ANOVA/t-test, `generate_plotly_spec`) execute deterministically with pytest verification passing.
  Why now: The kernel is "Python computes; LLM reasons". Establishing the mathematically verified computational foundation and synthetic dataset first guarantees that all subsequent AI planning and UI layers have real, verifiable data to build upon.
  PRD ref: `prd.md > 1. Dataset Upload & Inspection`, `prd.md > 3. Deterministic Statistical Computation`
  Spec ref: `spec.md > Backend Modules`, `spec.md > Data Model`
  Build: Scaffold `backend/` and `data/`, generate realistic 127-observation synthetic viability CSV, implement inspection and statistical testing tools using SciPy/Pandas, implement Plotly JSON generator, and write pytest unit tests.
  Verify (mechanical): Run `pytest backend/tests/test_stats.py` and verify all tests pass; start FastAPI server and test `curl http://localhost:8000/api/health` and `/api/load-demo`.
  Learner check: Run the backend test command and see all statistical tests (ANOVA, t-test, descriptive means) calculate the exact numbers from the synthetic dataset.
  Commit: `Implement analytical backend, synthetic viability dataset, and statistical tests`

- [ ] **2. AI Analysis Planning & Grounded Interpretation Pipeline**
  Becomes usable: The AI reasoning boundary is connected: an incoming natural-language question is translated into a validated JSON analysis plan by Gemini Flash (with offline rule fallback), the backend validates and executes the requested test, and a strictly grounded scientific explanation is generated citing only the verified Python numbers.
  Why now: Proves the complete AI/Python boundary end-to-end on the command line / API level before building the frontend interface.
  PRD ref: `prd.md > 2. Natural Language Question Processing & AI Planning`, `prd.md > 4. Grounded Scientific Interpretation`
  Spec ref: `spec.md > How This Works, In Plain Language`, `spec.md > AI / Python Boundary`
  Build: Create `backend/agent.py` implementing structured intent extraction, schema validation, and grounded result synthesis with required disclaimers. Expose `POST /api/analyze`.
  Verify (mechanical): Run automated API integration test querying "Which treatment produced the highest cell viability compared with control?" and assert that response contains verified mean viability, ANOVA p-value, Plotly spec, and non-causal disclaimer.
  Learner check: Send a test query to the `/api/analyze` endpoint and observe the AI plan and grounded explanation returned with exact Python-calculated numbers.
  Commit: `Add AI intent planner, grounded explainer, and analyze endpoint`

- [ ] **3. Frontend Workbench — Dataset Ingestion & Summary UI**
  Becomes usable: A running React + Vite + Tailwind frontend (`:5173`) featuring the dark laboratory workbench aesthetic, a drag-and-drop CSV upload zone, a 1-click "Try Example Dataset" button, and instant dataset summary cards (observations, treatments, doses, columns).
  Why now: Provides the visual entry point and first screen (Screen A) of the user journey, connected live to the backend API.
  PRD ref: `prd.md > Screens and Layout`, `prd.md > 1. Dataset Upload & Inspection`
  Spec ref: `spec.md > Frontend Components`, `spec.md > Look and Feel`
  Build: Initialize Vite React app in `frontend/`, configure Tailwind CSS and colors, implement `Header.jsx` and `DatasetWorkbench.jsx`, and wire API calls to `POST /api/load-demo` and `POST /api/upload`.
  Verify (mechanical): Run `npm run build` in `frontend/` to confirm clean compilation; start Vite dev server and check that loading the page returns HTTP 200 and loads demo dataset via API.
  Learner check: Open `http://localhost:5173`, click "Try Example Dataset", and see the 127 observations, 4 treatments, 3 doses, and column chips render immediately.
  Commit: `Build frontend workbench layout, upload component, and dataset summary cards`

- [ ] **4. Full Interactive Loop — Question Console, Live Stepper, Plotly Charts & Results**
  Becomes usable: The complete end-to-end application. The user can type a question or click suggested question chips, watch the live analysis stepper update in real time, and view high-impact result cards, an interactive Plotly visualization, and the grounded scientific interpretation.
  Why now: Delivers the final screens (Screens B, C, D) and closes the entire core loop for the hackathon proof-of-concept.
  PRD ref: `prd.md > The Core Journey` (steps 3-5), `prd.md > Screen C`, `prd.md > Screen D`
  Spec ref: `spec.md > Components`, `spec.md > ResultDeck.jsx`
  Build: Implement `QuestionConsole.jsx`, `AnalysisActivity.jsx`, and `ResultDeck.jsx` with `react-plotly.js`. Connect the full query flow to `POST /api/analyze` and handle unsupported queries and error states gracefully.
  Verify (mechanical): Submit query "Which treatment produced the highest cell viability compared with control?", verify progress steps transition, verify Plotly chart mounts, and verify stat cards render exact ANOVA numbers. Test unsupported query refusal.
  Learner check: Run through the complete user workflow: Click example dataset, click "Which treatment has the highest viability?", click "Analyze →", and explore the resulting interactive Plotly chart and scientific interpretation.
  Commit: `Complete end-to-end workflow with question console, live stepper, and Plotly visualization`

## Hands-on Checkpoints

- [ ] Early usable behavior explored — Slice 2 (API-level verification of AI planner & Python computation)
- [ ] Final kick-the-tires exploration and feedback completed — Slice 4 (Full web app UI walkthrough)

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [ ] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: [to be recorded upon completion]
Route and stops: [to be recorded upon completion]
Edit outcome: [to be recorded upon completion]
Reflection: [to be recorded upon completion]
Activity mode: [to be recorded upon completion]

## Revisions

