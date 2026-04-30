// Données factices pour le mockup UX chef d'atelier.
// Toute ressemblance avec un atelier réel est volontaire mais générique.

const ATELIER = {
  nom: "Mécanique Précision SAS",
  ville: "Saint-Étienne (42)",
  certifications: ["EN 9100", "IATF 16949"],
  chefAtelier: "Pierre Marchand",
  date: "lundi 12 mai 2026 — 7h45",
};

const MACHINES = [
  { id: "CN-1", nom: "Tour CN-1", type: "Tour CN", color: "#0ea5e9" },
  { id: "CN-2", nom: "Tour CN-2", type: "Tour CN", color: "#0284c7" },
  { id: "CN-3", nom: "Tour CN-3", type: "Tour CN", color: "#0369a1" },
  { id: "CN-4", nom: "Tour CN-4 (axe C)", type: "Tour CN", color: "#075985" },
  { id: "CN-5", nom: "Tour CN-5 (axe C)", type: "Tour CN", color: "#0c4a6e" },
  { id: "FR-1", nom: "Fraiseuse FR-1 (5 axes)", type: "Fraiseuse", color: "#7c3aed" },
  { id: "FR-2", nom: "Fraiseuse FR-2 (5 axes)", type: "Fraiseuse", color: "#6d28d9" },
  { id: "RC-1", nom: "Rectifieuse RC-1", type: "Rectifieuse", color: "#be185d" },
];

const CLIENTS = {
  Safran: { tier: 1, certif: "EN 9100", couleur: "#7f1d1d" }, // wine
  Stellantis: { tier: 2, certif: "IATF 16949", couleur: "#c2410c" }, // orange
  ProtoLab: { tier: 3, certif: null, couleur: "#475569" }, // slate
  Bosch: { tier: 2, certif: "IATF 16949", couleur: "#b45309" }, // amber
};

const TIER_INFO = {
  1: { label: "Tier 1 — critique", couleur: "#7f1d1d", bg: "#fee2e2" },
  2: { label: "Tier 2 — standard", couleur: "#c2410c", bg: "#ffedd5" },
  3: { label: "Tier 3 — opportuniste", couleur: "#475569", bg: "#f1f5f9" },
};

