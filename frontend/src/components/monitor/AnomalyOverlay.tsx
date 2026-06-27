import { ReferenceArea } from 'recharts';
import type { MetricPoint } from '../../hooks/useMetrics';

export function AnomalyOverlay({ points }: { points: MetricPoint[] }) {
  return (
    <>
      {points
        .filter((point) => point.severity === 'critical' || point.severity === 'warning')
        .slice(-20)
        .map((point) => (
          <ReferenceArea
            key={`${point.timestamp}-${point.anomaly_score}`}
            x1={point.timestamp}
            x2={point.timestamp}
            fill="#F85149"
            fillOpacity={0.15}
            strokeOpacity={0}
          />
        ))}
    </>
  );
}
