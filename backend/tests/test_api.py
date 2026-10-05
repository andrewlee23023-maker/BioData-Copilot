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
    # First load demo to get session_id
    res1 = client.post("/api/load-demo")
    session_id = res1.json()["session_id"]
    
    res2 = client.get(f"/api/dataset/{session_id}")
    assert res2.status_code == 200
    data = res2.json()
    assert len(data["preview"]) == 10
    assert data["preview"][0]["sample_id"] == "SMP-0001"
