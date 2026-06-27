from __future__ import annotations

from src.pipeline.common import append_jsonl, utc_now
from src.pipeline.state import invalidate_from, run_dir


class DriftDetector:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        try:
            from river.drift import ADWIN

            self.detector = ADWIN()
        except Exception:
            self.detector = None
        self.previous_mean: float | None = None

    def update(self, value: float) -> bool:
        drift = False
        if self.detector is not None:
            self.detector.update(value)
            drift = bool(getattr(self.detector, "drift_detected", False))
        else:
            drift = self.previous_mean is not None and abs(value - self.previous_mean) > 3.0
            self.previous_mean = value if self.previous_mean is None else self.previous_mean * 0.99 + value * 0.01
        if drift:
            append_jsonl(run_dir(self.run_id) / "drift_log.jsonl", {"detected_at": utc_now(), "value": float(value)})
            invalidate_from(self.run_id, "process")
        return drift
