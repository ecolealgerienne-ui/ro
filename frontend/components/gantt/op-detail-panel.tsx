'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { OpView } from './types';

interface OpDetailPanelProps {
  op: OpView;
  onClose: () => void;
}

const TIER_BADGE: Record<1 | 2 | 3, 'tier1' | 'tier2' | 'tier3'> = {
  1: 'tier1',
  2: 'tier2',
  3: 'tier3',
};

const TIER_LABEL: Record<1 | 2 | 3, string> = {
  1: 'Tier 1 — critique',
  2: 'Tier 2 — standard',
  3: 'Tier 3 — opportuniste',
};

export function OpDetailPanel({ op, onClose }: OpDetailPanelProps) {
  return (
    <aside className="fixed right-0 top-0 z-30 h-full w-96 overflow-y-auto border-l border-slate-200 bg-white shadow-2xl">
      <div className="flex items-start justify-between border-b border-slate-200 p-5">
        <div>
          <div className="text-xs text-slate-500">
            t = {fmtMin(op.start)} → {fmtMin(op.end)} (durée {fmtMin(op.durationMin)})
          </div>
          <div className="mt-0.5 font-mono text-sm text-slate-600">{op.orderRef}</div>
          <h3 className="text-lg font-semibold text-slate-900">{op.clientName}</h3>
          <div className="text-sm text-slate-700">{op.partRef}</div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant={TIER_BADGE[op.clientTier]}>{TIER_LABEL[op.clientTier]}</Badge>
            {op.isFrozen && (
              <Badge variant="warning">En cours · gelé</Badge>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-700"
          aria-label="Fermer"
        >
          ✕
        </button>
      </div>

      <div className="space-y-4 p-5 text-sm">
        <div>
          <div className="mb-1 text-xs uppercase tracking-wider text-slate-500">Affectation</div>
          <div>
            Machine M<strong>{op.machineIdInt}</strong> · op{' '}
            <strong>#{op.sequenceIdx}</strong> du job J{op.jobIdInt}
          </div>
        </div>

        <div>
          <div className="mb-1 text-xs uppercase tracking-wider text-slate-500">
            Pourquoi ici ?
          </div>
          <div className="text-slate-700">
            {op.clientTier === 1
              ? 'Le solveur a placé cet OF en priorité (Tier 1) sur la première fenêtre disponible de la machine compatible.'
              : op.isFrozen
                ? 'Cette opération est gelée car elle a démarré avant la fenêtre de freeze.'
                : 'Placement issu de l’optimisation makespan + soft constraints actives.'}
          </div>
        </div>

        <div className="space-y-2 border-t border-slate-100 pt-3">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            disabled
            title="Disponible jalon J4"
          >
            ✋ Geler cet OF
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            disabled
            title="Disponible jalon J4"
          >
            📅 Forcer démarrage à une date précise
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            disabled
            title="Disponible jalon J4"
          >
            💬 Demander : « pourquoi pas plus tôt ? »
          </Button>
          <Button
            variant="destructive"
            size="sm"
            className="w-full justify-start"
            disabled
            title="Disponible jalon J4"
          >
            ⏸ Reporter à la semaine prochaine
          </Button>
          <p className="pt-2 text-[11px] italic text-slate-500">
            Actions disponibles en jalon J4 (conversation + validation systématique).
          </p>
        </div>
      </div>
    </aside>
  );
}

function fmtMin(min: number): string {
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (m === 0) return `${h}h`;
  return `${h}h${m.toString().padStart(2, '0')}`;
}
