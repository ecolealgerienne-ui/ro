"""Générateur d'ateliers de mécanique de précision synthétiques.

Étape 0.5 — socle structurel :
- Machines (typées selon distribution réaliste)
- Opérateurs (qualifications par opération)
- OF (Ordres de Fabrication) avec gammes opératoires sur machines compatibles
- Métadonnées + reproductibilité par seed

Hors scope 0.5 (déplacé en 0.6) : sequence-dependent setup matrix,
shared resources, calendars multi-équipes, soft constraints en langage
naturel, certification, mode `--with-noise`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

import numpy as np
from numpy.random import Generator
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.verticals.mech_workshop.distributions import (
    CLIENT_NAMES_BY_TIER,
    CLIENT_TIER_WEIGHT,
    CLIENT_TIERS,
    MACHINE_TYPES_DEFAULT,
    MATERIAL_DIFFICULTY_MULTIPLIER,
    MATERIALS_DEFAULT,
    OPERATION_BASE_TIMES_MIN,
    OPERATION_MACHINE_COMPAT,
    OPERATIONS_CANONICAL,
)

# ---------- Paramètres de génération ----------


class GenerationParams(BaseModel):
    """Paramètres de génération d'un atelier."""

    model_config = ConfigDict(frozen=True)

    n_machines_min: int = Field(default=5, ge=1)
    n_machines_max: int = Field(default=25, ge=1)
    n_operators_min: int = Field(default=3, ge=1)
    n_operators_max: int = Field(default=30, ge=1)
    n_jobs_min: int = Field(default=50, ge=1)
    n_jobs_max: int = Field(default=300, ge=1)

    operations_per_job_min: int = Field(default=2, ge=1)
    operations_per_job_max: int = Field(default=8, ge=1)

    planning_horizon_days: int = Field(default=10, ge=1)

    # Distributions personnalisables (None = défaut métier)
    machine_types_distribution: dict[str, float] | None = None
    materials_distribution: dict[str, float] | None = None

    # Calendrier (mode simple : 1 équipe, 8h/jour, 5 jours)
    daily_work_minutes: int = Field(default=480, ge=1)  # 8 h
    n_shifts: int = Field(default=1, ge=1, le=3)
    days_per_week: int = Field(default=5, ge=1, le=7)

    # Ressources partagées (aspiration, alim 400V) — proba d'injection à la génération
    shared_resource_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    shared_resource_min_machines: int = Field(default=2, ge=2)
    shared_resource_max_machines: int = Field(default=4, ge=2)
    shared_resource_max_concurrent: int = Field(default=2, ge=1)

    seed: int = 42

    @model_validator(mode="after")
    def _check_min_max(self) -> GenerationParams:
        for lo, hi, name in [
            (self.n_machines_min, self.n_machines_max, "n_machines"),
            (self.n_operators_min, self.n_operators_max, "n_operators"),
            (self.n_jobs_min, self.n_jobs_max, "n_jobs"),
            (self.operations_per_job_min, self.operations_per_job_max, "operations_per_job"),
        ]:
            if lo > hi:
                raise ValueError(f"{name}_min ({lo}) > {name}_max ({hi})")
        return self


# ---------- Schéma de sortie ----------


class SyntheticMachine(BaseModel):
    model_config = ConfigDict(frozen=True)

    machine_id: int = Field(..., ge=0)
    name: str
    machine_type: str


class SyntheticOperator(BaseModel):
    model_config = ConfigDict(frozen=True)

    operator_id: int = Field(..., ge=0)
    name: str
    qualifications: list[str]


