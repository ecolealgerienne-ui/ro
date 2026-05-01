'use client';

import type { Machine } from '@/lib/api/types';
import type { GanttFilters } from './types';

interface GanttFiltersBarProps {
  filters: GanttFilters;
  onChange: (filters: GanttFilters) => void;
  clients: string[];
  machines: Machine[];
  freezeEnabled: boolean;
  onFreezeToggle: (enabled: boolean) => void;
}

export function GanttFiltersBar({
  filters,
  onChange,
  clients,
  machines,
  freezeEnabled,
  onFreezeToggle,
}: GanttFiltersBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-white p-4">
      <div className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-wider text-slate-500">Filtres :</span>
        <select
          value={filters.clientName ?? ''}
          onChange={(e) => onChange({ ...filters, clientName: e.target.value || null })}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
        >
          <option value="">Tous clients</option>
          {clients.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={filters.tier ?? ''}
          onChange={(e) =>
            onChange({
              ...filters,
              tier: e.target.value ? (Number(e.target.value) as 1 | 2 | 3) : null,
            })
          }
          className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
        >
          <option value="">Tous tiers</option>
          <option value="1">Tier 1</option>
          <option value="2">Tier 2</option>
          <option value="3">Tier 3</option>
        </select>
        <select
          value={filters.machineIdInt ?? ''}
          onChange={(e) =>
            onChange({
              ...filters,
              machineIdInt: e.target.value === '' ? null : Number(e.target.value),
            })
          }
          className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
        >
          <option value="">Toutes machines</option>
          {machines.map((m) => (
            <option key={m.id} value={m.machineIdInt}>
              M{m.machineIdInt} · {m.name}
            </option>
          ))}
        </select>
      </div>
      <div className="ml-auto flex items-center gap-3 text-sm">
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="checkbox"
            checked={freezeEnabled}
            onChange={(e) => onFreezeToggle(e.target.checked)}
            className="rounded"
          />
          <span className="text-slate-700">Zone freeze</span>
        </label>
      </div>
    </div>
  );
}
