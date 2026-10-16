import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["demo_data_available"] is True

def test_api_load_demo():
    response = client.post("/api/load-demo")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["is_synthetic"] is True
    assert data["inspection"]["rows"] == 127
    assert data["inspection"]["summary"]["treatments_count"] == 4
    assert data["inspection"]["summary"]["doses_count"] == 3
    assert data["inspection"]["summary"]["replicates_count"] == 3

def test_api_get_dataset_info():
    res1 = client.post("/api/load-demo")
    session_id = res1.json()["session_id"]
    
    res2 = client.get(f"/api/dataset/{session_id}")
    assert res2.status_code == 200
    data = res2.json()
    assert len(data["preview"]) == 10
    assert data["preview"][0]["sample_id"] == "SMP-0001"

def test_analyze_highest_viability():
    # 1. Load dataset
    res_load = client.post("/api/load-demo")
    session_id = res_load.json()["session_id"]
    
    # 2. Ask core question
    payload = {
        "session_id": session_id,
        "question": "Which treatment produced the highest cell viability compared with control?"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["supported"] is True
    assert len(data["steps"]) >= 4
    assert data["stats"]["top_performer"] == "Drug B"
    assert data["stats"]["delta_vs_reference"] > 0
    assert data["stats"]["p_value"] < 0.05
    assert "data" in data["plotly_spec"]
    assert "Drug B" in data["interpretation"]
    assert "not establish causality" in data["interpretation"]

def test_analyze_pairwise_comparison():
    res_load = client.post("/api/load-demo")
    session_id = res_load.json()["session_id"]
    
    payload = {
        "session_id": session_id,
        "question": "Is Drug B significantly different from Control?"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is True
    assert data["plan"]["target_group"] == "Drug B"
    assert data["stats"]["test_name"] in ["Welch's Two-Sample t-test", "Mann-Whitney U Test"]
    assert data["stats"]["p_value"] < 0.05

def test_analyze_dose_trend():
    res_load = client.post("/api/load-demo")
    session_id = res_load.json()["session_id"]
    
    payload = {
        "session_id": session_id,
        "question": "How does viability change with dose?"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is True
    assert data["plan"]["group_column"] == "dose"
    assert data["plan"]["test_type"] == "dose_trend"
    assert "correlation_r" in data["stats"] or "f_statistic" in data["stats"]

def test_analyze_unsupported_question():
    res_load = client.post("/api/load-demo")
    session_id = res_load.json()["session_id"]
    
    payload = {
        "session_id": session_id,
        "question": "Can you predict patient survival from this dataset?"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is False
    assert "currently supports descriptive analyses" in data["reason"]

def test_analyze_missing_column():
    res_load = client.post("/api/load-demo")
    session_id = res_load.json()["session_id"]
    
    payload = {
        "session_id": session_id,
        "question": "Compare expression levels"
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["supported"] is False
    assert "expression" in data["reason"]


# ===========================================================================
# Upload limit, CORS, bounded sessions, blocked analysis via API
# ===========================================================================
import io
import time
import backend.main as main


@pytest.fixture
def clean_sessions():
    main.SESSION_STORE.clear()
    yield
    main.SESSION_STORE.clear()


def _csv(n_control=5, n_b=5):
    rows = ["treatment,dose,viability"]
    rows += [f"Control,0,{90 + i % 3}" for i in range(n_control)]
    rows += [f"Drug B,10,{95 + i % 3}" for i in range(n_b)]
    return "\n".join(rows).encode()


def test_upload_valid_csv():
    r = client.post("/api/upload", files={"file": ("data.csv", _csv(), "text/csv")})
    assert r.status_code == 200 and r.json()["inspection"]["rows"] == 10


def test_upload_rejects_non_csv_and_malformed():
    assert client.post("/api/upload", files={"file": ("x.txt", b"a,b", "text/plain")}).status_code == 400
    assert client.post("/api/upload", files={"file": ("x.csv", b"\xff\xfe\x00bad", "text/csv")}).status_code == 400


def test_upload_over_limit_is_413_via_bounded_read(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 100)
    r = client.post("/api/upload", files={"file": ("big.csv", b"a,b\n" + b"1,2\n" * 200, "text/csv")})
    assert r.status_code == 413
    assert "25 MB" in r.json()["detail"]


def test_upload_over_limit_is_413_via_content_length_precheck(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    monkeypatch.setattr(main, "_MULTIPART_OVERHEAD_BYTES", 0)
    r = client.post("/api/upload", files={"file": ("big.csv", b"a,b\n" + b"1,2\n" * 50, "text/csv")})
    assert r.status_code == 413


def test_documented_limit_is_25mb():
    assert main.MAX_UPLOAD_BYTES == 25 * 1024 * 1024


def test_chunked_reader_stops_at_limit(monkeypatch):
    import asyncio
    from fastapi import HTTPException

    class FakeUpload:
        def __init__(self):
            self.reads = 0
        async def read(self, n):
            self.reads += 1
            return b"x" * n  # endless stream

    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 3 * main._READ_CHUNK_BYTES)
    fake = FakeUpload()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main._read_upload_limited(fake))
    assert exc.value.status_code == 413
    assert fake.reads <= 4  # never reads unbounded data into memory


def test_cors_only_allows_configured_origin():
    ok = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    evil = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in evil.headers
    assert main.FRONTEND_ORIGIN == "http://localhost:5173" or "FRONTEND_ORIGIN" in __import__("os").environ


def test_session_store_is_capped(monkeypatch, clean_sessions):
    monkeypatch.setattr(main, "MAX_SESSIONS", 3)
    ids = [client.post("/api/load-demo").json()["session_id"] for _ in range(5)]
    assert len(main.SESSION_STORE) == 3
    assert client.get(f"/api/dataset/{ids[0]}").status_code == 404      # oldest evicted
    assert client.get(f"/api/dataset/{ids[-1]}").status_code == 200


def test_session_store_expires_idle_sessions(clean_sessions):
    sid = client.post("/api/load-demo").json()["session_id"]
    with main._SESSION_LOCK:
        main._cleanup_sessions(now=time.time() + main.SESSION_TTL_SECONDS + 5)
    assert sid not in main.SESSION_STORE
    assert client.get(f"/api/dataset/{sid}").status_code == 404


def test_session_access_refreshes_lru_order(monkeypatch, clean_sessions):
    monkeypatch.setattr(main, "MAX_SESSIONS", 2)
    a = client.post("/api/load-demo").json()["session_id"]
    b = client.post("/api/load-demo").json()["session_id"]
    client.get(f"/api/dataset/{a}")                                     # touch a, so b is now oldest
    c = client.post("/api/load-demo").json()["session_id"]
    assert a in main.SESSION_STORE and c in main.SESSION_STORE and b not in main.SESSION_STORE


def test_analyze_blocked_by_small_sample_via_api():
    up = client.post("/api/upload", files={"file": ("small.csv", _csv(n_control=5, n_b=2), "text/csv")}).json()
    r = client.post("/api/analyze", json={"session_id": up["session_id"],
                                         "question": "Is Drug B significantly different from Control?"})
    assert r.status_code == 200
    data = r.json()
    assert data["supported"] is True
    assert data["stats"]["blocked"] is True and "p_value" not in data["stats"]
    assert data["stats"]["blocked_reasons"][0]["code"] == "insufficient_sample_size"
    assert data["statistical_audit"]["status"] == "blocked"
    assert [t["key"] for t in data["analysis_trace"]] == [
        "dataset_inspected", "groups_identified", "sample_sizes_checked",
        "assumptions_checked", "test_executed", "result_validated"]


def test_analyze_response_contains_trace_and_audit():
    sid = client.post("/api/load-demo").json()["session_id"]
    data = client.post("/api/analyze", json={"session_id": sid, "question": "Is Drug B significantly different from Control?"}).json()
    audit = data["statistical_audit"]
    assert audit["selected_test"] == "Welch's Two-Sample t-test"
    assert audit["groups"] == ["Drug B", "Control"]
    assert audit["computed_by"] == "Python / SciPy"
    assert audit["formatted_p_value"] == "< 0.001"
    assert data["explanation_source"] == "deterministic_template"      # no Gemini key in tests
    assert all(t["status"] in ("passed", "executed") for t in data["analysis_trace"])


def test_analyze_unknown_session_is_404():
    r = client.post("/api/analyze", json={"session_id": "nope", "question": "q"})
    assert r.status_code == 404


# ===========================================================================
# Planner routing fixes, question cap, and rate limiting (via API)
# ===========================================================================

def test_analyze_two_named_groups_via_api():
    sid = client.post("/api/load-demo").json()["session_id"]
    data = client.post("/api/analyze", json={
        "session_id": sid, "question": "Compare Drug A and Drug B"}).json()
    assert data["supported"] is True
    assert data["statistical_audit"]["groups"] == ["Drug A", "Drug B"]
    assert data["statistical_audit"]["selected_test"] == "Welch's Two-Sample t-test"


def test_analyze_unknown_group_clarification_via_api():
    sid = client.post("/api/load-demo").json()["session_id"]
    data = client.post("/api/analyze", json={
        "session_id": sid,
        "question": "Is Drug Z significantly different from Control?"}).json()
    assert data["supported"] is False
    assert data["error_type"] == "unknown_group"
    assert "Drug Z" in data["reason"]
    assert "Control, Drug A, Drug B, Drug C" in data["reason"]


def test_analyze_rejects_overlong_question():
    sid = client.post("/api/load-demo").json()["session_id"]
    r = client.post("/api/analyze", json={"session_id": sid, "question": "x" * 501})
    assert r.status_code == 400
    assert "too long" in r.json()["detail"]
    # At the boundary it still works.
    ok = client.post("/api/analyze", json={"session_id": sid, "question": "x" * 500})
    assert ok.status_code == 200


def test_analyze_rate_limit(monkeypatch):
    monkeypatch.setattr(main, "RATE_LIMIT_MAX", 2)
    monkeypatch.setattr(main, "RATE_LIMIT_WINDOW_SECONDS", 60)
    main._rate_buckets.clear()
    try:
        sid = client.post("/api/load-demo").json()["session_id"]
        payload = {"session_id": sid, "question": "Is Drug B significantly different from Control?"}
        assert client.post("/api/analyze", json=payload).status_code == 200
        assert client.post("/api/analyze", json=payload).status_code == 200
        r = client.post("/api/analyze", json=payload)
        assert r.status_code == 429
        assert "Too many requests" in r.json()["detail"]
    finally:
        main._rate_buckets.clear()
