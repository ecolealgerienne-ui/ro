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
