import { useEffect, useState } from 'react';
import { useAnomalyStore } from '../../store/anomalyStore';

export function AlertBanner() {
  const lastCritical = useAnomalyStore((state) => state.lastCritical);
  const dismissedCriticalId = useAnomalyStore((state) => state.dismissedCriticalId);
  const dismiss = useAnomalyStore((state) => state.dismissCritical);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!lastCritical || dismissedCriticalId === lastCritical.event_id) return;
    setVisible(true);
    const id = window.setTimeout(() => setVisible(false), 30000);
    return () => window.clearTimeout(id);
  }, [dismissedCriticalId, lastCritical]);

  if (!lastCritical || !visible || dismissedCriticalId === lastCritical.event_id) return null;
  return (
    <section className="alert-banner" style={{ transition: 'all 0.3s ease', animation: 'slideDown 0.3s ease' }}>
      <div>
        <strong>Anomaly detected</strong> — {lastCritical.service_name} / {lastCritical.metric_name} — score:{' '}
        {lastCritical.anomaly_score.toFixed(2)}
        {lastCritical.narrative && (
          <p style={{ margin: '6px 0 0', fontSize: '13px', color: 'var(--text-secondary)' }}>
            {lastCritical.narrative}
          </p>
        )}
      </div>
      <button onClick={dismiss}>Dismiss</button>
    </section>
  );
}
