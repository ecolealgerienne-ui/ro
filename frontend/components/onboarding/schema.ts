/**
 * Schéma du questionnaire arborescent V1.
 *
 * Spec V3 §4 prévoit 80-150 questions dans l'arbre dont chaque DP n'en voit
 * que 15-25. V1 simplifie à 5 sections (15 questions essentielles + 3
 * conditionnelles selon réponses). Les mini-questionnaires contextuels
 * post-J0 (5.3) sont V2.
 */

export type QuestionId =
  | 'workshop_name'
  | 'workshop_city'
  | 'workshop_certifications'
  | 'n_operators'
  | 'shift_start'
  | 'shift_end'
  | 'workdays'
  | 'machines'
  | 'clients'
  | 'setup_dependent'
  | 'family_count'
  | 'transition_hint'
  | 'main_pain_point';

export interface MachineEntry {
  name: string;
  type: string;
}

export interface ClientEntry {
  name: string;
  tier: 1 | 2 | 3;
  certifications: string[];
}

/**
 * Données collectées par l'onboarding. Tous les champs sont optionnels au
 * début de la session, requis à la soumission selon la step où ils sont posés.
 */
export interface OnboardingData {
  workshop_name?: string;
  workshop_city?: string;
  workshop_certifications?: string[];
  n_operators?: number;
  shift_start?: number;
  shift_end?: number;
  workdays?: number[];
  machines?: MachineEntry[];
  clients?: ClientEntry[];
  setup_dependent?: 'yes' | 'partial' | 'no' | 'dontknow';
  family_count?: number;
  transition_hint?: string;
  main_pain_point?: string;
}

export interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  /** Aide contextuelle "Pourquoi cette question ?" — affichée à droite. */
  why: string;
  /** Validation : retourne null si OK, sinon message d'erreur. */
  validate: (data: OnboardingData) => string | null;
  /** Skip si la condition est fausse. */
  skipIf?: (data: OnboardingData) => boolean;
}

export const STEPS: OnboardingStep[] = [
  {
    id: 'identity',
    title: 'Identité de l\'atelier',
    description: 'On commence par le nom de ton atelier et sa localisation.',
    why: 'Ces infos servent à l\'affichage et aux logs. Elles ne sont jamais partagées hors de ton instance.',
    validate: (d) =>
      !d.workshop_name?.trim()
        ? 'Le nom de l\'atelier est requis.'
        : !d.workshop_city?.trim()
          ? 'La ville est requise.'
          : null,
  },
  {
    id: 'certifications',
    title: 'Certifications',
    description: 'Quelles normes qualité sont en vigueur dans ton atelier ?',
    why: 'Les certifications conditionnent les obligations de traçabilité (lot, certificat matière) et certains contrôles obligatoires (rectifieuse certifiée pour aéro).',
    validate: () => null, // optionnel
  },
  {
    id: 'team',
    title: 'Équipe & horaires',
    description: 'Combien d\'opérateurs et quels horaires ?',
    why: 'Les opérateurs apparaissent comme contrainte de capacité (un opérateur ne peut pas tenir 2 machines en même temps). Les horaires définissent les fenêtres de production disponibles.',
    validate: (d) => {
      if (d.n_operators === undefined || d.n_operators < 1) return 'Au moins 1 opérateur requis.';
      if (d.shift_start === undefined || d.shift_end === undefined)
        return 'Horaires requis.';
      if (d.shift_start >= d.shift_end) return 'Heure de fin doit être après heure de début.';
      if (!d.workdays || d.workdays.length === 0) return 'Choisis au moins 1 jour travaillé.';
      return null;
    },
  },
  {
    id: 'machines',
    title: 'Machines',
    description: 'Liste tes machines avec leur nom et type.',
    why: 'Chaque machine est une ressource du solveur. La liste précise (vs. juste un nombre) permet d\'afficher le Gantt par machine et de gérer les indisponibilités spécifiques.',
    validate: (d) =>
      !d.machines || d.machines.length === 0
        ? 'Au moins 1 machine requise.'
        : d.machines.some((m) => !m.name.trim())
          ? 'Toutes les machines doivent avoir un nom.'
          : null,
  },
  {
    id: 'clients',
    title: 'Donneurs d\'ordre',
    description: 'Tes 3-5 plus gros clients, avec leur niveau de criticité.',
    why: 'Le tier conditionne la priorité du solveur : Tier 1 (aéro/médical) est protégé en cas de replan, Tier 3 absorbe les déplacements. Convention "tier 1 critique = 10× tier 3 standard".',
    validate: (d) =>
      !d.clients || d.clients.length === 0
        ? 'Au moins 1 donneur d\'ordre requis.'
        : d.clients.some((c) => !c.name.trim())
          ? 'Tous les clients doivent avoir un nom.'
          : null,
  },
  {
    id: 'setup',
    title: 'Setup-dependent ?',
    description:
      'Tes temps de réglage dépendent-ils de l\'enchaînement des pièces (ex: passer titane → aluminium prend plus de temps que titane → titane) ?',
    why: 'Si oui, le solveur va grouper les pièces par famille pour minimiser les changements d\'outils. C\'est en moyenne +18% de capacité chez nos clients design partners.',
    validate: (d) =>
      !d.setup_dependent ? 'Choisis une réponse (tu peux dire "je ne sais pas").' : null,
  },
  {
    id: 'family_count',
    title: 'Combien de familles de pièces ?',
    description: 'Estimation : combien de familles différentes traites-tu (matière + forme proches) ?',
    why: 'Le clustering automatique (Phase 1.7) déduit les familles à partir de la nomenclature. Cette question sert juste à dimensionner la matrice de transition. 5-15 familles est typique.',
    validate: (d) =>
      d.family_count === undefined || d.family_count < 1 ? 'Donne une estimation (1-50).' : null,
    skipIf: (d) => d.setup_dependent !== 'yes',
  },
  {
    id: 'pain_point',
    title: 'Qu\'est-ce qui t\'enlève le sommeil aujourd\'hui ?',
    description:
      'Une chose dans la planification que tu aimerais améliorer en priorité (texte libre, optionnel).',
    why: 'On utilise cette réponse pour calibrer les priorités du solveur (poids tardiness vs. stabilité vs. utilisation) et pour cibler le suivi des 4 prochaines semaines.',
    validate: () => null,
  },
];

export const CERTIFICATIONS_OPTIONS = [
  'EN 9100 (aéronautique)',
  'IATF 16949 (auto)',
  'ISO 13485 (médical)',
  'ISO 9001 (générique)',
];

export const MACHINE_TYPES = [
  'Tour CN',
  'Tour CN (axe C)',
  'Fraiseuse 3 axes',
  'Fraiseuse 5 axes',
  'Rectifieuse',
  'Affûteuse',
  'Banc de mesure',
  'Autre',
];

export const WORKDAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

/** Filtre les étapes à afficher selon les réponses courantes. */
export function activeSteps(data: OnboardingData): OnboardingStep[] {
  return STEPS.filter((s) => !s.skipIf?.(data));
}
