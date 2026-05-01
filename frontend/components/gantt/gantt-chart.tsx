'use client';

import type { Machine } from '@/lib/api/types';
import type { OpView } from './types';
import { TIER_BG } from './types';
import { cn } from '@/lib/utils';

interface GanttChartProps {
  machines: Machine[];
  ops: OpView[];
  makespan: number;
  freezeHorizon: number;
  onOpClick?: (op: OpView) => void;
  selectedOpKey?: string;
}

const PX_PER_MIN = 1.2; // 1 min = 1.2 px → 60 min = 72 px (lisible)
const ROW_HEIGHT = 48;
const LABEL_WIDTH = 160;
const HEADER_HEIGHT = 32;

const opKey = (op: OpView) => `${op.jobIdInt}-${op.sequenceIdx}`;

export function GanttChart({
  machines,
  ops,
  makespan,
  freezeHorizon,
  onOpClick,
  selectedOpKey,
}: GanttChartProps) {
  // Largeur min pour un Gantt lisible : 60 min = 1h
  const totalMin = Math.max(makespan, 60);
  const ganttWidth = totalMin * PX_PER_MIN;
  const totalWidth = LABEL_WIDTH + ganttWidth;

  // Header : ticks toutes les 60 min
  const tickInterval = totalMin > 480 ? 120 : 60; // 2h si makespan > 8h
  const ticks: number[] = [];
  for (let t = 0; t <= totalMin; t += tickInterval) ticks.push(t);

  // Group ops par machineIdInt pour rendu rapide
  const opsByMachine = new Map<number, OpView[]>();
  for (const m of machines) opsByMachine.set(m.machineIdInt, []);
  for (const op of ops) {
    if (!opsByMachine.has(op.machineIdInt)) opsByMachine.set(op.machineIdInt, []);
    opsByMachine.get(op.machineIdInt)!.push(op);
  }

  return (
    <div className="overflow-x-auto">
      <div style={{ width: totalWidth }} className="relative">
        {/* Header ticks */}
        <div
          className="flex border-b-2 border-slate-300 bg-slate-50"
          style={{ height: HEADER_HEIGHT }}
        >
          <div style={{ width: LABEL_WIDTH }} className="border-r border-slate-300" />
          <div className="relative flex-1">
            {ticks.map((t) => (
              <div
                key={t}
                className="absolute top-0 h-full border-l border-slate-200 px-1.5 text-[11px] text-slate-500"
                style={{ left: t * PX_PER_MIN }}
              >
                {fmtMin(t)}
              </div>
            ))}
          </div>
        </div>

        {/* Lignes machines */}
        <div className="relative">
          {/* Zone freeze (overlay) */}
          {freezeHorizon > 0 && (
            <div
              className="pointer-events-none absolute z-10 border-r-2 border-dashed border-blue-500"
              style={{
                left: LABEL_WIDTH,
                top: 0,
                width: freezeHorizon * PX_PER_MIN,
                height: machines.length * ROW_HEIGHT,
                background: 'rgba(96,165,250,0.08)',
              }}
            >
              <div className="border-b border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                Zone freeze ({fmtMin(freezeHorizon)})
              </div>
            </div>
          )}

          {machines.map((m) => {
            const machineOps = opsByMachine.get(m.machineIdInt) ?? [];
            return (
              <div
                key={m.id}
                className="flex border-b border-slate-100 hover:bg-slate-50/40"
                style={{ height: ROW_HEIGHT }}
              >
                <div
                  style={{ width: LABEL_WIDTH }}
                  className="flex flex-col justify-center border-r border-slate-200 px-3 py-2"
                >
                  <div className="font-mono text-xs text-slate-500">
                    M{m.machineIdInt} · {m.type ?? ''}
                  </div>
                  <div className="truncate text-sm text-slate-800">{m.name}</div>
                </div>
                <div className="relative flex-1">
                  {machineOps.map((op) => {
                    const left = op.start * PX_PER_MIN;
                    const width = (op.end - op.start) * PX_PER_MIN;
                    const isSelected = selectedOpKey === opKey(op);
                    return (
                      <button
                        key={`${op.jobIdInt}-${op.sequenceIdx}`}
                        type="button"
                        onClick={() => onOpClick?.(op)}
                        className={cn(
                          'absolute z-20 flex flex-col justify-center overflow-hidden rounded px-2 py-1 text-left text-[11px] font-medium text-white transition-all',
                          'hover:-translate-y-px hover:shadow-md',
                          op.isFrozen && 'ring-2 ring-blue-400 ring-offset-1',
                          isSelected && 'ring-2 ring-amber-400 ring-offset-2',
                        )}
                        style={{
                          left,
                          width: Math.max(width, 2),
                          top: 8,
                          height: ROW_HEIGHT - 16,
                          background: TIER_BG[op.clientTier],
                        }}
                        title={`${op.orderRef} · ${op.clientName} · T${op.clientTier} · ${fmtMin(op.start)}–${fmtMin(op.end)}`}
                      >
                        <div className="truncate font-mono text-[10px] opacity-90">
                          {op.orderRef}
                        </div>
                        <div className="truncate">{op.clientName}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function fmtMin(min: number): string {
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (m === 0) return `${h}h`;
  return `${h}h${m.toString().padStart(2, '0')}`;
}
