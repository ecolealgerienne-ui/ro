'use client';

import Link from 'next/link';
import { use } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { UploadZone } from '@/components/preflight/upload-zone';
import { usePreflightSessions } from '@/lib/api/hooks';

export default function PreflightListPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: workshopId } = use(params);
  const sessionsQuery = usePreflightSessions(workshopId);
  const sessions = sessionsQuery.data ?? [];

  return (
    <div className="space-y-6 p-6">
      <header>
        <div className="text-xs uppercase tracking-wider text-slate-500">Imports</div>
        <h1 className="text-2xl font-semibold text-slate-900">Imports CSV ERP</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload un export ERP, le pre-flight détecte les anomalies en 3 niveaux
          (certaines bloquantes / probables / surprenantes).
        </p>
      </header>

      <UploadZone workshopId={workshopId} />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between border-b py-3">
          <CardTitle className="text-base font-semibold">Imports récents</CardTitle>
          <span className="text-xs text-slate-500">{sessions.length} session(s)</span>
        </CardHeader>
        <CardContent className="p-0">
          {sessionsQuery.isLoading && (
            <div className="p-6 text-sm text-slate-500">Chargement…</div>
          )}
          {sessions.length === 0 && !sessionsQuery.isLoading && (
            <div className="p-6 text-sm text-slate-500">
              Aucun import pour l&apos;instant. Utilise la zone ci-dessus pour démarrer.
            </div>
          )}
          {sessions.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {sessions.map((s) => (
                <li key={s.id}>
                  <Link
                    href={`/workshops/${workshopId}/preflight/${s.id}`}
                    className="flex items-center justify-between p-4 hover:bg-slate-50"
                  >
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">📊</div>
                      <div>
                        <div className="font-medium text-slate-900">{s.fileName}</div>
                        <div className="mt-0.5 text-xs text-slate-500">
                          {new Date(s.importedAt).toLocaleString('fr-FR')} · {s.nRowsTotal} lignes
                          totales · <strong>{s.nRowsImported}</strong> importées
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {s._count.anomalies > 0 ? (
                        <Badge variant="warning">
                          {s._count.anomalies} anomalie{s._count.anomalies > 1 ? 's' : ''}
                        </Badge>
                      ) : (
                        <Badge variant="success">Clean</Badge>
                      )}
                      <span className="text-slate-400">→</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
