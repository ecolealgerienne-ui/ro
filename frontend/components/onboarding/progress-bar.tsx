import { cn } from '@/lib/utils';

interface ProgressBarProps {
  current: number;
  total: number;
  steps: { id: string; title: string }[];
}

export function ProgressBar({ current, total, steps }: ProgressBarProps) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
        <span>
          Étape <strong className="text-slate-900">{current + 1}</strong> sur{' '}
          <strong className="text-slate-900">{total}</strong>
        </span>
        <span>{Math.round(((current + 1) / total) * 100)} %</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full bg-indigo-600 transition-all"
          style={{ width: `${((current + 1) / total) * 100}%` }}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {steps.map((s, idx) => (
          <span
            key={s.id}
            className={cn(
              'h-2 w-2 rounded-full',
              idx < current && 'bg-emerald-500',
              idx === current && 'bg-indigo-600',
              idx > current && 'bg-slate-300',
            )}
            title={s.title}
          />
        ))}
      </div>
    </div>
  );
}
