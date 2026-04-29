"""Patterns CP-SAT réutilisables pour la modélisation d'ordonnancement.

Chaque fonction est une primitive testée qui ajoute un type de contrainte au
modèle. Elles servent de briques pour le solveur JSSP basique (étape 0.3) puis
seront étendues en bibliothèque structurée à l'étape 1.1.

Référence : `specs-techniques-v3.md` §5.3 et `specs-poc-scripts-v1.md` §Module
core/patterns.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def add_no_overlap_machine(model: Any, intervals: Sequence[Any]) -> None:
    """Ajoute la contrainte NoOverlap pour les opérations d'une même machine.

    Args:
        model: `cp_model.CpModel`.
        intervals: Liste de `IntervalVar` correspondant aux opérations
            assignées à la machine. Vide ou taille 1 → no-op.
    """
    if len(intervals) > 1:
        model.add_no_overlap(list(intervals))


def add_precedence_in_job(
    model: Any,
    end_vars: Sequence[Any],
    start_vars: Sequence[Any],
) -> None:
    """Ajoute la contrainte de précédence séquentielle dans un job.

    Force `end_vars[i] <= start_vars[i+1]` pour i de 0 à n-2 — encode la
    gamme opératoire.

    Args:
        model: `cp_model.CpModel`.
        end_vars: Variables de fin des opérations dans l'ordre de la gamme.
        start_vars: Variables de début dans le même ordre. Doit avoir la
            même longueur que `end_vars`.

    Raises:
        ValueError: Si les listes ont des tailles différentes.
    """
    if len(end_vars) != len(start_vars):
        raise ValueError(
            f"end_vars ({len(end_vars)}) et start_vars ({len(start_vars)}) "
            "doivent avoir la même longueur"
        )
    for i in range(len(end_vars) - 1):
        model.add(end_vars[i] <= start_vars[i + 1])


def make_makespan_objective(
    model: Any,
    end_vars: Sequence[Any],
    horizon: int,
) -> Any:
    """Crée la variable makespan, l'égalité au max des fins, et minimise.

    Args:
        model: `cp_model.CpModel`.
        end_vars: Variables de fin des dernières opérations de chaque job
            (ou de toutes les opérations — `max_equality` est tolérant).
        horizon: Borne supérieure sur le makespan (utilisée pour le domaine
            de la variable).

    Returns:
        La variable `makespan` créée — utile si l'appelant veut l'introspecter.

    Raises:
        ValueError: Si `end_vars` est vide ou si `horizon` est négatif.
    """
    if not end_vars:
        raise ValueError("end_vars ne peut pas être vide")
    if horizon < 0:
        raise ValueError(f"horizon doit être ≥ 0, reçu {horizon}")

    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, list(end_vars))
    model.minimize(makespan)
    return makespan


def add_no_overlap_with_setup(
    model: Any,
    starts: Sequence[Any],
    ends: Sequence[Any],
    family_ids: Sequence[int],
    transition_matrix: Sequence[Sequence[int]],
    *,
    name_prefix: str = "seq",
) -> None:
    """Ajoute la contrainte de non-chevauchement avec setup time dépendant de la séquence.

    Pour chaque paire d'opérations (i, j) sur la même machine :
        - soit op_i avant op_j : start[j] >= end[i] + transition[fam_i][fam_j]
        - soit op_j avant op_i : start[i] >= end[j] + transition[fam_j][fam_i]

    Cette modélisation par paires disjonctives sert l'étape 0.6 du POC. La
    spec produit (`specs-fonctionnelles-v3.md` §7.1) recommande le pattern
    `AddNoOverlap(transition_matrix=...)` natif de CP-SAT pour la production —
    à substituer en étape 1.1 lors du refactor en classes `Pattern`.

    Args:
        model: `cp_model.CpModel`.
        starts: Variables de début des opérations sur la machine.
        ends: Variables de fin (même longueur que `starts`).
        family_ids: Identifiant de famille de pièce de chaque opération
            (indices dans `transition_matrix`).
        transition_matrix: Matrice carrée `transition_matrix[from][to]`
            donnant le setup en unités de temps. Diagonale typiquement 0.
        name_prefix: Préfixe des noms de variables booléennes auxiliaires.

    Raises:
        ValueError: Si les longueurs sont incohérentes ou si la matrice
            n'est pas carrée / contient des valeurs négatives.
    """
    n = len(starts)
    if n != len(ends):
        raise ValueError(f"starts ({n}) et ends ({len(ends)}) doivent avoir la même longueur")
    if n != len(family_ids):
        raise ValueError(
            f"starts ({n}) et family_ids ({len(family_ids)}) doivent avoir la même longueur"
        )
    if n <= 1:
        return

    n_families = len(transition_matrix)
    for row in transition_matrix:
        if len(row) != n_families:
            raise ValueError(
                f"transition_matrix doit être carrée ({n_families}×{n_families}), "
                f"ligne de taille {len(row)} trouvée"
            )
        for v in row:
            if v < 0:
                raise ValueError(f"transition_matrix : valeurs négatives interdites, vu {v}")

    for fid in family_ids:
        if not 0 <= fid < n_families:
            raise ValueError(
                f"family_id {fid} hors borne (matrice {n_families}×{n_families})"
            )

    for i in range(n):
        for j in range(i + 1, n):
            fam_i = family_ids[i]
            fam_j = family_ids[j]
            setup_ij = transition_matrix[fam_i][fam_j]
            setup_ji = transition_matrix[fam_j][fam_i]

            i_before_j = model.new_bool_var(f"{name_prefix}_{i}_before_{j}")
            model.add(starts[j] >= ends[i] + setup_ij).only_enforce_if(i_before_j)
            model.add(starts[i] >= ends[j] + setup_ji).only_enforce_if(i_before_j.Not())
