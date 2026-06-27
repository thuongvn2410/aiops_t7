from __future__ import annotations

import argparse
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ANOMOD_ROOT = ROOT / ".cache" / "AnoMod" / "SN_data"

SERVICES = [
    "compose-post-service",
    "user-service",
    "social-graph-service",
    "home-timeline-service",
    "user-timeline-service",
    "media-service",
    "text-service",
]

METRIC_UNITS = {
    "latency_ms": "ms",
    "cpu_usage": "%",
    "error_rate": "ratio",
    "request_rate": "rps",
}


def ch_post(base_url: str, query: str) -> str:
    request = Request(base_url, data=query.encode("utf-8"), method="POST")
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def ch_get(base_url: str, query: str) -> str:
    with urlopen(f"{base_url}?query={quote(query)}", timeout=30) as response:
        return response.read().decode("utf-8")


def escape_tsv(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def ch_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def insert_tsv(base_url: str, table: str, columns: list[str], rows: list[list]) -> None:
    if not rows:
        return
    query = f"INSERT INTO aiops.{table} ({', '.join(columns)}) FORMAT TabSeparated\n"
    body = "\n".join("\t".join(escape_tsv(item) for item in row) for row in rows)
    ch_post(base_url, query + body)


def scenario_dirs(kind: str) -> list[Path]:
    base = ANOMOD_ROOT / kind
    return sorted([path for path in base.iterdir() if path.is_dir()]) if base.exists() else []


def parse_summary(summary_path: Path) -> dict[str, dict[str, int]]:
    if not summary_path.exists():
        return {}
    content = summary_path.read_text(encoding="utf-8", errors="ignore")
    services: dict[str, dict[str, int]] = {}
    for line in content.splitlines():
        match = re.search(r"-\s*([^:]+):\s*([0-9.]+)([KMG]?)\s*\((\d+)行\).*错误:\s*(\d+).*警告:\s*(\d+)", line)
        if not match:
            continue
        name, size, suffix, lines, errors, warnings = match.groups()
        mult = {"": 1, "K": 1_000, "M": 1_000_000, "G": 1_000_000_000}[suffix]
        services[name.strip()] = {
            "bytes": int(float(size) * mult),
            "lines": int(lines),
            "errors": int(errors),
            "warnings": int(warnings),
        }
    return services


def severity_factor(case_name: str) -> float:
    if case_name.startswith("Normal"):
        return 1.0
    if case_name.startswith("Perf_CPU"):
        return 3.8
    if case_name.startswith("Perf_Disk"):
        return 3.2
    if case_name.startswith("Perf_Network"):
        return 2.8
    if case_name.startswith("Svc_Kill") or case_name.startswith("Code_Stop"):
        return 4.5
    if case_name.startswith("DB_Redis"):
        return 3.5
    return 2.4


def service_from_summary_name(name: str) -> str:
    words = re.sub(r"([a-z])([A-Z])", r"\1-\2", name).lower()
    words = words.replace("_", "-")
    return f"anomod-{words}"


def build_rows() -> tuple[list[list], list[list], list[list]]:
    rng = random.Random(42)
    log_cases = scenario_dirs("log_data")
    metric_cases = scenario_dirs("metric_data")
    selected_cases = [path for path in log_cases if "Normal_Baseline" in path.name]
    selected_cases += [path for path in log_cases if not path.name.startswith("Normal")][:8]
    if not selected_cases:
        selected_cases = log_cases[:8] or metric_cases[:8]

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=240)
    metrics: list[list] = []
    logs: list[list] = []
    traces: list[list] = []
    cursor = start

    for case_index, case_dir in enumerate(selected_cases):
        case_name = case_dir.name.split("_logs_")[0].split("_metrics_")[0]
        factor = severity_factor(case_name)
        summary = parse_summary(case_dir / "summary.txt")
        summary_services = list(summary)[:5] or SERVICES[:5]
        case_duration = 22 if case_name.startswith("Normal") else 18
        for offset in range(case_duration):
            ts = cursor + timedelta(seconds=offset)
            for raw_service in summary_services:
                svc = service_from_summary_name(raw_service)
                stats = summary.get(raw_service, {})
                base_latency = 80 + rng.random() * 30 + min(stats.get("lines", 0) / 4500, 50)
                is_fault = factor > 1.2 and offset >= max(3, case_duration // 3)
                spike = factor if is_fault else 1.0
                cpu = min(99.0, 28 + rng.random() * 10 + (spike - 1.0) * 22)
                latency = base_latency * spike + rng.random() * 12
                error_rate = min(1.0, (stats.get("errors", 0) / max(1, stats.get("lines", 1))) + (0.22 if is_fault else 0.01))
                request_rate = max(1.0, 120 + rng.random() * 50 - (40 if is_fault and factor >= 4 else 0))
                for metric_name, value in [
                    ("latency_ms", latency),
                    ("cpu_usage", cpu),
                    ("error_rate", error_rate),
                    ("request_rate", request_rate),
                ]:
                    metrics.append([
                        svc,
                        f"{svc}-host-1",
                        "prod",
                        ch_time(ts),
                        metric_name,
                        round(value, 6),
                        METRIC_UNITS[metric_name],
                    ])
                if offset in {0, case_duration // 2, case_duration - 1}:
                    level = "ERROR" if is_fault else "INFO"
                    message = (
                        f"AnoMod case={case_name} service={raw_service} "
                        f"latency_ms={latency:.2f} cpu={cpu:.2f} error_rate={error_rate:.3f}"
                    )
                    trace_id = f"anomod-{case_index}-{offset}-{raw_service}"
                    span_id = f"span-{case_index}-{offset}"
                    logs.append([
                        trace_id,
                        span_id,
                        svc,
                        f"{svc}-host-1",
                        ch_time(ts),
                        level,
                        message,
                        "anomod-loader",
                    ])
                    traces.append([
                        trace_id,
                        span_id,
                        "",
                        svc,
                        f"{case_name}/request",
                        ch_time(ts),
                        round(latency, 6),
                        1 if is_fault else 0,
                        f'{{"case":"{case_name}","source":"AnoMod SN_data"}}',
                    ])
        cursor += timedelta(seconds=case_duration + 2)

    # Add a live anomalous tail so the backend scheduler sees AnoMod data immediately.
    live_start = datetime.now(timezone.utc) - timedelta(seconds=45)
    for offset in range(45):
        ts = live_start + timedelta(seconds=offset)
        for svc in ["anomod-user-service", "anomod-social-graph-service"]:
            is_fault = offset >= 12
            latency = 120 + offset * (11 if is_fault else 0.8) + rng.random() * 8
            cpu = 42 + (44 if is_fault else 0) + rng.random() * 5
            error_rate = 0.02 + (0.35 if is_fault else 0)
            for metric_name, value in [
                ("latency_ms", latency),
                ("cpu_usage", cpu),
                ("error_rate", error_rate),
                ("request_rate", 100 - (35 if is_fault else 0) + rng.random() * 5),
            ]:
                metrics.append([
                    svc,
                    f"{svc}-host-live",
                    "prod",
                    ch_time(ts),
                    metric_name,
                    round(value, 6),
                    METRIC_UNITS[metric_name],
                ])
            if offset % 10 == 0:
                trace_id = f"anomod-live-{svc}-{offset}"
                logs.append([
                    trace_id,
                    f"span-live-{offset}",
                    svc,
                    f"{svc}-host-live",
                    ch_time(ts),
                    "ERROR" if is_fault else "INFO",
                    f"AnoMod live replay service={svc} latency_ms={latency:.2f} cpu={cpu:.2f} error_rate={error_rate:.3f}",
                    "anomod-loader",
                ])
                traces.append([
                    trace_id,
                    f"span-live-{offset}",
                    "",
                    svc,
                    "anomod/live-replay",
                    ch_time(ts),
                    round(latency, 6),
                    1 if is_fault else 0,
                    '{"case":"AnoMod live replay"}',
                ])
    return metrics, logs, traces


def clean_anomod_rows(base_url: str) -> None:
    for table, column in [("metrics", "service_name"), ("logs", "service_name"), ("traces", "service_name")]:
        ch_post(base_url, f"ALTER TABLE aiops.{table} DELETE WHERE {column} LIKE 'anomod-%'")
    for table in ["anomaly_events", "alert_incidents"]:
        ch_post(base_url, f"ALTER TABLE aiops.{table} DELETE WHERE service_name LIKE 'anomod-%'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load AnoMod-derived SN_data telemetry into ClickHouse.")
    parser.add_argument("--clickhouse-url", default="http://127.0.0.1:8123/")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    if not ANOMOD_ROOT.exists():
        raise SystemExit(f"AnoMod SN_data not found: {ANOMOD_ROOT}")

    if not args.no_clean:
        clean_anomod_rows(args.clickhouse_url)
    metrics, logs, traces = build_rows()
    insert_tsv(
        args.clickhouse_url,
        "metrics",
        ["service_name", "host", "env", "timestamp", "metric_name", "value", "unit"],
        metrics,
    )
    insert_tsv(
        args.clickhouse_url,
        "logs",
        ["trace_id", "span_id", "service_name", "host", "timestamp", "level", "message", "logger"],
        logs,
    )
    insert_tsv(
        args.clickhouse_url,
        "traces",
        ["trace_id", "span_id", "parent_span_id", "service_name", "operation", "start_time", "duration_ms", "status_code", "attributes"],
        traces,
    )
    print(f"inserted metrics={len(metrics)} logs={len(logs)} traces={len(traces)}")
    print(ch_get(args.clickhouse_url, "SELECT 'metrics', count() FROM aiops.metrics WHERE service_name LIKE 'anomod-%'"))
    print(ch_get(args.clickhouse_url, "SELECT 'logs', count() FROM aiops.logs WHERE service_name LIKE 'anomod-%'"))
    print(ch_get(args.clickhouse_url, "SELECT 'traces', count() FROM aiops.traces WHERE service_name LIKE 'anomod-%'"))


if __name__ == "__main__":
    main()
