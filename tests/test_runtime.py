from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import app
from src.pipeline.state import run_dir
from src.runtime import RuntimeScorer


def test_runtime_scorer_writes_events(processed_run: str) -> None:
    root = run_dir(processed_run)
    events = root / "runtime_events.jsonl"
    before = events.read_text(encoding="utf-8").count("\n") if events.exists() else 0
    event = RuntimeScorer(processed_run).score(
        {
            "source": "metric",
            "features": {
                "cpu_usage": 98.0,
                "memory_usage": 82.0,
                "latency_ms": 390.0,
                "error_rate": 0.45,
                "duration_ms": 420.0,
                "error": 1,
                "call_depth": 6,
            },
        }
    )
    assert {"event_id", "timestamp", "source", "anomaly_score", "label", "model", "features", "rca"} <= set(event)
    assert events.exists()
    assert events.read_text(encoding="utf-8").count("\n") > before


def test_runtime_api_endpoints(processed_run: str) -> None:
    client = TestClient(app)
    response = client.post(
        "/ingest",
        json={
            "run_id": processed_run,
            "source": "log",
            "message": "ERROR checkout latency=420 cpu=99 request_id=req-test",
            "features": {"cpu_usage": 99, "memory_usage": 80, "latency_ms": 420, "error_rate": 0.4, "duration_ms": 450, "error": 1},
        },
    )
    assert response.status_code == 200
    assert "anomaly_score" in response.json()
    assert client.get(f"/runtime/events?run_id={processed_run}&limit=5").json()["events"]
    assert client.get("/monitor").status_code == 200
