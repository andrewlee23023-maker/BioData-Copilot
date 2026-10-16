import os
import pytest
import pandas as pd
from backend.agent import run_agent_reasoning_loop, execute_tool, TOOL_REGISTRY

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "synthetic_viability.csv")

@pytest.fixture
def df():
    return pd.read_csv(DATA_PATH)

def test_unauthorized_tool_prevention(df):
    """Ensures agent cannot execute arbitrary code or unauthorized tools."""
    with pytest.raises(ValueError) as excinfo:
        execute_tool("arbitrary_python_executor", {"code": "import os"}, df)
    assert "Unauthorized tool" in str(excinfo.value)

def test_agent_pairwise_drug_b(df):
    """
    Test 1: Pairwise comparison for Drug B vs Control.
    Must return explicit pairwise semantics and never mention Drug A in explanation.
    """
    question = "Is Drug B significantly different from Control?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is True
    stats = result["stats"]
    assert stats["comparison_type"] == "pairwise"
    assert stats["target_group"] == "Drug B"
    assert stats["reference_group"] == "Control"
    assert stats["difference_pp"] == 4.04
    assert stats["test"] in ["Welch's t-test", "Welch's Two-Sample t-test"]
    assert stats["significant"] is True
    
    # Critical guardrail against explanation hallucination
    assert "Drug B" in result["interpretation"]
    assert "Drug A" not in result["interpretation"]

def test_agent_pairwise_drug_a(df):
    """
    Test 2: Pairwise comparison for Drug A vs Control.
    Must return explicit target_group = Drug A and never mention Drug B in explanation.
    """
    question = "Is Drug A significantly different from Control?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is True
    stats = result["stats"]
    assert stats["comparison_type"] == "pairwise"
    assert stats["target_group"] == "Drug A"
    assert stats["reference_group"] == "Control"
    
    # Critical guardrail against explanation hallucination
    assert "Drug A" in result["interpretation"]
    assert "Drug B" not in result["interpretation"]

def test_agent_descriptive_highest_viability(df):
    """
    Test 3: Descriptive question must execute summarize_groups without unnecessary hypothesis test.
    """
    question = "Which treatment has the highest mean viability?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is True
    stats = result["stats"]
    assert stats["comparison_type"] == "descriptive"
    assert stats["top_performer"] == "Drug B"
    
    completed = result["agent_state"]["completed_analyses"]
    assert "summarize_groups" in completed
    assert "compare_groups" not in completed  # No unnecessary ANOVA or t-test

def test_agent_filtered_dose_response(df):
    """
    Test 4: Specific drug dose query must call filter_dataset before analyzing dose response.
    """
    question = "How does Drug B respond to dose?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is True
    completed = result["agent_state"]["completed_analyses"]
    assert "filter_dataset" in completed
    assert "compare_groups" in completed
    assert result["stats"]["comparison_type"] == "dose_trend"

def test_agent_general_dose_trend(df):
    """
    Test 5: General dose question must evaluate trend across all doses.
    """
    question = "How does viability change with dose?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is True
    assert result["stats"]["comparison_type"] == "dose_trend"
    assert "dose" in result["interpretation"].lower()

def test_agent_unsupported_category_refusal(df):
    """
    Test 6: Unsupported clinical/predictive question must trigger graceful policy refusal.
    """
    question = "Can you predict patient survival?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is False
    assert "currently supports" in result["reason"]

def test_agent_missing_column_refusal(df):
    """
    Test 7: Query referencing unmeasured column must be refused with clear reason.
    """
    question = "Show gene expression across treatments"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is False
    assert "expression" in result["reason"]

def test_filter_dataset_tool_direct(df):
    """
    Test 8: Direct execution of filter_dataset tool.
    """
    res = execute_tool("filter_dataset", {"filters": {"treatment": ["Drug B", "Control"]}}, df)
    assert res["filtered_rows"] == 19 + 34
    assert res["original_rows"] == 127
    assert set(res["remaining_groups"]["treatment"]) == {"Drug B", "Control"}


# ===========================================================================
# Tool validation, plan validation, guardrail enforcement, explanation grounding
# ===========================================================================
import re
import backend.agent as agent
from backend.agent import (
    ToolRequestError, validate_tool_request, _validate_llm_decision, decide_next_action,
    _validate_explanation_entities, _generate_explanation_with_source,
)


def tiny_df():
    """Control n=6, Drug A n=6, Drug B n=2 (Drug B is below the n >= 3 policy)."""
    rows = []
    for g, vals in {"Control": [90, 91, 92, 90, 91, 93], "Drug A": [70, 71, 72, 69, 70, 73], "Drug B": [95, 96]}.items():
        rows += [{"treatment": g, "dose": 10.0, "viability": float(v)} for v in vals]
    return pd.DataFrame(rows)


