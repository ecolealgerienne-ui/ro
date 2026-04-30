"""Modèles de données du POC scheduler.

Représente un atelier d'ordonnancement (Job-Shop Scheduling Problem) :
jobs avec gammes opératoires séquentielles, machines, opérations.

Étape 1.1b : enrichissement avec les contraintes industrielles
- `Operation.family_id` et `qualified_operator_ids` (per-operation)
- `WorkshopInstance.n_operators`, `transition_matrix`, `shared_resources`,
  `machine_unavailability` (per-instance)

Tous les nouveaux champs sont **optionnels avec valeur par défaut neutre** —
les instances JSSP existantes (Taillard, mini-tests) restent valides sans
modification.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Operation(BaseModel):
    """Une opération à effectuer sur une machine donnée pour un job donné."""

    model_config = ConfigDict(frozen=True)

    job_id: int = Field(..., ge=0, description="Identifiant du job parent (0-indexé)")
    sequence_idx: int = Field(..., ge=0, description="Position dans la gamme du job (0-indexé)")
    machine_id: int = Field(
        ..., ge=0, description="Machine sur laquelle l'opération s'exécute (0-indexé)"
    )
    duration: int = Field(
        ..., ge=0, description="Durée d'exécution (unités cohérentes avec l'instance)"
    )

    # Champs industriels (étape 1.1b) — neutres par défaut
    family_id: int = Field(
        default=0,
        ge=0,
        description="Identifiant de famille de pièce, indice dans `WorkshopInstance.transition_matrix`. "
        "Valeur par défaut 0 ; ignorée si `transition_matrix` est vide.",
    )
    qualified_operator_ids: list[int] = Field(
        default_factory=list,
        description="Liste des operator_id qualifiés pour cette opération. "
        "Vide = pas de contrainte opérateur (tout opérateur peut faire l'op).",
    )


class Job(BaseModel):
    """Un job composé d'une suite ordonnée d'opérations (gamme opératoire).

    Champs optionnels (étape 1.6) :
        - deadline : échéance en unités de temps cohérentes avec horizon. Permet
          aux soft constraints de pénaliser la tardiveté.
        - client : identifiant du donneur d'ordre. Permet aux soft constraints
          de moduler la priorité par client.
    """

    model_config = ConfigDict(frozen=True)

    job_id: int = Field(..., ge=0)
    operations: list[Operation]
    deadline: int | None = Field(
        default=None,
        ge=0,
        description="Échéance en unités de temps cohérentes avec horizon. None = pas de contrainte.",
    )
    client: str | None = Field(
        default=None,
        description="Identifiant du donneur d'ordre (texte libre).",
    )

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


class SharedResourceSpec(BaseModel):
    """Ressource partagée par plusieurs machines : limite de N opérations actives simultanément."""

    model_config = ConfigDict(frozen=True)

    resource_name: str
    machine_ids: list[int]
    max_concurrent: int = Field(..., ge=1)

    @model_validator(mode="after")
    def _check_machine_ids_non_empty(self) -> SharedResourceSpec:
        if not self.machine_ids:
            raise ValueError(f"SharedResource '{self.resource_name}' : machine_ids vide")
        if len(self.machine_ids) != len(set(self.machine_ids)):
            raise ValueError(
                f"SharedResource '{self.resource_name}' : machine_ids contient des doublons"
            )
        return self


class MachineUnavailabilitySpec(BaseModel):
    """Plages d'indisponibilité d'une machine (pauses, MP, weekends)."""

    model_config = ConfigDict(frozen=True)

    machine_id: int = Field(..., ge=0)
    periods: list[tuple[int, int]]

    @model_validator(mode="after")
    def _check_periods(self) -> MachineUnavailabilitySpec:
        for i, (start, end) in enumerate(self.periods):
            if start < 0 or end < 0:
                raise ValueError(
                    f"Machine {self.machine_id}, période {i} : bornes négatives ({start}, {end})"
                )
            if start >= end:
                raise ValueError(
                    f"Machine {self.machine_id}, période {i} : start ({start}) doit être < end ({end})"
                )
        return self


class WorkshopInstance(BaseModel):
    """Une instance complète de problème d'ordonnancement.

    Représente un atelier chargé d'une liste de jobs à séquencer. Sert d'input
    au solveur CP-SAT.

    Champs JSSP de base (toujours présents) :
        - jobs, machines, name, best_known_makespan, metadata

    Champs industriels (étape 1.1b, optionnels) :
        - n_operators : nombre d'opérateurs distincts
        - transition_matrix : matrice carrée (n_families × n_families) des
          temps de setup entre familles
        - shared_resources : liste de ressources partagées
        - machine_unavailability : indisponibilités par machine
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

    # Champs industriels (étape 1.1b)
    n_operators: int = Field(
        default=0,
        ge=0,
        description="Nombre total d'opérateurs (operator_id ∈ [0, n_operators[). "
        "0 = pas de contrainte opérateur.",
    )
    transition_matrix: list[list[int]] = Field(
        default_factory=list,
        description="Matrice carrée des setup times inter-familles (en unités de temps). "
        "Vide = pas de setup-dependent.",
    )
    shared_resources: list[SharedResourceSpec] = Field(
        default_factory=list,
        description="Ressources partagées limitant le parallélisme.",
    )
    machine_unavailability: list[MachineUnavailabilitySpec] = Field(
        default_factory=list,
        description="Plages d'indisponibilité par machine.",
    )

    @property
    def n_jobs(self) -> int:
        return len(self.jobs)

    @property
    def n_machines(self) -> int:
        return len(self.machines)

    @property
    def has_operator_constraints(self) -> bool:
        if self.n_operators == 0:
            return False
        return any(op.qualified_operator_ids for job in self.jobs for op in job.operations)

    @property
    def has_setup_constraints(self) -> bool:
        return bool(self.transition_matrix)

    @property
    def has_shared_resources(self) -> bool:
        return bool(self.shared_resources)

    @property
    def has_unavailability(self) -> bool:
        return bool(self.machine_unavailability)

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

    @model_validator(mode="after")
    def _check_transition_matrix_shape(self) -> WorkshopInstance:
        if not self.transition_matrix:
            return self
        n = len(self.transition_matrix)
        for i, row in enumerate(self.transition_matrix):
            if len(row) != n:
                raise ValueError(
                    f"transition_matrix non carrée : ligne {i} de taille {len(row)} ≠ {n}"
                )
            for v in row:
                if v < 0:
                    raise ValueError(f"transition_matrix : valeurs négatives interdites ({v})")
        # Vérifie que tous les family_id des opérations sont dans la borne
        for job in self.jobs:
            for op in job.operations:
                if op.family_id >= n:
                    raise ValueError(
                        f"Operation (job={op.job_id}, seq={op.sequence_idx}) : "
                        f"family_id {op.family_id} ≥ taille matrice {n}"
                    )
        return self

    @model_validator(mode="after")
    def _check_qualified_operator_ids(self) -> WorkshopInstance:
        if self.n_operators == 0:
            return self
        for job in self.jobs:
            for op in job.operations:
                for op_id in op.qualified_operator_ids:
                    if not 0 <= op_id < self.n_operators:
                        raise ValueError(
                            f"Operation (job={op.job_id}, seq={op.sequence_idx}) : "
                            f"qualified_operator_id {op_id} hors borne [0, {self.n_operators}["
                        )
        return self

    @model_validator(mode="after")
    def _check_shared_resources_machine_ids(self) -> WorkshopInstance:
        if not self.shared_resources:
            return self
        valid_ids = {m.machine_id for m in self.machines}
        for res in self.shared_resources:
            for mid in res.machine_ids:
                if mid not in valid_ids:
                    raise ValueError(
                        f"SharedResource '{res.resource_name}' : machine_id {mid} "
                        "absent de l'atelier"
                    )
        return self

    @model_validator(mode="after")
    def _check_machine_unavailability(self) -> WorkshopInstance:
        if not self.machine_unavailability:
            return self
        valid_ids = {m.machine_id for m in self.machines}
        seen: set[int] = set()
        for spec in self.machine_unavailability:
            if spec.machine_id not in valid_ids:
                raise ValueError(
                    f"MachineUnavailability : machine_id {spec.machine_id} absent de l'atelier"
                )
            if spec.machine_id in seen:
                raise ValueError(
                    f"MachineUnavailability : machine_id {spec.machine_id} apparaît plusieurs fois"
                )
            seen.add(spec.machine_id)
        return self
