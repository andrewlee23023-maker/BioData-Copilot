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


# ===========================================================================
# Scientific guardrail tests
# ===========================================================================
import numpy as np
from scipy import stats as scipy_stats
from backend.tools import stats as stats_mod
from backend.tools.stats import check_assumptions, MIN_N_PER_GROUP


def make_df(sizes, seed=0, value_col="viability", group_col="treatment"):
    """Synthetic dataset: {group: n} with clearly different means and some spread."""
    rng = np.random.default_rng(seed)
    rows = []
    for i, (g, n) in enumerate(sizes.items()):
        for v in rng.normal(80 + 5 * i, 2.0, n):
            rows.append({group_col: g, value_col: round(float(v), 2)})
    return pd.DataFrame(rows)


@pytest.fixture
def valid_df():
    return make_df({"Control": 6, "Drug A": 6, "Drug B": 6})


INFERENTIAL = [
    ("one_way_anova", {}),
    ("two_sample_t_test", {"ref_group": "Control", "target_group": "Drug B"}),
    ("mann_whitney_u", {"ref_group": "Control", "target_group": "Drug B"}),
    ("dose_trend", {}),
]


@pytest.fixture
def spy_inferential(monkeypatch):
    """Wraps every SciPy inferential function used by stats.py and records calls."""
    calls = []
    for name in ["f_oneway", "ttest_ind", "mannwhitneyu", "pearsonr", "linregress", "tukey_hsd"]:
        original = getattr(scipy_stats, name)

        def wrapper(*a, _n=name, _o=original, **k):
            calls.append(_n)
            return _o(*a, **k)

        monkeypatch.setattr(scipy_stats, name, wrapper)
    return calls


def test_min_sample_policy_is_three():
    assert MIN_N_PER_GROUP == 3


# --- valid dataset -----------------------------------------------------------
def test_valid_dataset_is_allowed(valid_df):
    res = check_assumptions(valid_df, "treatment", "viability")
    assert res["inferential_allowed"] is True
    assert res["blocked_reasons"] == []
    assert res["sample_size_adequate"] is True
    assert res["min_required_n"] == 3
    assert res["normality_status"] == "Not assessed"


def test_exactly_three_per_group_is_allowed():
    df = make_df({"Control": 3, "Drug B": 3})
    res = compare_groups(df, "treatment", "viability", "two_sample_t_test", ref_group="Control", target_group="Drug B")
    assert res["blocked"] is False
    assert "p_value" in res


# --- n < 3 per group ---------------------------------------------------------
@pytest.mark.parametrize("test_type,kwargs", INFERENTIAL[:3])
def test_n_below_three_blocks_inference(test_type, kwargs):
    df = make_df({"Control": 6, "Drug A": 6, "Drug B": 2})
    res = compare_groups(df, "treatment", "viability", test_type, **kwargs)
    assert res["blocked"] is True
    assert res["analysis_status"] == "blocked"
    assert any(r["code"] == "insufficient_sample_size" for r in res["blocked_reasons"])
    assert "p_value" not in res and "test_name" not in res
    assert "Drug B" in res["blocked_message"]


def test_pairwise_only_checks_the_two_compared_groups():
    """A tiny, unrelated group must not block a pairwise test between two adequate groups."""
    df = make_df({"Control": 6, "Drug A": 6, "Drug B": 2})
    res = compare_groups(df, "treatment", "viability", "two_sample_t_test", ref_group="Control", target_group="Drug A")
    assert res["blocked"] is False and "p_value" in res


# --- missing column ----------------------------------------------------------
def test_missing_measurement_column(valid_df):
    res = compare_groups(valid_df, "treatment", "no_such_column")
    assert res["blocked"] is True
    assert res["blocked_reasons"][0]["code"] == "missing_column"
    assert "no_such_column" in res["blocked_message"]
    assert check_assumptions(valid_df, "treatment", "no_such_column")["inferential_allowed"] is False
    with pytest.raises(ValueError):
        summarize_groups(valid_df, "treatment", "no_such_column")


def test_missing_group_column(valid_df):
    res = compare_groups(valid_df, "no_such_group", "viability")
    assert res["blocked"] is True and res["blocked_reasons"][0]["code"] == "missing_column"


# --- only one group ----------------------------------------------------------
@pytest.mark.parametrize("test_type", ["one_way_anova", "two_sample_t_test", "mann_whitney_u"])
def test_only_one_group_blocks(test_type):
    df = make_df({"Control": 10})
    res = compare_groups(df, "treatment", "viability", test_type)
    assert res["blocked"] is True
    assert any(r["code"] == "insufficient_groups" for r in res["blocked_reasons"])
    assert res["group_summary"]["Control"]["n"] == 10  # descriptive still available