# --- tool request validation ------------------------------------------------------
def test_validate_rejects_unknown_tool_and_bad_arg_shapes(df):
    with pytest.raises(ToolRequestError, match="Unauthorized tool"):
        validate_tool_request("os_system", {}, df)
    with pytest.raises(ToolRequestError):
        validate_tool_request(None, {}, df)
    with pytest.raises(ToolRequestError, match="must be an object"):
        validate_tool_request("compare_groups", ["treatment"], df)
    with pytest.raises(ToolRequestError, match="Unexpected argument"):
        validate_tool_request("compare_groups", {"code": "import os"}, df)
    with pytest.raises(ToolRequestError, match="Unexpected argument"):
        validate_tool_request("inspect_dataset", {"group_column": "treatment"}, df)


def test_validate_rejects_missing_columns_without_guessing(df):
    with pytest.raises(ToolRequestError) as exc:
        validate_tool_request("compare_groups", {"group_column": "treatment", "value_column": "expression"}, df)
    assert exc.value.error_type == "missing_column"
    assert "expression" in str(exc.value) and "viability" in str(exc.value)  # lists available columns
    with pytest.raises(ToolRequestError) as exc:
        validate_tool_request("filter_dataset", {"filters": {"nope": ["x"]}}, df)
    assert exc.value.error_type == "missing_column"
    with pytest.raises(ToolRequestError):
        execute_tool("check_assumptions", {"group_column": "nope", "value_column": "viability"}, df)


def test_validate_rejects_unsupported_test_and_chart(df):
    with pytest.raises(ToolRequestError, match="Unsupported test_type"):
        validate_tool_request("compare_groups", {"test_type": "two_way_anova"}, df)
    with pytest.raises(ToolRequestError, match="Unsupported chart_type"):
        validate_tool_request("create_visualization", {"chart_type": "violin"}, df)
    with pytest.raises(ToolRequestError, match="filters"):
        validate_tool_request("filter_dataset", {"filters": "treatment=Drug B"}, df)


def test_validate_normalizes_defaults_and_empty_placeholders(df):
    args = validate_tool_request("compare_groups", {"group_column": "treatment", "value_column": "viability",
                                                    "ref_group": "", "target_group": None, "test_type": ""}, df)
    assert args["test_type"] == "one_way_anova" and args["ref_group"] == "Control"
    assert "target_group" not in args


def test_execute_tool_compare_groups_returns_blocked_not_exception():
    res = execute_tool("compare_groups", {"group_column": "treatment", "value_column": "viability",
                                          "test_type": "one_way_anova"}, tiny_df())
    assert res["blocked"] is True and "p_value" not in res


# --- LLM plan validation: Python decides what is acceptable ---------------------------------
def _state(completed=("inspect_dataset",)):
    return {"user_question": "q", "completed_analyses": list(completed)}


def test_llm_plan_validation_rejects_bad_plans(df):
    bad_plans = [
        {"status": "maybe"},
        "not a dict",
        {"status": "continue"},                                                       # no action
        {"status": "continue", "next_action": {"tool": "os_system", "arguments": {}}},  # unknown tool
        {"status": "continue", "next_action": {"tool": "inspect_dataset", "arguments": {}}},  # repeats tool
        {"status": "continue", "next_action": {"tool": "compare_groups",
                                               "arguments": {"group_column": "nope", "value_column": "viability"}}},
        {"status": "continue", "next_action": {"tool": "compare_groups", "arguments": {"test_type": "bayes"}}},
        {"status": "complete"},                                                       # nothing computed yet
    ]
    for plan in bad_plans:
        with pytest.raises(ToolRequestError):
            _validate_llm_decision(plan, _state(), df)


def test_llm_plan_validation_accepts_good_plan(df):
    plan = {"status": "continue", "reason": "r", "next_action": {
        "tool": "compare_groups", "arguments": {"group_column": "treatment", "value_column": "viability",
                                                "test_type": "one_way_anova", "target_group": ""}}}
    out = _validate_llm_decision(plan, _state(), df)
    assert out["next_action"]["arguments"]["ref_group"] == "Control"
    done = _validate_llm_decision({"status": "complete"}, _state(("inspect_dataset", "compare_groups")), df)
    assert done["status"] == "complete"


def test_invalid_gemini_plan_falls_back_to_deterministic_planner(df, monkeypatch):
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(agent, "_call_gemini_reasoner", lambda state: {
        "status": "continue", "reason": "hack", "supported": True,
        "next_action": {"tool": "exec_python", "arguments": {"code": "import os"}}})
    monkeypatch.setattr(agent, "_call_gemini_explainer", lambda q, s: (_ for _ in ()).throw(RuntimeError("down")))
    result = run_agent_reasoning_loop(df, "Is Drug B significantly different from Control?")
    assert result["supported"] is True
    assert result["plan_rejections"] and "Unauthorized tool" in result["plan_rejections"][0]
    assert any(s["tool"] == "plan_validation" and s["status"] == "refused" for s in result["steps"])
    assert "Deterministic" in result["planner"]
    assert result["stats"]["comparison_type"] == "pairwise"


