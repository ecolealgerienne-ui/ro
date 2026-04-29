"""Tests unitaires des primitives CP-SAT de `src.core.patterns`.

Chaque pattern est testé isolément en construisant un mini-modèle minimal et
en vérifiant la cohérence du résultat solver.
"""

from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from src.core.patterns import (
    add_no_overlap_machine,
    add_no_overlap_with_setup,
    add_precedence_in_job,
    make_makespan_objective,
)


# ----- add_no_overlap_machine -----


def test_no_overlap_forces_sequencing() -> None:
    """Deux opérations sur la même machine ne peuvent pas se chevaucher."""
    model = cp_model.CpModel()
    horizon = 20
    s1 = model.new_int_var(0, horizon, "s1")
    e1 = model.new_int_var(0, horizon, "e1")
    i1 = model.new_interval_var(s1, 5, e1, "i1")
    s2 = model.new_int_var(0, horizon, "s2")
    e2 = model.new_int_var(0, horizon, "e2")
    i2 = model.new_interval_var(s2, 5, e2, "i2")

    add_no_overlap_machine(model, [i1, i2])

    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, [e1, e2])
    model.minimize(makespan)

    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    # Deux opés de durée 5 séquencées → makespan = 10
    assert int(solver.objective_value) == 10


def test_no_overlap_empty_or_singleton_is_noop() -> None:
    """0 ou 1 interval → pas de contrainte ajoutée, le modèle reste résoluble."""
    model = cp_model.CpModel()
    s = model.new_int_var(0, 100, "s")
    e = model.new_int_var(0, 100, "e")
    i = model.new_interval_var(s, 3, e, "i")

    add_no_overlap_machine(model, [])
    add_no_overlap_machine(model, [i])

    model.minimize(e)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 3


# ----- add_precedence_in_job -----


def test_precedence_chains_three_ops() -> None:
    """Trois opés en chaîne → makespan = somme des durées."""
    model = cp_model.CpModel()
    horizon = 50
    starts, ends = [], []
    for k, dur in enumerate([4, 3, 2]):
        s = model.new_int_var(0, horizon, f"s{k}")
        e = model.new_int_var(0, horizon, f"e{k}")
        model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)

    add_precedence_in_job(model, ends, starts)

    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)

    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 4 + 3 + 2  # 9


def test_precedence_mismatched_lengths_raises() -> None:
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="même longueur"):
        add_precedence_in_job(model, [e], [s, s])


def test_precedence_singleton_is_noop() -> None:
    """Un seul élément → pas de contrainte mais pas d'erreur."""
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    model.new_interval_var(s, 5, e, "i")
    add_precedence_in_job(model, [e], [s])
    model.minimize(e)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 5


# ----- make_makespan_objective -----


def test_makespan_minimizes_to_max_end() -> None:
    """Avec deux fins indépendantes, makespan = max(durées)."""
    model = cp_model.CpModel()
    horizon = 30
    s1 = model.new_int_var(0, horizon, "s1")
    e1 = model.new_int_var(0, horizon, "e1")
    model.new_interval_var(s1, 7, e1, "i1")
    s2 = model.new_int_var(0, horizon, "s2")
    e2 = model.new_int_var(0, horizon, "e2")
    model.new_interval_var(s2, 4, e2, "i2")

    make_makespan_objective(model, [e1, e2], horizon)

    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 7


def test_makespan_empty_raises() -> None:
    model = cp_model.CpModel()
    with pytest.raises(ValueError, match="vide"):
        make_makespan_objective(model, [], horizon=100)


def test_makespan_negative_horizon_raises() -> None:
    model = cp_model.CpModel()
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="horizon"):
        make_makespan_objective(model, [e], horizon=-1)


# ----- add_no_overlap_with_setup -----


def _build_machine_with_setup(
    durations: list[int],
    family_ids: list[int],
    transition_matrix: list[list[int]],
    horizon: int = 100,
) -> tuple[cp_model.CpModel, list, list, list]:
    """Construit un modèle avec n opérations sur une machine + setup."""
    model = cp_model.CpModel()
    starts, ends, intervals = [], [], []
    for k, dur in enumerate(durations):
        s = model.new_int_var(0, horizon, f"s{k}")
        e = model.new_int_var(0, horizon, f"e{k}")
        i = model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)
        intervals.append(i)
    add_no_overlap_with_setup(model, starts, ends, family_ids, transition_matrix)
    return model, starts, ends, intervals


