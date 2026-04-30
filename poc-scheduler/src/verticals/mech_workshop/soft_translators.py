"""Soft constraint translators pour la verticale `mech_workshop`.

Convertit des `SoftConstraint` produites par l'agent 3.6 (NL → JSON typé) en
`SoftPenaltyVar` directement utilisables dans l'objectif CP-SAT.

Le module est specialise meca : connait les conventions d'unites de temps
(minutes), les categories de soft constraints (definies dans agent 3.6), les
champs metier de Job (`deadline`, `client`).

V1 — 6 translators couvrant 4 idiomes CP-SAT distincts :

PROPORTIONNEL (penalite = entier en fonction lineaire des decisions) :
1. **`tardiness_per_job`** : sum(max(0, end - deadline)) pour jobs avec
   `deadline`. Filtre par client si specifie. Implemente `client_priority`.
3. **`encourage_early_completion`** : sum(end_last_op) sur tous les jobs.
   Different du makespan qui minimise le **max** : minimise la somme prefere
   finir tot plusieurs jobs plutot qu'optimiser le dernier.

BOOLEEN reified (penalite = compte d'evenements binaires) :
2. **`avoid_machine_during_period`** : count des ops de la machine ciblee
   qui chevauchent la periode (`start < period_end` ET `end > period_start`).

COUNT BUCKETÉ (compte par fenetre temporelle) :
4. **`limit_ops_per_day_on_machine`** : pour chaque jour, count des ops
   demarrant dans le jour ; penalite = excess au-dela de `max_per_day`.
   Implemente `limit_setups_per_day_on_machine`.

SPREAD min/max (etalement temporel agrege) :
5. **`prefer_grouping_by_family`** : sum sur (machine, family_id) du spread
   `(max_end - min_start)`. Minimiser = grouper les ops de meme famille
   sur chaque machine. Implemente `prefer_grouping_by_material` (family_id
   sert de proxy matiere/type).
6. **`prefer_grouping_by_client`** : meme idiome mais group par
   (machine, client). Necessite Job.client. Filtrable par
   `client_reference`.

Idiomes restants a traiter (Phase 1.6.next ou V2) :
- CHOICE / DISJUNCTION (preferer machine A vs B) : necessite que
  `Operation.machine_id` devienne une variable de decision (refactor du
  modele). Translator `prefer_machine_over_other` non livre.
- WINDOW cyclique (shift matin/apres-midi/nuit chaque jour) : necessite
  un encodage modulo. Translator `prefer_operation_in_shift` non livre.
- Operator-related (`operator_avoidance`, `operator_preference`) :
  necessite l'exposition des variables `present[i][k]` du
  `QualifiedOperatorPattern` au-dela du solver. Non livre.
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

    return SoftPenaltyVar(
        label=label,
        weight=_to_int_weight(constraint.weight_hint),
        var=total,
        expected_max=horizon * len(tardy_vars),  # 1.3 — tardive max = horizon par job
    )


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

    return SoftPenaltyVar(
        label=label,
        weight=_to_int_weight(constraint.weight_hint),
        var=total,
        expected_max=len(overlap_flags),  # 1.3 — au pire toutes les ops chevauchent
    )


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

    return SoftPenaltyVar(
        label=label,
        weight=_to_int_weight(constraint.weight_hint),
        var=total,
        expected_max=horizon * len(last_ends),  # 1.3 — somme max si chacun finit a horizon
    )


# ---------- Translator 4 : limit_ops_per_day_on_machine ----------


def translate_limit_ops_per_day_on_machine(
    model: Any,
    *,
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    constraint: SoftConstraint,
    machine_name_to_id: Mapping[str, int],
    day_offsets: Sequence[tuple[int, int]],
) -> SoftPenaltyVar | None:
    """Penalite = somme sur les jours du depassement de `max_setups_per_day`.

    Idiome COUNT BUCKETÉ : pour chaque jour [day_start, day_end], on compte les
    ops de la machine ciblee qui demarrent dans ce jour. Si > max_per_day, le
    surplus est penalise.

    Args:
        machine_name_to_id: mapping nom machine (depuis NL) -> machine_id.
        day_offsets: liste de (day_start, day_end) en unites d'horizon. La
            verticale derive cette liste du calendrier (typiquement 480 min/jour
            sur 5 jours/semaine).
    """
    machine_ref = constraint.parameters.get("machine_reference")
    if not isinstance(machine_ref, str):
        return None
    machine_id = machine_name_to_id.get(machine_ref)
    if machine_id is None:
        return None
    raw_max = constraint.parameters.get("max_setups_per_day")
    if not isinstance(raw_max, int) or raw_max < 0:
        return None
    max_per_day = raw_max

    ops_on_machine: list[tuple[int, int]] = []
    for job in instance.jobs:
        for op in job.operations:
            if op.machine_id == machine_id:
                ops_on_machine.append((job.job_id, op.sequence_idx))
    if not ops_on_machine:
        return None

    excess_terms: list[Any] = []
    n_ops = len(ops_on_machine)
    for day_idx, (day_start, day_end) in enumerate(day_offsets):
        if day_start < 0 or day_end <= day_start:
            raise ValueError(
                f"day_offsets[{day_idx}] : intervalle invalide [{day_start}, {day_end})"
            )
        in_day_flags: list[Any] = []
        for job_id, seq_idx in ops_on_machine:
            start = op_vars[(job_id, seq_idx)]["start"]
            ge_low = model.new_bool_var(f"ge_low_d{day_idx}_j{job_id}_o{seq_idx}")
            model.add(start >= day_start).only_enforce_if(ge_low)
            model.add(start < day_start).only_enforce_if(ge_low.Not())
            lt_high = model.new_bool_var(f"lt_high_d{day_idx}_j{job_id}_o{seq_idx}")
            model.add(start < day_end).only_enforce_if(lt_high)
            model.add(start >= day_end).only_enforce_if(lt_high.Not())
            in_day = model.new_bool_var(f"in_day_d{day_idx}_j{job_id}_o{seq_idx}")
            # in_day = ge_low AND lt_high
            model.add_bool_and([ge_low, lt_high]).only_enforce_if(in_day)
            model.add_bool_or([ge_low.Not(), lt_high.Not()]).only_enforce_if(in_day.Not())
            in_day_flags.append(in_day)
        count_var = model.new_int_var(0, n_ops, f"cnt_d{day_idx}_m{machine_id}")
        model.add(count_var == sum(in_day_flags))
        excess = model.new_int_var(0, n_ops, f"excess_d{day_idx}_m{machine_id}")
        model.add_max_equality(excess, [0, count_var - max_per_day])
        excess_terms.append(excess)

    label = f"limit_ops_per_day_m{machine_id}_max{max_per_day}"
    total = model.new_int_var(0, n_ops * len(day_offsets), f"{label}_total")
    model.add(total == sum(excess_terms))
    return SoftPenaltyVar(
        label=label,
        weight=_to_int_weight(constraint.weight_hint),
        var=total,
        # 1.3 — au pire toutes les ops dans tous les jours = n_ops × n_jours d'excess.
        # Borne lache mais coherente : meme si peu probable, evite la division par 0.
        expected_max=max(1, n_ops * len(day_offsets)),
    )


# ---------- Translator 5 : prefer_grouping_by_family_on_machine ----------


def translate_prefer_grouping_by_family(
    model: Any,
    *,
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    constraint: SoftConstraint,
) -> SoftPenaltyVar | None:
    """Penalite = somme sur (machine, family) du spread (max_end - min_start).

    Idiome SPREAD : pour chaque groupe (machine_id, family_id) avec >= 2 ops,
    on calcule l'etalement temporel. Minimiser ce total revient a regrouper
    les ops de meme famille sur chaque machine. Reflete `prefer_grouping_by_material`
    du module 3.6 (family_id sert de proxy matiere/type).
    """
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for job in instance.jobs:
        for op in job.operations:
            groups.setdefault((op.machine_id, op.family_id), []).append(
                (job.job_id, op.sequence_idx)
            )

    spreads: list[Any] = []
    for (machine_id, family_id), op_keys in groups.items():
        if len(op_keys) < 2:
            continue
        starts = [op_vars[k]["start"] for k in op_keys]
        ends = [op_vars[k]["end"] for k in op_keys]
        max_end = model.new_int_var(0, horizon, f"max_end_m{machine_id}_f{family_id}")
        min_start = model.new_int_var(0, horizon, f"min_start_m{machine_id}_f{family_id}")
        model.add_max_equality(max_end, ends)
        model.add_min_equality(min_start, starts)
        spread = model.new_int_var(0, horizon, f"spread_m{machine_id}_f{family_id}")
        model.add(spread == max_end - min_start)
        spreads.append(spread)

    if not spreads:
        return None

    label = "prefer_grouping_by_family_total_spread"
    total = model.new_int_var(0, horizon * len(spreads), f"{label}_total")
    model.add(total == sum(spreads))
    return SoftPenaltyVar(
        label=label,
        weight=_to_int_weight(constraint.weight_hint),
        var=total,
        # 1.3 — chaque spread <= horizon, somme bornee par horizon × n_groupes.
        expected_max=horizon * len(spreads),
    )


# ---------- Translator 6 : prefer_grouping_by_client_on_machine ----------


def translate_prefer_grouping_by_client(
    model: Any,
    *,
    instance: WorkshopInstance,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    constraint: SoftConstraint,
) -> SoftPenaltyVar | None:
    """Penalite = somme sur (machine, client) du spread.

    Idiome SPREAD : meme idee que `prefer_grouping_by_family` mais regroupement
    par client donneur d'ordre. Necessite que les jobs aient `client` defini.
    Si `client_reference` est specifie dans la contrainte, on filtre sur ce client.
    """
    target_client_param = constraint.parameters.get("client_reference")
    target_client = (
        target_client_param.strip()
        if isinstance(target_client_param, str) and target_client_param.strip()
        else None
    )

    # Resoudre job_id -> client (eligible si non None et match cible si specifiee)
    job_client: dict[int, str] = {}
    for job in instance.jobs:
        if job.client is None:
            continue
        if target_client is not None and job.client != target_client:
            continue
        job_client[job.job_id] = job.client

    if not job_client:
        return None

    groups: dict[tuple[int, str], list[tuple[int, int]]] = {}
    for job in instance.jobs:
        client = job_client.get(job.job_id)
        if client is None:
            continue
        for op in job.operations:
            groups.setdefault((op.machine_id, client), []).append((job.job_id, op.sequence_idx))

    spreads: list[Any] = []
    for (machine_id, client), op_keys in groups.items():
        if len(op_keys) < 2:
            continue
        starts = [op_vars[k]["start"] for k in op_keys]
        ends = [op_vars[k]["end"] for k in op_keys]
        # CP-SAT n'aime pas les caracteres bizarres dans les noms ; on sanitize.
        safe_client = "".join(c if c.isalnum() else "_" for c in client)
        max_end = model.new_int_var(0, horizon, f"max_end_m{machine_id}_c{safe_client}")
        min_start = model.new_int_var(0, horizon, f"min_start_m{machine_id}_c{safe_client}")
        model.add_max_equality(max_end, ends)
        model.add_min_equality(min_start, starts)
        spread = model.new_int_var(0, horizon, f"spread_m{machine_id}_c{safe_client}")
        model.add(spread == max_end - min_start)
        spreads.append(spread)

    if not spreads:
        return None

    label = (
        f"prefer_grouping_by_client_{target_client}_total_spread"
        if target_client is not None
        else "prefer_grouping_by_client_total_spread"
    )
    total = model.new_int_var(0, horizon * len(spreads), f"{label}_total")
    model.add(total == sum(spreads))
    return SoftPenaltyVar(
        label=label,
        weight=_to_int_weight(constraint.weight_hint),
        var=total,
        # 1.3 — meme borne que la version family : horizon × n_groupes.
        expected_max=horizon * len(spreads),
    )


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
    day_offsets: Sequence[tuple[int, int]] | None = None,
) -> list[SoftPenaltyVar]:
    """Dispatcher generique : applique le bon translator par categorie.

    Args:
        machine_name_to_id: si certains soft pointent sur des machines par leur
            nom (ex: "M3"), fournir la table de correspondance. Sinon None et
            les categories qui en ont besoin retournent None.
        period_resolver: pour `avoid_machine_during_period`, mapping
            `period_type` (night/weekend/lunch_break/custom) -> (start, end) en
            unites d'horizon. None = on ignore les categories qui en ont besoin.
        day_offsets: pour `limit_setups_per_day_on_machine`, liste de
            (day_start, day_end) en unites d'horizon. None = on ignore.

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
        elif sc.category == "limit_setups_per_day_on_machine":
            if machine_name_to_id is None or day_offsets is None:
                continue
            sp = translate_limit_ops_per_day_on_machine(
                model,
                instance=instance,
                op_vars=op_vars,
                horizon=horizon,
                constraint=sc,
                machine_name_to_id=machine_name_to_id,
                day_offsets=day_offsets,
            )
        elif sc.category == "prefer_grouping_by_material":
            sp = translate_prefer_grouping_by_family(
                model,
                instance=instance,
                op_vars=op_vars,
                horizon=horizon,
                constraint=sc,
            )
        elif sc.category == "prefer_grouping_by_client":
            sp = translate_prefer_grouping_by_client(
                model,
                instance=instance,
                op_vars=op_vars,
                horizon=horizon,
                constraint=sc,
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
