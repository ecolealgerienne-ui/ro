"""Objectifs composites — interface haut niveau pour priorites relatives.

Module **vertical-agnostic**. Permet a un utilisateur d'exprimer ses priorites
entre objectifs d'ordonnancement (makespan, tardiness, stabilite, completion)
via des labels nommes (DISABLED / LOW / MEDIUM / HIGH / CRITICAL) plutot qu'en
manipulant directement les poids entiers passes a `WeightedObjectivePattern`.

Pipeline :

    user                                      builder                    solver
    ────                                      ───────                    ──────
    CompositeObjectiveSpec(...)
        ↓
    build_composite_soft_penalties(spec, ...) ─→ SoftPenaltyBuilder ─→ JSSPSolver.solve(
                                                                          soft_penalty_builder=builder,
                                                                          makespan_weight=spec.makespan_weight)

Les priorites sont mappees sur une echelle geometrique (1, 5, 25, 125) qui
garantit qu'un cran superieur domine clairement le cran inferieur sans pour
autant rendre les autres objectifs negligeables. Le poids 0 (DISABLED) signale
que l'objectif est exclu de l'objectif (la fonction ne genere pas de
SoftPenaltyVar pour cette categorie).

Doctrine :
- Le moteur expose 4 objectifs **universels** : `makespan`, `tardiness`,
  `stability`, `early_completion`. Tous les autres soft constraints (vertical-
  specifiques) restent geres via `SoftConstraintsAgent` + dispatcher de la
  verticale.
- Le composite peut **etendre** avec un callable `vertical_extras` qui retourne
  des `SoftPenaltyVar` supplementaires (ex: les translators meca).
- Aucune categorie metier n'est cablee dans cet engine.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import WorkshopInstance
from src.core.soft_constraints import (
    SoftPenaltyVar,
    aggregate_completion_var,
    aggregate_tardiness_var,
    schedule_stability_var,
    tier_weighted_stability_var,
)


class ObjectivePriority(StrEnum):
    """Priorite relative d'un objectif dans la fonction objectif composite."""

    DISABLED = "DISABLED"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


PRIORITY_TO_WEIGHT: Final[dict[ObjectivePriority, int]] = {
    ObjectivePriority.DISABLED: 0,
    ObjectivePriority.LOW: 1,
    ObjectivePriority.MEDIUM: 5,
    ObjectivePriority.HIGH: 25,
    ObjectivePriority.CRITICAL: 125,
}