// 25 OF répartis sur la semaine 12-16 mai. Couvre 3 clients, 4 tiers.
// Format : [of_id, client, machine, debut_h, duree_h, etat]
const ORDRES = [
  // Lundi 12 mai
  { id: "OF-2026-0847", client: "Safran", piece: "Bague aube TBP", machine: "CN-3", jour: "lun", debut: 8.0, duree: 3.5, etat: "en_cours" },
  { id: "OF-2026-0848", client: "Safran", piece: "Carter HP étage 4", machine: "FR-1", jour: "lun", debut: 9.5, duree: 5.0, etat: "planifie" },
  { id: "OF-2026-0851", client: "Stellantis", piece: "Pignon différentiel", machine: "CN-1", jour: "lun", debut: 8.0, duree: 4.0, etat: "en_cours" },
  { id: "OF-2026-0852", client: "Stellantis", piece: "Pignon différentiel", machine: "CN-2", jour: "lun", debut: 8.0, duree: 4.0, etat: "en_cours" },
  { id: "OF-2026-0855", client: "ProtoLab", piece: "Proto coque ITER", machine: "FR-2", jour: "lun", debut: 13.0, duree: 4.5, etat: "planifie" },
  { id: "OF-2026-0858", client: "Bosch", piece: "Axe transmission", machine: "CN-4", jour: "lun", debut: 8.5, duree: 6.0, etat: "planifie" },

  // Mardi 13 mai
  { id: "OF-2026-0849", client: "Safran", piece: "Disque turbine HP", machine: "RC-1", jour: "mar", debut: 8.0, duree: 7.0, etat: "planifie" },
  { id: "OF-2026-0853", client: "Stellantis", piece: "Couronne dent.", machine: "CN-1", jour: "mar", debut: 8.0, duree: 5.5, etat: "planifie" },
  { id: "OF-2026-0854", client: "Stellantis", piece: "Couronne dent.", machine: "CN-2", jour: "mar", debut: 8.0, duree: 5.5, etat: "planifie" },
  { id: "OF-2026-0856", client: "ProtoLab", piece: "Bride hydraulique", machine: "FR-1", jour: "mar", debut: 14.5, duree: 3.0, etat: "planifie" },
  { id: "OF-2026-0859", client: "Bosch", piece: "Axe transmission", machine: "CN-4", jour: "mar", debut: 8.5, duree: 6.0, etat: "planifie" },
  { id: "OF-2026-0863", client: "Stellantis", piece: "Bride moteur", machine: "FR-2", jour: "mar", debut: 8.0, duree: 5.0, etat: "planifie" },

  // Mercredi 14 mai
  { id: "OF-2026-0860", client: "Safran", piece: "Bague aube TBP", machine: "CN-3", jour: "mer", debut: 8.0, duree: 3.5, etat: "planifie" },
  { id: "OF-2026-0861", client: "Stellantis", piece: "Pignon BV6", machine: "CN-5", jour: "mer", debut: 8.0, duree: 4.5, etat: "planifie" },
  { id: "OF-2026-0862", client: "Stellantis", piece: "Pignon BV6", machine: "CN-5", jour: "mer", debut: 13.0, duree: 4.5, etat: "planifie" },
  { id: "OF-2026-0864", client: "ProtoLab", piece: "Proto coque ITER", machine: "FR-2", jour: "mer", debut: 13.5, duree: 4.5, etat: "planifie" },
  { id: "OF-2026-0867", client: "Bosch", piece: "Bague intermédiaire", machine: "CN-1", jour: "mer", debut: 8.0, duree: 5.0, etat: "planifie" },

  // Jeudi 15 mai
  { id: "OF-2026-0865", client: "Safran", piece: "Carter HP étage 4", machine: "FR-1", jour: "jeu", debut: 8.0, duree: 5.0, etat: "planifie" },
  { id: "OF-2026-0866", client: "Stellantis", piece: "Pignon différentiel", machine: "CN-2", jour: "jeu", debut: 8.0, duree: 4.0, etat: "planifie" },
  { id: "OF-2026-0868", client: "ProtoLab", piece: "Bride hydraulique", machine: "FR-1", jour: "jeu", debut: 14.0, duree: 3.0, etat: "planifie" },
  { id: "OF-2026-0869", client: "Bosch", piece: "Axe transmission", machine: "CN-4", jour: "jeu", debut: 8.5, duree: 6.0, etat: "planifie" },
  { id: "OF-2026-0871", client: "Stellantis", piece: "Couronne dent.", machine: "CN-1", jour: "jeu", debut: 8.0, duree: 5.5, etat: "planifie" },

  // Vendredi 16 mai
  { id: "OF-2026-0870", client: "Safran", piece: "Disque turbine HP", machine: "RC-1", jour: "ven", debut: 8.0, duree: 7.0, etat: "planifie" },
  { id: "OF-2026-0872", client: "Stellantis", piece: "Bride moteur", machine: "FR-2", jour: "ven", debut: 8.0, duree: 5.0, etat: "planifie" },
  { id: "OF-2026-0873", client: "ProtoLab", piece: "Proto coque ITER", machine: "FR-2", jour: "ven", debut: 13.5, duree: 4.5, etat: "planifie" },
];

const ALERTES = [
  {
    id: "alert-1",
    severite: "critique",
    titre: "Risque de retard OF Safran",
    detail: "OF-2026-0847 (Bague aube TBP) prévu fini à 11h30 → deadline 12h. Marge = 30 min.",
    action: "Voir l'OF",
  },
  {
    id: "alert-2",
    severite: "majeur",
    titre: "Maintenance CN-3 vendredi",
    detail: "Indisponibilité programmée 14h-18h. 2 OF Safran à replanifier avant.",
    action: "Replanifier",
  },
  {
    id: "alert-3",
    severite: "info",
    titre: "Nouvelle commande Stellantis",
    detail: "12 OF Pignon BV6 reçus à 7h. Ordre de magnitude : 60h de charge sur CN-5.",
    action: "Importer",
  },
];

