"""
continuous_baseline.py
======================
Chay nen: bam metric binh thuong lien tuc moi INTERVAL giay.
Giu cho rolling window luon co du baseline de model hoc.

Chay: python scripts/continuous_baseline.py
Dung: Ctrl+C
"""

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import time
import random
import signal
import argparse
from datetime import datetime, timezone

try:
    import clickhouse_connect
except ImportError:
    print("Thieu clickhouse-connect. Chay: pip install clickhouse-connect")
    sys.exit(1)

CH_HOST = "localhost"
CH_PORT = 8123
CH_DB   = "aiops"
CH_USER = "default"
CH_PASS = ""

# Gia tri baseline (mean, std)
BASELINE = {
    "svc-payment": {
        "cpu_usage":       (28.0, 3.0,  "%"),
        "memory_usage":    (52.0, 4.0,  "%"),
        "request_latency": (115.0, 12.0, "ms"),
        "error_rate":      (0.4,  0.1,  "%"),
        "throughput":      (820.0, 45.0, "rps"),
    },
    "svc-api-gateway": {
        "cpu_usage":          (22.0, 2.5, "%"),
        "active_connections": (195.0, 18.0, "conn"),
        "request_latency":    (105.0, 10.0, "ms"),
        "error_rate":         (0.3,  0.08, "%"),
    },
    "svc-database": {
        "cpu_usage":     (18.0, 2.0, "%"),
        "query_latency": (22.0, 4.0, "ms"),
        "connections":   (38.0, 4.0, "conn"),
        "disk_io":       (115.0, 12.0, "MB/s"),
    },
}

HOSTS = {
    "svc-payment":     "pay-prod-01",
    "svc-api-gateway": "gw-prod-01",
    "svc-database":    "db-prod-01",
}

_running = True

def handle_stop(sig, frame):
    global _running
    _running = False
    print("\n[BASELINE] Dung. He thong se tiep tuc hoat dong binh thuong.")

signal.signal(signal.SIGINT, handle_stop)
signal.signal(signal.SIGTERM, handle_stop)


def connect():
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, database=CH_DB,
        username=CH_USER, password=CH_PASS, connect_timeout=5,
    )
    client.ping()
    return client


def insert_batch(client, rows):
    client.insert(
        "metrics",
        rows,
        column_names=["service_name", "host", "env", "timestamp", "metric_name", "value", "unit"],
    )


def main():
    parser = argparse.ArgumentParser(description="Continuous baseline injector")
    parser.add_argument("--interval", type=float, default=5.0, help="Giay giua moi tick (default 5s)")
    args = parser.parse_args()

    print(f"[BASELINE] Ket noi ClickHouse {CH_HOST}:{CH_PORT}...")
    client = connect()
    print(f"[BASELINE] OK. Bat dau inject baseline moi {args.interval}s. Nhan Ctrl+C de dung.\n")

    tick = 0
    while _running:
        tick += 1
        ts = datetime.now(timezone.utc)
        ts_label = datetime.now().strftime("%H:%M:%S")
        rows = []
        for svc, metrics in BASELINE.items():
            host = HOSTS[svc]
            for metric, (mean, std, unit) in metrics.items():
                value = round(max(0.0, random.gauss(mean, std)), 3)
                rows.append([svc, host, "prod", ts, metric, value, unit])
        try:
            insert_batch(client, rows)
            total_metrics = len(rows)
            print(f"[{ts_label}] tick={tick:04d}  {total_metrics} metrics  (baseline normal)", flush=True)
        except Exception as e:
            print(f"[{ts_label}] INSERT ERROR: {e}", flush=True)
            try:
                client = connect()
            except Exception:
                pass
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
