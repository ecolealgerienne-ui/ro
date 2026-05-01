'use client';

import { Button } from '@/components/ui/button';
import {
  CERTIFICATIONS_OPTIONS,
  MACHINE_TYPES,
  WORKDAY_LABELS,
  type ClientEntry,
  type MachineEntry,
  type OnboardingData,
} from './schema';
import { cn } from '@/lib/utils';

interface StepProps {
  data: OnboardingData;
  onChange: (patch: Partial<OnboardingData>) => void;
}

const inputCls =
  'w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none';
const labelCls = 'mb-1 block text-sm font-medium text-slate-700';

export function IdentityStep({ data, onChange }: StepProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className={labelCls}>Nom de l&apos;atelier *</label>
        <input
          type="text"
          className={inputCls}
          value={data.workshop_name ?? ''}
          onChange={(e) => onChange({ workshop_name: e.target.value })}
          placeholder="Ex : Mécanique Précision SAS"
          autoFocus
        />
      </div>
      <div>
        <label className={labelCls}>Ville *</label>
        <input
          type="text"
          className={inputCls}
          value={data.workshop_city ?? ''}
          onChange={(e) => onChange({ workshop_city: e.target.value })}
          placeholder="Ex : Saint-Étienne"
        />
      </div>
    </div>
  );
}

export function CertificationsStep({ data, onChange }: StepProps) {
  const selected = new Set(data.workshop_certifications ?? []);
  function toggle(c: string) {
    const next = new Set(selected);
    if (next.has(c)) next.delete(c);
    else next.add(c);
    onChange({ workshop_certifications: Array.from(next) });
  }
  return (
    <div className="space-y-2">
      {CERTIFICATIONS_OPTIONS.map((c) => (
        <label
          key={c}
          className={cn(
            'flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors',
            selected.has(c)
              ? 'border-indigo-500 bg-indigo-50/40'
              : 'border-slate-200 hover:bg-slate-50',
          )}
        >
          <input
            type="checkbox"
            checked={selected.has(c)}
            onChange={() => toggle(c)}
            className="mt-1"
          />
          <span className="text-sm text-slate-900">{c}</span>
        </label>
      ))}
      <p className="pt-1 text-xs text-slate-500">
        Aucune certification spécifique ? Tu peux passer cette étape sans cocher.
      </p>
    </div>
  );
}

