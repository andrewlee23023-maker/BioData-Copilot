import os
import pytest
import pandas as pd
from backend.tools.inspect import inspect_dataset
from backend.tools.stats import summarize_groups, compare_groups
from backend.tools.viz import generate_plotly_spec

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "synthetic_viability.csv")

@pytest.fixture
def demo_df():
    assert os.path.exists(DATA_PATH), f"Data file missing at {DATA_PATH}"
    return pd.read_csv(DATA_PATH)

def test_inspect_dataset(demo_df):
    info = inspect_dataset(demo_df)
    assert info["rows"] == 127
    assert "treatment" in info["columns"]
    assert "viability" in info["columns"]
    assert info["summary"]["treatments_count"] == 4
    assert info["summary"]["doses_count"] == 3
    assert info["summary"]["replicates_count"] == 3
    assert "Control" in info["summary"]["treatments"]

def test_summarize_groups(demo_df):
    summary = summarize_groups(demo_df, "treatment", "viability")
    assert "Control" in summary
    assert "Drug B" in summary
    assert summary["Drug B"]["mean"] > summary["Control"]["mean"]
    assert summary["Control"]["n"] > 0
    assert summary["Drug B"]["std"] > 0

def test_check_assumptions(demo_df):
    from backend.tools.stats import check_assumptions
    assumptions = check_assumptions(demo_df, "treatment", "viability")
    assert assumptions["sample_size_adequate"] is True
    assert assumptions["sample_size_status"] == "Adequate"
    assert assumptions["normality_status"] == "Not assessed"
    assert "variance_status" in assumptions
    assert assumptions["scientific_summary"] == "Sample size and variance checks completed."

def test_compare_groups_anova(demo_df):
    res = compare_groups(demo_df, "treatment", "viability", test_type="one_way_anova", ref_group="Control")
    assert res["test_name"] == "One-way ANOVA"
    assert res["top_performer"] == "Drug B"
    assert res["p_value"] < 0.05
    assert res["delta_vs_reference"] > 0
    assert res["posthoc_performed"] is True
    assert res["posthoc_test"] == "Tukey HSD (Family-Wise Error Rate Controlled)"
    assert len(res["pairwise_comparisons"]) == 6
    assert "top_vs_reference_posthoc" in res
    assert res["top_vs_reference_posthoc"]["comparison"] == "Drug B vs Control"
    assert "causality_disclaimer" in res["guardrails"]
    assert "synthetic_disclaimer" in res["guardrails"]

def test_compare_groups_ttest(demo_df):
    res = compare_groups(demo_df, "treatment", "viability", test_type="two_sample_t_test", ref_group="Control", target_group="Drug B")
    assert res["test_name"] == "Welch's Two-Sample t-test"
    assert "t_statistic" in res
    assert "p_value" in res

def test_generate_plotly_spec(demo_df):
    plan = {"group_column": "treatment", "value_column": "viability", "chart_type": "box"}
    stats_res = compare_groups(demo_df, "treatment", "viability")
    spec = generate_plotly_spec(demo_df, plan, stats_res)
    assert "data" in spec
    assert "layout" in spec
    assert len(spec["data"]) > 0
