"""Bridge entre le snapshot JSON cote backend (Phase 4 J3) et l'engine Pydantic.

Le backend NestJS serialise un Workshop + ses relations dans un JSON Prisma
(camelCase, UUID des relations) stocke dans `Version.snapshot`. Cet engine
Python travaille en `WorkshopInstance` Pydantic (snake_case, indices entiers
pour les machines / jobs / operators).

Ce module fait la traduction. Vertical-agnostic : ne contient aucune logique
metier specifique meca, juste le mapping structurel des champs.

Convention de mapping :
- machineId UUID (Prisma) -> machine_id_int via la liste des machines du
  workshop. C'est ce qu'attend le solveur (cf. `Operation.machine_id` dans
  src.core.models).
- Order.criticality, sinon Client.tier, sinon None -> Job.criticality. La
  surcharge au niveau OF prime sur le tier client (decision V1 cote backend).
- shiftStart/shiftEnd/workdays/transition_matrix : pour V1 on mappe juste
  transition_matrix sur WorkshopInstance ; les calendriers seront integres
  via UnavailableIntervalsPattern dans une iteration future.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.core.models import (
    Job,
    Machine,
    MachineUnavailabilitySpec,
    Operation,
    SharedResourceSpec,
    WorkshopInstance,
)


def instance_from_snapshot(snapshot: Mapping[str, Any]) -> WorkshopInstance:
    """Construit un `WorkshopInstance` a partir d'un snapshot Prisma serialise.

    Args:
        snapshot: dict produit par `VersionsService.buildSnapshot` cote backend.

    Returns:
        `WorkshopInstance` Pydantic, pret a etre passe au pipeline.

    Raises:
        ValueError: si le snapshot est mal forme (relations absentes, machines
        UUID non resolvables, etc.).
    """
    name = str(snapshot.get("name") or snapshot.get("id") or "workshop")

    raw_machines = snapshot.get("machines") or []
    machines = [
        Machine(machine_id=int(m["machineIdInt"]), name=str(m.get("name") or ""))
        for m in raw_machines
    ]
    machine_uuid_to_int: dict[str, int] = {
        str(m["id"]): int(m["machineIdInt"]) for m in raw_machines
    }

    raw_orders = snapshot.get("orders") or []
    jobs: list[Job] = []
    for order in raw_orders:
        job_data = order.get("job")
        if job_data is None:
            # OF importe sans gamme : ignore cote solveur (correspond a un OF
            # juste enregistre, pas encore detaille).
            continue

        client = order.get("client") or {}
        order_criticality = job_data.get("criticality")
        client_tier = client.get("tier")
        criticality = (
            int(order_criticality)
            if order_criticality is not None
            else (int(client_tier) if client_tier is not None else None)
        )

        operations: list[Operation] = []
        for op in job_data.get("operations") or []:
            machine_uuid = str(op["machineId"])
            if machine_uuid not in machine_uuid_to_int:
                raise ValueError(
                    f"Operation reference machine_id={machine_uuid} absente du workshop"
                )
            operations.append(
                Operation(
                    job_id=int(job_data["jobIdInt"]),
                    sequence_idx=int(op["sequenceIdx"]),
                    machine_id=machine_uuid_to_int[machine_uuid],
                    duration=int(op["durationMin"]),
                    family_id=int(op.get("familyId") or 0),
                    qualified_operator_ids=list(op.get("qualifiedOperatorIds") or []),
                )
            )
        if not operations:
            continue

        deadline_raw = order.get("deadline")
        deadline: int | None = None
        if deadline_raw is not None:
            # V1 : on n'integre pas encore la deadline en minutes-from-now ; le
            # solveur s'en sert seulement pour les soft constraints. Champ
            # propage tel-quel pour permettre les futurs translators.
            deadline = None  # placeholder explicite

        jobs.append(
            Job(
                job_id=int(job_data["jobIdInt"]),
                operations=operations,
                deadline=deadline,
                client=str(client.get("name") or "") or None,
                criticality=criticality,
            )
        )

    raw_shared = snapshot.get("sharedRes") or []
    shared_resources = [
        SharedResourceSpec(
            resource_name=str(sr["resourceName"]),
            machine_ids=[int(i) for i in (sr.get("machineIdsInt") or [])],
            max_concurrent=int(sr["maxConcurrent"]),
        )
        for sr in raw_shared
        if sr.get("machineIdsInt")
    ]

    raw_unavail = snapshot.get("unavailability") or []
    unavailability: list[MachineUnavailabilitySpec] = []
    for u in raw_unavail:
        nested = u.get("machine") or {}
        machine_id_int = nested.get("machineIdInt")
        if machine_id_int is None:
            machine_uuid = str(u.get("machineId") or "")
            if machine_uuid not in machine_uuid_to_int:
                raise ValueError(
                    f"MachineUnavailability sur machine_id={machine_uuid} absente du workshop"
                )
            machine_id_int = machine_uuid_to_int[machine_uuid]
        periods_raw = u.get("periods") or []
        periods = [(int(p[0]), int(p[1])) for p in periods_raw]
        if not periods:
            continue
        unavailability.append(
            MachineUnavailabilitySpec(machine_id=int(machine_id_int), periods=periods)
        )

    transition_matrix_raw = snapshot.get("transitionMatrix")
    transition_matrix: list[list[int]] = []
    if isinstance(transition_matrix_raw, list):
        transition_matrix = [[int(v) for v in row] for row in transition_matrix_raw]

    return WorkshopInstance(
        name=name,
        jobs=jobs,
        machines=machines,
        n_operators=int(snapshot.get("nOperators") or 0),
        transition_matrix=transition_matrix,
        shared_resources=shared_resources,
        machine_unavailability=unavailability,
    )


__all__ = ["instance_from_snapshot"]
