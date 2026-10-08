import os
import json
import re
import httpx
import pandas as pd
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from backend.tools.inspect import inspect_dataset
from backend.tools.stats import summarize_groups, compare_groups, check_assumptions, MIN_N_PER_GROUP, SUPPORTED_TESTS, TEST_ALIASES
from backend.tools.viz import generate_plotly_spec
from backend.tools.filter import filter_dataset

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Single place to configure the Gemini model (override with GEMINI_MODEL in .env).
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SUPPORTED_CHART_TYPES = ["box", "bar", "scatter"]
_TOOL_ARG_KEYS = {
    "inspect_dataset": set(),
    "filter_dataset": {"filters"},
    "check_assumptions": {"group_column", "value_column", "test_type", "ref_group", "target_group"},
    "summarize_groups": {"group_column", "value_column"},
    "compare_groups": {"group_column", "value_column", "test_type", "ref_group", "target_group"},
    "create_visualization": {"group_column", "value_column", "chart_type"},
}


class ToolRequestError(ValueError):
    """A tool request (from Gemini or anywhere else) failed Python-side validation."""
    def __init__(self, message: str, error_type: str = "invalid_tool_request"):
        super().__init__(message)
        self.error_type = error_type

# ---------------------------------------------------------------------------
# Predefined Validated Tool Registry (LLM cannot execute arbitrary code)
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    "inspect_dataset": {
        "description": "Inspects dataset dimensions, column names, candidate grouping & measurement columns, and missing values.",
        "parameters": {}
    },
    "filter_dataset": {
        "description": "Filters dataset to a specific subset of interest (e.g. particular treatments, timepoints, or doses) before analysis.",
        "parameters": {"filters": "Dict[str, Union[List[Any], Any]]"}
    },
    "check_assumptions": {
        "description": f"Checks sample sizes (n >= {MIN_N_PER_GROUP} per group), missing values, variance spread across groups, and reports normality status. Reports whether inferential testing is allowed.",
        "parameters": {"group_column": "str", "value_column": "str", "test_type": "Optional[str]", "ref_group": "Optional[str]", "target_group": "Optional[str]"}
    },
    "summarize_groups": {
        "description": "Calculates descriptive statistics (mean, std, sem, median, min, max, n) for continuous values grouped by category.",
        "parameters": {"group_column": "str", "value_column": "str"}
    },
    "compare_groups": {
        "description": "Executes deterministic hypothesis testing (One-way ANOVA with Tukey HSD post-hoc, Welch's t-test, Mann-Whitney U, or dose trend correlation). Python re-validates assumptions and sample sizes first and blocks the test if they fail; this cannot be overridden.",
        "parameters": {
            "group_column": "str", 
            "value_column": "str", 
            "test_type": "str (one_way_anova | two_sample_t_test | mann_whitney_u | dose_trend)",
            "ref_group": "Optional[str]",
            "target_group": "Optional[str]"
        }
    },
    "create_visualization": {
        "description": "Generates publication-quality interactive Plotly JSON figure specification.",
        "parameters": {
            "group_column": "str",
            "value_column": "str",
            "chart_type": "str (box | bar | scatter)"
        }
    }
}

REASONER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "status": {
            "type": "STRING",
            "enum": ["continue", "complete"]
        },
        "reason": {
            "type": "STRING"
        },
        "confidence": {
            "type": "STRING",
            "enum": ["high", "medium", "low"]
        },
        "next_action": {
            "type": "OBJECT",
            "properties": {
                "tool": {
                    "type": "STRING",
                    "enum": [
                        "inspect_dataset",
                        "filter_dataset",
                        "check_assumptions",
                        "summarize_groups",
                        "compare_groups",
                        "create_visualization"
                    ]
                },
                "arguments": {
                    "type": "OBJECT",
                    "properties": {
                        "group_column": {"type": "STRING"},
                        "value_column": {"type": "STRING"},
                        "test_type": {"type": "STRING"},
                        "ref_group": {"type": "STRING"},
                        "target_group": {"type": "STRING"},
                        "chart_type": {"type": "STRING"},
                        "filters": {"type": "OBJECT"}
                    }
                }
            }
        }
    },
    "required": ["status", "reason"]
}

