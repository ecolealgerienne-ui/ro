# Rapport d'avancement Phase 1 — Bibliothèque de patterns + objectifs composites

> Document narratif complémentaire à `v0-status.md` (tracker structuré).
> Documente les résultats concrets, décisions techniques et métriques de chaque étape.
> Mis à jour à chaque étape stabilisée.

**Snapshot : 2026-04-29 — Phase 1.1 stabilisée, 1.1.opt en attente**

---

## Synthèse

| Indicateur | Valeur |
|------------|--------|
| Phase courante | 1 — Bibliothèque de patterns + objectifs composites |
| Étapes Phase 1 stabilisées | **1/8** (1.1 ✅) |
| Étape ajoutée suite à 1.1d | **1.1.opt** ⬜ — migration setup pattern, prioritaire avant Gate 1 |
| Tests automatisés | **168 passants** (~125s exécution complète, dont ~120s en intégration CP-SAT) |
| Pause | Décision de pauser et continuer plus tard |

---

## Étape 1.1 — Refactor patterns en classes `Pattern` + intégration solveur

**Objectif** : transformer les 7 fonctions-patterns du POC en bibliothèque OOP réutilisable, et activer leur application conditionnelle dans le solveur selon les contraintes industrielles présentes dans l'instance.

Découpée en 4 sous-étapes pour stabiliser progressivement.

### 1.1a — Pattern ABC + 7 classes concrètes + registry

**Livrables**
- `src/core/pattern.py` — ABC `Pattern` (name, description, `apply(model, **context)`)
- 7 classes concrètes : `NoOverlapMachine`, `PrecedenceInJob`, `MakespanObjective`, `SequenceDependentSetup`, `QualifiedOperator`, `SharedResourceExclusion`, `UnavailableIntervals`
- Registry `PATTERNS: dict[str, type[Pattern]]` + helpers `get_pattern(name)` / `list_patterns()`
- `src/core/patterns.py` (le module fonction) refactoré en délégates fins — backward-compatible
- 16 tests d'équivalence et de validation

**Statut** : ✅ stabilisée le 2026-04-29.

### 1.1b — Extension `WorkshopInstance` avec contraintes industrielles

**Livrables**
- `Operation` enrichie de `family_id` (default 0) et `qualified_operator_ids` (default `[]`)
- `WorkshopInstance` enrichie de `n_operators`, `transition_matrix`, `shared_resources`, `machine_unavailability` — tous **optionnels avec valeur neutre par défaut**
- 4 properties d'introspection : `has_setup_constraints`, `has_operator_constraints`, `has_shared_resources`, `has_unavailability`
- 5 nouveaux validators Pydantic
- `OPERATION_FAMILY` (7 familles) + `DEFAULT_TRANSITION_MATRIX` (7×7 calibrée méca précision) dans `distributions.py`
- `synthetic_adapter` populate les nouveaux champs (3 flags `enable_setup`/`enable_operators`/`enable_shared_resources`, tous activés par défaut)
- 25 tests (14 modèles + 11 adapter)

**Statut** : ✅ stabilisée le 2026-04-29.

### 1.1c — Intégration des patterns au pipeline du solveur

**Livrables**
- `JSSPSolver.solve()` refactoré : utilise les classes `Pattern` directement
- Application conditionnelle selon les `has_*` properties de l'instance — backward-compatible (Taillard et JSSP nu inchangés)
- `SolverResult.patterns_applied: list[str]` pour traçabilité
- `_compute_horizon` ajoute marge pour setups + indispos
- 6 nouveaux tests E2E (full stack, traçabilité, dégradé, sanity, indispo, non-régression Taillard)
- 168/168 tests passants en 124s

**Statut** : ✅ stabilisée le 2026-04-29.

### 1.1d — Mesure d'impact des patterns

**Livrables**
- `stress_test_synthetic.py` étendu avec `--mode` (basic/setup/operator/shared/full)
- Nouveau sous-commande `compare` : exécute plusieurs modes sur les mêmes seeds et produit un tableau côte-à-côte
- `StressRecord` gagne `mode` et `patterns_count`
- Sortie CSV enrichie

**Résultats** (10 ateliers, profil mixed small/medium/large, budget 60s × 8 workers)

| Mode | Feasible | Rate % | OPTIMAL | Mean time | Max time |
|------|----------|--------|---------|-----------|----------|
| basic | 10/10 | 100.0 | 10 | 0.2s | 0.6s |
| setup | 3/10 | **30.0** | 3 | 44.5s | 62.4s |
| operator | 9/10 | 90.0 | 9 | 8.3s | 62.1s |
| shared | 10/10 | 100.0 | 10 | 0.3s | 0.6s |
| full | 4/10 | **40.0** | 4 | 43.6s | 62.3s |

**Verdict empirique**

- **`setup-dependent` est le seul pattern qui ne scale pas** dans son implémentation actuelle (par paires disjonctives, O(N²) booléens par machine)
- **`operator`** scale très bien (90 %) malgré l'intuition contraire — les intervals optionnels CP-SAT sont efficaces
- **`shared`** scale parfaitement via `add_cumulative` natif
- **`full` ≈ `setup`** car le setup domine la complexité

