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
