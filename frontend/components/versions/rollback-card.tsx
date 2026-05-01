'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ValidationCard } from '@/components/conversation/validation-card';

interface RollbackCardProps {
  baseVersionNumber: number | null;
  baseIsActive: boolean;
  onConfirm: (versionNumber: number) => void;
  isPending?: boolean;
  error?: string | null;
}

/**
 * Carte rollback avec validation systématique. Si la version cible (slot
 * "base" dans le diff) est active, on désactive le bouton car le backend
 * renvoie 409.
 */
export function RollbackCard({
  baseVersionNumber,
  baseIsActive,
  onConfirm,
  isPending,
  error,
}: RollbackCardProps) {
  const [showValidation, setShowValidation] = useState(false);

  if (!baseVersionNumber) {
    return (
      <Card>
        <CardContent className="p-5 text-sm text-slate-500">
          Sélectionne une version <strong>base</strong> (Shift+click dans la timeline) pour
          activer le rollback.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-5">
        <h3 className="font-semibold text-slate-900">
          Restaurer la version v{baseVersionNumber} ?
        </h3>
        <p className="mt-1 text-sm text-slate-700">
          Le rollback ne supprime jamais l&apos;historique. Il crée une <strong>nouvelle</strong>{' '}
          version au sommet de la timeline avec le snapshot de v{baseVersionNumber}.
        </p>
        {baseIsActive && (
          <div className="mt-3 rounded bg-rose-50 px-3 py-2 text-xs text-rose-800">
            ⚠ v{baseVersionNumber} est déjà la version active. Choisis une autre version.
          </div>
        )}
        {error && (
          <div className="mt-3 rounded bg-rose-50 px-3 py-2 text-xs text-rose-800">{error}</div>
        )}
        {showValidation ? (
          <div className="mt-3">
            <ValidationCard
              title={`Confirmer le rollback vers v${baseVersionNumber}`}
              body={
                <>
                  Une nouvelle version sera créée au sommet de la timeline.{' '}
                  <strong>L&apos;historique reste intact.</strong>
                </>
              }
              onConfirm={() => {
                onConfirm(baseVersionNumber);
                setShowValidation(false);
              }}
              onCancel={() => setShowValidation(false)}
            />
          </div>
        ) : (
          <Button
            onClick={() => setShowValidation(true)}
            disabled={baseIsActive || isPending}
            className="mt-3"
            variant="default"
          >
            {isPending ? 'Rollback en cours…' : `Restaurer v${baseVersionNumber} →`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
