"""Tests unitaires des primitives CP-SAT de `src.core.patterns`.

Chaque pattern est testé isolément en construisant un mini-modèle minimal et
en vérifiant la cohérence du résultat solver.
"""

from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from src.core.patterns import (
    add_no_overlap_machine,
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
