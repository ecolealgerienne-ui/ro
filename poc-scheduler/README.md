# poc-scheduler

Moteur d'ordonnancement industriel multi-vertical : OR-Tools CP-SAT, pre-flight CSV,
score de confiance, simulation opérationnelle, golden cases versionnés.

Référentiels :
- `../specs-fonctionnelles-v3.md` / `../specs-techniques-v3.md` — spec produit / archi
- `../specs-poc-scripts-v1.md` — spec POC scripts
- `../v0-status.md` — suivi d'avancement structuré
- `../phase-0-report.md`, `../phase-1-report.md`, `../phase-2-report.md` — rapports narratifs
- `../CONTRIBUTING.md` — conventions, dont **§8 architecture multi-verticale**

---

## Prérequis

- WSL (Ubuntu) ou Linux natif
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
| `uv run pytest` | Lance la suite de tests (~ 2 min, 228+ tests) |
| `uv run pytest tests/test_golden_cases.py -v` | Lance les golden cases seuls (< 1 s) |
| `uv run ruff check` | Lint (doit retourner `All checks passed!`) |
| `uv run ruff format` | Format auto |
| `uv run mypy src` | Type checking strict |
| `uv run python scripts/preflight_check.py <csv>` | CLI pre-flight CSV ERP (verticale méca) |
| `uv run python scripts/llm_prompt_builder.py <csv>` | CLI prompt-builder pre-flight + LLM |
| `uv run python scripts/download_benchmarks.py taillard` | Télécharge les instances Taillard |

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
│   ├── core/                   # Engine générique
│   │   ├── models.py           # WorkshopInstance, Job, Operation, Machine, …
│   │   ├── pattern.py          # ABC Pattern + 7 classes (registry)
│   │   ├── patterns.py         # API fonctionnelle (delegates legacy)
│   │   ├── solver.py           # JSSPSolver, SolverResult, validate_schedule
│   │   ├── scoring.py          # Score de confiance (4 métriques + hard gate)
│   │   ├── simulation.py       # Simulation post-hoc (verdict ACCEPT/WARN/REJECT)
│   │   ├── circuit_breaker.py  # Circuit breaker INFEASIBLE (3 retries + MIS)
│   │   ├── pipeline.py         # Pipeline complet (solve → sim → score → decide)
│   │   ├── soft_constraints.py # WeightedObjectivePattern + SoftPenaltyVar (1.6, 1.3, 1.5)
│   │   ├── objectives.py       # CompositeObjectiveSpec + priorités nommées (1.2)
│   │   ├── replanification.py  # FreezeSpec + SolutionHintSpec + derive helper (1.4)
│   │   ├── clustering.py       # agglomerative_cluster engine generic (1.7)
│   │   └── mis.py              # extract_mis_approximate + CorrectiveAction (1.8)
│   ├── preflight/              # Pre-flight CSV générique (vertical-agnostic)
│   ├── loaders/                # Loaders génériques (Taillard, benchmark runner)
│   ├── llm/                    # Couche LLM générique (provider, parsing)
│   │   ├── types.py            # Message, Role
│   │   ├── parsing.py          # extract_json_block (cascade fence/braces)
│   │   └── provider.py         # LLMProvider ABC + FakeLLMProvider + ClaudeAPIProvider
│   ├── agents/                 # Base abstraite des agents LLM
│   │   └── base.py             # Agent ABC single-shot prompt → JSON Pydantic
│   └── verticals/
│       └── mech_workshop/      # Verticale n°1 : sous-traitance mécanique
│           ├── distributions.py
│           ├── generator.py    # Atelier synthétique
│           ├── adapter.py      # Synthetic → WorkshopInstance
│           ├── preflight_config.py    # MECH_COLUMN_PATTERNS, MECH_REQUIRED_*
│           ├── scoring_config.py      # MECH_CONFIDENCE_WEIGHTS
│           ├── simulation_config.py   # MECH_SIMULATION_THRESHOLDS
│           ├── replanification_config.py  # MECH_TIER_WEIGHTS (1.5)
│           ├── clustering.py          # order_distance + cluster_orders_to_families (1.7)
│           ├── soft_translators.py    # 6 translators NL→pénalités CP-SAT (1.6)
│           ├── prompts/               # 5 prompts + 2 schémas (markdown)
│           └── agents/                # 5 agents Phase 3
│               ├── extraction_questionnaire.py  # 3.4
│               ├── extraction_csv.py            # 3.5 (prompt v3 validé)
│               ├── soft_constraints_nl.py       # 3.6 (prompt v1 validé 75/75)
│               ├── explanation.py               # 3.7
│               └── conversational_edit.py       # 3.8
├── scripts/                    # CLI (preflight_check, llm_prompt_builder, …)
├── tests/
│   ├── test_*.py               # Tests unitaires + intégration
│   └── golden_cases/           # Bibliothèque versionnée (engine-level)
│       ├── _schema.py          # Pydantic strict
│       ├── _runner.py          # Loader YAML + exécuteur
│       └── cases/*.yaml        # Cas pilotes
└── data/                       # gitignored (Taillard, instances synthétiques)
```

**Pattern engine ↔ vertical** : l'engine fournit le **mécanisme**, la verticale
fournit la **calibration** (poids, seuils, listes canoniques, patterns regex
ERP). Appliqué pour preflight, scoring, simulation, golden cases.

---

## État d'avancement

Voir `../v0-status.md` pour la vue d'ensemble par phases, et les rapports
narratifs (`../phase-{0,1,2}-report.md`).

**Étape courante : Phase 2 — Trust layer technique.**

- ✅ Phase 0 stabilisée (Gate 0 ✓ : OR-Tools validé sur Taillard)
- ✅ **Phase 1 close** (9/9 étapes traitées : 1.1, 1.2 composite, 1.3 calibration, 1.4 replanif, 1.5 tier, 1.6 soft constraints, 1.7 clustering, 1.8 MIS ; **1.1.opt** ✓ critère assoupli — migration `setup-dependent` vers `add_circuit` livrée, gain mesurable 30 % → 40 % feasibility, target 80 % hors d'atteinte sans redesign solveur)
- ✅ **Phase 2 stabilisée + Gate 1 ✓** (trust layer technique livrée, 0 erreur silencieuse / 20 ateliers tests)
- ✅ **Phase 3 stabilisée** (3.3-3.8 livrés, 13 trials réels OK, prompts validés ; 3.1/3.2 MCP abandonnés)
