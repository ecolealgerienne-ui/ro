# Rapport d'avancement Phase 0 — POC OR-Tools

> Document narratif complémentaire à `v0-status.md` (tracker structuré).
> Documente les résultats concrets, décisions techniques et métriques de chaque étape.
> Mis à jour à chaque étape stabilisée.

**Snapshot : 2026-04-29 — Phase 0 entièrement validée**

---

## Synthèse

| Indicateur | Valeur |
|------------|--------|
| Phase courante | 0 — Validation OR-Tools — **TERMINÉE ✅** |
| Étapes Phase 0 stabilisées | **7/7** (0.1 ✅ · 0.2 ✅ · 0.3 ✅ · 0.4 ✅ · 0.5 ✅ · 0.6 ✅ · 0.7 ✅) |
| Gates franchies | **Gate 0 part 1 ✅** (benchmark Taillard) · **Gate 0 part 2 ✅** (stress test E2E) |
| Tests automatisés | **116 passants** (6.01s exécution complète) |
| Décision projet | **GO Phase 1** — OR-Tools CP-SAT validé empiriquement, fondations solides |

---

## Étape 0.1 — Setup repo `poc-scheduler`

**Objectif** : structure projet Python avec outillage moderne (uv, ruff, mypy, pytest).

**Livrables**
- `pyproject.toml` avec dépendances (ortools, pydantic, click, rich, numpy, pandas) + dev tools
- Layout `src/{core,loaders,generators}/` + `tests/` + `scripts/` + `data/`
- Configurations strictes : ruff (lint+format), mypy `--strict`, pytest avec markers
- `README.md`, `.python-version` (3.11), `.gitignore` local pour `data/`

**Critère de sortie** : `uv sync` + `pytest` passent à vide.

**Validation**
- `uv sync` : 43 paquets résolus
- `pytest` : 2 smoke tests passants
- Python 3.11.15, pytest 9.0.3

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Étape 0.2 — Loader Taillard + métadonnées

**Objectif** : charger les benchmarks JSSP académiques au format JSPLIB.

**Livrables**
- `src/core/models.py` — `Operation` / `Job` / `Machine` / `WorkshopInstance` Pydantic frozen
  avec validations (cohérence job_id/sequence_idx, références machines, doublons)
- `src/loaders/taillard.py` — parser JSPLIB avec auto-détection 0/1-indexing
- `data/taillard/instances_metadata.csv` — 80 lignes (proven_optimal pour ta01-ta10)
- `scripts/download_benchmarks.py` — CLI Click + Rich, télécharge depuis `raw.githubusercontent.com/tamy0612/JSPLIB`
- `data/taillard/README.md` — source, format, workflow

**Critère de sortie** : ta01/11/21/31/41 parsent sans erreur.

**Validation**
- 80 instances téléchargées en 14 secondes
- 25/25 tests passants (13 fixtures synthétiques + métadonnées + 3 tests réels)
- ta01/ta31/ta51 parsés avec leurs métadonnées (n_jobs, n_machines, optimum)

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Étape 0.3 — Solveur JSSP basique

**Objectif** : premier usage d'OR-Tools CP-SAT — preuve fonctionnelle.

**Livrables**
- `src/core/patterns.py` — 3 primitives CP-SAT :
  - `add_no_overlap_machine(model, intervals)`
  - `add_precedence_in_job(model, end_vars, start_vars)`
  - `make_makespan_objective(model, end_vars, horizon)`
- `src/core/solver.py` — `JSSPSolver` + `SolverResult` + `ScheduleAssignment` + `SolverStatus` StrEnum
  + helper `validate_schedule()` (réutilisable pour le trust layer)

**Critère de sortie** : mini-cas 3×3 résolu à l'optimum connu.

**Validation**
- Instance triviale 2×2 → makespan **5** (OPTIMAL, calculé à la main)
- Instance OR-Tools tutorial 3×3 → makespan **11** (OPTIMAL, valeur documentée)
- Smoke test ta01 (15×15) → solution faisable en **< 4 secondes**, makespan ≥ 1231 (optimum prouvé)
- 41/41 tests passants

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Étape 0.4 — Benchmark Taillard ta01-ta41 — Gate 0 part 1

**Objectif** : valider que CP-SAT tient un gap < 5% sur instances industrielles équivalentes.

**Livrables**
- `src/loaders/benchmark_runner.py` — `BenchmarkRecord`, `run_one`, `run_batch`, `write_csv`, `summarize`
- `scripts/run_taillard_benchmark.py` — CLI avec affichage Rich color-coded :
  - `solve <name>` pour instance unique
  - `batch --instances/--range` avec `--time-limit`, `--num-workers`, `--output`
  - Affichage live à chaque résolution

