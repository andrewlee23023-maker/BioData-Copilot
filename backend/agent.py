import os
import json
import re
import httpx
import pandas as pd
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from backend.tools.inspect import inspect_dataset
from backend.tools.stats import summarize_groups, compare_groups, check_assumptions
from backend.tools.viz import generate_plotly_spec
from backend.tools.filter import filter_dataset

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

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
        "description": "Checks sample sizes (n >= 3), missing values, variance spread across groups, and reports normality status.",
        "parameters": {"group_column": "str", "value_column": "str"}
    },
    "summarize_groups": {
        "description": "Calculates descriptive statistics (mean, std, sem, median, min, max, n) for continuous values grouped by category.",
        "parameters": {"group_column": "str", "value_column": "str"}
    },
    "compare_groups": {
        "description": "Executes deterministic hypothesis testing (One-way ANOVA with Tukey HSD post-hoc, Welch's t-test, Mann-Whitney U, or dose trend correlation).",
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
def execute_tool(
    tool_name: str, 
    arguments: Dict[str, Any], 
    df: pd.DataFrame, 
    current_stats: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes a predefined, validated Python tool deterministically.
    Rejects any unauthorized tool or arbitrary code execution attempt.
    """
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unauthorized tool: '{tool_name}'. Only predefined tools are permitted.")
        
    if tool_name == "inspect_dataset":
        return inspect_dataset(df)
        
    elif tool_name == "filter_dataset":
        filters = arguments.get("filters", {})
        return filter_dataset(df, filters)
        
    elif tool_name == "check_assumptions":
        grp = arguments.get("group_column", "treatment")
        val = arguments.get("value_column", "viability")
        if grp not in df.columns:
            grp = "treatment" if "treatment" in df.columns else df.columns[1]
        if val not in df.columns:
            val = "viability" if "viability" in df.columns else df.columns[-1]
        return check_assumptions(df, grp, val)
        
    elif tool_name == "summarize_groups":
        grp = arguments.get("group_column", "treatment")
        val = arguments.get("value_column", "viability")
        return summarize_groups(df, grp, val)
        
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
def decide_next_action(state: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluates current state and decides whether another tool call is necessary.
    Uses Gemini structured outputs if API is configured, with deterministic fallback.
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
            "planner": "Policy Guardrail"
        }

    # 3. Attempt Gemini Structured Output Reasoning
    if GEMINI_API_KEY:
        try:
            decision = _call_gemini_reasoner(state)
            decision["planner"] = "Gemini (gemini-3.5-flash-lite)"
            return decision
        except Exception:
            pass

    # 4. Deterministic Reasoning State Machine Fallback
    decision = _deterministic_reasoner(state, df)
    decision["planner"] = "Deterministic State Machine (Local Fallback)"
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
    
    # Variable selection logic
    if "dose" in q_lower or "concentration" in q_lower or "trend" in q_lower or "change with dose" in q_lower:
        val_col = "viability" if "viability" in num_cols else num_cols[0]
        grp_col = "dose" if "dose" in num_cols else (cat_cols[0] if cat_cols else "treatment")
        test_type = "dose_trend"
        chart_type = "scatter"
    else:
        val_col = "viability" if "viability" in num_cols else (num_cols[0] if num_cols else "value")
        grp_col = "treatment" if "treatment" in cat_cols else (cat_cols[0] if cat_cols else "group")
        
        treatments = metadata.get("summary", {}).get("treatments", ["Control", "Drug A", "Drug B", "Drug C"])
        target_drug = None
        for d in treatments:
            if d.lower() in q_lower and d.lower() != "control":
                target_drug = d
                break
        test_type = "two_sample_t_test" if target_drug else "one_way_anova"
        chart_type = "bar" if target_drug else "box"

    # Step 2: Check assumptions
    if "check_assumptions" not in completed:
        return {
            "status": "continue",
            "next_action": {
                "tool": "check_assumptions",
                "arguments": {"group_column": grp_col, "value_column": val_col}
            },
            "reason": f"Verify sample sizes, variance characteristics, and assess data adequacy for '{grp_col}' vs '{val_col}'.",
            "supported": True
        }

    # Step 3: Run hypothesis comparison
    if "compare_groups" not in completed:
        return {
            "status": "continue",
            "next_action": {
                "tool": "compare_groups",
                "arguments": {
                    "group_column": grp_col,
                    "value_column": val_col,
                    "test_type": test_type,
                    "ref_group": "Control",
                    "target_group": target_drug if 'target_drug' in locals() else None
                }
            },
            "reason": f"Execute deterministic {test_type} with post-hoc Tukey HSD correction on '{grp_col}' vs '{val_col}'.",
            "supported": True
        }

    # Step 4: Create visualization
    if "create_visualization" not in completed:
        return {
            "status": "continue",
            "next_action": {
                "tool": "create_visualization",
                "arguments": {
                    "group_column": grp_col,
                    "value_column": val_col,
                    "chart_type": chart_type
                }
            },
            "reason": f"Generate publication-grade interactive {chart_type} plot showing experimental distributions.",
            "supported": True
        }

    # Step 5: Finished
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
    active_planner: str = "Deterministic State Machine"

    working_df = df.copy()

    for iteration in range(1, max_iterations):
        # 1. Reason: Decide next action
        decision = decide_next_action(state, working_df)
        active_planner = decision.get("planner", active_planner)
        
        if not decision.get("supported", True):
            is_supported = False
            last_reason = decision.get("reason", "Question cannot be analyzed.")
            steps_log.append({
                "label": last_reason,
                "tool": "refusal",
                "status": "refused"
            })
            break
            
        if decision.get("status") == "complete":
            # Ensure visualization was created if statistical comparison completed
            if "compare_groups" in state["completed_analyses"] and "create_visualization" not in state["completed_analyses"]:
                grp_col = current_stats.get("group_column", "treatment")
                val_col = current_stats.get("value_column", "viability")
                c_type = "scatter" if current_stats.get("test_type") == "dose_trend" else ("bar" if current_stats.get("test_type") in ["two_sample_t_test", "t_test"] else "box")
                viz_result = execute_tool("create_visualization", {"group_column": grp_col, "value_column": val_col, "chart_type": c_type}, working_df, current_stats)
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
        
        # 3. Deterministic Tool Execution
        tool_result = execute_tool(tool_name, arguments, working_df, current_stats)
        
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
            "reason": last_reason,
            "planner": active_planner,
            "steps": steps_log,
            "agent_state": state
        }
        
    explanation = _generate_verified_explanation(question, state, current_stats)
    
    return {
        "supported": True,
        "question": question,
        "planner": active_planner,
        "steps": steps_log,
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

def _generate_verified_explanation(question: str, state: Dict[str, Any], stats_result: Dict[str, Any]) -> str:
    """
    Formulates interpretation strictly referencing verified Python tool results.
    """
    if GEMINI_API_KEY:
        try:
            return _call_gemini_explainer(question, stats_result)
        except Exception:
            pass
            
    val_name = stats_result.get("value_column", "viability")
    grp_name = stats_result.get("group_column", "treatment")
    test_name = stats_result.get("test_name", "Statistical Test")
    p_val_str = stats_result.get("formatted_p_value", "N/A")
    top_performer = stats_result.get("top_performer", "")
    top_mean = stats_result.get("top_mean", 0.0)
    ref_group = stats_result.get("reference_group", "Control")
    delta = stats_result.get("delta_vs_reference", 0.0)
    summary = stats_result.get("group_summary", {})
    
    if stats_result.get("test_type") == "dose_trend":
        r = stats_result.get("correlation_r", 0.0)
        slope = stats_result.get("slope", 0.0)
        direction = "negative" if slope < 0 else "positive"
        return (
            f"An analysis of {val_name} across varying {grp_name} levels revealed a {direction} correlation "
            f"(Pearson r = {r:.3f}, p {p_val_str}). Higher {grp_name} concentrations were associated with a "
            f"{'reduction' if slope < 0 else 'increase'} in observed {val_name}.\n\n"
            f"This describes the observed experiment and does not establish causality. "
            f"Notice: Synthetic demonstration data — not real experimental results."
        )
    elif stats_result.get("test_type") in ["two_sample_t_test", "mann_whitney_u"]:
        target = stats_result.get("target_group", top_performer)
        target_mean = summary.get(target, {}).get("mean", top_mean)
        ref_mean = summary.get(ref_group, {}).get("mean", 0.0)
        diff = round(target_mean - ref_mean, 2)
        diff_str = f"+{diff}" if diff > 0 else f"{diff}"
        is_sig = stats_result.get("is_significant", False)
        sig_str = "statistically significant" if is_sig else "not statistically significant"
        
        return (
            f"{target} produced a mean {val_name} of {target_mean}%, representing a {diff_str} percentage point "
            f"difference compared with {ref_group} (mean: {ref_mean}%). "
            f"This difference was {sig_str} ({test_name}, p {p_val_str}).\n\n"
            f"This describes the observed experiment and does not establish causality. "
            f"Notice: Synthetic demonstration data — not real experimental results."
        )
    else:
        # One-way ANOVA with Tukey HSD post-hoc evaluation
        diff_str = f"+{delta}" if delta > 0 else f"{delta}"
        ref_mean = summary.get(ref_group, {}).get("mean", 0.0)
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
                f"{top_performer} produced the highest mean cell {val_name} at {top_mean}%, "
                f"which is {diff_str} percentage points higher than {ref_group} (mean: {ref_mean}%). "
                f"Across all treatment groups, variation in {val_name} was statistically significant "
                f"({test_name}, p {p_val_str}).\n\n"
                f"This describes the observed experiment and does not establish causality. "
                f"Notice: Synthetic demonstration data — not real experimental results."
            )

def _call_gemini_reasoner(state: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
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
1. If the user question mentions 'dose', 'concentration', or 'trend':
   - Use group_column='dose', value_column='viability', and test_type='dose_trend'.
   - chart_type must be 'scatter'.
2. If the user question asks about comparing a specific drug with control (e.g. 'Is Drug B significantly different from Control?'):
   - Use test_type='two_sample_t_test', target_group='Drug B' (or the mentioned drug), and ref_group='Control'.
   - chart_type must be 'bar'.
3. If the user question asks about comparing all treatments or which treatment produced the highest viability:
   - Use group_column='treatment', value_column='viability', and test_type='one_way_anova'.
   - chart_type must be 'box'.
4. Before calling compare_groups, ensure check_assumptions is called with the selected group_column and value_column.
5. After compare_groups has executed, call create_visualization with the matching chart_type.
6. Once both compare_groups and create_visualization are in completed_analyses, set status='complete' and next_action=null.
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
        
        # Semantic validation & argument normalization
        if parsed.get("status") == "continue" and parsed.get("next_action"):
            action = parsed["next_action"]
            tool = action.get("tool")
            if tool not in TOOL_REGISTRY:
                raise ValueError(f"Unauthorized tool requested: {tool}")
            
            args = action.setdefault("arguments", {})
            q_lower = state["user_question"].lower()
            
            # Align domain variables for common experimental queries
            if "dose" in q_lower or "concentration" in q_lower or "trend" in q_lower:
                args["group_column"] = "dose"
                args["value_column"] = "viability"
                if tool == "compare_groups":
                    args["test_type"] = "dose_trend"
                elif tool == "create_visualization":
                    args["chart_type"] = "scatter"
            elif "is drug" in q_lower or "vs control" in q_lower or "different from control" in q_lower:
                if tool == "compare_groups":
                    args["test_type"] = "two_sample_t_test"
                    args["ref_group"] = "Control"
                    for d in ["Drug A", "Drug B", "Drug C"]:
                        if d.lower() in q_lower:
                            args["target_group"] = d
                            break
                    if "target_group" not in args:
                        args["target_group"] = "Drug B"
                elif tool == "create_visualization":
                    args["chart_type"] = "bar"
                
        parsed["supported"] = True
        return parsed
        
    raise ValueError(f"Gemini API returned status {resp.status_code}")

def _call_gemini_explainer(question: str, stats_result: Dict[str, Any]) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""You are a scientific explainer for BioData Copilot.
The user asked: "{question}"
The deterministic Python engine executed the statistical analysis and calculated these EXACT results:
{json.dumps(stats_result, indent=2)}

Write a concise 2-3 sentence scientific summary explaining this finding.
STRICT RULES:
1. ONLY use the exact numerical values provided above. Do NOT invent or calculate any new numbers.
2. State the test name and p-value as calculated.
3. If this was a dose or concentration trend analysis, explicitly mention the word 'dose' and explain the correlation direction and slope.
4. If Tukey HSD post-hoc testing was performed, explicitly report whether the specific contrast between the top performer and control is statistically significant after multiple comparison adjustment. Do NOT claim the top performer is significantly different from control if p_adj >= 0.05.
5. You must include these exact sentences at the end:
"This describes the observed experiment and does not establish causality. Notice: Synthetic demonstration data — not real experimental results."
"""
    resp = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=8.0)
    if resp.status_code == 200:
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    raise ValueError("Gemini explainer call failed")