# ---------------------------------------------------------------------------
# Tool Execution Engine
# ---------------------------------------------------------------------------
def validate_tool_request(tool_name: Any, arguments: Any, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Python-side validation of ANY tool request (LLM-proposed or deterministic).
    Returns normalized arguments or raises ToolRequestError. Columns are never silently
    substituted: a request for a column that does not exist is an error, not a guess.
    """
    if not isinstance(tool_name, str) or tool_name not in TOOL_REGISTRY:
        raise ToolRequestError(f"Unauthorized tool: '{tool_name}'. Only predefined tools are permitted.")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ToolRequestError(f"Arguments for '{tool_name}' must be an object, got {type(arguments).__name__}.")
    # LLMs often emit empty-string/null placeholders for optional arguments; treat as absent.
    arguments = {k: v for k, v in arguments.items() if v is not None and v != ""}
    unknown = set(arguments) - _TOOL_ARG_KEYS[tool_name]
    if unknown:
        raise ToolRequestError(f"Unexpected argument(s) for '{tool_name}': {sorted(unknown)}.")

    args = dict(arguments)
    cols = list(df.columns)
    for key, default in (("group_column", "treatment"), ("value_column", "viability")):
        if key in _TOOL_ARG_KEYS[tool_name]:
            args.setdefault(key, default)
            if args[key] not in cols:
                raise ToolRequestError(
                    f"Column '{args[key]}' (requested as {key}) not found. Available columns: {cols}.",
                    error_type="missing_column")
    for key in ("ref_group", "target_group", "test_type", "chart_type"):
        if args.get(key) is not None and not isinstance(args[key], str):
            raise ToolRequestError(f"Argument '{key}' must be a string.")
    if tool_name in ("compare_groups", "check_assumptions") and args.get("test_type") is not None:
        if args["test_type"] not in TEST_ALIASES:
            raise ToolRequestError(f"Unsupported test_type '{args['test_type']}'. Supported: {SUPPORTED_TESTS}.")
    if tool_name == "compare_groups":
        args.setdefault("test_type", "one_way_anova")
        args.setdefault("ref_group", "Control")
    if tool_name == "create_visualization":
        args.setdefault("chart_type", "box")
        if args["chart_type"] not in SUPPORTED_CHART_TYPES:
            raise ToolRequestError(f"Unsupported chart_type '{args['chart_type']}'. Supported: {SUPPORTED_CHART_TYPES}.")
    if tool_name == "filter_dataset":
        filters = args.get("filters", {})
        if not isinstance(filters, dict):
            raise ToolRequestError("'filters' must be an object mapping column -> value(s).")
        bad = [c for c in filters if c not in cols]
        if bad:
            raise ToolRequestError(f"Filter column(s) {bad} not found. Available columns: {cols}.",
                                   error_type="missing_column")
        args["filters"] = filters
    return args


def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    df: pd.DataFrame,
    current_stats: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes a predefined, validated Python tool deterministically.
    Rejects any unauthorized tool, invalid arguments, or arbitrary code execution attempt.
    Statistical guardrails live inside the stats tools themselves (compare_groups re-validates
    every request), so they cannot be bypassed by choosing a different tool order.
    """
    arguments = validate_tool_request(tool_name, arguments, df)

    if tool_name == "inspect_dataset":
        return inspect_dataset(df)

    elif tool_name == "filter_dataset":
        filters = arguments.get("filters", {})
        return filter_dataset(df, filters)

    elif tool_name == "check_assumptions":
        return check_assumptions(
            df, arguments["group_column"], arguments["value_column"],
            test_type=arguments.get("test_type"),
            ref_group=arguments.get("ref_group"),
            target_group=arguments.get("target_group"),
        )

    elif tool_name == "summarize_groups":
        grp = arguments.get("group_column", "treatment")
        val = arguments.get("value_column", "viability")
        try:
            raw_summary = summarize_groups(df, grp, val)
        except ValueError as e:
            raise ToolRequestError(str(e))
        if not raw_summary:
            raise ToolRequestError("No groups with data to summarize.")
        top_group = max(raw_summary.items(), key=lambda x: x[1]["mean"])
        ref_group = "Control" if "Control" in raw_summary else (list(raw_summary.keys())[0] if raw_summary else "")
        ref_mean = raw_summary.get(ref_group, {}).get("mean", 0.0) if ref_group else 0.0
        delta = round(top_group[1]["mean"] - ref_mean, 2)
        return {
            "comparison_type": "descriptive",
            "test_name": "Descriptive Group Summary",
            "group_column": grp,
            "value_column": val,
            "top_performer": top_group[0],
            "top_mean": top_group[1]["mean"],
            "reference_group": ref_group,
            "delta_vs_reference": delta,
            "group_summary": raw_summary,
            "guardrails": {
                "causality_disclaimer": "This describes the observed experiment and does not establish causality.",
                "synthetic_disclaimer": "Synthetic demonstration data — not real experimental results."
            }
        }
        
    elif tool_name == "compare_groups":
        grp = arguments.get("group_column", "treatment")
        val = arguments.get("value_column", "viability")
        test = arguments.get("test_type", "one_way_anova")
        ref = arguments.get("ref_group", "Control")
        target = arguments.get("target_group", None)
        return compare_groups(df, grp, val, test_type=test, ref_group=ref, target_group=target)
        
    elif tool_name == "create_visualization":
        grp = arguments.get("group_column", "treatment")
        val = arguments.get("value_column", "viability")
        chart = arguments.get("chart_type", "box")
        plan = {"group_column": grp, "value_column": val, "chart_type": chart}
        stats_data = current_stats or compare_groups(df, grp, val)
        return generate_plotly_spec(df, plan, stats_data)
        
    raise ValueError(f"Execution handler missing for tool: {tool_name}")

# ---------------------------------------------------------------------------
# Reasoning-Driven Orchestrator
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
def _validate_llm_decision(decision: Dict[str, Any], state: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Python validates every plan Gemini proposes before it can influence execution.
    Raises ToolRequestError for malformed plans, unknown tools/columns/tests, repeated tools,
    or premature completion. The caller then falls back to the deterministic planner.
    """
    if not isinstance(decision, dict) or decision.get("status") not in ("continue", "complete"):
        raise ToolRequestError("Plan is malformed (missing or invalid status).", "invalid_plan")
    completed = set(state.get("completed_analyses", []))
    if decision["status"] == "complete":
        if not ({"summarize_groups", "compare_groups"} & completed):
            raise ToolRequestError("Plan declared completion before any analysis was computed.", "invalid_plan")
        return decision
    action = decision.get("next_action")
    if not isinstance(action, dict) or "tool" not in action:
        raise ToolRequestError("Plan has status 'continue' but no valid next_action.", "invalid_plan")
    if action["tool"] in completed:
        raise ToolRequestError(f"Plan repeats already-completed tool '{action['tool']}'.", "invalid_plan")
    action["arguments"] = validate_tool_request(action["tool"], action.get("arguments"), df)
    return decision


def decide_next_action(state: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluates current state and decides whether another tool call is necessary.
    Gemini proposes the plan; Python validates it; the deterministic planner is the fallback.
    Statistical guardrails are enforced inside the stats tools, so no plan can bypass them.
    """
    q_lower = state["user_question"].lower()
    
    # 1. Refusal check for unsupported question categories
    unsupported_kw = ["survival", "predict", "patient", "clinical trial", "machine learning", "neural network"]
    for kw in unsupported_kw:
        if kw in q_lower:
            return {
                "status": "complete",
                "next_action": None,
                "reason": "This demo currently supports descriptive analyses, group comparisons, correlations, and basic experimental trends.",
                "supported": False,
                "error_type": "unsupported_question",
                "planner": "Policy Guardrail"
            }
            
    # 2. Missing column check
    metadata = state.get("dataset_metadata", {})
    cols = metadata.get("columns", [])
    if "expression" in q_lower and "expression" not in cols:
        return {
            "status": "complete",
            "next_action": None,
            "reason": "I couldn't find an expression measurement in this dataset.",
            "supported": False,
            "error_type": "missing_column",
            "planner": "Policy Guardrail"
        }

    # 2b. Dataset must have something to measure and something to group by
    if not metadata.get("numeric_columns") or not (metadata.get("categorical_columns") or metadata.get("candidate_grouping_columns")):
        return {
            "status": "complete",
            "next_action": None,
            "reason": "This dataset needs at least one numeric measurement column and one grouping column to be analyzed.",
            "supported": False,
            "error_type": "unsuitable_dataset",
            "planner": "Policy Guardrail"
        }

    # 3. Gemini proposes; Python validates. Invalid plans are rejected and logged, never executed.
    plan_rejected = None
    if GEMINI_API_KEY:
        try:
            decision = _call_gemini_reasoner(state)
            decision = _validate_llm_decision(decision, state, df)
            decision["planner"] = f"Gemini ({GEMINI_MODEL})"
            return decision
        except ToolRequestError as e:
            plan_rejected = str(e)
        except Exception:
            pass  # API/network failure: silent fallback, as before

    # 4. Deterministic Reasoning State Machine Fallback
    decision = _deterministic_reasoner(state, df)
    decision["planner"] = "Deterministic State Machine (Local Fallback)"
    if plan_rejected:
        decision["plan_rejected"] = plan_rejected
    return decision

def _deterministic_reasoner(state: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    q_lower = state["user_question"].lower()
    completed = state.get("completed_analyses", [])
    metadata = state.get("dataset_metadata", {})
    
    # Step 1: Inspect dataset
    if "inspect_dataset" not in completed:
        return {
            "status": "continue",
            "next_action": {
                "tool": "inspect_dataset",
                "arguments": {}
            },
            "reason": "Inspect dataset schema, available columns, and data types to identify grouping and measurement variables.",
            "supported": True
        }
        
    num_cols = metadata.get("numeric_columns", ["viability"])
    cat_cols = metadata.get("categorical_columns", ["treatment"])
    treatments = metadata.get("summary", {}).get("treatments", ["Control", "Drug A", "Drug B", "Drug C"])
    
    # Check if a specific treatment was targeted
    target_drug = None
    for d in treatments:
        if d.lower() in q_lower and d.lower() != "control":
            target_drug = d
            break

    # Determine Question Type
    is_dose_query = any(kw in q_lower for kw in ["dose", "concentration", "trend", "change with dose"])
    is_descriptive = any(kw in q_lower for kw in [
        "highest mean", "highest viability", "which treatment has the highest",
        "highest average", "which treatment produced the highest", "summarize",
        "what is the average", "summary of"
    ]) and not any(kw in q_lower for kw in ["significantly different", "vs control", "compared with control", "compared to control", "t-test", "anova", "hypothesis"])
    # A pairwise test needs an explicitly named treatment; never default to a guessed one.
    # Without a named drug, "significantly different overall" is a multi-group (ANOVA) question.
    is_pairwise = target_drug is not None and (
        any(kw in q_lower for kw in ["is drug", "significantly different", "vs control", "different from control"])
        or (not is_descriptive and not is_dose_query)
    )

    # -------------------------------------------------------------------------
    # Workflow A: Filtered Dose Question (e.g. "How does Drug B respond to dose?")
    # -------------------------------------------------------------------------
    if is_dose_query and target_drug:
        val_col = "viability" if "viability" in num_cols else num_cols[0]
        grp_col = "dose" if "dose" in num_cols else (cat_cols[0] if cat_cols else "dose")
        
        if "filter_dataset" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "filter_dataset",
                    "arguments": {"filters": {"treatment": [target_drug]}}
                },
                "reason": f"The question concerns {target_drug} specifically; restrict dataset to {target_drug} prior to dose response analysis.",
                "supported": True
            }
        if "compare_groups" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "compare_groups",
                    "arguments": {
                        "group_column": grp_col,
                        "value_column": val_col,
                        "test_type": "dose_trend"
                    }
                },
                "reason": f"Evaluate dose-response correlation and linear trend on filtered {target_drug} subset.",
                "supported": True
            }
        if "create_visualization" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "create_visualization",
                    "arguments": {
                        "group_column": grp_col,
                        "value_column": val_col,
                        "chart_type": "scatter"
                    }
                },
                "reason": f"Generate publication-grade scatter plot with trendline showing {target_drug} dose response.",
                "supported": True
            }
        return {
            "status": "complete",
            "next_action": None,
            "reason": "Sufficient evidence collected. All numerical claims verified from deterministic Python tools.",
            "supported": True
        }

    # -------------------------------------------------------------------------
    # Workflow B: General Dose Question (e.g. "How does viability change with dose?")
    # -------------------------------------------------------------------------
    if is_dose_query:
        val_col = "viability" if "viability" in num_cols else num_cols[0]
        grp_col = "dose" if "dose" in num_cols else (cat_cols[0] if cat_cols else "treatment")
        
        if "check_assumptions" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "check_assumptions",
                    "arguments": {"group_column": grp_col, "value_column": val_col, "test_type": "dose_trend"}
                },
                "reason": f"Verify sample sizes (n >= {MIN_N_PER_GROUP} per dose level) and variance characteristics across dose levels.",
                "supported": True
            }
        if "compare_groups" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "compare_groups",
                    "arguments": {
                        "group_column": grp_col,
                        "value_column": val_col,
                        "test_type": "dose_trend"
                    }
                },
                "reason": f"Calculate Pearson correlation and linear regression slope across dose concentrations.",
                "supported": True
            }
        if "create_visualization" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "create_visualization",
                    "arguments": {
                        "group_column": grp_col,
                        "value_column": val_col,
                        "chart_type": "scatter"
                    }
                },
                "reason": "Generate publication-grade scatter plot showing viability vs dose concentration.",
                "supported": True
            }
        return {
            "status": "complete",
            "next_action": None,
            "reason": "Sufficient evidence collected. All numerical claims verified from deterministic Python tools.",
            "supported": True
        }

    # -------------------------------------------------------------------------
    # Workflow C: Descriptive Question (e.g. "Which treatment has the highest mean viability?")
    # (NO unnecessary hypothesis test!)
    # -------------------------------------------------------------------------
    if is_descriptive:
        val_col = "viability" if "viability" in num_cols else num_cols[0]
        grp_col = "treatment" if "treatment" in cat_cols else cat_cols[0]
        
        if "summarize_groups" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "summarize_groups",
                    "arguments": {"group_column": grp_col, "value_column": val_col}
                },
                "reason": f"Compute descriptive summary statistics (mean, SEM, SD, min, max, n) across {grp_col} groups.",
                "supported": True
            }
        if "create_visualization" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "create_visualization",
                    "arguments": {
                        "group_column": grp_col,
                        "value_column": val_col,
                        "chart_type": "bar"
                    }
                },
                "reason": f"Generate bar chart displaying group means with SEM error bars.",
                "supported": True
            }
        return {
            "status": "complete",
            "next_action": None,
            "reason": "Sufficient descriptive evidence collected. No hypothesis test needed.",
            "supported": True
        }

    # -------------------------------------------------------------------------
    # Workflow D: Pairwise Inferential Question (e.g. "Is Drug B significantly different from Control?")
    # -------------------------------------------------------------------------
    if is_pairwise:
        val_col = "viability" if "viability" in num_cols else num_cols[0]
        grp_col = "treatment" if "treatment" in cat_cols else cat_cols[0]
        eff_target = target_drug
        
        if "check_assumptions" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "check_assumptions",
                    "arguments": {"group_column": grp_col, "value_column": val_col,
                              "test_type": "two_sample_t_test", "ref_group": "Control", "target_group": eff_target}
                },
                "reason": f"Verify sample sizes (n >= {MIN_N_PER_GROUP} per group), variance characteristics, and data adequacy for '{eff_target}' vs 'Control'.",
                "supported": True
            }
        if "compare_groups" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "compare_groups",
                    "arguments": {
                        "group_column": grp_col,
                        "value_column": val_col,
                        "test_type": "two_sample_t_test",
                        "ref_group": "Control",
                        "target_group": eff_target
                    }
                },
                "reason": f"Perform Welch's two-sample t-test comparing {eff_target} specifically against Control.",
                "supported": True
            }
        if "create_visualization" not in completed:
            return {
                "status": "continue",
                "next_action": {
                    "tool": "create_visualization",
                    "arguments": {
                        "group_column": grp_col,
                        "value_column": val_col,
                        "chart_type": "bar"
                    }
                },
                "reason": f"Generate bar plot comparing {eff_target} against Control with error bars.",
                "supported": True
            }
        return {
            "status": "complete",
            "next_action": None,
            "reason": "Sufficient evidence collected. All numerical claims verified from deterministic Python tools.",
            "supported": True
        }

    # -------------------------------------------------------------------------
    # Workflow E: Multi-Group Inferential Question (e.g. One-way ANOVA)
    # -------------------------------------------------------------------------
    val_col = "viability" if "viability" in num_cols else num_cols[0]
    grp_col = "treatment" if "treatment" in cat_cols else cat_cols[0]
    
    if "check_assumptions" not in completed:
        return {
            "status": "continue",
            "next_action": {
                "tool": "check_assumptions",
                "arguments": {"group_column": grp_col, "value_column": val_col,
                          "test_type": "one_way_anova", "ref_group": "Control"}
            },
            "reason": f"Verify sample sizes (n >= {MIN_N_PER_GROUP} per group), variance spread, and check assumptions across all {grp_col} groups.",
            "supported": True
        }
    if "compare_groups" not in completed:
        return {
            "status": "continue",
            "next_action": {
                "tool": "compare_groups",
                "arguments": {
                    "group_column": grp_col,
                    "value_column": val_col,
                    "test_type": "one_way_anova",
                    "ref_group": "Control"
                }
            },
            "reason": f"Execute One-way ANOVA with post-hoc Tukey HSD correction across all treatment groups.",
            "supported": True
        }
    if "create_visualization" not in completed:
        return {
            "status": "continue",
            "next_action": {
                "tool": "create_visualization",
                "arguments": {
                    "group_column": grp_col,
                    "value_column": val_col,
                    "chart_type": "box"
                }
            },
            "reason": "Generate publication-grade box plot showing distributions across all treatment groups.",
            "supported": True
        }
    return {
        "status": "complete",
        "next_action": None,
        "reason": "Sufficient evidence collected. All numerical claims verified from deterministic Python tools.",
        "supported": True
    }

