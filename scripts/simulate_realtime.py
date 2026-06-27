from __future__ import annotations

import argparse
import json
import math
import random
import time
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen


def post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def sample(i: int) -> dict:
    burst = i % 35 in {0, 1, 2, 3}
    cpu = 48 + 10 * math.sin(i / 8) + random.gauss(0, 2)
    memory = 62 + 5 * math.cos(i / 11) + random.gauss(0, 1)
    latency = 120 + 25 * math.sin(i / 9) + random.gauss(0, 8)
    error_rate = max(0.0, random.gauss(0.025, 0.01))
    level = "INFO"
    if burst:
        cpu += random.uniform(35, 55)
        latency += random.uniform(180, 260)
        error_rate += random.uniform(0.25, 0.45)
        level = "ERROR"
    source = random.choice(["metric", "log", "trace"])
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "features": {
            "cpu_usage": round(cpu, 3),
            "memory_usage": round(memory, 3),
            "latency_ms": round(latency, 3),
            "error_rate": round(min(1.0, error_rate), 4),
            "duration_ms": round(latency * random.uniform(0.7, 1.4), 3),
            "error": 1 if level == "ERROR" else 0,
            "call_depth": random.randint(1, 8),
        },
    }
    if source == "log":
        payload["message"] = f"{level} checkout latency={latency:.1f} cpu={cpu:.1f} request_id=req-{i % 97}"
    if source == "trace":
        payload["trace_id"] = f"trace-live-{i // 4}"
        payload["span_id"] = f"span-live-{i}"
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Send synthetic realtime telemetry to the AIOps API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/ingest")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--count", type=int, default=0, help="0 means run forever")
    args = parser.parse_args()
    i = 0
    while args.count == 0 or i < args.count:
        payload = sample(i)
        try:
            event = post_json(args.url, payload)
            state = "ANOMALY" if event.get("label") else "normal"
            print(f"{i:05d} {state:7s} score={event.get('anomaly_score', 0):.3f} source={payload['source']}")
        except URLError as exc:
            print(f"API unavailable: {exc}")
        i += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
