# V0 — Statut d'avancement projet

> Document de suivi des étapes de construction du SaaS d'ordonnancement IA pour la sous-traitance mécanique PME.
> Référentiel : `specs-fonctionnelles-v3.md`, `specs-techniques-v3.md`, `specs-poc-scripts-v1.md`.
> Mis à jour à chaque transition d'étape.

---

## Légende des statuts

| Statut | Signification |
|--------|---------------|
| `⬜ à faire` | Étape non commencée |
| `🟡 en cours` | Étape démarrée, non validée |
| `🔵 en test` | Implémentation finie, validation en cours |
| `✅ stabilisée` | Critère de sortie atteint, étape verrouillée |
| `🔴 bloquée` | Blocage technique ou décision en attente |
| `⏸️ en pause` | Reportée volontairement |
| `❌ abandonnée` | Sortie du périmètre |

---

## Vue d'ensemble

| Phase | Intitulé | Statut global | Démarrage | Fin |
|-------|----------|---------------|-----------|-----|
| 0 | Validation OR-Tools (go/no-go projet) | ✅ stabilisée | 2026-04-29 | 2026-04-29 |
| 1 | Bibliothèque de patterns + objectifs composites | 🟡 en cours | 2026-04-29 | — |
| 2 | Trust layer technique (sans LLM) | ⬜ à faire | — | — |
| 3 | Agents LLM + serveur MCP | ⬜ à faire | — | — |
| 4 | Backend SaaS + persistance | ⬜ à faire | — | — |
| 5 | Frontend chef d'atelier | ⬜ à faire | — | — |
| 6 | PWA opérateur | ⬜ à faire | — | — |
| 7 | Observabilité, sécurité, production | ⬜ à faire | — | — |
| 8 | Pilote design partners | ⬜ à faire | — | — |

**Gates de décision** :
- **Gate 0** (fin Phase 0) : faisabilité technique CP-SAT — go/no-go projet
- **Gate 1** (fin Phase 2) : fiabilité moteur — < 1 erreur silencieuse / 100 ateliers tests
- **Gate 2** (fin Phase 8) : signal PMF — *"je peux plus revenir à Excel"*

---

## Phase 0 — Validation OR-Tools (go/no-go projet)

> Objectif : prouver que CP-SAT tient les SLA sur cas académiques + cas synthétiques réalistes méca.
> Référentiel : `specs-poc-scripts-v1.md`

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 0.1 | Setup repo `poc-scheduler` (uv, ruff, mypy, pytest, structure `src/`) | ✅ stabilisée | 2026-04-29 | 2026-04-29 | `uv sync` + `pytest` passent à vide | Validé en local WSL : 2/2 tests OK, Python 3.11.15, pytest 9.0.3 |
| 0.2 | Loader Taillard + parser CSV optima | ✅ stabilisée | 2026-04-29 | 2026-04-29 | Fichiers ta01/11/21/31/41 parsent sans erreur | Validé : 25/25 tests, 80/80 instances téléchargées en 14s, ta01/ta31/ta51 parsés avec métadonnées |
| 0.3 | Solveur JSSP basique (NoOverlap par machine, Precedence, Makespan) | ✅ stabilisée | 2026-04-29 | 2026-04-29 | Mini-cas 3×3 résolu à l'optimum connu | Validé : 41/41 tests, 2×2 → makespan 5 (OPTIMAL), 3×3 OR-Tools → makespan 11 (OPTIMAL), smoke ta01 résolu en < 4s avec makespan ≥ 1231 |
| 0.4 | Benchmark Taillard ta01-ta41, budget 120s | ✅ stabilisée | 2026-04-29 | 2026-04-29 | **Gap < 5% vs optimum sur 4/5 instances** | **5/5 sous 5%** : ta01 0.00% (OPTIMAL en 2.8s) · ta11 1.03% · ta21 2.62% · ta31 1.19% · ta41 4.24% · gap moyen 1.82% · max 4.24% — Gate 0 part 1 ✓ |
| 0.5 | Générateur d'ateliers synthétiques (machines, opérateurs, OF, gammes) | ✅ stabilisée | 2026-04-29 | 2026-04-29 | 1 atelier généré < 2s, schéma Pydantic strict | Validé : 1 atelier en 10 ms (200× plus rapide que cible), 100 ateliers en 0.92s (109/sec), reproductibilité par seed confirmée par diff |
| 0.6 | Patterns avancés : setup sequence-dependent, qualified operator, shared resources, calendars | ✅ stabilisée | 2026-04-29 | 2026-04-29 | Chaque pattern a ses tests unitaires golden | **24 tests golden** · 0.6a setup-dependent (9) · 0.6b operator (6) + shared (4) · 0.6c calendar (5) + extensions générateur (6) |
| 0.7 | Test intégration générateur → solveur (50-200 OF, 5-25 machines) | ✅ stabilisée | 2026-04-29 | 2026-04-29 | **Solution faisable < 60s sur 80% des cas** | **30/30 OPTIMAL** en 6s total (mean 0.2s, max 1.6s) sur profils mixed small/medium/large jusqu'à 25 mach × 198 OF (996 ops). Gate 0 part 2 ✓. **Note** : résultat sur JSSP de base sans patterns avancés actifs (setup/operator/shared/calendar) — leur intégration arrive en Phase 1.1, vraie épreuve scale à ce moment. |

