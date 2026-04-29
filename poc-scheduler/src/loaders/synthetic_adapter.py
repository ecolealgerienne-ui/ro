"""Adaptateur entre `SyntheticWorkshop` (haut niveau métier) et `WorkshopInstance` (JSSP).

Le `SyntheticWorkshop` produit par le générateur expose des opérations avec une
liste de machines compatibles (`compatible_machine_ids`). Le solveur JSSP de
base (étape 0.3) attend une opération assignée à UNE machine fixe. Cet
adaptateur fait le pont en assignant chaque opération à la machine compatible
la moins chargée parmi celles disponibles.

Cette stratégie d'assignation simple (load-balancing greedy) est adaptée au
POC. Une version plus avancée — laisser le solveur choisir parmi les machines
compatibles via des intervals optionnels — sera intégrée à l'étape 1.1 lors
du refactor en classes `Pattern`.
"""

from __future__ import annotations

from src.core.models import Job, Machine, Operation, WorkshopInstance
from src.generators.workshop_generator import SyntheticWorkshop


def synthetic_to_jssp_instance(
    workshop: SyntheticWorkshop,
    *,
    name: str | None = None,
) -> WorkshopInstance:
    """Convertit un `SyntheticWorkshop` en `WorkshopInstance` JSSP résoluble.

    Stratégie d'assignation : pour chaque opération, choisit la machine
    compatible avec la charge cumulée la plus faible (greedy load-balancing).

    Args:
        workshop: Atelier synthétique généré.
        name: Nom optionnel pour l'instance ; sinon dérivé des métadonnées.

    Returns:
        `WorkshopInstance` avec une opération par couple (job, sequence_idx),
        chaque opération assignée à une machine fixe.

    Raises:
        ValueError: Si une opération a une liste de machines compatibles vide
            (anomalie de génération).
    """
    instance_name = name or _derive_name(workshop)
    machines = [Machine(machine_id=m.machine_id, name=m.name) for m in workshop.machines]

    machine_loads: dict[int, int] = {m.machine_id: 0 for m in workshop.machines}
    jobs: list[Job] = []

    for j_idx, order in enumerate(workshop.orders):
        operations: list[Operation] = []
        for op in order.operations:
            if not op.compatible_machine_ids:
                raise ValueError(
                    f"Opération {op.operation_type} de l'OF {order.order_id} "
                    "n'a aucune machine compatible — anomalie de génération"
                )
            chosen = min(op.compatible_machine_ids, key=lambda m: machine_loads[m])
            machine_loads[chosen] += op.estimated_duration_min
            operations.append(
                Operation(
                    job_id=j_idx,
                    sequence_idx=op.sequence_idx,
                    machine_id=chosen,
                    duration=op.estimated_duration_min,
                )
            )
        jobs.append(Job(job_id=j_idx, operations=operations))

    metadata: dict[str, str] = {
        "source": "synthetic_workshop",
        "seed": str(workshop.metadata.get("seed", "")),
        "n_jobs": str(len(workshop.orders)),
        "n_machines": str(len(workshop.machines)),
    }

    return WorkshopInstance(
        name=instance_name,
        jobs=jobs,
        machines=machines,
        best_known_makespan=None,
        metadata=metadata,
    )


def _derive_name(workshop: SyntheticWorkshop) -> str:
    seed = workshop.metadata.get("seed", "?")
    n_jobs = len(workshop.orders)
    n_machines = len(workshop.machines)
    return f"synth_s{seed}_j{n_jobs}_m{n_machines}"
