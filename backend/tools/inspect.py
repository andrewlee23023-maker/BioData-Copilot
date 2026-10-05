import pandas as pd
from typing import Dict, Any

def inspect_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Inspects tabular dataset for shape, types, missing values, and biological groups.
    """
    rows, cols = df.shape
    columns = list(df.columns)
    
    numeric_cols = [c for c in columns if pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in columns if c not in numeric_cols]
    
    missing_values = {c: int(df[c].isna().sum()) for c in columns if df[c].isna().sum() > 0}
    
    # Detect experimental design features (3 treatment doses excluding 0/vehicle control)
    if "dose" in df.columns:
        active_doses = df[df["dose"] > 0]["dose"].nunique()
        unique_doses = int(active_doses if active_doses > 0 else df["dose"].nunique())
    else:
        unique_doses = 0
    unique_treatments = int(df["treatment"].nunique()) if "treatment" in df.columns else 0
    unique_replicates = int(df["replicate"].nunique()) if "replicate" in df.columns else 0
    
    treatment_names = list(df["treatment"].dropna().unique()) if "treatment" in df.columns else []
    
    return {
        "rows": rows,
        "columns": columns,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "missing_values": missing_values,
        "summary": {
            "observations": rows,
            "treatments_count": unique_treatments,
            "doses_count": unique_doses,
            "replicates_count": unique_replicates,
            "treatments": treatment_names
        }
    }