# ---------------------------------------------------------------------------
# Main Tool-Using Agent Loop
# ---------------------------------------------------------------------------
def run_agent_reasoning_loop(df: pd.DataFrame, question: str, max_iterations: int = 6) -> Dict[str, Any]:
    """
    Orchestrates the reasoning-driven tool-using loop:
    1. Inspect state
    2. Determine missing information
    3. Select and execute next tool
    4. Re-evaluate state
    5. Continue until adequately answered
    6. Formulate grounded interpretation
    """
    initial_inspection = inspect_dataset(df)
    
    state: Dict[str, Any] = {
        "user_question": question,
        "dataset_metadata": initial_inspection,
        "observations": initial_inspection.get("summary", {}),
        "completed_analyses": ["inspect_dataset"],
        "tool_history": [{
            "step": 1,
            "tool": "inspect_dataset",
            "arguments": {},
            "reason": "Inspect dataset schema, available columns, and biological parameters.",
            "output_summary": {
                "rows": initial_inspection["rows"],
                "columns": initial_inspection["columns"],
                "numeric_columns": initial_inspection["numeric_columns"],
                "categorical_columns": initial_inspection["categorical_columns"]
            }
        }],
        "current_findings": {},
        "remaining_information_needed": "Check sample sizes and variance characteristics",
        "final_result": None
    }
    
    steps_log: List[Dict[str, Any]] = [{
        "label": "Inspect dataset schema, available columns, and data types.",
        "tool": "inspect_dataset",
        "status": "done"
    }]
    current_stats: Dict[str, Any] = {}
    current_plotly_spec: Dict[str, Any] = {}
    last_reason: str = ""
    is_supported: bool = True
    error_type: Optional[str] = None
    plan_rejections: List[str] = []
    active_planner: str = "Deterministic State Machine"

    working_df = df.copy()

    for iteration in range(1, max_iterations):
        # 1. Reason: Decide next action
        decision = decide_next_action(state, working_df)
        active_planner = decision.get("planner", active_planner)
        
        if decision.get("plan_rejected"):
            plan_rejections.append(decision["plan_rejected"])
            steps_log.append({
                "label": f"Gemini plan rejected by Python validation ({decision['plan_rejected']}); using deterministic planner.",
                "tool": "plan_validation",
                "status": "refused"
            })

        if not decision.get("supported", True):
            is_supported = False
            error_type = decision.get("error_type", "unsupported_question")
            last_reason = decision.get("reason", "Question cannot be analyzed.")
            steps_log.append({
                "label": last_reason,
                "tool": "refusal",
                "status": "refused"
            })
            break
            
        if decision.get("status") == "complete":
            # Ensure visualization was created if statistical comparison or summary completed
            has_stats = "compare_groups" in state["completed_analyses"] or "summarize_groups" in state["completed_analyses"]
            if has_stats and "create_visualization" not in state["completed_analyses"]:
                grp_col = current_stats.get("group_column", "treatment")
                val_col = current_stats.get("value_column", "viability")
                c_type = "scatter" if current_stats.get("test_type") == "dose_trend" else ("bar" if current_stats.get("test_type") in ["two_sample_t_test", "t_test"] or current_stats.get("comparison_type") == "descriptive" else "box")
                if current_stats.get("blocked"):
                    c_type = "bar"  # blocked analyses are shown descriptively
                try:
                    viz_result = execute_tool("create_visualization", {"group_column": grp_col, "value_column": val_col, "chart_type": c_type}, working_df, current_stats)
                except Exception:
                    if not current_stats.get("blocked"):
                        raise
                    viz_result = {}  # no plot for blocked/malformed data
                current_plotly_spec = viz_result
                state["completed_analyses"].append("create_visualization")
                state["tool_history"].append({
                    "step": len(state["tool_history"]) + 1,
                    "tool": "create_visualization",
                    "arguments": {"group_column": grp_col, "value_column": val_col, "chart_type": c_type},
                    "reason": f"Generate publication-grade interactive {c_type} plot showing experimental distributions.",
                    "output_summary": {"chart_type": c_type}
                })
                steps_log.append({
                    "label": f"Generate publication-grade interactive {c_type} plot showing experimental distributions.",
                    "tool": "create_visualization",
                    "status": "done"
                })
            steps_log.append({
                "label": "Evidence sufficient: Synthesizing verified scientific interpretation",
                "tool": "finalize_response",
                "status": "done"
            })
            break
            
        # 2. Tool Selection & Validation
        action = decision.get("next_action")
        if not action or "tool" not in action:
            break
            
        tool_name = action["tool"]
        arguments = action.get("arguments", {})
        reason = decision.get("reason", f"Executing {tool_name}")
        
        # 3. Deterministic Tool Execution (Python validates the request again; invalid requests
        #    become a structured refusal instead of a crash)
        try:
            tool_result = execute_tool(tool_name, arguments, working_df, current_stats)
        except ToolRequestError as e:
            is_supported = False
            error_type = e.error_type
            last_reason = f"Invalid analysis request ({tool_name}): {e}"
            steps_log.append({"label": last_reason, "tool": tool_name, "status": "refused"})
            break
        except Exception:
            if tool_name == "create_visualization" and current_stats.get("blocked"):
                tool_result = {}  # plot unavailable for blocked analyses
            else:
                raise
        
        # If tool was filter_dataset, update working dataframe
        if tool_name == "filter_dataset" and "filtered_rows" in tool_result:
            filters = arguments.get("filters", {})
            for col, criteria in filters.items():
                if col in working_df.columns:
                    if isinstance(criteria, list):
                        working_df = working_df[working_df[col].isin(criteria)]
                    elif isinstance(criteria, (int, float, str)):
                        working_df = working_df[working_df[col] == criteria]
        
        # 4. State Update
        state["completed_analyses"].append(tool_name)
        output_summary = {k: v for k, v in tool_result.items() if k not in ["data", "layout"]} if isinstance(tool_result, dict) else str(tool_result)[:100]
        
        state["tool_history"].append({
            "step": iteration + 1,
            "tool": tool_name,
            "arguments": arguments,
            "reason": reason,
            "output_summary": output_summary
        })
        
        if isinstance(tool_result, dict) and tool_result.get("blocked"):
            steps_log.append({
                "label": f"Statistical test blocked by Python guardrails: {tool_result.get('blocked_message', '')}",
                "tool": tool_name,
                "status": "refused"
            })
        else:
            steps_log.append({
                "label": reason,
                "tool": tool_name,
                "status": "done"
            })
        
        if tool_name == "inspect_dataset":
            state["dataset_metadata"] = tool_result
            state["observations"] = tool_result.get("summary", {})
            state["remaining_information_needed"] = "Check sample sizes and variance characteristics"
        elif tool_name == "filter_dataset":
            state["current_findings"]["filter"] = tool_result
            state["remaining_information_needed"] = f"Proceed with analysis on {tool_result['filtered_rows']} filtered rows"
        elif tool_name == "check_assumptions":
            state["current_findings"]["assumptions"] = tool_result
            state["remaining_information_needed"] = "Perform hypothesis test and compute effect sizes"
        elif tool_name == "summarize_groups":
            current_stats = tool_result
            state["current_findings"]["summary"] = tool_result
            state["final_result"] = tool_result
            state["remaining_information_needed"] = "Generate visual distributions chart"
        elif tool_name == "compare_groups":
            current_stats = tool_result
            state["current_findings"]["statistics"] = tool_result
            state["final_result"] = tool_result
            state["remaining_information_needed"] = "Generate visual distributions chart"
        elif tool_name == "create_visualization":
            current_plotly_spec = tool_result
            state["remaining_information_needed"] = "None. All required evidence collected and verified."

    # 5. Final Response Generation from Verified Results ONLY
    if not is_supported:
        return {
            "supported": False,
            "error_type": error_type or "unsupported_question",
            "reason": last_reason,
            "planner": active_planner,
            "plan_rejections": plan_rejections,
            "steps": steps_log,
            "agent_state": state
        }

    if not current_stats:
        return {
            "supported": False,
            "error_type": "no_analysis_completed",
            "reason": "No analysis could be completed for this question with the available data.",
            "planner": active_planner,
            "plan_rejections": plan_rejections,
            "steps": steps_log,
            "agent_state": state
        }
        
    explanation, explanation_source = _generate_explanation_with_source(question, state, current_stats)
    
    return {
        "supported": True,
        "question": question,
        "planner": active_planner,
        "plan_rejections": plan_rejections,
        "steps": steps_log,
        "analysis_trace": _build_analysis_trace(state, current_stats, explanation_source),
        "statistical_audit": _build_statistical_audit(current_stats, explanation_source),
        "explanation_source": explanation_source,
        "plan": state.get("final_result", {}),
        "stats": current_stats,
        "plotly_spec": current_plotly_spec,
        "interpretation": explanation,
        "agent_state": {
            "user_question": state["user_question"],
            "planner": active_planner,
            "dataset_metadata": {
                "rows": state["dataset_metadata"].get("rows"),
                "columns": state["dataset_metadata"].get("columns"),
                "numeric_columns": state["dataset_metadata"].get("numeric_columns"),
                "categorical_columns": state["dataset_metadata"].get("categorical_columns")
            },
            "observations": state["observations"],
            "completed_analyses": state["completed_analyses"],
            "tool_history": state["tool_history"],
            "current_findings": state["current_findings"],
            "remaining_information_needed": state["remaining_information_needed"],
            "final_result": state.get("final_result", {})
        }
    }

