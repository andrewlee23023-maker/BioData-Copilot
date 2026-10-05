import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Any, Optional

def summarize_groups(df: pd.DataFrame, group_col: str, value_col: str) -> Dict[str, Any]:
    """
    Computes descriptive statistics for a continuous measurement grouped by a categorical variable.
    """
    if group_col not in df.columns or value_col not in df.columns:
        raise ValueError(f"Columns '{group_col}' and/or '{value_col}' not found in dataset.")
    
    clean_df = df[[group_col, value_col]].dropna()
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

def check_assumptions(df: pd.DataFrame, group_col: str, value_col: str) -> Dict[str, Any]:
    """
    Evaluates statistical characteristics prior to inferential testing:
    - Minimum sample size per group (n >= 3)
    - Missingness / null values
    - Group variances and distribution spread
    - Normality status (declared as not assessed)
    """
    if group_col not in df.columns or value_col not in df.columns:
        raise ValueError(f"Columns '{group_col}' and/or '{value_col}' not found in dataset.")
        
    clean_df = df[[group_col, value_col]].dropna()
    missing_count = int(df[[group_col, value_col]].isna().any(axis=1).sum())
    
    groups_counts = clean_df.groupby(group_col)[value_col].count().to_dict()
    min_sample = min(groups_counts.values()) if groups_counts else 0
    max_sample = max(groups_counts.values()) if groups_counts else 0
    adequate_sample = bool(min_sample >= 3)
    
    # Variance check
    variances = clean_df.groupby(group_col)[value_col].var().dropna().to_dict()
    if len(variances) >= 2:
        max_var = max(variances.values())
        min_var = min(variances.values())
        var_ratio = round(float(max_var / min_var), 2) if min_var > 0 else 1.0
    else:
        var_ratio = 1.0
        
    recommended_test = "one_way_anova" if len(groups_counts) > 2 else "two_sample_t_test"
    sample_size_status = "Adequate" if adequate_sample else f"Inadequate (min n = {min_sample} < 3)"
    variance_status = "No large variance imbalance detected" if var_ratio <= 3.0 else f"Variance imbalance detected (ratio: {var_ratio}x)"
    normality_status = "Not assessed"
        
    return {
        "group_column": group_col,
        "value_column": value_col,
        "total_observations": len(clean_df),
        "missing_rows_excluded": missing_count,
        "group_sample_sizes": {str(k): int(v) for k, v in groups_counts.items()},
        "min_sample_size": int(min_sample),
        "max_sample_size": int(max_sample),
        "sample_size_adequate": adequate_sample,
        "sample_size_status": sample_size_status,
        "variance_ratio": var_ratio,
        "variance_status": variance_status,
        "normality_status": normality_status,
        "recommended_test": recommended_test,
        "scientific_summary": "Sample size and variance checks completed.",
        "scientific_note": "Sample size and variance checks completed. Normality not assessed."
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
    if group_col not in df.columns or value_col not in df.columns:
        raise ValueError(f"Columns '{group_col}' and/or '{value_col}' not found in dataset.")
    
    clean_df = df[[group_col, value_col]].dropna()
    groups_data = {}
    for name, grp in clean_df.groupby(group_col)[value_col]:
        groups_data[str(name)] = grp.values
        
    group_names = list(groups_data.keys())
    if len(group_names) < 2:
        return {
            "error": "At least 2 distinct groups are required for statistical comparison.",
            "groups_found": group_names
        }
        
    summary = summarize_groups(df, group_col, value_col)
    
    # Identify top performer
    top_group = max(summary.items(), key=lambda x: x[1]["mean"])
    top_group_name = top_group[0]
    top_group_mean = top_group[1]["mean"]
    
    # Reference group comparison
    effective_ref = ref_group if (ref_group in summary) else group_names[0]
    ref_mean = summary[effective_ref]["mean"]
    delta_vs_control = round(top_group_mean - ref_mean, 2)
    
    result = {
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
        result.update({
            "test_name": "Welch's Two-Sample t-test",
            "target_group": g1,
            "comparison": f"{g1} vs {g2}",
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p_val), 4),
            "is_significant": bool(p_val < 0.05),
            "formatted_p_value": "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
        })
    elif test_type in ["mann_whitney_u", "mann_whitney"]:
        g1 = target_group if target_group in groups_data else (top_group_name if top_group_name != effective_ref else group_names[1])
        g2 = effective_ref
        u_stat, p_val = stats.mannwhitneyu(groups_data[g1], groups_data[g2])
        result.update({
            "test_name": "Mann-Whitney U Test",
            "target_group": g1,
            "comparison": f"{g1} vs {g2}",
            "u_statistic": round(float(u_stat), 4),
            "p_value": round(float(p_val), 4),
            "is_significant": bool(p_val < 0.05),
            "formatted_p_value": "< 0.001" if p_val < 0.001 else f"= {p_val:.3f}"
        })
    elif test_type in ["correlation", "dose_trend"]:
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