**🚦 Gate 0 — décision projet** : si 0.4 ou 0.7 échouent → no-go ou repensage architecture (MiniZinc ? Hexaly ? découpage du problème ?).

---

## Phase 1 — Bibliothèque de patterns + objectifs composites

> Objectif : transformer le POC en socle réutilisable, prêt à porter les soft constraints et la replanification.

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 1.1 | Refactor patterns en classes `Pattern` (schema Pydantic, `apply`, `validate`, `get_test_cases`) | 🟡 en cours | 2026-04-29 | — | Tous les patterns de 0.6 passent par cette interface | 1.1a ✅ · 1.1b ✅ · 1.1c ✅ (solveur intègre tous les patterns conditionnellement, 168 tests passent en 124s) · 1.1d en cours (stress test full patterns + comparaison perf) |
| 1.2 | Objectif composite (makespan + tardiness + stability) | ⬜ à faire | — | — | Solveur accepte priorités relatives utilisateur | — |
| 1.3 | Calibration dynamique des poids (pré-résolution + normalisation) | ⬜ à faire | — | — | Sur 10 instances : aucun terme n'écrase les autres | — |
| 1.4 | Replanification incrémentale (freeze partiel + solution hint) | ⬜ à faire | — | — | Re-solve < 30% du temps initial sur petites perturbations | — |
| 1.5 | Stabilité pondérée par criticité Tier 1/2/3 | ⬜ à faire | — | — | Déplacer Tier 1 coûte 10× plus que Tier 3 | — |
| 1.6 | Soft constraints en pénalités (interface programmatique, sans LLM) | ⬜ à faire | — | — | 5 soft constraints + 5 hard cohabitent proprement | — |
| 1.7 | Clustering automatique des familles de pièces | ⬜ à faire | — | — | 100 pièces → 5-15 familles validées sur cas synthétique | — |
| 1.8 | Extraction MIS approximée + génération actions correctives déterministes | ⬜ à faire | — | — | Sur 20 cas INFEASIBLE intentionnels : MIS pertinent dans 80% | — |

---

## Phase 2 — Trust layer technique (sans LLM)

> Objectif : ce que le produit doit faire avant même la couche IA. Discipline anti-erreur silencieuse.

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 2.1 | Bibliothèque de 100 golden cases versionnée (YAML/JSON) | ⬜ à faire | — | — | Suite pytest qui les rejoue, < 2 min total | — |
| 2.2 | Module score de confiance (heuristiques pondérées) | ⬜ à faire | — | — | Score calculé sur tout résultat solver, seuils calibrés | — |
| 2.3 | Module simulation opérationnelle (fragmentation, transitions, micro-pauses, ratio setup/utile) | ⬜ à faire | — | — | Métriques calculées, seuils par défaut, rejet/recyclage automatique | — |
| 2.4 | Circuit breaker INFEASIBLE (3 retries → bascule MIS) | ⬜ à faire | — | — | Pas de boucle infinie, sortie déterministe | — |
| 2.5 | Pipeline complet : solving → validation cas-tests → simulation → score → décision | ⬜ à faire | — | — | E2E sur 20 ateliers générés, rapport propre | — |

**🚦 Gate 1 — fiabilité moteur** : < 1 erreur silencieuse / 100 ateliers tests. Sinon, repensage trust layer avant LLM.

---

## Phase 3 — Agents LLM + serveur MCP