def _validate_explanation_entities(explanation: str, stats_result: Dict[str, Any]) -> bool:
    """
    Validates that the generated explanation discusses ONLY the entities present
    in the computed stats result, preventing the 'Result: Drug B vs Control, Explanation: Drug A'
    hallucination bug.
    """
    exp_lower = explanation.lower()
    comp_type = stats_result.get("comparison_type")
    
    if comp_type == "pairwise":
        target = stats_result.get("target_group", "")
        ref = stats_result.get("reference_group", "")
        
        # Target group must be explicitly present
        if target and target.lower() not in exp_lower:
            return False
            
        # Reference group must be present if provided
        if ref and ref.lower() not in exp_lower:
            return False
            
        # Exclude other treatments from erroneously creeping into a pairwise contrast
        summary = stats_result.get("group_summary", {})
        for grp in summary.keys():
            if isinstance(grp, str) and grp not in [target, ref] and len(grp) > 2:
                if grp.lower() in exp_lower:
                    return False
                    
    elif comp_type == "dose_trend":
        if "dose" not in exp_lower and "concentration" not in exp_lower:
            return False
            
    elif comp_type == "descriptive":
        top = stats_result.get("top_performer", "")
        if top and top.lower() not in exp_lower:
            return False
            
    return True

DISCLAIMER = ("This describes the observed experiment and does not establish causality. "
              "Notice: Synthetic demonstration data — not real experimental results.")


