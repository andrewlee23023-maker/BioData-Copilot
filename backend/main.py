import os
import io
import uuid
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

from backend.tools.inspect import inspect_dataset
from backend.tools.stats import summarize_groups, compare_groups
from backend.tools.viz import generate_plotly_spec
from backend.agent import plan_analysis, generate_grounded_explanation

app = FastAPI(title="BioData Copilot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_STORE: Dict[str, pd.DataFrame] = {}
DEMO_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_viability.csv")

class AnalyzeRequest(BaseModel):
    session_id: str
    question: str

@app.get("/api/health")
def health_check():
    return {
        "status": "ok", 
        "app": "BioData Copilot",
        "demo_data_available": os.path.exists(DEMO_FILE_PATH)
    }

@app.post("/api/load-demo")
def load_demo():
    if not os.path.exists(DEMO_FILE_PATH):
        raise HTTPException(status_code=404, detail="Synthetic demo dataset not found.")
    
    df = pd.read_csv(DEMO_FILE_PATH)
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = df
    
    inspection = inspect_dataset(df)
    return {
        "session_id": session_id,
        "is_synthetic": True,
        "filename": "synthetic_viability.csv",
        "inspection": inspection
    }

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files (.csv) are currently supported.")
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
        
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = df
    
    inspection = inspect_dataset(df)
    return {
        "session_id": session_id,
        "is_synthetic": False,
        "filename": file.filename,
        "inspection": inspection
    }

@app.get("/api/dataset/{session_id}")
def get_dataset_info(session_id: str):
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail="Session expired or dataset not found.")
    
    df = SESSION_STORE[session_id]
    return {
        "session_id": session_id,
        "inspection": inspect_dataset(df),
        "preview": df.head(10).to_dict(orient="records")
    }

@app.post("/api/analyze")
def analyze_question(req: AnalyzeRequest):
    if req.session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail="Session expired or dataset not found. Please upload a dataset.")
    
    df = SESSION_STORE[req.session_id]
    inspection = inspect_dataset(df)
    
    # Step 1: AI intent planning
    plan = plan_analysis(req.question, inspection)
    if not plan.get("supported", True):
        return {
            "supported": False,
            "reason": plan.get("reason", "This question cannot be analyzed with the current dataset."),
            "steps": [
                {"label": "Inspecting dataset & verifying question", "status": "done"},
                {"label": "Unsupported question type detected", "status": "refused"}
            ]
        }
        
    # Step 2: Validate columns
    group_col = plan.get("group_column", "treatment")
    value_col = plan.get("value_column", "viability")
    if group_col not in df.columns or value_col not in df.columns:
        return {
            "supported": False,
            "reason": f"Required columns '{group_col}' or '{value_col}' not found in dataset.",
            "steps": [
                {"label": "Inspecting dataset schema", "status": "done"},
                {"label": f"Column '{group_col}' or '{value_col}' missing", "status": "error"}
            ]
        }
        
    # Step 3: Python deterministic computation
    test_type = plan.get("test_type", "one_way_anova")
    ref_group = plan.get("reference_group", "Control")
    target_group = plan.get("target_group", None)
    
    stats_result = compare_groups(
        df=df,
        group_col=group_col,
        value_col=value_col,
        test_type=test_type,
        ref_group=ref_group,
        target_group=target_group
    )
    
    # Step 4: Deterministic Plotly JSON figure
    plotly_spec = generate_plotly_spec(df, plan, stats_result)
    
    # Step 5: Grounded scientific interpretation
    explanation = generate_grounded_explanation(req.question, plan, stats_result)
    
    steps = [
        {"label": "Inspecting dataset & verifying schema", "status": "done"},
        {"label": f"Identifying experimental groups ({group_col} vs {value_col})", "status": "done"},
        {"label": f"Checking sample sizes & distributions", "status": "done"},
        {"label": f"Running statistical test ({stats_result.get('test_name', 'Hypothesis Test')})", "status": "done"},
        {"label": "Generating Plotly interactive visualization", "status": "done"},
        {"label": "Synthesizing verified scientific interpretation", "status": "done"}
    ]
    
    return {
        "supported": True,
        "question": req.question,
        "steps": steps,
        "plan": plan,
        "stats": stats_result,
        "plotly_spec": plotly_spec,
        "interpretation": explanation
    }
