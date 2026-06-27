import type { AnomalyEvent } from '../../api/websocket';
import { StatusBadge } from '../shared/StatusBadge';
import { toVNDateTime } from '../../utils/time';

export function IncidentCard({ event }: { event: AnomalyEvent }) {
  const causes = Array.isArray(event.rca_causes) ? (event.rca_causes as string[]) : [];
  return (
    <details className="incident-card">
      <summary>
        <span className="timestamp">{toVNDateTime(event.detected_at)}</span>
        <span className="service-chip">{event.service_name}</span>
        <span>{event.metric_name}</span>
        <span className="metric-number">{event.anomaly_score.toFixed(3)}</span>
        <StatusBadge status={event.severity} />
      </summary>
      <div style={{ padding: '8px 0 4px' }}>
        <p style={{ margin: '0 0 8px', color: 'var(--text-secondary)', fontSize: '13px' }}>
          {event.narrative || 'Đang phân tích...'}
        </p>
        {causes.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
            {causes.map((cause, i) => (
              <span
                key={i}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: '999px',
                  padding: '2px 10px',
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--accent-purple)',
                }}
              >
                {cause}
              </span>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
