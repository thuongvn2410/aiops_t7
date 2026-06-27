# AIOps Anomaly Detection Platform

GPU target: RTX 4060 Ti 16GB.

## ClickHouse Monitor Stack

The monitor stack lives in `backend/`, `frontend/`, and `db/`.

```bash
docker compose up --build
```

Open the React monitor:

```text
http://localhost:3000
```

Backend API:

```text
http://localhost:8000/api/health
ws://localhost:8000/ws
```

The backend reads only `aiops.metrics`, `aiops.logs`, and `aiops.traces`. It writes only `aiops.anomaly_events` and `aiops.alert_incidents`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## GPU Compute Estimate

```text
GPU compute estimate (RTX 4060 Ti 16GB):
  Isolation Forest : ~0.05h  (CPU)
  Autoencoder      : ~0.5h   (GPU, mixed precision)
  DeepSVDD         : ~0.8h   (GPU)
  XGBoost          : ~0.1h   (GPU hist)
  TFT              : ~2.0h   (GPU, gradient checkpointing)
  Ensemble fit     : ~0.05h  (CPU)
  -------------------------------------
  Total first run  : ~3.5h   (cached stages skip on re-run)
```

## Run Order

```bash
python -m src.pipeline.acquire
pytest tests/test_acquire.py -v

python -m src.pipeline.prepare
pytest tests/test_prepare.py -v

python -m src.pipeline.process --model all
pytest tests/test_models.py -v

python -m src.pipeline.parse
pytest tests/test_parse.py -v

python -m src.pipeline.render
pytest tests/test_render.py -v
```

API:

```bash
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Realtime monitor:

```bash
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
python scripts/simulate_realtime.py --interval 1
```

Open:

```text
http://127.0.0.1:8000/monitor
```

Dashboard:

```bash
streamlit run dashboard/app.py
```

## State Machine

Each pipeline stage is idempotent. Existing output files mean the stage is complete and can be skipped. Use `RUN_ID` to target an existing run; otherwise the newest run is reused when appropriate or a fresh run id is created.
"# aiops_t7" 
