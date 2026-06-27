from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.db.client import clickhouse_status, get_client
from backend.models.detector import load_or_train_detector
from backend.models.trainer import save_model, train_from_clickhouse
from backend.routers.alerts import router as alerts_router
from backend.routers.health import router as health_router
from backend.routers.metrics import router as metrics_router
from backend.services.scheduler import PollingService
from backend.ws.manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = load_or_train_detector(retrain=False)
    app.state.stop_event = asyncio.Event()
    app.state.heartbeat_task = asyncio.create_task(ws_manager.heartbeat_loop(app.state.stop_event))
    try:
        if clickhouse_status() == "ok":
            app.state.poller = PollingService(get_client(), app.state.detector, ws_manager)
            app.state.poller.start()
        else:
            app.state.poller = None
            print("scheduler disabled=clickhouse unavailable")
    except Exception as exc:
        app.state.poller = None
        print(f"scheduler disabled={exc}")
    yield
    app.state.stop_event.set()
    if app.state.poller is not None:
        await app.state.poller.shutdown()
    await app.state.heartbeat_task


app = FastAPI(title="AIOps Monitor Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(metrics_router)
app.include_router(alerts_router)
app.include_router(health_router)


@app.post("/api/model/retrain")
def retrain() -> dict:
    model, threshold, rows_used = train_from_clickhouse(get_client(), lookback_minutes=15)
    manifest = save_model(model, threshold, rows_used)
    app.state.detector = load_or_train_detector(retrain=False)
    if getattr(app.state, "poller", None) is not None:
        app.state.poller.detector = app.state.detector
    return {"status": "ok", "trained_at": manifest["trained_at"], "rows_used": rows_used}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
    except Exception:
        await ws_manager.disconnect(ws)
