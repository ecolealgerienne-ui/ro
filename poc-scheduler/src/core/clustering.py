"""Clustering generique d'items par similarite.

Module **vertical-agnostic**. Fournit un clustering agglomeratif greedy
average-linkage qui prend :

- une `Mapping[ID, T]` d'items a regrouper
- une fonction `distance_fn(T, T) -> float` (semantique definie par la verticale)
- une plage cible `(target_min, target_max)` du nombre de clusters

Et retourne `dict[ID, int]` (item_id -> cluster_id, 0-indexe).

Algorithme :
- Init : chaque item dans son propre cluster (n clusters initiaux).
- Iter : trouver la paire de clusters avec la plus petite distance moyenne,
  la fusionner. Repeter jusqu'a n_clusters <= target_max.
- Si n_items <= target_max au depart : pas de fusion, chaque item reste seul.
- Si la distance entre clusters non encore fusionnes depasse `merge_distance_threshold`
  (optionnel), arrete les fusions meme si on n'a pas atteint target_min — evite
  de regrouper des items dissemblables juste pour atteindre le quota.

Complexite : O(n^3) — pour n=100, ~10^6 ops, quelques secondes en Python pur.
Au-dela de n=200, optimiser via une matrice de distance precalculee + tas.

La verticale fournit la `distance_fn` qui encode la similarite metier
(ex: en meca : Jaccard ops + match materiau + Jaccard machines).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TypeVar

ID = TypeVar("ID")
T = TypeVar("T")


def agglomerative_cluster(
    items: Mapping[ID, T],
    distance_fn: Callable[[T, T], float],
    *,
    target_n_clusters: tuple[int, int] = (5, 15),
    merge_distance_threshold: float | None = None,
) -> dict[ID, int]:
    """Clustering agglomeratif greedy average-linkage.

    Args:
        items: items a clusteriser (cle = identifiant, valeur = donnees).
        distance_fn: distance entre deux items, dans [0, +inf). Symetrique
            attendue mais non verifiee (la verticale doit garantir).
        target_n_clusters: (min, max) du nombre de clusters voulu.
        merge_distance_threshold: si fourni, arrete les fusions des que la
            distance moyenne minimum entre 2 clusters depasse ce seuil. Permet
            d'eviter de fusionner des items dissemblables juste pour atteindre
            target_min. None = on continue jusqu'a target_max.

    Returns:
        `dict[ID, int]` : item_id -> cluster_id (0-indexe, dense).

    Raises:
        ValueError: si target_n_clusters est invalide.
    """
    target_min, target_max = target_n_clusters
    if target_min < 1 or target_max < target_min:
        raise ValueError(f"target_n_clusters invalide : ({target_min}, {target_max})")

    item_ids: list[ID] = list(items.keys())
    n = len(item_ids)
    if n == 0:
        return {}
    if n <= target_max:
        # Pas besoin de fusionner.
        return {item_id: i for i, item_id in enumerate(item_ids)}

    # Init : chaque item dans son cluster.
    clusters: list[list[ID]] = [[item_id] for item_id in item_ids]

    # Boucle : on continue tant qu'on peut potentiellement fusionner.
    # - Au-dessus de target_max : merge force.
    # - Entre target_min et target_max : merge optionnel, depend du threshold.
    # - A target_min : stop (on ne peut pas descendre plus bas).
    while len(clusters) > target_min:
        best_dist = float("inf")
        best_pair: tuple[int, int] = (-1, -1)
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                total = 0.0
                count = 0
                for a in clusters[i]:
                    for b in clusters[j]:
                        total += distance_fn(items[a], items[b])
                        count += 1
                avg = total / count if count else 0.0
                if avg < best_dist:
                    best_dist = avg
                    best_pair = (i, j)

        if best_pair[0] == -1:
            break  # securite, ne devrait pas arriver

        # Zone optionnelle : on est en-dessous de target_max, on regarde le threshold.
        if len(clusters) <= target_max:
            if merge_distance_threshold is None:
                break  # pas de threshold -> on s'arrete a target_max
            if best_dist > merge_distance_threshold:
                break  # paire trop dissemblable -> on n'enforce pas la fusion

        i, j = best_pair
        clusters[i].extend(clusters[j])
        clusters.pop(j)

    # Mapping final.
    out: dict[ID, int] = {}
    for cluster_id, members in enumerate(clusters):
        for item_id in members:
            out[item_id] = cluster_id
    return out


__all__ = ["agglomerative_cluster"]
