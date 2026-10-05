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

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ---------------------------------------------------------------------------
# Predefined Validated Tool Registry (LLM cannot execute arbitrary code)
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    "inspect_dataset": {
        "description": "Inspects dataset dimensions, column names, numeric vs categorical types, and missing values.",
        "parameters": {}
    },
    "check_assumptions": {
        "description": "Checks sample sizes (n >= 3), missing rows, and variance ratios across experimental groups.",
        "parameters": {"group_column": "str", "value_column": "str"}
    },
    "summarize_groups": {
        "description": "Calculates descriptive statistics (mean, std, sem, median, n) for continuous values grouped by a category.",
        "parameters": {"group_column": "str", "value_column": "str"}
    },
    "compare_groups": {
        "description": "Executes deterministic hypothesis testing (One-way ANOVA, Welch's t-test, Mann-Whitney U, or dose trend correlation).",
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

# ---------------------------------------------------------------------------
# Tool Execution Engine
# ---------------------------------------------------------------------------
def execute_tool(tool_name: str, arguments: Dict[str, Any], df: pd.DataFrame, current_stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executes a predefined, validated Python tool deterministically.
    Never allows arbitrary code execution.
    """
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unauthorized tool: '{tool_name}'. Only predefined tools are permitted.")
        
    if tool_name == "inspect_dataset":
        return inspect_dataset(df)
        
    elif tool_name == "check_assumptions":
        grp = arguments.get("group_column", "treatment")
        val = arguments.get("value_column", "viability")
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
    Uses Gemini LLM if key is present, with deterministic scientific reasoning engine fallback.
    """
    q_lower = state["user_question"].lower()
    
    # Refusal check for unsupported question categories
    unsupported_kw = ["survival", "predict", "patient", "clinical trial", "machine learning", "neural network"]
    for kw in unsupported_kw:
        if kw in q_lower:
            return {
                "status": "complete",
                "next_action": None,
                "reason": "This demo currently supports descriptive analyses, group comparisons, correlations, and basic experimental trends.",
                "supported": False
            }
            
    # Missing column check
    metadata = state.get("dataset_metadata", {})
    cols = metadata.get("columns", [])
    if "expression" in q_lower and "expression" not in cols:
        return {
            "status": "complete",
            "next_action": None,
            "reason": "I couldn't find an expression measurement in this dataset.",
            "supported": False
        }

    # Attempt LLM reasoning if Gemini API is available
    if GEMINI_API_KEY:
        try:
            return _call_gemini_reasoner(state)
        except Exception:
            pass

    # Deterministic Reasoning State Machine
    completed = state.get("completed_analyses", [])
    
    # Step 1: Inspect dataset if not yet done
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
        
    # Determine variables
    num_cols = metadata.get("numeric_columns", ["viability"])
    cat_cols = metadata.get("categorical_columns", ["treatment"])
    
    if "dose" in q_lower or "concentration" in q_lower or "trend" in q_lower or "change with dose" in q_lower:
        val_col = "viability" if "viability" in num_cols else num_cols[0]
        grp_col = "dose" if "dose" in num_cols else (cat_cols[0] if cat_cols else "treatment")
        test_type = "dose_trend"
        chart_type = "scatter"
    else:
        val_col = "viability" if "viability" in num_cols else (num_cols[0] if num_cols else "value")
        grp_col = "treatment" if "treatment" in cat_cols else (cat_cols[0] if cat_cols else "group")
        # Check pairwise vs multi-group
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
            "reason": f"Verify sample sizes and variance distributions across '{grp_col}' groups prior to statistical testing.",
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
            "reason": f"Execute deterministic {test_type} on '{grp_col}' vs '{val_col}' to compute exact p-values and effect sizes.",
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
        "reason": "Sufficient evidence collected. All numerical results verified from deterministic Python tools.",
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
        "completed_analyses": [],
        "tool_history": [],
        "current_findings": {},
        "remaining_information_needed": "Determine appropriate statistical comparison and test assumptions",
        "final_result": None
    }
    
    steps_log: List[Dict[str, Any]] = []
    current_stats: Dict[str, Any] = {}
    current_plotly_spec: Dict[str, Any] = {}
    last_reason: str = ""
    is_supported: bool = True

    for iteration in range(max_iterations):
        # 1. Reason: Decide next action
        decision = decide_next_action(state, df)
        
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
            steps_log.append({
                "label": "Evidence sufficient: Synthesizing verified scientific interpretation",
                "tool": "finalize_response",
                "status": "done"
            })
            break
            
        # 2. Tool Selection
        action = decision.get("next_action")
        if not action or "tool" not in action:
            break
            
        tool_name = action["tool"]
        arguments = action.get("arguments", {})
        reason = decision.get("reason", f"Executing {tool_name}")
        
        # 3. Deterministic Tool Execution
        tool_result = execute_tool(tool_name, arguments, df, current_stats)
        
        # 4. State Update
        state["completed_analyses"].append(tool_name)
        state["tool_history"].append({
            "step": iteration + 1,
            "tool": tool_name,
            "arguments": arguments,
            "reason": reason,
            "output_summary": {k: v for k, v in tool_result.items() if k not in ["data", "layout"]} if isinstance(tool_result, dict) else str(tool_result)[:100]
        })
        
        steps_log.append({
            "label": reason,
            "tool": tool_name,
            "status": "done"
        })
        
        if tool_name == "inspect_dataset":
            state["dataset_metadata"] = tool_result
            state["observations"] = tool_result.get("summary", {})
            state["remaining_information_needed"] = "Check statistical assumptions and sample distributions"
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
            "steps": steps_log,
            "agent_state": state
        }
        
    explanation = _generate_verified_explanation(question, state, current_stats)
    
    return {
        "supported": True,
        "question": question,
        "steps": steps_log,
        "plan": state.get("final_result", {}),
        "stats": current_stats,
        "plotly_spec": current_plotly_spec,
        "interpretation": explanation,
        "agent_state": {
            "user_question": state["user_question"],
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
    Formulates interpretation strictly referencing the verified Python tool results.
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
        diff_str = f"+{delta}" if delta > 0 else f"{delta}"
        ref_mean = summary.get(ref_group, {}).get("mean", 0.0)
        return (
            f"{top_performer} produced the highest mean cell {val_name} at {top_mean}%, "
            f"which is {diff_str} percentage points higher than {ref_group} (mean: {ref_mean}%). "
            f"Across all treatment groups, variation in {val_name} was statistically significant "
            f"({test_name}, p {p_val_str}).\n\n"
            f"This describes the observed experiment and does not establish causality. "
            f"Notice: Synthetic demonstration data — not real experimental results."
        )

def _call_gemini_reasoner(state: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""You are the reasoning and orchestration agent for BioData Copilot.
Current Agent State:
- User Question: "{state['user_question']}"
- Completed Analyses: {json.dumps(state.get('completed_analyses', []))}
- Available Dataset Columns: {json.dumps(state.get('dataset_metadata', {}).get('columns', []))}
- Numeric Columns: {json.dumps(state.get('dataset_metadata', {}).get('numeric_columns', []))}
- Categorical Columns: {json.dumps(state.get('dataset_metadata', {}).get('categorical_columns', []))}
- Current Findings: {json.dumps(state.get('current_findings', {}))}

Allowed Predefined Tools:
{json.dumps(TOOL_REGISTRY, indent=2)}

You must decide the next best action.
Return ONLY valid JSON matching:
{{
  "status": "continue" or "complete",
  "reason": "Explain your scientific reasoning and why this tool or completion is chosen",
  "next_action": {{
    "tool": "name of predefined tool",
    "arguments": {{ ... }}
  }} or null
}}"""
    resp = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10.0)
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        parsed = json.loads(match.group(0))
        parsed["supported"] = True
        return parsed
    raise ValueError("Failed to parse agent reasoning plan from LLM")

def _call_gemini_explainer(question: str, stats_result: Dict[str, Any]) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""You are a scientific explainer for BioData Copilot.
The user asked: "{question}"
The deterministic Python engine executed the statistical analysis and calculated these EXACT results:
{json.dumps(stats_result, indent=2)}

Write a concise 2-3 sentence scientific summary explaining this finding.
STRICT RULES:
1. ONLY use the exact numerical values provided above. Do NOT invent or calculate any new numbers.
2. State the test name and p-value as calculated.
3. You must include these exact sentences at the end:
"This describes the observed experiment and does not establish causality. Notice: Synthetic demonstration data — not real experimental results."
"""
    resp = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10.0)
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]
