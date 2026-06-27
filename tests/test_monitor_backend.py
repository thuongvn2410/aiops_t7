from __future__ import annotations

from backend.models.detector import selftest


def test_detector_selftest() -> None:
    result = selftest()
    assert result["rows"] == 10
    assert result["max_score"] >= 0.0
    assert result["model_loaded"] is True


def test_monitor_schema_file_exists() -> None:
    from pathlib import Path

    schema = Path("db/init_schema.sql").read_text(encoding="utf-8")
    for table in ["metrics", "logs", "traces", "anomaly_events", "alert_incidents"]:
        assert f"aiops.{table}" in schema
