"""
Demo kịch bản: Payment Service Under Attack
============================================
Mô phỏng 3 giai đoạn:
  1. BASELINE  — hệ thống bình thường (cpu ~30%, latency ~120ms, error_rate ~0.5%)
  2. INCIDENT  — tấn công DDoS giả lập (cpu spike 92%, latency 850ms, error_rate 18%)
  3. RECOVERY  — hệ thống hồi phục từ từ

Chạy: python scripts/demo_scenario.py
Yêu cầu: docker-compose up -d đang chạy, clickhouse port 8123 mở
"""

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import time
import random
import math
import argparse
from datetime import datetime, timezone

try:
    import clickhouse_connect
except ImportError:
    print("Thiếu clickhouse-connect. Chạy: pip install clickhouse-connect")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────
CH_HOST  = "localhost"
CH_PORT  = 8123
CH_DB    = "aiops"
CH_USER  = "default"
CH_PASS  = ""

SERVICES = {
    "svc-payment":     {"host": "pay-prod-01", "env": "prod"},
    "svc-api-gateway": {"host": "gw-prod-01",  "env": "prod"},
    "svc-database":    {"host": "db-prod-01",  "env": "prod"},
}

# Metrics mỗi service phát ra
SERVICE_METRICS = {
    "svc-payment": [
        ("cpu_usage",      "%"),
        ("memory_usage",   "%"),
        ("request_latency","ms"),
        ("error_rate",     "%"),
        ("throughput",     "rps"),
    ],
    "svc-api-gateway": [
        ("cpu_usage",      "%"),
        ("active_connections", "conn"),
        ("request_latency","ms"),
        ("error_rate",     "%"),
    ],
    "svc-database": [
        ("cpu_usage",      "%"),
        ("query_latency",  "ms"),
        ("connections",    "conn"),
        ("disk_io",        "MB/s"),
    ],
}

# Giá trị baseline (mean, std)
BASELINE = {
    "cpu_usage":          (30.0, 3.0),
    "memory_usage":       (55.0, 4.0),
    "request_latency":    (120.0, 15.0),
    "error_rate":         (0.5, 0.15),
    "throughput":         (850.0, 50.0),
    "active_connections": (200.0, 20.0),
    "query_latency":      (25.0, 5.0),
    "connections":        (40.0, 5.0),
    "disk_io":            (120.0, 15.0),
}

# Giá trị anomaly (incident phase)
INCIDENT = {
    "cpu_usage":          (92.0, 2.0),
    "memory_usage":       (88.0, 3.0),
    "request_latency":    (850.0, 80.0),
    "error_rate":         (18.5, 2.0),
    "throughput":         (2100.0, 150.0),  # traffic spike
    "active_connections": (1800.0, 200.0),
    "query_latency":      (380.0, 60.0),
    "connections":        (198.0, 10.0),    # connection pool exhaustion
    "disk_io":            (480.0, 40.0),
}


def connect():
    print(f"[DEMO] Kết nối ClickHouse {CH_HOST}:{CH_PORT}...")
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, database=CH_DB,
        username=CH_USER, password=CH_PASS,
        connect_timeout=5,
    )
    client.ping()
    print("[DEMO] ClickHouse OK\n")
    return client


def insert_metric(client, service, metric_name, value, unit, env, host):
    ts = datetime.now(timezone.utc)
    client.insert(
        "metrics",
        [[service, host, env, ts, metric_name, round(value, 3), unit]],
        column_names=["service_name","host","env","timestamp","metric_name","value","unit"],
    )


def sample(stats: dict, name: str, noise: float = 1.0) -> float:
    mean, std = stats[name]
    return max(0.0, random.gauss(mean, std * noise))


def print_phase(label: str, color_code: str = ""):
    reset = "\033[0m"
    print(f"\n{'='*60}")
    print(f"  {color_code}{label}{reset}")
    print(f"{'='*60}\n")


