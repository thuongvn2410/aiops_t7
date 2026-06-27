import { useCallback, useEffect, useState } from 'react';
import { http } from '../api/http';

export interface MetricPoint {
  timestamp: string;
  value: number;
  service: string;
  metric_name: string;
  unit?: string;
  anomaly_score?: number;
  severity?: string;
}

export function useServices() {
  const [services, setServices] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    http
      .get<string[]>('/api/metrics/services')
      .then((res) => setServices(res.data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);
  return { services, loading, error };
}

export function useMetricTimeline(serviceName: string, metricName: string) {
  const [points, setPoints] = useState<MetricPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    if (!serviceName || !metricName) return;
    setLoading(true);
    setError('');
    http
      .get<MetricPoint[]>('/api/metrics/timeline', { params: { service_name: serviceName, metric_name: metricName, minutes: 60 } })
      .then((res) => setPoints(res.data.slice(-200)))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [serviceName, metricName]);

  useEffect(() => load(), [load]);

  const append = useCallback((point: MetricPoint) => {
    setPoints((prev) => [...prev, point].slice(-200));
  }, []);

  return { points, loading, error, reload: load, append };
}

export function useMetricNames(serviceName: string) {
  const [metricNames, setMetricNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    http
      .get<string[]>('/api/metrics/metric-names', { params: serviceName ? { service_name: serviceName } : {} })
      .then((res) => setMetricNames(res.data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [serviceName]);

  return { metricNames, loading, error };
}