> Objectif : couche IA disciplinée, cantonnée à extraction / explication. Aucune génération de code OR-Tools.

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 3.1 | Serveur MCP avec outils de modélisation (6 outils) | ⬜ à faire | — | — | Tests d'appel direct via SDK MCP | — |
| 3.2 | Outils MCP versioning (3) + exécution/explication (5) | ⬜ à faire | — | — | Couverture complète spec 5.2 | — |
| 3.3 | Abstraction `LLMProvider` (Claude primaire, Mistral fallback) | ⬜ à faire | — | — | Suite tests multi-modèles | — |
| 3.4 | Agent extraction — questionnaire arborescent → spec structurée | ⬜ à faire | — | — | 10 cas types, validation Pydantic stricte | — |
| 3.5 | Agent extraction — Excel/CSV + fuzzy matching + Data Quality | ⬜ à faire | — | — | > 90% lignes correctement classées sur 5 fichiers ERP | — |
| 3.6 | Traduction soft constraints NL → pénalités | ⬜ à faire | — | — | 20 phrases types correctement traduites | — |
| 3.7 | Agent explication — placement OF + INFEASIBLE NL | ⬜ à faire | — | — | Évaluation manuelle sur 30 cas | — |
| 3.8 | Modifications conversationnelles ("priorité 1 sur Safran") | ⬜ à faire | — | — | 10 modifications types testées avec validation humaine | — |

---

## Phase 4 — Backend SaaS + persistance

> Objectif : socle production multi-tenant, versioning, orchestration jobs.

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 4.1 | Setup NestJS + Prisma + PostgreSQL + Docker Compose | ⬜ à faire | — | — | API healthcheck OK | — |
| 4.2 | Multi-tenancy (middleware Prisma `tenant_id`) | ⬜ à faire | — | — | Tests isolation tenant A vs B | — |
| 4.3 | Auth (Argon2id, JWT + refresh) | ⬜ à faire | — | — | Flow login complet | — |
| 4.4 | Modèle de données complet (toutes tables spec 3.2) | ⬜ à faire | — | — | Migrations versionnées | — |
| 4.5 | API CRUD modèles d'atelier + versioning (snapshot/diff/rollback) | ⬜ à faire | — | — | Couverture endpoints spec | — |
| 4.6 | Queue BullMQ + orchestration jobs solving | ⬜ à faire | — | — | Job long async OK, SSE updates | — |
| 4.7 | Pont backend ↔ microservice Python (HTTP + queue) | ⬜ à faire | — | — | E2E : trigger solve depuis API → résultat persisté | — |
| 4.8 | Module Data Quality côté backend (sessions, anomalies, dashboard data) | ⬜ à faire | — | — | Import Excel → anomalies persistées | — |

---

## Phase 5 — Frontend chef d'atelier

> Objectif : UI principale avec questionnaire, dashboard, Gantt, conversation, versioning.

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 5.1 | Setup Next.js 15 + Tailwind + shadcn + auth client | ⬜ à faire | — | — | Login + dashboard vide | — |
| 5.2 | Questionnaire arborescent conditionnel (15 questions essentielles) | ⬜ à faire | — | — | Onboarding cas type complet | — |
| 5.3 | Mini-questionnaires contextuels + onboarding progressif | ⬜ à faire | — | — | Déclencheurs testés | — |
| 5.4 | Dashboard chef d'atelier (KPI + alertes) | ⬜ à faire | — | — | Données mockées puis réelles | — |
| 5.5 | Gantt interactif (DHTMLX ou Bryntum, choix après essais) | ⬜ à faire | — | — | Drag-drop, freeze, criticité couleur | Décision lib à arbitrer |
| 5.6 | Interface conversation + validation systématique avant action | ⬜ à faire | — | — | 5 commandes types fonctionnelles | — |
| 5.7 | Module import Data Quality (UX validation 3 niveaux) | ⬜ à faire | — | — | Flow upload → dashboard → corrections | — |
| 5.8 | UX historique versioning (timeline, diff, rollback) | ⬜ à faire | — | — | Rollback testé | — |
| 5.9 | Module infaisabilité (explication NL + actions correctives) | ⬜ à faire | — | — | UX claire sur 5 cas INFEASIBLE | — |

---

## Phase 6 — PWA opérateur

> Objectif : tablette atelier offline-first pour scan / déclaration / signalement.

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 6.1 | Setup Next.js + next-pwa + service worker offline-first | ⬜ à faire | — | — | Installation tablette Android testée | — |
| 6.2 | Écran "Mes OF du jour" + scan QR (caméra) | ⬜ à faire | — | — | Flow scan opérationnel | — |
| 6.3 | Déclarations début/fin + photo signalement | ⬜ à faire | — | — | Persistence locale OK | — |
| 6.4 | Sync différée + queue mutations + last-write-wins | ⬜ à faire | — | — | Test mode avion → reconnexion | — |

---

## Phase 7 — Observabilité, sécurité, production

