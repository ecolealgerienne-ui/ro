"""Modèles de données du POC scheduler.

Représente un atelier d'ordonnancement (Job-Shop Scheduling Problem) :
jobs avec gammes opératoires séquentielles, machines, opérations.

Utilisé en entrée du solveur CP-SAT et en sortie des loaders.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Operation(BaseModel):
    """Une opération à effectuer sur une machine donnée pour un job donné."""

    model_config = ConfigDict(frozen=True)

    job_id: int = Field(..., ge=0, description="Identifiant du job parent (0-indexé)")
    sequence_idx: int = Field(..., ge=0, description="Position dans la gamme du job (0-indexé)")
    machine_id: int = Field(..., ge=0, description="Machine sur laquelle l'opération s'exécute (0-indexé)")
    duration: int = Field(..., ge=0, description="Durée d'exécution (unités cohérentes avec l'instance)")


class Job(BaseModel):
    """Un job composé d'une suite ordonnée d'opérations (gamme opératoire)."""

    model_config = ConfigDict(frozen=True)

    job_id: int = Field(..., ge=0)
    operations: list[Operation]

    @model_validator(mode="after")
    def _check_operations_consistency(self) -> Job:
        for idx, op in enumerate(self.operations):
            if op.job_id != self.job_id:
                raise ValueError(
                    f"Operation.job_id={op.job_id} incohérent avec Job.job_id={self.job_id}"
                )
            if op.sequence_idx != idx:
                raise ValueError(
                    f"Operation.sequence_idx={op.sequence_idx} attendu {idx} dans le job {self.job_id}"
                )
        return self

    @property
    def n_operations(self) -> int:
        return len(self.operations)


class Machine(BaseModel):
    """Une machine de l'atelier."""

    model_config = ConfigDict(frozen=True)

    machine_id: int = Field(..., ge=0)
    name: str | None = None


class WorkshopInstance(BaseModel):
    """Une instance complète de problème d'ordonnancement.

    Représente un atelier (machines, opérateurs implicites en JSSP) chargé d'une
    liste de jobs à séquencer. Sert d'input au solveur CP-SAT.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    jobs: list[Job]
    machines: list[Machine]
    best_known_makespan: int | None = Field(
        default=None,
        description="Optimum ou meilleure valeur connue pour cette instance (pour benchmarks)",
    )
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def n_jobs(self) -> int:
        return len(self.jobs)

    @property
    def n_machines(self) -> int:
        return len(self.machines)

    @model_validator(mode="after")
    def _check_machine_ids(self) -> WorkshopInstance:
        machine_ids = {m.machine_id for m in self.machines}
        for job in self.jobs:
            for op in job.operations:
                if op.machine_id not in machine_ids:
                    raise ValueError(
                        f"Operation référence machine_id={op.machine_id} absente "
                        f"de la liste des machines de l'instance {self.name}"
                    )
        return self

    @model_validator(mode="after")
    def _check_unique_machine_ids(self) -> WorkshopInstance:
        ids = [m.machine_id for m in self.machines]
        if len(ids) != len(set(ids)):
            raise ValueError(f"machine_id dupliqués dans l'instance {self.name}")
        return self