def _generate_explanation_with_source(question: str, state: Dict[str, Any], stats_result: Dict[str, Any]):
    """
    Returns (text, source) where source is "gemini" or "deterministic_template".
    Gemini only ever sees Python-computed results, and its text is entity-validated.
    Blocked analyses are explained by a fixed template: the LLM never gets to narrate around a guardrail.
    """
    if stats_result.get("blocked"):
        return _deterministic_explanation(stats_result), "deterministic_template"
    if GEMINI_API_KEY:
        try:
            candidate_text = _call_gemini_explainer(question, stats_result)
            if _validate_explanation_entities(candidate_text, stats_result):
                if "does not establish causality" not in candidate_text:
                    candidate_text = f"{candidate_text.rstrip()}\n\n{DISCLAIMER}"
                return candidate_text, "gemini"
        except Exception:
            pass
    return _deterministic_explanation(stats_result), "deterministic_template"


def _generate_verified_explanation(question: str, state: Dict[str, Any], stats_result: Dict[str, Any]) -> str:
    """
    Formulates interpretation strictly referencing verified Python tool results.
    Validates generated entities; if validation fails, falls back to deterministic explanation.
    """
    return _generate_explanation_with_source(question, state, stats_result)[0]


def _variance_caution(stats_result: Dict[str, Any]) -> str:
    warnings = stats_result.get("assumption_checks", {}).get("warnings", [])
    if stats_result.get("comparison_type") == "multi_group_anova" and any("equal-variance" in w for w in warnings):
        return ("Caution: group variances differ substantially, and ANOVA/Tukey HSD assume equal variances, "
                "so p-values should be interpreted with care.")
    return ""


