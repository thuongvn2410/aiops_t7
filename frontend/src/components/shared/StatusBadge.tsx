import clsx from 'clsx';

type Status = 'ok' | 'warning' | 'critical' | 'unknown' | 'info';

export function StatusBadge({ status, label }: { status: Status; label?: string }) {
  return <span className={clsx('status-badge', `status-${status}`)}>{label || status}</span>;
}
