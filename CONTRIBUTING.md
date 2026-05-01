# CONTRIBUTING

> Conventions de travail pour le projet.
> Document à respecter pour tous les commits, branches, revues.

---

## 1. Environnement de dev

- **Système** : WSL (Ubuntu) sur Windows
- **Éditeur** : VSCode avec extension *Remote - WSL*
- **Shell** : bash (WSL)
- **Python** : 3.11+ via [`uv`](https://docs.astral.sh/uv/)
- **Node** : 20 LTS via `nvm` ou `volta`
- **Docker** : Docker Desktop avec intégration WSL2 (phases 4+)

Installation `uv` :
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Structure du dépôt (monorepo)

```
ro/
├── README.md                              # vue d'ensemble (point d'entrée)
├── CONTRIBUTING.md                        # ce fichier
├── v0-status.md                           # tracker structuré par étape
├── phase-{0,1,2,3,4}-report.md            # rapports narratifs par phase
├── specs-fonctionnelles-v3.md             # spec produit
├── specs-techniques-v3.md                 # spec architecture
├── specs-poc-scripts-v1.md                # spec scripts POC
├── guide-entretiens-decouverte-phase0.md
├── .gitignore  .gitattributes  .pre-commit-config.yaml
│
├── poc-scheduler/        # Phases 0-3 — moteur Python (CP-SAT + agents LLM)
│                          #   + scripts d'intégration Phase 4 (db_worker, preflight_service)
├── backend/               # Phase 4 — NestJS API + Prisma + Postgres
├── frontend/              # Phase 5 — Next.js + Tailwind + shadcn (chef d'atelier)
├── mockups/               # Mockups V0 (jetables, archivés en référence)
├── pwa/                   # Phase 6 — PWA opérateur (à créer)
└── infra/                 # Phase 7 — Docker Compose, monitoring, déploiement
```

Les dossiers sont créés au fur et à mesure des phases. **Note Phase 1-3** : le
microservice Python (CP-SAT + agents LLM) reste dans `poc-scheduler/`, il n'y a
pas eu de scission `solver-service/` séparé. La Phase 4 a ajouté les scripts
d'intégration backend (`scripts/db_worker.py`, `scripts/preflight_service.py`)
sous `poc-scheduler/scripts/`. La Phase 5 a converti les mockups V0 (HTML
statique dans `mockups/`) en vraies pages Next.js dans `frontend/` ; les
mockups restent en référence jetable.

---

## 3. Stratégie de branches

| Branche | Rôle |
|---------|------|
| `main` | État stable, releasable |
| `dev` | Intégration continue, base des features |
| `feat/<phase>.<étape>-<slug>` | Une étape du `v0-status.md` (ex: `feat/0.1-setup-poc`) |
| `fix/<slug>` | Correctif ciblé |
| `chore/<slug>` | Outillage, infra, refacto sans logique |
| `docs/<slug>` | Documentation seule |

**Règles :**
- Pas de commit direct sur `main`. Merges via PR uniquement.
- `dev` reçoit les feature branches via PR (squash merge ou merge commit selon l'étape).
- Une feature branch couvre **une seule étape** du `v0-status.md`. Pas de branches XXL.
- Branche supprimée après merge.

---

## 4. Convention de commits — Conventional Commits

Format : `<type>(<scope>): <sujet>`

**Types autorisés :**
- `feat` — nouvelle fonctionnalité
- `fix` — correctif de bug
- `refactor` — refacto sans changement de comportement
- `perf` — optimisation perf
- `test` — ajout/modification de tests
- `docs` — documentation
- `chore` — outillage, build, deps
- `ci` — pipelines CI/CD
- `style` — formatage (rare, devrait être automatique)
- `build` — système de build

**Scopes recommandés** (selon composant) :
`poc`, `solver`, `agents`, `llm`, `backend`, `frontend`, `pwa`, `infra`, `docs`, `tests`.

**Exemples :**
```
feat(poc): add Taillard benchmark loader
fix(solver): correct off-by-one in setup time matrix
test(poc): add golden cases for NoOverlap pattern
docs: update v0-status.md with phase 0.4 result
chore: bump ortools to 9.11
```

**Sujet :**
- Impératif présent (`add`, pas `added` ni `adds`)
- Pas de point final
- Première lettre minuscule (sauf nom propre)
- Max 72 caractères

**Corps (optionnel)** : explique le *pourquoi*, pas le *quoi*.

---

## 5. Pull Requests

**Titre** : suit la convention de commits (`feat(poc): ...`).

**Description** doit contenir :
- Lien vers l'étape `v0-status.md` couverte (ex: `Couvre étape 0.1`)
- Critère de sortie atteint ou non
- Tests joués (commandes copiables)
- Captures si UI

**Avant de demander la review :**
- [ ] Tous les tests passent (`uv run pytest`, `npm test` selon scope)
- [ ] `pre-commit run --all-files` passe
- [ ] `mypy --strict` (Python) ou `tsc --noEmit` (TS) sans erreur
- [ ] `v0-status.md` mis à jour si l'étape est terminée

**Stratégie de merge :** squash merge par défaut (1 PR = 1 commit dans `dev`).

---

## 6. Pre-commit hooks

Configurés dans `.pre-commit-config.yaml`. Activation :
```bash
uv pip install pre-commit
pre-commit install
```

Hooks actifs :
- `trailing-whitespace`, `end-of-file-fixer`
- `check-yaml`, `check-toml`, `check-json`
- `mixed-line-ending` (force LF)
- `check-added-large-files` (max 1 MB)
- `ruff` (lint + format Python)

À ajouter quand le code arrive : `mypy`, `eslint`, `prettier`.

---

## 7. Qualité de code

### Python
- `ruff check` + `ruff format` (config dans `pyproject.toml` du sous-projet)
- `mypy --strict` sur le code applicatif
- Type hints obligatoires sur signatures publiques
- Docstrings style Google sur fonctions publiques
- Tests `pytest` — couverture > 80% sur modules critiques

### TypeScript / JS (backend NestJS)
- `eslint` + `prettier` (configs dans `backend/`)
- `tsc --noEmit` sans warning (scripts `npm run typecheck`)
- Tests `jest` + `supertest` pour les e2e (`npm run test:e2e`)
- Strict mode TypeScript : `noImplicitAny`, `strictNullChecks`,
  `forceConsistentCasingInFileNames`
- DTO via `class-validator` + `ValidationPipe` global avec
  `whitelist: true, forbidNonWhitelisted: true` (équivalent Pydantic
  `extra="forbid"` côté API)
- Pas de `any` non justifié — préférer `unknown` + narrowing

### TypeScript / JS (frontend Next.js)
- `eslint` (via `next lint`) + `prettier` + `prettier-plugin-tailwindcss`
  (tri auto des classes Tailwind)
- `tsc --noEmit` strict (scripts `npm run typecheck`)
- Path alias `@/*` → racine du projet (`@/components/...`, `@/lib/...`)
- **Server Components par défaut**, `'use client'` uniquement quand
  nécessaire (interactivité, hooks TanStack Query, state local)
- Composants shadcn dans `frontend/components/ui/` — **manuels** (config
  `components.json` + copie inline depuis ui.shadcn.com), pas via
  `npx shadcn add` car l'environnement CI/dev ne supporte pas l'interactif
- API client : `lib/api/client.ts` (fetch natif Node 22 + `ApiError`),
  `lib/api/types.ts` (miroirs Prisma maintenus à la main, **synchroniser
  manuellement** si le schéma backend change), `lib/api/hooks.ts`
  (TanStack Query)
- Pas d'auth V1 (cohérent avec backend, différé Phase 7)
- TanStack Query : `staleTime: 30s` par défaut, retry skip 4xx,
  refetch interval intelligent (poll 2s seulement si solve-jobs
  pending/running détectés)

### SQL / migrations
- Migrations Prisma versionnées (`backend/prisma/migrations/`)
- Pas de migration destructive sans procédure de rollback
- Naming DB : tables `snake_case` au pluriel (`workshops`, `solve_jobs`),
  colonnes `snake_case` mappées via `@map()` aux propriétés `camelCase` Prisma
- IDs : UUID v4 (`@db.Uuid`) + indices entiers métier (`machine_id_int`,
  `job_id_int`) pour cohérence avec l'engine Python (cf. §8)

---

## 8. Architecture multi-verticale (poc-scheduler/src)

Le code applicatif est séparé en deux strates : **engine générique** et
**verticales métier**. Pattern audité 11 fois consécutives (verticalité tenue
à 92 %, audit Sprint 1).

```
poc-scheduler/src/
├── core/                     # Moteur générique (vertical-agnostic)
│   ├── models.py             # WorkshopInstance + validate_time_period helper
│   ├── pattern.py / patterns.py     # ABC Pattern + 7 classes
│   ├── solver.py             # JSSPSolver, validate_schedule
│   ├── scoring.py            # Phase 2.2 — score de confiance générique
│   ├── simulation.py         # Phase 2.3 — simulation opérationnelle générique
│   ├── circuit_breaker.py    # Phase 2.4 — circuit breaker INFEASIBLE
│   ├── pipeline.py           # Phase 2.5 — pipeline complet
│   ├── soft_constraints.py   # Phase 1.6 — SoftPenaltyVar + WeightedObjective
│   ├── objectives.py         # Phase 1.2 — CompositeObjectiveSpec
│   ├── replanification.py    # Phase 1.4 — FreezeSpec + SolutionHintSpec
│   ├── clustering.py         # Phase 1.7 — agglomerative_cluster
│   ├── mis.py                # Phase 1.8 — extract_mis_approximate
│   └── snapshot_bridge.py    # Phase 4 J4 — JSON Prisma ↔ WorkshopInstance
├── preflight/                # Pre-flight CSV générique (vertical-agnostic)
├── loaders/                  # Loaders génériques (Taillard, benchmark)
├── llm/                      # Couche LLM générique (provider, parsing)
├── agents/                   # Base abstraite des agents LLM
└── verticals/
    ├── __init__.py
    └── mech_workshop/        # Verticale n°1 : sous-traitance mécanique
        ├── distributions.py
        ├── generator.py / adapter.py
        ├── preflight_config.py     # MECH_COLUMN_PATTERNS, MECH_REQUIRED_*
        ├── scoring_config.py       # MECH_CONFIDENCE_WEIGHTS
        ├── simulation_config.py    # MECH_SIMULATION_THRESHOLDS
        ├── replanification_config.py  # MECH_TIER_WEIGHTS (1.5)
        ├── clustering.py           # order_distance + cluster_orders_to_families
        ├── soft_translators.py     # 6 translators NL → CP-SAT
        ├── prompts/                # 5 prompts + 2 schémas (markdown)
        └── agents/                 # 5 agents Phase 3 (3.4-3.8)
```

Les **scripts d'intégration backend** (`scripts/db_worker.py`,
`scripts/preflight_service.py`) consomment l'engine + une verticale (V1 :
`mech_workshop`). Ils sont eux-mêmes vertical-agnostic dans leur logique
(SQL + HTTP + I/O), la verticale est sélectionnée à l'instanciation. À
l'arrivée d'une 2ᵉ verticale, on choisira via discriminant
`Workshop.metadata` ou colonne dédiée `vertical_kind`.

