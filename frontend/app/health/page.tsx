'use client';

import { useQuery } from '@tanstack/react-query';
import { api, API_BASE_URL } from '@/lib/api/client';
import type { HealthStatus } from '@/lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function HealthPage() {
  const q = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthStatus>('/health'),
    refetchInterval: 5_000,
  });

  return (
    <main className="container mx-auto max-w-2xl py-12">
      <h1 className="mb-6 text-2xl font-semibold">Health backend</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Statut</CardTitle>
          <CardDescription>{API_BASE_URL}/health · refresh toutes les 5 s</CardDescription>
        </CardHeader>
        <CardContent>
          {q.isLoading && <div className="text-slate-500">Chargement…</div>}
          {q.isError && (
            <Badge variant="destructive">
              Erreur : {q.error instanceof Error ? q.error.message : 'inconnue'}
            </Badge>
          )}
          {q.data && (
            <dl className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <dt className="w-32 text-slate-500">status</dt>
                <dd>
                  <Badge variant={q.data.status === 'ok' ? 'success' : 'warning'}>
                    {q.data.status}
                  </Badge>
                </dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="w-32 text-slate-500">database</dt>
                <dd>
                  <Badge variant={q.data.database === 'up' ? 'success' : 'destructive'}>
                    {q.data.database}
                  </Badge>
                </dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="w-32 text-slate-500">uptime</dt>
                <dd>{q.data.uptime_s}s</dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="w-32 text-slate-500">version</dt>
                <dd className="font-mono">{q.data.version}</dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="w-32 text-slate-500">timestamp</dt>
                <dd className="text-xs text-slate-500">{q.data.timestamp}</dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
