from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from src.pipeline.common import utc_now
from src.pipeline.state import get_latest_run_id, run_dir, stage_status
from src.runtime import get_scorer, read_jsonl

app = FastAPI(title="AIOps Anomaly Detection Platform")


def _canonical_event(score: float, label: int, features: dict, source: str = "metric") -> dict:
    return {
        "event_id": str(uuid4()),
        "timestamp": utc_now(),
        "source": source,
        "anomaly_score": float(score),
        "label": int(label),
        "model": "ensemble",
        "features": {k: float(v) for k, v in features.items() if isinstance(v, (int, float))},
        "rca": None,
    }


@app.post("/predict")
def predict(telemetry: dict) -> dict:
    try:
        return get_scorer(telemetry.get("run_id")).score(telemetry)
    except Exception:
        features = telemetry.get("features", telemetry)
        numeric_values = [float(v) for v in features.values() if isinstance(v, (int, float))]
        score = min(1.0, max(numeric_values, default=0.0) / 100.0)
        return _canonical_event(score=score, label=int(score >= 0.8), features=features, source=telemetry.get("source", "metric"))


@app.post("/ingest")
def ingest(telemetry: dict) -> dict:
    return get_scorer(telemetry.get("run_id")).score(telemetry)


@app.get("/runtime/events")
def runtime_events(limit: int = 100, run_id: str | None = None) -> dict:
    selected = run_id or get_latest_run_id()
    if not selected:
        return {"run_id": None, "events": []}
    return {"run_id": selected, "events": read_jsonl(run_dir(selected) / "runtime_events.jsonl", limit)}


@app.get("/runtime/alerts")
def runtime_alerts(limit: int = 50, run_id: str | None = None) -> dict:
    selected = run_id or get_latest_run_id()
    if not selected:
        return {"run_id": None, "alerts": []}
    return {"run_id": selected, "alerts": read_jsonl(run_dir(selected) / "runtime_alerts.jsonl", limit)}


@app.get("/runs/{run_id}/metrics")
def run_metrics(run_id: str) -> dict:
    path = run_dir(run_id) / "parsed" / "metrics.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="metrics.json not found")
    import json

    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/runs/{run_id}/status")
