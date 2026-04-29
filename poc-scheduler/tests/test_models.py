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
