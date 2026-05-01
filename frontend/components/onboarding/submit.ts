import { api } from '@/lib/api/client';
import type { Workshop } from '@/lib/api/types';
import type { OnboardingData } from './schema';

/**
 * Convertit les données du questionnaire en appels API séquentiels :
 * 1. POST /workshops (atelier de base)
 * 2. POST /workshops/:id/machines (par machine)
 * 3. POST /workshops/:id/clients (par client)
 *
 * Les opérateurs et la matrice de transition sont créés vides V1, à
 * configurer plus tard via les mini-questionnaires contextuels (5.3 V2).
 *
 * Retourne le workshopId créé pour redirection.
 */
export async function submitOnboarding(data: OnboardingData): Promise<string> {
  // 1. Atelier
  const workshop = await api.post<Workshop>('/workshops', {
    name: data.workshop_name!,
    city: data.workshop_city,
    certifications: data.workshop_certifications ?? [],
    nOperators: data.n_operators ?? 0,
    shiftStart: data.shift_start,
    shiftEnd: data.shift_end,
    workdays: data.workdays,
  });

  // 2. Machines (séquentiel pour preserver ordre des machineIdInt)
  for (const m of data.machines ?? []) {
    if (!m.name.trim()) continue;
    await api.post(`/workshops/${workshop.id}/machines`, {
      name: m.name.trim(),
      type: m.type || undefined,
    });
  }

  // 3. Clients
  for (const c of data.clients ?? []) {
    if (!c.name.trim()) continue;
    await api.post(`/workshops/${workshop.id}/clients`, {
      name: c.name.trim(),
      tier: c.tier,
      certifications: c.certifications ?? [],
    });
  }

  return workshop.id;
}
