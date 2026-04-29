# poc-scheduler

POC OR-Tools CP-SAT pour valider la faisabilité technique du moteur d'ordonnancement industriel.

Référentiel : `../specs-poc-scripts-v1.md`. Suivi d'avancement : `../v0-status.md` (Phase 0).

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
| `uv run pytest` | Lance la suite de tests |
| `uv run ruff check .` | Lint |
| `uv run ruff format .` | Format |
| `uv run mypy src` | Type checking strict |
| `uv run pre-commit run --all-files` | Lance tous les hooks |

---

## Structure

```
poc-scheduler/
├── pyproject.toml          # config projet + outillage
├── .python-version         # version Python (3.11)
├── README.md
├── src/
│   ├── core/               # modèles, solver, patterns CP-SAT
│   ├── loaders/            # parseurs Taillard, runners benchmark
│   └── generators/         # génération d'ateliers synthétiques
├── scripts/                # entry points CLI
├── tests/                  # pytest
└── data/
    ├── taillard/           # téléchargé via script (gitignored)
    └── synthetic/          # généré (gitignored)
```

---

## État d'avancement

Voir `../v0-status.md` Phase 0 pour le détail des étapes 0.1 → 0.7.

**Étape courante : 0.1 — Setup.**

Critère de sortie : `uv sync` et `uv run pytest` passent.
