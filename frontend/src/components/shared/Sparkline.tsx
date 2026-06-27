import { Line, LineChart, ResponsiveContainer } from 'recharts';

export function Sparkline({ data }: { data: Array<{ value: number }> }) {
  if (!data.length) return <div className="sparkline-empty">No points</div>;
  return (
    <ResponsiveContainer width="100%" height={42}>
      <LineChart data={data.slice(-15)}>
        <Line type="monotone" dataKey="value" stroke="var(--accent-blue)" strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
