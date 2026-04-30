"""Distributions et constantes métier pour la génération d'ateliers synthétiques.

Ces valeurs sont calibrées sur la réalité de la sous-traitance mécanique de
précision (ICP : PME 10-50 personnes, 5-25 machines CN, certifiables aéro/auto).

Référence : `specs-poc-scripts-v1.md` §Distributions métier réalistes.
"""

from __future__ import annotations

from typing import Final

# ---------- Types de machines ----------

MACHINE_TYPES_DEFAULT: Final[dict[str, float]] = {
    "tour_cn_2_axes": 0.20,
    "tour_cn_4_axes": 0.10,
    "fraiseuse_cn_3_axes": 0.25,
    "fraiseuse_cn_5_axes": 0.15,
    "centre_usinage": 0.10,
    "rectifieuse_cylindrique": 0.05,
    "rectifieuse_plane": 0.05,
    "perceuse_cn": 0.05,
    "machine_controle_3d": 0.05,
}

# ---------- Matières ----------

MATERIALS_DEFAULT: Final[dict[str, float]] = {
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

# Multiplicateur de durée de cycle selon la matière (relatif à l'aluminium).
# Plus la matière est dure / délicate, plus le multiplicateur est élevé.
MATERIAL_DIFFICULTY_MULTIPLIER: Final[dict[str, float]] = {
    "aluminium_2017": 1.0,
    "aluminium_7075_T6": 1.1,
    "acier_inox_316L": 1.6,
    "acier_inox_304": 1.5,
    "acier_42CrMo4": 1.4,
    "titane_TA6V": 2.2,
    "laiton_CuZn40": 0.9,
    "bronze": 1.1,
    "plastique_technique": 0.7,
    "autres": 1.2,
}

# ---------- Opérations canoniques ----------

OPERATIONS_CANONICAL: Final[tuple[str, ...]] = (
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
    "traitement_thermique_externe",
    "anodisation_externe",
)

# Compatibilité opération → types de machines acceptables.
OPERATION_MACHINE_COMPAT: Final[dict[str, tuple[str, ...]]] = {
    "tournage_ebauche": ("tour_cn_2_axes", "tour_cn_4_axes"),
    "tournage_finition": ("tour_cn_2_axes", "tour_cn_4_axes"),
    "fraisage_ebauche": ("fraiseuse_cn_3_axes", "fraiseuse_cn_5_axes", "centre_usinage"),
    "fraisage_finition": ("fraiseuse_cn_3_axes", "fraiseuse_cn_5_axes", "centre_usinage"),
    "fraisage_5axes": ("fraiseuse_cn_5_axes", "centre_usinage"),
    "percage": ("perceuse_cn", "fraiseuse_cn_3_axes", "centre_usinage"),
    "taraudage": ("perceuse_cn", "fraiseuse_cn_3_axes", "centre_usinage"),
    "rectification_cylindrique": ("rectifieuse_cylindrique",),
    "rectification_plane": ("rectifieuse_plane",),
    "controle_dimensionnel": ("machine_controle_3d",),
    # Opérations manuelles : toutes machines (encodage simplifié — en V1 produit
    # ce sera modélisé avec des postes opérateur dédiés).
    "ebavurage": tuple(MACHINE_TYPES_DEFAULT.keys()),
    "marquage": tuple(MACHINE_TYPES_DEFAULT.keys()),
    "lavage": tuple(MACHINE_TYPES_DEFAULT.keys()),
    # Sous-traitances externes : pas de machine interne (filtrées par le générateur).
    "traitement_thermique_externe": (),
    "anodisation_externe": (),
}

# ---------- Temps de cycle de référence (minutes), aluminium 2017 = 1.0×) ----------
# Format : (mean_min, std_min). À multiplier par MATERIAL_DIFFICULTY_MULTIPLIER.
OPERATION_BASE_TIMES_MIN: Final[dict[str, tuple[float, float]]] = {
    "tournage_ebauche": (35.0, 12.0),
    "tournage_finition": (25.0, 8.0),
    "fraisage_ebauche": (45.0, 15.0),
    "fraisage_finition": (30.0, 10.0),
    "fraisage_5axes": (60.0, 20.0),
    "percage": (8.0, 3.0),
    "taraudage": (5.0, 2.0),
    "rectification_cylindrique": (40.0, 12.0),
    "rectification_plane": (35.0, 10.0),
    "controle_dimensionnel": (15.0, 5.0),
    "ebavurage": (10.0, 4.0),
    "marquage": (3.0, 1.0),
    "lavage": (8.0, 2.0),
    "traitement_thermique_externe": (1440.0, 480.0),  # 24h ± 8h, sous-traitance
    "anodisation_externe": (2880.0, 720.0),  # 48h ± 12h, sous-traitance
}

# ---------- Tiers clients ----------

CLIENT_TIERS: Final[dict[str, float]] = {
    "Tier_1_strategic": 0.15,
    "Tier_2_important": 0.35,
    "Tier_3_standard": 0.50,
}

CLIENT_TIER_WEIGHT: Final[dict[str, int]] = {
    "Tier_1_strategic": 10,
    "Tier_2_important": 5,
    "Tier_3_standard": 1,
}

# Pool de clients fictifs par tier (exemples du segment aéro/auto/médical).
CLIENT_NAMES_BY_TIER: Final[dict[str, tuple[str, ...]]] = {
    "Tier_1_strategic": ("Client_AeroT1_A", "Client_AutoT1_B", "Client_DefT1_C"),
    "Tier_2_important": (
        "Client_AeroT2_D",
        "Client_AeroT2_E",
        "Client_MedT2_F",
        "Client_AutoT2_G",
    ),
    "Tier_3_standard": (
        "Client_GenT3_H",
        "Client_GenT3_I",
        "Client_GenT3_J",
        "Client_GenT3_K",
        "Client_GenT3_L",
    ),
}


# ---------- Familles de pièces et matrice de transition (étape 1.1b) ----------
#
# Chaque opération canonique appartient à une famille (regroupement par type
# de procédé). La matrice de transition donne les setup times entre familles
# en minutes. Diagonale = 0 (pas de setup intra-famille).
#
# Cette modélisation simplifiée (familles globales, matrice unique) sera
# raffinée en étape 1.7 avec un clustering automatique par atelier.

OPERATION_FAMILY: Final[dict[str, int]] = {
    "tournage_ebauche": 0,
    "tournage_finition": 0,
    "fraisage_ebauche": 1,
    "fraisage_finition": 1,
    "fraisage_5axes": 1,
    "percage": 2,
    "taraudage": 2,
    "rectification_cylindrique": 3,
    "rectification_plane": 3,
    "controle_dimensionnel": 4,
    "ebavurage": 5,
    "marquage": 5,
    "lavage": 5,
    "traitement_thermique_externe": 6,
    "anodisation_externe": 6,
}

N_FAMILIES: Final[int] = 7

# Setup times inter-familles (minutes).
# Lignes = depuis, colonnes = vers. Ordres de grandeur calibrés sur la pratique
# atelier méca précision (changement matière, changement outillage).
DEFAULT_TRANSITION_MATRIX: Final[tuple[tuple[int, ...], ...]] = (
    # tournage(0), fraisage(1), percage(2), rectif(3), controle(4), finition(5), externe(6)
    (0, 20, 15, 30, 5, 10, 0),  # depuis tournage
    (20, 0, 15, 30, 5, 10, 0),  # depuis fraisage
    (15, 15, 0, 25, 5, 10, 0),  # depuis percage/taraudage
    (30, 30, 25, 0, 10, 15, 0),  # depuis rectification (changement abrasif coûteux)
    (5, 5, 5, 10, 0, 5, 0),  # depuis controle (poste différent, peu d'impact)
    (10, 10, 10, 15, 5, 0, 0),  # depuis finition manuelle
    (0, 0, 0, 0, 0, 0, 0),  # depuis externe (sous-traitance, pas de setup interne)
)
