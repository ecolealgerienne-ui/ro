"""Tests des modèles Pydantic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.models import Job, Machine, Operation, WorkshopInstance


def _make_job(job_id: int, n_ops: int) -> Job:
    operations = [
        Operation(job_id=job_id, sequence_idx=i, machine_id=i, duration=10) for i in range(n_ops)
    ]
    return Job(job_id=job_id, operations=operations)


def test_operation_validates_non_negative() -> None:
    with pytest.raises(ValidationError):
        Operation(job_id=-1, sequence_idx=0, machine_id=0, duration=5)
    with pytest.raises(ValidationError):
        Operation(job_id=0, sequence_idx=0, machine_id=0, duration=-5)


def test_job_consistency_check_rejects_wrong_job_id() -> None:
    bad_op = Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5)
    with pytest.raises(ValidationError, match="incohérent"):
        Job(job_id=0, operations=[bad_op])


def test_job_consistency_check_rejects_wrong_sequence() -> None:
    op = Operation(job_id=0, sequence_idx=5, machine_id=0, duration=5)
    with pytest.raises(ValidationError, match="sequence_idx"):
        Job(job_id=0, operations=[op])


def test_workshop_instance_rejects_unknown_machine() -> None:
    job = _make_job(job_id=0, n_ops=2)
    with pytest.raises(ValidationError, match="absente"):
        WorkshopInstance(name="bad", jobs=[job], machines=[Machine(machine_id=0)])


def test_workshop_instance_rejects_duplicate_machines() -> None:
    job = _make_job(job_id=0, n_ops=1)
    with pytest.raises(ValidationError, match="dupliqués"):
        WorkshopInstance(
            name="dup",
            jobs=[job],
            machines=[Machine(machine_id=0), Machine(machine_id=0)],
        )


def test_workshop_instance_properties() -> None:
    jobs = [_make_job(job_id=j, n_ops=3) for j in range(2)]
    machines = [Machine(machine_id=m) for m in range(3)]
    instance = WorkshopInstance(name="ok", jobs=jobs, machines=machines)
    assert instance.n_jobs == 2
    assert instance.n_machines == 3


def test_models_are_frozen() -> None:
    op = Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)
    with pytest.raises(ValidationError):
        op.duration = 10  # type: ignore[misc]


# ---------- Champs industriels (étape 1.1b) ----------


from src.core.models import MachineUnavailabilitySpec, SharedResourceSpec  # noqa: E402


def _make_simple_instance(**kwargs):
    """Crée une instance minimale 1 job × 1 machine pour tester les nouveaux champs."""
    op = Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5, **kwargs)
    job = Job(job_id=0, operations=[op])
    machine = Machine(machine_id=0)
    return job, machine


def test_operation_default_family_id_zero() -> None:
    op = Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5)
    assert op.family_id == 0
    assert op.qualified_operator_ids == []


def test_operation_with_industrial_fields() -> None:
    op = Operation(
        job_id=0,
        sequence_idx=0,
        machine_id=0,
        duration=5,
        family_id=2,
        qualified_operator_ids=[0, 1, 3],
    )
    assert op.family_id == 2
    assert op.qualified_operator_ids == [0, 1, 3]


def test_workshop_instance_defaults_neutral() -> None:
    job, machine = _make_simple_instance()
    instance = WorkshopInstance(name="test", jobs=[job], machines=[machine])
    assert instance.n_operators == 0
    assert instance.transition_matrix == []
    assert instance.shared_resources == []
    assert instance.machine_unavailability == []
    assert not instance.has_setup_constraints
    assert not instance.has_operator_constraints
    assert not instance.has_shared_resources
    assert not instance.has_unavailability


def test_workshop_instance_has_setup_when_matrix_set() -> None:
    job, machine = _make_simple_instance(family_id=1)
    instance = WorkshopInstance(
        name="test",
        jobs=[job],
        machines=[machine],
        transition_matrix=[[0, 5], [5, 0]],
    )
    assert instance.has_setup_constraints


def test_workshop_instance_has_operator_when_qualifications_set() -> None:
    job, machine = _make_simple_instance(qualified_operator_ids=[0])
    instance = WorkshopInstance(
        name="test",
        jobs=[job],
        machines=[machine],
        n_operators=2,
    )
    assert instance.has_operator_constraints


def test_transition_matrix_must_be_square() -> None:
    job, machine = _make_simple_instance()
    with pytest.raises(ValidationError, match="non carrée"):
        WorkshopInstance(
            name="test",
            jobs=[job],
            machines=[machine],
            transition_matrix=[[0, 5], [5]],
        )


def test_transition_matrix_rejects_negative() -> None:
    job, machine = _make_simple_instance()
    with pytest.raises(ValidationError, match="négatives"):
        WorkshopInstance(
            name="test",
            jobs=[job],
            machines=[machine],
            transition_matrix=[[0, -1], [1, 0]],
        )


def test_family_id_must_be_within_matrix() -> None:
    job, machine = _make_simple_instance(family_id=5)
    with pytest.raises(ValidationError, match="family_id"):
        WorkshopInstance(
            name="test",
            jobs=[job],
            machines=[machine],
            transition_matrix=[[0, 1], [1, 0]],  # 2 familles, family_id=5 invalide
        )


def test_qualified_operator_id_within_n_operators() -> None:
    job, machine = _make_simple_instance(qualified_operator_ids=[3])
    with pytest.raises(ValidationError, match="qualified_operator_id"):
        WorkshopInstance(
            name="test",
            jobs=[job],
            machines=[machine],
            n_operators=2,
        )


def test_shared_resource_spec_validates_machine_ids() -> None:
    with pytest.raises(ValidationError, match="vide"):
        SharedResourceSpec(resource_name="aspi", machine_ids=[], max_concurrent=1)
    with pytest.raises(ValidationError, match="doublons"):
        SharedResourceSpec(resource_name="aspi", machine_ids=[0, 0], max_concurrent=1)


def test_shared_resource_must_reference_existing_machines() -> None:
    job, machine = _make_simple_instance()
    with pytest.raises(ValidationError, match="absent"):
        WorkshopInstance(
            name="test",
            jobs=[job],
            machines=[machine],
            shared_resources=[
                SharedResourceSpec(resource_name="aspi", machine_ids=[5], max_concurrent=1)
            ],
        )


def test_machine_unavailability_validates_periods() -> None:
    with pytest.raises(ValidationError, match=r"start.*<.*end"):
        MachineUnavailabilitySpec(machine_id=0, periods=[(10, 5)])
    with pytest.raises(ValidationError, match="négatives"):
        MachineUnavailabilitySpec(machine_id=0, periods=[(-1, 5)])


def test_machine_unavailability_rejects_unknown_machine() -> None:
    job, machine = _make_simple_instance()
    with pytest.raises(ValidationError, match="absent"):
        WorkshopInstance(
            name="test",
            jobs=[job],
            machines=[machine],
            machine_unavailability=[MachineUnavailabilitySpec(machine_id=99, periods=[(0, 10)])],
        )


def test_machine_unavailability_rejects_duplicates() -> None:
    job, machine = _make_simple_instance()
    with pytest.raises(ValidationError, match="plusieurs fois"):
        WorkshopInstance(
            name="test",
            jobs=[job],
            machines=[machine],
            machine_unavailability=[
                MachineUnavailabilitySpec(machine_id=0, periods=[(0, 10)]),
                MachineUnavailabilitySpec(machine_id=0, periods=[(20, 30)]),
            ],
        )
