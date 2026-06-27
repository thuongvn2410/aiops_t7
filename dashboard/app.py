from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.pipeline.state import DATA_DIR, get_latest_run_id, run_dir, stage_status

st.set_page_config(page_title="AIOps Dashboard", layout="wide")
st.title("AIOps Anomaly Detection")

runs = sorted([p.name for p in DATA_DIR.glob("*") if p.is_dir()], reverse=True)
run_id = st.sidebar.selectbox("Run", runs, index=0 if runs else None) if runs else get_latest_run_id()

if not run_id:
    st.info("No pipeline runs found.")
    st.stop()

root = run_dir(run_id)
tabs = st.tabs(["Anomaly Timeline", "Pipeline Status", "Model Leaderboard", "Alert Feed", "Cost Tracker"])

with tabs[0]:
    split = root / "splits" / "test.parquet"
    if split.exists():
        frame = pd.read_parquet(split).tail(60)
        st.line_chart(frame.set_index("timestamp")[["latency_ms", "cpu_usage", "error_rate"]])

with tabs[1]:
    st.dataframe(pd.DataFrame([stage_status(run_id)]).T.rename(columns={0: "complete"}))

with tabs[2]:
    metrics = root / "parsed" / "metrics.json"
    if metrics.exists():
        st.dataframe(pd.DataFrame(json.loads(metrics.read_text(encoding="utf-8"))["models"]))

with tabs[3]:
    errors = root / "parse_errors.jsonl"
    if errors.exists():
        for line in errors.read_text(encoding="utf-8").splitlines()[-20:]:
            st.json(json.loads(line))

with tabs[4]:
    manifest = root / "process" / "run_manifest.json"
    if manifest.exists():
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        rows = payload.get("models", [])
        st.dataframe(pd.DataFrame(rows))
