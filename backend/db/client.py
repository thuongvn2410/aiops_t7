from __future__ import annotations

from functools import lru_cache
import socket

from backend.config import (
    CLICKHOUSE_CONNECT_TIMEOUT,
    CLICKHOUSE_DB,
    CLICKHOUSE_HOST,
    CLICKHOUSE_PASS,
    CLICKHOUSE_PORT,
    CLICKHOUSE_SEND_RECEIVE_TIMEOUT,
    CLICKHOUSE_USER,
)


@lru_cache(maxsize=1)
def get_client():
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASS,
        connect_timeout=CLICKHOUSE_CONNECT_TIMEOUT,
        send_receive_timeout=CLICKHOUSE_SEND_RECEIVE_TIMEOUT,
    )


def clickhouse_status() -> str:
    try:
        with socket.create_connection((CLICKHOUSE_HOST, CLICKHOUSE_PORT), timeout=0.5):
            pass
        from backend.db.queries import q_select_one

        get_client().query(q_select_one())
        return "ok"
    except Exception:
        return "error"