def _build_analysis_trace(state: Dict[str, Any], stats_result: Dict[str, Any], explanation_source: str) -> List[Dict[str, str]]:
    """Structured post-hoc record of what the backend did (returned with the result; not a live stream)."""
    meta = state.get("dataset_metadata", {})
    summary = {k: v for k, v in stats_result.get("group_summary", {}).items() if isinstance(v, dict) and "mean" in v}
    ac = stats_result.get("assumption_checks")
    blocked = bool(stats_result.get("blocked"))
    descriptive = stats_result.get("comparison_type") == "descriptive"

    def find(prefix: str):
        for c in (ac or {}).get("checks", []):
            if c["name"].startswith(prefix):
                return c
        return None

    sample = find("Sample sizes")
    assume = find("Assumptions checked")
    warnings = [w for w in (ac or {}).get("warnings", [])]
    if blocked:
        test_item = ("blocked", stats_result.get("blocked_message", "Blocked by Python guardrails."))
    elif descriptive or ac is None:
        test_item = ("not_applicable", "Descriptive question: no inferential test requested.")
    else:
        test_item = ("executed", stats_result.get("test_name", "Statistical test"))
    if explanation_source == "gemini":
        valid_detail = "Numbers computed by Python; Gemini explanation passed entity validation."
    else:
        valid_detail = "Numbers computed by Python; explanation produced by deterministic template."

    return [
        {"key": "dataset_inspected", "label": "Dataset inspected", "status": "passed",
         "detail": f"{meta.get('rows')} rows, {len(meta.get('columns', []))} columns"},
        {"key": "groups_identified", "label": "Groups identified", "status": "passed" if summary else "failed",
         "detail": f"{len(summary)} group(s): {', '.join(summary)}" if summary else "No usable groups found"},
        {"key": "sample_sizes_checked", "label": f"Sample sizes checked (n >= {MIN_N_PER_GROUP} per group)",
         "status": ("passed" if sample["passed"] else "failed") if sample else "not_applicable",
         "detail": sample["detail"] if sample else "Descriptive summary: n reported per group, not gated."},
        {"key": "assumptions_checked", "label": "Assumptions checked",
         "status": ("passed" if assume["passed"] else "failed") if assume else "not_applicable",
         "detail": "; ".join(warnings) if warnings else "No inferential test requested."},
        {"key": "test_executed", "label": "Statistical test executed", "status": test_item[0], "detail": test_item[1]},
        {"key": "result_validated", "label": "Result validated", "status": "passed", "detail": valid_detail},
    ]


def _build_statistical_audit(stats_result: Dict[str, Any], explanation_source: str) -> Dict[str, Any]:
    """Compact audit of the numbers shown to the user. Every value is copied from the Python result."""
    summary = {k: v for k, v in stats_result.get("group_summary", {}).items() if isinstance(v, dict) and "mean" in v}
    comp = stats_result.get("comparison_type")
    blocked = bool(stats_result.get("blocked"))
    pair = [g for g in (stats_result.get("target_group"), stats_result.get("reference_group")) if g in summary]
    if pair and (comp == "pairwise" or (blocked and stats_result.get("target_group"))):
        names = pair  # the groups actually being compared
    else:
        names = list(summary)

    effect = None
    if not blocked:
        if comp == "pairwise":
            effect = {"label": "Difference vs reference (pp)", "value": stats_result.get("difference_pp"),
                      "comparison": stats_result.get("comparison")}
        elif comp == "multi_group_anova":
            ph = stats_result.get("top_vs_reference_posthoc") or {}
            effect = {"label": "Highest mean minus reference (pp)", "value": stats_result.get("delta_vs_reference"),
                      "comparison": f"{stats_result.get('top_performer')} vs {stats_result.get('reference_group')}",
                      "posthoc_p_adj": ph.get("formatted_p_adj")}
        elif comp == "dose_trend" and stats_result.get("slope") is not None:
            effect = {"label": "Slope per dose unit", "value": stats_result.get("slope"),
                      "r": stats_result.get("correlation_r")}
        elif comp == "descriptive":
            effect = {"label": "Highest mean minus reference (pp, descriptive)",
                      "value": stats_result.get("delta_vs_reference"),
                      "comparison": f"{stats_result.get('top_performer')} vs {stats_result.get('reference_group')}"}

    return {
        "status": "blocked" if blocked else ("descriptive" if comp == "descriptive" else "completed"),
        "selected_test": stats_result.get("test_name") or ("Blocked: " + str(stats_result.get("test_type")) if blocked else "Descriptive Group Summary"),
        "groups": names,
        "n_per_group": {g: summary[g]["n"] for g in names},
        "means": {g: summary[g]["mean"] for g in names},
        "effect": effect,
        "p_value": None if blocked else stats_result.get("p_value"),
        "formatted_p_value": None if blocked else stats_result.get("formatted_p_value"),
        "blocked_reasons": stats_result.get("blocked_reasons", []),
        "computed_by": "Python / SciPy",
        "interpreted_by": f"Gemini ({GEMINI_MODEL})" if explanation_source == "gemini" else "Deterministic template (Gemini not used for this interpretation)",
        "explanation_source": explanation_source,
    }