def test_gemini_planner_used_when_plan_is_valid(df, monkeypatch):
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(agent, "_call_gemini_reasoner", lambda state: {
        "status": "continue", "reason": "ok", "supported": True,
        "next_action": {"tool": "check_assumptions",
                        "arguments": {"group_column": "treatment", "value_column": "viability"}}})
    decision = decide_next_action({**_state(), "dataset_metadata": {"numeric_columns": ["viability"],
                                   "categorical_columns": ["treatment"], "columns": list(df.columns)}}, df)
    assert decision["planner"] == f"Gemini ({agent.GEMINI_MODEL})"


# --- the LLM cannot bypass the statistical guardrails ------------------------------------------
def test_llm_skipping_assumption_check_still_cannot_run_blocked_test(monkeypatch):
    """Gemini jumps straight to compare_groups on an inadequate dataset: Python still blocks it."""
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "fake-key")
    sequence = iter([
        {"status": "continue", "reason": "skip checks", "supported": True, "next_action": {
            "tool": "compare_groups", "arguments": {"group_column": "treatment", "value_column": "viability",
                                                    "test_type": "two_sample_t_test", "ref_group": "Control",
                                                    "target_group": "Drug B"}}},
        {"status": "complete", "reason": "done", "supported": True, "next_action": None},
    ])
    monkeypatch.setattr(agent, "_call_gemini_reasoner", lambda state: next(sequence))
    explainer_calls = []
    monkeypatch.setattr(agent, "_call_gemini_explainer", lambda q, s: explainer_calls.append(1) or "Drug B is significant, p = 0.001")
    result = run_agent_reasoning_loop(tiny_df(), "Is Drug B significantly different from Control?")
    assert result["supported"] is True
    assert result["stats"]["blocked"] is True
    assert "p_value" not in result["stats"]
    assert explainer_calls == []                      # Gemini never narrates a blocked result
    assert "not run" in result["interpretation"]
    assert "significant" not in result["interpretation"].lower().replace("not significant", "")
    assert result["statistical_audit"]["status"] == "blocked"
    assert result["statistical_audit"]["p_value"] is None
    trace = {t["key"]: t["status"] for t in result["analysis_trace"]}
    assert trace["test_executed"] == "blocked" and trace["sample_sizes_checked"] == "failed"
    assert any(s["status"] == "refused" and "blocked" in s["label"].lower() for s in result["steps"])


def test_blocked_deterministic_flow_returns_descriptive_and_trace():
    result = run_agent_reasoning_loop(tiny_df(), "Is Drug B significantly different from Control?")
    assert result["supported"] is True and result["stats"]["blocked"] is True
    assert result["stats"]["group_summary"]["Drug B"]["n"] == 2          # descriptive still present
    assert result["statistical_audit"]["n_per_group"] == {"Drug B": 2, "Control": 6}
    assert "completed_analyses" in result["agent_state"]
    assert "Drug B: 95.5% (n = 2)" in result["interpretation"]


def test_agent_invalid_request_becomes_structured_refusal(df, monkeypatch):
    monkeypatch.setattr(agent, "_deterministic_reasoner", lambda state, d: {
        "status": "continue", "supported": True, "reason": "bad",
        "next_action": {"tool": "summarize_groups", "arguments": {"group_column": "treatment", "value_column": "nope"}}})
    result = run_agent_reasoning_loop(df, "Summarize treatments")
    assert result["supported"] is False
    assert result["error_type"] == "missing_column"
    assert "nope" in result["reason"]


def test_unsupported_and_missing_column_refusals_have_error_types(df):
    assert run_agent_reasoning_loop(df, "Can you predict patient survival?")["error_type"] == "unsupported_question"
    assert run_agent_reasoning_loop(df, "Show gene expression across treatments")["error_type"] == "missing_column"


def test_dataset_without_numeric_measurement_is_refused():
    only_text = pd.DataFrame({"treatment": ["A", "B"] * 5, "note": ["x"] * 10})
    result = run_agent_reasoning_loop(only_text, "Compare treatments")
    assert result["supported"] is False and result["error_type"] == "unsuitable_dataset"


# --- explanation grounding ------------------------------------------------------------------
PAIR = {"comparison_type": "pairwise", "target_group": "Drug B", "reference_group": "Control",
        "group_summary": {"Control": {"mean": 91.0}, "Drug A": {"mean": 62.0}, "Drug B": {"mean": 95.0}}}


