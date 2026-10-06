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
