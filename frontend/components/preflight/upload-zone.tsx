'use client';

import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useUploadPreflight } from '@/lib/api/hooks';
import { useRouter } from 'next/navigation';

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 Mio (aligné avec backend FileInterceptor)

export function UploadZone({ workshopId }: { workshopId: string }) {
  const router = useRouter();
  const upload = useUploadPreflight(workshopId);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFile(file: File | null) {
    setError(null);
    if (!file) return;
    if (file.size > MAX_FILE_SIZE) {
      setError(`Fichier trop volumineux : ${(file.size / 1024 / 1024).toFixed(1)} Mio (max 5 Mio).`);
      return;
    }
    if (!/\.(csv|tsv|txt)$/i.test(file.name)) {
      setError(`Format non supporté : ${file.name}. Utilise un CSV/TSV.`);
      return;
    }
    upload.mutate(file, {
      onSuccess: (session) => {
        router.push(`/workshops/${workshopId}/preflight/${session.id}`);
      },
      onError: (e) => {
        setError(e instanceof Error ? e.message : 'Erreur upload');
      },
    });
  }

  return (
    <Card>
      <CardContent
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFile(e.dataTransfer.files?.[0] ?? null);
        }}
        className={`cursor-pointer space-y-3 border-2 border-dashed p-10 text-center transition-colors ${
          dragOver ? 'border-indigo-500 bg-indigo-50/50' : 'border-slate-300 hover:border-indigo-300'
        }`}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.tsv,text/csv,text/plain"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        />
        <div className="text-4xl">📥</div>
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            Glisse un CSV ici, ou clique pour choisir
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Format : CSV/TSV · jusqu&apos;à 5 Mio · UTF-8 ou auto-détecté
          </p>
        </div>
        {upload.isPending && (
          <div className="text-sm text-indigo-600">Analyse en cours…</div>
        )}
        {error && (
          <div className="rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            inputRef.current?.click();
          }}
          disabled={upload.isPending}
        >
          Parcourir…
        </Button>
      </CardContent>
    </Card>
  );
}