def run_phase(client, phase_name: str, stats: dict, ticks: int, interval: float, color: str):
    print_phase(phase_name, color)
    for tick in range(1, ticks + 1):
        ts_label = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts_label}] Tick {tick}/{ticks}", end="  ")
        for svc, meta in SERVICES.items():
            for metric, unit in SERVICE_METRICS[svc]:
                val = sample(stats, metric)
                insert_metric(client, svc, metric, val, unit, meta["env"], meta["host"])
        print(f"[OK] {len(SERVICES)} services x metrics inserted")
        time.sleep(interval)


def print_banner():
    print("""
==========================================================
   AIOps Monitor -- Demo Kich Ban
   "Payment Service Under Attack"
==========================================================

Kich ban:
  Phase 1 BASELINE  -- he thong binh thuong
  Phase 2 INCIDENT  -- DDoS gia lap, CPU spike, latency tang 7x
  Phase 3 RECOVERY  -- he thong hoi phuc

Theo doi tai:
  Frontend:  http://localhost:3000
  API Health: http://localhost:8000/api/health
  Alerts:    http://localhost:8000/api/alerts/recent?limit=10

Nhan Ctrl+C de dung bat ky luc nao.
""")


def main():
    parser = argparse.ArgumentParser(description="AIOps Demo Scenario")
    parser.add_argument("--baseline-ticks", type=int, default=24,
                        help="Số ticks phase baseline (default 24 = ~2 phút)")
    parser.add_argument("--incident-ticks", type=int, default=24,
                        help="Số ticks phase incident (default 24 = ~2 phút)")
    parser.add_argument("--recovery-ticks", type=int, default=24,
                        help="Số ticks phase recovery (default 24 = ~2 phút)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Giây giữa mỗi tick (default 5s — khớp với POLL_INTERVAL_SEC)")
    args = parser.parse_args()

    print_banner()
    client = connect()

    try:
        # ── Phase 1: BASELINE ────────────────────────────────────────────
        run_phase(
            client,
            "PHASE 1 — BASELINE: Hệ thống bình thường",
            BASELINE,
            ticks=args.baseline_ticks,
            interval=args.interval,
            color="\033[32m",  # green
        )

        # ── Phase 2: INCIDENT ────────────────────────────────────────────
        print("\n[!!] BAT DAU INCIDENT -- CPU spike + DDoS traffic")
        run_phase(
            client,
            "PHASE 2 — INCIDENT: DDoS Attack Simulation",
            INCIDENT,
            ticks=args.incident_ticks,
            interval=args.interval,
            color="\033[31m",  # red
        )

        # ── Phase 3: RECOVERY ────────────────────────────────────────────
        # Nội suy từ incident → baseline theo hàm sigmoid
        print("\n[>>] HE THONG HOI PHUC -- giam dan ve baseline")
        print_phase("PHASE 3 -- RECOVERY: Gradual Recovery", "\033[36m")
        total = args.recovery_ticks
        for tick in range(1, total + 1):
            alpha = 1 / (1 + math.exp(-10 * (tick / total - 0.5)))  # sigmoid 0→1
            ts_label = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts_label}] Tick {tick}/{total} (recovery {alpha*100:.0f}%)", end="  ")
            for svc, meta in SERVICES.items():
                for metric, unit in SERVICE_METRICS[svc]:
                    inc_mean, inc_std  = INCIDENT[metric]
                    base_mean, base_std = BASELINE[metric]
                    mean = inc_mean + alpha * (base_mean - inc_mean)
                    std  = inc_std  + alpha * (base_std  - inc_std)
                    val  = max(0.0, random.gauss(mean, std))
                    insert_metric(client, svc, metric, val, unit, meta["env"], meta["host"])
            print("[OK]")
            time.sleep(args.interval)

        print("\n\033[32m✅ Demo hoàn thành!\033[0m")
        print("\nKiểm tra kết quả:")
        print("  curl http://localhost:8000/api/alerts/recent?limit=20")
        print("  curl http://localhost:8000/api/health")

    except KeyboardInterrupt:
        print("\n\n[DEMO] Dừng bởi người dùng.")


if __name__ == "__main__":
    main()