**Pattern engine ↔ vertical** : l'engine fournit le **mécanisme** (calcul,
algorithme), la verticale fournit la **calibration** (poids, seuils, listes
canoniques). Appliqué pour preflight, scoring, simulation, clustering,
replanification, MIS, soft constraints, golden cases.

### Règles d'imports (à respecter strictement)

| Source | Peut importer | Ne peut PAS importer |
|--------|---------------|----------------------|
| `src.core.*` | stdlib, 3rd-party | `src.preflight.*`, `src.verticals.*`, `src.loaders.*` |
| `src.preflight.*` | stdlib, 3rd-party | `src.verticals.*`, `src.core.*` |
| `src.loaders.*` | `src.core.*` | `src.verticals.*` |
| `src.verticals.<X>.*` | `src.core.*`, `src.preflight.*`, `src.loaders.*`, modules de la **même** verticale | `src.verticals.<Y>.*` (autre verticale) |
| `scripts/*`, `tests/*` | tout | — |

**Principes :**
- Le moteur (`core` + `preflight` + `loaders`) ne connaît AUCUNE verticale.
- Les verticales sont **indépendantes** entre elles. Pour partager du code, on
  remonte dans `core/` ou un nouveau module générique — pas d'import croisé.
- Toute config métier (patterns regex, distributions, listes canoniques) vit
  dans `verticals/<nom>/`, jamais dans le moteur.
