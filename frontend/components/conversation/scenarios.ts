/**
 * Scénarios scriptés V1 — pré-réponses pour l'agent conversationnel.
 *
 * V1 : pas d'intégration LLM live (les agents Phase 3 existent côté Python
 * mais leur appel depuis le frontend nécessite un endpoint backend dédié,
 * différé J4 V2). Ces scénarios servent à valider l'UX décisionnelle avec
 * les design partners avant d'engager l'effort backend LLM.
 *
 * Match heuristique sur le texte utilisateur. Si rien ne matche, on retourne
 * une réponse générique "non pris en charge V1".
 */

export interface ScriptedAction {
  id: string;
  kind: 'apply_priority' | 'reschedule' | 'freeze' | 'defer' | 'noop';
  description: string;
  preview: ScriptedPreview;
}

export interface ScriptedPreview {
  metrics: { label: string; value: string; delta?: string; tone?: 'good' | 'bad' | 'neutral' }[];
  impacted: { orderRef: string; client: string; tier: 1 | 2 | 3; change: string }[];
  guarantees: string[];
}

export interface ScriptedReply {
  /** Message utilisateur d'entrée qui matche ce scénario (regex). */
  match: RegExp;
  /** Réponse de l'assistant en plusieurs tours. */
  turns: string[];
  /** Action proposée à valider. */
  action: ScriptedAction;
}

const SCENARIOS: ScriptedReply[] = [
  {
    match: /priorit[ée].*safran|safran.*priorit[ée]/i,
    turns: [
      "Compris. J'analyse les impacts d'une priorité absolue sur les OF Safran de la semaine.",
      `Voici ce que ça implique :
• Les OF Safran (Tier 1) seraient placés en premier sur leurs machines respectives.
• Quelques OF Stellantis (Tier 2) reculent de 1.5j en moyenne.
• 0 OF impacté pour Bosch.
• Aucun conflit de ressource détecté, planning faisable.`,
    ],
    action: {
      id: 'safran-prio',
      kind: 'apply_priority',
      description: 'Priorité absolue Safran',
      preview: {
        metrics: [
          { label: 'Makespan', value: '4j 4h', delta: '−2h', tone: 'good' },
          { label: 'Score', value: '89/100', delta: '+2', tone: 'good' },
          { label: 'OF déplacés', value: '5 / 25' },
          { label: 'Conflits', value: 'Aucun', tone: 'good' },
        ],
        impacted: [
          { orderRef: 'OF-2026-0851', client: 'Stellantis', tier: 2, change: '+1.5j' },
          { orderRef: 'OF-2026-0852', client: 'Stellantis', tier: 2, change: '+1.5j' },
          { orderRef: 'OF-2026-0855', client: 'ProtoLab', tier: 3, change: '+1 sem.' },
        ],
        guarantees: ['Tous les OF Tier 1 protégés', 'Aucun retard sur deadlines'],
      },
    },
  },
  {
    match: /(d[ée]cale|reporte|repousse).*OF[\s-]?(\w+)/i,
    turns: [
      "Compris. J'évalue l'impact du décalage de cet OF.",
      `Si je reporte cet OF d'une semaine :
• Ses opérations sont retirées de la semaine en cours.
• 2 OF Stellantis remontent dans le planning (gain ~5h chacun).
• Le client doit être informé du décalage.
• Aucun conflit de ressource détecté.`,
    ],
    action: {
      id: 'defer-of',
      kind: 'defer',
      description: 'Reporter l\'OF d\'une semaine',
      preview: {
        metrics: [
          { label: 'Makespan', value: '4j 1h', delta: '−5h', tone: 'good' },
          { label: 'Score', value: '85/100', delta: '−2', tone: 'bad' },
          { label: 'OF déplacés', value: '3 / 25' },
        ],
        impacted: [
          { orderRef: 'OF demandé', client: '—', tier: 2, change: '→ S+1' },
        ],
        guarantees: ['Communication client à confirmer'],
      },
    },
  },
  {
    match: /(geler|freeze|fige).*(OF|machine)/i,
    turns: [
      "Compris. Geler cet élément le rendra immuable jusqu'à la prochaine fenêtre de replanification.",
      `Effet :
• L'OF / la machine reste à sa position actuelle.
• Le solveur ne pourra plus le déplacer même si une meilleure config existe.
• Tu peux dégeler à tout moment depuis le Gantt.`,
    ],
    action: {
      id: 'freeze',
      kind: 'freeze',
      description: 'Geler la position',
      preview: {
        metrics: [
          { label: 'Score', value: '87/100', delta: '0', tone: 'neutral' },
          { label: 'Flexibilité solveur', value: '−1 ddl', tone: 'neutral' },
        ],
        impacted: [],
        guarantees: ['Aucun OF Tier 1 impacté'],
      },
    },
  },
  {
    match: /(prochaine|next).*(d[ée]ch[ée]ance|deadline)/i,
    turns: [
      `Prochaine échéance critique :
• OF-2026-0847 (Safran, Bague aube TBP) → deadline lundi 19 mai 12h
• Marge actuelle : 30 min
• Risque : si la machine CN-3 a une indisponibilité non planifiée, retard quasi certain.`,
    ],
    action: {
      id: 'noop-info',
      kind: 'noop',
      description: 'Information seule',
      preview: { metrics: [], impacted: [], guarantees: [] },
    },
  },
];

/** Réponse générique si rien ne matche. */
const FALLBACK: ScriptedReply = {
  match: /.*/,
  turns: [
    "Désolé, cette demande n'est pas encore prise en charge en V1. Les actions disponibles sont : changer la priorité d'un client, décaler un OF, geler un OF/machine, demander la prochaine échéance.",
  ],
  action: {
    id: 'fallback',
    kind: 'noop',
    description: 'Aucune action proposée',
    preview: { metrics: [], impacted: [], guarantees: [] },
  },
};

export function findScenario(text: string): ScriptedReply {
  const trimmed = text.trim();
  if (!trimmed) return FALLBACK;
  for (const s of SCENARIOS) {
    if (s.match.test(trimmed)) return s;
  }
  return FALLBACK;
}

export const SUGGESTIONS = [
  'Priorité 1 sur Safran cette semaine',
  'Décale OF-2026-0851 d\'une semaine',
  'Que se passe-t-il si je gèle l\'OF Bosch ?',
  'Prochaine échéance critique ?',
];
