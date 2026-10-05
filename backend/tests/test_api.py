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