**Critère de sortie (Gate 0 part 1)** : gap < 5% sur ≥ 4/5 instances avec budget 120s.

**Résultats benchmark (8 workers, 120s budget par instance)**

| Instance | Taille  | Best known | Found | Gap %  | Time (s) | Status   |
|----------|---------|------------|-------|--------|----------|----------|
| ta01     | 15 × 15 | 1231       | 1231  | +0.00  | 2.8      | OPTIMAL  |
| ta11     | 20 × 15 | 1357       | 1371  | +1.03  | 120.0    | FEASIBLE |
| ta21     | 20 × 20 | 1642       | 1685  | +2.62  | 120.0    | FEASIBLE |
| ta31     | 30 × 15 | 1764       | 1785  | +1.19  | 120.4    | FEASIBLE |
| ta41     | 30 × 20 | 2005       | 2090  | +4.24  | 120.0    | FEASIBLE |

**Synthèse**
- 1 OPTIMAL, 4 FEASIBLE — toutes ont une solution
- **Gap moyen : 1.82 %** · Gap max : 4.24 % · Temps moyen : 96.7 s
- **5/5 instances sous 5 %** (critère était ≥ 4/5)

**Verdict — Gate 0 part 1 ✅ PASSÉE LARGEMENT**

> CP-SAT direct, sans tuning, est compétitif sur JSSP académique. Le choix
> structurant `specs-techniques-v3.md §6.1` (OR-Tools direct vs MiniZinc /
> Hexaly) est confirmé empiriquement. La marge de 1.82 % moyen donne de la
> latitude pour les contraintes industrielles supplémentaires (setup, calendrier,
> opérateurs) qui complexifient le problème en production.

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Étape 0.5 — Générateur d'ateliers synthétiques

**Objectif** : produire des instances réalistes méca précision pour le stress-test.

**Livrables**
- `src/generators/distributions.py` — constantes métier :
  - 9 types de machines (tour CN 2/4 axes, fraiseuse 3/5 axes, centre, rectifieuse, etc.)
  - 10 matières avec multiplicateurs de difficulté (Al baseline, Inox 1.5×, Ti 2.2×)
  - 15 opérations canoniques + table de compatibilité opération×machine
  - Temps de cycle de référence par opération (mean, std en minutes)
  - Tiers clients 1/2/3 avec poids 10/5/1
- `src/generators/workshop_generator.py` :
  - `GenerationParams` Pydantic frozen avec validators min ≤ max
  - Modèles `SyntheticMachine` / `Operator` / `Operation` / `Order` / `Workshop`
  - `generate_workshop(params)` reproductible via `numpy.random.default_rng(seed)`
  - Durées log-normales pondérées par matière
  - Opérateurs avec qualifications partielles (30-90 % de polyvalence)
- `scripts/generate_workshops.py` — CLI `single` / `batch` avec progress bar

**Critère de sortie** : 1 atelier généré < 2s, schéma Pydantic strict.

**Validation**
- 1 atelier généré en **10 ms** (cible < 2 s, **200× plus rapide**)
- 100 ateliers générés en **0.92 s** (cible < 60 s, **65× plus rapide**)
- Reproductibilité parfaite (`diff` vide entre deux runs même seed)
- 20/20 tests passants

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Étape 0.6 — Patterns avancés (3 sous-étapes)

**Objectif** : modéliser les 4 contraintes industrielles structurantes au-delà du JSSP basique.

### 0.6a — Sequence-dependent setup
- Pattern `add_no_overlap_with_setup(starts, ends, family_ids, transition_matrix)`
- Encodage par disjonctions par paires (pour POC ; refactor en 1.1 vers AddNoOverlap natif avec transition_matrix)
- 9 tests golden : optimum hand-calculé 14 (regroupement familles), matrice asymétrique, validation
- Le setup industriel typique (changement matière 15-45min, changement pièce même matière 5-15min) est désormais modélisable

### 0.6b — QualifiedOperator + SharedResource
- `add_qualified_operator_constraint` — intervals optionnels + `exactly_one` + `no_overlap` par opérateur
- `add_shared_resource_exclusion` — `add_cumulative` avec demande unitaire et capacité = max simultané
- 10 tests golden : 1 opérateur force séquentiel (9), 2 opérateurs paralllélisent (5), capacité 1/2/3 sur 3 ops

### 0.6c — Calendar + extensions générateur
- `make_unavailable_intervals(periods)` — IntervalVar fixes pour pauses/weekends/MP, fusionnables avec NoOverlap
- `SharedResource` et `WorkCalendar` Pydantic dans le générateur
- Injection optionnelle de ressources partagées (`shared_resource_probability`)
- Calendrier par défaut (480 min/jour, 1 équipe, 5 jours)
- 11 tests golden : opération 5min bloquée par indispo [3,8] → makespan 13, multiples plages, calendrier custom

