import os
import pytest
import pandas as pd
from backend.agent import run_agent_reasoning_loop, execute_tool, TOOL_REGISTRY

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "synthetic_viability.csv")

@pytest.fixture
def df():
    return pd.read_csv(DATA_PATH)

def test_unauthorized_tool_prevention(df):
    with pytest.raises(ValueError) as excinfo:
        execute_tool("arbitrary_python_executor", {"code": "import os"}, df)
    assert "Unauthorized tool" in str(excinfo.value)

def test_agent_reasoning_loop_highest_viability(df):
    question = "Which treatment produced the highest cell viability compared with control?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is True
    assert result["stats"]["top_performer"] == "Drug B"
    assert "data" in result["plotly_spec"]
    assert "Drug B" in result["interpretation"]
    assert "not establish causality" in result["interpretation"]
    
    # Verify Agent State and Tool History
    state = result["agent_state"]
    assert state["user_question"] == question
    assert "inspect_dataset" in state["completed_analyses"]
    assert "check_assumptions" in state["completed_analyses"]
    assert "compare_groups" in state["completed_analyses"]
    assert "create_visualization" in state["completed_analyses"]
    
    # Verify tool history trace
    history = state["tool_history"]
    assert len(history) >= 4
    for entry in history:
        assert "tool" in entry
        assert "arguments" in entry
        assert "reason" in entry

def test_agent_reasoning_loop_dose_trend(df):
    question = "How does viability change with dose?"
    result = run_agent_reasoning_loop(df, question)
    
    assert result["supported"] is True
    state = result["agent_state"]
    assert "compare_groups" in state["completed_analyses"]
    assert "create_visualization" in state["completed_analyses"]
    assert "dose" in result["interpretation"]

def test_agent_unsupported_question_refusal(df):
    question = "Predict patient survival based on viability"
    result = run_agent_reasoning_loop(df, question)
    assert result["supported"] is False
    assert "currently supports descriptive analyses" in result["reason"]

def test_filter_dataset_tool(df):
    from backend.agent import execute_tool
    res = execute_tool("filter_dataset", {"filters": {"treatment": ["Drug B", "Control"]}}, df)
    assert res["filtered_rows"] == 19 + 34
    assert res["original_rows"] == 127
    assert set(res["remaining_groups"]["treatment"]) == {"Drug B", "Control"}