def _deterministic_explanation(stats_result: Dict[str, Any]) -> str:
    if stats_result.get("blocked"):
        reasons = " ".join(r["message"] for r in stats_result.get("blocked_reasons", []))
        group_means = [f"{k}: {v.get('mean')}% (n = {v.get('n')})" for k, v in stats_result.get("group_summary", {}).items()
                       if isinstance(v, dict) and "mean" in v]
        desc = f" Descriptive statistics only: {', '.join(group_means)}." if group_means else ""
        return (
            f"The requested statistical test was not run because the data do not meet the minimum requirements. "
            f"{reasons}{desc}\n\n"
            f"No conclusion about group differences can be drawn from this analysis.\n\n{DISCLAIMER}"
        )
    text = _deterministic_explanation_core(stats_result)
    caution = _variance_caution(stats_result)
    if caution:
        head, sep, tail = text.partition("\n\n")
        text = f"{head} {caution}{sep}{tail}"
    return text


def _deterministic_explanation_core(stats_result: Dict[str, Any]) -> str:
    val_name = stats_result.get("value_column", "viability")
    comp_type = stats_result.get("comparison_type", "")
    summary = stats_result.get("group_summary", {})
    
    if comp_type == "pairwise":
        target = stats_result.get("target_group", "Target")
        ref = stats_result.get("reference_group", "Control")
        target_mean = stats_result.get("target_mean", summary.get(target, {}).get("mean", 0.0) if isinstance(summary.get(target), dict) else 0.0)
        ref_mean = stats_result.get("reference_mean", summary.get(ref, {}).get("mean", 0.0) if isinstance(summary.get(ref), dict) else 0.0)
        diff_pp = stats_result.get("difference_pp", round(target_mean - ref_mean, 2))
        diff_str = f"+{diff_pp}" if diff_pp > 0 else f"{diff_pp}"
        test_name = stats_result.get("test", stats_result.get("test_name", "Welch's t-test"))
        p_val_str = stats_result.get("formatted_p_value", f"= {stats_result.get('p_value', 'N/A')}")
        is_sig = stats_result.get("significant", stats_result.get("is_significant", False))
        sig_str = "statistically significant" if is_sig else "not statistically significant"
        
        return (
            f"{target} produced a mean {val_name} of {target_mean}%, representing a {diff_str} percentage point "
            f"difference compared with {ref} (mean: {ref_mean}%). "
            f"This difference was {sig_str} using {test_name} (p {p_val_str}).\n\n"
            f"This describes the observed experiment and does not establish causality. "
            f"Notice: Synthetic demonstration data — not real experimental results."
        )
    elif comp_type == "descriptive":
        top = stats_result.get("top_performer", "")
        top_mean = stats_result.get("top_mean", 0.0)
        group_means = [f"{k}: {v.get('mean')}%" for k, v in summary.items() if isinstance(v, dict) and "mean" in v]
        breakdown_str = f" Group breakdown: {', '.join(group_means)}." if group_means else ""
        return (
            f"Across observed treatments, {top} produced the highest mean {val_name} at {top_mean}%.{breakdown_str}\n\n"
            f"This describes the observed experiment and does not establish causality. "
            f"Notice: Synthetic demonstration data — not real experimental results."
        )
    elif comp_type == "dose_trend" or stats_result.get("test_type") == "dose_trend":
        r = stats_result.get("correlation_r", 0.0)
        slope = stats_result.get("slope", 0.0)
        p_val_str = stats_result.get("formatted_p_value", f"= {stats_result.get('p_value', 'N/A')}")
        direction = "negative" if slope < 0 else "positive"
        return (
            f"An analysis of {val_name} across varying dose concentrations revealed a {direction} correlation "
            f"(Pearson r = {r:.3f}, p {p_val_str}). Higher dose levels were associated with a "
            f"{'reduction' if slope < 0 else 'increase'} in observed {val_name} (slope: {slope:.3f}).\n\n"
            f"This describes the observed experiment and does not establish causality. "
            f"Notice: Synthetic demonstration data — not real experimental results."
        )
    else:
        # Multi-group ANOVA
        top_performer = stats_result.get("top_performer", "")
        top_mean = stats_result.get("top_mean", 0.0)
        ref_group = stats_result.get("reference_group", "Control")
        delta = stats_result.get("delta_vs_reference", 0.0)
        diff_str = f"+{delta}" if delta > 0 else f"{delta}"
        test_name = stats_result.get("test_name", "One-way ANOVA")
        p_val_str = stats_result.get("formatted_p_value", "N/A")
        ref_mean = summary.get(ref_group, {}).get("mean", 0.0) if isinstance(summary.get(ref_group), dict) else 0.0
        top_posthoc = stats_result.get("top_vs_reference_posthoc")
        
        if top_posthoc:
            p_adj_str = top_posthoc.get("formatted_p_adj", "N/A")
            is_posthoc_sig = top_posthoc.get("is_significant", False)
            if not is_posthoc_sig:
                return (
                    f"{top_performer} produced the highest observed mean {val_name} at {top_mean}%, "
                    f"which is {diff_str} percentage points higher than {ref_group} (mean: {ref_mean}%). "
                    f"Across all treatment groups, variation in {val_name} was statistically significant ({test_name}, p {p_val_str}). "
                    f"However, post-hoc Tukey HSD testing indicates that the difference between {top_performer} and {ref_group} "
                    f"specifically does not reach significance after multiple-comparison adjustment (p_adj {p_adj_str}). "
                    f"Overall significance is driven primarily by marked reductions in other groups.\n\n"
                    f"This describes the observed experiment and does not establish causality. "
                    f"Notice: Synthetic demonstration data — not real experimental results."
                )
            else:
                return (
                    f"{top_performer} produced the highest mean {val_name} at {top_mean}%, "
                    f"which is {diff_str} percentage points higher than {ref_group} (mean: {ref_mean}%). "
                    f"This difference was confirmed statistically significant in post-hoc testing "
                    f"(Tukey HSD, p_adj {p_adj_str}; overall ANOVA p {p_val_str}).\n\n"
                    f"This describes the observed experiment and does not establish causality. "
                    f"Notice: Synthetic demonstration data — not real experimental results."
                )
        else:
            return (
                f"{top_performer} produced the highest mean {val_name} at {top_mean}%, "
                f"which is {diff_str} percentage points higher than {ref_group} (mean: {ref_mean}%). "
                f"Across all treatment groups, variation in {val_name} was statistically significant "
                f"({test_name}, p {p_val_str}).\n\n"
                f"This describes the observed experiment and does not establish causality. "
                f"Notice: Synthetic demonstration data — not real experimental results."
            )