# --- malformed / non-numeric measurement data -----------------------------------
def test_malformed_measurement_blocks_inference_without_crashing(valid_df):
    df = valid_df.copy()
    df["viability"] = df["viability"].astype(object)
    df.loc[0, "viability"] = "n/a (contaminated)"
    res = compare_groups(df, "treatment", "viability")
    assert res["blocked"] is True
    assert res["blocked_reasons"][0]["code"] == "non_numeric_measurement"
    assert "p_value" not in res


def test_fully_non_numeric_measurement(valid_df):
    df = valid_df.copy()
    df["viability"] = ["high", "low"] * 9
    res = compare_groups(df, "treatment", "viability")
    assert res["blocked"] is True
    assert res["blocked_reasons"][0]["code"] == "non_numeric_measurement"
    assert res["group_summary"] == {}  # nothing numeric to describe
    with pytest.raises(ValueError):
        summarize_groups(df, "treatment", "viability")


def test_missing_values_are_excluded_and_reported(valid_df):
    df = valid_df.copy()
    df.loc[[0, 1], "viability"] = np.nan
    res = check_assumptions(df, "treatment", "viability")
    assert res["missing_rows_excluded"] == 2
    assert res["inferential_allowed"] is True


def test_zero_variance_blocks():
    df = pd.DataFrame({"treatment": ["A"] * 4 + ["B"] * 4, "viability": [90.0] * 8})
    res = compare_groups(df, "treatment", "viability", "one_way_anova")
    assert res["blocked"] is True
    assert any(r["code"] == "no_variance" for r in res["blocked_reasons"])


# --- invalid comparison --------------------------------------------------------
def test_unknown_target_group_is_blocked_not_guessed(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "two_sample_t_test",
                         ref_group="Control", target_group="Drug Z")
    assert res["blocked"] is True
    assert res["blocked_reasons"][0]["code"] == "group_not_found"


def test_unknown_reference_group_is_blocked_for_pairwise(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "two_sample_t_test",
                         ref_group="Vehicle", target_group="Drug A")
    assert res["blocked"] is True and res["blocked_reasons"][0]["code"] == "group_not_found"


def test_target_equal_to_reference_is_invalid(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "two_sample_t_test",
                         ref_group="Control", target_group="Control")
    assert res["blocked"] is True
    assert any(r["code"] == "invalid_comparison" for r in res["blocked_reasons"])


def test_unsupported_test_type_is_blocked(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "two_way_anova")
    assert res["blocked"] is True
    assert res["blocked_reasons"][0]["code"] == "unsupported_test"


# --- THE key guardrail test ----------------------------------------------------------
@pytest.mark.parametrize("test_type,kwargs", INFERENTIAL[:3])
@pytest.mark.parametrize("bad", ["small_n", "one_group", "non_numeric", "missing_column", "zero_variance"])
def test_assumption_failure_blocks_inferential_test_from_executing(spy_inferential, test_type, kwargs, bad):
    """
    When validation fails, NO SciPy inferential function may be called.
    (Positive control below proves the spy really sees calls when validation passes.)
    """
    if bad == "small_n":
        df, vcol = make_df({"Control": 6, "Drug A": 6, "Drug B": 2}), "viability"
    elif bad == "one_group":
        df, vcol = make_df({"Control": 8}), "viability"
    elif bad == "non_numeric":
        df, vcol = make_df({"Control": 6, "Drug A": 6, "Drug B": 6}), "viability"
        df["viability"] = df["viability"].astype(object)
        df.loc[0, "viability"] = "oops"
    elif bad == "missing_column":
        df, vcol = make_df({"Control": 6, "Drug A": 6, "Drug B": 6}), "nope"
    else:
        df = pd.DataFrame({"treatment": ["Control"] * 4 + ["Drug B"] * 4, "viability": [1.0] * 8})
        vcol = "viability"

    # the standalone assumption check reports the failure...
    assumptions = check_assumptions(df, "treatment", vcol, test_type, **kwargs)
    assert assumptions["inferential_allowed"] is False
    # ...and compare_groups enforces it on its own, even if the caller never asked
    res = compare_groups(df, "treatment", vcol, test_type, **kwargs)
    assert res["blocked"] is True
    assert spy_inferential == [], f"inferential test executed despite failed check: {spy_inferential}"


def test_positive_control_spy_sees_calls_when_valid(spy_inferential, valid_df):
    compare_groups(valid_df, "treatment", "viability", "one_way_anova")
    assert "f_oneway" in spy_inferential
    compare_groups(valid_df, "treatment", "viability", "two_sample_t_test", ref_group="Control", target_group="Drug B")
    assert "ttest_ind" in spy_inferential


