import { useEffect, useMemo } from 'react';
import { toVNTime } from '../../utils/time';
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { AnomalyEvent } from '../../api/websocket';
import { useMetricNames, useMetricTimeline } from '../../hooks/useMetrics';
import { AnomalyOverlay } from './AnomalyOverlay';

export function MetricTimeline({
  serviceName,
  metricName,
  services,
  onServiceChange,
  onMetricChange,
  lastEvent
}: {
  serviceName: string;
  metricName: string;
  services: string[];
  onServiceChange: (service: string) => void;
  onMetricChange: (metric: string) => void;
  lastEvent?: AnomalyEvent;
}) {
  const { points, loading, error, append } = useMetricTimeline(serviceName, metricName);
  const { metricNames } = useMetricNames(serviceName);

  // Auto-select first available metric when current selection doesn't exist for this service
  useEffect(() => {
    if (metricNames.length && metricName && !metricNames.includes(metricName)) {
      onMetricChange(metricNames[0]);
    }
  }, [metricNames, metricName, onMetricChange]);

  useEffect(() => {
    if (!lastEvent || lastEvent.service_name !== serviceName || lastEvent.metric_name !== metricName) return;
    append({
      timestamp: lastEvent.detected_at,
      value: lastEvent.anomaly_score,
      service: lastEvent.service_name,
      metric_name: lastEvent.metric_name,
      anomaly_score: lastEvent.anomaly_score,
      severity: lastEvent.severity
    });
  }, [append, lastEvent, metricName, serviceName]);

  const chartData = useMemo(
    () => points.map((point) => ({ ...point, time: toVNTime(point.timestamp) })),
    [points]
  );

  return (
    <section className="panel timeline-panel">
      <div className="panel-header">
        <div>
          <h2>Metric Timeline</h2>
          <span className="muted">Sliding window capped at 200 points</span>
        </div>
        <div className="selector-row">
          <select value={serviceName} onChange={(event) => onServiceChange(event.target.value)} aria-label="service selector">
            {services.length ? services.map((service) => <option key={service}>{service}</option>) : <option>No service</option>}
          </select>
          <select value={metricName} onChange={(event) => onMetricChange(event.target.value)} aria-label="metric selector">
            {(metricNames.length ? metricNames : [metricName]).map((metric) => <option key={metric}>{metric}</option>)}
          </select>
        </div>
      </div>
      {loading && <div className="empty-state">Loading metric history...</div>}
      {error && <div className="error-state">Timeline error: {error}</div>}
      {!loading && !error && !chartData.length && <div className="empty-state">No timeline data yet.</div>}
      {!!chartData.length && (
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartData}>
            <CartesianGrid stroke="var(--border-muted)" />
            <XAxis dataKey="timestamp" tickFormatter={(value) => toVNTime(value)} stroke="var(--text-secondary)" minTickGap={32} />
            <YAxis stroke="var(--text-secondary)" />
            <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
            <AnomalyOverlay points={points} />
            <Line type="monotone" dataKey="value" stroke="var(--accent-blue)" dot={false} strokeWidth={2} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