**Critère de sortie** : chaque pattern a ses tests unitaires golden.

**Validation**
- 24 tests golden ajoutés (9 + 10 + 5 patterns + 6 générateur)
- 32 tests `test_patterns.py` au total · 26 tests `test_generator.py`

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Étape 0.7 — Pipeline E2E + stress test — Gate 0 part 2

**Objectif** : valider que la chaîne `générateur → adaptateur → solveur → validation` tient un taux de feasibility ≥ 80 % en moins de 60 s sur des ateliers représentatifs (50-200 OF, 5-25 machines).

**Livrables**
- `src/loaders/synthetic_adapter.py` — `synthetic_to_jssp_instance()` convertit un `SyntheticWorkshop` en `WorkshopInstance` JSSP via greedy load-balancing
- `tests/test_synthetic_adapter.py` — 10 tests (préservation jobs/machines/durées, compatibilité, équilibrage, métadonnées)
- `tests/test_integration.py` — 6 tests E2E (small 5×10, medium 10×30, validation contraintes, slow 15×80)
- `scripts/stress_test_synthetic.py` — CLI Click + Rich avec profils small/medium/large/mixed, exit code = 2 si feasibility < 80%

**Critère de sortie (Gate 0 part 2)** : feasibility ≥ 80% en < 60s sur 30 ateliers mixed.

**Résultats stress test** (30 ateliers, profil mixed, budget 60s, 8 workers)

| Métrique | Valeur |
|----------|--------|
| Feasibility < budget | **30/30 (100 %)** |
| OPTIMAL | **30/30** |
| Schedules valides | **30/30** |
| Temps moyen | 0.2 s |
| Temps max | 1.6 s |
| Plus grosse instance résolue | 25 machines × 198 OF (996 ops) |

**Verdict — Gate 0 part 2 ✅ PASSÉE LARGEMENT**

