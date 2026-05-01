'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  Anomaly,
  AnomalyStatus,
  OrderListItem,
  PreflightSessionDetail,
  PreflightSessionListItem,
  Schedule,
  SolveJob,
  VersionListItem,
  WorkshopDetail,
  WorkshopWithCount,
} from './types';
import { API_BASE_URL } from './client';

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

// ---------- Preflight sessions ----------

export const usePreflightSessions = (workshopId: string | undefined) =>
  useQuery({
    queryKey: ['workshops', workshopId, 'preflight-sessions'],
    queryFn: () =>
      api.get<PreflightSessionListItem[]>(`/workshops/${workshopId}/preflight-sessions`),
    enabled: !!workshopId,
  });

export const usePreflightSession = (
  workshopId: string | undefined,
  sessionId: string | undefined,
) =>
  useQuery({
    queryKey: ['workshops', workshopId, 'preflight-sessions', sessionId],
    queryFn: () =>
      api.get<PreflightSessionDetail>(
        `/workshops/${workshopId}/preflight-sessions/${sessionId}`,
      ),
    enabled: !!workshopId && !!sessionId,
  });

/**
 * Upload multipart d'un CSV. fetch direct (pas via api.post car JSON) :
 * on construit un FormData explicite.
 */
export const useUploadPreflight = (workshopId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(
        `${API_BASE_URL}/workshops/${workshopId}/preflight-sessions`,
        { method: 'POST', body: form },
      );
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Upload failed: ${res.status} ${text.slice(0, 200)}`);
      }
      return (await res.json()) as PreflightSessionDetail;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['workshops', workshopId, 'preflight-sessions'] });
    },
  });
};

export const useUpdateAnomaly = (workshopId: string, sessionId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      anomalyId,
      status,
      resolution,
    }: {
      anomalyId: string;
      status: AnomalyStatus;
      resolution?: string;
    }) =>
      api.patch<Anomaly>(
        `/workshops/${workshopId}/preflight-sessions/${sessionId}/anomalies/${anomalyId}`,
        { status, resolution },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ['workshops', workshopId, 'preflight-sessions', sessionId],
      });
    },
  });
};

// ---------- Version detail (avec snapshot) ----------

export interface VersionDetail extends VersionListItem {
  snapshot: unknown;
  workshopId: string;
  updatedAt?: string;
}

export const useVersionDetail = (
  workshopId: string | undefined,
  versionNumber: number | undefined,
) =>
  useQuery({
    queryKey: ['workshops', workshopId, 'versions', versionNumber],
    queryFn: () =>
      api.get<VersionDetail>(`/workshops/${workshopId}/versions/${versionNumber}`),
    enabled: !!workshopId && versionNumber !== undefined,
  });

export const useRollback = (workshopId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (versionNumber: number) =>
      api.post<VersionDetail>(`/workshops/${workshopId}/versions/${versionNumber}/rollback`),
    onSuccess: () => {
      // Toutes les caches dépendant des versions deviennent stale
      void qc.invalidateQueries({ queryKey: ['workshops', workshopId] });
    },
  });
};
