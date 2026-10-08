import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Any, Optional, List

# MVP scientific policy: every group entering an inferential test needs n >= 3.
MIN_N_PER_GROUP = 3
# Dose-trend predictors with more distinct levels than this are treated as continuous
# (per-level n is then not meaningful; only total n >= MIN_N_PER_GROUP applies).
MAX_DOSE_LEVELS_FOR_PER_LEVEL_N = 10
VARIANCE_RATIO_WARN = 3.0

TEST_ALIASES = {
    "one_way_anova": "one_way_anova", "anova": "one_way_anova",
    "two_sample_t_test": "two_sample_t_test", "t_test": "two_sample_t_test",
    "mann_whitney_u": "mann_whitney_u", "mann_whitney": "mann_whitney_u",
    "dose_trend": "dose_trend", "correlation": "dose_trend",
}
SUPPORTED_TESTS = sorted(set(TEST_ALIASES.values()))


def _numeric_series(df: pd.DataFrame, value_col: str):
    """Returns (numeric series, count of non-null entries that are not numeric)."""
    raw = df[value_col]
    coerced = pd.to_numeric(raw, errors="coerce")
    malformed = int((coerced.isna() & raw.notna()).sum())
    return coerced, malformed


def _block(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def validate_inferential_request(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    test_type: Optional[str] = None,
    ref_group: Optional[str] = None,
    target_group: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single source of truth for whether an inferential test may run.
    Never raises. Returns {"allowed": bool, "blocked_reasons": [...], "warnings": [...],
    "checks": [...], ...group info}. compare_groups() calls this BEFORE any test, so no caller
    (including the LLM planner) can skip it.
    """
    blocked: List[Dict[str, str]] = []
    warnings: List[str] = []
    checks: List[Dict[str, Any]] = []
    canonical = TEST_ALIASES.get(test_type) if test_type else None

    def add_check(name: str, passed: bool, detail: str):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    info: Dict[str, Any] = {
        "test_type": test_type, "canonical_test": canonical,
        "group_sample_sizes": {}, "missing_rows_excluded": 0,
        "non_numeric_values": 0, "variance_ratio": 1.0, "groups_evaluated": [],
    }

    def finish():
        info.update({"allowed": len(blocked) == 0, "blocked_reasons": blocked,
                     "warnings": warnings, "checks": checks})
        return info

    # 1. Test must be a supported one
    if test_type is not None and canonical is None:
        blocked.append(_block("unsupported_test",
                              f"Test '{test_type}' is not supported. Supported: {', '.join(SUPPORTED_TESTS)}."))
        add_check("Supported test", False, f"'{test_type}' is not supported")
    elif test_type is not None:
        add_check("Supported test", True, canonical)

    # 2. Columns must exist
    missing = [c for c in (group_col, value_col) if c not in df.columns]
    if missing:
        blocked.append(_block("missing_column",
                              f"Column(s) {missing} not found. Available columns: {list(df.columns)}."))
        add_check("Columns present", False, f"missing: {missing}")
        return finish()
    add_check("Columns present", True, f"{group_col}, {value_col}")

    # 3. Measurement must be numeric (no silent coercion of malformed entries)
    values, malformed = _numeric_series(df, value_col)
    info["non_numeric_values"] = malformed
    if malformed > 0 or (values.notna().sum() == 0):
        blocked.append(_block("non_numeric_measurement",
                              f"Measurement column '{value_col}' contains {malformed} non-numeric value(s) "
                              f"or no numeric data; inferential tests require a clean numeric measurement."))
        add_check("Numeric measurement", False, f"{malformed} non-numeric value(s)")
        return finish()
    add_check("Numeric measurement", True, value_col)

    work = pd.DataFrame({group_col: df[group_col], value_col: values})
    info["missing_rows_excluded"] = int(work.isna().any(axis=1).sum())
    work = work.dropna()
    counts = {str(k): int(v) for k, v in work.groupby(group_col)[value_col].count().items()}
    info["group_sample_sizes"] = counts
    groups = {str(k): g.values for k, g in work.groupby(group_col)[value_col]}

    # 4. Which groups does this test actually compare?
    pairwise = canonical in ("two_sample_t_test", "mann_whitney_u")
    if pairwise:
        ref = ref_group if ref_group is not None else (next(iter(groups), None))
        if ref not in groups:
            blocked.append(_block("group_not_found",
                                  f"Reference group '{ref_group}' not found. Available groups: {list(groups)}."))
        if target_group is not None and target_group not in groups:
            blocked.append(_block("group_not_found",
                                  f"Target group '{target_group}' not found. Available groups: {list(groups)}."))
        if len(groups) < 2:
            blocked.append(_block("insufficient_groups", "At least 2 distinct groups are required."))
        if target_group is not None and target_group == ref:
            blocked.append(_block("invalid_comparison", "Target and reference group must be different."))
        # Explicit target: only target and reference are compared. No target: compare_groups picks
        # one, so every group must be adequate.
        evaluated = [g for g in (target_group, ref) if g in groups] if target_group is not None else list(groups)
    elif canonical == "dose_trend" and pd.api.types.is_numeric_dtype(work[group_col]):
        evaluated = list(groups) if len(groups) <= MAX_DOSE_LEVELS_FOR_PER_LEVEL_N else []
        if len(groups) < 2:
            blocked.append(_block("insufficient_groups", "At least 2 distinct dose levels are required."))
        if len(work) < MIN_N_PER_GROUP:
            blocked.append(_block("insufficient_sample_size",
                                  f"Only {len(work)} observation(s); need n >= {MIN_N_PER_GROUP}."))
        if len(groups) >= 2 and work[group_col].nunique() < 2:
            blocked.append(_block("no_variance", f"'{group_col}' has no variation."))
    else:  # ANOVA, or dose_trend on a categorical grouping
        evaluated = list(groups)
        if len(groups) < 2:
            blocked.append(_block("insufficient_groups",
                                  f"At least 2 distinct groups are required; found {len(groups)}."))
    info["groups_evaluated"] = evaluated
    add_check("Groups identified", len(groups) >= 2 and not any(
        b["code"] in ("group_not_found", "invalid_comparison", "insufficient_groups") for b in blocked),
        f"{len(groups)} group(s): {list(groups)}")

    # 5. Sample size policy: n >= MIN_N_PER_GROUP in every evaluated group
    small = {g: counts[g] for g in evaluated if g in counts and counts[g] < MIN_N_PER_GROUP}
    if small:
        blocked.append(_block("insufficient_sample_size",
                              f"Every compared group needs n >= {MIN_N_PER_GROUP}; too small: "
                              + ", ".join(f"{g} (n = {n})" for g, n in small.items()) + "."))
    add_check("Sample sizes (n >= %d per group)" % MIN_N_PER_GROUP, not small,
              ("n per group: " + ", ".join(f"{g} = {counts.get(g)}" for g in evaluated)) if evaluated
              else f"total n = {len(work)}")

    # 6. Variance checks
    if evaluated:
        variances = {g: float(np.var(groups[g], ddof=1)) for g in evaluated if len(groups[g]) > 1}
        if variances:
            if all(v == 0 for v in variances.values()):
                blocked.append(_block("no_variance",
                                      "All compared groups have zero variance; the test statistic is undefined."))
            elif min(variances.values()) > 0:
                info["variance_ratio"] = round(max(variances.values()) / min(variances.values()), 2)
            else:
                warnings.append("At least one compared group has zero variance.")
            if info["variance_ratio"] > VARIANCE_RATIO_WARN and canonical != "mann_whitney_u":
                if canonical == "two_sample_t_test":
                    warnings.append(f"Variance imbalance ({info['variance_ratio']}x); Welch's t-test does not "
                                    f"assume equal variances.")
                else:
                    warnings.append(f"Variance imbalance ({info['variance_ratio']}x) across groups; "
                                    f"equal-variance assumption of ANOVA/Tukey HSD may not hold — interpret with caution.")
    if canonical == "dose_trend" and pd.api.types.is_numeric_dtype(work[group_col]) and len(work) >= 2:
        if work[value_col].nunique() < 2:
            blocked.append(_block("no_variance", f"'{value_col}' has no variation; correlation is undefined."))
    warnings.append("Normality was not formally assessed.")
    add_check("Assumptions checked", not any(b["code"] in ("no_variance",) for b in blocked),
              "variance spread checked; normality not formally assessed")
    return finish()


def summarize_groups(df: pd.DataFrame, group_col: str, value_col: str) -> Dict[str, Any]:
    """
    Computes descriptive statistics for a continuous measurement grouped by a categorical variable.
    Descriptive statistics are always allowed (they are not gated by inferential guardrails).
    """
    if group_col not in df.columns or value_col not in df.columns:
        raise ValueError(f"Columns '{group_col}' and/or '{value_col}' not found in dataset.")

    values, _ = _numeric_series(df, value_col)
    if values.notna().sum() == 0:
        raise ValueError(f"Measurement column '{value_col}' has no numeric data.")
    clean_df = pd.DataFrame({group_col: df[group_col], value_col: values}).dropna()
    grouped = clean_df.groupby(group_col)[value_col]
    
    summary = {}
    for name, grp in grouped:
        n = int(len(grp))
        mean_val = float(grp.mean())
        std_val = float(grp.std()) if n > 1 else 0.0
        sem_val = float(grp.sem()) if n > 1 else 0.0
        median_val = float(grp.median())
        summary[str(name)] = {
            "n": n,
            "mean": round(mean_val, 2),
            "std": round(std_val, 2),
            "sem": round(sem_val, 2),
            "median": round(median_val, 2),
            "min": round(float(grp.min()), 2),
            "max": round(float(grp.max()), 2)
        }
    
    return summary

def check_assumptions(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    test_type: Optional[str] = None,
    ref_group: Optional[str] = None,
    target_group: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates whether inferential testing is permitted, using the same validation that
    compare_groups() enforces (so this report can never disagree with what actually runs):
    - Minimum sample size per compared group (n >= MIN_N_PER_GROUP = 3)
    - Columns present, numeric measurement, enough distinct groups, valid comparison
    - Group variance spread (reported as a warning) and normality (declared as not assessed)
    Never raises for bad input; returns inferential_allowed=False with structured blocked_reasons.
    """
    if test_type is None and group_col in df.columns:
        n_groups = df[group_col].dropna().nunique()
        test_type = "one_way_anova" if n_groups > 2 else "two_sample_t_test"
    v = validate_inferential_request(df, group_col, value_col, test_type, ref_group, target_group)

    counts = v["group_sample_sizes"]
    min_sample = min(counts.values()) if counts else 0
    max_sample = max(counts.values()) if counts else 0
    codes = {b["code"] for b in v["blocked_reasons"]}
    adequate_sample = bool(counts) and "insufficient_sample_size" not in codes
    var_ratio = v["variance_ratio"]
    sample_size_status = "Adequate" if adequate_sample else (
        f"Inadequate (min n = {min_sample} < {MIN_N_PER_GROUP})" if counts else "Not assessed")
    variance_status = ("No large variance imbalance detected" if var_ratio <= VARIANCE_RATIO_WARN
                       else f"Variance imbalance detected (ratio: {var_ratio}x)")
    note = f"{variance_status}; normality was not formally assessed."
    if v["blocked_reasons"]:
        summary = "Inferential test blocked: " + " ".join(b["message"] for b in v["blocked_reasons"])
    else:
        summary = "Sample size and variance checks completed."

    return {
        "group_column": group_col,
        "value_column": value_col,
        "total_observations": int(sum(counts.values())),
        "missing_rows_excluded": v["missing_rows_excluded"],
        "group_sample_sizes": counts,
        "min_sample_size": int(min_sample),
        "max_sample_size": int(max_sample),
        "min_required_n": MIN_N_PER_GROUP,
        "sample_size_adequate": adequate_sample,
        "sample_size_status": sample_size_status,
        "variance_ratio": var_ratio,
        "variance_status": variance_status,
        "normality_status": "Not assessed",
        "recommended_test": v["canonical_test"] or test_type,
        "inferential_allowed": v["allowed"],
        "blocked_reasons": v["blocked_reasons"],
        "warnings": v["warnings"],
        "checks": v["checks"],
        "scientific_summary": summary,
        "scientific_note": note
    }

def _blocked_result(df, group_col, value_col, test_type, ref_group, target_group, validation) -> Dict[str, Any]:
    """Structured 'analysis blocked' payload. Contains NO test statistic or p-value."""
    try:
        descriptive = summarize_groups(df, group_col, value_col)
    except Exception:
        descriptive = {}
    reasons = validation["blocked_reasons"]
    message = "Inferential test blocked: " + " ".join(r["message"] for r in reasons)
    return {
        "blocked": True,
        "analysis_status": "blocked",
        "comparison_type": "blocked",
        "group_column": group_col,
        "value_column": value_col,
        "test_type": test_type,
        "reference_group": ref_group,
        "target_group": target_group,
        "blocked_reasons": reasons,
        "blocked_message": message,
        "error": message,
        "assumption_checks": {
            "checks": validation["checks"],
            "warnings": validation["warnings"],
            "group_sample_sizes": validation["group_sample_sizes"],
            "min_required_n": MIN_N_PER_GROUP,
        },
        "group_summary": descriptive,
        "descriptive_only": True,
        "guardrails": {
            "causality_disclaimer": "This describes the observed experiment and does not establish causality.",
            "synthetic_disclaimer": "Synthetic demonstration data — not real experimental results."
        }
    }


def compare_groups(
    df: pd.DataFrame,
    group_col: str, 
    value_col: str, 
    test_type: str = "one_way_anova",
    ref_group: Optional[str] = "Control",
    target_group: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes deterministic hypothesis testing (ANOVA, t-test, Mann-Whitney U)
    or trend analysis across experimental conditions.
    """
    # GUARDRAIL: validate BEFORE any inferential test. This is enforced here (not only in the
    # planner), so neither the LLM nor any caller can skip it. If blocked, no test is executed;
    # descriptive statistics are still returned when the data allows them.
    validation = validate_inferential_request(df, group_col, value_col, test_type, ref_group, target_group)
    if not validation["allowed"]:
        return _blocked_result(df, group_col, value_col, test_type, ref_group, target_group, validation)

    clean_df = pd.DataFrame({
        group_col: df[group_col],
        value_col: pd.to_numeric(df[value_col], errors="coerce"),
    }).dropna()
    groups_data = {}
    for name, grp in clean_df.groupby(group_col)[value_col]:
        groups_data[str(name)] = grp.values

    group_names = list(groups_data.keys())

    summary = summarize_groups(df, group_col, value_col)
    
    group_items = {k: v for k, v in summary.items() if isinstance(v, dict) and "mean" in v}
    top_group = max(group_items.items(), key=lambda x: x[1]["mean"])
    top_group_name = top_group[0]
    top_group_mean = top_group[1]["mean"]
    
    # Reference group comparison
    effective_ref = ref_group if (ref_group in summary) else group_names[0]
    ref_mean = summary[effective_ref]["mean"]
    delta_vs_control = round(top_group_mean - ref_mean, 2)
    
    result = {
        "blocked": False,
        "analysis_status": "completed",
        "assumption_checks": {
            "checks": validation["checks"],
            "warnings": validation["warnings"],
            "group_sample_sizes": validation["group_sample_sizes"],
            "min_required_n": MIN_N_PER_GROUP,
        },
        "group_column": group_col,
        "value_column": value_col,
        "test_type": test_type,
        "reference_group": effective_ref,
        "target_group": target_group,
        "top_performer": top_group_name,
        "top_mean": top_group_mean,
        "delta_vs_reference": delta_vs_control,
        "group_summary": summary,
        "guardrails": {
            "causality_disclaimer": "This describes the observed experiment and does not establish causality.",
            "synthetic_disclaimer": "Synthetic demonstration data — not real experimental results."
        }
    }
    
    # Statistical tests
    if test_type in ["one_way_anova", "anova"]:
        f_stat, p_val = stats.f_oneway(*groups_data.values())
        result.update({
            "test_name": "One-way ANOVA",
            "comparison_type": "multi_group_anova",
            "f_statistic": round(float(f_stat), 4),
            "p_value": round(float(p_val), 4),
            "is_significant": bool(p_val < 0.05),
            "formatted_p_value": "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
        })
        
        # Post-hoc pairwise analysis with Tukey HSD if overall ANOVA is significant and groups >= 3
        if len(group_names) >= 3 and p_val < 0.05:
            try:
                data_arrays = [groups_data[name] for name in group_names]
                tukey_res = stats.tukey_hsd(*data_arrays)
                ref_idx = group_names.index(effective_ref)
                top_idx = group_names.index(top_group_name)
                
                pairwise_list = []
                for i in range(len(group_names)):
                    for j in range(i + 1, len(group_names)):
                        g_a, g_b = group_names[i], group_names[j]
                        p_pair = float(tukey_res.pvalue[i, j])
                        stat_pair = float(tukey_res.statistic[i, j])
                        pairwise_list.append({
                            "comparison": f"{g_a} vs {g_b}",
                            "difference": round(stat_pair, 2),
                            "p_adj": round(p_pair, 4),
                            "formatted_p_adj": "< 0.001" if p_pair < 0.001 else f"= {p_pair:.3f}",
                            "is_significant": bool(p_pair < 0.05)
                        })
                        
                top_vs_ref_p = float(tukey_res.pvalue[top_idx, ref_idx])
                top_vs_ref_diff = round(float(tukey_res.statistic[top_idx, ref_idx]), 2)
                top_vs_ref_sig = bool(top_vs_ref_p < 0.05)
                
                result.update({
                    "posthoc_performed": True,
                    "posthoc_test": "Tukey HSD (Family-Wise Error Rate Controlled)",
                    "pairwise_comparisons": pairwise_list,
                    "top_vs_reference_posthoc": {
                        "comparison": f"{top_group_name} vs {effective_ref}",
                        "difference": top_vs_ref_diff,
                        "p_adj": round(top_vs_ref_p, 4),
                        "formatted_p_adj": "< 0.001" if top_vs_ref_p < 0.001 else f"= {top_vs_ref_p:.3f}",
                        "is_significant": top_vs_ref_sig
                    }
                })
            except Exception as e:
                result["posthoc_error"] = str(e)
    elif test_type in ["two_sample_t_test", "t_test"]:
        g1 = target_group if target_group in groups_data else (top_group_name if top_group_name != effective_ref else group_names[1])
        g2 = effective_ref
        t_stat, p_val = stats.ttest_ind(groups_data[g1], groups_data[g2], equal_var=False)
        target_m = summary[g1]["mean"]
        ref_m = summary[g2]["mean"]
        diff_pp = round(target_m - ref_m, 2)
        result.update({
            "test_name": "Welch's Two-Sample t-test",
            "test": "Welch's t-test",
            "comparison_type": "pairwise",
            "target_group": g1,
            "reference_group": g2,
            "target_mean": target_m,
            "reference_mean": ref_m,
            "difference_pp": diff_pp,
            "delta_vs_reference": diff_pp,
            "comparison": f"{g1} vs {g2}",
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p_val), 4),
            "significant": bool(p_val < 0.05),
            "is_significant": bool(p_val < 0.05),
            "formatted_p_value": "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
        })
    elif test_type in ["mann_whitney_u", "mann_whitney"]:
        g1 = target_group if target_group in groups_data else (top_group_name if top_group_name != effective_ref else group_names[1])
        g2 = effective_ref
        u_stat, p_val = stats.mannwhitneyu(groups_data[g1], groups_data[g2])
        target_m = summary[g1]["mean"]
        ref_m = summary[g2]["mean"]
        diff_pp = round(target_m - ref_m, 2)
        result.update({
            "test_name": "Mann-Whitney U Test",
            "test": "Mann-Whitney U Test",
            "comparison_type": "pairwise",
            "target_group": g1,
            "reference_group": g2,
            "target_mean": target_m,
            "reference_mean": ref_m,
            "difference_pp": diff_pp,
            "u_statistic": round(float(u_stat), 4),
            "p_value": round(float(p_val), 4),
            "significant": bool(p_val < 0.05),
            "is_significant": bool(p_val < 0.05),
            "formatted_p_value": "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
        })
    elif test_type in ["correlation", "dose_trend"]:
        result["comparison_type"] = "dose_trend"
        if pd.api.types.is_numeric_dtype(clean_df[group_col]):
            r_val, p_val = stats.pearsonr(clean_df[group_col], clean_df[value_col])
            slope, intercept, r_value, p_value, std_err = stats.linregress(clean_df[group_col], clean_df[value_col])
            result.update({
                "test_name": "Pearson Correlation & Linear Regression",
                "correlation_r": round(float(r_val), 4),
                "p_value": round(float(p_val), 4),
                "slope": round(float(slope), 4),
                "is_significant": bool(p_val < 0.05),
                "formatted_p_value": "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
            })
        else:
            f_stat, p_val = stats.f_oneway(*groups_data.values())
            result.update({
                "test_name": "One-way ANOVA (Trend Evaluation)",
                "f_statistic": round(float(f_stat), 4),
                "p_value": round(float(p_val), 4),
                "is_significant": bool(p_val < 0.05),
                "formatted_p_value": "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
            })
            
    return result
