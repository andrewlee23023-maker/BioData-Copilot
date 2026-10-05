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

app = FastAPI(title="BioData Copilot API", version="1.0.0")

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: session_id -> pd.DataFrame
SESSION_STORE: Dict[str, pd.DataFrame] = {}

DEMO_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_viability.csv")

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
