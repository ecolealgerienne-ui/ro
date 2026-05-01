'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { Anomaly, AnomalyStatus } from '@/lib/api/types';
import { cn } from '@/lib/utils';

const STATUS_VARIANT: Record<AnomalyStatus, 'secondary' | 'success' | 'warning' | 'destructive'> = {
  pending: 'secondary',
  resolved: 'success',
  ignored: 'warning',
  excluded: 'destructive',
};

const STATUS_LABEL: Record<AnomalyStatus, string> = {
  pending: 'À traiter',
  resolved: 'Corrigé',
  ignored: 'Ignoré',
  excluded: 'Exclu',
};

interface AnomalyRowProps {
  anomaly: Anomaly;
  onUpdate: (status: AnomalyStatus, resolution?: string) => void;
  isPending?: boolean;
}

export function AnomalyRow({ anomaly, onUpdate, isPending }: AnomalyRowProps) {
  const [resolutionInput, setResolutionInput] = useState('');
  const [showResolve, setShowResolve] = useState(false);
  const isLocked = anomaly.status !== 'pending';

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-start justify-between p-4">
        <div className="flex-1">
          <div className="mb-1 flex items-center gap-2 text-xs">
            <span className="font-mono text-slate-600">ligne {anomaly.rowIndex + 1}</span>
            {anomaly.column && (
              <span className="font-mono text-slate-500">· col {anomaly.column}</span>
            )}
            <Badge variant="outline">{anomaly.code}</Badge>
            <Badge variant={STATUS_VARIANT[anomaly.status]}>
              {STATUS_LABEL[anomaly.status]}
            </Badge>
          </div>
          <div className="text-sm text-slate-800">{anomaly.suggestion ?? anomaly.code}</div>
          {anomaly.rawValue && (
            <div className="mt-1 font-mono text-xs">
              <span className="text-slate-500">valeur reçue :</span>{' '}
              <span className="rounded bg-rose-50 px-1.5 py-0.5 text-rose-800">
                {anomaly.rawValue}
              </span>
            </div>
          )}
          {anomaly.resolution && (
            <div className="mt-2 text-xs italic text-emerald-700">
              ↪ {anomaly.resolution}
            </div>
          )}
        </div>
        {!isLocked && (
          <div className="flex shrink-0 flex-col gap-2">
            <Button
              size="sm"
              className="bg-emerald-600 text-white hover:bg-emerald-700"
              onClick={() => setShowResolve((v) => !v)}
              disabled={isPending}
            >
              ✓ Résoudre
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onUpdate('ignored')}
              disabled={isPending}
            >
              Ignorer
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-rose-700"
              onClick={() => onUpdate('excluded', 'Ligne exclue de l\'import')}
              disabled={isPending}
            >
              Exclure
            </Button>
          </div>
        )}
      </div>
      {showResolve && !isLocked && (
        <div className="border-t border-slate-100 bg-slate-50 p-3">
          <input
            type="text"
            value={resolutionInput}
            onChange={(e) => setResolutionInput(e.target.value)}
            placeholder={`Ex : "Corrigé en 45 min" — résolution texte (auditable)`}
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
            autoFocus
          />
          <div className="mt-2 flex gap-2">
            <Button
              size="sm"
              className={cn('bg-emerald-600 text-white hover:bg-emerald-700')}
              onClick={() => {
                onUpdate('resolved', resolutionInput.trim() || 'Corrigé');
                setShowResolve(false);
                setResolutionInput('');
              }}
              disabled={isPending}
            >
              Confirmer la résolution
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowResolve(false)}>
              Annuler
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
