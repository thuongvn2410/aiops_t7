import { useEffect, useRef, useState } from 'react';
import { WS_URL, type AnomalyEvent, type WsMessage } from '../api/websocket';
import { useAnomalyStore } from '../store/anomalyStore';

export type WsStatus = 'connected' | 'disconnected' | 'reconnecting';

export function useWebSocket(onAnomaly?: (event: AnomalyEvent) => void) {
  const [status, setStatus] = useState<WsStatus>('disconnected');
  const [lastHeartbeat, setLastHeartbeat] = useState<string>('');
  const [lastEvent, setLastEvent] = useState<AnomalyEvent | undefined>();
  const addAlert = useAnomalyStore((state) => state.addAlert);
  const retryRef = useRef<number>();

  useEffect(() => {
    let socket: WebSocket | undefined;
    let cancelled = false;

    const connect = () => {
      setStatus('reconnecting');
      socket = new WebSocket(WS_URL);
      socket.onopen = () => setStatus('connected');
      socket.onmessage = (raw) => {
        const message = JSON.parse(raw.data) as WsMessage;
        if (message.type === 'heartbeat') {
          setLastHeartbeat((message.data as { sent_at: string }).sent_at);
        }
        if (message.type === 'anomaly') {
          const event = message.data as AnomalyEvent;
          setLastEvent(event);
          addAlert(event);
          onAnomaly?.(event);
        }
      };
      socket.onclose = () => {
        if (!cancelled) {
          setStatus('disconnected');
          retryRef.current = window.setTimeout(connect, 3000);
        }
      };
      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (retryRef.current) window.clearTimeout(retryRef.current);
      socket?.close();
    };
  }, [addAlert, onAnomaly]);

  return { status, lastHeartbeat, lastEvent };
}