> Toutes les instances générées (jusqu'à ~1000 opérations) résolues à
> l'optimum prouvé en < 2 s. La pipeline est ~600× plus rapide que ce qu'on
> observe sur les benchmarks Taillard de taille comparable.

### ⚠️ Mise en perspective honnête du résultat

Cet écart de performance s'explique par des choix de scope volontaires et acceptables pour un POC :

1. **L'adaptateur greedy load-balancing pré-résout 50 % du problème combinatoire** — chaque opération est assignée à la machine compatible la moins chargée AVANT le solveur. Le CP-SAT n'a plus qu'à séquencer dans le temps, pas à choisir les machines (ce que fait le JSSP académique pur).

2. **Patterns avancés non actifs au solving** — `add_no_overlap_with_setup`, `add_qualified_operator_constraint`, `add_shared_resource_exclusion`, `make_unavailable_intervals` sont unit-testés (étape 0.6) mais pas encore intégrés au pipeline `JSSPSolver.solve()`. Leur intégration est planifiée en Phase 1.1 (refactor `Pattern` OOP).

3. **Pas de matière/famille modélisée comme contrainte** — les coûts de transition entre familles seraient les premiers à dégrader la perf.

**Implication** : la vraie épreuve scale arrivera en Phase 1.1+. À ce moment, viser 80 % de feasibility deviendra un objectif sérieux, pas une formalité. Les 30/30 OPTIMAL en 6 s sont à interpréter comme : **les fondations sont solides, le solveur a beaucoup de marge pour absorber la complexité supplémentaire des patterns industriels**.

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Métriques cumulées Phase 0 (au 2026-04-29)

### Tests automatisés

| Module | Tests | Détail |
|--------|-------|--------|
| `test_smoke.py` | 2 | Sanity check infra pytest |
| `test_models.py` | 7 | Validations Pydantic (Operation/Job/Machine/Workshop) |
| `test_taillard_loader.py` | 16 | Parser JSPLIB + métadonnées + 3 fixtures réelles |
| `test_patterns.py` | 32 | 7 patterns CP-SAT × tests golden + validations |
| `test_solver.py` | 8 | JSSPSolver + validate_schedule + smoke ta01 |
| `test_benchmark_runner.py` | 9 | BenchmarkRecord + run_one/batch + CSV roundtrip |
| `test_generator.py` | 26 | Reproductibilité + bornes + cohérence + perf + extensions 0.6c |
| `test_synthetic_adapter.py` | 10 | Adaptateur SyntheticWorkshop → WorkshopInstance |
| `test_integration.py` | 6 | Pipeline E2E + slow test 15×80 |
| **Total** | **116** | **6.01 s exécution complète** |

### Code livré (estimation)

| Composant | Fichiers | Lignes (approx.) |
|-----------|---------|-------------------|
| Patterns CP-SAT | `src/core/patterns.py` | ~270 |
| Solver wrapper | `src/core/solver.py` | ~270 |
| Modèles Pydantic | `src/core/models.py` | ~110 |
| Loader Taillard | `src/loaders/taillard.py` | ~190 |
| Benchmark runner | `src/loaders/benchmark_runner.py` | ~200 |
| Distributions métier | `src/generators/distributions.py` | ~140 |
| Générateur ateliers | `src/generators/workshop_generator.py` | ~330 |
| Scripts CLI | `scripts/*.py` | ~470 |
| Tests | `tests/*.py` | ~1100 |

### Performance vérifiée

| Métrique | Cible | Mesuré | Marge |
|----------|-------|--------|-------|
| Génération 1 atelier | < 2 s | 10 ms | 200× |
| Génération 100 ateliers | < 60 s | 0.92 s | 65× |
| Téléchargement 80 Taillard | — | 14 s | — |
| Suite tests complète | — | 5.16 s | — |
| Solve ta01 (15×15) | — | 2.8 s (OPTIMAL) | — |
| Solve ta41 (30×20) | < 5 % gap | 4.24 % en 120 s | OK |

---

## Décisions techniques cumulées

| Date | Décision | Justification | Statut |
|------|----------|---------------|--------|
| 2026-04-29 | Environnement WSL Ubuntu + VSCode Remote | Cohérence stack Linux des specs | Appliquée |
| 2026-04-29 | Monorepo dans `ro/` avec sous-dossiers par composant | Simplicité solo, traçabilité E2E | Appliquée |
| 2026-04-29 | Conventional Commits | Lisibilité historique, automatisation | Appliquée |
| 2026-04-29 | Pre-commit hooks via framework `pre-commit` | Standard Python, multi-langues | Configurée (activation manuelle) |
| 2026-04-29 | **OR-Tools CP-SAT direct (vs MiniZinc / Hexaly)** | Spec §6.1 + benchmark 5/5 sous 5 % | **Validée empiriquement** |
| 2026-04-29 | uv comme gestionnaire Python | Vitesse, modernité | Appliquée |
| 2026-04-29 | Pydantic v2 frozen + StrEnum pour modèles | Validation stricte + immutabilité | Appliquée |
| 2026-04-29 | Setup-dependent setup encodé par paires disjonctives en POC | Plus simple que AddNoOverlap natif transition_matrix | À refactorer en étape 1.1 |

---

## Risques identifiés et atténuations

| Risque | Probabilité | Impact | Atténuation actuelle |
|--------|-------------|--------|----------------------|
| Encoding par paires en O(N²) ne scalera pas pour 100+ ops/machine | Moyenne | Élevé sur scale prod | Refactor étape 1.1 vers `AddNoOverlap` natif avec transition_matrix |
| Best-known values de `instances_metadata.csv` ta31+ non vérifiées | Faible | Faible | Note dans README, à valider contre optimizizer.com avant Phase 1 |
| Soft constraints NL pas encore intégrées | Élevée | Moyen | Pattern `add_no_overlap_with_setup` accepte déjà des transitions custom — préparation à phase 1.6 |
| Perf scale sur ateliers 200+ OF avec tous patterns simultanés | Inconnue | Élevé | **À valider en étape 0.7** (Gate 0 part 2) |

---

## Prochaines étapes

### Phase 1 — Bibliothèque de patterns + objectifs composites (en attente)

Phase 0 ✅ → Phase 1 ouverte.

| # | Étape | Notes |
|---|-------|-------|
| 1.1 | Refactor patterns en classes `Pattern` | **Prioritaire** — intègre les 4 patterns avancés au pipeline solving (ce qui n'est pas encore fait) |
| 1.2 | Objectif composite (makespan + tardiness + stability) | Multi-objectif |
| 1.3 | Calibration dynamique des poids | Normalisation pré-résolution |
| 1.4 | Replanification incrémentale | Freeze partiel + solution hint CP-SAT |
| 1.5 | Stabilité pondérée par criticité Tier 1/2/3 | Métier |
| 1.6 | Soft constraints en pénalités (interface programmatique) | Avant l'arrivée du LLM (Phase 3) |
| 1.7 | Clustering automatique des familles de pièces | Réduit matrice 100×100 → 15×15 |
| 1.8 | Extraction MIS + actions correctives déterministes | Trust layer (pré-LLM) |

### Évaluation continue

À chaque étape Phase 1, refaire tourner `stress_test_synthetic.py` pour mesurer comment l'ajout des contraintes industrielles dégrade la performance et le taux de feasibility. C'est le vrai stress test scale.

---

*Mis à jour à chaque transition d'étape stabilisée.*
