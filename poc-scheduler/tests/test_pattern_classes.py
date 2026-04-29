"""Tests des classes `Pattern` (étape 1.1).

Vérifient que :
1. La registry contient les 7 patterns attendus.
2. Chaque classe est instanciable et expose `name`, `description`.
3. Chaque pattern produit le même résultat solver que la fonction délégate.
4. `get_pattern(name)` retourne une instance utilisable.

Les tests fonctionnels approfondis (golden cases) restent dans
`test_patterns.py` qui exerce déjà l'API de fonctions (qui délègue désormais
aux classes).
"""

from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from src.core.pattern import (
    PATTERNS,
    MakespanObjectivePattern,
    NoOverlapMachinePattern,
    Pattern,
    PrecedenceInJobPattern,
    QualifiedOperatorPattern,
    SequenceDependentSetupPattern,
    SharedResourceExclusionPattern,
    UnavailableIntervalsPattern,
    get_pattern,
    list_patterns,
)


# ---------- Registry ----------


EXPECTED_PATTERN_NAMES = {
    "no_overlap_machine",
    "precedence_in_job",
    "makespan_objective",
    "no_overlap_with_setup",
    "qualified_operator",
    "shared_resource_exclusion",
    "unavailable_intervals",
}


def test_registry_contains_all_patterns() -> None:
    assert set(PATTERNS.keys()) == EXPECTED_PATTERN_NAMES


def test_list_patterns_sorted() -> None:
    names = list_patterns()
    assert names == sorted(names)
    assert set(names) == EXPECTED_PATTERN_NAMES


def test_get_pattern_returns_instance() -> None:
    pattern = get_pattern("no_overlap_machine")
    assert isinstance(pattern, NoOverlapMachinePattern)
    assert isinstance(pattern, Pattern)


def test_get_pattern_unknown_raises() -> None:
    with pytest.raises(KeyError, match="inconnu"):
        get_pattern("foo_bar_baz")


@pytest.mark.parametrize("name,expected_cls", [
    ("no_overlap_machine", NoOverlapMachinePattern),
    ("precedence_in_job", PrecedenceInJobPattern),
    ("makespan_objective", MakespanObjectivePattern),
    ("no_overlap_with_setup", SequenceDependentSetupPattern),
    ("qualified_operator", QualifiedOperatorPattern),
    ("shared_resource_exclusion", SharedResourceExclusionPattern),
    ("unavailable_intervals", UnavailableIntervalsPattern),
])
def test_each_pattern_in_registry(name: str, expected_cls: type[Pattern]) -> None:
    cls = PATTERNS[name]
    assert cls is expected_cls
    assert cls.name == name
    assert cls.description  # non-vide


# ---------- Smoke tests sur les classes : équivalence avec les fonctions ----------


def test_no_overlap_class_produces_correct_solve() -> None:
    """Deux ops durée 5 sur la même machine → makespan 10 via classe."""
    model = cp_model.CpModel()
    horizon = 20
    s1 = model.new_int_var(0, horizon, "s1")
    e1 = model.new_int_var(0, horizon, "e1")
    i1 = model.new_interval_var(s1, 5, e1, "i1")
    s2 = model.new_int_var(0, horizon, "s2")
    e2 = model.new_int_var(0, horizon, "e2")
    i2 = model.new_interval_var(s2, 5, e2, "i2")

    NoOverlapMachinePattern().apply(model, intervals=[i1, i2])

    makespan = model.new_int_var(0, horizon, "ms")
    model.add_max_equality(makespan, [e1, e2])
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert int(solver.objective_value) == 10


def test_precedence_class_chains_correctly() -> None:
    model = cp_model.CpModel()
    horizon = 30
    starts, ends = [], []
    for k, dur in enumerate([4, 3, 2]):
        s = model.new_int_var(0, horizon, f"s{k}")
        e = model.new_int_var(0, horizon, f"e{k}")
        model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)

    PrecedenceInJobPattern().apply(model, end_vars=ends, start_vars=starts)

    makespan = model.new_int_var(0, horizon, "ms")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert int(solver.objective_value) == 9


