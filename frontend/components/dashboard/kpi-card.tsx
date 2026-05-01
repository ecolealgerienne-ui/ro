import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger';
}

const TONE_CLASS: Record<NonNullable<KpiCardProps['tone']>, string> = {
  default: 'text-slate-900',
  success: 'text-emerald-600',
  warning: 'text-amber-600',
  danger: 'text-rose-700',
};

export function KpiCard({ label, value, hint, tone = 'default' }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</div>
        <div className={cn('mt-2 text-2xl font-semibold', TONE_CLASS[tone])}>{value}</div>
        {hint && <div className="mt-2 text-xs text-slate-500">{hint}</div>}
      </CardContent>
    </Card>
  );
}
