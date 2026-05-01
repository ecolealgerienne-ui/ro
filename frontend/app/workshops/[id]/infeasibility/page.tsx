'use client';

import Link from 'next/link';
import { use, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useSolveJobs, useTriggerSolve } from '@/lib/api/hooks';
import type { SolveJob } from '@/lib/api/types';
import { cn } from '@/lib/utils';

export default function InfeasibilityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: workshopId } = use(params);
  const solveJobsQuery = useSolveJobs(workshopId);
  const triggerSolve = useTriggerSolve(workshopId);

  const problematicJobs = useMemo(() => {
    return (solveJobsQuery.data ?? []).filter(
      (j) => j.status === 'failed' || isInfeasibleResult(j),
    );
  }, [solveJobsQuery.data]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedJob = useMemo(
    () => problematicJobs.find((j) => j.id === selectedId) ?? problematicJobs[0],
    [selectedId, problematicJobs],
  );

  return (
    <div className="space-y-5 p-6">
      <header>
        <div className="text-xs uppercase tracking-wider text-slate-500">Diagnostic</div>
        <h1 className="text-2xl font-semibold text-slate-900">Diagnostic d&apos;infaisabilité</h1>
        <p className="mt-1 text-sm text-slate-600">
          Analyse formelle (MIS) + actions correctives suggérées quand le solveur ne trouve pas de
          planning.
        </p>
      </header>

      {problematicJobs.length === 0 ? (
        <Card>
          <CardContent className="space-y-3 p-8 text-center">
            <div className="text-4xl">✓</div>
            <h2 className="text-lg font-semibold text-slate-900">
              Aucun planning en échec actuellement
            </h2>
            <p className="text-sm text-slate-600">
              Cette page liste les solves qui ont retourné INFEASIBLE ou FAILED. Tous tes derniers
              solves se sont bien passés.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link href={`/workshops/${workshopId}`}>← Retour au dashboard</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-[280px_1fr] gap-4">
          <Card className="overflow-hidden">
            <CardHeader className="border-b py-3">
              <CardTitle className="text-base font-semibold">
                Solves en échec ({problematicJobs.length})
              </CardTitle>
            </CardHeader>
            <ul className="divide-y divide-slate-100">
              {problematicJobs.map((j) => (
                <li
                  key={j.id}
                  className={cn(
                    'cursor-pointer p-3 hover:bg-slate-50',
                    selectedJob?.id === j.id && 'border-l-4 border-rose-500 bg-rose-50',
                  )}
                  onClick={() => setSelectedId(j.id)}
                >
                  <div className="font-mono text-xs text-slate-600">{j.id.slice(0, 8)}…</div>
                  <div className="mt-1 flex items-center gap-2">
                    <Badge variant="destructive">{j.status}</Badge>
                    <span className="text-xs text-slate-500">
                      {new Date(j.createdAt).toLocaleString('fr-FR')}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          {selectedJob && <DiagnosticPanel job={selectedJob} workshopId={workshopId} onRetry={() => triggerSolve.mutate(undefined)} />}
        </div>
      )}
    </div>
  );
}

function DiagnosticPanel({
  job,
  workshopId,
  onRetry,
}: {
  job: SolveJob;
  workshopId: string;
  onRetry: () => void;
}) {
  const result = job.result as ResultShape | null;
  const decision = result?.decision;
  const cb = result?.circuit_breaker;
  const misSummary = cb?.mis_summary ?? null;
  const causes = parseMisCauses(misSummary);

  return (
    <div className="space-y-4">
      <Card className="border-rose-300 bg-rose-50">
        <CardContent className="flex items-start gap-4 p-5">
          <div className="text-3xl">⚠</div>
          <div className="flex-1">
            <div className="text-lg font-semibold text-rose-900">
              {job.status === 'failed' ? 'Solve FAILED' : 'Planning INFEASIBLE'}
            </div>
            <div className="mt-1 text-sm text-rose-900/90">
              {job.errorMessage ??
                decision?.reasons?.[0] ??
                "Le solveur n'a pas trouvé de planning faisable dans le budget temps imparti."}
            </div>
            {job.startedAt && job.finishedAt && (
              <div className="mt-2 text-xs text-rose-800/80">
                Tentative {job.attempts}× · durée{' '}
                {Math.round(
                  (new Date(job.finishedAt).getTime() - new Date(job.startedAt).getTime()) / 1000,
                )}
                s
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {cb && (
        <Card>
          <CardHeader className="border-b py-3">
            <CardTitle className="text-base font-semibold">
              Ce que le système a fait avant de te déranger
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <ol className="space-y-2 text-sm text-slate-700">
              {cb.attempts.map((a, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <span
                    className={
                      a.status === 'INFEASIBLE'
                        ? 'mt-0.5 text-rose-600'
                        : 'mt-0.5 text-emerald-600'
                    }
                  >
                    {a.status === 'INFEASIBLE' ? '⨯' : '✓'}
                  </span>
                  <div>
                    Tentative {idx + 1} — budget {a.time_limit_s}s :{' '}
                    <span
                      className={
                        a.status === 'INFEASIBLE'
                          ? 'font-medium text-rose-700'
                          : 'text-slate-500'
                      }
                    >
                      {a.status}
                      {a.makespan ? ` (makespan ${a.makespan})` : ''}
                    </span>
                  </div>
                </li>
              ))}
              {cb.outcome === 'INFEASIBLE' && (
                <li className="flex items-start gap-3">
                  <span className="mt-0.5 text-emerald-600">✓</span>
                  <div>Extraction des causes par analyse formelle (MIS)</div>
                </li>
              )}
            </ol>
          </CardContent>
        </Card>
      )}

      {causes.length > 0 && (
        <div>
          <h2 className="mb-3 px-1 text-base font-semibold text-slate-900">
            Causes identifiées ({causes.length})
          </h2>
          <div className="space-y-3">
            {causes.map((cause, idx) => (
              <CauseCard key={idx} cause={cause} index={idx + 1} workshopId={workshopId} />
            ))}
          </div>
        </div>
      )}

      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="p-5">
          <div className="font-semibold text-amber-900">Alternative — mode dégradé</div>
          <p className="mt-1 text-sm text-amber-900/90">
            <strong>Ignorer Tier 1 strict</strong> : le solveur trouvera un planning faisable mais
            les OF Tier 1 (Safran, médical, aéro) ne seront plus prioritaires.
          </p>
          <div className="mt-3 rounded bg-amber-100/60 px-3 py-2 text-xs text-amber-800">
            <strong>Risque :</strong> Échéances Tier 1 exposées à un possible retard.
          </div>
          <Button onClick={onRetry} className="mt-3 bg-amber-700 hover:bg-amber-800">
            Lancer en mode dégradé
          </Button>
        </CardContent>
      </Card>

      <div className="rounded-lg border bg-slate-100 p-5 text-sm text-slate-700">
        <strong>Tu reprends la main.</strong> Le système ne décide rien à ta place. Choisis une
        action ci-dessus, ou demande une analyse plus profonde via la{' '}
        <Link
          href={`/workshops/${workshopId}/conversation`}
          className="font-medium text-indigo-700 underline"
        >
          conversation
        </Link>
        .
      </div>
    </div>
  );
}

interface ParsedCause {
  kind: string;
  identifier: string;
  description: string;
  action?: { kind: string; description: string };
}

const KIND_STYLE: Record<string, { label: string; icon: string; color: string }> = {
  MACHINE_UNAVAILABILITY: {
    label: 'Indisponibilité machine',
    icon: '🔧',
    color: 'bg-blue-100 text-blue-800',
  },
  JOB: { label: 'Ordre de fabrication', icon: '📦', color: 'bg-purple-100 text-purple-800' },
  SHARED_RESOURCE: {
    label: 'Ressource partagée',
    icon: '🔗',
    color: 'bg-teal-100 text-teal-800',
  },
};

function CauseCard({
  cause,
  index,
  workshopId,
}: {
  cause: ParsedCause;
  index: number;
  workshopId: string;
}) {
  const style = KIND_STYLE[cause.kind] ?? {
    label: cause.kind,
    icon: '⚠',
    color: 'bg-slate-100 text-slate-700',
  };

  return (
    <Card>
      <CardContent className="p-0">
        <div className="flex items-start gap-3 border-b border-slate-100 px-5 py-4">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-rose-100 text-sm font-semibold text-rose-700">
            {index}
          </div>
          <div className="flex-1">
            <div className="mb-1 flex items-center gap-2">
              <span
                className={cn(
                  'rounded px-2 py-0.5 text-xs font-medium',
                  style.color,
                )}
              >
                {style.icon} {style.label}
              </span>
              <span className="font-mono text-xs text-slate-500">{cause.identifier}</span>
            </div>
            <div className="text-sm text-slate-800">{cause.description}</div>
          </div>
        </div>
        {cause.action && (
          <div className="bg-slate-50 px-5 py-4">
            <div className="mb-2 text-xs uppercase tracking-wider text-slate-500">
              Action corrective suggérée
            </div>
            <div className="font-medium text-slate-900">{cause.action.description}</div>
            <div className="mt-3 flex gap-2">
              <Button asChild size="sm">
                <Link
                  href={`/workshops/${workshopId}/conversation?q=${encodeURIComponent(cause.action.description)}`}
                >
                  Discuter cette action →
                </Link>
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------- Helpers ----------

interface ResultShape {
  decision?: { kind: string; reasons?: string[] };
  circuit_breaker?: {
    outcome: string;
    attempts: { index: number; time_limit_s: number; status: string; makespan: number | null }[];
    mis_summary: string | null;
  };
}

function isInfeasibleResult(j: SolveJob): boolean {
  const r = j.result as ResultShape | null;
  if (!r) return false;
  return r.decision?.kind === 'REJECT' || r.circuit_breaker?.outcome === 'INFEASIBLE';
}

/**
 * Parse le `mis_summary` en text brut (généré par
 * `MISReport.to_summary()` côté Python) en une liste structurée.
 *
 * Format attendu :
 *   "INFEASIBLE — N élément(s) cause(s) identifié(s) :
 *     - [KIND] identifier : description
 *     ...
 *    Actions correctives suggérées :
 *     - description action 1
 *     - description action 2"
 */
function parseMisCauses(summary: string | null): ParsedCause[] {
  if (!summary) return [];
  const causes: ParsedCause[] = [];
  const elementRe = /^\s*-\s*\[(\w+)\]\s*([^:]+)\s*:\s*(.+)$/gm;
  let match: RegExpExecArray | null;
  while ((match = elementRe.exec(summary)) !== null) {
    causes.push({
      kind: match[1],
      identifier: match[2].trim(),
      description: match[3].trim(),
    });
  }
  // Best-effort : associer actions par ordre (1 action par cause si même nombre)
  const actionsRe = /Actions correctives suggerees :([\s\S]*?)(?:\nNotes :|$)/;
  const actionsBlock = summary.match(actionsRe)?.[1];
  if (actionsBlock) {
    const actionRe = /^\s*-\s*(.+)$/gm;
    const actions: string[] = [];
    while ((match = actionRe.exec(actionsBlock)) !== null) {
      actions.push(match[1].trim());
    }
    actions.forEach((desc, i) => {
      if (causes[i]) {
        causes[i].action = { kind: 'corrective', description: desc };
      }
    });
  }
  return causes;
}
