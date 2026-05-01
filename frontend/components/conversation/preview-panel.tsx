import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { ScriptedPreview } from './scenarios';
import { cn } from '@/lib/utils';

const TIER_BADGE: Record<1 | 2 | 3, 'tier1' | 'tier2' | 'tier3'> = {
  1: 'tier1',
  2: 'tier2',
  3: 'tier3',
};

export function PreviewPanel({ preview }: { preview: ScriptedPreview | null }) {
  if (!preview) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-slate-500">
        L&apos;aperçu d&apos;impact apparaîtra ici dès qu&apos;une modification sera proposée.
      </div>
    );
  }

  return (
    <div className="space-y-5 p-5">
      {preview.metrics.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {preview.metrics.map((m) => (
            <Card key={m.label}>
              <CardContent className="p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  {m.label}
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="font-semibold text-slate-900">{m.value}</span>
                  {m.delta && (
                    <span
                      className={cn(
                        'text-xs font-medium',
                        m.tone === 'good' && 'text-emerald-600',
                        m.tone === 'bad' && 'text-rose-700',
                        m.tone === 'neutral' && 'text-slate-500',
                        !m.tone && 'text-slate-500',
                      )}
                    >
                      {m.delta}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {preview.impacted.length > 0 && (
        <Card>
          <CardHeader className="border-b py-2">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-slate-500">
              OF impactés ({preview.impacted.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y divide-slate-100 text-sm">
              {preview.impacted.map((i) => (
                <li key={i.orderRef} className="flex items-center justify-between p-3">
                  <div>
                    <div className="font-mono text-xs text-slate-600">{i.orderRef}</div>
                    <div className="text-slate-800">{i.client}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={TIER_BADGE[i.tier]}>T{i.tier}</Badge>
                    <span className="text-xs text-slate-500">{i.change}</span>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {preview.guarantees.length > 0 && (
        <div className="rounded border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          <div className="mb-1 font-semibold">✓ Garanties</div>
          <ul className="list-inside list-disc text-xs">
            {preview.guarantees.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
