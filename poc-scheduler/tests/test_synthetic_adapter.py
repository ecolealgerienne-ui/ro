"""Tests de l'adaptateur SyntheticWorkshop → WorkshopInstance JSSP."""

from __future__ import annotations

import pytest

from src.generators.workshop_generator import GenerationParams, generate_workshop
from src.loaders.synthetic_adapter import synthetic_to_jssp_instance


def test_adapter_preserves_job_count() -> None:
    params = GenerationParams(
        seed=42, n_machines_min=8, n_machines_max=8, n_jobs_min=20, n_jobs_max=20
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert instance.n_jobs == len(workshop.orders)


def test_adapter_preserves_machine_count() -> None:
    params = GenerationParams(
        seed=42, n_machines_min=10, n_machines_max=10, n_jobs_min=20, n_jobs_max=20
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert instance.n_machines == 10


def test_adapter_preserves_operations_count() -> None:
    params = GenerationParams(
        seed=42, n_machines_min=8, n_machines_max=8, n_jobs_min=15, n_jobs_max=15
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    expected = sum(len(o.operations) for o in workshop.orders)
    actual = sum(len(j.operations) for j in instance.jobs)
    assert actual == expected


def test_adapter_assigns_to_compatible_machine() -> None:
    """Chaque opération est assignée à une machine de sa liste compatible."""
    params = GenerationParams(seed=42, n_jobs_min=20, n_jobs_max=20)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    for j_idx, job in enumerate(instance.jobs):
        original_order = workshop.orders[j_idx]
        for op in job.operations:
            original_op = original_order.operations[op.sequence_idx]
            assert op.machine_id in original_op.compatible_machine_ids


def test_adapter_preserves_durations() -> None:
    params = GenerationParams(seed=42, n_jobs_min=15, n_jobs_max=15)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    for j_idx, job in enumerate(instance.jobs):
        original_order = workshop.orders[j_idx]
        for op in job.operations:
            original_op = original_order.operations[op.sequence_idx]
            assert op.duration == original_op.estimated_duration_min


def test_adapter_load_balances_across_compatible_machines() -> None:
    """Avec un atelier où plusieurs machines partagent les mêmes opérations,
    la charge doit être répartie."""
    params = GenerationParams(
        seed=42,
        n_machines_min=15,
        n_machines_max=15,
        n_jobs_min=50,
        n_jobs_max=50,
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)

    machine_load: dict[int, int] = {m.machine_id: 0 for m in instance.machines}
    for job in instance.jobs:
        for op in job.operations:
            machine_load[op.machine_id] += op.duration

    loads = [v for v in machine_load.values() if v > 0]
    if len(loads) >= 2:
        max_load = max(loads)
        min_load = min(loads)
        assert max_load <= min_load * 10, (
            f"Charge déséquilibrée : min={min_load}, max={max_load}"
        )


def test_adapter_metadata_includes_source() -> None:
    params = GenerationParams(seed=42)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert instance.metadata["source"] == "synthetic_workshop"
    assert instance.metadata["seed"] == "42"


def test_adapter_uses_custom_name() -> None:
    params = GenerationParams(seed=42)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop, name="custom_name")
    assert instance.name == "custom_name"


def test_adapter_default_name_includes_seed() -> None:
    params = GenerationParams(seed=99, n_machines_min=8, n_machines_max=8, n_jobs_min=10, n_jobs_max=10)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert "99" in instance.name


def test_adapter_validation_passes_on_generated_workshop() -> None:
    """L'instance produite doit passer la validation Pydantic du WorkshopInstance."""
    params = GenerationParams(seed=42, n_jobs_min=30, n_jobs_max=30)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    machine_ids = {m.machine_id for m in instance.machines}
    for job in instance.jobs:
        for op in job.operations:
            assert op.machine_id in machine_ids
            assert op.duration >= 1


# ---------- Champs industriels (étape 1.1b) ----------


def test_adapter_populates_n_operators_by_default() -> None:
    params = GenerationParams(seed=42, n_operators_min=8, n_operators_max=8)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert instance.n_operators == 8


def test_adapter_populates_transition_matrix_by_default() -> None:
    from src.generators.distributions import N_FAMILIES

    params = GenerationParams(seed=42)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert len(instance.transition_matrix) == N_FAMILIES
    assert all(len(row) == N_FAMILIES for row in instance.transition_matrix)
    # Diagonale doit être à 0 (pas de setup intra-famille)
    for i in range(N_FAMILIES):
        assert instance.transition_matrix[i][i] == 0


def test_adapter_assigns_family_ids_to_operations() -> None:
    from src.generators.distributions import OPERATION_FAMILY

    params = GenerationParams(seed=42, n_jobs_min=20, n_jobs_max=20)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    for j_idx, job in enumerate(instance.jobs):
        original_order = workshop.orders[j_idx]
        for op in job.operations:
            original_op = original_order.operations[op.sequence_idx]
            expected_family = OPERATION_FAMILY[original_op.operation_type]
            assert op.family_id == expected_family


def test_adapter_assigns_qualified_operator_ids() -> None:
    params = GenerationParams(seed=42, n_jobs_min=15, n_jobs_max=15, n_operators_min=5, n_operators_max=5)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    for job in instance.jobs:
        for op in job.operations:
            assert op.qualified_operator_ids
            assert all(0 <= oid < instance.n_operators for oid in op.qualified_operator_ids)


def test_adapter_qualified_operators_match_workshop_qualifications() -> None:
    """Si un opérateur est qualifié pour 'tournage_ebauche', il doit apparaître
    dans qualified_operator_ids des opérations de ce type."""
    params = GenerationParams(seed=7, n_jobs_min=20, n_jobs_max=20)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)

    qualified_by_type: dict[str, set[int]] = {}
    for op in workshop.operators:
        for qual in op.qualifications:
            qualified_by_type.setdefault(qual, set()).add(op.operator_id)

    for j_idx, job in enumerate(instance.jobs):
        original_order = workshop.orders[j_idx]
        for op in job.operations:
            original_op_type = original_order.operations[op.sequence_idx].operation_type
            expected = qualified_by_type.get(original_op_type)
            if expected:
                assert set(op.qualified_operator_ids) == expected


def test_adapter_propagates_shared_resources() -> None:
    params = GenerationParams(
        seed=42,
        shared_resource_probability=1.0,
        n_machines_min=10,
        n_machines_max=10,
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert len(instance.shared_resources) == len(workshop.shared_resources)
    for spec, original in zip(instance.shared_resources, workshop.shared_resources):
        assert spec.resource_name == original.resource_name
        assert spec.machine_ids == original.machine_ids
        assert spec.max_concurrent == original.max_concurrent


def test_adapter_disable_setup_keeps_neutral_defaults() -> None:
    params = GenerationParams(seed=42)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop, enable_setup=False)
    assert instance.transition_matrix == []
    for job in instance.jobs:
        for op in job.operations:
            assert op.family_id == 0


def test_adapter_disable_operators_keeps_neutral_defaults() -> None:
    params = GenerationParams(seed=42)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop, enable_operators=False)
    assert instance.n_operators == 0
    for job in instance.jobs:
        for op in job.operations:
            assert op.qualified_operator_ids == []


def test_adapter_disable_shared_resources_keeps_empty() -> None:
    params = GenerationParams(
        seed=42, shared_resource_probability=1.0, n_machines_min=10, n_machines_max=10
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop, enable_shared_resources=False)
    assert instance.shared_resources == []


def test_adapter_resulting_instance_has_industrial_flags() -> None:
    params = GenerationParams(
        seed=42,
        n_jobs_min=10,
        n_jobs_max=10,
        n_operators_min=3,
        n_operators_max=3,
    )
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop)
    assert instance.has_setup_constraints
    assert instance.has_operator_constraints


def test_adapter_metadata_records_flags() -> None:
    params = GenerationParams(seed=42)
    workshop = generate_workshop(params)
    instance = synthetic_to_jssp_instance(workshop, enable_setup=False, enable_operators=True)
    assert instance.metadata["enable_setup"] == "False"
    assert instance.metadata["enable_operators"] == "True"
