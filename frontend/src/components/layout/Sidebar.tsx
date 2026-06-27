import clsx from 'clsx';

const items = ['Overview', 'Services', 'Alerts'];

export function Sidebar({ active, onSelect }: { active: string; onSelect: (item: string) => void }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-mark">AIOps</div>
      {items.map((item) => (
        <button key={item} className={clsx('nav-item', active === item && 'active')} onClick={() => onSelect(item)}>
          {item}
        </button>
      ))}
    </aside>
  );
}
