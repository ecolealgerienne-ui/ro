'use client';

import Link from 'next/link';
import { use } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertsList, type Alert } from '@/components/dashboard/alerts-list';
import { KpiCard } from '@/components/dashboard/kpi-card';
import { MiniGantt } from '@/components/dashboard/mini-gantt';
import { useOrders, useSolveJobs, useVersions, useWorkshop } from '@/lib/api/hooks';

export default function DashboardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const workshopQuery = useWorkshop(id);
  const ordersQuery = useOrders(id);
  const versionsQuery = useVersions(id);
  const solveJobsQuery = useSolveJobs(id);

  if (workshopQuery.isLoading) {
    return <div className="p-8 text-slate-500">Chargement…</div>;
  }
  if (workshopQuery.isError || !workshopQuery.data) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="p-6 text-rose-700">
            Workshop introuvable. Backend injoignable ou ID invalide.
          </CardContent>
        </Card>
      </div>
    );
  }

  const workshop = workshopQuery.data;
  const orders = ordersQuery.data ?? [];
  const machines = workshop.machines;
  const versions = versionsQuery.data ?? [];
  const solveJobs = solveJobsQuery.data ?? [];
  const activeVersion = versions.find((v) => v.isActive);
  const lastDoneJob = solveJobs.find((j) => j.status === 'done');
  const runningJob = solveJobs.find((j) => j.status === 'pending' || j.status === 'running');

  const tierCounts = orders.reduce(
    (acc, o) => {
      const t = (o.client.tier ?? 2) as 1 | 2 | 3;
      acc[t] = (acc[t] ?? 0) + 1;
      return acc;
    },
    {} as Record<1 | 2 | 3, number>,
  );

  // V1 — alertes statiques jusqu'à ce qu'on ait une vraie source de signaux
  // (pipeline de simulation + circuit breaker côté solveur).
  const alerts: Alert[] = [];
  if (runningJob) {
    alerts.push({
      id: 'solve-pending',
      severity: 'info',
      title: 'Solve en cours',
      detail: `Job ${runningJob.id.slice(0, 8)}… status=${runningJob.status}. Le worker Python travaille.`,
      action: 'Voir',
    });
  }
  if (lastDoneJob?.simulationVerdict === 'WARN') {
    alerts.push({
      id: 'sim-warn',
      severity: 'majeur',
      title: 'Simulation : verdict WARN',
      detail: 'Le dernier solve a déclenché des seuils opérationnels (fragmentation, micro-pauses).',
      action: 'Détail',
    });
  }
  if (orders.filter((o) => o.client.tier === 1).length > 0) {
    alerts.push({
      id: 'tier1-info',
      severity: 'info',
      title: `${orders.filter((o) => o.client.tier === 1).length} OF Tier 1 actif(s)`,
      detail: 'Les OF critiques (Safran, médical, aéro) sont prioritaires sur le scheduling.',
    });
  }

  return (
    <div className="space-y-6 p-8">
      <header className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">Vue d&apos;ensemble</div>
          <h1 className="text-2xl font-semibold text-slate-900">{workshop.name}</h1>
          <div className="mt-1 text-sm text-slate-500">
            {workshop.city ?? '—'} · {workshop.certifications.join(', ') || 'aucune certif'} ·
            {' '}
            {workshop.nOperators} opérateur{workshop.nOperators > 1 ? 's' : ''}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            Importer données
          </Button>
          <Button size="sm">Replanifier</Button>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard
          label="Statut planning"
          value={
            activeVersion ? (
              <span className="text-emerald-600">✓ v{activeVersion.versionNumber}</span>
            ) : (
              <span className="text-slate-500">—</span>
            )
          }
          hint={
            activeVersion ? (
              <>
                {new Date(activeVersion.createdAt).toLocaleString('fr-FR')} · {activeVersion.author}
              </>
            ) : (
              'Aucune version active'
            )
          }
          tone={activeVersion ? 'success' : 'default'}
        />
        <KpiCard
          label="OF planifiés"
          value={orders.length}
          hint={
            <>
              <span className="font-medium text-rose-700">{tierCounts[1] ?? 0} T1</span> ·
              <span className="ml-1 font-medium text-orange-700">{tierCounts[2] ?? 0} T2</span> ·
              <span className="ml-1 font-medium text-slate-500">{tierCounts[3] ?? 0} T3</span>
            </>
          }
        />
        <KpiCard
          label="Machines"
          value={machines.length}
          hint={`${workshop._count.versions} version${workshop._count.versions > 1 ? 's' : ''} historisée${workshop._count.versions > 1 ? 's' : ''}`}
        />
        <KpiCard
          label="Score de confiance"
          value={
            lastDoneJob?.confidenceScore != null ? (
              <span>{lastDoneJob.confidenceScore}/100</span>
            ) : (
              <span className="text-slate-400">—</span>
            )
          }
          hint={
            lastDoneJob ? (
              <>verdict simulation : <strong>{lastDoneJob.simulationVerdict ?? 'n/a'}</strong></>
            ) : (
              'Aucun solve done'
            )
          }
          tone={
            lastDoneJob?.confidenceScore && lastDoneJob.confidenceScore >= 80
              ? 'success'
              : lastDoneJob?.confidenceScore && lastDoneJob.confidenceScore >= 60
                ? 'warning'
                : 'default'
          }
        />
      </section>

      <AlertsList alerts={alerts} />

      <MiniGantt machines={machines} orders={orders} />

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Link
          href={`/workshops/${id}/conversation`}
          className="block rounded-lg border bg-white p-5 transition-all hover:border-indigo-300 hover:shadow-sm"
        >
          <div className="mb-2 text-2xl">💬</div>
          <div className="font-semibold text-slate-900">Demander une modification</div>
          <div className="mt-1 text-sm text-slate-600">
            « Priorité 1 sur Safran cette semaine »
          </div>
        </Link>
        <Link
          href={`/workshops/${id}/preflight`}
          className="block rounded-lg border bg-white p-5 transition-all hover:border-indigo-300 hover:shadow-sm"
        >
          <div className="mb-2 text-2xl">📥</div>
          <div className="font-semibold text-slate-900">Importer des OFs</div>
          <div className="mt-1 text-sm text-slate-600">
            CSV ERP → preflight 3 niveaux d&apos;anomalies
          </div>
        </Link>
        <Link
          href={`/workshops/${id}/versions`}
          className="block rounded-lg border bg-white p-5 transition-all hover:border-indigo-300 hover:shadow-sm"
        >
          <div className="mb-2 text-2xl">🕐</div>
          <div className="font-semibold text-slate-900">Historique &amp; rollback</div>
          <div className="mt-1 text-sm text-slate-600">Comparer 2 versions, restaurer si besoin</div>
        </Link>
      </section>
    </div>
  );
}
