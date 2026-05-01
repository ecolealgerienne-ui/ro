'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type { WorkshopWithCount } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function HomePage() {
  const workshopsQuery = useQuery({
    queryKey: ['workshops'],
    queryFn: () => api.get<WorkshopWithCount[]>('/workshops'),
  });

  return (
    <main className="container mx-auto max-w-5xl py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold text-slate-900">ro — chef d&apos;atelier</h1>
        <p className="mt-2 text-slate-600">
          SaaS d&apos;ordonnancement IA pour la sous-traitance mécanique de précision.
        </p>
      </header>

      <section className="mb-10">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Vos ateliers</CardTitle>
            <CardDescription>Sélectionnez un atelier pour ouvrir son dashboard.</CardDescription>
          </CardHeader>
          <CardContent>
            {workshopsQuery.isLoading && <div className="text-slate-500">Chargement…</div>}
            {workshopsQuery.isError && (
              <div className="text-rose-700">
                Backend injoignable. Vérifie que `npm run start:dev` tourne dans `backend/`.
              </div>
            )}
            {workshopsQuery.data?.length === 0 && (
              <div className="text-slate-600">
                Aucun atelier configuré. Crée-en un via l&apos;API ou attends la Phase 5 J7
                (onboarding).
              </div>
            )}
            <ul className="divide-y">
              {workshopsQuery.data?.map((w) => (
                <li key={w.id} className="flex items-center justify-between py-3">
                  <div>
                    <div className="font-medium text-slate-900">{w.name}</div>
                    <div className="text-xs text-slate-500">
                      {w.city ?? '—'} · {w._count.machines} machines · {w._count.orders} OF ·
                      v{w._count.versions} versions
                    </div>
                  </div>
                  <Button asChild variant="default" size="sm">
                    <Link href={`/workshops/${w.id}`}>Ouvrir →</Link>
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Healthcheck backend</CardTitle>
          </CardHeader>
          <CardContent>
            <Link href="/health" className="text-indigo-700 underline-offset-4 hover:underline">
              /health → état backend + DB
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Mockups UX</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">
              Les mockups HTML statiques (Phase 5 prep) sont dans <code>../mockups/</code>.
            </p>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
