'use client';

import { use, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { GanttChart } from '@/components/gantt/gantt-chart';
import { GanttFiltersBar } from '@/components/gantt/gantt-filters';
import { GanttLegend } from '@/components/gantt/gantt-legend';
import { OpDetailPanel } from '@/components/gantt/op-detail-panel';
import {
  applyFilters,
  buildOpViews,
  DEFAULT_FILTERS,
  uniqueClients,
  type GanttFilters,
  type OpView,
} from '@/components/gantt/types';
import {
  useOrders,
  useSchedule,
  useSolveJobs,
  useTriggerSolve,
  useWorkshop,
} from '@/lib/api/hooks';

/** Horizon de freeze : 8h en minutes (zone glissante "ne replanifie pas"). */
const FREEZE_HORIZON_MIN = 8 * 60;

export default function GanttPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const workshopQuery = useWorkshop(id);
  const ordersQuery = useOrders(id);
  const scheduleQuery = useSchedule(id);
  const solveJobsQuery = useSolveJobs(id);
  const triggerSolve = useTriggerSolve(id);

  const [filters, setFilters] = useState<GanttFilters>(DEFAULT_FILTERS);
  const [freezeEnabled, setFreezeEnabled] = useState(true);
  const [selected, setSelected] = useState<OpView | null>(null);

  const machines = workshopQuery.data?.machines ?? [];
  const orders = ordersQuery.data ?? [];
  const schedule = scheduleQuery.data;

  const allOps = useMemo<OpView[]>(() => {
    if (!schedule) return [];
    return buildOpViews(
      schedule.assignments,
      orders,
      freezeEnabled ? FREEZE_HORIZON_MIN : 0,
    );
  }, [schedule, orders, freezeEnabled]);

  const filteredOps = useMemo(() => applyFilters(allOps, filters), [allOps, filters]);
  const clients = useMemo(() => uniqueClients(allOps), [allOps]);

  if (workshopQuery.isLoading || scheduleQuery.isLoading) {
    return <div className="p-8 text-slate-500">Chargement…</div>;
  }
  if (!workshopQuery.data) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="p-6 text-rose-700">
            Workshop introuvable.
          </CardContent>
        </Card>
      </div>
    );
  }

  const runningJob = solveJobsQuery.data?.find(
    (j) => j.status === 'pending' || j.status === 'running',
  );

  return (
    <div className="space-y-4 p-6">
      <header className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">Planning</div>
          <h1 className="text-2xl font-semibold text-slate-900">Gantt — semaine en cours</h1>
          {schedule && (
            <p className="mt-1 text-sm text-slate-600">
              version <span className="font-mono">v{schedule.versionNumber}</span> · makespan{' '}
              <strong>{fmtMakespan(schedule.makespanMin)}</strong> ·{' '}
              {schedule.assignments.length} affectations
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {runningJob && (
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-900">
              Solve en cours…
            </span>
          )}
          <Button
            size="sm"
            onClick={() => triggerSolve.mutate(undefined)}
            disabled={!!runningJob || triggerSolve.isPending}
          >
            {triggerSolve.isPending ? 'Lancement…' : 'Replanifier'}
          </Button>
        </div>
      </header>

      <GanttFiltersBar
        filters={filters}
        onChange={setFilters}
        clients={clients}
        machines={machines}
        freezeEnabled={freezeEnabled}
        onFreezeToggle={setFreezeEnabled}
      />

      <GanttLegend />

      {!schedule ? (
        <Card>
          <CardContent className="space-y-4 p-8 text-center">
            <div className="text-4xl">📅</div>
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Pas encore de planning solvé
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                Lance un solve depuis le bouton « Replanifier ». Le worker Python le récupèrera
                dans les 2 s, et le résultat s&apos;affichera ici dès qu&apos;il aura fini.
              </p>
            </div>
            <Button onClick={() => triggerSolve.mutate(undefined)} disabled={!!runningJob}>
              Lancer le premier solve →
            </Button>
            {orders.length === 0 && (
              <p className="text-xs text-amber-700">
                ⚠ Aucun OF dans ce workshop. Crée d&apos;abord des OFs via l&apos;API ou via
                l&apos;import CSV (J5).
              </p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <GanttChart
              machines={machines}
              ops={filteredOps}
              makespan={schedule.makespanMin}
              freezeHorizon={freezeEnabled ? FREEZE_HORIZON_MIN : 0}
              onOpClick={setSelected}
              selectedOpKey={
                selected ? `${selected.jobIdInt}-${selected.sequenceIdx}` : undefined
              }
            />
            <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-5 py-3 text-sm">
              <div className="flex items-center gap-6 text-slate-700">
                <span>
                  <strong>{filteredOps.length}</strong> /{' '}
                  <span className="text-slate-500">{allOps.length}</span> ops affichées
                </span>
                <span>
                  Makespan : <strong>{fmtMakespan(schedule.makespanMin)}</strong>
                </span>
                {schedule.versionIsActive && (
                  <span className="font-medium text-emerald-700">
                    ✓ Version active v{schedule.versionNumber}
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {selected && (
        <OpDetailPanel op={selected} workshopId={id} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}

function fmtMakespan(min: number): string {
  const days = Math.floor(min / (60 * 8));
  const remH = (min % (60 * 8)) / 60;
  if (days > 0) return `${days}j ${Math.round(remH)}h`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h${m.toString().padStart(2, '0')}`;
}