const KPI = {
  ofPlanifies: 25,
  ofTier1: 5,
  ofTier2: 14,
  ofTier3: 6,
  utilisationMoyenne: 73,
  scoreConfiance: 87,
  makespanSemaine: 4.5, // jours
  status: "valide",
  versionActive: "v23",
};

const VERSIONS = [
  {
    id: "v23",
    date: "lun 12 mai 7h32",
    auteur: "Pierre M.",
    message: "Replanif après réception 12 OF Pignon BV6 Stellantis",
    ofCount: 25,
    makespan: "4j 6h",
    actif: true,
  },
  {
    id: "v22",
    date: "ven 9 mai 17h15",
    auteur: "Pierre M.",
    message: "Gel zone matin (8h-12h) jeudi pour audit Safran",
    ofCount: 13,
    makespan: "3j 8h",
    actif: false,
  },
  {
    id: "v21",
    date: "jeu 8 mai 14h02",
    auteur: "auto-replan",
    message: "Replanif auto après panne RC-1 (résolue à 11h)",
    ofCount: 13,
    makespan: "3j 9h",
    actif: false,
  },
  {
    id: "v20",
    date: "lun 5 mai 7h58",
    auteur: "Pierre M.",
    message: "Plan semaine S19",
    ofCount: 14,
    makespan: "4j 2h",
    actif: false,
  },
];

// Conversation : exemple de scenario "priorité 1 sur Safran"
const CONVERSATION = [
  {
    role: "user",
    texte: "Priorité 1 sur Safran cette semaine, j'ai une visite client jeudi.",
    heure: "7h47",
  },
  {
    role: "assistant",
    texte: "Compris. J'analyse les impacts d'une priorité absolue sur les 5 OF Safran de la semaine.",
    heure: "7h47",
  },
  {
    role: "assistant",
    texte: `Voici ce que ça implique :

• Les 5 OF Safran (Tier 1) seraient placés en premier sur leurs machines respectives.
• 4 OF Stellantis (Tier 2) reculent de 1.5j en moyenne.
• 1 OF ProtoLab (Tier 3) glisse à la semaine prochaine.
• 0 OF impacté pour Bosch.
• Makespan global : 4j 6h → 4j 4h (gain 2h).
• Aucun conflit de ressource détecté, planning faisable.`,
    heure: "7h47",
    validation: {
      titre: "Appliquer cette modification ?",
      diff: {
        avant: "Mix client équilibré, makespan 4j 6h",
        apres: "Safran prioritaire absolu, makespan 4j 4h, +1.5j moyen sur Stellantis",
      },
      ofImpactes: 5,
    },
  },
];

// Infaisabilité : scénario pilote
const INFAISABILITE = {
  contexte: "Replanification suite à : nouvelle commande Stellantis 12 OF + maintenance CN-3 vendredi 14h-18h.",
  causes: [
    {
      kind: "MACHINE_UNAVAILABILITY",
      identifier: "CN-3 maintenance vendredi 14h-18h",
      description: "Indisponibilité de la machine CN-3 du vendredi 14h au vendredi 18h bloque 2 OF Safran (OF-2026-0860, OF-2026-0865) avec deadline lundi matin.",
      action: {
        kind: "remove_unavailability",
        label: "Reporter la maintenance d'une semaine",
        impact: "Libère CN-3 vendredi → les 2 OF Safran rentrent dans la semaine.",
        cout: "Demande de report à valider avec maintenance industrielle.",
      },
    },
    {
      kind: "JOB",
      identifier: "OF-2026-0892 (Stellantis Pignon BV6, 45h sur FR-2)",
      description: "Cet OF arrivé ce matin est trop long pour les fenêtres restantes de FR-2 cette semaine, vu la priorité Safran demandée.",
      action: {
        kind: "defer_job",
        label: "Décaler OF-2026-0892 à la semaine prochaine",
        impact: "Stellantis informé du décalage de 5 jours. Planning S20 absorbe sans problème.",
        cout: "À valider avec donneur d'ordre Stellantis (deadline initial : J+10).",
      },
    },
  ],
  alternative: {
    label: "Mode dégradé : ignorer Tier 1 strict",
    impact: "Le solveur trouvera un planning faisable mais les Safran ne seront plus prioritaires.",
    risque: "Visite client jeudi exposée.",
  },
};
