import type { Machine, OrderListItem } from '@/lib/api/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const TIER_BG: Record<1 | 2 | 3, string> = {
  1: '#7f1d1d',
  2: '#c2410c',
  3: '#475569',
};

interface MiniGanttProps {
  machines: Machine[];
  orders: OrderListItem[];
}

/**
 * Mini-Gantt pour le dashboard : 1 ligne par machine, segments colorés par tier.
 *
 * V1 : on n'a pas encore le Schedule réel (qui vient du worker Python). On
 * affiche les OFs pending par machine en cumul de durée (sans dimension
 * temps absolue). Le Gantt complet (Phase 5 J3) consommera le Schedule.
 */
export function MiniGantt({ machines, orders }: MiniGanttProps) {
  const ordersByMachine = new Map<string, OrderListItem[]>();
  for (const m of machines) ordersByMachine.set(m.id, []);
  for (const o of orders) {
    // V1 : on a pas access aux operations pour la machine ici (l'API list
    // d'orders n'expose pas operations). On groupe par première op via
    // l'orderRef pour donner un visuel — placeholder jusqu'à J3.
    if (!o.job) continue;
    // Placeholder : distribution round-robin sur les machines pour la démo
    const idx = Math.abs(orderHash(o.orderRef)) % machines.length;
    const m = machines[idx];
    if (m) ordersByMachine.get(m.id)!.push(o);
  }

  if (machines.length === 0) {
    return (
      <Card>
        <CardHeader className="border-b py-3">
          <CardTitle className="text-base font-semibold">Aperçu charge machines</CardTitle>
        </CardHeader>
        <CardContent className="p-6 text-center text-sm text-slate-500">
          Aucune machine configurée.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between border-b py-3">
        <CardTitle className="text-base font-semibold">Aperçu charge machines</CardTitle>
        <span className="text-xs text-slate-500">
          V1 (vue indicative — Gantt complet à venir J3)
        </span>
      </CardHeader>
      <CardContent className="space-y-2 p-5">
        {machines.map((m) => {
          const ofsForMachine = ordersByMachine.get(m.id) ?? [];
          return (
            <div key={m.id} className="grid grid-cols-[140px_1fr] items-center gap-2">
              <div className="font-mono text-xs text-slate-700">{m.name}</div>
              <div className="flex h-6 items-center gap-px overflow-hidden rounded bg-slate-100">
                {ofsForMachine.length === 0 ? (
                  <div className="h-full w-full bg-slate-50" />
                ) : (
                  ofsForMachine.slice(0, 10).map((o) => (
                    <div
                      key={o.id}
                      className="h-full flex-1 rounded opacity-85"
                      style={{ background: TIER_BG[(o.client.tier as 1 | 2 | 3) ?? 2] }}
                      title={`${o.orderRef} · ${o.client.name} · T${o.client.tier}`}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
        <div className="mt-3 flex items-center gap-4 border-t border-slate-100 pt-2 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded" style={{ background: TIER_BG[1] }} />
            Tier 1
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded" style={{ background: TIER_BG[2] }} />
            Tier 2
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded" style={{ background: TIER_BG[3] }} />
            Tier 3
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function orderHash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i);
  return h;
}