def test_entity_validation_pairwise():
    assert _validate_explanation_entities("Drug B exceeded Control (p < 0.001).", PAIR) is True
    assert _validate_explanation_entities("Drug B was higher.", PAIR) is False                      # reference missing
    assert _validate_explanation_entities("Control was lower.", PAIR) is False                      # target missing
    assert _validate_explanation_entities("Drug B beat Control, unlike Drug A.", PAIR) is False     # stray entity


def test_entity_validation_dose_and_descriptive():
    dose = {"comparison_type": "dose_trend"}
    assert _validate_explanation_entities("Higher dose reduced viability.", dose) is True
    assert _validate_explanation_entities("Viability fell.", dose) is False
    desc = {"comparison_type": "descriptive", "top_performer": "Drug B"}
    assert _validate_explanation_entities("Drug B was highest.", desc) is True
    assert _validate_explanation_entities("Drug A was highest.", desc) is False


def test_gemini_explanation_accepted_only_if_grounded(df, monkeypatch):
    stats = run_agent_reasoning_loop(df, "Is Drug B significantly different from Control?")["stats"]
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(agent, "_call_gemini_explainer", lambda q, s: "Drug B differed from Control (Welch, p < 0.001).")
    text, source = _generate_explanation_with_source("q", {}, stats)
    assert source == "gemini" and "does not establish causality" in text     # disclaimer enforced by Python
    monkeypatch.setattr(agent, "_call_gemini_explainer", lambda q, s: "Drug A was far worse than Drug B and Control.")
    text, source = _generate_explanation_with_source("q", {}, stats)
    assert source == "deterministic_template" and "Drug A" not in text       # hallucinated entity rejected
    monkeypatch.setattr(agent, "_call_gemini_explainer", lambda q, s: (_ for _ in ()).throw(RuntimeError("timeout")))
    assert _generate_explanation_with_source("q", {}, stats)[1] == "deterministic_template"


def test_anova_explanation_carries_variance_caution(df):
    result = run_agent_reasoning_loop(df, "Are treatments significantly different overall?")
    assert result["stats"]["comparison_type"] == "multi_group_anova"
    assert "variances differ substantially" in result["interpretation"]
    assert result["analysis_trace"][4]["status"] == "executed"
    assert result["statistical_audit"]["computed_by"] == "Python / SciPy"


# --- configuration -----------------------------------------------------------------------------
def test_gemini_model_is_configured_in_one_place():
    src = open(agent.__file__, encoding="utf-8").read()
    assert len(re.findall(r"gemini-[0-9][\w.\-]*", src)) == 1      # only the default in GEMINI_MODEL
    assert agent.GEMINI_MODEL in agent.GEMINI_URL


# ===========================================================================
# Planner routing fixes: two-group comparisons and unknown-group clarification
# ===========================================================================

def test_pairwise_two_named_groups_compares_both(df):
    """'Compare Drug A and Drug B' must compare A vs B, not A vs Control."""
    r = run_agent_reasoning_loop(df, "Compare Drug A and Drug B")
    audit = r["statistical_audit"]
    assert r["supported"] is True
    assert audit["groups"] == ["Drug A", "Drug B"]
    assert audit["selected_test"] == "Welch's Two-Sample t-test"


def test_pairwise_reversed_order_names_target_first(df):
    """Question order decides target vs reference: 'Drug B vs Drug A' -> B vs A."""
    r = run_agent_reasoning_loop(df, "Is Drug B different from Drug A?")
    audit = r["statistical_audit"]
    assert r["supported"] is True
    assert audit["groups"] == ["Drug B", "Drug A"]


def test_pairwise_single_named_group_defaults_to_control(df):
    """One named group keeps the previous Control default."""
    r = run_agent_reasoning_loop(df, "Is Drug B significantly different?")
    audit = r["statistical_audit"]
    assert r["supported"] is True
    assert audit["groups"] == ["Drug B", "Control"]


def test_unknown_group_returns_clarification(df):
    """A nonexistent group is a clarification, not a silent ANOVA rerun."""
    r = run_agent_reasoning_loop(df, "Is Drug Z significantly different from Control?")
    assert r["supported"] is False
    assert r["error_type"] == "unknown_group"
    assert "Drug Z" in r["reason"]
    assert "Control, Drug A, Drug B, Drug C" in r["reason"]


def test_unknown_group_dose_question_returns_clarification(df):
    r = run_agent_reasoning_loop(df, "How does Drug Z respond to dose?")
    assert r["supported"] is False
    assert r["error_type"] == "unknown_group"


def test_generic_drug_mention_is_not_flagged(df):
    """Prose like 'drug response mechanism' must not trigger the unknown-group guard."""
    r = run_agent_reasoning_loop(df, "What is the drug response mechanism?")
    assert r.get("error_type") != "unknown_group"
