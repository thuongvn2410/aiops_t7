from __future__ import annotations

from pathlib import Path


def test_frontend_contract_files_exist() -> None:
    root = Path("frontend/src")
    required = [
        "App.tsx",
        "api/http.ts",
        "api/websocket.ts",
        "hooks/useWebSocket.ts",
        "store/anomalyStore.ts",
        "components/monitor/MetricTimeline.tsx",
        "components/alerts/AlertBanner.tsx",
        "styles/theme.css",
    ]
    for rel in required:
        assert (root / rel).exists()


def test_frontend_uses_env_urls_and_dark_theme() -> None:
    http = Path("frontend/src/api/http.ts").read_text(encoding="utf-8")
    ws = Path("frontend/src/api/websocket.ts").read_text(encoding="utf-8")
    theme = Path("frontend/src/styles/theme.css").read_text(encoding="utf-8")
    assert "VITE_API_URL" in http
    assert "VITE_WS_URL" in ws
    assert "--bg-base: #0D1117" in theme
    assert "#fff" not in theme.lower()
