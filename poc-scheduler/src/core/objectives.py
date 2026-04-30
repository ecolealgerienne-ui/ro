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
    var: Any | None, *, label: str, priority: ObjectivePriority
) -> SoftPenaltyVar | None:
    """Construit un SoftPenaltyVar si la priorite est > DISABLED et la var existe."""
    if var is None or priority is ObjectivePriority.DISABLED:
        return None
    weight = PRIORITY_TO_WEIGHT[priority]
    if weight < 1:
        return None
    return SoftPenaltyVar(label=label, weight=weight, var=var)


def build_composite_soft_penalties(
    spec: CompositeObjectiveSpec,
    *,
    reference_schedule: Mapping[tuple[int, int], int] | None = None,
    vertical_extras: Callable[..., Sequence[SoftPenaltyVar]] | None = None,
) -> Callable[..., Sequence[SoftPenaltyVar]]:
    """Construit un `SoftPenaltyBuilder` configure selon la spec composite.

    Args:
        spec: priorites relatives des 4 objectifs universels.
        reference_schedule: si fourni et `spec.stability != DISABLED`, ajoute
            la penalite de stabilite (deviation vs ce reference). Sinon, la
            stabilite est silencieusement absente.
        vertical_extras: callable optionnel pour ajouter des `SoftPenaltyVar`
            specifiques a la verticale (ex: le dispatcher de soft constraints
            NL-driven). Signature : `(*, model, instance, op_vars, horizon) ->
            Sequence[SoftPenaltyVar]`.

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

        # Tardiness aggregate
        if spec.tardiness is not ObjectivePriority.DISABLED:
            tardy = aggregate_tardiness_var(
                model, instance=instance, op_vars=op_vars, horizon=horizon
            )
            sp = _maybe_penalty(tardy, label="composite_tardiness", priority=spec.tardiness)
            if sp is not None:
                out.append(sp)

        # Stability vs reference
        if spec.stability is not ObjectivePriority.DISABLED and reference_schedule is not None:
            stab = schedule_stability_var(
                model,
                op_vars=op_vars,
                horizon=horizon,
                reference_schedule=reference_schedule,
            )
            sp = _maybe_penalty(stab, label="composite_stability", priority=spec.stability)
            if sp is not None:
                out.append(sp)

        # Early completion (sum of last ends)
        if spec.early_completion is not ObjectivePriority.DISABLED:
            comp = aggregate_completion_var(
                model, instance=instance, op_vars=op_vars, horizon=horizon
            )
            sp = _maybe_penalty(
                comp,
                label="composite_early_completion",
                priority=spec.early_completion,
            )
            if sp is not None:
                out.append(sp)

        # Vertical extras (ex: dispatcher meca pour soft NL-driven)
        if vertical_extras is not None:
            extras = vertical_extras(
                model=model, instance=instance, op_vars=op_vars, horizon=horizon
            )
            out.extend(extras)

        return out

    return builder


__all__ = [
    "PRIORITY_TO_WEIGHT",
    "CompositeObjectiveSpec",
    "ObjectivePriority",
    "build_composite_soft_penalties",
]
