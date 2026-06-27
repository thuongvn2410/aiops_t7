import { useEffect, useState } from 'react';
import { StatusBadge } from '../shared/StatusBadge';
import type { WsStatus } from '../../hooks/useWebSocket';
import { nowVN } from '../../utils/time';

export function TopBar({ status, modelLoaded, threshold }: { status: WsStatus; modelLoaded: boolean; threshold?: number | null }) {
  const [now, setNow] = useState(nowVN());
  useEffect(() => {
    const id = window.setInterval(() => setNow(nowVN()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const wsState = status === 'connected' ? 'ok' : status === 'reconnecting' ? 'warning' : 'critical';
  return (
    <header className="topbar">
      <div>
        <strong>Realtime Operations Monitor</strong>
        <span className="topbar-sub">ClickHouse / IsolationForest / WebSocket</span>
      </div>
      <div className="topbar-right">
        <StatusBadge status={wsState} label={`WS ${status}`} />
        <span className="model-pill">Model: {modelLoaded ? 'IsolationForest' : 'fallback'} | threshold: {threshold?.toFixed?.(2) ?? '0.60'}</span>
        <span className="clock">{now}</span>
      </div>
    </header>
  );
}
