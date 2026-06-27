from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 9000))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "aiops")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASS = os.getenv("CLICKHOUSE_PASS", "")
CLICKHOUSE_CONNECT_TIMEOUT = int(os.getenv("CLICKHOUSE_CONNECT_TIMEOUT", 2))
CLICKHOUSE_SEND_RECEIVE_TIMEOUT = int(os.getenv("CLICKHOUSE_SEND_RECEIVE_TIMEOUT", 3))
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", 5))
LOOKBACK_SEC = int(os.getenv("LOOKBACK_SEC", 60))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", 0.6))
MODEL_STORE = Path(os.getenv("MODEL_STORE", Path(__file__).resolve().parent / "model_store"))
MODEL_STORE.mkdir(parents=True, exist_ok=True)
