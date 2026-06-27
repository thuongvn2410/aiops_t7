import type { AnomalyEvent } from '../../api/websocket';
import { StatusBadge } from '../shared/StatusBadge';
import { Sparkline } from '../shared/Sparkline';

function statusFor(service: string, alerts: AnomalyEvent[]) {
  const recent = alerts.find((alert) => alert.service_name === service);
  if (!recent) return 'ok';
  if (recent.severity === 'critical') return 'critical';
  if (recent.severity === 'warning') return 'warning';
  return 'info';
}

export function ServiceGrid({
  services,
  alerts,
  selected,
  onSelect
}: {
  services: string[];
  alerts: AnomalyEvent[];
  selected: string;
  onSelect: (service: string) => void;
}) {
  if (!services.length) {
    return <section className="panel empty-state">No services yet. Waiting for ClickHouse metrics.</section>;
  }
  return (
    <section className="service-grid">
      {services.map((service) => {
        const status = statusFor(service, alerts);
        const openCount = alerts.filter((alert) => alert.service_name === service).length;
        const spark = alerts
          .filter((alert) => alert.service_name === service)
          .slice(0, 15)
          .reverse()
          .map((alert) => ({ value: alert.anomaly_score }));
        return (
          <button key={service} className={`service-card ${selected === service ? 'selected' : ''}`} onClick={() => onSelect(service)}>
            <div className="card-row">
              <span className="service-name">{service}</span>
              <StatusBadge status={status as 'ok' | 'warning' | 'critical' | 'info'} />
            </div>
            <Sparkline data={spark} />
            <div className="card-row muted">
              <span>Open alerts</span>
              <span className="metric-number">{openCount}</span>
            </div>
          </button>
        );
      })}
    </section>
  );
}