class SyntheticOperation(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence_idx: int = Field(..., ge=0)
    operation_type: str
    compatible_machine_ids: list[int]
    estimated_duration_min: int = Field(..., ge=1)


class SyntheticOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    client: str
    client_tier: Literal[1, 2, 3]
    priority_weight: int = Field(..., ge=1)
    deadline: date
    material: str
    operations: list[SyntheticOperation]


class SharedResource(BaseModel):
    """Ressource physique partagée par plusieurs machines (aspiration, 400V, espace)."""

    model_config = ConfigDict(frozen=True)

    resource_name: str
    machine_ids: list[int]
    max_concurrent: int = Field(..., ge=1)


class WorkCalendar(BaseModel):
    """Calendrier de travail simple : durée d'équipe × nb équipes × jours/sem."""

    model_config = ConfigDict(frozen=True)

    daily_work_minutes: int = Field(..., ge=1)
    n_shifts: int = Field(..., ge=1, le=3)
    days_per_week: int = Field(..., ge=1, le=7)

    @property
    def total_minutes_per_day(self) -> int:
        return self.daily_work_minutes * self.n_shifts


class SyntheticWorkshop(BaseModel):
    model_config = ConfigDict(frozen=True)

    metadata: dict[str, str | int]
    machines: list[SyntheticMachine]
    operators: list[SyntheticOperator]
    orders: list[SyntheticOrder]
    shared_resources: list[SharedResource] = Field(default_factory=list)
    calendar: WorkCalendar | None = None


# ---------- Génération ----------


def generate_workshop(params: GenerationParams) -> SyntheticWorkshop:
    """Génère un atelier synthétique complet selon `params`."""
    rng = np.random.default_rng(params.seed)

    machine_dist = params.machine_types_distribution or MACHINE_TYPES_DEFAULT
    material_dist = params.materials_distribution or MATERIALS_DEFAULT

    n_machines = int(rng.integers(params.n_machines_min, params.n_machines_max + 1))
    n_operators = int(rng.integers(params.n_operators_min, params.n_operators_max + 1))
    n_jobs = int(rng.integers(params.n_jobs_min, params.n_jobs_max + 1))

    machines = _generate_machines(rng, n_machines, machine_dist)
    feasible_ops, op_to_machine_ids = _resolve_feasible_operations(machines)

    operators = _generate_operators(rng, n_operators, feasible_ops)
    orders = _generate_orders(
        rng,
        n_jobs=n_jobs,
        feasible_ops=feasible_ops,
        op_to_machine_ids=op_to_machine_ids,
        params=params,
        material_dist=material_dist,
    )

    shared_resources = _maybe_generate_shared_resources(rng, machines, params)
    calendar = WorkCalendar(
        daily_work_minutes=params.daily_work_minutes,
        n_shifts=params.n_shifts,
        days_per_week=params.days_per_week,
    )

    metadata: dict[str, str | int] = {
        "seed": params.seed,
        "n_machines": n_machines,
        "n_operators": n_operators,
        "n_jobs": n_jobs,
        "n_shared_resources": len(shared_resources),
        "planning_horizon_days": params.planning_horizon_days,
        "generator_version": "0.6c",
    }

    return SyntheticWorkshop(
        metadata=metadata,
        machines=machines,
        operators=operators,
        orders=orders,
        shared_resources=shared_resources,
        calendar=calendar,
    )


# ---------- Sous-fonctions ----------


def _sample_categorical(
    rng: Generator,
    distribution: dict[str, float],
    size: int,
) -> list[str]:
    """Échantillonne `size` valeurs d'une distribution catégorielle (poids relatifs)."""
    keys = list(distribution.keys())
    weights = np.array([distribution[k] for k in keys], dtype=np.float64)
    weights = weights / weights.sum()
    indices = rng.choice(len(keys), size=size, p=weights)
    return [keys[i] for i in indices]


def _generate_machines(
    rng: Generator,
    n: int,
    distribution: dict[str, float],
) -> list[SyntheticMachine]:
    types = _sample_categorical(rng, distribution, n)
    return [
        SyntheticMachine(machine_id=i, name=f"M{i:02d}", machine_type=t)
        for i, t in enumerate(types)
    ]


def _resolve_feasible_operations(
    machines: list[SyntheticMachine],
) -> tuple[tuple[str, ...], dict[str, list[int]]]:
    """Détermine les opérations réalisables dans cet atelier.

    Returns:
        Tuple (`feasible_ops`, `op_to_machine_ids`) :
        - `feasible_ops` : opérations qui ont au moins une machine compatible présente
        - `op_to_machine_ids` : pour chaque opération réalisable, la liste des
            machine_ids compatibles dans cet atelier
    """
    machine_types_present: dict[str, list[int]] = {}
    for m in machines:
        machine_types_present.setdefault(m.machine_type, []).append(m.machine_id)

    feasible: list[str] = []
    op_to_ids: dict[str, list[int]] = {}
    for op in OPERATIONS_CANONICAL:
        compatible_types = OPERATION_MACHINE_COMPAT.get(op, ())
        ids: list[int] = []
        for t in compatible_types:
            ids.extend(machine_types_present.get(t, []))
        if ids:
            feasible.append(op)
            op_to_ids[op] = sorted(set(ids))
    return tuple(feasible), op_to_ids


def _generate_operators(
    rng: Generator,
    n: int,
    feasible_ops: tuple[str, ...],
) -> list[SyntheticOperator]:
    """Génère `n` opérateurs avec des qualifications partielles couvrant les opérations réalisables."""
    operators: list[SyntheticOperator] = []
    for i in range(n):
        # Polyvalence variable : 30-90% des opérations réalisables maîtrisées
        coverage = float(rng.uniform(0.3, 0.9))
        n_qual = max(1, round(coverage * len(feasible_ops)))
        qualifications = list(rng.choice(feasible_ops, size=n_qual, replace=False))
        operators.append(
            SyntheticOperator(
                operator_id=i,
                name=f"OP{i:02d}",
                qualifications=sorted(qualifications),
            )
        )
    return operators


def _generate_orders(
    rng: Generator,
    *,
    n_jobs: int,
    feasible_ops: tuple[str, ...],
    op_to_machine_ids: dict[str, list[int]],
    params: GenerationParams,
    material_dist: dict[str, float],
) -> list[SyntheticOrder]:
    today = date(2026, 1, 1)
    orders: list[SyntheticOrder] = []

    materials = _sample_categorical(rng, material_dist, n_jobs)
    tiers = _sample_categorical(rng, CLIENT_TIERS, n_jobs)

    for i in range(n_jobs):
        material = materials[i]
        tier_label = tiers[i]
        tier_num: Literal[1, 2, 3] = _tier_to_int(tier_label)
        priority = CLIENT_TIER_WEIGHT[tier_label]

        client_pool = CLIENT_NAMES_BY_TIER[tier_label]
        client = str(rng.choice(client_pool))

        deadline_offset = int(rng.integers(1, params.planning_horizon_days + 1))
        deadline = today + timedelta(days=deadline_offset)

        n_ops = int(rng.integers(params.operations_per_job_min, params.operations_per_job_max + 1))
        chosen_ops = list(rng.choice(feasible_ops, size=n_ops, replace=True))

        difficulty = MATERIAL_DIFFICULTY_MULTIPLIER.get(material, 1.0)
        operations = [
            SyntheticOperation(
                sequence_idx=k,
                operation_type=op_type,
                compatible_machine_ids=op_to_machine_ids[op_type],
                estimated_duration_min=_sample_duration(rng, op_type, difficulty),
            )
            for k, op_type in enumerate(chosen_ops)
        ]

        orders.append(
            SyntheticOrder(
                order_id=f"OF-2026-{i + 1:05d}",
                client=client,
                client_tier=tier_num,
                priority_weight=priority,
                deadline=deadline,
                material=material,
                operations=operations,
            )
        )
    return orders


def _tier_to_int(tier_label: str) -> Literal[1, 2, 3]:
    if tier_label.startswith("Tier_1"):
        return 1
    if tier_label.startswith("Tier_2"):
        return 2
    return 3


def _sample_duration(rng: Generator, op_type: str, material_multiplier: float) -> int:
    """Échantillonne une durée d'opération en minutes (lognormale, jamais < 1)."""
    mean, std = OPERATION_BASE_TIMES_MIN[op_type]
    mean *= material_multiplier
    std *= material_multiplier
    if mean <= 0:
        return 1
    # Lognormal calibrée pour avoir mean/std proches en pratique pour les
    # ordres de grandeur usuels.
    sigma = float(np.sqrt(np.log(1.0 + (std / mean) ** 2)))
    mu = float(np.log(mean) - 0.5 * sigma**2)
    sample = float(rng.lognormal(mu, sigma))
    return max(1, round(sample))


# ---------- Génération des ressources partagées ----------


_SHARED_RESOURCE_NAMES: tuple[str, ...] = (
    "aspiration_zone_A",
    "aspiration_zone_B",
    "alimentation_400V_zone_A",
    "alimentation_400V_zone_B",
    "fluide_coupe_central",
)


def _maybe_generate_shared_resources(
    rng: Generator,
    machines: list[SyntheticMachine],
    params: GenerationParams,
) -> list[SharedResource]:
    """Injecte 0 ou 1 ressource partagée selon `shared_resource_probability`.

    Si tirage positif, sélectionne aléatoirement entre `min_machines` et
    `max_machines` parmi celles disponibles, et fixe `max_concurrent`.

    Returns:
        Liste de `SharedResource` (vide si pas d'injection ou pas assez de
        machines pour respecter les bornes).
    """
    if params.shared_resource_probability <= 0.0:
        return []
    if float(rng.random()) >= params.shared_resource_probability:
        return []
    if len(machines) < params.shared_resource_min_machines:
        return []

    upper = min(params.shared_resource_max_machines, len(machines))
    n_concerned = int(rng.integers(params.shared_resource_min_machines, upper + 1))
    chosen_ids = sorted(
        rng.choice([m.machine_id for m in machines], size=n_concerned, replace=False).tolist()
    )
    name = str(rng.choice(_SHARED_RESOURCE_NAMES))
    max_concurrent = min(params.shared_resource_max_concurrent, max(1, n_concerned - 1))
    return [
        SharedResource(
            resource_name=name,
            machine_ids=[int(x) for x in chosen_ids],
            max_concurrent=max_concurrent,
        )
    ]
