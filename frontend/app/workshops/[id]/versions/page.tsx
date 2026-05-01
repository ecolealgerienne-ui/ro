'use client';

import { use, useEffect, useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { DiffPanel } from '@/components/versions/diff-panel';
import { RollbackCard } from '@/components/versions/rollback-card';
import { VersionsTimeline } from '@/components/versions/versions-timeline';
import { useRollback, useVersionDetail, useVersions } from '@/lib/api/hooks';

export default function VersionsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: workshopId } = use(params);
  const versionsQuery = useVersions(workshopId);
  const versions = useMemo(() => versionsQuery.data ?? [], [versionsQuery.data]);

  const activeVersion = versions.find((v) => v.isActive);
  const previousActive = versions.find((v) => !v.isActive); // 1ère non active dans liste DESC

  const [baseVersionNumber, setBaseVersionNumber] = useState<number | null>(null);
  const [targetVersionNumber, setTargetVersionNumber] = useState<number | null>(null);

  // Sélection par défaut : target = active, base = précédente
  useEffect(() => {
    if (versions.length > 0 && targetVersionNumber === null) {
      setTargetVersionNumber(activeVersion?.versionNumber ?? versions[0].versionNumber);
    }
    if (versions.length > 1 && baseVersionNumber === null && previousActive) {
      setBaseVersionNumber(previousActive.versionNumber);
    }
  }, [versions, activeVersion, previousActive, baseVersionNumber, targetVersionNumber]);

  const baseDetail = useVersionDetail(workshopId, baseVersionNumber ?? undefined);
  const targetDetail = useVersionDetail(workshopId, targetVersionNumber ?? undefined);

  const rollback = useRollback(workshopId);
  const [rollbackError, setRollbackError] = useState<string | null>(null);

  function handleSelect(versionNumber: number, slot: 'base' | 'target') {
    if (slot === 'base') setBaseVersionNumber(versionNumber);
    else setTargetVersionNumber(versionNumber);
  }

  function handleRollback(versionNumber: number) {
    setRollbackError(null);
    rollback.mutate(versionNumber, {
      onError: (e) =>
        setRollbackError(e instanceof Error ? e.message : 'Erreur rollback'),
    });
  }

  if (versionsQuery.isLoading) {
    return <div className="p-8 text-slate-500">Chargement…</div>;
  }

  return (
    <div className="space-y-5 p-6">
      <header>
        <div className="text-xs uppercase tracking-wider text-slate-500">Historique</div>
        <h1 className="text-2xl font-semibold text-slate-900">Versions du workshop</h1>
        <p className="mt-1 text-sm text-slate-600">
          Chaque modification crée une nouvelle version avec un snapshot complet. Le rollback ne
          supprime jamais l&apos;historique — il crée une nouvelle version au sommet.
        </p>
      </header>

      {versions.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-slate-500">
            Aucune version pour ce workshop.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-[360px_1fr] gap-4">
          <VersionsTimeline
            versions={versions}
            baseVersionNumber={baseVersionNumber}
            targetVersionNumber={targetVersionNumber}
            onSelect={handleSelect}
          />

          <div className="space-y-4">
            <DiffPanel
              base={
                baseDetail.data
                  ? {
                      versionNumber: baseDetail.data.versionNumber,
                      snapshot: baseDetail.data.snapshot,
                    }
                  : null
              }
              target={
                targetDetail.data
                  ? {
                      versionNumber: targetDetail.data.versionNumber,
                      snapshot: targetDetail.data.snapshot,
                      isActive: targetDetail.data.isActive,
                    }
                  : null
              }
            />

            <RollbackCard
              baseVersionNumber={baseVersionNumber}
              baseIsActive={baseDetail.data?.isActive ?? false}
              onConfirm={handleRollback}
              isPending={rollback.isPending}
              error={rollbackError}
            />
          </div>
        </div>
      )}
    </div>
  );
}
