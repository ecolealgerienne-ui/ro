'use client';

import Link from 'next/link';
import { use, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AnomalyRow } from '@/components/preflight/anomaly-row';
import { usePreflightSession, useUpdateAnomaly } from '@/lib/api/hooks';
import type { Anomaly, AnomalyLevel } from '@/lib/api/types';
import { cn } from '@/lib/utils';

const LEVEL_TABS: Array<{
  level: AnomalyLevel;
  emoji: string;
  label: string;
  description: string;
}> = [
  {
    level: 'certain',
    emoji: '🔴',
    label: 'Niveau 1 — anomalies certaines',
    description: 'Bloquantes, doivent être corrigées avant le solve.',
  },
  {
    level: 'probable',
    emoji: '🟠',
    label: 'Niveau 2 — probables',
    description: 'À valider une par une (acceptable mais inhabituel).',
  },
  {
    level: 'surprising',
    emoji: '🔵',
    label: 'Niveau 3 — surprenantes',
    description: 'Ack only — valeurs possibles mais à signaler.',
  },
];

export default function PreflightSessionDetailPage({
  params,
}: {
  params: Promise<{ id: string; sessionId: string }>;
}) {
  const { id: workshopId, sessionId } = use(params);
  const sessionQuery = usePreflightSession(workshopId, sessionId);
  const updateAnomaly = useUpdateAnomaly(workshopId, sessionId);

  const [activeTab, setActiveTab] = useState<AnomalyLevel>('certain');

  const grouped = useMemo(() => {
    const empty: Record<AnomalyLevel, Anomaly[]> = {
      certain: [],
      probable: [],
      surprising: [],
    };
    if (!sessionQuery.data) return empty;
    for (const a of sessionQuery.data.anomalies) empty[a.level].push(a);
    return empty;
  }, [sessionQuery.data]);

  const counts = useMemo(
    () => ({
      certain: grouped.certain.length,
      probable: grouped.probable.length,
      surprising: grouped.surprising.length,
      pendingCertain: grouped.certain.filter((a) => a.status === 'pending').length,
    }),
    [grouped],
  );

  if (sessionQuery.isLoading) {
    return <div className="p-8 text-slate-500">Chargement…</div>;
  }
  if (!sessionQuery.data) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="p-6 text-rose-700">Session introuvable.</CardContent>
        </Card>
      </div>
    );
  }

  const session = sessionQuery.data;

  return (
    <div className="space-y-5 p-6">
      <header className="flex items-start justify-between">
        <div>
          <Link
            href={`/workshops/${workshopId}/preflight`}
            className="text-xs text-slate-500 hover:text-slate-700"
          >
            ← Tous les imports
          </Link>
          <h1 className="text-2xl font-semibold text-slate-900">{session.fileName}</h1>
          <p className="mt-1 text-sm text-slate-600">
            {new Date(session.importedAt).toLocaleString('fr-FR')} · {session.nRowsTotal} lignes ·
            <strong className="ml-1">{session.nRowsImported}</strong> importables ·{' '}
            {session.fileHash && (
              <span className="font-mono text-xs text-slate-400">
                sha256 {session.fileHash.slice(0, 12)}…
              </span>
            )}
          </p>
        </div>
        {counts.pendingCertain > 0 && (
          <Badge variant="destructive">
            {counts.pendingCertain} bloquante{counts.pendingCertain > 1 ? 's' : ''} restant
            {counts.pendingCertain > 1 ? 'es' : 'e'}
          </Badge>
        )}
      </header>

      <div className="flex gap-1 border-b border-slate-200">
        {LEVEL_TABS.map((tab) => {
          const active = activeTab === tab.level;
          const count = counts[tab.level];
          return (
            <button
              key={tab.level}
              type="button"
              onClick={() => setActiveTab(tab.level)}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-3 text-sm transition-colors',
                active
                  ? 'border-indigo-500 font-semibold text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-900',
              )}
            >
              <span>{tab.emoji}</span>
              <span>{tab.label}</span>
              <Badge
                variant={
                  count === 0
                    ? 'secondary'
                    : tab.level === 'certain'
                      ? 'destructive'
                      : tab.level === 'probable'
                        ? 'warning'
                        : 'secondary'
                }
              >
                {count}
              </Badge>
            </button>
          );
        })}
      </div>

      <Card>
        <CardHeader className="border-b py-3">
          <CardTitle className="text-sm text-slate-700">
            {LEVEL_TABS.find((t) => t.level === activeTab)?.description}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-5">
          {grouped[activeTab].length === 0 ? (
            <div className="py-6 text-center text-sm text-slate-500">
              Aucune anomalie à ce niveau.
            </div>
          ) : (
            grouped[activeTab].map((a) => (
              <AnomalyRow
                key={a.id}
                anomaly={a}
                isPending={updateAnomaly.isPending}
                onUpdate={(status, resolution) =>
                  updateAnomaly.mutate({ anomalyId: a.id, status, resolution })
                }
              />
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex items-center justify-between p-5">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'flex h-10 w-10 items-center justify-center rounded-full font-bold',
                counts.pendingCertain > 0
                  ? 'bg-rose-100 text-rose-700'
                  : 'bg-emerald-100 text-emerald-700',
              )}
            >
              {counts.pendingCertain > 0 ? counts.pendingCertain : '✓'}
            </div>
            <div>
              <div className="font-semibold text-slate-900">
                {counts.pendingCertain > 0
                  ? `${counts.pendingCertain} correction${counts.pendingCertain > 1 ? 's' : ''} obligatoire${counts.pendingCertain > 1 ? 's' : ''} avant solve`
                  : 'Toutes les anomalies bloquantes sont traitées'}
              </div>
              <div className="text-xs text-slate-500">
                Tu peux revenir aux anomalies non bloquantes plus tard depuis cette page.
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href={`/workshops/${workshopId}/preflight`}>← Tous les imports</Link>
            </Button>
            <Button
              asChild
              size="sm"
              disabled={counts.pendingCertain > 0}
              className={counts.pendingCertain > 0 ? 'pointer-events-none opacity-50' : ''}
            >
              <Link href={`/workshops/${workshopId}`}>Continuer →</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
