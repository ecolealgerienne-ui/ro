"""Tests du générateur d'ateliers synthétiques."""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from src.generators.distributions import (
    MACHINE_TYPES_DEFAULT,
    OPERATION_MACHINE_COMPAT,
    OPERATIONS_CANONICAL,
)
from src.generators.workshop_generator import (
    GenerationParams,
    SyntheticWorkshop,
    generate_workshop,
)


# ---------- Validation des params ----------


def test_params_default_values() -> None:
    p = GenerationParams()
    assert p.n_machines_min == 5
    assert p.n_machines_max == 25
    assert p.seed == 42


def test_params_rejects_min_greater_than_max() -> None:
    with pytest.raises(ValidationError, match="n_machines"):
        GenerationParams(n_machines_min=30, n_machines_max=10)


# ---------- Reproductibilité ----------


def test_same_seed_produces_identical_output() -> None:
    params = GenerationParams(seed=123, n_machines_min=10, n_machines_max=10, n_jobs_min=20, n_jobs_max=20)
    w1 = generate_workshop(params)
    w2 = generate_workshop(params)
    assert w1.model_dump_json() == w2.model_dump_json()


def test_different_seeds_produce_different_outputs() -> None:
    p1 = GenerationParams(seed=1, n_machines_min=10, n_machines_max=10, n_jobs_min=20, n_jobs_max=20)
    p2 = GenerationParams(seed=2, n_machines_min=10, n_machines_max=10, n_jobs_min=20, n_jobs_max=20)
    w1 = generate_workshop(p1)
    w2 = generate_workshop(p2)
    assert w1.model_dump_json() != w2.model_dump_json()


# ---------- Respect des bornes ----------


def test_machines_count_within_range() -> None:
    params = GenerationParams(seed=7, n_machines_min=8, n_machines_max=12)
    workshop = generate_workshop(params)
    assert 8 <= len(workshop.machines) <= 12


def test_jobs_count_within_range() -> None:
    params = GenerationParams(seed=7, n_jobs_min=30, n_jobs_max=60)
    workshop = generate_workshop(params)
    assert 30 <= len(workshop.orders) <= 60


def test_operators_count_within_range() -> None:
    params = GenerationParams(seed=7, n_operators_min=4, n_operators_max=8)
    workshop = generate_workshop(params)
    assert 4 <= len(workshop.operators) <= 8


def test_operations_per_job_within_range() -> None:
    params = GenerationParams(
        seed=7,
        n_machines_min=15,
        n_machines_max=15,
        n_jobs_min=50,
        n_jobs_max=50,
        operations_per_job_min=3,
        operations_per_job_max=5,
    )
    workshop = generate_workshop(params)
    for order in workshop.orders:
        assert 3 <= len(order.operations) <= 5


# ---------- Cohérence opérations × machines ----------


def test_operations_have_at_least_one_compatible_machine() -> None:
    """Aucune opération générée ne doit pointer vers une liste vide de machines."""
    params = GenerationParams(seed=42, n_jobs_min=100, n_jobs_max=100)
    workshop = generate_workshop(params)
    for order in workshop.orders:
        for op in order.operations:
            assert op.compatible_machine_ids, (
                f"Opération {op.operation_type} de l'OF {order.order_id} sans machine compatible"
            )


def test_compatible_machine_ids_match_actual_machines() -> None:
    params = GenerationParams(seed=99, n_jobs_min=50, n_jobs_max=50)
    workshop = generate_workshop(params)
    machine_ids = {m.machine_id for m in workshop.machines}
    machine_types_by_id = {m.machine_id: m.machine_type for m in workshop.machines}
    for order in workshop.orders:
        for op in order.operations:
            for mid in op.compatible_machine_ids:
                assert mid in machine_ids
                # La machine doit avoir un type compatible avec l'opération
                machine_type = machine_types_by_id[mid]
                assert machine_type in OPERATION_MACHINE_COMPAT[op.operation_type]


def test_machine_types_are_valid() -> None:
    params = GenerationParams(seed=7)
    workshop = generate_workshop(params)
    valid_types = set(MACHINE_TYPES_DEFAULT.keys())
    for m in workshop.machines:
        assert m.machine_type in valid_types


def test_operations_use_canonical_types() -> None:
    params = GenerationParams(seed=7, n_jobs_min=50, n_jobs_max=50)
    workshop = generate_workshop(params)
    valid_ops = set(OPERATIONS_CANONICAL)
    for order in workshop.orders:
        for op in order.operations:
            assert op.operation_type in valid_ops


# ---------- Cohérence métier ----------


def test_client_tier_matches_priority_weight() -> None:
    params = GenerationParams(seed=7, n_jobs_min=100, n_jobs_max=100)
    workshop = generate_workshop(params)
    expected = {1: 10, 2: 5, 3: 1}
    for order in workshop.orders:
        assert order.priority_weight == expected[order.client_tier]


def test_deadline_within_horizon() -> None:
    params = GenerationParams(seed=7, planning_horizon_days=14, n_jobs_min=50, n_jobs_max=50)
    workshop = generate_workshop(params)
    deadlines_offsets = [(o.deadline - workshop.orders[0].deadline).days for o in workshop.orders]
    # Deadlines décalées de 1 à horizon_days, donc l'écart max ≤ horizon - 1
    assert min(deadlines_offsets) >= -(params.planning_horizon_days - 1)
    assert max(deadlines_offsets) <= (params.planning_horizon_days - 1)


def test_durations_are_positive() -> None:
    params = GenerationParams(seed=7, n_jobs_min=50, n_jobs_max=50)
    workshop = generate_workshop(params)
    for order in workshop.orders:
        for op in order.operations:
            assert op.estimated_duration_min >= 1


def test_operators_have_at_least_one_qualification() -> None:
    params = GenerationParams(seed=7, n_operators_min=5, n_operators_max=5)
    workshop = generate_workshop(params)
    for op in workshop.operators:
        assert len(op.qualifications) >= 1


# ---------- Performance ----------


def test_single_workshop_under_2_seconds() -> None:
    """Critère de sortie 0.5 : 1 atelier généré en < 2s."""
    params = GenerationParams(seed=42)  # défauts : peut aller jusqu'à 25 machines, 300 jobs
    t0 = time.perf_counter()
    generate_workshop(params)
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"Génération trop lente : {elapsed:.2f}s"


def test_batch_of_10_under_5_seconds() -> None:
    t0 = time.perf_counter()
    for s in range(10):
        generate_workshop(GenerationParams(seed=s))
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"Batch de 10 trop lent : {elapsed:.2f}s"


# ---------- Sérialisation ----------


def test_output_serializes_to_json() -> None:
    params = GenerationParams(seed=7)
    workshop = generate_workshop(params)
    json_str = workshop.model_dump_json(indent=2)
    assert json_str.startswith("{")
    parsed = SyntheticWorkshop.model_validate_json(json_str)
    assert len(parsed.machines) == len(workshop.machines)
    assert len(parsed.orders) == len(workshop.orders)


def test_output_metadata_has_expected_keys() -> None:
    params = GenerationParams(seed=42)
    workshop = generate_workshop(params)
    expected_keys = {"seed", "n_machines", "n_operators", "n_jobs", "planning_horizon_days", "generator_version"}
    assert expected_keys <= set(workshop.metadata.keys())
