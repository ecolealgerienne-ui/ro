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
├── specs-fonctionnelles-v3.md
├── specs-techniques-v3.md
├── specs-poc-scripts-v1.md
├── v0-status.md
├── CONTRIBUTING.md
├── .gitignore
├── .gitattributes
├── .pre-commit-config.yaml
├── poc-scheduler/        # Phase 0 — POC OR-Tools
├── solver-service/       # Phases 1-3 — microservice Python (CP-SAT + agents LLM via tool use Claude API)
├── backend/              # Phase 4 — NestJS API
├── frontend/             # Phase 5 — Next.js chef d'atelier
├── pwa/                  # Phase 6 — PWA opérateur
└── infra/                # Phase 7 — Docker Compose, monitoring, déploiement
```

Les dossiers sont créés au fur et à mesure des phases.

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

### TypeScript / JS
- `eslint` + `prettier`
- `tsc --noEmit` sans warning
- Tests `vitest` ou `jest`

### SQL / migrations
- Migrations Prisma versionnées
- Pas de migration destructive sans procédure de rollback

---

## 8. Architecture multi-verticale (poc-scheduler/src)

Le code applicatif est séparé en deux strates :

```
poc-scheduler/src/
├── core/           # Moteur générique (CP-SAT, modèles, patterns, scoring, simulation)
│   ├── models.py
│   ├── pattern.py / patterns.py
│   ├── solver.py
│   ├── scoring.py            # Phase 2.2 — score de confiance générique
│   └── simulation.py         # Phase 2.3 — simulation opérationnelle générique
├── preflight/      # Pre-flight CSV générique (vertical-agnostic)
├── loaders/        # Loaders génériques (Taillard, runners benchmark)
└── verticals/
    ├── __init__.py
    └── mech_workshop/
        ├── distributions.py      # types machine, matières, opérations
        ├── generator.py          # générateur d'ateliers synthétiques
        ├── adapter.py            # SyntheticWorkshop → WorkshopInstance
        ├── preflight_config.py   # MECH_COLUMN_PATTERNS, MECH_REQUIRED_*
        ├── scoring_config.py     # MECH_CONFIDENCE_WEIGHTS
        └── simulation_config.py  # MECH_SIMULATION_THRESHOLDS
```

**Pattern engine ↔ vertical** : l'engine fournit le **mécanisme** (calcul,
algorithme), la verticale fournit la **calibration** (poids, seuils, listes
canoniques). Appliqué pour preflight, scoring, simulation, golden cases.

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

(Ces checks seront automatisés via pre-commit en Phase 2.)

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