class CompositeObjectiveSpec(BaseModel):
    """Specification haut niveau d'une fonction objectif composite.

    Chaque champ est une `ObjectivePriority` qui sera mappee sur un poids
    entier via `PRIORITY_TO_WEIGHT`. Les objectifs DISABLED ne contribuent
    pas du tout.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    makespan: ObjectivePriority = Field(
        default=ObjectivePriority.HIGH,
        description="Minimisation du makespan (temps total). Toujours present dans l'objectif.",
    )
    tardiness: ObjectivePriority = Field(
        default=ObjectivePriority.MEDIUM,
        description="Penalite de tardivete totale (necessite des `Job.deadline`).",
    )
    stability: ObjectivePriority = Field(
        default=ObjectivePriority.DISABLED,
        description=(
            "Penalite de deviation vs un planning de reference (replanification). "
            "Necessite `reference_schedule` non None lors du build."
        ),
    )
    early_completion: ObjectivePriority = Field(
        default=ObjectivePriority.DISABLED,
        description=(
            "Penalite proportionnelle a la somme des fins. Different du makespan "
            "(qui minimise le max) : minimise la somme prefere finir tot plusieurs jobs."
        ),
    )

    @property
    def makespan_weight(self) -> int:
        """Poids entier passe a `WeightedObjectivePattern.apply(makespan_weight=...)`.

        Garde-fou : si le makespan est explicitement DISABLED par l'utilisateur,
        on retourne 1 quand meme — le makespan est techniquement requis dans
        le modele (la `WeightedObjectivePattern` le construit pour produire la
        IntVar makespan exposee au solver). DISABLED sur makespan signifie
        seulement "ne pas chercher a le minimiser activement" — son poids
        reste minimal a 1.
        """
        weight = PRIORITY_TO_WEIGHT[self.makespan]
        return max(1, weight)


def _maybe_penalty(
    var: Any | None,
    *,
    label: str,
    priority: ObjectivePriority,
    expected_max: int | None = None,
) -> SoftPenaltyVar | None:
    """Construit un SoftPenaltyVar si la priorite est > DISABLED et la var existe.

    `expected_max` (Phase 1.3) : ordre de grandeur attendu de `var` au pire cas,
    sert a la calibration dynamique pour eviter qu'une penalite a grosse echelle
    n'ecrase les autres.
    """
    if var is None or priority is ObjectivePriority.DISABLED:
        return None
    weight = PRIORITY_TO_WEIGHT[priority]
    if weight < 1:
        return None
    return SoftPenaltyVar(label=label, weight=weight, var=var, expected_max=expected_max)


# ---------- Calibration dynamique des poids (Phase 1.3) ----------

# Cible d'echelle apres calibration : chaque penalite calibree contribue
# environ `CALIBRATION_TARGET` au pire cas, AVANT amplification par sa priorite.
# Ainsi, deux penalites de meme priorite contribuent dans le meme ordre de
# grandeur, quelle que soit leur echelle brute (minutes vs counts vs ratios).
CALIBRATION_TARGET: Final[int] = 1000


def calibrate_penalty_weights(
    penalties: Sequence[SoftPenaltyVar],
    *,
    target: int = CALIBRATION_TARGET,
) -> list[SoftPenaltyVar]:
    """Re-ponderation des SoftPenaltyVar pour eviter qu'une penalite n'ecrase les autres.

    Pour chaque penalite avec `expected_max` defini, le nouveau poids est :

        new_weight = max(1, round(weight * target / expected_max))

    Cela rend les penalites comparables : une penalite "tardiness" en minutes
    (scale 1e5) et une penalite "count overlaps" (scale 1e1) contribuent
    similairement au pire cas avant d'etre amplifiees par leurs priorites.

    Les penalites sans `expected_max` sont laissees inchangees (le translator
    n'a pas annote, on ne peut pas calibrer).

    Args:
        penalties: liste de SoftPenaltyVar produites par les translators.
        target: scale cible apres calibration. Defaut 1000.

    Returns:
        Nouvelle liste avec poids ajustes. Liste originale non mutee.
    """
    if target < 1:
        raise ValueError(f"target doit etre >= 1, recu {target}")
    out: list[SoftPenaltyVar] = []
    for sp in penalties:
        if sp.expected_max is None or sp.expected_max <= 0:
            out.append(sp)
            continue
        new_weight = max(1, round(sp.weight * target / sp.expected_max))
        # On preserve `expected_max` post-calibration pour traceabilite.
        out.append(
            SoftPenaltyVar(
                label=sp.label, weight=new_weight, var=sp.var, expected_max=sp.expected_max
            )
        )
    return out


def build_composite_soft_penalties(
    spec: CompositeObjectiveSpec,
    *,
    reference_schedule: Mapping[tuple[int, int], int] | None = None,
    stability_tier_weights: Mapping[int, int] | None = None,
    vertical_extras: Callable[..., Sequence[SoftPenaltyVar]] | None = None,
    calibrate: bool = True,
    calibration_target: int = CALIBRATION_TARGET,
) -> Callable[..., Sequence[SoftPenaltyVar]]:
    """Construit un `SoftPenaltyBuilder` configure selon la spec composite.

    Args:
        spec: priorites relatives des 4 objectifs universels.
        reference_schedule: si fourni et `spec.stability != DISABLED`, ajoute
            la penalite de stabilite (deviation vs ce reference). Sinon, la
            stabilite est silencieusement absente.
        stability_tier_weights: si fourni (Phase 1.5), utilise
            `tier_weighted_stability_var` au lieu de `schedule_stability_var`.
            Le mapping `tier -> weight` est typiquement fourni par la verticale
            (ex: `MECH_TIER_WEIGHTS = {1: 10, 2: 3, 3: 1}`). Sans effet si
            `reference_schedule` est None.
        vertical_extras: callable optionnel pour ajouter des `SoftPenaltyVar`
            specifiques a la verticale (ex: le dispatcher de soft constraints
            NL-driven). Signature : `(*, model, instance, op_vars, horizon) ->
            Sequence[SoftPenaltyVar]`.
        calibrate: applique `calibrate_penalty_weights` sur les penalites
            collectees avant retour. Defaut True (Phase 1.3). False = poids
            bruts (comportement Phase 1.2).
        calibration_target: scale cible pour la calibration. Defaut 1000.

    Returns:
        Une fonction `(*, model, instance, op_vars, horizon) -> list[SoftPenaltyVar]`
        compatible avec `JSSPSolver.solve(soft_penalty_builder=...)`.
    """

    def builder(
        *,
        model: Any,
        instance: WorkshopInstance,
        op_vars: Mapping[tuple[int, int], Mapping[str, Any]],
        horizon: int,
    ) -> list[SoftPenaltyVar]:
        out: list[SoftPenaltyVar] = []

        # Tardiness aggregate — expected_max = horizon * n_jobs_with_deadline
        if spec.tardiness is not ObjectivePriority.DISABLED:
            tardy = aggregate_tardiness_var(
                model, instance=instance, op_vars=op_vars, horizon=horizon
            )
            n_with_deadline = sum(1 for j in instance.jobs if j.deadline is not None)
            expected_max = max(1, horizon * n_with_deadline)
            sp = _maybe_penalty(
                tardy,
                label="composite_tardiness",
                priority=spec.tardiness,
                expected_max=expected_max,
            )
            if sp is not None:
                out.append(sp)

        # Stability vs reference — expected_max = horizon * n_ops_in_reference
        # (multiplie par max_tier_weight si tier-pondere, Phase 1.5)
        if spec.stability is not ObjectivePriority.DISABLED and reference_schedule is not None:
            if stability_tier_weights:
                stab = tier_weighted_stability_var(
                    model,
                    instance=instance,
                    op_vars=op_vars,
                    horizon=horizon,
                    reference_schedule=reference_schedule,
                    weight_per_tier=stability_tier_weights,
                )
                max_tier_weight = max(stability_tier_weights.values(), default=1)
                expected_max = max(1, horizon * len(reference_schedule) * max_tier_weight)
                label = "composite_stability_tier_weighted"
            else:
                stab = schedule_stability_var(
                    model,
                    op_vars=op_vars,
                    horizon=horizon,
                    reference_schedule=reference_schedule,
                )
                expected_max = max(1, horizon * len(reference_schedule))
                label = "composite_stability"
            sp = _maybe_penalty(
                stab,
                label=label,
                priority=spec.stability,
                expected_max=expected_max,
            )
            if sp is not None:
                out.append(sp)

        # Early completion — expected_max = horizon * n_jobs (somme des fins)
        if spec.early_completion is not ObjectivePriority.DISABLED:
            comp = aggregate_completion_var(
                model, instance=instance, op_vars=op_vars, horizon=horizon
            )
            expected_max = max(1, horizon * len(instance.jobs))
            sp = _maybe_penalty(
                comp,
                label="composite_early_completion",
                priority=spec.early_completion,
                expected_max=expected_max,
            )
            if sp is not None:
                out.append(sp)

        # Vertical extras (ex: dispatcher meca pour soft NL-driven)
        if vertical_extras is not None:
            extras = vertical_extras(
                model=model, instance=instance, op_vars=op_vars, horizon=horizon
            )
            out.extend(extras)

        # Calibration : re-pondere selon les expected_max annotes par les
        # translators. Les penalites sans expected_max sont laissees inchangees.
        if calibrate:
            out = calibrate_penalty_weights(out, target=calibration_target)

        return out

    return builder


__all__ = [
    "CALIBRATION_TARGET",
    "PRIORITY_TO_WEIGHT",
    "CompositeObjectiveSpec",
    "ObjectivePriority",
    "build_composite_soft_penalties",
    "calibrate_penalty_weights",
]
