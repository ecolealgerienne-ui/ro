"""Verticale `mech_workshop` — sous-traitance mécanique de précision.

ICP : PME 10-50 personnes, 5-25 machines CN, certifiables aéro/auto/médical.

Cette verticale spécialise le moteur générique de scheduling pour le métier
de sous-traitance mécanique :

- **Distributions métier** (`distributions.py`) : types de machines (tour CN,
  fraiseuse, rectifieuse, etc.), matières (Al, Inox, Ti…), opérations canoniques
  (tournage, fraisage, perçage…), familles et matrice de transition pour
  les setup times.
- **Générateur synthétique** (`generator.py`) : produit des ateliers méca
  réalistes pour les tests de stress du solveur.
- **Adapteur** (`adapter.py`) : convertit un `SyntheticWorkshop` (modèle
  haut niveau métier) en `WorkshopInstance` (modèle JSSP générique du moteur).
- **Configuration pre-flight** (`preflight_config.py`) : patterns de colonnes
  ERP méca, champs canoniques, fournis au moteur pre-flight générique.
- **Calibration scoring** (`scoring_config.py`) : poids des métriques de
  confiance, fournis au moteur de scoring générique.

Les imports admis :

- `src.core.*` (le moteur)
- `src.preflight.*` (preflight générique)
- `src.loaders.*` (loaders génériques type Taillard)
- modules de la même verticale

Les imports interdits :

- `src.verticals.<autre_verticale>.*` (les verticales sont indépendantes)
"""

from src.verticals.mech_workshop.adapter import synthetic_to_jssp_instance
from src.verticals.mech_workshop.distributions import (
    CLIENT_NAMES_BY_TIER,
    CLIENT_TIER_WEIGHT,
    CLIENT_TIERS,
    DEFAULT_TRANSITION_MATRIX,
    MACHINE_TYPES_DEFAULT,
    MATERIAL_DIFFICULTY_MULTIPLIER,
    MATERIALS_DEFAULT,
    N_FAMILIES,
    OPERATION_BASE_TIMES_MIN,
    OPERATION_FAMILY,
    OPERATION_MACHINE_COMPAT,
    OPERATIONS_CANONICAL,
)
from src.verticals.mech_workshop.generator import (
    GenerationParams,
    SharedResource,
    SyntheticMachine,
    SyntheticOperation,
    SyntheticOperator,
    SyntheticOrder,
    SyntheticWorkshop,
    WorkCalendar,
    generate_workshop,
)
from src.verticals.mech_workshop.preflight_config import (
    MECH_CANONICAL_FIELDS,
    MECH_COLUMN_PATTERNS,
    MECH_REQUIRED_CANONICAL_FIELDS,
)
from src.verticals.mech_workshop.scoring_config import MECH_CONFIDENCE_WEIGHTS
from src.verticals.mech_workshop.simulation_config import MECH_SIMULATION_THRESHOLDS

__all__ = [
    "CLIENT_NAMES_BY_TIER",
    "CLIENT_TIERS",
    "CLIENT_TIER_WEIGHT",
    "DEFAULT_TRANSITION_MATRIX",
    "MACHINE_TYPES_DEFAULT",
    "MATERIALS_DEFAULT",
    "MATERIAL_DIFFICULTY_MULTIPLIER",
    "MECH_CANONICAL_FIELDS",
    "MECH_COLUMN_PATTERNS",
    "MECH_CONFIDENCE_WEIGHTS",
    "MECH_REQUIRED_CANONICAL_FIELDS",
    "MECH_SIMULATION_THRESHOLDS",
    "N_FAMILIES",
    "OPERATIONS_CANONICAL",
    "OPERATION_BASE_TIMES_MIN",
    "OPERATION_FAMILY",
    "OPERATION_MACHINE_COMPAT",
    "GenerationParams",
    "SharedResource",
    "SyntheticMachine",
    "SyntheticOperation",
    "SyntheticOperator",
    "SyntheticOrder",
    "SyntheticWorkshop",
    "WorkCalendar",
    "generate_workshop",
    "synthetic_to_jssp_instance",
]
