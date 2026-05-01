# Spec technique — Scripts POC pour validation moteur OR-Tools

> Document à destination de Claude Code pour implémentation
> Cible : 2 scripts Python autonomes pour démarrer le POC du SaaS d'ordonnancement
> Contexte projet : voir `specs-fonctionnelles-v3.md` et `specs-techniques-v3.md`

---

## Vue d'ensemble

Deux scripts Python indépendants à livrer dans un même repo :

1. **`taillard_loader.py`** — charge les benchmarks JSSP académiques publics, les modélise en CP-SAT, mesure la performance contre les optima connus.
2. **`workshop_generator.py`** — génère des ateliers de mécanique de précision synthétiques avec contraintes réalistes, exporte au format compatible avec le solveur.

Les deux scripts partagent une même base de code pour la modélisation CP-SAT (DRY).

---

## Structure du repo cible

```
poc-scheduler/
├── README.md
├── pyproject.toml
├── .gitignore
├── data/
│   ├── taillard/             # téléchargé via script
│   ├── dmu/                  # optionnel
│   └── synthetic/            # généré
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py         # dataclasses : Job, Operation, Machine, Workshop
│   │   ├── solver.py         # wrapper CP-SAT commun
│   │   └── patterns.py       # patterns CP-SAT réutilisables
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── taillard.py       # parsing fichiers Taillard
│   │   └── benchmark_runner.py
│   └── generators/
│       ├── __init__.py
│       ├── workshop_generator.py
│       └── distributions.py  # paramètres statistiques métier
├── scripts/
│   ├── download_benchmarks.sh    # télécharge Taillard + DMU
│   ├── run_taillard_benchmark.py # entry point script 1
│   └── generate_workshops.py     # entry point script 2
└── tests/
    ├── test_taillard_loader.py
    ├── test_solver.py
    └── test_generator.py
```

---

## Prérequis techniques

### Environnement Python

- **Version :** Python 3.11+
- **Gestionnaire :** `uv` (rapide, moderne, recommandé) ou `poetry`
- **Pas de venv classique** — utiliser uv pour la rapidité d'installation

### Dépendances

```toml
[project]
dependencies = [
    "ortools>=9.10",
    "pydantic>=2.0",
    "click>=8.1",          # CLI
    "rich>=13.0",          # UI console (tableaux, progress)
    "numpy>=1.26",
    "pandas>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "ruff>=0.4",
    "mypy>=1.10",
]
```

---

## Datasets publics — comment les récupérer

### Taillard benchmark (priorité 1)

**Source officielle :** http://mistic.heig-vd.ch/taillard/problemes.dir/ordonnancement.dir/ordonnancement.html

**Mirror GitHub fiable :**
- https://github.com/tamy0612/JSPLIB (collection de benchmarks JSSP)
- Format texte simple, parseur facile

**Structure attendue d'un fichier Taillard (`ta01.txt` par exemple) :**

```
Nb of jobs, Nb of Machines, Time seed, Machine seed, Upper bound, Lower bound :
   15  15 1166510396  164000672    1231    1231
Times
54 34 61 ...
83 70 47 ...
...
Machines
8 1 6 ...
13 12 9 ...
...
```

**80 instances disponibles** (ta01 à ta80), tailles allant de 15×15 à 100×20.

**Pour démarrer :** 5 instances suffisent (`ta01`, `ta11`, `ta21`, `ta31`, `ta41`).

### DMU benchmark (priorité 2, optionnel)

**Source :** https://web.archive.org/web/*/http://web.cba.neu.edu/~msolomon/problems.htm

**Mirror :** également présent dans JSPLIB

### Lawrence (LA) benchmark (priorité 3, optionnel)

**Source :** OR-Library de Beasley
**URL :** http://people.brunel.ac.uk/~mastjjb/jeb/orlib/jobshopinfo.html
**40 instances** plus petites, utiles pour tests rapides.

### Optima connus (pour validation)

Le fichier `instances_metadata.csv` (à inclure dans le repo) doit contenir, pour chaque instance :

```csv
name,n_jobs,n_machines,best_known_makespan,source_optimum
ta01,15,15,1231,proven_optimal
ta02,15,15,1244,proven_optimal
...
```

**Source pour ces valeurs :** https://optimizizer.com/TA.php (référence communauté pour les optima Taillard).