def test_setup_groups_same_family_optimally() -> None:
    """3 ops, 2 familles A/B, transition de 2.

    op0=A(5), op1=B(3), op2=A(4).
    Optimum = 14 (regrouper la famille A ou B → un seul changement = 2).
    Sans setup ce serait 12 ; avec setup mal placé ce serait 16.
    """
    durations = [5, 3, 4]
    family_ids = [0, 1, 0]  # A, B, A
    transition_matrix = [
        [0, 2],
        [2, 0],
    ]
    model, _, ends, _ = _build_machine_with_setup(durations, family_ids, transition_matrix)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 14


def test_setup_zero_matrix_equals_pure_no_overlap() -> None:
    """Avec une matrice de transition nulle, le makespan = somme des durées."""
    durations = [5, 3, 4]
    family_ids = [0, 1, 0]
    transition_matrix = [
        [0, 0],
        [0, 0],
    ]
    model, _, ends, _ = _build_machine_with_setup(durations, family_ids, transition_matrix)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == sum(durations)


def test_setup_intra_family_zero_inter_family_costly() -> None:
    """5 ops, 2 familles, transition inter-famille = 10.

    Familles : [A, A, B, B, A]
    Durées :   [3, 2, 4, 1, 2]
    Best : grouper A(3+2+2=7) puis B(4+1=5), ou inverse, avec une transition.
    Optimum = 7+5+10 = 22 (si tout en A puis B, ou inverse).
    """
    durations = [3, 2, 4, 1, 2]
    family_ids = [0, 0, 1, 1, 0]
    transition_matrix = [
        [0, 10],
        [10, 0],
    ]
    model, _, ends, _ = _build_machine_with_setup(durations, family_ids, transition_matrix)
    makespan = model.new_int_var(0, 200, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 22


def test_setup_asymmetric_matrix_picks_cheaper_direction() -> None:
    """Transitions A→B=10, B→A=2. Optimum = commencer par A puis aller en B.

    op0=A(3), op1=B(4). Si A puis B : 3+10+4 = 17. Si B puis A : 4+2+3 = 9.
    """
    durations = [3, 4]
    family_ids = [0, 1]
    transition_matrix = [
        [0, 10],
        [2, 0],
    ]
    model, _, ends, _ = _build_machine_with_setup(durations, family_ids, transition_matrix)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 9


def test_setup_singleton_is_noop() -> None:
    """Un seul op → pas de contrainte, makespan = durée."""
    durations = [7]
    family_ids = [0]
    transition_matrix = [[0]]
    model, _, ends, _ = _build_machine_with_setup(durations, family_ids, transition_matrix)
    model.minimize(ends[0])
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 7


def test_setup_validates_lengths() -> None:
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="même longueur"):
        add_no_overlap_with_setup(model, [s], [e, e], [0], [[0]])
    with pytest.raises(ValueError, match="même longueur"):
        add_no_overlap_with_setup(model, [s], [e], [0, 0], [[0]])


def test_setup_validates_square_matrix() -> None:
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="carrée"):
        add_no_overlap_with_setup(model, [s, s], [e, e], [0, 0], [[0, 1], [1]])


def test_setup_rejects_negative_values() -> None:
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="négatives"):
        add_no_overlap_with_setup(model, [s, s], [e, e], [0, 0], [[0, -1], [1, 0]])


def test_setup_rejects_out_of_range_family_id() -> None:
    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="hors borne"):
        add_no_overlap_with_setup(model, [s, s], [e, e], [0, 5], [[0, 1], [1, 0]])


# ----- add_qualified_operator_constraint -----


def _build_two_independent_ops(
    durations: list[int],
    qualifications: list[list[int]],
    n_operators: int,
    horizon: int = 100,
) -> tuple[cp_model.CpModel, list, list]:
    """Construit 2 opérations indépendantes (pas de NoOverlap machine)."""
    from src.core.patterns import add_qualified_operator_constraint

    model = cp_model.CpModel()
    starts, ends = [], []
    for k, dur in enumerate(durations):
        s = model.new_int_var(0, horizon, f"s{k}")
        e = model.new_int_var(0, horizon, f"e{k}")
        model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)
    add_qualified_operator_constraint(model, starts, ends, durations, qualifications, n_operators)
    return model, starts, ends


def test_single_operator_forces_sequencing() -> None:
    """2 ops indépendantes (pas même machine) mais 1 seul opérateur qualifié → séquentiel."""
    durations = [5, 4]
    qualifications = [[0], [0]]  # seul l'opérateur 0 peut faire les deux
    n_operators = 1
    model, _, ends = _build_two_independent_ops(durations, qualifications, n_operators)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    # Forcé séquentiel : 5 + 4 = 9
    assert int(solver.objective_value) == 9


