---
doc: scope
status: approved
---

# BioData Copilot

A focused web app for biology and biotech researchers that turns natural-language questions about experimental data into verifiable Python calculations, visualizations, and scientific explanations.

## The Unique Kernel
**"LLM reasons; Python computes."** The LLM translates user intent into an executable statistical plan, while deterministic Python performs all data filtering, math, statistical testing, and plotting. The LLM never invents numbers; every reported metric is mathematically verified from the backend computation.

## Who It's For
A biology or biotech bench researcher with an experimental dataset (e.g., cell viability, dose-response assays) who wants to explore hypotheses and compare experimental groups quickly without writing boilerplate Pandas/SciPy code or manually formatting charts.

## The Core Loop
1. Upload experimental CSV (or click "Try example dataset").
2. Inspect the dataset summary (observations, treatments, doses, replicates, columns).
3. Ask a plain-English scientific question (or pick a suggested prompt).
4. Watch the transparent analysis steps (inspecting -> selecting analysis -> running calculation -> rendering plot).
5. Review the verified numerical result, interactive visualization, and concise, grounded scientific interpretation.

## Inspiration & Identity
- **Feel:** High-end scientific data workbench. Clean, modern, distraction-free laboratory aesthetic (slate/emerald palette, sharp typography, generous whitespace).
- **Tone:** Rigorous, objective, cautious. Avoids overclaiming or asserting causality.
- **Reference:** Modern computational notebooks and biotech analysis tools (e.g., Benchling, Observable) combined with intuitive AI guidance.

## Why This Matters to the Learner
Learning how to effectively build with AI agents and discovering practical, trustworthy ways AI can empower daily scientific workflows while maintaining strict computational rigor.

## What "Working" Looks Like
A researcher loads a synthetic cell-viability CSV, asks: *"Which treatment produced the highest cell viability compared with control?"*, sees transparent step-by-step progress, receives an exact mean viability, relative difference compared with control, a verified statistical test (e.g., One-way ANOVA or t-test), a clean visualization, and a grounded explanation explicitly noting the synthetic nature of the data.

## The POC Boundary
**Included in this build:**
- Single-page web application (React + Vite + Tailwind CSS + Plotly frontend; Python + FastAPI backend)
- Synthetic biotech dataset (`sample_id`, `cell_line`, `treatment`, `dose`, `timepoint`, `replicate`, `viability`) with instant "Try Example Dataset" button
- CSV upload & dataset inspection tool (row count, columns, types, missingness, group detection)
- Focused statistical analysis tools (descriptive stats/means/medians/SD, group comparison: two-group t-test, Mann-Whitney U, one-way ANOVA)
- Deterministic visualization generation (box plots, bar charts with error bars, scatter/dose-response, line plots)
- Structured AI analysis planning and grounded interpretation generation using Gemini API
- Transparent step-by-step analysis activity UI
- Scientific guardrails (check sample sizes, missingness, no hallucinated metrics, synthetic data disclaimer, causality disclaimer)

## Later
- Multi-dataset joins and longitudinal time-course modeling
- Advanced multivariate statistics (two-way ANOVA, mixed-effects models, non-linear dose-response curve fitting / IC50)
- Exporting reproducible Python scripts/Jupyter notebooks of the executed analysis
- Automated outlier detection and normality test recommendations

## Explicitly Cut
- **User authentication and accounts:** Unnecessary overhead for a local proof-of-concept.
- **Persistent databases:** In-memory / session-based data processing is faster and self-contained.
- **RAG / external literature search:** Distracts from experimental data verification.
- **Multi-agent or autonomous coding loops:** Unpredictable and slow; single-purpose deterministic tools ensure 100% reliability.
- **Dozens of statistical tests:** Limiting to core experimental comparisons guarantees robustness.
- **Arbitrary code execution:** LLM cannot run arbitrary unvetted code; only predefined, validated Python functions execute.
