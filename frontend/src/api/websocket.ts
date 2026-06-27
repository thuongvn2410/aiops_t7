export const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';

export type Severity = 'critical' | 'warning' | 'info';

export interface AnomalyEvent {
  event_id: string;
  service_name: string;
  metric_name: string;
  anomaly_score: number;
  severity: Severity;
  detected_at: string;
  rca_causes: unknown[];
  source_table?: string;
  narrative?: string;
}

export interface WsMessage {
  type: 'anomaly' | 'heartbeat';
  data: AnomalyEvent | { sent_at: string };
}