def test_dose_trend_blocked_when_inadequate(spy_inferential):
    one_level = pd.DataFrame({"dose": [10.0] * 6, "viability": [90, 91, 92, 93, 94, 95.0]})
    res = compare_groups(one_level, "dose", "viability", "dose_trend")
    assert res["blocked"] is True
    constant_y = pd.DataFrame({"dose": [10.0] * 3 + [50.0] * 3, "viability": [90.0] * 6})
    assert compare_groups(constant_y, "dose", "viability", "dose_trend")["blocked"] is True
    sparse = pd.DataFrame({"dose": [10.0] * 3 + [50.0] * 2, "viability": [90, 91, 92, 80, 81.0]})
    assert compare_groups(sparse, "dose", "viability", "dose_trend")["blocked"] is True
    assert spy_inferential == []


def test_check_assumptions_and_compare_groups_always_agree(valid_df):
    for df in (valid_df, make_df({"Control": 6, "Drug B": 2}), make_df({"Control": 5})):
        for test_type, kwargs in INFERENTIAL[:3]:
            a = check_assumptions(df, "treatment", "viability", test_type, **kwargs)
            c = compare_groups(df, "treatment", "viability", test_type, **kwargs)
            assert a["inferential_allowed"] == (not c["blocked"])


# --- valid tests give correct, independently verifiable numbers ------------------------------
def test_valid_welch_ttest_matches_scipy(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "two_sample_t_test",
                         ref_group="Control", target_group="Drug B")
    a = valid_df[valid_df.treatment == "Drug B"].viability
    b = valid_df[valid_df.treatment == "Control"].viability
    t, p = scipy_stats.ttest_ind(a, b, equal_var=False)
    assert res["test_name"] == "Welch's Two-Sample t-test"
    assert res["t_statistic"] == round(float(t), 4)
    assert res["p_value"] == round(float(p), 4)
    assert res["difference_pp"] == round(a.mean() - b.mean(), 2)
    assert res["comparison"] == "Drug B vs Control"
    assert res["blocked"] is False and res["analysis_status"] == "completed"


def test_valid_anova_matches_scipy(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "one_way_anova", ref_group="Control")
    f, p = scipy_stats.f_oneway(*[g.viability.values for _, g in valid_df.groupby("treatment")])
    assert res["test_name"] == "One-way ANOVA"
    assert res["f_statistic"] == round(float(f), 4)
    assert res["p_value"] == round(float(p), 4)
    assert res["is_significant"] is True
    assert res["posthoc_performed"] is True
    assert len(res["pairwise_comparisons"]) == 3


def test_valid_mann_whitney_runs(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "mann_whitney_u",
                         ref_group="Control", target_group="Drug A")
    assert res["test_name"] == "Mann-Whitney U Test" and "u_statistic" in res


def test_valid_dose_trend_runs():
    df = pd.DataFrame({"dose": [10.0] * 3 + [50.0] * 3 + [100.0] * 3,
                       "viability": [95, 94, 96, 85, 84, 86, 70, 71, 69.0]})
    res = compare_groups(df, "dose", "viability", "dose_trend")
    assert res["blocked"] is False
    assert res["correlation_r"] < -0.9 and res["slope"] < 0


def test_expected_result_fields_on_success(valid_df):
    res = compare_groups(valid_df, "treatment", "viability", "one_way_anova")
    for key in ["blocked", "analysis_status", "assumption_checks", "group_summary", "test_name", "p_value",
                "formatted_p_value", "is_significant", "top_performer", "reference_group",
                "delta_vs_reference", "guardrails"]:
        assert key in res, key
    assert res["assumption_checks"]["min_required_n"] == 3
    assert {c["name"] for c in res["assumption_checks"]["checks"]} >= {"Columns present", "Numeric measurement"}


def test_expected_result_fields_when_blocked():
    res = compare_groups(make_df({"Control": 6, "Drug B": 2}), "treatment", "viability", "two_sample_t_test",
                         ref_group="Control", target_group="Drug B")
    for key in ["blocked", "analysis_status", "blocked_reasons", "blocked_message", "assumption_checks",
                "group_summary", "descriptive_only", "guardrails"]:
        assert key in res, key
    for forbidden in ["p_value", "t_statistic", "test_name", "is_significant", "significant"]:
        assert forbidden not in res, forbidden
    for r in res["blocked_reasons"]:
        assert set(r) == {"code", "message"}


# --- descriptive statistics still work when inferential analysis is blocked --------------------
def test_descriptive_stats_survive_a_blocked_inferential_test():
    df = make_df({"Control": 6, "Drug A": 6, "Drug B": 2})
    blocked = compare_groups(df, "treatment", "viability", "one_way_anova")
    assert blocked["blocked"] is True
    direct = summarize_groups(df, "treatment", "viability")
    assert blocked["group_summary"] == direct
    assert direct["Drug B"]["n"] == 2
    expected_mean = round(float(df[df.treatment == "Drug B"].viability.mean()), 2)
    assert direct["Drug B"]["mean"] == expected_mean
