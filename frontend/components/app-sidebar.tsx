'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkshop, useVersions } from '@/lib/api/hooks';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊', href: '' },
  { id: 'gantt', label: 'Planning', icon: '📅', href: '/gantt' },
  { id: 'conversation', label: 'Conversation', icon: '💬', href: '/conversation' },
  { id: 'preflight', label: 'Imports CSV', icon: '📥', href: '/preflight' },
  { id: 'versions', label: 'Historique', icon: '🕐', href: '/versions' },
];

export function AppSidebar({ workshopId }: { workshopId: string }) {
  const pathname = usePathname();
  const workshopQuery = useWorkshop(workshopId);
  const versionsQuery = useVersions(workshopId);
  const activeVersion = versionsQuery.data?.find((v) => v.isActive);
  const base = `/workshops/${workshopId}`;

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-slate-200 bg-slate-900 text-slate-100">
      <div className="border-b border-slate-800 px-5 py-5">
        <Link href="/" className="block">
          <div className="text-base font-semibold text-white">
            {workshopQuery.data?.name ?? 'Atelier'}
          </div>
          <div className="mt-0.5 text-xs text-slate-400">
            {workshopQuery.data?.city ?? '—'}
          </div>
        </Link>
      </div>

      <nav className="mt-3 flex-1">
        {NAV.map((item) => {
          const href = `${base}${item.href}`;
          const isActive =
            item.href === '' ? pathname === base : pathname?.startsWith(href);
          return (
            <Link
              key={item.id}
              href={href}
              className={cn(
                'flex items-center gap-3 px-5 py-3 text-sm transition-colors hover:bg-slate-800',
                isActive
                  ? 'border-l-4 border-indigo-500 bg-slate-800 pl-4 text-white'
                  : 'text-slate-300',
              )}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-800 px-5 py-4 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
            CA
          </div>
          <div>
            <div className="font-medium text-slate-200">Chef d&apos;atelier</div>
            <div>session locale</div>
          </div>
        </div>
        {activeVersion && (
          <div className="mt-2 border-t border-slate-800 pt-2">
            Version active :{' '}
            <span className="font-mono text-emerald-400">v{activeVersion.versionNumber}</span>
          </div>
        )}
      </div>
    </aside>
  );
}
