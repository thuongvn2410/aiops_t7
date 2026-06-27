import { useCallback, useEffect, useState } from 'react';
import { http } from '../api/http';
import type { AnomalyEvent } from '../api/websocket';
import { useAnomalyStore } from '../store/anomalyStore';

export function useAlerts() {
  const alerts = useAnomalyStore((state) => state.alerts);
  const setInitialAlerts = useAnomalyStore((state) => state.setInitialAlerts);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    http
      .get<AnomalyEvent[]>('/api/alerts/recent', { params: { limit: 50 } })
      .then((res) => {
        setInitialAlerts(res.data);
        setError('');
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [setInitialAlerts]);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 5000);
    return () => window.clearInterval(id);
  }, [load]);

  return { alerts, loading, error };
}
