'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { compareSnapshots } from './compare';
import { cn } from '@/lib/utils';

interface DiffPanelProps {
  base: { versionNumber: number; snapshot: unknown } | null;
  target: { versionNumber: number; snapshot: unknown; isActive: boolean } | null;
}

export function DiffPanel({ base, target }: DiffPanelProps) {
  if (!base || !target) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-sm text-slate-500">
          Sélectionne deux versions dans la timeline pour voir le diff.
        </CardContent>
      </Card>
    );
  }
  if (base.versionNumber === target.versionNumber) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-sm text-slate-500">
          Les versions <strong>base</strong> et <strong>cible</strong> sont identiques. Sélectionne
          deux versions différentes pour voir le diff.
        </CardContent>
      </Card>
    );
  }
  const result = compareSnapshots(base.snapshot, target.snapshot);

  return (
    <Card>
      <CardHeader className="border-b py-3">
        <CardTitle className="text-base font-semibold">
          Diff <span className="font-mono text-amber-700">v{base.versionNumber}</span> →{' '}
          <span className="font-mono text-indigo-700">
            v{target.versionNumber}
            {target.isActive && ' (active)'}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 p-5">
        <div className="grid grid-cols-3 gap-3">
          {result.metrics.map((m) => (
            <div
              key={m.label}
              className="rounded border border-slate-200 bg-white p-3"
            >
              <div className="text-[10px] uppercase tracking-wider text-slate-500">{m.label}</div>
              <div className="flex items-baseline gap-2">
                <span className="text-lg font-semibold text-slate-900">{m.after}</span>
                {m.delta && (
                  <span
                    className={cn(
                      'text-xs font-medium',
                      m.tone === 'good' && 'text-emerald-600',
                      m.tone === 'bad' && 'text-rose-700',
                    )}
                  >
                    {m.delta}
                  </span>
                )}
              </div>
              <div className="text-[10px] text-slate-500">v{base.versionNumber} : {m.before}</div>
            </div>
          ))}
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Changements détaillés
          </h3>
          <ul className="divide-y divide-slate-100 rounded border border-slate-200 bg-white text-sm">
            {result.summary.map((s, idx) => (
              <li key={idx} className="px-3 py-2 text-slate-700">
                {s}
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
