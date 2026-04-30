"""Soft constraints — penalites ponderees agregees a l'objectif CP-SAT.

Module **vertical-agnostic**. Fournit le mecanisme generique pour combiner le
makespan et un ensemble de penalites soft dans une fonction objectif unique :

    minimise(makespan_weight * makespan + sum(weight_i * penalty_i))

Doctrine :
- Une **soft constraint** = une preference d'ordonnancement, qui n'est pas
  obligatoire mais penalisee si violee (cf. specs §7.2 et agent 3.6 NL→soft).
- Une **hard constraint** = obligatoire, encodee directement dans le modele
  (NoOverlap, Precedence, etc.). Une violation = INFEASIBLE.
- Les soft constraints sont **traduites par la verticale** en penalty terms
  via `src/verticals/<vertical>/soft_translators.py`. Cet engine ne connait
  aucune categorie metier.

Le pattern WeightedObjectivePattern remplace MakespanObjectivePattern lorsqu'il
y a au moins 1 soft penalty. S'il n'y en a aucune, comportement identique.

Note importante sur l'extraction du makespan apres solving :
- Avec MakespanObjectivePattern, `solver.objective_value` == makespan.
- Avec WeightedObjectivePattern, `solver.objective_value` == somme ponderee.
  Le solver doit utiliser `solver.value(makespan_var)` pour recuperer le
  makespan brut. Le pattern retourne donc la `IntVar` makespan pour permettre
  cette extraction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

from src.core.pattern import Pattern


@dataclass(frozen=True)
class SoftPenaltyVar:
    """Une penalite soft prete a etre integree dans l'objectif.

    Attributs :
        label   : identifiant lisible (pour tracing / debugging post-solving).
        weight  : poids entier strictement positif (CP-SAT n'aime pas les floats
                  dans l'objectif). La verticale convertit les `weight_hint`
                  flottants de `SoftConstraintsAgent` en entiers (typiquement
                  `int(weight_hint * 100)`).
        var     : `cp_model.IntVar` representant la penalite (>= 0). La
                  semantique exacte (compte, overlap, lateness, etc.) depend
                  du translator metier qui l'a produite.
        expected_max : ordre de grandeur attendu de `var` au pire cas (Phase 1.3).
                  Sert a la calibration dynamique : `calibrate_penalty_weights`
                  re-pondere les penalites pour que toutes contribuent dans le
                  meme ordre de grandeur avant que les priorites n'amplifient.
                  None = pas de calibration appliquee (comportement legacy).
    """

    label: str
    weight: int
    var: Any  # cp_model.IntVar — Any car SDK CP-SAT non typé
    expected_max: int | None = None


class WeightedObjectivePattern(Pattern):
    """Objectif combinant makespan + somme ponderee de penalites soft.

    Si `soft_penalties` est vide, equivalent a `MakespanObjectivePattern`.
    """

    name: ClassVar[str] = "weighted_objective"
    description: ClassVar[str] = "Minimise makespan_weight * makespan + sum(weight_i * penalty_i)."

    def apply(
        self,
        model: Any,
        *,
        end_vars: Sequence[Any],
        horizon: int,
        soft_penalties: Sequence[SoftPenaltyVar] = (),
        makespan_weight: int = 1,
    ) -> Any:
        """Construit l'objectif et le minimise. Retourne la `IntVar` makespan.

        Args:
            model: `cp_model.CpModel`.
            end_vars: variables de fin de chaque dernier op de chaque job.
            horizon: borne sup theorique du makespan.
            soft_penalties: liste de `SoftPenaltyVar` produites par les
                translators de la verticale. Peut etre vide.
            makespan_weight: poids du makespan dans la somme ponderee. Defaut 1.
                Augmenter pour rendre le makespan dominant ; diminuer pour
                privilegier les soft.

        Returns:
            La `IntVar` makespan, pour extraction post-solving via
            `solver.value(makespan_var)`.
        """
        if not end_vars:
            raise ValueError("end_vars ne peut pas etre vide")
        if horizon < 0:
            raise ValueError(f"horizon doit etre >= 0, recu {horizon}")
        if makespan_weight < 1:
            raise ValueError(f"makespan_weight doit etre >= 1, recu {makespan_weight}")
        for sp in soft_penalties:
            if sp.weight < 1:
                raise ValueError(
                    f"SoftPenaltyVar '{sp.label}' : weight doit etre >= 1, recu {sp.weight}"
                )

        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, list(end_vars))

        if not soft_penalties:
            model.minimize(makespan_weight * makespan)
            return makespan

        # Somme ponderee : makespan + Sum(w_i * penalty_i)
        terms: list[Any] = [makespan_weight * makespan]
        terms.extend(sp.weight * sp.var for sp in soft_penalties)
        model.minimize(sum(terms))
        return makespan


# ---------- Helpers engine generiques pour objectifs composites (Phase 1.2) ----------
#
# Ces helpers retournent des IntVars CP-SAT representant des objectifs universels
# (tardiness, completion, stability). Vertical-agnostic : ils operent uniquement
# sur des champs de `WorkshopInstance` et `op_vars` standards.
#
# La couche `src/core/objectives.py` les compose en un `SoftPenaltyBuilder`
# selon les priorites nommees fournies par l'utilisateur.


def aggregate_tardiness_var(
    model: Any,
    *,
    instance: Any,  # WorkshopInstance — Any pour eviter import circulaire
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
) -> Any | None:
    """Retourne une IntVar = somme des max(0, end - deadline) sur tous les jobs.

    Filtre uniquement les jobs avec `deadline` defini. Retourne None si aucun
    job n'a de deadline (rien a penaliser).
    """
    eligible = [j for j in instance.jobs if j.deadline is not None]
    if not eligible:
        return None
    tardy_vars: list[Any] = []
    for job in eligible:
        last_idx = max(op.sequence_idx for op in job.operations)
        last_end = op_vars[(job.job_id, last_idx)]["end"]
        tardy = model.new_int_var(0, horizon, f"tardy_agg_j{job.job_id}")
        model.add_max_equality(tardy, [0, last_end - job.deadline])
        tardy_vars.append(tardy)
    total = model.new_int_var(0, horizon * len(tardy_vars), "tardiness_aggregate_total")
    model.add(total == sum(tardy_vars))
    return total


def aggregate_completion_var(
    model: Any,
    *,
    instance: Any,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
) -> Any | None:
    """Retourne une IntVar = somme des fins de chaque job.

    Different du makespan (qui minimise le max) : minimiser cette somme prefere
    finir tot plusieurs jobs plutot qu'optimiser le dernier.
    """
    last_ends: list[Any] = []
    for job in instance.jobs:
        last_idx = max(op.sequence_idx for op in job.operations)
        last_ends.append(op_vars[(job.job_id, last_idx)]["end"])
    if not last_ends:
        return None
    total = model.new_int_var(0, horizon * len(last_ends), "completion_aggregate_total")
    model.add(total == sum(last_ends))
    return total


def schedule_stability_var(
    model: Any,
    *,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    reference_schedule: Mapping[tuple[int, int], int],
) -> Any | None:
    """Retourne une IntVar = somme des |new_start - old_start| pour les ops du
    reference schedule presentes dans op_vars.

    Args:
        reference_schedule: dict {(job_id, seq_idx): old_start_value} —
            typiquement extrait d'un `SolverResult` precedent (replanification).

    Returns:
        IntVar de la deviation totale, ou None si aucune ref ne match `op_vars`.
    """
    deviations: list[Any] = []
    for (job_id, seq_idx), old_start in reference_schedule.items():
        if (job_id, seq_idx) not in op_vars:
            continue
        new_start = op_vars[(job_id, seq_idx)]["start"]
        diff = model.new_int_var(-horizon, horizon, f"diff_j{job_id}_o{seq_idx}")
        model.add(diff == new_start - old_start)
        abs_diff = model.new_int_var(0, horizon, f"abs_diff_j{job_id}_o{seq_idx}")
        model.add_abs_equality(abs_diff, diff)
        deviations.append(abs_diff)
    if not deviations:
        return None
    total = model.new_int_var(0, horizon * len(deviations), "stability_total")
    model.add(total == sum(deviations))
    return total


def tier_weighted_stability_var(
    model: Any,
    *,
    instance: Any,
    op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon: int,
    reference_schedule: Mapping[tuple[int, int], int],
    weight_per_tier: Mapping[int, int],
    default_weight: int = 1,
) -> Any | None:
    """Stabilite ponderee par criticite — variant tier-aware de `schedule_stability_var`.

    Pour chaque op `(job_id, seq_idx)` du reference :

        deviation = |new_start - old_start|
        weight    = weight_per_tier[job.criticality]  si defini,
                    sinon `default_weight`
        contribution = weight × deviation

    Le total = somme des contributions ponderees. Les ops dont le `Job.criticality`
    n'est pas dans `weight_per_tier` utilisent `default_weight`.

    Use case (Phase 1.5) : penaliser **plus** les deviations des jobs critiques
    (Tier 1) que celles des jobs standards (Tier 3) lors d'une replanification.
    Critere produit : "deplacer un Tier 1 doit couter 10× plus qu'un Tier 3".

    Args:
        instance: WorkshopInstance (pour acceder a `Job.criticality`).
        weight_per_tier: mapping `tier -> weight_multiplier`. Convention typique
            (mech_workshop) : `{1: 10, 2: 3, 3: 1}`.
        default_weight: poids applique aux jobs sans `criticality` (ou avec
            tier absent de `weight_per_tier`). Defaut 1.

    Returns:
        IntVar de la deviation ponderee totale, ou None si aucune ref ne match
        `op_vars`.

    Raises:
        ValueError: si `default_weight < 1` ou si un poids dans
            `weight_per_tier` est < 1.
    """
    if default_weight < 1:
        raise ValueError(f"default_weight doit etre >= 1, recu {default_weight}")
    for tier, w in weight_per_tier.items():
        if w < 1:
            raise ValueError(f"weight_per_tier[{tier}] doit etre >= 1, recu {w}")

    job_criticality: dict[int, int | None] = {
        job.job_id: job.criticality for job in instance.jobs
    }

    weighted_terms: list[Any] = []
    max_weight = max(
        (weight_per_tier.get(c, default_weight) for c in job_criticality.values()),
        default=default_weight,
    )
    for (job_id, seq_idx), old_start in reference_schedule.items():
        if (job_id, seq_idx) not in op_vars:
            continue
        new_start = op_vars[(job_id, seq_idx)]["start"]
        diff = model.new_int_var(-horizon, horizon, f"twdiff_j{job_id}_o{seq_idx}")
        model.add(diff == new_start - old_start)
        abs_diff = model.new_int_var(0, horizon, f"twabs_j{job_id}_o{seq_idx}")
        model.add_abs_equality(abs_diff, diff)
        crit = job_criticality.get(job_id)
        weight = weight_per_tier.get(crit, default_weight) if crit is not None else default_weight
        weighted_terms.append(weight * abs_diff)

    if not weighted_terms:
        return None
    bound = horizon * len(weighted_terms) * max(1, max_weight)
    total = model.new_int_var(0, bound, "tier_weighted_stability_total")
    model.add(total == sum(weighted_terms))
    return total
