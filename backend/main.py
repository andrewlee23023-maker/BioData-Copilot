import os
import io
import time
import uuid
import threading
from collections import OrderedDict
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

from backend.tools.inspect import inspect_dataset
from backend.tools.stats import summarize_groups, compare_groups
from backend.agent import run_agent_reasoning_loop

app = FastAPI(title="BioData Copilot API", version="1.0.0")

# CORS: only the configured frontend origin(s). Comma-separate to allow several.
# (No authentication is used, so credentials are not allowed cross-origin.)
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Documented upload limit: 25 MB.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_MULTIPART_OVERHEAD_BYTES = 64 * 1024  # form boundaries/headers on top of the file itself
_READ_CHUNK_BYTES = 1024 * 1024


@app.middleware("http")
async def reject_oversized_uploads(request: Request, call_next):
    """Cheap early rejection using Content-Length, before the body is parsed."""
    if request.url.path == "/api/upload":
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD_BYTES:
            return JSONResponse(status_code=413, content={"detail": "File too large. Maximum upload size is 25 MB."})
    return await call_next(request)


async def _read_upload_limited(file: UploadFile) -> bytes:
    """Reads an upload in chunks and stops as soon as it exceeds the limit (never unbounded)."""
    buf = bytearray()
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 25 MB.")
    return bytes(buf)


# In-memory sessions, bounded by size (oldest-used evicted first) and idle time (TTL).
MAX_SESSIONS = int(os.environ.get("MAX_SESSIONS", "50"))
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "3600"))
SESSION_STORE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_SESSION_LOCK = threading.Lock()


def _cleanup_sessions(now: Optional[float] = None) -> None:
    """Caller must hold _SESSION_LOCK."""
    now = time.time() if now is None else now
    for sid in [k for k, v in SESSION_STORE.items() if now - v["last_access"] > SESSION_TTL_SECONDS]:
        del SESSION_STORE[sid]
    while len(SESSION_STORE) > MAX_SESSIONS:
        SESSION_STORE.popitem(last=False)


def _store_session(df: pd.DataFrame) -> str:
    session_id = str(uuid.uuid4())
    with _SESSION_LOCK:
        SESSION_STORE[session_id] = {"df": df, "last_access": time.time()}
        _cleanup_sessions()
    return session_id


def _get_session_df(session_id: str, detail: str = "Session expired or dataset not found.") -> pd.DataFrame:
    with _SESSION_LOCK:
        _cleanup_sessions()
        entry = SESSION_STORE.get(session_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=detail)
        entry["last_access"] = time.time()
        SESSION_STORE.move_to_end(session_id)
        return entry["df"]


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
    session_id = _store_session(df)
    
    inspection = inspect_dataset(df)
    return {
        "session_id": session_id,
        "is_synthetic": True,
        "filename": "synthetic_viability.csv",
        "inspection": inspection
    }

@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files (.csv) are currently supported.")
    
    contents = await _read_upload_limited(file)  # raises HTTP 413 if over 25 MB
    try:
        df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
        
    session_id = _store_session(df)
    
    inspection = inspect_dataset(df)
    return {
        "session_id": session_id,
        "is_synthetic": False,
        "filename": file.filename,
        "inspection": inspection
    }

@app.get("/api/dataset/{session_id}")
def get_dataset_info(session_id: str):
    df = _get_session_df(session_id)
    return {
        "session_id": session_id,
        "inspection": inspect_dataset(df),
        "preview": df.head(10).to_dict(orient="records")
    }

@app.post("/api/analyze")
def analyze_question(req: AnalyzeRequest):
    df = _get_session_df(req.session_id, "Session expired or dataset not found. Please upload a dataset.")
    
    # Execute the reasoning-driven tool-using agent loop
    result = run_agent_reasoning_loop(df, req.question)
    return result
