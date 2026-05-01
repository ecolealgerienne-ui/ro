import { TIER_BG } from './types';

export function GanttLegend() {
  return (
    <div className="flex flex-wrap items-center gap-6 px-2 text-xs text-slate-600">
      <span className="flex items-center gap-1.5">
        <span
          className="h-3 w-3 rounded"
          style={{ background: TIER_BG[1] }}
          aria-hidden
        />
        Tier 1 — critique
      </span>
      <span className="flex items-center gap-1.5">
        <span
          className="h-3 w-3 rounded"
          style={{ background: TIER_BG[2] }}
          aria-hidden
        />
        Tier 2 — standard
      </span>
      <span className="flex items-center gap-1.5">
        <span
          className="h-3 w-3 rounded"
          style={{ background: TIER_BG[3] }}
          aria-hidden
        />
        Tier 3 — opportuniste
      </span>
      <span className="ml-4 flex items-center gap-1.5">
        <span className="h-3 w-3 rounded border-2 border-blue-400" aria-hidden />
        OF gelé (en cours)
      </span>
    </div>
  );
}