### Script de téléchargement

`scripts/download_benchmarks.sh` doit :

1. Créer `data/taillard/` si absent
2. Télécharger les 80 instances Taillard depuis le mirror GitHub JSPLIB (https://github.com/tamy0612/JSPLIB) via `curl` ou `wget`
3. Vérifier les checksums (md5 dans un fichier `data/taillard/checksums.md5`)
4. Afficher un message clair : "✓ 80 instances Taillard téléchargées"
5. Idem pour DMU si flag `--with-dmu` passé

**Fallback :** si le mirror principal est indisponible, prévoir une URL alternative et l'afficher dans la doc.

---

## Script 1 : `taillard_loader.py`

### Objectif fonctionnel

Charger une instance Taillard, la modéliser en CP-SAT via le moteur commun du repo, lancer le solveur avec un budget temps configurable, comparer le résultat à l'optimum connu, afficher un rapport.

### Responsabilités

#### Module `loaders/taillard.py`

```python
def parse_taillard_file(path: Path) -> WorkshopInstance:
    """
    Parse un fichier Taillard au format texte.
    Retourne une WorkshopInstance avec :
    - n_jobs, n_machines
    - matrice times (n_jobs × n_machines)
    - matrice machines_order (n_jobs × n_machines)
    - best_known_makespan (depuis instances_metadata.csv)
    """
```

#### Module `core/models.py`

```python
@dataclass
class Operation:
    job_id: int
    sequence_idx: int       # 0-indexed dans la gamme du job
    machine_id: int
    duration: int           # minutes

@dataclass
class Job:
    job_id: int
    operations: list[Operation]
    
@dataclass
class Machine:
    machine_id: int
    name: str = None        # généré si non fourni
    
@dataclass
class WorkshopInstance:
    name: str
    jobs: list[Job]
    machines: list[Machine]
    best_known_makespan: int | None = None
    metadata: dict = field(default_factory=dict)
```

#### Module `core/solver.py`

```python
class JSSPSolver:
    """Solveur CP-SAT pour le Job-Shop Scheduling Problem classique."""
    
    def __init__(
        self,
        time_limit_seconds: int = 60,
        num_workers: int = 8,
        log_search_progress: bool = False
    ): ...
    
    def solve(self, instance: WorkshopInstance) -> SolverResult:
        """
        Construit le modèle CP-SAT, lance la résolution.
        Retourne SolverResult avec :
        - status (OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN)
        - makespan trouvé
        - schedule (liste d'assignations)
        - solve_time_seconds
        - objective_bound (pour calcul gap)
        """
```

#### Module `core/patterns.py`

Implémenter au minimum :

- `add_no_overlap_machine(model, intervals_per_machine)` — contrainte NoOverlap par machine
- `add_precedence_in_job(model, intervals_per_job)` — précédence des opérations d'un même job
- `make_makespan_objective(model, end_vars)` — objectif minimisation makespan

Ces patterns sont les briques de base qui seront étendues plus tard pour les soft constraints, sequence-dependent setup, etc.

#### Script entry point `scripts/run_taillard_benchmark.py`

CLI avec `click`. Usage cible :

```bash
# Solver une instance unique
python scripts/run_taillard_benchmark.py solve ta01 --time-limit 60

# Solver un batch
python scripts/run_taillard_benchmark.py batch --instances ta01,ta11,ta21 --time-limit 120

# Solver tous les ta01 à ta20
python scripts/run_taillard_benchmark.py batch --range ta01-ta20 --time-limit 60 --output results.csv
```

**Sortie console attendue :** tableau `rich` avec colonnes `instance | n_jobs | n_machines | best_known | found | gap_% | time_s | status`.

**Sortie fichier (CSV optionnel) :** mêmes colonnes pour analyse.

### Critères de succès du script 1

- Charge correctement les 80 instances Taillard (test : tous les fichiers parsent sans erreur)
- Sur 5 instances de référence (ta01, ta11, ta21, ta31, ta41) avec budget 120s : **gap < 5% par rapport à l'optimum connu**
- Sortie lisible et exportable
- Code propre, typé (mypy strict), testé unitairement

### Tests unitaires obligatoires

- `test_taillard_loader.py` : parser sur fichiers ta01, ta31, ta51 (tailles différentes)
- `test_solver.py` : résolution d'un mini-problème jouet (3 jobs × 3 machines) avec optimum connu
- Tests des patterns CP-SAT individuellement

---

## Script 2 : `workshop_generator.py`

### Objectif fonctionnel

Générer des ateliers de mécanique de précision synthétiques **réalistes** (vs. les benchmarks académiques propres), paramétrables, avec des distributions calibrées sur la réalité française du segment ICP.

L'objectif est double : disposer de cas pour tester le solveur en stress, et constituer la base initiale des golden cases du trust layer.

### Paramètres de génération

```python
@dataclass
class GenerationParams:
    # Taille atelier
    n_machines_min: int = 5
    n_machines_max: int = 25
    n_operators_min: int = 3
    n_operators_max: int = 30
    
    # Charge production
    n_jobs_min: int = 50
    n_jobs_max: int = 300
    
    # Horizon de planning (jours ouvrés)
    planning_horizon_days: int = 10
    
    # Caractéristiques métier
    machine_types_distribution: dict[str, float] = None  # cf. ci-dessous
    materials_distribution: dict[str, float] = None      # cf. ci-dessous
    
    # Complexité gammes
    operations_per_job_min: int = 2
    operations_per_job_max: int = 8
    
    # Sequence-dependent setup
    enable_setup_times: bool = True
    setup_time_matrix_density: float = 0.7  # % de paires avec setup non-nul
    
    # Soft constraints (préférences)
    n_soft_constraints_min: int = 0
    n_soft_constraints_max: int = 5
    
    # Calendar / disponibilité
    enable_calendars: bool = True
    n_shifts: int = 1                 # 1, 2 ou 3 équipes
    
    # Exigences certification
    certification_level: Literal["none", "EN9100_lite", "EN9100_strict"] = "none"
    
    # Reproductibilité
    seed: int = 42
```

### Distributions métier réalistes

#### Types de machines (mécanique de précision)

```python
MACHINE_TYPES_DEFAULT = {
    "tour_cn_2_axes": 0.20,
    "tour_cn_4_axes": 0.10,
    "fraiseuse_cn_3_axes": 0.25,
    "fraiseuse_cn_5_axes": 0.15,
    "centre_usinage": 0.10,
    "rectifieuse_cylindrique": 0.05,
    "rectifieuse_plane": 0.05,
    "perceuse_cn": 0.05,
    "machine_controle_3D": 0.05,
}
```

#### Matières

```python
MATERIALS_DEFAULT = {
    "aluminium_2017": 0.15,
    "aluminium_7075_T6": 0.20,
    "acier_inox_316L": 0.15,
    "acier_inox_304": 0.10,
    "acier_42CrMo4": 0.10,
    "titane_TA6V": 0.10,
    "laiton_CuZn40": 0.05,
    "bronze": 0.05,
    "plastique_technique": 0.05,
    "autres": 0.05,
}
```

#### Opérations canoniques

```python
OPERATIONS_CANONICAL = [
    "tournage_ebauche",
    "tournage_finition",
    "fraisage_ebauche",
    "fraisage_finition",
    "fraisage_5axes",
    "percage",
    "taraudage",
    "rectification_cylindrique",
    "rectification_plane",
    "controle_dimensionnel",
    "ebavurage",
    "marquage",
    "lavage",
    "traitement_thermique_externe",  # sous-traitance
    "anodisation_externe",            # sous-traitance
]
```

Chaque opération a une **compatibilité machine** (table de mapping fournie en code) et un **temps de cycle moyen + écart-type** par matière.

#### Compatibilité opérations × machines

À fournir en table dans `generators/distributions.py`. Exemple :

```python
OPERATION_MACHINE_COMPAT = {
    "tournage_ebauche": ["tour_cn_2_axes", "tour_cn_4_axes"],
    "fraisage_5axes": ["fraiseuse_cn_5_axes", "centre_usinage"],
    "rectification_cylindrique": ["rectifieuse_cylindrique"],
    # ...
}
```

#### Sequence-dependent setup (matrice de transition)

Réaliste pour la mécanique :
- Changement de matière : 15-45 minutes selon les matières (matrice à fournir)
- Changement de pièce même matière : 5-15 minutes
- Pas de changement (même série) : 0-2 minutes

Distribution log-normale autour de ces moyennes pour capturer la variabilité.

### Soft constraints générées

Pool de phrases-types injectables (en français, en langage naturel pour test du LLM) :

```python
SOFT_CONSTRAINTS_POOL = [
    "Éviter de faire tourner la machine {machine} la nuit",
    "Regrouper si possible les pièces de la même matière {material}",
    "L'opérateur {operator} préfère ne pas faire de {operation_type}",
    "Privilégier la machine {machine_a} sur {machine_b} si les deux sont disponibles",
    "Les OF du client {client} doivent finir avant {deadline}",
    "Éviter de fragmenter les séries de plus de {n} pièces",
    "Limiter à {n} setups par jour sur la machine {machine}",
    "Les opérations de finition se font de préférence en équipe du matin",
]
```

Le générateur en pioche aléatoirement N selon `n_soft_constraints_min/max` et substitue les paramètres avec des valeurs cohérentes du contexte généré.

### Contraintes physiques implicites injectées

Pour tester la gestion des partages de ressources, le générateur peut injecter :

```python
@dataclass
class SharedResource:
    resource_name: str           # "aspiration_atelier_1", "alimentation_400V_zone_B"
    machines_concerned: list[int]
    max_concurrent: int = 1      # nombre max de machines actives simultanément
```

**Probabilité d'injection :** 30% des ateliers générés en ont au moins un partage de ressource. C'est ce qui crée la complexité réaliste.

### Distribution des criticités client

```python
CLIENT_TIERS = {
    "Tier_1_strategic": 0.15,    # Safran, Airbus direct, etc.
    "Tier_2_important": 0.35,
    "Tier_3_standard": 0.50,
}
```

Avec poids dans la fonction objectif : Tier 1 = 10, Tier 2 = 5, Tier 3 = 1.

### Format de sortie

#### Format JSON principal (un fichier par atelier)

```json
{
  "metadata": {
    "name": "workshop_synthetic_001",
    "generated_at": "2026-04-29T10:30:00Z",
    "seed": 42,
    "params_hash": "abc123",
    "certification_level": "EN9100_lite"
  },
  "machines": [...],
  "operators": [...],
  "part_families": [...],
  "transition_matrix": {...},
  "shared_resources": [...],
  "calendar": {...},
  "orders": [
    {
      "id": "OF-2026-0001",
      "client": "Client_Tier1_A",
      "client_tier": 1,
      "deadline": "2026-05-15",
      "priority_weight": 10,
      "operations": [...]
    }
  ],
  "soft_constraints": [
    {
      "natural_language": "Éviter de faire tourner la machine M3 la nuit",
      "weight_hint": 0.5
    }
  ]
}
```

#### Format CSV alternatif (pour Excel/analyse manuelle)

5 fichiers CSV par atelier généré, dans un dossier dédié :
- `machines.csv`
- `operators.csv`
- `orders.csv`
- `operations.csv`
- `transitions.csv`

### Mode "data quality test"

Flag optionnel `--with-noise` qui injecte volontairement des problèmes de Data Quality dans la sortie pour tester le module DQ du produit :

- Variations orthographiques des matières (`"Alu 7075"`, `"AL-7075"`, `"7075 T6"`) sur le même atelier
- Quelques temps de réglage à 0 ou aberrants
- Quelques durées négatives (1-2% des lignes)
- Quelques doublons d'OF

**Niveau de bruit configurable :** `--noise-level=light|medium|heavy`.

### Script entry point `scripts/generate_workshops.py`

CLI avec `click`. Usage cible :

```bash
# Génération simple
python scripts/generate_workshops.py single --output data/synthetic/

# Batch
python scripts/generate_workshops.py batch --count 100 --output data/synthetic/batch01/

# Avec params custom
python scripts/generate_workshops.py single \
  --machines 15 \
  --jobs 200 \
  --certification EN9100_strict \
  --shifts 2 \
  --with-noise --noise-level medium \
  --seed 42 \
  --output workshop_test.json

# Génération d'un set de stress test
python scripts/generate_workshops.py stress \
  --output data/synthetic/stress/ \
  --sizes small,medium,large
```

### Critères de succès du script 2

- Génère un atelier valide (toutes les contraintes structurelles respectées : opérations sur machines compatibles, opérateurs qualifiés, etc.) en moins de 2 secondes
- Génère 100 ateliers en moins de 60 secondes
- Le fichier JSON produit est conforme à un schéma Pydantic strict
- Les ateliers générés sont **résolvables** par le solveur du script 1 (test d'intégration : générer un atelier, le résoudre, vérifier qu'on obtient une solution faisable)
- Reproductibilité parfaite avec un seed fixé

### Tests unitaires obligatoires

- `test_generator.py` :
  - Génération avec seed produit toujours le même output
  - Tous les paramètres min/max sont respectés
  - Compatibilité opérations/machines respectée
  - Sortie JSON conforme au schéma Pydantic
  - Mode `--with-noise` injecte effectivement des anomalies

---

## Critères transverses (les deux scripts)

### Qualité du code

- **Type hints partout**, validation `mypy --strict`
- **Linting** : `ruff check` doit passer sans warning
- **Format** : `ruff format` appliqué
- **Documentation** : docstrings sur toutes les fonctions publiques (style Google)
- **Pas de magic numbers** : constantes nommées dans `core/constants.py`

### Performance

- Le solveur tourne en `num_workers >= 4` pour CP-SAT (parallélisme)
- Le générateur n'utilise pas de I/O dans la boucle de génération (tout en mémoire, écriture en fin)

### Logging

- Utiliser `logging` standard avec niveaux INFO/WARNING/ERROR
- Pas de `print` en production (sauf dans les CLIs où on utilise `rich`)
- Format structuré (timestamp + module + niveau + message)

### Reproductibilité

- Tout aléa passe par un `random.Random(seed)` ou `numpy.random.default_rng(seed)`
- Le seed est exposé dans la CLI et stocké dans les métadonnées de sortie

### Documentation README

Le `README.md` du repo doit contenir, dans cet ordre :

1. Description courte du projet (3 lignes)
2. Prérequis (Python 3.11+, uv)
3. Installation (`uv sync`)
4. Téléchargement des benchmarks (`./scripts/download_benchmarks.sh`)
5. Exemples d'usage des deux scripts (commandes copiables)
6. Structure du projet
7. Comment lancer les tests
8. Roadmap (lien vers les specs fonctionnelles V3)

---

## Ce qui est **hors scope** de ces deux scripts

Pour éviter la dérive et rester focalisé sur le POC :

- **Pas de serveur MCP** dans ces scripts (vient plus tard)
- **Pas d'agent LLM** (vient plus tard)
- **Pas de simulation opérationnelle** post-solveur (vient plus tard)
- **Pas de UI** (CLI suffit)
- **Pas de persistance DB** (fichiers JSON suffisent)
- **Pas de multi-tenant** (un seul utilisateur)
- **Pas de versioning** (pas pertinent à ce stade)

Ces scripts sont uniquement le **socle de validation technique** : "mon moteur OR-Tools fonctionne sur des cas de référence académiques + sur des cas synthétiques réalistes".

---

## Workflow de validation cible (après livraison)

1. `./scripts/download_benchmarks.sh` → récupère les datasets
2. `python scripts/run_taillard_benchmark.py batch --range ta01-ta05 --time-limit 60`
   → doit afficher des gaps < 5% sur les 5 instances
3. `python scripts/generate_workshops.py single --output test.json`
   → produit un fichier JSON valide
4. `python scripts/generate_workshops.py batch --count 50 --output stress/`
   → produit 50 ateliers en moins de 30 secondes
5. **Test d'intégration** : charger un atelier généré, lancer le solveur, vérifier qu'on obtient une solution faisable

Si ces 5 étapes passent, le POC technique est validé et tu peux passer à la suite (intégration LLM, MCP, etc.).

---

## Notes finales pour Claude Code

- **Le code doit être rejouable** : pas de paths absolus, pas de dépendances système au-delà de Python
- **Privilégier la lisibilité** sur la performance prématurée (sauf si critique)
- **Pas de framework lourd** : pas de FastAPI, pas de SQLAlchemy, pas de Celery dans ce POC
- **Si une décision est ambiguë** : choisir la solution la plus simple, documenter le choix en commentaire, ne pas hésiter à mettre un `# TODO: revisit when integrating with main product`
- **En cas de doute sur la modélisation CP-SAT** : se référer aux exemples officiels d'OR-Tools (https://developers.google.com/optimization/scheduling/job_shop)

---

*Fin du document — Spec POC Scripts V1*
