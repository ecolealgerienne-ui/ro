"""Tests Phase 1.7 — clustering automatique des familles de pieces.

Couvre :
- Engine `agglomerative_cluster` : edge cases (vide, n <= max), validation
  des arguments, fusion correcte, threshold pour arret precoce.
- Vertical `order_distance` : sémantique (0 si identique, 1 si totalement
  disjoint, ponderation respectee).
- Vertical `cluster_orders_to_families` :
  - 100 OF synthetiques -> 5-15 familles (critere de sortie)
  - OF similaires regroupees (verifie sur cas force)
  - Singletons preserves quand n_orders < target_max
"""

from __future__ import annotations

import pytest

from src.core.clustering import agglomerative_cluster
from src.verticals.mech_workshop.agents import ExtractedOperation, ExtractedOrder
from src.verticals.mech_workshop.clustering import (
    cluster_orders_to_families,
    order_distance,
)

# ---------- Engine : agglomerative_cluster ----------


def test_cluster_empty_returns_empty() -> None:
    assert agglomerative_cluster({}, lambda a, b: 0.0) == {}


def test_cluster_singletons_when_under_target_max() -> None:
    """5 items, target_max=10 : pas de fusion, chaque item dans son cluster."""
    items = {f"x{i}": i for i in range(5)}
    out = agglomerative_cluster(items, lambda a, b: abs(a - b), target_n_clusters=(2, 10))
    assert len(set(out.values())) == 5  # 5 clusters distincts
    assert all(item in out for item in items)


def test_cluster_merges_to_target_max() -> None:
    """20 items numeriques distincts, target=(3, 5) : fusionne pour atteindre <= 5."""
    items = {f"x{i}": float(i) for i in range(20)}
    out = agglomerative_cluster(items, lambda a, b: abs(a - b), target_n_clusters=(3, 5))
    n_clusters = len(set(out.values()))
    assert 3 <= n_clusters <= 5


def test_cluster_threshold_stops_early() -> None:
    """Avec un threshold faible, on arrete des qu'on est sous target_min."""
    # 10 items en 2 groupes : [0..4] et [100..104]
    items = {f"a{i}": float(i) for i in range(5)}
    items.update({f"b{i}": float(100 + i) for i in range(5)})
    out = agglomerative_cluster(
        items,
        lambda a, b: abs(a - b),
        target_n_clusters=(1, 5),
        merge_distance_threshold=10.0,
    )
    n_clusters = len(set(out.values()))
    # Avec threshold=10 et un gap de 100 entre les groupes, on ne fusionne pas
    # les 2 groupes meme si target_min=1.
    assert n_clusters == 2


def test_cluster_invalid_target_raises() -> None:
    with pytest.raises(ValueError, match=r"target_n_clusters"):
        agglomerative_cluster({"x": 1}, lambda a, b: 0.0, target_n_clusters=(0, 5))
    with pytest.raises(ValueError, match=r"target_n_clusters"):
        agglomerative_cluster({"x": 1}, lambda a, b: 0.0, target_n_clusters=(5, 3))


# ---------- Vertical : order_distance ----------


def _order(
    order_id: str,
    *,
    op_types: list[str],
    machines: list[str],
    material: str = "aluminium",
) -> ExtractedOrder:
    """Helper : construit un ExtractedOrder minimal pour les tests."""
    return ExtractedOrder(
        order_id=order_id,
        client="X",
        piece_name=f"piece_{order_id}",
        material_normalized=material,
        operations=[
            ExtractedOperation(
                sequence_idx=i,
                operation_type=op_types[i],
                machine=machines[i],
                duration_min=10,
            )
            for i in range(len(op_types))
        ],
    )


def test_order_distance_identical_is_zero() -> None:
    o1 = _order("OF1", op_types=["tournage", "fraisage"], machines=["TOUR-01", "FRAIS-01"])
    o2 = _order("OF2", op_types=["tournage", "fraisage"], machines=["TOUR-01", "FRAIS-01"])
    assert order_distance(o1, o2) == 0.0


def test_order_distance_totally_different() -> None:
    o1 = _order(
        "OF1",
        op_types=["tournage"],
        machines=["TOUR-01"],
        material="aluminium",
    )
    o2 = _order(
        "OF2",
        op_types=["fraisage"],
        machines=["FRAIS-01"],
        material="acier",
    )
    # d_ops = 1, d_mat = 1, d_mach = 1 -> distance = 1.0
    assert order_distance(o1, o2) == 1.0


def test_order_distance_only_material_differs() -> None:
    o1 = _order("OF1", op_types=["tournage"], machines=["TOUR-01"], material="aluminium")
    o2 = _order("OF2", op_types=["tournage"], machines=["TOUR-01"], material="acier")
    # d_ops = 0, d_mat = 1, d_mach = 0 -> distance = 0.3
    assert order_distance(o1, o2) == pytest.approx(0.3)


