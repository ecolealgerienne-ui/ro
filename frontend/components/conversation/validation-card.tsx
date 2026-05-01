'use client';

import { Button } from '@/components/ui/button';

interface ValidationCardProps {
  title: string;
  body: React.ReactNode;
  /** Compteur d'OF impactés à afficher dans le badge. Optionnel. */
  ofImpactes?: number;
  onConfirm: () => void;
  onCancel: () => void;
  onSeeDetail?: () => void;
}

/**
 * Carte de validation systématique — principe directeur de l'UX :
 * "le chef d'atelier garde toujours le dernier mot" (specs V3 §6).
 *
 * S'affiche après chaque proposition de modification par l'assistant.
 * Aucune action n'est appliquée sans le clic Appliquer explicite.
 */
export function ValidationCard({
  title,
  body,
  ofImpactes,
  onConfirm,
  onCancel,
  onSeeDetail,
}: ValidationCardProps) {
  return (
    <div className="my-3 rounded-lg border-2 border-amber-300 bg-amber-50 p-4">
      <div className="flex items-start gap-3">
        <div className="text-lg text-amber-600">⚠</div>
        <div className="flex-1">
          <div className="mb-1 font-semibold text-amber-900">{title}</div>
          <div className="mb-3 text-sm text-amber-900/80">{body}</div>
          {ofImpactes !== undefined && (
            <div className="mb-3 text-xs text-amber-800">
              <strong>{ofImpactes}</strong> OF impacté{ofImpactes > 1 ? 's' : ''} — voir colonne
              droite pour le détail.
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={onConfirm}
              className="bg-emerald-600 text-white hover:bg-emerald-700"
            >
              ✓ Appliquer
            </Button>
            <Button size="sm" variant="outline" onClick={onCancel}>
              ✗ Annuler
            </Button>
            {onSeeDetail && (
              <Button size="sm" variant="ghost" onClick={onSeeDetail}>
                Voir le détail complet
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
