# poc-scheduler

Moteur d'ordonnancement industriel multi-vertical : OR-Tools CP-SAT, pre-flight
CSV, score de confiance, simulation opérationnelle, golden cases versionnés,
agents LLM + scripts d'intégration backend.

Référentiels :
- `../README.md` — vue d'ensemble du monorepo
- `../docs/specs-fonctionnelles-v3.md` / `../docs/specs-techniques-v3.md` — spec produit / archi
- `../docs/specs-poc-scripts-v1.md` — spec POC scripts
- `../docs/v0-status.md` — suivi d'avancement structuré
- `../phase-{0,1,2,3,4}-report.md` — rapports narratifs par phase
- `../CONTRIBUTING.md` — conventions, dont **§8 architecture multi-verticale**

---

## Prérequis

- WSL (Ubuntu) ou Linux natif (testé aussi macOS)
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) pour la gestion d'environnement et de dépendances

Installation `uv` :
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Installation

Depuis le dossier `poc-scheduler/` :

```bash
uv sync
```

Active l'environnement virtuel implicitement (uv le crée et l'utilise via `uv run`).

---

## Commandes principales

| Commande | Effet |
|----------|-------|
| `uv sync` | Installe / synchronise les dépendances |
| `uv run pytest` | Lance la suite de tests (~ 110 s, 382 tests, 5 skipped Taillard) |
| `uv run pytest -m "not slow"` | Suite rapide (~ 60 s, 377 tests) — adapté CI |
| `uv run pytest tests/test_golden_cases.py -v` | Lance les golden cases seuls (< 1 s) |
| `uv run ruff check` | Lint (doit retourner `All checks passed!`) |
| `uv run ruff format` | Format auto |
| `uv run mypy src` | Type checking strict |
| `uv run python scripts/preflight_check.py <csv>` | CLI pre-flight CSV ERP (verticale méca) |
| `uv run python scripts/llm_prompt_builder.py <csv>` | CLI prompt-builder pre-flight + LLM |
| `uv run python scripts/download_benchmarks.py taillard` | Télécharge les instances Taillard |
| `uv run python scripts/db_worker.py --polling-interval 2` | **Worker DB-as-queue** (Phase 4 J4) — voir « Bridge backend » |
| `uv run uvicorn scripts.preflight_service:app --port 8001` | **Service FastAPI sync** pour pre-flight (Phase 4 J5) |
| `uv run python scripts/seed_via_api.py` | **Seed via API** : reset DB + atelier vitrine + CSVs + solve (idempotent, démo + smoke E2E) |
| `uv run python scripts/seed_via_api.py seed --stress 5` | + 5 ateliers paramétriques (générateur synthétique) |

---

## Architecture (multi-verticale)

Le code applicatif est strictement séparé en deux strates : **engine générique**
(vertical-agnostic) et **verticales métier**. Voir `CONTRIBUTING.md §8` pour
la discipline d'imports et le garde-fou grep.

