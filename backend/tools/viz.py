import pandas as pd
from typing import Dict, Any

def generate_plotly_spec(df: pd.DataFrame, plan: Dict[str, Any], stats_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a publication-grade, interactive Plotly figure specification.
    """
    group_col = plan.get("group_column", "treatment")
    value_col = plan.get("value_column", "viability")
    chart_type = plan.get("chart_type", "box")
    
    cols_to_keep = [group_col, value_col]
    for c in ["dose", "replicate", "timepoint"]:
        if c in df.columns and c not in cols_to_keep:
            cols_to_keep.append(c)
    clean_df = df[cols_to_keep].dropna()
    
    # Modern scientific color palette
    palette = ["#10b981", "#06b6d4", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899"]
    
    traces = []
    
    # Check if dose trend
    if group_col == "dose" or chart_type == "scatter":
        # Group by dose to get mean line + scatter for individual observations
        grouped = clean_df.groupby(group_col)[value_col].agg(["mean", "sem"]).reset_index()
        
        # Raw scatter points
        traces.append({
            "x": clean_df[group_col].tolist(),
            "y": clean_df[value_col].tolist(),
            "mode": "markers",
            "type": "scatter",
            "name": "Replicate Observations",
            "marker": {
                "color": "rgba(148, 163, 184, 0.6)",
                "size": 7,
                "line": {"color": "#475569", "width": 1}
            },
            "hoverinfo": "x+y"
        })
        
        # Mean trendline with error bars
        traces.append({
            "x": grouped[group_col].tolist(),
            "y": grouped["mean"].round(2).tolist(),
            "error_y": {
                "type": "data",
                "array": grouped["sem"].round(2).tolist(),
                "visible": True,
                "color": "#10b981",
                "thickness": 1.5,
                "width": 6
            },
            "mode": "lines+markers",
            "type": "scatter",
            "name": "Group Mean ± SEM",
            "line": {"color": "#10b981", "width": 2.5},
            "marker": {"color": "#10b981", "size": 9}
        })
        
        layout_title = f"{value_col.capitalize()} vs {group_col.capitalize()}"
        x_title = f"{group_col.capitalize()} (Concentration)"
    
    elif chart_type == "bar":
        raw_summary = stats_result.get("group_summary", {})
        summary = {k: v for k, v in raw_summary.items() if isinstance(v, dict) and "mean" in v}
        x_vals = list(summary.keys())
        y_vals = [s["mean"] for s in summary.values()]
        errors = [s["sem"] for s in summary.values()]
        
        traces.append({
            "x": x_vals,
            "y": y_vals,
            "error_y": {
                "type": "data",
                "array": errors,
                "visible": True,
                "color": "#cbd5e1",
                "thickness": 1.5,
                "width": 5
            },
            "type": "bar",
            "name": "Mean ± SEM",
            "marker": {
                "color": [palette[i % len(palette)] for i in range(len(x_vals))],
                "opacity": 0.85,
                "line": {"color": "#f8fafc", "width": 1}
            }
        })
        layout_title = f"Mean {value_col.capitalize()} by {group_col.capitalize()}"
        x_title = group_col.capitalize()
        
    else:
        # Default: High-fidelity box plot with underlying jittered jitter observations
        groups = clean_df[group_col].unique()
        for idx, grp in enumerate(groups):
            grp_data = clean_df[clean_df[group_col] == grp][value_col].tolist()
            color = palette[idx % len(palette)]
            traces.append({
                "y": grp_data,
                "name": str(grp),
                "type": "box",
                "boxpoints": "all",
                "jitter": 0.35,
                "pointpos": -1.8,
                "marker": {"size": 6, "color": color},
                "line": {"width": 1.5, "color": color},
                "fillcolor": f"rgba{tuple(list(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + [0.25])}"
            })
            
        layout_title = f"{value_col.capitalize()} Distribution across {group_col.capitalize()}"
        x_title = group_col.capitalize()

    layout = {
        "title": {
            "text": layout_title,
            "font": {"size": 16, "color": "#f8fafc", "family": "Inter, sans-serif"}
        },
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(15, 23, 42, 0.6)",
        "margin": {"l": 50, "r": 20, "t": 45, "b": 45},
        "xaxis": {
            "title": {"text": x_title, "font": {"color": "#94a3b8"}},
            "gridcolor": "#1e293b",
            "tickfont": {"color": "#cbd5e1"}
        },
        "yaxis": {
            "title": {"text": f"{value_col.capitalize()} (%)", "font": {"color": "#94a3b8"}},
            "gridcolor": "#1e293b",
            "tickfont": {"color": "#cbd5e1"}
        },
        "legend": {
            "font": {"color": "#94a3b8"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1
        },
        "showlegend": True
    }
    
    return {
        "data": traces,
        "layout": layout,
        "config": {"responsive": True, "displayModeBar": False}
    }
