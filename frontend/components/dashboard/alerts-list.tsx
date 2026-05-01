import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export interface Alert {
  id: string;
  severity: 'critique' | 'majeur' | 'info';
  title: string;
  detail: string;
  action?: string;
}

const SEV_STYLE: Record<Alert['severity'], { bg: string; border: string; icon: string; label: string }> = {
  critique: {
    bg: 'bg-rose-50',
    border: 'border-l-rose-600',
    icon: '🔴',
    label: 'Critique',
  },
  majeur: {
    bg: 'bg-orange-50',
    border: 'border-l-orange-500',
    icon: '🟠',
    label: 'Majeur',
  },
  info: {
    bg: 'bg-sky-50',
    border: 'border-l-sky-500',
    icon: '🔵',
    label: 'Info',
  },
};

export function AlertsList({ alerts }: { alerts: Alert[] }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between border-b py-3">
        <CardTitle className="text-base font-semibold">Alertes &amp; événements</CardTitle>
        <span className="text-xs text-slate-500">
          {alerts.length} alerte{alerts.length > 1 ? 's' : ''} active{alerts.length > 1 ? 's' : ''}
        </span>
      </CardHeader>
      <CardContent className="p-0">
        {alerts.length === 0 ? (
          <div className="px-5 py-6 text-center text-sm text-slate-500">
            Aucune alerte active.
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {alerts.map((a) => {
              const style = SEV_STYLE[a.severity];
              return (
                <li
                  key={a.id}
                  className={cn(
                    'flex items-start gap-3 border-l-4 px-5 py-3',
                    style.bg,
                    style.border,
                  )}
                >
                  <div className="text-lg" aria-label={style.label}>
                    {style.icon}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-slate-900">{a.title}</div>
                    <div className="mt-0.5 text-sm text-slate-600">{a.detail}</div>
                  </div>
                  {a.action && (
                    <button
                      type="button"
                      className="rounded px-3 py-1 text-sm font-medium text-indigo-600 hover:bg-white hover:text-indigo-800"
                    >
                      {a.action} →
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