```
poc-scheduler/
├── pyproject.toml
├── README.md
├── src/
│   ├── core/                       # Engine générique (vertical-agnostic)
│   │   ├── models.py               # WorkshopInstance, Job, Operation, Machine, …
│   │   │                           #   + validate_time_period helper (Sprint 1 audit)
│   │   ├── pattern.py              # ABC Pattern + 7 classes (registry)
│   │   ├── patterns.py             # API fonctionnelle (delegates legacy)
│   │   ├── solver.py               # JSSPSolver, SolverResult, validate_schedule
│   │   ├── scoring.py              # Score de confiance (4 métriques + hard gate)
│   │   ├── simulation.py           # Simulation post-hoc (verdict ACCEPT/WARN/REJECT)
│   │   ├── circuit_breaker.py      # Circuit breaker INFEASIBLE (3 retries + MIS)
│   │   ├── pipeline.py             # Pipeline complet (solve → sim → score → decide)
│   │   ├── soft_constraints.py     # WeightedObjectivePattern + SoftPenaltyVar (1.6, 1.3, 1.5)
│   │   ├── objectives.py           # CompositeObjectiveSpec + priorités nommées (1.2)
│   │   ├── replanification.py      # FreezeSpec + SolutionHintSpec + derive helper (1.4)
│   │   ├── clustering.py           # agglomerative_cluster engine generic (1.7)
│   │   ├── mis.py                  # extract_mis_approximate + CorrectiveAction (1.8)
│   │   └── snapshot_bridge.py      # JSON Prisma ↔ WorkshopInstance Pydantic (Phase 4 J4)
│   ├── preflight/                  # Pre-flight CSV générique (vertical-agnostic)
│   ├── loaders/                    # Loaders génériques (Taillard, benchmark runner)
│   ├── llm/                        # Couche LLM générique (provider, parsing)
│   │   ├── types.py                # Message, Role
│   │   ├── parsing.py              # extract_json_block (cascade fence/braces)
│   │   └── provider.py             # LLMProvider ABC + FakeLLMProvider + ClaudeAPIProvider
│   ├── agents/                     # Base abstraite des agents LLM
│   │   └── base.py                 # Agent ABC single-shot prompt → JSON Pydantic
│   └── verticals/
│       └── mech_workshop/          # Verticale n°1 : sous-traitance mécanique
│           ├── distributions.py
│           ├── generator.py        # Atelier synthétique
│           ├── adapter.py          # Synthetic → WorkshopInstance
│           ├── preflight_config.py     # MECH_COLUMN_PATTERNS, MECH_REQUIRED_*
│           ├── scoring_config.py       # MECH_CONFIDENCE_WEIGHTS
│           ├── simulation_config.py    # MECH_SIMULATION_THRESHOLDS
│           ├── replanification_config.py  # MECH_TIER_WEIGHTS (1.5)
│           ├── clustering.py           # order_distance + cluster_orders_to_families (1.7)
│           ├── soft_translators.py     # 6 translators NL → pénalités CP-SAT (1.6)
│           ├── prompts/                # 5 prompts + 2 schémas (markdown)
│           └── agents/                 # 5 agents Phase 3
│               ├── extraction_questionnaire.py  # 3.4
│               ├── extraction_csv.py            # 3.5 (prompt v3 validé)
│               ├── soft_constraints_nl.py       # 3.6 (prompt v1 validé 75/75)
│               ├── explanation.py               # 3.7
│               └── conversational_edit.py       # 3.8
├── scripts/                        # CLI + bridges backend
│   ├── preflight_check.py          # CLI pre-flight standalone
│   ├── llm_prompt_builder.py       # CLI pre-flight + prompt LLM
│   ├── download_benchmarks.py      # Loader Taillard
│   ├── stress_test_synthetic.py    # Benchmark scale par mode (1.1d)
│   ├── db_worker.py                # ★ Phase 4 J4 — worker DB-as-queue solves
│   └── preflight_service.py        # ★ Phase 4 J5 — FastAPI sync pour preflight
├── tests/
│   ├── test_*.py                   # Tests unitaires + intégration (382 tests)
│   └── golden_cases/               # Bibliothèque versionnée (engine-level)
│       ├── _schema.py              # Pydantic strict
│       ├── _runner.py              # Loader YAML + exécuteur
│       └── cases/*.yaml            # Cas pilotes
└── data/                           # gitignored (Taillard, instances synthétiques)
```

**Pattern engine ↔ vertical** : l'engine fournit le **mécanisme**, la verticale
fournit la **calibration** (poids, seuils, listes canoniques, patterns regex
ERP). Appliqué pour preflight, scoring, simulation, clustering, replanification,
MIS, golden cases. Audité 11 fois consécutives (Sprint 1, commit `278845c`,
verticalité tenue à 92 %).

---

## Bridge avec le backend (Phase 4)

Deux scripts dans `scripts/` font le pont avec le backend NestJS, selon le
profil de la tâche :

### `db_worker.py` — DB-as-queue pour solves (10-60 s)

Le worker polle `solve_jobs WHERE status='pending'` toutes les 2 s, claim
atomique via `FOR UPDATE SKIP LOCKED`, exécute le pipeline complet, écrit le
résultat. Multi-workers safe sans Redis.