> Objectif : produit déployable et observable en conditions réelles.

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 7.1 | Logs structurés (Loki + Promtail) | ⬜ à faire | — | — | 3 catégories séparées (tech, business, LLM) | — |
| 7.2 | Métriques Prometheus + Grafana (business + tech) | ⬜ à faire | — | — | Dashboards spec 12.2 | — |
| 7.3 | Tracing OpenTelemetry → Tempo | ⬜ à faire | — | — | Trace solve E2E | — |
| 7.4 | Alerting (critiques + warnings) | ⬜ à faire | — | — | 4 alertes critiques live | — |
| 7.5 | Backup PostgreSQL + test restore | ⬜ à faire | — | — | RPO 5 min / RTO 4h validés | — |
| 7.6 | CI/CD GitHub Actions complet | ⬜ à faire | — | — | Pipeline full passing | — |
| 7.7 | Déploiement staging + production Hetzner | ⬜ à faire | — | — | Smoke tests E2E | — |
| 7.8 | RGPD : export, suppression, purge logs 90j | ⬜ à faire | — | — | Procédures testées | — |

---

## Phase 8 — Pilote design partners

> Objectif : valider PMF avec 5-7 design partners équilibrés (≥2 français certifiés aéro).

| # | Étape | Statut | Démarrage | Fin | Critère de sortie | Notes |
|---|-------|--------|-----------|-----|-------------------|-------|
| 8.1 | Onboarding 1er DP (idéalement français certifié aéro) | ⬜ à faire | — | — | Plannings produits utilisés en réel | — |
| 8.2 | Boucle feedback + correctifs (probable retour Phase 1-3) | ⬜ à faire | — | — | 30 jours d'usage continu | — |
| 8.3 | Onboarding 4-6 DP supplémentaires | ⬜ à faire | — | — | Mix géo + certification respecté | — |
| 8.4 | Mesure critères go/no-go phase 1 spec | ⬜ à faire | — | — | 4-5/7 utilisent ≥3 fois/sem à 60j ; < 1 erreur silencieuse / client / mois | Gate 2 |

**🚦 Gate 2 — signal PMF early** : si on n'entend pas *"je peux plus revenir à Excel"* à 12 mois → wedge à repenser.

---

## Journal des décisions

> À remplir au fil de l'eau pour les choix structurants (lib Gantt, provider LLM, infra, etc.).

| Date | Décision | Contexte | Impact |
|------|----------|----------|--------|
| 2026-04-29 | Environnement de dev = WSL (Ubuntu) + VSCode Remote | Cohérence avec stack Linux des specs, élimination des soucis CRLF/path | Tous les scripts en bash, paths Unix |
| 2026-04-29 | Monorepo dans `ro/` avec sous-dossiers par composant | Simplicité solo, refactoring facile, traçabilité E2E | Pas de repo séparé pour `poc-scheduler` |
| 2026-04-29 | Convention de commits = Conventional Commits | Lisibilité historique, automatisation possible (changelog) | Tous les commits suivent `<type>(<scope>): <sujet>` |
| 2026-04-29 | Stratégie de branches = `main` + `dev` + `feat/<phase>.<étape>-<slug>` | Trace par étape `v0-status.md`, PR pour review même solo | À appliquer une fois la branche `claude/create-session-Y481M` mergée |
| 2026-04-29 | **Gate 0 part 1 ✅ — OR-Tools CP-SAT validé sur Taillard** | Batch ta01/11/21/31/41 budget 120s × 8 workers : 5/5 instances sous 5% de gap, gap moyen 1.82%, max 4.24% (ta41). ta01 résolu à l'optimum prouvé en 2.8s. | Décision : **GO** sur le moteur OR-Tools direct (vs MiniZinc, Hexaly). Le choix structurant `specs-techniques-v3.md §6.1` est confirmé empiriquement. |
| 2026-04-29 | **Gate 0 part 2 ✅ — Pipeline E2E synthétique scale** | Stress test 30 ateliers (mixed small/medium/large, jusqu'à 25 mach × 198 OF / 996 ops) avec budget 60s : 30/30 OPTIMAL en 6s total, mean 0.2s, max 1.6s. | Décision : **GO** Phase 1. Mais résultat à relativiser : pas de patterns avancés actifs au solving, et adapter pré-assigne les machines par greedy load-balancing (réduit la difficulté combinatoire). La vraie épreuve scale arrive en Phase 1.1+ avec l'intégration des contraintes industrielles. |
| 2026-04-29 | **Phase 0 ✅ entièrement validée** | 7/7 étapes stabilisées · 116 tests passants en 6s · Gate 0 entièrement franchie | Phase 1 ouverte. Premier chantier prioritaire : refactor patterns en classes (1.1) puis intégration au solveur. |

---

## Journal des retours en arrière

> Si une phase ultérieure révèle un manque dans une phase antérieure, on le trace ici.

| Date | Phase impactée | Étape | Raison | Action |
|------|---------------|-------|--------|--------|
| — | — | — | — | — |

---

*Document créé le 2026-04-29.*