def test_two_operators_allow_parallel() -> None:
    """2 ops indépendantes, 2 opérateurs qualifiés chacun → parallèle possible."""
    from src.core.patterns import add_qualified_operator_constraint

    durations = [5, 4]
    qualifications = [[0, 1], [0, 1]]
    n_operators = 2
    model = cp_model.CpModel()
    starts, ends = [], []
    for k, dur in enumerate(durations):
        s = model.new_int_var(0, 100, f"s{k}")
        e = model.new_int_var(0, 100, f"e{k}")
        model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)
    add_qualified_operator_constraint(model, starts, ends, durations, qualifications, n_operators)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    # Avec 2 opérateurs, parallélisable → max(5, 4) = 5
    assert int(solver.objective_value) == 5


def test_disjoint_qualifications_force_specific_assignment() -> None:
    """3 ops indépendantes, qualifications disjointes : op0→opérateur0, op1→opérateur1, op2→opérateur0."""
    from src.core.patterns import add_qualified_operator_constraint

    durations = [3, 4, 5]
    qualifications = [[0], [1], [0]]
    n_operators = 2
    model = cp_model.CpModel()
    starts, ends = [], []
    for k, dur in enumerate(durations):
        s = model.new_int_var(0, 100, f"s{k}")
        e = model.new_int_var(0, 100, f"e{k}")
        model.new_interval_var(s, dur, e, f"i{k}")
        starts.append(s)
        ends.append(e)
    add_qualified_operator_constraint(model, starts, ends, durations, qualifications, n_operators)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    # Opérateur 0 fait op0 (3) + op2 (5) = 8 séquentiel
    # Opérateur 1 fait op1 (4) en parallèle
    # → makespan = max(8, 4) = 8
    assert int(solver.objective_value) == 8


def test_qualified_operator_validates_lengths() -> None:
    from src.core.patterns import add_qualified_operator_constraint

    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="même longueur"):
        add_qualified_operator_constraint(
            model, [s], [e, e], [5], [[0]], n_operators=1
        )


def test_qualified_operator_rejects_empty_qualifications() -> None:
    from src.core.patterns import add_qualified_operator_constraint

    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="sans opérateur qualifié"):
        add_qualified_operator_constraint(model, [s], [e], [3], [[]], n_operators=1)


def test_qualified_operator_rejects_out_of_range() -> None:
    from src.core.patterns import add_qualified_operator_constraint

    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    with pytest.raises(ValueError, match="hors borne"):
        add_qualified_operator_constraint(model, [s], [e], [3], [[5]], n_operators=2)


# ----- add_shared_resource_exclusion -----


def _build_n_independent_ops(n: int, duration: int, horizon: int = 100):
    model = cp_model.CpModel()
    intervals, ends = [], []
    for k in range(n):
        s = model.new_int_var(0, horizon, f"s{k}")
        e = model.new_int_var(0, horizon, f"e{k}")
        i = model.new_interval_var(s, duration, e, f"i{k}")
        intervals.append(i)
        ends.append(e)
    return model, intervals, ends


def test_shared_resource_capacity_one_serializes_all() -> None:
    """3 ops, capacité 1 → toutes séquentielles → makespan = 3 × duration."""
    from src.core.patterns import add_shared_resource_exclusion

    model, intervals, ends = _build_n_independent_ops(n=3, duration=5)
    add_shared_resource_exclusion(model, intervals, max_concurrent=1)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 15


def test_shared_resource_capacity_two_allows_pairs() -> None:
    """3 ops de durée 5, capacité 2 → 2 en parallèle + 1 reste → makespan = 10."""
    from src.core.patterns import add_shared_resource_exclusion

    model, intervals, ends = _build_n_independent_ops(n=3, duration=5)
    add_shared_resource_exclusion(model, intervals, max_concurrent=2)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 10


def test_shared_resource_capacity_geq_count_is_noop() -> None:
    """3 ops, capacité 3 → tous parallèles → makespan = duration."""
    from src.core.patterns import add_shared_resource_exclusion

    model, intervals, ends = _build_n_independent_ops(n=3, duration=5)
    add_shared_resource_exclusion(model, intervals, max_concurrent=3)
    makespan = model.new_int_var(0, 100, "makespan")
    model.add_max_equality(makespan, ends)
    model.minimize(makespan)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert int(solver.objective_value) == 5


def test_shared_resource_rejects_zero_capacity() -> None:
    from src.core.patterns import add_shared_resource_exclusion

    model = cp_model.CpModel()
    s = model.new_int_var(0, 10, "s")
    e = model.new_int_var(0, 10, "e")
    i = model.new_interval_var(s, 3, e, "i")
    with pytest.raises(ValueError, match="≥ 1"):
        add_shared_resource_exclusion(model, [i], max_concurrent=0)
