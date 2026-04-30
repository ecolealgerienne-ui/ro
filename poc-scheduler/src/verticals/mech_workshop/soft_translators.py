"""Soft constraint translators pour la verticale `mech_workshop`.

Convertit des `SoftConstraint` produites par l'agent 3.6 (NL → JSON typé) en
`SoftPenaltyVar` directement utilisables dans l'objectif CP-SAT.

Le module est specialise meca : connait les conventions d'unites de temps
(minutes), les categories de soft constraints (definies dans agent 3.6), les
champs metier de Job (`deadline`, `client`).

V1 — 3 translators couvrant 3 idiomes CP-SAT distincts :

1. **`tardiness_per_job`** (idiome PROPORTIONNEL) :
   penalite = somme des max(0, end_last_op - deadline) pour chaque job avec
   `deadline` defini. Permet d'implementer `client_priority` du module 3.6
   (en filtrant sur le client correspondant).

2. **`avoid_machine_during_period`** (idiome BOOLEEN reified) :
   penalite = nombre d'ops de la machine ciblee qui chevauchent la periode
   ciblee. Une op chevauche si `start < period_end` ET `end > period_start`.

3. **`encourage_early_completion`** (idiome PROPORTIONNEL aggregat) :
   penalite = somme des fins de tous les jobs (end_last_op). Different du
   makespan qui minimise le **max** : minimise la somme aboutit a une
   distribution differente (privilegie de finir vite plusieurs jobs plutot
   qu'optimiser le dernier). Aucun parametre.

Idiomes restants a traiter (Phase 1.6.next) :
- COUNT (transitions de famille / changements de matiere par machine)
- CHOICE / DISJUNCTION (preferer machine A vs B quand decision possible)
- WINDOW (preferer un shift donne — horaires journaliers cycliques)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.core.models import Job, WorkshopInstance
from src.core.soft_constraints import SoftPenaltyVar
from src.verticals.mech_workshop.agents import SoftConstraint

# Echelle integer pour convertir weight_hint flottant [0,1] en weight entier.
# weight_int = max(1, round(weight_hint * WEIGHT_SCALE)).
WEIGHT_SCALE: int = 100


def _to_int_weight(weight_hint: float) -> int:
    """Convertit un weight_hint [0,1] en poids entier >= 1."""
    return max(1, round(weight_hint * WEIGHT_SCALE))


def _last_end_var_per_job(
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
) -> dict[int, Any]:
    """Retourne {job_id: end_var de la derniere op du job}."""
    out: dict[int, Any] = {}
    for job in instance.jobs:
        last_idx = max(op.sequence_idx for op in job.operations)
        out[job.job_id] = op_vars[(job.job_id, last_idx)]["end"]
    return out


# ---------- Translator 1 : tardiness_per_job ----------


def translate_tardiness_per_job(
    model: Any,
    *,
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    constraint: SoftConstraint,
) -> SoftPenaltyVar | None:
    """Penalite proportionnelle a la tardivete totale.

    Filtre par client si `constraint.parameters["client_reference"]` est defini ;
    sinon applique a tous les jobs avec `deadline`.

    Returns None si aucun job avec `deadline` correspond (rien a penaliser).
    """
    target_client: str | None = None
    if constraint.category == "client_priority":
        ref = constraint.parameters.get("client_reference")
        if isinstance(ref, str) and ref.strip():
            target_client = ref.strip()

    eligible_jobs: list[Job] = [
        j
        for j in instance.jobs
        if j.deadline is not None and (target_client is None or j.client == target_client)
    ]
    if not eligible_jobs:
        return None

    last_ends = _last_end_var_per_job(instance, op_vars)
    tardy_vars: list[Any] = []
    for job in eligible_jobs:
        assert job.deadline is not None  # garde-fou type-checker
        tardy = model.new_int_var(0, horizon, f"tardy_j{job.job_id}")
        # tardy = max(0, end_last - deadline)
        model.add_max_equality(tardy, [0, last_ends[job.job_id] - job.deadline])
        tardy_vars.append(tardy)

    label = (
        f"tardiness_client_{target_client}" if target_client is not None else "tardiness_all_jobs"
    )
    total = model.new_int_var(0, horizon * len(tardy_vars), f"{label}_total")
    model.add(total == sum(tardy_vars))

    return SoftPenaltyVar(label=label, weight=_to_int_weight(constraint.weight_hint), var=total)


# ---------- Translator 2 : avoid_machine_during_period ----------


def translate_avoid_machine_during_period(
    model: Any,
    *,
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    constraint: SoftConstraint,
    machine_name_to_id: Mapping[str, int],
    period_start: int,
    period_end: int,
) -> SoftPenaltyVar | None:
    """Penalite = nombre d'ops de la machine ciblee chevauchant la periode.

    Args:
        machine_name_to_id: la verticale gere le mapping nom (ex: "M3" depuis
            le NL) -> machine_id. Si la machine n'est pas reconnue, retourne None.
        period_start, period_end: bornes en unites de temps coherentes avec
            l'horizon. La verticale convertit `period_type` (night/weekend/...)
            en bornes concretes selon le calendrier.
    """
    if period_start < 0 or period_end <= period_start:
        raise ValueError(
            f"avoid_machine_during_period : periode invalide [{period_start}, {period_end})"
        )

    machine_ref = constraint.parameters.get("machine_reference")
    if not isinstance(machine_ref, str):
        return None
    machine_id = machine_name_to_id.get(machine_ref)
    if machine_id is None:
        return None

    overlap_flags: list[Any] = []
    for job in instance.jobs:
        for op in job.operations:
            if op.machine_id != machine_id:
                continue
            v = op_vars[(job.job_id, op.sequence_idx)]
            start, end = v["start"], v["end"]

            # op_overlaps = NOT (end <= period_start OR start >= period_end)
            ends_before = model.new_bool_var(f"ovl_b_j{job.job_id}_o{op.sequence_idx}")
            model.add(end <= period_start).only_enforce_if(ends_before)
            model.add(end > period_start).only_enforce_if(ends_before.Not())

            starts_after = model.new_bool_var(f"ovl_a_j{job.job_id}_o{op.sequence_idx}")
            model.add(start >= period_end).only_enforce_if(starts_after)
            model.add(start < period_end).only_enforce_if(starts_after.Not())

            overlaps = model.new_bool_var(f"ovl_in_j{job.job_id}_o{op.sequence_idx}")
            # overlaps = NOT(ends_before OR starts_after)
            #         = ends_before.Not() AND starts_after.Not()
            model.add_bool_or([ends_before, starts_after, overlaps])
            model.add(ends_before == 0).only_enforce_if(overlaps)
            model.add(starts_after == 0).only_enforce_if(overlaps)

            overlap_flags.append(overlaps)

    if not overlap_flags:
        return None

    label = f"avoid_m{machine_id}_period_{period_start}_{period_end}"
    total = model.new_int_var(0, len(overlap_flags), f"{label}_total")
    model.add(total == sum(overlap_flags))

    return SoftPenaltyVar(label=label, weight=_to_int_weight(constraint.weight_hint), var=total)


# ---------- Translator 3 : encourage_early_completion ----------


def translate_encourage_early_completion(
    model: Any,
    *,
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    constraint: SoftConstraint,
) -> SoftPenaltyVar | None:
    """Penalite = somme des fins de tous les jobs.

    Different du makespan (qui minimise le max). Aboutit a un planning plus
    "etale" : on prefere finir 5 jobs en moyenne tot, meme si le dernier finit
    un peu plus tard, plutot que de minimiser le dernier au detriment des autres.

    Aucun parametre dans `constraint.parameters`.
    """
    last_ends = _last_end_var_per_job(instance, op_vars)
    if not last_ends:
        return None

    label = "encourage_early_completion_sum_ends"
    total = model.new_int_var(0, horizon * len(last_ends), f"{label}_total")
    model.add(total == sum(last_ends.values()))

    return SoftPenaltyVar(label=label, weight=_to_int_weight(constraint.weight_hint), var=total)


# ---------- Dispatcher : SoftConstraint -> SoftPenaltyVar ----------


def translate_soft_constraints(
    model: Any,
    *,
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    soft_constraints: Sequence[SoftConstraint],
    machine_name_to_id: Mapping[str, int] | None = None,
    period_resolver: Mapping[str, tuple[int, int]] | None = None,
) -> list[SoftPenaltyVar]:
    """Dispatcher generique : applique le bon translator par categorie.

    Args:
        machine_name_to_id: si certains soft pointent sur des machines par leur
            nom (ex: "M3"), fournir la table de correspondance. Sinon None et
            les categories qui en ont besoin retournent None.
        period_resolver: pour `avoid_machine_during_period`, mapping
            `period_type` (night/weekend/lunch_break/custom) -> (start, end) en
            unites d'horizon. None = on ignore les categories qui en ont besoin.

    Returns:
        Liste des `SoftPenaltyVar` produites (les categories non gerables
        retournent None et sont filtrees ici).
    """
    out: list[SoftPenaltyVar] = []
    for sc in soft_constraints:
        sp: SoftPenaltyVar | None = None
        if sc.category == "client_priority":
            sp = translate_tardiness_per_job(
                model,
                instance=instance,
                op_vars=op_vars,
                horizon=horizon,
                constraint=sc,
            )
        elif sc.category == "avoid_machine_during_period":
            if machine_name_to_id is None or period_resolver is None:
                continue
            period_type = sc.parameters.get("period_type")
            if not isinstance(period_type, str) or period_type not in period_resolver:
                continue
            ps, pe = period_resolver[period_type]
            sp = translate_avoid_machine_during_period(
                model,
                instance=instance,
                op_vars=op_vars,
                horizon=horizon,
                constraint=sc,
                machine_name_to_id=machine_name_to_id,
                period_start=ps,
                period_end=pe,
            )
        # Categorie pseudo "early completion" : pas dans le catalog 3.6, peut
        # etre invoquee directement par le code applicatif via category="other"
        # avec parameters={"kind": "encourage_early_completion"}.
        elif sc.category == "other" and sc.parameters.get("kind") == "encourage_early_completion":
            sp = translate_encourage_early_completion(
                model,
                instance=instance,
                op_vars=op_vars,
                horizon=horizon,
                constraint=sc,
            )

        if sp is not None:
            out.append(sp)
    return out