def test_order_distance_partial_op_overlap() -> None:
    o1 = _order(
        "OF1",
        op_types=["tournage", "fraisage"],
        machines=["TOUR-01", "FRAIS-01"],
        material="aluminium",
    )
    o2 = _order(
        "OF2",
        op_types=["tournage", "rectification"],
        machines=["TOUR-01", "RECT-01"],
        material="aluminium",
    )
    # ops : intersection {tournage} (1), union {tournage, fraisage, rectification} (3)
    # → d_ops = 1 - 1/3 = 2/3
    # machines : intersection {TOUR-01} (1), union {TOUR-01, FRAIS-01, RECT-01} (3)
    # → d_mach = 2/3
    # materiau identique → d_mat = 0
    # distance = 0.5*(2/3) + 0.3*0 + 0.2*(2/3) = (0.5+0.2)*(2/3) = 7/15 ≈ 0.4667
    assert order_distance(o1, o2) == pytest.approx(7 / 15)


# ---------- Vertical : cluster_orders_to_families ----------


def test_cluster_orders_singletons_when_few_items() -> None:
    orders = [_order(f"OF{i}", op_types=["tournage"], machines=["TOUR-01"]) for i in range(3)]
    out = cluster_orders_to_families(orders, target_n_clusters=(2, 10))
    # 3 OF, target_max=10 : pas de fusion, 3 clusters distincts.
    assert len(set(out.values())) == 3


def test_cluster_orders_groups_similar_pieces() -> None:
    """OF similaires (memes ops, meme matiere) regroupes ensemble."""
    # 6 OF en 2 familles claires :
    # - 3 OF "tournage simple alu" sur TOUR-01
    # - 3 OF "fraisage 5 axes inox" sur FRAIS-02
    orders = []
    for i in range(3):
        orders.append(
            _order(
                f"T{i}",
                op_types=["tournage"],
                machines=["TOUR-01"],
                material="aluminium",
            )
        )
    for i in range(3):
        orders.append(
            _order(
                f"F{i}",
                op_types=["fraisage", "controle"],
                machines=["FRAIS-02", "MMT-01"],
                material="inox",
            )
        )
    out = cluster_orders_to_families(orders, target_n_clusters=(2, 2))
    # On force 2 clusters : les 3 T doivent etre dans un cluster, les 3 F dans l'autre.
    assert out["T0"] == out["T1"] == out["T2"]
    assert out["F0"] == out["F1"] == out["F2"]
    assert out["T0"] != out["F0"]


# ---------- Critere de sortie 1.7 : 100 OF -> 5-15 familles ----------


def _build_synthetic_orders_100(n_orders: int = 100) -> list[ExtractedOrder]:
    """Construit 100 OF synthetiques distribues en ~8 archetypes metier.

    Chaque archetype represente un type de piece typique en sous-traitance meca :
    tournage simple, tournage-fraisage, fraisage 5 axes, rectification, etc.
    Les archetypes sont distincts mais avec un peu de variation au sein de chacun.
    """
    archetypes = [
        # (op_types, machines, material)
        (["tournage"], ["TOUR-01"], "aluminium"),
        (["tournage", "fraisage"], ["TOUR-01", "FRAIS-01"], "aluminium"),
        (["tournage", "fraisage", "controle"], ["TOUR-02", "FRAIS-01", "MMT-01"], "inox"),
        (["fraisage_5_axes", "controle"], ["FRAIS-02", "MMT-01"], "titane"),
        (["rectification"], ["RECT-01"], "acier"),
        (["tournage", "rectification"], ["TOUR-01", "RECT-01"], "acier"),
        (["fraisage", "percage"], ["FRAIS-01", "PERC-01"], "aluminium"),
        (["tournage_long", "controle"], ["TOUR-03", "MMT-01"], "inox"),
    ]
    orders: list[ExtractedOrder] = []
    for i in range(n_orders):
        op_types, machines, material = archetypes[i % len(archetypes)]
        orders.append(
            _order(
                f"OF-{i:03d}", op_types=list(op_types), machines=list(machines), material=material
            )
        )
    return orders


def test_critere_de_sortie_100_pieces_5_to_15_families() -> None:
    """Critere de sortie 1.7 : 100 OF synthetiques -> 5 a 15 familles."""
    orders = _build_synthetic_orders_100()
    assert len(orders) == 100

    out = cluster_orders_to_families(orders, target_n_clusters=(5, 15))
    n_families = len(set(out.values()))

    assert 5 <= n_families <= 15, f"Critere non respecte : {n_families} familles (vise 5-15)"
    # Chaque OF a une famille assignee.
    assert all(o.order_id in out for o in orders)


def test_synthetic_archetypes_are_within_same_family() -> None:
    """Les OF du meme archetype doivent finir dans la meme famille.

    On a 8 archetypes × 12-13 OF chacun (100 / 8). Avec target=(5, 8), le
    nombre max de clusters force la coalescence complete par archetype : 100
    items moins 92 merges = 8 clusters, exactement un par archetype.
    """
    orders = _build_synthetic_orders_100()
    out = cluster_orders_to_families(orders, target_n_clusters=(5, 8))

    # Pour chaque archetype (i % 8 == k), tous les OF doivent avoir le meme cluster.
    for archetype_idx in range(8):
        same_archetype_ofs = [f"OF-{i:03d}" for i in range(100) if i % 8 == archetype_idx]
        clusters_in_archetype = {out[oid] for oid in same_archetype_ofs}
        assert len(clusters_in_archetype) == 1, (
            f"Archetype {archetype_idx} eclate sur {len(clusters_in_archetype)} familles"
        )
