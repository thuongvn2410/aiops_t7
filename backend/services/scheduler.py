from __future__ import annotations

import asyncio
import time
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.config import LOOKBACK_SEC, POLL_INTERVAL_SEC
from backend.db.queries import q_recent_metrics
from backend.models.detector import Detector
from backend.models.features import build_features, rows_to_frame
from backend.services.alert_dedup import process as dedup_process
from backend.services.anomaly_writer import anomaly_payload, write_anomaly
from backend.services.rca_narrator import generate_rca_narrative
from backend.ws.manager import ConnectionManager


class PollingService:
    def __init__(self, client, detector: Detector, ws_manager: ConnectionManager) -> None:
        self.client = client
        self.detector = detector
        self.ws_manager = ws_manager
        self.scheduler = AsyncIOScheduler()

    async def poll_once(self) -> dict[str, Any]:
        started = time.perf_counter()
        rows_processed = 0
        anomalies = 0
        try:
            result = self.client.query(q_recent_metrics(LOOKBACK_SEC))
            features = build_features(rows_to_frame(result))
            rows_processed = len(features)
            scored = self.detector.predict(features)
            for _, row in scored[scored["is_anomaly"]].iterrows():
                try:
                    event = anomaly_payload(row)
                    metric_value = float(row.get("value", 0.0))
                    baseline_value = float(row.get("rolling_mean_12", metric_value))
                    event["narrative"] = await generate_rca_narrative(
                        service_name=event["service_name"],
                        metric_name=event["metric_name"],
                        anomaly_score=event["anomaly_score"],
                        rca_causes=event.get("rca_causes", []),
                        metric_value=metric_value,
                        baseline_value=baseline_value,
                    )
                    write_anomaly(self.client, event)
                    incident = dedup_process(self.client, event)
                    event["incident"] = incident
                    await self.ws_manager.broadcast({"type": "anomaly", "data": event})
                    anomalies += 1
                except Exception as row_exc:
                    print(f"scheduler row_error metric={row.get('metric_name','?')} err={row_exc}")
        except Exception as exc:
            print(f"scheduler error={exc}")
        latency_ms = (time.perf_counter() - started) * 1000
        print(f"scheduler rows_processed={rows_processed} anomalies={anomalies} latency_ms={latency_ms:.2f}")
        return {"rows_processed": rows_processed, "anomalies": anomalies, "latency_ms": latency_ms}

    def start(self) -> None:
        self.scheduler.add_job(self.poll_once, "interval", seconds=POLL_INTERVAL_SEC, id="aiops-poll", replace_existing=True)
        self.scheduler.start()

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
