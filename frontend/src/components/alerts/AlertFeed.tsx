import { useMemo, useState } from 'react';
import type { Severity } from '../../api/websocket';
import { useAlerts } from '../../hooks/useAlerts';
import { IncidentCard } from './IncidentCard';

const filters = ['all', 'critical', 'warning', 'info'] as const;

export function AlertFeed() {
  const { alerts, loading, error } = useAlerts();
  const [filter, setFilter] = useState<(typeof filters)[number]>('all');
  const visible = useMemo(() => (filter === 'all' ? alerts : alerts.filter((alert) => alert.severity === filter)), [alerts, filter]);

  return (
    <section className="panel alert-feed">
      <div className="panel-header">
        <h2>Alert Feed</h2>
        <div className="filter-bar">
          {filters.map((item) => (
            <button key={item} className={filter === item ? 'active' : ''} onClick={() => setFilter(item)}>
              {item}
            </button>
          ))}
        </div>
      </div>
      {loading && <div className="empty-state">Loading alerts...</div>}
      {error && <div className="error-state">Alert load error: {error}</div>}
      {!loading && !error && !visible.length && <div className="empty-state">No alerts in this filter.</div>}
      <div className="feed-list">{visible.map((event) => <IncidentCard key={event.event_id} event={event} />)}</div>
    </section>
  );
}