**Décision actée**

Insertion d'une étape **1.1.opt** prioritaire avant Gate 1 : migration de `SequenceDependentSetupPattern` vers l'encodage natif `AddNoOverlap(transition_matrix=...)` de CP-SAT, comme recommandé par `specs-fonctionnelles-v3.md §7.1`.

Phases 1.2 à 1.6 peuvent continuer en parallèle car indépendantes du setup pattern.

**Statut** : ✅ stabilisée le 2026-04-29.

---

## Métriques cumulées Phase 1.1 (au 2026-04-29)

### Tests automatisés

| Module | Tests | Phase 0 | Phase 1.1 | Total |
|--------|-------|---------|-----------|-------|
| `test_smoke.py` | 2 | 2 | — | 2 |
| `test_models.py` | 21 | 7 | +14 | 21 |
| `test_taillard_loader.py` | 16 | 16 | — | 16 |
| `test_patterns.py` | 32 | 32 | — | 32 |
| `test_pattern_classes.py` | 16 | — | +16 | 16 |
| `test_solver.py` | 8 | 8 | — | 8 |
| `test_benchmark_runner.py` | 9 | 9 | — | 9 |
| `test_generator.py` | 26 | 26 | — | 26 |
| `test_synthetic_adapter.py` | 21 | 10 | +11 | 21 |
| `test_integration.py` | 12 | 6 | +6 | 12 |
| **Total** | **163** | **116** | **+47** | **163** |

Note : 168 reportés pendant exécution, 163 dans la liste — diff potentiellement due à des paramétrages.

### Performance solveur (sur 10 ateliers mixed)

| Pattern actif | Feasibility ≤ 60s | Mean time | Verdict |
|---------------|-------------------|-----------|---------|
| Aucun (basic) | 100 % | 0.2s | référence |
| `setup` | 30 % | 44.5s | ⚠ ne scale pas (encodage par paires) |
| `operator` | 90 % | 8.3s | ✓ scale bien |
| `shared` | 100 % | 0.3s | ✓ scale parfaitement |
| Full stack | 40 % | 43.6s | ⚠ dominé par setup |

---

## Décisions techniques Phase 1

| Date | Décision | Justification | Statut |
|------|----------|---------------|--------|
| 2026-04-29 | Pattern API : ABC avec `apply(model, **context)` | Permet kwargs typés par sous-classe sans hiérarchie complexe | Appliquée |
| 2026-04-29 | Champs industriels optionnels avec defaults neutres | Backward-compat avec Taillard et tests existants | Appliquée |
| 2026-04-29 | Adapter avec flags `enable_*` opt-in | Permet la comparaison de perf en 1.1d | Appliquée |
| 2026-04-29 | Solveur applique conditionnellement via `has_*` properties | Évite les coûts inutiles sur instances JSSP nues | Appliquée |
| 2026-04-29 | Insertion étape 1.1.opt suite aux résultats 1.1d | Setup-dependent par paires confirmé non-scalable empiriquement | Décidée, pas encore appliquée |
| 2026-04-29 | Phases 1.2-1.6 peuvent continuer en parallèle | Toutes indépendantes du setup pattern | À acter au moment de la reprise |

---

## Risques identifiés

| Risque | Probabilité | Impact | Atténuation |
|--------|-------------|--------|-------------|
| Migration setup vers `AddNoOverlap(transition_matrix=...)` plus complexe que prévu | Moyenne | Moyen | Étape 1.1.opt isolée, peut prendre 1-2 sessions sans bloquer le reste |
| L'API Python d'OR-Tools peut ne pas exposer `transition_matrix` directement | Moyenne | Moyen | Fallback : utiliser `cp_model_pb2` directement, ou attendre une nouvelle version d'ortools |
| Le bottleneck setup peut limiter Gate 1 (< 1 erreur silencieuse / 100 ateliers) | Faible | Élevé | 1.1.opt obligatoire avant Gate 1 (Phase 2) |
| Combinaison de tous les patterns + objectif composite (Phase 1.2) peut révéler d'autres bottlenecks | Inconnue | Moyen | Re-run stress test à chaque étape Phase 1 stabilisée |

---

## Prochaines étapes (à reprendre ultérieurement)

### Option recommandée : continuer en parallèle

1. **Phase 1.2** — Objectif composite (makespan + tardiness + stability) — **prioritaire produit**
2. **Phase 1.1.opt** — Migration setup pattern — à insérer avant Gate 1, peut être fait en parallèle ou plus tard
3. **Phase 1.3** — Calibration dynamique des poids
4. ... (1.4-1.8 selon `v0-status.md`)

### Options alternatives discutées

- **Faire 1.1.opt tout de suite** : cohérent avec la discipline "stabilise avant de continuer", mais retarde la valeur produit
- **Pauser et faire un point stratégique** : utile si remise en question du wedge ou de la séquence

À discuter à la reprise.

---

*Mis à jour à chaque transition d'étape stabilisée.*
