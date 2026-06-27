from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import app


def test_predict_returns_canonical_schema() -> None:
    client = TestClient(app)
    response = client.post("/predict", json={"source": "metric", "features": {"cpu_usage": 95, "latency_ms": 220}})
    assert response.status_code == 200
    payload = response.json()
    assert {"event_id", "timestamp", "source", "anomaly_score", "label", "model", "features", "rca"} <= set(payload)
    assert payload["source"] == "metric"


def test_health() -> None:
    assert TestClient(app).get("/health").json()["status"] == "ok"
