import type { Machine, OrderListItem, ScheduleAssignment } from '@/lib/api/types';

/** Vue enrichie d'une op : assignment + meta du job/order parent. */
export interface OpView {
  jobIdInt: number;
  sequenceIdx: number;
  machineIdInt: number;
  start: number;
  end: number;
  durationMin: number;
  // Meta enrichies
  orderRef: string;
  partRef: string;
  clientName: string;
  clientTier: 1 | 2 | 3;
  isFrozen: boolean; // start <= freeze horizon
}

export interface GanttFilters {
  clientName: string | null;
  tier: 1 | 2 | 3 | null;
  machineIdInt: number | null;
}

export const DEFAULT_FILTERS: GanttFilters = {
  clientName: null,
  tier: null,
  machineIdInt: null,
};

/**
 * Construit la liste des OpViews à partir du Schedule + machines + orders.
 * Joint les assignments (entiers) avec les meta-données (UUID).
 */
export function buildOpViews(
  assignments: ScheduleAssignment[],
  orders: OrderListItem[],
  freezeHorizon: number,
): OpView[] {
  // Index orders par jobIdInt
  const orderByJobIdInt = new Map<number, OrderListItem>();
  for (const o of orders) {
    if (o.job?.jobIdInt != null) orderByJobIdInt.set(o.job.jobIdInt, o);
  }

  return assignments.map((a) => {
    const order = orderByJobIdInt.get(a.job_id);
    return {
      jobIdInt: a.job_id,
      sequenceIdx: a.sequence_idx,
      machineIdInt: a.machine_id,
      start: a.start,
      end: a.end,
      durationMin: a.end - a.start,
      orderRef: order?.orderRef ?? `job-${a.job_id}`,
      partRef: order?.partRef ?? '—',
      clientName: order?.client.name ?? '—',
      clientTier: (order?.client.tier as 1 | 2 | 3) ?? 2,
      isFrozen: a.start < freezeHorizon,
    };
  });
}

export function applyFilters(ops: OpView[], filters: GanttFilters): OpView[] {
  return ops.filter((op) => {
    if (filters.clientName && op.clientName !== filters.clientName) return false;
    if (filters.tier && op.clientTier !== filters.tier) return false;
    if (filters.machineIdInt != null && op.machineIdInt !== filters.machineIdInt) return false;
    return true;
  });
}

export const TIER_BG: Record<1 | 2 | 3, string> = {
  1: '#7f1d1d',
  2: '#c2410c',
  3: '#475569',
};

/** Liste unique des clients depuis les ops. */
export function uniqueClients(ops: OpView[]): string[] {
  return Array.from(new Set(ops.map((o) => o.clientName))).sort();
}
