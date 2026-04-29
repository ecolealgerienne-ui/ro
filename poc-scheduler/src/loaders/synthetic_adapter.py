"""Adaptateur entre `SyntheticWorkshop` (haut niveau métier) et `WorkshopInstance` (JSSP).

Le `SyntheticWorkshop` produit par le générateur expose des opérations avec une
liste de machines compatibles (`compatible_machine_ids`) et des qualifications
opérateurs au niveau atelier. Cet adaptateur :

1. Assigne chaque opération à une machine compatible via greedy load-balancing
2. Renseigne `family_id` et `qualified_operator_ids` per-opération
3. Renseigne `n_operators`, `transition_matrix`, `shared_resources` au niveau
   instance
4. Renseigne `machine_unavailability` (vide pour l'instant — la traduction
   du calendar viendra plus tard)

Mode opt-in : par défaut tous les enrichissements industriels sont actifs.
Désactivables via flags pour tests / comparaison de perf.
"""

from __future__ import annotations

from src.core.models import (
    Job,
    Machine,
    Operation,
    SharedResourceSpec,
    WorkshopInstance,
)
from src.generators.distributions import (
    DEFAULT_TRANSITION_MATRIX,
    OPERATION_FAMILY,
)
from src.generators.workshop_generator import SyntheticWorkshop


def synthetic_to_jssp_instance(
    workshop: SyntheticWorkshop,
    *,
    name: str | None = None,
    enable_setup: bool = True,
    enable_operators: bool = True,
    enable_shared_resources: bool = True,
) -> WorkshopInstance:
    """Convertit un `SyntheticWorkshop` en `WorkshopInstance` JSSP résoluble.

    Stratégie d'assignation : pour chaque opération, choisit la machine
    compatible avec la charge cumulée la plus faible (greedy load-balancing).

    Args:
        workshop: Atelier synthétique généré.
        name: Nom optionnel pour l'instance ; sinon dérivé des métadonnées.
        enable_setup: Active la matrice de transition + family_id (étape 1.1b).
        enable_operators: Active n_operators + qualified_operator_ids per op.
        enable_shared_resources: Reporte les ressources partagées.

    Returns:
        `WorkshopInstance` enrichie selon les flags. Les flags désactivés
        laissent les champs à leur valeur neutre par défaut (équivalent à
        l'adaptateur de l'étape 0.7).

    Raises:
        ValueError: Si une opération a une liste de machines compatibles vide.
    """
    instance_name = name or _derive_name(workshop)
    machines = [Machine(machine_id=m.machine_id, name=m.name) for m in workshop.machines]

    machine_loads: dict[int, int] = {m.machine_id: 0 for m in workshop.machines}
    operator_qualifications_by_op_type = (
        _build_qualifications_index(workshop) if enable_operators else {}
    )

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

            family_id = OPERATION_FAMILY.get(op.operation_type, 0) if enable_setup else 0
            qualified_ops = (
                operator_qualifications_by_op_type.get(op.operation_type, [])
                if enable_operators
                else []
            )

            operations.append(
                Operation(
                    job_id=j_idx,
                    sequence_idx=op.sequence_idx,
                    machine_id=chosen,
                    duration=op.estimated_duration_min,
                    family_id=family_id,
                    qualified_operator_ids=qualified_ops,
                )
            )
        jobs.append(Job(job_id=j_idx, operations=operations))

    n_operators = len(workshop.operators) if enable_operators else 0
    transition_matrix: list[list[int]] = (
        [list(row) for row in DEFAULT_TRANSITION_MATRIX] if enable_setup else []
    )
    shared_resources = (
        [
            SharedResourceSpec(
                resource_name=res.resource_name,
                machine_ids=list(res.machine_ids),
                max_concurrent=res.max_concurrent,
            )
            for res in workshop.shared_resources
        ]
        if enable_shared_resources
        else []
    )

    metadata: dict[str, str] = {
        "source": "synthetic_workshop",
        "seed": str(workshop.metadata.get("seed", "")),
        "n_jobs": str(len(workshop.orders)),
        "n_machines": str(len(workshop.machines)),
        "enable_setup": str(enable_setup),
        "enable_operators": str(enable_operators),
        "enable_shared_resources": str(enable_shared_resources),
    }

    return WorkshopInstance(
        name=instance_name,
        jobs=jobs,
        machines=machines,
        best_known_makespan=None,
        metadata=metadata,
        n_operators=n_operators,
        transition_matrix=transition_matrix,
        shared_resources=shared_resources,
        machine_unavailability=[],
    )


def _build_qualifications_index(workshop: SyntheticWorkshop) -> dict[str, list[int]]:
    """Pour chaque type d'opération, liste les operator_id qualifiés.

    Si aucun opérateur n'est qualifié pour un type donné (cas rare avec
    polyvalence 30-90 %), fallback sur tous les opérateurs (= pas de contrainte).
    """
    index: dict[str, list[int]] = {}
    all_operator_ids = sorted(op.operator_id for op in workshop.operators)
    op_types_seen: set[str] = set()

    for op in workshop.operators:
        for qual in op.qualifications:
            index.setdefault(qual, []).append(op.operator_id)
            op_types_seen.add(qual)

    for op_type in op_types_seen:
        index[op_type] = sorted(set(index[op_type]))

    # Fallback : pour chaque type d'opération sans opérateur qualifié, autoriser tous
    for order in workshop.orders:
        for op in order.operations:
            if op.operation_type not in index:
                index[op.operation_type] = list(all_operator_ids)

    return index


def _derive_name(workshop: SyntheticWorkshop) -> str:
    seed = workshop.metadata.get("seed", "?")
    n_jobs = len(workshop.orders)
    n_machines = len(workshop.machines)
    return f"synth_s{seed}_j{n_jobs}_m{n_machines}"