- Ajouter une verticale = créer `src/verticals/<nouveau>/` avec son `__init__.py`.

### Garde-fou (à exécuter avant commit / en CI)

```bash
# Aucun import depuis src/core/ vers src/verticals/ ou src/preflight/
! grep -RE "^from src\.(verticals|preflight)" poc-scheduler/src/core/

# Aucun import depuis src/preflight/ vers src/verticals/ ou src/core/
! grep -RE "^from src\.(verticals|core)" poc-scheduler/src/preflight/

# Aucun import croisé entre verticales
! grep -RE "^from src\.verticals\.[a-z_]+" poc-scheduler/src/verticals/ \
    | grep -v "$(basename $(dirname %))"
```

Audit étendu (Sprint 1, post-Phase 4) : pas seulement les imports, mais aussi
les **fuites sémantiques dans les docstrings** de l'engine. Cibles à éviter :
mention `mech_workshop` dans `src/core/`, terminologie métier hors-engine
(« chef d'atelier », « OF », « atelier ») dans les commentaires de
mécanismes universels.

(Ces checks seront automatisés via pre-commit en Phase 7 sécurité prod.)

---

## 9. Ce qu'on ne fait pas

- Pas de force push sur `main` ni `dev`
- Pas de `--no-verify` pour bypass les hooks
- Pas de commit de secrets, `.env`, dumps DB
- Pas de fichiers binaires > 1 MB sans Git LFS (à mettre en place si besoin)
- Pas de TODO sans ticket / mention `v0-status.md`

---

## 10. Mise à jour du `v0-status.md`

À chaque transition d'étape :
- Statut mis à jour (`⬜ → 🟡 → 🔵 → ✅`)
- Date de démarrage et/ou fin renseignée (format `YYYY-MM-DD`)
- Notes synthétiques : décisions, blocages, métriques de sortie

À chaque décision structurante : ajouter une ligne dans le **Journal des décisions**.

À chaque retour en arrière sur une phase antérieure : ajouter une ligne dans le **Journal des retours en arrière**.

---

*Document vivant — à amender quand les conventions évoluent.*
