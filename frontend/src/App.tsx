import { useCallback, useEffect, useMemo, useState } from 'react';
import { http } from './api/http';
import type { AnomalyEvent } from './api/websocket';
import { AlertBanner } from './components/alerts/AlertBanner';
import { AlertFeed } from './components/alerts/AlertFeed';
import { Sidebar } from './components/layout/Sidebar';
import { TopBar } from './components/layout/TopBar';
import { MetricTimeline } from './components/monitor/MetricTimeline';
import { ServiceGrid } from './components/monitor/ServiceGrid';
import { useServices } from './hooks/useMetrics';
import { useWebSocket } from './hooks/useWebSocket';
import { useAnomalyStore } from './store/anomalyStore';

interface Health {
  status: string;
  clickhouse: string;
  model_loaded: boolean;
  threshold?: number;
}

function App() {
  const [active, setActive] = useState('Overview');
  const [selectedService, setSelectedService] = useState('');
  const [selectedMetric, setSelectedMetric] = useState('cpu_usage');
  const [health, setHealth] = useState<Health>({ status: 'loading', clickhouse: 'unknown', model_loaded: false });
  const [healthError, setHealthError] = useState('');
  const alerts = useAnomalyStore((state) => state.alerts);
  const { services, loading: servicesLoading, error: servicesError } = useServices();

  useEffect(() => {
    if (!selectedService && services.length) setSelectedService(services[0]);
  }, [selectedService, services]);

  const handleAnomaly = useCallback((event: AnomalyEvent) => {
    if (!selectedService) setSelectedService(event.service_name);
  }, [selectedService]);

  const ws = useWebSocket(handleAnomaly);

  useEffect(() => {
    const load = () => {
      http
        .get<Health>('/api/health')
        .then((res) => {
          setHealth(res.data);
          setHealthError('');
        })
        .catch((err) => setHealthError(err.message));
    };
    load();
    const id = window.setInterval(load, 10000);
    return () => window.clearInterval(id);
  }, []);

  const serviceList = useMemo(() => {
    const fromAlerts = alerts.map((alert) => alert.service_name);
    return Array.from(new Set([...services, ...fromAlerts])).filter(Boolean);
  }, [alerts, services]);

  return (
    <div className="app-shell">
      <Sidebar active={active} onSelect={setActive} />
      <div className="main-shell">
        <TopBar status={ws.status} modelLoaded={health.model_loaded} threshold={health.threshold} />
        <main className="content">
          <AlertBanner />
          {healthError && <div className="error-state">Health check error: {healthError}</div>}
          {health.clickhouse === 'error' && !services.length && !alerts.length && (
            <div className="warning-state">ClickHouse is unavailable. UI remains online and will fill when data arrives.</div>
          )}
          {servicesLoading && <div className="empty-state">Loading service inventory...</div>}
          {servicesError && <div className="error-state">Service load error: {servicesError}</div>}
          <ServiceGrid services={serviceList} alerts={alerts} selected={selectedService} onSelect={setSelectedService} />
          <MetricTimeline
            serviceName={selectedService}
            metricName={selectedMetric}
            services={serviceList}
            onServiceChange={setSelectedService}
            onMetricChange={setSelectedMetric}
            lastEvent={ws.lastEvent}
          />
          <AlertFeed />
        </main>
      </div>
    </div>
  );
}

export default App;
