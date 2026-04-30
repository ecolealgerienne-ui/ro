"""Clustering automatique des familles de pieces — verticale `mech_workshop`.

L'engine generique (`src.core.clustering.agglomerative_cluster`) gere le
clustering ; ce module fournit la **distance metier** specifique a la
sous-traitance mecanique.

Distance entre deux OF (ExtractedOrder) — combinaison ponderee :

- 50 % : distance Jaccard sur les types d'operations (gamme operatoire).
  Deux OF sont similaires s'ils utilisent les memes types d'ops
  (tournage, fraisage, rectification, etc.).
- 30 % : match materiau (binaire). Materiaux differents = penalite forte.
- 20 % : distance Jaccard sur les machines utilisees. Permet de regrouper
  les pieces compatibles avec le meme parc machine.

Justification des poids (a recalibrer post-pilotes) :
- La sequence d'ops domine le clustering : c'est ce qui definit le savoir-faire
  et les setups dans un atelier meca.
- Le materiau est important mais secondaire (peut affecter setup mais le
  vrai signal est dans les ops).
- Les machines sont un proxy faible (deux pieces similaires peuvent passer sur
  des machines distinctes selon la charge).

Critere de sortie 1.7 : 100 pieces synthetiques -> 5-15 familles, pieces
similaires regroupees.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from src.core.clustering import agglomerative_cluster
from src.verticals.mech_workshop.agents import ExtractedOrder

# Ponderation metier (somme = 1.0). Documentee pour traceabilite.
WEIGHT_OP_TYPES: Final[float] = 0.5
WEIGHT_MATERIAL: Final[float] = 0.3
WEIGHT_MACHINES: Final[float] = 0.2


def _jaccard_distance(s1: set[str], s2: set[str]) -> float:
    """Distance de Jaccard entre 2 ensembles : 0 = identiques, 1 = disjoints."""
    if not s1 and not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    if union == 0:
        return 0.0
    return 1.0 - intersection / union


def order_distance(o1: ExtractedOrder, o2: ExtractedOrder) -> float:
    """Distance metier entre 2 OF, dans [0, 1].

    0 = OF identiques (memes ops, memes machines, meme materiau).
    1 = OF totalement dissemblables (aucune op commune, materiaux differents,
        aucune machine commune).
    """
    op_types_1 = {op.operation_type for op in o1.operations}
    op_types_2 = {op.operation_type for op in o2.operations}
    machines_1 = {op.machine for op in o1.operations}
    machines_2 = {op.machine for op in o2.operations}

    d_ops = _jaccard_distance(op_types_1, op_types_2)
    d_mach = _jaccard_distance(machines_1, machines_2)
    d_mat = 0.0 if o1.material_normalized == o2.material_normalized else 1.0

    return WEIGHT_OP_TYPES * d_ops + WEIGHT_MATERIAL * d_mat + WEIGHT_MACHINES * d_mach


def cluster_orders_to_families(
    orders: Iterable[ExtractedOrder],
    *,
    target_n_clusters: tuple[int, int] = (5, 15),
    merge_distance_threshold: float | None = None,
) -> dict[str, int]:
    """Regroupe les OF en familles via clustering agglomeratif average-linkage.

    Args:
        orders: liste d'OF (typiquement la sortie de `CSVExtractionAgent`).
        target_n_clusters: (min, max) du nombre de familles vise. Defaut
            (5, 15) — convergent avec la guidance metier (un atelier meca
            "manageable" a 5-15 familles distinctes).
        merge_distance_threshold: si fourni, arrete les fusions des que les
            clusters restants sont trop dissemblables (distance moyenne min >
            seuil). Permet d'eviter de fusionner des familles fondamentalement
            differentes juste pour atteindre target_min. Defaut None.

    Returns:
        `dict[order_id, family_id]` (family_id 0-indexe, dense).
    """
    items: dict[str, ExtractedOrder] = {o.order_id: o for o in orders}
    return agglomerative_cluster(
        items,
        order_distance,
        target_n_clusters=target_n_clusters,
        merge_distance_threshold=merge_distance_threshold,
    )


__all__ = [
    "WEIGHT_MACHINES",
    "WEIGHT_MATERIAL",
    "WEIGHT_OP_TYPES",
    "cluster_orders_to_families",
    "order_distance",
]