```bash
export DATABASE_URL="postgresql://ro_user:ro_dev_password@localhost:5432/ro_dev"
uv run python scripts/db_worker.py --polling-interval 2
```

Architecture :
```
Backend → INSERT solve_jobs (status=pending) → ──┐
                                                 ▼
                              ┌──── poll(2s) FOR UPDATE SKIP LOCKED ────┐
                              │                                         │
                              ▼                                         │
                    Worker Python claim →                               │
                    instance_from_snapshot() →                          │
                    run_pipeline() →                                    │
                    UPSERT schedules + UPDATE solve_jobs (done) ────────┘
```

Le bridge `src/core/snapshot_bridge.py::instance_from_snapshot` traduit le
snapshot JSON Prisma (UUID, camelCase) en `WorkshopInstance` Pydantic (indices
entiers, snake_case) pour passer au solveur.

### `preflight_service.py` — FastAPI synchrone pour pre-flight (~1 s)

Mini service uvicorn + FastAPI qui expose `POST /preflight` (multipart) wrappant
`src/preflight/run_preflight()` avec calibration `mech_workshop`. Le backend
forwarde l'upload CSV via `fetch` natif Node 22.

```bash
uv run uvicorn scripts.preflight_service:app --port 8001
# → http://localhost:8001/health
```

Pourquoi sync (pas DB-as-queue) : pre-flight rapide, l'overhead de polling n'a
pas de sens. Pattern HTTP bloquant suffit.

Détails : [`../docs/phase-4-report.md`](../docs/phase-4-report.md) jalons J4 et J5.

---

## État d'avancement

Voir `../docs/v0-status.md` pour la vue d'ensemble par phases, et les rapports
narratifs (`../phase-{0,1,2,3,4}-report.md`).

- ✅ **Phase 0 stabilisée** — Gate 0 ✓ : OR-Tools validé sur Taillard (5/5 instances < 5 % gap)
- ✅ **Phase 1 close** (9/9 étapes traitées)
  - 1.1, 1.2 composite, 1.3 calibration, 1.4 replanif, 1.5 tier, 1.6 soft constraints, 1.7 clustering, 1.8 MIS ✅
  - **1.1.opt** ✓ critère assoupli — migration `setup-dependent` vers
    `add_circuit` livrée, gain mesurable 30 % → 40 % feasibility ; target 80 %
    hors d'atteinte sans redesign solveur (cf. `../docs/phase-1-report.md`)
- ✅ **Phase 2 stabilisée + Gate 1 ✓** — trust layer technique, 0 erreur silencieuse sur 20 ateliers tests
- ✅ **Phase 3 stabilisée** — 3.3-3.8 livrés (13 trials réels OK, prompts validés) ; 3.1/3.2 MCP abandonnés
- ✅ **Phase 4 stabilisée V1** — `scripts/db_worker.py` + `scripts/preflight_service.py` + `src/core/snapshot_bridge.py` livrés

---

## Statut audit (Sprint 1, commit `278845c`)

Audit complet du codebase mené sur 4 axes (verticalité, gestion d'erreurs,
qualité de code, tests + architecture). Score global : **B+**.

| Axe | Note | Verdict |
|-----|------|---------|
| Verticalité | A- | 92 %, fuites mineures docstrings (corrigées Sprint 1) |
| Gestion d'erreurs | B | 4 critiques + 6 majeurs identifiés, structurellement bon |
| Qualité code | B+ | 1 critique + 5 majeurs, conventions excellentes |
| Tests | B | 382 passants, fragility timing + couplage solver |
| Architecture | A- | Aucun cycle, `__init__.py` propres, 1 god module signalé |

Sprint 1 livré : `extra="forbid"` sur 24 BaseModel, factorisation
`validate_time_period`, fuites docstrings nettoyées, guards `Job.operations`,
test trivial supprimé. Sprint 2 (refactors moyens M1-M3, M11) reporté
post-Phase 5.

Détails dans le journal des décisions de `../docs/v0-status.md`.
