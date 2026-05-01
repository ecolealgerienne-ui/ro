'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { VersionListItem } from '@/lib/api/types';
import { cn } from '@/lib/utils';

interface VersionsTimelineProps {
  versions: VersionListItem[];
  baseVersionNumber: number | null;
  targetVersionNumber: number | null;
  onSelect: (versionNumber: number, slot: 'base' | 'target') => void;
}

export function VersionsTimeline({
  versions,
  baseVersionNumber,
  targetVersionNumber,
  onSelect,
}: VersionsTimelineProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b py-3">
        <CardTitle className="text-base font-semibold">
          Versions ({versions.length})
        </CardTitle>
        <p className="text-xs text-slate-500">
          Click → définit la version <strong>cible</strong>. Shift+click → version{' '}
          <strong>base</strong> (à comparer).
        </p>
      </CardHeader>
      <ul className="divide-y divide-slate-100">
        {versions.map((v) => {
          const isBase = baseVersionNumber === v.versionNumber;
          const isTarget = targetVersionNumber === v.versionNumber;
          return (
            <li
              key={v.id}
              className={cn(
                'cursor-pointer p-3 transition-colors hover:bg-slate-50',
                v.isActive && 'border-l-4 border-emerald-500 bg-emerald-50',
                isTarget && !v.isActive && 'border-l-4 border-indigo-500 bg-indigo-50',
                isBase && !v.isActive && !isTarget && 'border-l-4 border-amber-500 bg-amber-50',
              )}
              onClick={(e) => onSelect(v.versionNumber, e.shiftKey ? 'base' : 'target')}
            >
              <div className="flex items-start gap-2">
                <span
                  className={cn(
                    'mt-0.5 font-mono text-sm font-semibold',
                    v.isActive ? 'text-emerald-700' : 'text-slate-700',
                  )}
                >
                  v{v.versionNumber}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm font-medium text-slate-900">{v.message}</div>
                  <div className="mt-0.5 text-xs text-slate-500">
                    {new Date(v.createdAt).toLocaleString('fr-FR')} · {v.author}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {v.isActive && <Badge variant="success">ACTIVE</Badge>}
                    {isTarget && !v.isActive && <Badge variant="default">cible</Badge>}
                    {isBase && <Badge variant="warning">base</Badge>}
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
