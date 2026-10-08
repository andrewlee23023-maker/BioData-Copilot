---
doc: prd
status: approved
---

# BioData Copilot — Product Requirements

A focused web application for biology and biotechnology researchers that transforms plain-English questions about experimental tabular datasets into verified Python statistical computations, publication-ready visualizations, and grounded scientific interpretations.
Source: `scope.md > The Unique Kernel` and `scope.md > The Core Loop`.

## The Core Journey
1. **Landing & Dataset Upload (Screen A):** The researcher opens the web app and is greeted by a clean, scientific workspace. They can either upload their experimental CSV or click **"Try Example Dataset"** (a synthetic 127-observation cell-viability assay).
2. **Dataset Inspection:** The app immediately parses and validates the CSV. It displays a clear dataset summary: observation count (127), group counts (4 treatments, 3 doses, 3 replicates), and a compact list of detected columns and data types.
3. **Question Formulation (Screen B):** The researcher enters a natural-language scientific question in a prominent input box (e.g., *"Which treatment produced the highest cell viability compared with control?"*), or selects one of 3 pre-populated example prompts.
4. **Transparent Analysis Activity (Screen C):** Clicking **"Analyze →"** transitions the UI into a real-time progress tracker. The user sees concrete backend checkpoints:
   - ✓ Inspecting dataset & verifying columns
   - ✓ Identifying experimental groups & reference
   - ✓ Checking sample sizes & missingness
   - → Running statistical analysis (e.g., One-way ANOVA / t-test)
   - ○ Generating interactive visualization
   - ○ Synthesizing grounded scientific interpretation
5. **Results & Grounded Scientific Explanation (Screen D):** The app presents:
   - A primary stat summary card (e.g., "Drug B produced the highest mean cell viability: 95.09%, +4.04 pp vs Control, p < 0.001 via One-way ANOVA with Tukey HSD post-hoc")
   - An interactive Plotly chart (box plot, bar with error bars, or dose-response scatter)
   - An **Analysis Trace** (what the backend did: dataset inspected, groups identified, sample sizes checked, assumptions checked, test executed or blocked, result validated) and a **Statistical Audit** (selected test, groups, n, means, difference, p-value, and which parts were computed by Python vs interpreted by Gemini). Both are returned with the finished result, not streamed live.
   - A concise scientific interpretation strictly grounded in the computed output
   - Explicit scientific disclaimers: synthetic demonstration data notice and non-causality disclosure.

## Screens and Layout
A unified single-page responsive layout with distinct functional sections:
- **Header:** App title ("BioData Copilot"), subtitle ("Ask questions about your experimental data"), and clear badge ("Synthetic Demo Ready").
- **Section 1: Data Workbench:** Drag-and-drop CSV upload zone, "Try Example Dataset" button, and instant dataset summary cards (Observations, Treatments, Doses, Columns detected).
- **Section 2: Question Console:** Large, accessible query input with "Analyze →" action button and quick-fill clickable sample questions.
- **Section 3: Analysis Activity Stream:** Live stepper indicating real backend execution states without fake delays.
- **Section 4: Result Deck:** High-impact metric cards, interactive Plotly visualization canvas, statistical parameter breakdown, and structured interpretation text with scientific caveats.

## Look and Feel
- **Aesthetic:** Modern computational biology workbench (inspired by Benchling, Streamlit, and Nextflow web tools).
- **Color Palette:** Deep slate/navy background (`#090d16` / `#111827`), crisp emerald green (`#10b981`) for scientific verification/positive delta, cyan (`#06b6d4`) for AI reasoning accents, muted slate (`#9ca3af`) for secondary text.
- **Typography:** Clean, highly legible sans-serif (`Inter` or system fonts), tabular numerals for statistical alignment, and monospace styling for variable/column names.
- **Tone:** Objective, rigorous, restrained. No chatty filler; no exaggerated claims.

## Features and Behavior

### 1. Dataset Upload & Inspection
- **Upload CSV:** Accepts RFC 4180 compliant CSV files up to 25MB.
- **Synthetic One-Click Demo:** Loads a realistic pre-configured cell-viability assay with 127 observations, 4 treatments (Control, Drug A, Drug B, Drug C), 3 doses, 3 replicates, and viability percentages.
- **Validation:** Inspects row count, column headers, numerical vs. categorical data types, and null/missing values.
- *Acceptance Criteria:*
  - [ ] Uploading valid CSV or clicking example dataset displays row count and column chips within 500ms.
  - [ ] Malformed or non-CSV files display a friendly error banner without page crash.

### 2. Natural Language Question Processing & AI Planning
- **Question Input:** Text box with character support and suggested question chips:
  - *"Which treatment has the highest viability?"*
  - *"Is Drug B significantly different from Control?"*
  - *"How does viability change with dose?"*
- **Structured Plan Generation:** The Gemini planner maps the question to a structured tool call (tool + arguments such as `group_column`, `value_column`, `test_type`, `ref_group`, `target_group`). Python validates every plan (known tool, existing columns, supported test, no repeated tools); invalid plans are rejected and the deterministic planner is used instead.
- *Acceptance Criteria:*
  - [ ] Clicking a suggested chip immediately fills the question field.
  - [ ] The AI outputs valid JSON specifying the analysis without performing mathematical calculation itself.
  - [ ] A Gemini plan that names an unknown tool, missing column, or unsupported test is rejected by Python and recorded in the trace.