def _call_gemini_reasoner(state: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    prompt = f"""You are the reasoning and orchestration agent for BioData Copilot.
Your role is to inspect the current state and select the single next best tool to answer the user's question.

CURRENT AGENT STATE:
- User Question: "{state['user_question']}"
- Candidate Grouping Columns: {json.dumps(state.get('dataset_metadata', {}).get('candidate_grouping_columns', []))}
- Candidate Measurement Columns: {json.dumps(state.get('dataset_metadata', {}).get('candidate_measurement_columns', []))}
- Available Columns: {json.dumps(state.get('dataset_metadata', {}).get('columns', []))}
- Completed Analyses: {json.dumps(state.get('completed_analyses', []))}
- Tool History & Outputs:
{json.dumps(state.get('tool_history', []), indent=2)}
- Current Findings:
{json.dumps(state.get('current_findings', {}), indent=2)}
- Remaining Information Needed:
"{state.get('remaining_information_needed', '')}"

ALLOWED PREDEFINED TOOLS:
{json.dumps(TOOL_REGISTRY, indent=2)}

INSTRUCTIONS:
1. Descriptive questions (e.g., 'Which treatment has the highest mean viability?', 'Summarize treatment groups'):
   - Do NOT run hypothesis tests. Call 'summarize_groups' with group_column='treatment', value_column='viability'.
   - Then call 'create_visualization' with chart_type='bar'.
2. Specific drug dose questions (e.g., 'How does Drug B respond to dose?'):
   - First call 'filter_dataset' with filters={{"treatment": ["Drug B"]}} to restrict to the target treatment.
   - Then call 'compare_groups' with group_column='dose', value_column='viability', test_type='dose_trend'.
   - Then call 'create_visualization' with chart_type='scatter'.
3. General dose trend questions (e.g., 'How does viability change with dose?'):
   - Call 'check_assumptions' with group_column='dose', value_column='viability'.
   - Call 'compare_groups' with group_column='dose', value_column='viability', test_type='dose_trend'.
   - Call 'create_visualization' with chart_type='scatter'.
4. Pairwise questions comparing a specific drug against control (e.g. 'Is Drug B significantly different from Control?'):
   - First call 'check_assumptions' with group_column='treatment', value_column='viability'.
   - Then call 'compare_groups' with test_type='two_sample_t_test', target_group='Drug B', ref_group='Control'.
   - Then call 'create_visualization' with chart_type='bar'.
5. Multi-group overall difference questions (e.g., 'Are treatments significantly different overall?'):
   - Call 'check_assumptions' with group_column='treatment', value_column='viability'.
   - Then call 'compare_groups' with test_type='one_way_anova', ref_group='Control'.
   - Then call 'create_visualization' with chart_type='box'.
6. Once the analysis and visualization tools are completed, return status='complete' and next_action=null.
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": REASONER_SCHEMA
        }
    }
    resp = httpx.post(url, json=payload, timeout=8.0)
    if resp.status_code == 200:
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(raw_text)
        
        # Python verification & argument normalization
        if parsed.get("status") == "continue" and parsed.get("next_action"):
            action = parsed["next_action"]
            tool = action.get("tool")
            if tool not in TOOL_REGISTRY:
                raise ValueError(f"Unauthorized tool requested: {tool}")
            
            args = action.setdefault("arguments", {})
            q_lower = state["user_question"].lower()
            treatments = state.get("dataset_metadata", {}).get("summary", {}).get("treatments", ["Control", "Drug A", "Drug B", "Drug C"])
            
            # Align domain variables for common experimental queries
            if "dose" in q_lower or "concentration" in q_lower or "trend" in q_lower:
                if "group_column" in _TOOL_ARG_KEYS[tool]:
                    args["group_column"] = "dose"
                    args["value_column"] = "viability"
                if tool == "compare_groups":
                    args["test_type"] = "dose_trend"
                elif tool == "create_visualization":
                    args["chart_type"] = "scatter"
            elif any(d.lower() in q_lower for d in treatments if d.lower() != "control"):
                # Pairwise comparison to control
                matched_target = None
                for d in treatments:
                    if d.lower() in q_lower and d.lower() != "control":
                        matched_target = d
                        break
                if tool == "compare_groups":
                    args["test_type"] = "two_sample_t_test"
                    args["ref_group"] = "Control"
                    args["target_group"] = matched_target or "Drug B"
                elif tool == "create_visualization":
                    args["chart_type"] = "bar"
                
        parsed["supported"] = True
        return parsed
        
    raise ValueError(f"Gemini API returned status {resp.status_code}")

def _call_gemini_explainer(question: str, stats_result: Dict[str, Any]) -> str:
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    prompt = f"""You are a scientific explainer for BioData Copilot.
The user asked: "{question}"
The deterministic Python engine executed the statistical analysis and calculated these EXACT results:
{json.dumps(stats_result, indent=2)}

Write a concise 2-3 sentence scientific summary explaining this finding.
STRICT RULES:
1. ONLY use the exact numerical values provided above. Do NOT invent or calculate any new numbers.
2. State the test name and p-value as calculated.
3. If this was a pairwise comparison (comparison_type='pairwise'), ONLY discuss the target_group and reference_group. Do NOT mention any other drugs!
4. If this was a dose or concentration trend analysis, explicitly mention the word 'dose' and explain the correlation direction and slope.
5. If Tukey HSD post-hoc testing was performed, explicitly report whether the specific contrast between the top performer and control is statistically significant after multiple comparison adjustment. Do NOT claim the top performer is significantly different from control if p_adj >= 0.05.
6. If assumption_checks.warnings mention a variance imbalance, briefly note that the equal-variance assumption may not hold.
7. You must include these exact sentences at the end:
"This describes the observed experiment and does not establish causality. Notice: Synthetic demonstration data — not real experimental results."
"""
    resp = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=8.0)
    if resp.status_code == 200:
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    raise ValueError("Gemini explainer call failed")