def run_status(run_id: str) -> dict:
    return stage_status(run_id)


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    latest = get_latest_run_id() or "none"
    return f'aiops_latest_run_info{{run_id="{latest}"}} 1\n'


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/monitor", response_class=HTMLResponse)
def monitor() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>AIOps Realtime Monitor</title>
  <style>
    :root { color-scheme: light; --bg:#f7f8fb; --panel:#fff; --ink:#17202a; --muted:#667085; --line:#e4e7ec; --red:#c92a2a; --green:#087f5b; --blue:#1c7ed6; }
    body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--ink); }
    header { padding:18px 24px; background:#101828; color:#fff; display:flex; justify-content:space-between; align-items:center; }
    main { padding:20px 24px; display:grid; grid-template-columns: 1.4fr .9fr; gap:16px; }
    section { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
    h2 { margin:0 0 12px; font-size:17px; }
    .cards { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px; margin-bottom:16px; }
    .card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }
    .label { color:var(--muted); font-size:12px; }
    .value { font-size:26px; font-weight:700; margin-top:4px; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { padding:9px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
    th { color:var(--muted); font-weight:600; }
    .alert { border-left:4px solid var(--red); background:#fff5f5; padding:10px 12px; border-radius:6px; margin-bottom:10px; }
    .normal { color:var(--green); font-weight:700; }
    .bad { color:var(--red); font-weight:700; }
    .pill { display:inline-block; padding:3px 8px; border-radius:999px; background:#eef4ff; color:#175cd3; font-size:12px; }
    canvas { width:100%; height:240px; border:1px solid var(--line); border-radius:6px; }
    @media (max-width: 900px) { main { grid-template-columns:1fr; } .cards { grid-template-columns:repeat(2, minmax(0,1fr)); } }
  </style>
</head>
<body>
  <header>
    <div><strong>AIOps Realtime Monitor</strong> <span id="run" class="pill"></span></div>
    <div id="clock"></div>
  </header>
  <main>
    <div>
      <div class="cards">
        <div class="card"><div class="label">Events</div><div class="value" id="eventCount">0</div></div>
        <div class="card"><div class="label">Alerts</div><div class="value bad" id="alertCount">0</div></div>
        <div class="card"><div class="label">Latest Score</div><div class="value" id="latestScore">0.000</div></div>
        <div class="card"><div class="label">Status</div><div class="value normal" id="status">OK</div></div>
      </div>
      <section>
        <h2>Metrics Timeline</h2>
        <canvas id="chart" width="900" height="260"></canvas>
      </section>
      <section style="margin-top:16px">
        <h2>Telemetry Stream</h2>
        <table>
          <thead><tr><th>Time</th><th>Source</th><th>CPU</th><th>Latency</th><th>Error Rate</th><th>Score</th><th>Model</th><th>State</th></tr></thead>
          <tbody id="events"></tbody>
        </table>
      </section>
    </div>
    <div>
      <section>
        <h2>Live Alerts</h2>
        <div id="alerts"></div>
      </section>
      <section style="margin-top:16px">
        <h2>Latest Logs & Traces</h2>
        <table>
          <thead><tr><th>Kind</th><th>Content</th></tr></thead>
          <tbody id="logs"></tbody>
        </table>
      </section>
    </div>
  </main>
  <script>
    function cell(v){ return v === undefined || v === null ? "" : v; }
    function shortTime(ts){ try { return new Date(ts).toLocaleTimeString(); } catch { return ts || ""; } }
    function draw(events){
      const c = document.getElementById("chart"), ctx = c.getContext("2d");
      ctx.clearRect(0,0,c.width,c.height);
      ctx.strokeStyle="#e4e7ec"; ctx.beginPath();
      for(let i=0;i<5;i++){ const y=20+i*50; ctx.moveTo(40,y); ctx.lineTo(c.width-20,y); }
      ctx.stroke();
      const rows = events.slice(-60);
      const series = [
        ["cpu_usage", "#1c7ed6", 100],
        ["latency_ms", "#f08c00", 400],
        ["error_rate", "#c92a2a", 1]
      ];
      series.forEach(([key,color,max]) => {
        ctx.strokeStyle=color; ctx.lineWidth=2; ctx.beginPath();
        rows.forEach((e,i) => {
          const x = 40 + (i / Math.max(1, rows.length-1)) * (c.width-70);
          const y = 240 - Math.min(max, Number(e.features?.[key] || 0)) / max * 210;
          if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
        });
        ctx.stroke();
      });
      ctx.fillStyle="#1c7ed6"; ctx.fillText("CPU", 48, 18);
      ctx.fillStyle="#f08c00"; ctx.fillText("Latency", 88, 18);
      ctx.fillStyle="#c92a2a"; ctx.fillText("Error", 150, 18);
    }
    async function refresh(){
      const ev = await fetch("/runtime/events?limit=100").then(r=>r.json());
      const al = await fetch("/runtime/alerts?limit=20").then(r=>r.json());
      const events = ev.events || [], alerts = al.alerts || [];
      document.getElementById("run").textContent = ev.run_id || "no run";
      document.getElementById("clock").textContent = new Date().toLocaleString();
      document.getElementById("eventCount").textContent = events.length;
      document.getElementById("alertCount").textContent = alerts.length;
      const latest = events[events.length-1] || {};
      document.getElementById("latestScore").textContent = Number(latest.anomaly_score || 0).toFixed(3);
      document.getElementById("status").textContent = alerts.length && alerts[alerts.length-1].event_id === latest.event_id ? "ALERT" : "OK";
      document.getElementById("status").className = alerts.length && alerts[alerts.length-1].event_id === latest.event_id ? "value bad" : "value normal";
      document.getElementById("events").innerHTML = events.slice(-20).reverse().map(e => `<tr><td>${shortTime(e.timestamp)}</td><td>${cell(e.source)}</td><td>${Number(e.features?.cpu_usage||0).toFixed(1)}</td><td>${Number(e.features?.latency_ms||0).toFixed(1)}</td><td>${Number(e.features?.error_rate||0).toFixed(3)}</td><td>${Number(e.anomaly_score||0).toFixed(3)}</td><td>${e.model}</td><td class="${e.label ? "bad" : "normal"}">${e.label ? "ANOMALY" : "normal"}</td></tr>`).join("");
      document.getElementById("alerts").innerHTML = alerts.slice(-10).reverse().map(e => `<div class="alert"><strong>${shortTime(e.timestamp)} anomaly score ${Number(e.anomaly_score).toFixed(3)}</strong><br/>source=${e.source}, model=${e.model}, cpu=${Number(e.features?.cpu_usage||0).toFixed(1)}, latency=${Number(e.features?.latency_ms||0).toFixed(1)}, error_rate=${Number(e.features?.error_rate||0).toFixed(3)}</div>`).join("") || "<p>No active alerts.</p>";
      document.getElementById("logs").innerHTML = events.slice(-12).reverse().map(e => `<tr><td>${cell(e.source)}</td><td>${cell(e.raw?.message || e.raw?.trace_id || JSON.stringify(e.features))}</td></tr>`).join("");
      draw(events);
    }
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>"""
