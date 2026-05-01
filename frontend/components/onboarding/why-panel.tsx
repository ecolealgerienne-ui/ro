import { Card, CardContent } from '@/components/ui/card';

export function WhyPanel({ why, totalSteps }: { why: string; totalSteps: number }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-5">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-amber-500">💡</span>
            <h3 className="text-sm font-semibold text-slate-900">Pourquoi cette question ?</h3>
          </div>
          <p className="text-sm leading-relaxed text-slate-700">{why}</p>
        </CardContent>
      </Card>

      <Card className="border-emerald-200 bg-emerald-50">
        <CardContent className="p-5">
          <h3 className="mb-2 text-sm font-semibold text-emerald-900">📅 Onboarding progressif</h3>
          <p className="text-sm leading-relaxed text-emerald-900/80">
            Pas besoin de tout configurer le J0. Cet onboarding pose les{' '}
            <strong>{totalSteps} questions essentielles</strong>. Les questions plus pointues
            (matrice setup-times, qualifications opérateurs, indisponibilités récurrentes)
            seront posées <strong>au fil des 4-6 prochaines semaines</strong>, avec des données
            réelles pour t&apos;aider à répondre.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
