"""
fire_anomaly.py
===============
Ban 1 burst metric bat thuong vao 1 service cu the.
Chay bang tay khi muon trigger anomaly trong demo.

Su dung:
  python scripts/fire_anomaly.py                        # payment bi DDoS (mac dinh)
  python scripts/fire_anomaly.py --scenario cpu         # cpu spike don gian
  python scripts/fire_anomaly.py --scenario db          # database overload
  python scripts/fire_anomaly.py --scenario cascade     # loi day chuyen 3 services
  python scripts/fire_anomaly.py --service svc-database # target cu the
  python scripts/fire_anomaly.py --repeat 3             # lap lai 3 lan (15 giay)
"""

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import time
import random
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

HOSTS = {
    "svc-payment":     "pay-prod-01",
    "svc-api-gateway": "gw-prod-01",
    "svc-database":    "db-prod-01",
}

# ── Cac kich ban anomaly ─────────────────────────────────────────────────────

SCENARIOS = {

    "ddos": {
        "name": "DDoS Attack on Payment Service",
        "desc": "Traffic dot bien, CPU tang, latency tang 7x, error rate 18%",
        "metrics": {
            "svc-payment": {
                "cpu_usage":       (93.0, 2.0,  "%"),
                "request_latency": (870.0, 80.0, "ms"),
                "error_rate":      (18.5, 2.0,  "%"),
                "throughput":      (2200.0, 150.0, "rps"),
                "memory_usage":    (88.0, 3.0,  "%"),
            },
            "svc-api-gateway": {
                "cpu_usage":          (85.0, 3.0,  "%"),
                "active_connections": (1850.0, 200.0, "conn"),
                "request_latency":    (650.0, 60.0, "ms"),
                "error_rate":         (12.0, 2.0,  "%"),
            },
        },
    },

    "cpu": {
        "name": "CPU Spike - Payment Service",
        "desc": "CPU dot bien len 95%, cac metric khac binh thuong",
        "metrics": {
            "svc-payment": {
                "cpu_usage":       (95.0, 1.5, "%"),
                "request_latency": (180.0, 20.0, "ms"),
                "error_rate":      (0.8,  0.2, "%"),
                "throughput":      (830.0, 40.0, "rps"),
                "memory_usage":    (78.0, 3.0, "%"),
            },
        },
    },

    "db": {
        "name": "Database Overload",
        "desc": "Query latency tang 20x, connection pool can kiet",
        "metrics": {
            "svc-database": {
                "cpu_usage":     (88.0, 3.0,  "%"),
                "query_latency": (480.0, 60.0, "ms"),
                "connections":   (198.0, 5.0,  "conn"),
                "disk_io":       (520.0, 40.0, "MB/s"),
            },
            "svc-payment": {
                "request_latency": (750.0, 80.0, "ms"),
                "error_rate":      (8.5,  2.0,  "%"),
                "cpu_usage":       (45.0, 4.0,  "%"),
                "throughput":      (820.0, 40.0, "rps"),
                "memory_usage":    (58.0, 4.0,  "%"),
            },
        },
    },

    "cascade": {
        "name": "Cascade Failure - All Services",
        "desc": "Loi day chuyen: DB -> API Gateway -> Payment",
        "metrics": {
            "svc-database": {
                "cpu_usage":     (91.0, 2.0,  "%"),
                "query_latency": (520.0, 50.0, "ms"),
                "connections":   (199.0, 3.0,  "conn"),
                "disk_io":       (490.0, 35.0, "MB/s"),
            },
            "svc-api-gateway": {
                "cpu_usage":          (78.0, 3.0,  "%"),
                "active_connections": (1600.0, 150.0, "conn"),
                "request_latency":    (580.0, 55.0, "ms"),
                "error_rate":         (9.5,  1.5,  "%"),
            },
            "svc-payment": {
                "cpu_usage":       (87.0, 2.5, "%"),
                "request_latency": (920.0, 90.0, "ms"),
                "error_rate":      (21.0, 3.0,  "%"),
                "throughput":      (2100.0, 180.0, "rps"),
                "memory_usage":    (90.0, 3.0,  "%"),
            },
        },
    },

}


def connect():
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, database=CH_DB,
        username=CH_USER, password=CH_PASS, connect_timeout=5,
    )
    client.ping()
    return client


def fire(client, scenario_data, target_service=None):
    ts = datetime.now(timezone.utc)
    ts_label = datetime.now().strftime("%H:%M:%S")
    rows = []
    metrics_map = scenario_data["metrics"]

    for svc, metrics in metrics_map.items():
        if target_service and svc != target_service:
            continue
        host = HOSTS.get(svc, "host-unknown")
        for metric, (mean, std, unit) in metrics.items():
            value = round(max(0.0, random.gauss(mean, std)), 3)
            rows.append([svc, host, "prod", ts, metric, value, unit])

    if not rows:
        print(f"[FIRE] Khong co metric nao cho service '{target_service}'")
        return

    client.insert(
        "metrics",
        rows,
        column_names=["service_name", "host", "env", "timestamp", "metric_name", "value", "unit"],
    )

    services_hit = list({r[0] for r in rows})
    print(f"[{ts_label}] FIRED {len(rows)} anomaly metrics -> {', '.join(services_hit)}", flush=True)
    for r in rows:
        print(f"           {r[0]:20s}  {r[4]:22s}  = {r[5]:.2f} {r[6]}", flush=True)


def print_menu():
    print("""
==========================================================
   FIRE ANOMALY - Manual Trigger
==========================================================

Kich ban co san:
  ddos     - DDoS Attack: CPU 93%%, latency 870ms, error 18%%
  cpu      - CPU Spike don: CPU 95%%, cac metric khac on
  db       - Database Overload: query_latency 480ms, connections 198
  cascade  - Cascade Failure: ca 3 services cung bi

Vi du:
  python scripts/fire_anomaly.py --scenario ddos
  python scripts/fire_anomaly.py --scenario cascade --repeat 3
  python scripts/fire_anomaly.py --scenario cpu --service svc-payment
""")


def main():
    parser = argparse.ArgumentParser(description="Manual anomaly trigger for demo")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default="ddos",
                        help="Kich ban anomaly (default: ddos)")
    parser.add_argument("--service", choices=list(HOSTS.keys()), default=None,
                        help="Chi target 1 service cu the")
    parser.add_argument("--repeat", type=int, default=1,
                        help="So lan ban lien tiep (moi 5s, default 1)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Giay giua cac lan ban khi repeat > 1")
    parser.add_argument("--list", action="store_true", help="Hien danh sach kich ban")
    args = parser.parse_args()

    if args.list:
        print_menu()
        return

    scenario = SCENARIOS[args.scenario]
    print(f"""
[FIRE] Kich ban : {scenario['name']}
[FIRE] Mo ta    : {scenario['desc']}
[FIRE] Lap lai  : {args.repeat}x (moi {args.interval}s)
[FIRE] Service  : {args.service or 'tat ca trong kich ban'}
""")

    print(f"[FIRE] Ket noi ClickHouse...")
    client = connect()
    print(f"[FIRE] OK. Bat dau ban...\n")

    for i in range(args.repeat):
        if i > 0:
            print(f"[FIRE] Cho {args.interval}s truoc lan ban thu {i+1}...")
            time.sleep(args.interval)
        fire(client, scenario, target_service=args.service)

    print(f"""
[FIRE] Xong! Backend se phat hien trong vong 5-15 giay.
       Theo doi tai: http://localhost:3000
       Logs: docker-compose logs -f backend
""")


if __name__ == "__main__":
    main()
