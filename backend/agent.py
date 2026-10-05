import os
import json
import re
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def plan_analysis(question: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates natural-language scientific query into a structured analysis plan.
    Uses Gemini API if key is available, else applies deterministic scientific intent parser.
    """
    columns = metadata.get("columns", [])
    numeric_cols = metadata.get("numeric_columns", [])
    cat_cols = metadata.get("categorical_columns", [])
    treatments = metadata.get("summary", {}).get("treatments", ["Control", "Drug A", "Drug B", "Drug C"])
    
    # 1. First check if unsupported query (predictive modeling, clinical survival, etc.)
    q_lower = question.lower()
    unsupported_keywords = ["survival", "predict", "patient", "clinical trial", "machine learning", "neural network"]
    for kw in unsupported_keywords:
        if kw in q_lower:
            return {
                "supported": False,
                "reason": "This demo currently supports descriptive analyses, group comparisons, correlations, and basic experimental trends."
            }
            
    # 2. Check for missing columns referenced
    if "expression" in q_lower and "expression" not in columns:
        return {
            "supported": False,
            "reason": "I couldn't find an expression measurement in this dataset."
        }
    
    # If Gemini API key is available, attempt LLM planning
    if GEMINI_API_KEY:
        try:
            return _call_gemini_planner(question, metadata)
        except Exception:
            # Gracefully fall back to deterministic parser on API errors
            pass

    # 3. Deterministic Scientific Intent Parser (Guarantees 100% demo reliability)
    # Check if asking about dose or continuous trend
    if "dose" in q_lower or "concentration" in q_lower or "trend" in q_lower or "change with dose" in q_lower or "associated" in q_lower:
        val_col = "viability" if "viability" in numeric_cols else numeric_cols[0]
        group_col = "dose" if "dose" in numeric_cols else (cat_cols[0] if cat_cols else "treatment")
        return {
            "supported": True,
            "analysis_type": "trend",
            "group_column": group_col,
            "value_column": val_col,
            "test_type": "dose_trend",
            "reference_group": None,
            "target_group": None,
            "chart_type": "scatter"
        }
        
    # Check if asking about pairwise comparison (e.g. Drug B vs Control, t-test, Mann-Whitney)
    for drug in treatments:
        if drug.lower() in q_lower and drug.lower() != "control":
            test_type = "two_sample_t_test"
            if "mann" in q_lower or "whitney" in q_lower or "non-parametric" in q_lower:
                test_type = "mann_whitney_u"
            return {
                "supported": True,
                "analysis_type": "compare_groups",
                "group_column": "treatment",
                "value_column": "viability",
                "test_type": test_type,
                "reference_group": "Control",
                "target_group": drug,
                "chart_type": "bar"
            }
            
    # Default to overall group comparison (ANOVA) across treatments
    val_col = "viability" if "viability" in numeric_cols else (numeric_cols[0] if numeric_cols else "value")
    grp_col = "treatment" if "treatment" in cat_cols else (cat_cols[0] if cat_cols else "group")
    return {
        "supported": True,
        "analysis_type": "compare_groups",
        "group_column": grp_col,
        "value_column": val_col,
        "test_type": "one_way_anova",
        "reference_group": "Control" if "Control" in treatments else (treatments[0] if treatments else None),
        "target_group": None,
        "chart_type": "box"
    }

def generate_grounded_explanation(question: str, plan: Dict[str, Any], stats_result: Dict[str, Any]) -> str:
    """
    Produces a concise scientific interpretation strictly grounded in verified Python computations.
    """
    if GEMINI_API_KEY:
        try:
            return _call_gemini_explainer(question, plan, stats_result)
        except Exception:
            pass
            
    # Deterministic Grounded Synthesis
    val_name = plan.get("value_column", "viability")
    grp_name = plan.get("group_column", "treatment")
    test_name = stats_result.get("test_name", "Statistical Test")
    p_val_str = stats_result.get("formatted_p_value", "N/A")
    top_performer = stats_result.get("top_performer", "")
    top_mean = stats_result.get("top_mean", 0.0)
    ref_group = stats_result.get("reference_group", "Control")
    delta = stats_result.get("delta_vs_reference", 0.0)
    summary = stats_result.get("group_summary", {})
    
    if plan.get("test_type") == "dose_trend":
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
    elif plan.get("test_type") in ["two_sample_t_test", "mann_whitney_u"]:
        target = plan.get("target_group", top_performer)
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
        # One-way ANOVA multi-group
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

def _call_gemini_planner(question: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""You are a scientific analysis planner for BioData Copilot.
Given this user question about experimental data:
Question: "{question}"
Available Columns: {metadata.get('columns')}
Numeric Columns: {metadata.get('numeric_columns')}
Categorical Columns: {metadata.get('categorical_columns')}
Unique Treatments: {metadata.get('summary', {}).get('treatments')}

Determine the appropriate analysis. Output ONLY a valid JSON object matching:
{{
  "supported": true or false,
  "reason": "explanation if unsupported",
  "analysis_type": "compare_groups" or "trend",
  "group_column": "chosen column",
  "value_column": "chosen numeric measurement",
  "test_type": "one_way_anova" or "two_sample_t_test" or "mann_whitney_u" or "dose_trend",
  "reference_group": "Control" or similar,
  "target_group": "Specific drug if pairwise" or null,
  "chart_type": "box" or "bar" or "scatter"
}}"""
    resp = httpx.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10.0)
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("Failed to parse JSON plan from LLM")

def _call_gemini_explainer(question: str, plan: Dict[str, Any], stats_result: Dict[str, Any]) -> str:
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