def test_makespan_class_returns_var() -> None:
    model = cp_model.CpModel()
    e1 = model.new_int_var(0, 100, "e1")
    e2 = model.new_int_var(0, 100, "e2")
    model.new_interval_var(model.new_int_var(0, 100, "s1"), 7, e1, "i1")
    model.new_interval_var(model.new_int_var(0, 100, "s2"), 4, e2, "i2")
    ms = MakespanObjectivePattern().apply(model, end_vars=[e1, e2], horizon=50)
    assert ms is not None
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert int(solver.value(ms)) == 7


def test_setup_class_groups_families() -> None:
    """Reprend le golden test setup-dependent via la classe."""
    model = cp_model.CpModel()
    starts, ends = [], []
    for k, dur in enumerate([5, 3, 4]):
        s = model.new_int_var(0, 100, f"s{k}")
        e = model.new_int_var(0, 100, f"e{k}")
        model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)

    SequenceDependentSetupPattern().apply(
        model,
        starts=starts,
        ends=ends,
        family_ids=[0, 1, 0],
        transition_matrix=[[0, 2], [2, 0]],
    )
    makespan = model.new_int_var(0, 100, "ms")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert int(solver.objective_value) == 14


def test_qualified_operator_class_forces_sequencing() -> None:
    """1 opérateur, 2 ops indépendantes → séquentiel via classe."""
    model = cp_model.CpModel()
    durations = [5, 4]
    starts, ends = [], []
    for k, dur in enumerate(durations):
        s = model.new_int_var(0, 100, f"s{k}")
        e = model.new_int_var(0, 100, f"e{k}")
        model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)

    QualifiedOperatorPattern().apply(
        model,
        starts=starts,
        ends=ends,
        durations=durations,
        qualifications=[[0], [0]],
        n_operators=1,
    )
    makespan = model.new_int_var(0, 100, "ms")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert int(solver.objective_value) == 9


def test_shared_resource_class_serializes_at_capacity_one() -> None:
    model = cp_model.CpModel()
    intervals, ends = [], []
    for k in range(3):
        s = model.new_int_var(0, 100, f"s{k}")
        e = model.new_int_var(0, 100, f"e{k}")
        intervals.append(model.new_interval_var(s, 5, e, f"i{k}"))
        ends.append(e)

    SharedResourceExclusionPattern().apply(model, intervals=intervals, max_concurrent=1)
    ms = model.new_int_var(0, 100, "ms")
    model.add_max_equality(ms, ends)
    model.minimize(ms)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert int(solver.objective_value) == 15


def test_unavailable_intervals_class_returns_intervals() -> None:
    model = cp_model.CpModel()
    intervals = UnavailableIntervalsPattern().apply(model, periods=[(3, 8), (13, 18)])
    assert len(intervals) == 2


def test_unavailable_intervals_class_blocks_op() -> None:
    """Op 5min + indispo [3,8] → makespan 13 via classe."""
    model = cp_model.CpModel()
    s = model.new_int_var(0, 100, "s")
    e = model.new_int_var(0, 100, "e")
    op_int = model.new_interval_var(s, 5, e, "op")

    unavail = UnavailableIntervalsPattern().apply(model, periods=[(3, 8)])
    NoOverlapMachinePattern().apply(model, intervals=[op_int, *unavail])
    model.minimize(e)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL
    assert int(solver.objective_value) == 13


# ---------- Pattern instantiation errors propagate ----------


def test_precedence_class_validates_lengths() -> None:
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="même longueur"):
        PrecedenceInJobPattern().apply(model, end_vars=[e], start_vars=[s, s])


def test_setup_class_validates_matrix_shape() -> None:
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="carrée"):
        SequenceDependentSetupPattern().apply(
            model,
            starts=[s, s],
            ends=[e, e],
            family_ids=[0, 0],
            transition_matrix=[[0, 1], [1]],
        )
