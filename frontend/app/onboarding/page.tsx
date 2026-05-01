'use client';

import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ProgressBar } from '@/components/onboarding/progress-bar';
import {
  CertificationsStep,
  ClientsStep,
  FamilyCountStep,
  IdentityStep,
  MachinesStep,
  PainPointStep,
  SetupStep,
  TeamStep,
} from '@/components/onboarding/steps';
import { activeSteps, type OnboardingData } from '@/components/onboarding/schema';
import { submitOnboarding } from '@/components/onboarding/submit';
import { WhyPanel } from '@/components/onboarding/why-panel';

const DEFAULT_DATA: OnboardingData = {
  workshop_certifications: [],
  shift_start: 360, // 6h
  shift_end: 1320, // 22h
  workdays: [1, 2, 3, 4, 5],
  machines: [{ name: '', type: 'Tour CN' }],
  clients: [{ name: '', tier: 2, certifications: [] }],
};

export default function OnboardingPage() {
  const router = useRouter();
  const [data, setData] = useState<OnboardingData>(DEFAULT_DATA);
  const [stepIdx, setStepIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const visibleSteps = useMemo(() => activeSteps(data), [data]);
  const step = visibleSteps[stepIdx];
  const isLast = stepIdx >= visibleSteps.length - 1;

  function patch(p: Partial<OnboardingData>) {
    setData((d) => ({ ...d, ...p }));
    setError(null);
  }

  function next() {
    const err = step.validate(data);
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    if (isLast) handleSubmit();
    else setStepIdx((i) => i + 1);
  }

  function prev() {
    setError(null);
    setStepIdx((i) => Math.max(0, i - 1));
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const workshopId = await submitOnboarding(data);
      router.push(`/workshops/${workshopId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la création');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded bg-indigo-600 font-bold text-white">
              P
            </div>
            <div>
              <div className="font-semibold text-slate-900">Configuration de votre atelier</div>
              <div className="text-xs text-slate-500">
                {visibleSteps.length} questions essentielles · environ 8 minutes
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => router.push('/')}
            className="text-sm text-slate-500 hover:text-slate-900"
          >
            Annuler
          </button>
        </div>
        <div className="mx-auto max-w-5xl px-6 pb-3">
          <ProgressBar
            current={stepIdx}
            total={visibleSteps.length}
            steps={visibleSteps.map((s) => ({ id: s.id, title: s.title }))}
          />
        </div>
      </header>

      <div className="mx-auto grid max-w-5xl gap-8 px-6 py-8 md:grid-cols-[1fr_320px]">
        <section className="space-y-6">
          <Card>
            <CardContent className="p-7">
              <div className="text-xs uppercase tracking-wider text-indigo-600 font-semibold">
                Étape {stepIdx + 1} / {visibleSteps.length}
              </div>
              <h1 className="mt-1 text-2xl font-semibold text-slate-900">{step.title}</h1>
              <p className="mt-2 text-sm text-slate-600">{step.description}</p>

              <div className="mt-6">{renderStep(step.id, data, patch)}</div>

              {error && (
                <div className="mt-4 rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {error}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              onClick={prev}
              disabled={stepIdx === 0 || submitting}
            >
              ← Précédent
            </Button>
            <span className="text-xs text-slate-500">
              Tu peux changer tes réponses depuis « Réglages » plus tard.
            </span>
            <Button onClick={next} disabled={submitting}>
              {submitting ? 'Création…' : isLast ? 'Créer l\'atelier →' : 'Suivant →'}
            </Button>
          </div>
        </section>

        <WhyPanel why={step.why} totalSteps={visibleSteps.length} />
      </div>

      <footer className="mx-auto max-w-5xl px-6 py-4 text-center text-xs text-slate-400">
        Configuration sauvegardée localement · tu peux fermer l&apos;onglet et reprendre plus tard.
      </footer>
    </main>
  );
}

function renderStep(
  id: string,
  data: OnboardingData,
  patch: (p: Partial<OnboardingData>) => void,
) {
  switch (id) {
    case 'identity':
      return <IdentityStep data={data} onChange={patch} />;
    case 'certifications':
      return <CertificationsStep data={data} onChange={patch} />;
    case 'team':
      return <TeamStep data={data} onChange={patch} />;
    case 'machines':
      return <MachinesStep data={data} onChange={patch} />;
    case 'clients':
      return <ClientsStep data={data} onChange={patch} />;
    case 'setup':
      return <SetupStep data={data} onChange={patch} />;
    case 'family_count':
      return <FamilyCountStep data={data} onChange={patch} />;
    case 'pain_point':
      return <PainPointStep data={data} onChange={patch} />;
    default:
      return <div>Étape inconnue : {id}</div>;
  }
}
