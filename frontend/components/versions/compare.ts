/**
 * Helper pour comparer 2 snapshots de versions Workshop.
 *
 * V1 : compteurs simples (machines, clients, orders) + delta count.
 * V2 si besoin : diff structurel JSON profond avec listes des additions /
 * suppressions / modifications par OF.
 */

interface SnapshotShape {
  name?: string;
  city?: string | null;
  certifications?: string[];
  nOperators?: number;
  machines?: { id: string; name: string }[];
  clients?: { id: string; name: string; tier: number }[];
  orders?: { id: string; orderRef: string; client?: { tier?: number } }[];
}

export interface CompareMetric {
  label: string;
  before: string | number;
  after: string | number;
  delta: string | null;
  tone: 'good' | 'bad' | 'neutral';
}

export interface CompareResult {
  metrics: CompareMetric[];
  summary: string[];
}

export function compareSnapshots(
  before: unknown,
  after: unknown,
): CompareResult {
  const a = (before ?? {}) as SnapshotShape;
  const b = (after ?? {}) as SnapshotShape;

  const machinesA = a.machines?.length ?? 0;
  const machinesB = b.machines?.length ?? 0;
  const clientsA = a.clients?.length ?? 0;
  const clientsB = b.clients?.length ?? 0;
  const ordersA = a.orders?.length ?? 0;
  const ordersB = b.orders?.length ?? 0;

  const metrics: CompareMetric[] = [
    metric('Machines', machinesA, machinesB),
    metric('Clients', clientsA, clientsB),
    metric('OFs', ordersA, ordersB),
  ];

  // Tier breakdown OFs
  const tierA = countByTier(a.orders ?? []);
  const tierB = countByTier(b.orders ?? []);
  metrics.push(
    metric('OFs Tier 1', tierA[1], tierB[1]),
    metric('OFs Tier 2', tierA[2], tierB[2]),
    metric('OFs Tier 3', tierA[3], tierB[3]),
  );

  const summary: string[] = [];
  if (a.name !== b.name) summary.push(`Nom : "${a.name ?? '—'}" → "${b.name ?? '—'}"`);
  if (a.city !== b.city) summary.push(`Ville : "${a.city ?? '—'}" → "${b.city ?? '—'}"`);
  if ((a.nOperators ?? 0) !== (b.nOperators ?? 0)) {
    summary.push(`Opérateurs : ${a.nOperators ?? 0} → ${b.nOperators ?? 0}`);
  }
  const certsA = (a.certifications ?? []).join(', ');
  const certsB = (b.certifications ?? []).join(', ');
  if (certsA !== certsB) summary.push(`Certifications : "${certsA || '—'}" → "${certsB || '—'}"`);

  // Diff orders ajoutés / supprimés
  const refsA = new Set((a.orders ?? []).map((o) => o.orderRef));
  const refsB = new Set((b.orders ?? []).map((o) => o.orderRef));
  const added = Array.from(refsB).filter((r) => !refsA.has(r));
  const removed = Array.from(refsA).filter((r) => !refsB.has(r));
  if (added.length > 0) summary.push(`+ ${added.length} OF ajouté(s) : ${added.slice(0, 3).join(', ')}${added.length > 3 ? '…' : ''}`);
  if (removed.length > 0) summary.push(`− ${removed.length} OF supprimé(s) : ${removed.slice(0, 3).join(', ')}${removed.length > 3 ? '…' : ''}`);

  // Diff machines
  const mA = new Set((a.machines ?? []).map((m) => m.name));
  const mB = new Set((b.machines ?? []).map((m) => m.name));
  const mAdded = Array.from(mB).filter((n) => !mA.has(n));
  const mRemoved = Array.from(mA).filter((n) => !mB.has(n));
  if (mAdded.length > 0) summary.push(`+ ${mAdded.length} machine(s) ajoutée(s) : ${mAdded.join(', ')}`);
  if (mRemoved.length > 0) summary.push(`− ${mRemoved.length} machine(s) supprimée(s) : ${mRemoved.join(', ')}`);

  if (summary.length === 0) {
    summary.push('Aucun changement structurel détecté entre les 2 snapshots.');
  }
  return { metrics, summary };
}

function metric(label: string, before: number, after: number): CompareMetric {
  const diff = after - before;
  return {
    label,
    before,
    after,
    delta: diff === 0 ? null : diff > 0 ? `+${diff}` : `${diff}`,
    tone: diff === 0 ? 'neutral' : diff > 0 ? 'good' : 'bad',
  };
}

function countByTier(orders: { client?: { tier?: number } }[]): Record<1 | 2 | 3, number> {
  const r: Record<1 | 2 | 3, number> = { 1: 0, 2: 0, 3: 0 };
  for (const o of orders) {
    const t = (o.client?.tier ?? 2) as 1 | 2 | 3;
    if (t === 1 || t === 2 || t === 3) r[t] += 1;
  }
  return r;
}
