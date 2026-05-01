'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

/**
 * Banner V1 statique pour l'onboarding progressif (5.3).
 *
 * Apparaît si l'atelier a été créé entre 25 et 35 jours auparavant
 * (fenêtre approximative pour le mini-questionnaire à 4 semaines).
 *
 * V2 : déclencheurs dynamiques (ex: 5 solves consécutifs avec tier-stability
 * non calibré → questions sur la criticité ; 10 OFs sans family_id → questions
 * sur les familles), avec persistance des réponses backend-side.
 */
export function ProgressiveOnboardingBanner({
  workshopCreatedAt,
}: {
  workshopCreatedAt: string;
}) {
  const [dismissed, setDismissed] = useState(false);
  const ageMs = Date.now() - new Date(workshopCreatedAt).getTime();
  const ageDays = ageMs / (1000 * 60 * 60 * 24);
  const inWindow = ageDays >= 25 && ageDays <= 35;

  if (!inWindow || dismissed) return null;

  return (
    <Card className="border-emerald-200 bg-emerald-50">
      <CardContent className="flex items-start gap-4 p-5">
        <div className="text-2xl">📅</div>
        <div className="flex-1">
          <div className="font-semibold text-emerald-900">
            5 questions contextuelles pour affiner le solveur
          </div>
          <p className="mt-1 text-sm text-emerald-900/80">
            Ton atelier tourne depuis ~4 semaines, on a maintenant des données réelles pour
            t&apos;aider à répondre à des questions plus pointues : matrice setup-times,
            qualifications opérateurs détaillées, indisponibilités récurrentes…
          </p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" disabled title="Disponible V2 — placeholder visuel V1">
              Démarrer (5 min)
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setDismissed(true)}>
              Plus tard
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
