import pandas as pd
from typing import Dict, Any, List, Union

def filter_dataset(df: pd.DataFrame, filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Subsets a dataset based on specified column criteria before analysis.
    Supports list of categorical values or numeric ranges.
    
    Example filters:
    {"treatment": ["Drug B", "Control"]}
    {"dose": [10.0]}
    """
    if not filters:
        return {
            "filtered_rows": len(df),
            "original_rows": len(df),
            "filters_applied": {},
            "status": "No filters applied"
        }
        
    filtered = df.copy()
    applied = {}
    
    for col, criteria in filters.items():
        if col not in df.columns:
            continue
            
        if isinstance(criteria, list):
            filtered = filtered[filtered[col].isin(criteria)]
            applied[col] = criteria
        elif isinstance(criteria, (int, float, str)):
            filtered = filtered[filtered[col] == criteria]
            applied[col] = [criteria]
        elif isinstance(criteria, dict):
            # Numeric range {min: ..., max: ...}
            if "min" in criteria:
                filtered = filtered[filtered[col] >= criteria["min"]]
            if "max" in criteria:
                filtered = filtered[filtered[col] <= criteria["max"]]
            applied[col] = criteria

    remaining_groups = {}
    for col in applied.keys():
        remaining_groups[col] = list(filtered[col].unique())
        
    return {
        "filtered_rows": int(len(filtered)),
        "original_rows": int(len(df)),
        "filters_applied": applied,
        "remaining_groups": remaining_groups,
        "status": f"Filtered from {len(df)} to {len(filtered)} rows"
    }