export function TeamStep({ data, onChange }: StepProps) {
  const workdays = new Set(data.workdays ?? []);
  function toggleDay(d: number) {
    const next = new Set(workdays);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    onChange({ workdays: Array.from(next).sort() });
  }
  return (
    <div className="space-y-4">
      <div>
        <label className={labelCls}>Nombre d&apos;opérateurs *</label>
        <input
          type="number"
          min={1}
          max={500}
          className={inputCls}
          value={data.n_operators ?? ''}
          onChange={(e) => onChange({ n_operators: e.target.value ? Number(e.target.value) : undefined })}
          placeholder="Ex : 5"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Heure de début *</label>
          <input
            type="time"
            className={inputCls}
            value={
              data.shift_start !== undefined ? minToHHmm(data.shift_start) : '06:00'
            }
            onChange={(e) => onChange({ shift_start: hhmmToMin(e.target.value) })}
          />
        </div>
        <div>
          <label className={labelCls}>Heure de fin *</label>
          <input
            type="time"
            className={inputCls}
            value={data.shift_end !== undefined ? minToHHmm(data.shift_end) : '22:00'}
            onChange={(e) => onChange({ shift_end: hhmmToMin(e.target.value) })}
          />
        </div>
      </div>
      <div>
        <label className={labelCls}>Jours travaillés *</label>
        <div className="flex flex-wrap gap-2">
          {WORKDAY_LABELS.map((label, idx) => {
            const day = idx + 1;
            return (
              <button
                key={day}
                type="button"
                onClick={() => toggleDay(day)}
                className={cn(
                  'rounded border px-3 py-1.5 text-sm transition-colors',
                  workdays.has(day)
                    ? 'border-indigo-500 bg-indigo-100 text-indigo-700'
                    : 'border-slate-300 hover:bg-slate-50',
                )}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function MachinesStep({ data, onChange }: StepProps) {
  const machines = data.machines ?? [];
  function update(idx: number, patch: Partial<MachineEntry>) {
    const next = [...machines];
    next[idx] = { ...next[idx], ...patch };
    onChange({ machines: next });
  }
  function add() {
    onChange({ machines: [...machines, { name: '', type: MACHINE_TYPES[0] }] });
  }
  function remove(idx: number) {
    onChange({ machines: machines.filter((_, i) => i !== idx) });
  }
  return (
    <div className="space-y-3">
      {machines.map((m, idx) => (
        <div key={idx} className="flex gap-2">
          <input
            type="text"
            className={inputCls}
            placeholder="Nom (ex: CN-1, FR-2…)"
            value={m.name}
            onChange={(e) => update(idx, { name: e.target.value })}
          />
          <select
            className={inputCls}
            value={m.type}
            onChange={(e) => update(idx, { type: e.target.value })}
          >
            {MACHINE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => remove(idx)}
            disabled={machines.length === 1}
            className="text-rose-700"
          >
            ✕
          </Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={add}>
        + Ajouter une machine
      </Button>
    </div>
  );
}

export function ClientsStep({ data, onChange }: StepProps) {
  const clients = data.clients ?? [];
  function update(idx: number, patch: Partial<ClientEntry>) {
    const next = [...clients];
    next[idx] = { ...next[idx], ...patch };
    onChange({ clients: next });
  }
  function add() {
    onChange({
      clients: [...clients, { name: '', tier: 2, certifications: [] }],
    });
  }
  function remove(idx: number) {
    onChange({ clients: clients.filter((_, i) => i !== idx) });
  }
  return (
    <div className="space-y-3">
      {clients.map((c, idx) => (
        <div key={idx} className="flex gap-2">
          <input
            type="text"
            className={inputCls}
            placeholder="Nom client (ex: Safran, Stellantis…)"
            value={c.name}
            onChange={(e) => update(idx, { name: e.target.value })}
          />
          <select
            className={cn(inputCls, 'max-w-[150px]')}
            value={c.tier}
            onChange={(e) => update(idx, { tier: Number(e.target.value) as 1 | 2 | 3 })}
          >
            <option value={1}>Tier 1 (critique)</option>
            <option value={2}>Tier 2 (standard)</option>
            <option value={3}>Tier 3 (opportuniste)</option>
          </select>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => remove(idx)}
            disabled={clients.length === 1}
            className="text-rose-700"
          >
            ✕
          </Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={add}>
        + Ajouter un donneur d&apos;ordre
      </Button>
      <p className="pt-1 text-xs text-slate-500">
        Tu pourras en ajouter plus tard. V1 : ne liste que les 3-5 plus gros pour calibrer le solveur.
      </p>
    </div>
  );
}

export function SetupStep({ data, onChange }: StepProps) {
  const options = [
    {
      v: 'yes',
      label: 'Oui, c\'est un sujet majeur',
      hint: 'On gagne 10-30% de capacité en groupant. Le système t\'aidera avec le clustering automatique.',
      branch: '↓ Cette réponse débloque 1 question supplémentaire (familles).',
    },
    {
      v: 'partial',
      label: 'Un peu, mais pas critique',
      hint: 'Quelques minutes de réglage entre pièces, sans impact significatif.',
      branch: null,
    },
    {
      v: 'no',
      label: 'Non, les réglages sont quasi nuls',
      hint: 'Soit même pièce en série, soit changements rapides (SMED).',
      branch: null,
    },
    {
      v: 'dontknow',
      label: 'Je ne sais pas — passe la question',
      hint: 'On reposera la question dans 4 semaines avec des données réelles.',
      branch: null,
    },
  ] as const;
  return (
    <div className="space-y-3">
      {options.map((o) => (
        <label
          key={o.v}
          className={cn(
            'block cursor-pointer rounded-lg border p-4 transition-colors',
            data.setup_dependent === o.v
              ? 'border-indigo-500 bg-indigo-50/40'
              : 'border-slate-200 hover:bg-slate-50',
          )}
        >
          <div className="flex items-start gap-3">
            <input
              type="radio"
              name="setup"
              checked={data.setup_dependent === o.v}
              onChange={() => onChange({ setup_dependent: o.v })}
              className="mt-1"
            />
            <div className="flex-1">
              <div className="font-semibold text-slate-900">{o.label}</div>
              <div className="mt-0.5 text-sm text-slate-600">{o.hint}</div>
              {o.branch && (
                <div className="mt-2 inline-flex items-center gap-1 rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-700">
                  {o.branch}
                </div>
              )}
            </div>
          </div>
        </label>
      ))}
    </div>
  );
}

export function FamilyCountStep({ data, onChange }: StepProps) {
  return (
    <div className="space-y-3">
      <div>
        <label className={labelCls}>Estimation du nombre de familles</label>
        <input
          type="number"
          min={1}
          max={50}
          className={inputCls}
          value={data.family_count ?? ''}
          onChange={(e) =>
            onChange({ family_count: e.target.value ? Number(e.target.value) : undefined })
          }
          placeholder="Ex : 8"
        />
      </div>
      <p className="text-xs text-slate-500">
        Le clustering automatique (Phase 1.7) déduira les familles à partir de tes nomenclatures
        réelles. Cette estimation sert juste à dimensionner le module au démarrage.
      </p>
    </div>
  );
}

export function PainPointStep({ data, onChange }: StepProps) {
  return (
    <div className="space-y-3">
      <textarea
        rows={4}
        className={cn(inputCls, 'resize-none')}
        value={data.main_pain_point ?? ''}
        onChange={(e) => onChange({ main_pain_point: e.target.value })}
        placeholder="Ex : « Mes replans matin sont trop longs », « Je rate trop souvent les deadlines Safran », « Mes opérateurs sont sous-utilisés »…"
      />
      <p className="text-xs text-slate-500">Optionnel mais utile : on s&apos;en sert pour calibrer les priorités et cibler le suivi.</p>
    </div>
  );
}

// ---------- helpers ----------

function minToHHmm(min: number): string {
  const h = Math.floor(min / 60).toString().padStart(2, '0');
  const m = (min % 60).toString().padStart(2, '0');
  return `${h}:${m}`;
}

function hhmmToMin(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number);
  return h * 60 + m;
}