### 3. Deterministic Statistical Computation (Python Engine)
- **Supported Tests:**
  - Group Summaries: mean, median, standard deviation, count (n).
  - Two-Group Comparison: Welch's t-test, Mann-Whitney U test.
  - Multi-Group Comparison: One-way ANOVA with Tukey HSD post-hoc comparison.
  - Dose / Trend: Pearson correlation and linear regression across a numeric dose column.
- **Deterministic Plots:** Generates interactive Plotly specification (JSON) for box plots, bar charts with SEM/SD error bars, and dose-response scatter/line charts.
- *Acceptance Criteria:*
  - [ ] All reported means, differences, test statistics (F, t, U), and p-values are computed directly by SciPy/Pandas.
  - [ ] **Statistical gate:** before any inferential test, Python verifies the columns exist, the measurement is numeric, at least 2 valid groups exist, the comparison is valid, variance is non-zero, and **n ≥ 3 in every compared group**. If any check fails, the test is not run; the result lists structured blocked reasons and still includes descriptive statistics. The gate lives in the stats code, so the LLM planner cannot bypass it.
  - [ ] Variance imbalance is reported as a warning (not a block); normality is stated as "not formally assessed".

### 4. Grounded Scientific Interpretation
- **AI Synthesis:** AI receives the exact structured numerical result from Python and generates a concise 2–3 sentence biological summary.
- **Guardrails:**
  - Mandatory disclaimer: *"Synthetic demonstration data — not real experimental results."*
  - Mandatory causal limitation: *"This describes the observed experiment and does not establish causality."*
  - Zero hallucination rule: No numeric value appears in the explanation that wasn't in the Python output. Explanations are entity-validated; on mismatch, a deterministic template is used and the audit labels the interpretation source.
  - Blocked analyses are always explained by a fixed template (never by the LLM) and state that no conclusion about group differences can be drawn.
- *Acceptance Criteria:*
  - [ ] The interpretation references the computed p-value and group difference accurately.
  - [ ] The disclaimers are visibly displayed below the result card.

## States and Boundaries
- **Initial / Empty State:** No dataset loaded; upload zone and "Try Example Dataset" button prominent. Question box disabled with placeholder prompt.
- **Dataset Loaded State:** Dataset metadata active. Question box enabled. Example questions clickable.
- **Analyzing State:** Action button disabled with spinner. Stepper shows active backend steps.
- **Results State:** Results deck expands with animated entry. Chart rendered and responsive.
- **Error State (Unsupported Question):** E.g., user asks *"Predict patient survival from this dataset"*. App returns: *"This demo currently supports descriptive analyses, group comparisons, correlations, and basic experimental trends."*
- **Error State (Missing Column):** E.g., user asks *"Compare expression levels"*. App returns: *"I couldn't find an expression measurement in this dataset."*
- **Blocked State (Inadequate Data):** E.g., a compared group has n < 3. The inferential test is not run; the audit shows "None: the test was not run", the blocking reasons, and descriptive means with n.
- **Upload Limit:** Files over 25 MB are rejected with HTTP 413 and a friendly message.

## Product Decisions
- **Predefined Analysis Tools Only:** Arbitrary Python code execution from LLMs was rejected due to safety and unpredictability; a small registry of validated tools (inspect, filter, check assumptions, summarize, compare, visualize) keeps results reproducible.
- **Gemini reasons; Python computes:** Gemini proposes plans and explains verified results; Python validates plans, enforces the statistical gate, and performs every calculation. Gemini cannot override a failed guardrail.
- **Pre-packaged Synthetic Dataset:** Built directly into the app so judges and reviewers can test the complete loop in 5 seconds with zero setup.
- **Plotly for Visualizations:** Chosen over static PNGs so users can hover over data points, inspect replicate values, and zoom.

## What We're Building (POC)
- Complete single-page application with FastAPI backend and React + Plotly frontend.
- Synthetic cell-viability assay generator/loader.
- 6 backend tools (inspect, filter, check assumptions, summarize, compare, plot) behind a validated registry.
- Gemini API planner & grounded explainer with a deterministic offline fallback (model configurable via `GEMINI_MODEL`).
- Statistical gate, Analysis Trace, and Statistical Audit.
- A pytest suite covering guardrails, plan validation, explanation grounding, upload limit, CORS, and session limits.

## Deferred From the POC
- Custom chart styling editor (color picker, axis range adjustments).
- Multi-dataset merge / join workflows.
- User account creation and cloud project saving.

## Non-Goals
- Generating arbitrary Python scripts for unrestricted execution.
- Literature search or PubMed retrieval.
- Complex multi-agent conversations.
- Fitting multi-parameter pharmacological models (e.g., non-linear 4PL curves) for the initial MVP.

## Open Questions
- None blocking. Gemini API key is read from `GEMINI_API_KEY`; the model from `GEMINI_MODEL`.
