"""Patterns CP-SAT — API fonctions (compatibilité ascendante).

Depuis l'étape 1.1 (Phase 1), l'API canonique est `src.core.pattern.Pattern` et
ses sous-classes. Ce module expose les mêmes patterns sous forme de fonctions
pour préserver la compatibilité avec le code existant (tests, solver, scripts).

Les fonctions ici sont des délégates fins vers les classes Pattern. Elles
seront marquées dépréciées en Phase 2.

Référence : `specs-techniques-v3.md` §5.3.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.core.pattern import (
    MakespanObjectivePattern,
    NoOverlapMachinePattern,
    PrecedenceInJobPattern,
    QualifiedOperatorPattern,
    SequenceDependentSetupPattern,
    SharedResourceExclusionPattern,
    UnavailableIntervalsPattern,
)


def add_no_overlap_machine(model: Any, intervals: Sequence[Any]) -> None:
    """Délégate vers `NoOverlapMachinePattern`. Voir cette classe pour détails."""
    NoOverlapMachinePattern().apply(model, intervals=intervals)


def add_precedence_in_job(
    model: Any,
    end_vars: Sequence[Any],
    start_vars: Sequence[Any],
) -> None:
    """Délégate vers `PrecedenceInJobPattern`."""
    PrecedenceInJobPattern().apply(model, end_vars=end_vars, start_vars=start_vars)


def make_makespan_objective(
    model: Any,
    end_vars: Sequence[Any],
    horizon: int,
) -> Any:
    """Délégate vers `MakespanObjectivePattern`."""
    return MakespanObjectivePattern().apply(model, end_vars=end_vars, horizon=horizon)


def add_no_overlap_with_setup(
    model: Any,
    starts: Sequence[Any],
    ends: Sequence[Any],
    family_ids: Sequence[int],
    transition_matrix: Sequence[Sequence[int]],
    *,
    name_prefix: str = "seq",
) -> None:
    """Délégate vers `SequenceDependentSetupPattern`."""
    SequenceDependentSetupPattern(name_prefix=name_prefix).apply(
        model,
        starts=starts,
        ends=ends,
        family_ids=family_ids,
        transition_matrix=transition_matrix,
    )


def add_qualified_operator_constraint(
    model: Any,
    starts: Sequence[Any],
    ends: Sequence[Any],
    durations: Sequence[int],
    qualifications: Sequence[Sequence[int]],
    n_operators: int,
    *,
    name_prefix: str = "qual",
) -> None:
    """Délégate vers `QualifiedOperatorPattern`."""
    QualifiedOperatorPattern(name_prefix=name_prefix).apply(
        model,
        starts=starts,
        ends=ends,
        durations=durations,
        qualifications=qualifications,
        n_operators=n_operators,
    )


def add_shared_resource_exclusion(
    model: Any,
    intervals: Sequence[Any],
    max_concurrent: int,
) -> None:
    """Délégate vers `SharedResourceExclusionPattern`."""
    SharedResourceExclusionPattern().apply(
        model,
        intervals=intervals,
        max_concurrent=max_concurrent,
    )


def make_unavailable_intervals(
    model: Any,
    periods: Sequence[tuple[int, int]],
    *,
    name_prefix: str = "unavail",
) -> list[Any]:
    """Délégate vers `UnavailableIntervalsPattern`."""
    return UnavailableIntervalsPattern(name_prefix=name_prefix).apply(model, periods=periods)
