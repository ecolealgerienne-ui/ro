'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  OrderListItem,
  Schedule,
  SolveJob,
  VersionListItem,
  WorkshopDetail,
  WorkshopWithCount,
} from './types';

// ---------- Workshops ----------

export const useWorkshops = () =>
  useQuery({
    queryKey: ['workshops'],
    queryFn: () => api.get<WorkshopWithCount[]>('/workshops'),
  });

export const useWorkshop = (workshopId: string | undefined) =>
  useQuery({
    queryKey: ['workshops', workshopId],
    queryFn: () => api.get<WorkshopDetail>(`/workshops/${workshopId}`),
    enabled: !!workshopId,
  });

// ---------- Orders ----------

export const useOrders = (workshopId: string | undefined) =>
  useQuery({
    queryKey: ['workshops', workshopId, 'orders'],
    queryFn: () => api.get<OrderListItem[]>(`/workshops/${workshopId}/orders`),
    enabled: !!workshopId,
  });

// ---------- Schedule ----------

export const useSchedule = (workshopId: string | undefined, versionId?: string) =>
  useQuery({
    queryKey: ['workshops', workshopId, 'schedule', versionId ?? 'active'],
    queryFn: () =>
      api.get<Schedule | null>(
        `/workshops/${workshopId}/schedule${versionId ? `?versionId=${versionId}` : ''}`,
      ),
    enabled: !!workshopId,
  });

// ---------- Versions ----------

export const useVersions = (workshopId: string | undefined) =>
  useQuery({
    queryKey: ['workshops', workshopId, 'versions'],
    queryFn: () => api.get<VersionListItem[]>(`/workshops/${workshopId}/versions`),
    enabled: !!workshopId,
  });

// ---------- Solve jobs ----------

export const useSolveJobs = (workshopId: string | undefined) =>
  useQuery({
    queryKey: ['workshops', workshopId, 'solve-jobs'],
    queryFn: () => api.get<SolveJob[]>(`/workshops/${workshopId}/solve-jobs`),
    enabled: !!workshopId,
    refetchInterval: (q) => {
      // Si un job pending ou running existe, on poll plus vite
      const data = q.state.data;
      if (Array.isArray(data) && data.some((j) => j.status === 'pending' || j.status === 'running')) {
        return 2_000;
      }
      return false;
    },
  });

/**
 * Lance un solve. Le worker Python le récupèrera dans les 2 s via DB-as-queue.
 * On invalide les caches solve-jobs + schedule pour rafraîchir l'UI.
 */
export const useTriggerSolve = (workshopId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config?: { time_budgets_s?: number[]; num_workers?: number }) =>
      api.post<SolveJob>(`/workshops/${workshopId}/solve-jobs`, { config: config ?? {} }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workshops', workshopId, 'solve-jobs'] });
      void qc.invalidateQueries({ queryKey: ['workshops', workshopId, 'schedule'] });
    },
  });
};
