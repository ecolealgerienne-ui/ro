"""Score de confiance — mecanisme generique d'evaluation d'un `SolverResult`.

Module **vertical-agnostic** : calcule des metriques universelles sur n'importe
quelle instance/resultat, et agrege en un score [0, 1] selon les poids fournis
par la verticale appelante.

Pipeline :
    SolverResult + WorkshopInstance + weights -> ConfidenceScore

Design :
- 4 metriques universelles, chacune normalisee dans [0, 1] (1 = bon) :
  * `status_quality`        OPTIMAL > FEASIBLE > UNKNOWN > INFEASIBLE
  * `gap_to_best_known`     ecart relatif au best_known_makespan (si dispo)
  * `solve_time_ratio`      1 - sqrt(t / time_limit) (penalise les solves lents)
  * `machine_utilization`   fraction du temps ou les machines sont occupees
- 1 GATE dur : `validate_schedule` doit passer. Echec -> score = 0.0.
- Agregation : moyenne ponderee des metriques, par les poids fournis.

Voir `src/verticals/<vertical>/scoring_config.py` pour les calibrations metier.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import WorkshopInstance
from src.core.solver import SolverResult, SolverStatus, validate_schedule

METRIC_NAMES: Final[tuple[str, ...]] = (
    "status_quality",
    "gap_to_best_known",
    "solve_time_ratio",
    "machine_utilization",
)

_STATUS_QUALITY: Final[dict[SolverStatus, float]] = {
    SolverStatus.OPTIMAL: 1.0,
    SolverStatus.FEASIBLE: 0.7,
    SolverStatus.UNKNOWN: 0.3,
    SolverStatus.INFEASIBLE: 0.0,
    SolverStatus.MODEL_INVALID: 0.0,
}


class ConfidenceMetric(BaseModel):
    """Une metrique calculee : valeur brute, valeur normalisee dans [0, 1], poids."""

    model_config = ConfigDict(frozen=True)

    name: str
    raw_value: float
    normalized: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0)


class ConfidenceScore(BaseModel):
    """Score agrege + detail des metriques + notes de diagnostic."""

    model_config = ConfigDict(frozen=True)

    overall: float = Field(..., ge=0.0, le=1.0)
    gate_passed: bool
    metrics: list[ConfidenceMetric]
    notes: list[str] = Field(default_factory=list)


def _machine_utilization(instance: WorkshopInstance, result: SolverResult) -> float:
    if result.makespan is None or result.makespan <= 0:
        return 0.0
    n_machines = len(instance.machines)
    if n_machines == 0:
        return 0.0
    busy = sum(a.end - a.start for a in result.schedule)
    return min(1.0, busy / (result.makespan * n_machines))


def _gap_normalized(instance: WorkshopInstance, result: SolverResult) -> tuple[float, float]:
    """Retourne (raw_gap_pct, normalized). Si non mesurable, raw = -1, normalized = 0.5."""
    if instance.best_known_makespan is None or result.makespan is None:
        return -1.0, 0.5
    gap = result.gap_percent(instance.best_known_makespan)
    if gap is None:
        return -1.0, 0.5
    return gap, max(0.0, 1.0 - min(abs(gap), 100.0) / 100.0)


def _solve_time_ratio_normalized(result: SolverResult, time_limit_s: float) -> tuple[float, float]:
    if time_limit_s <= 0:
        return 0.0, 1.0
    ratio = min(1.0, result.solve_time_seconds / time_limit_s)
    return ratio, max(0.0, 1.0 - ratio**0.5)


def score_solver_result(
    instance: WorkshopInstance,
    result: SolverResult,
    *,
    weights: Mapping[str, float],
    time_limit_s: float,
) -> ConfidenceScore:
    """Calcule le score de confiance d'un `SolverResult`.

    Args:
        instance: instance soumise au solveur.
        result: resultat du solveur.
        weights: poids par metrique (cles dans `METRIC_NAMES`). Cles inconnues
            ignorees ; cles manquantes -> poids 0.
        time_limit_s: limite de temps utilisee par le solveur (pour normaliser
            `solve_time_ratio`).

    Returns:
        `ConfidenceScore` complet (jamais d'exception, le score capture tout).

    Note:
        Si le gate `validate_schedule` echoue, `overall = 0.0` et `gate_passed
        = False`. Aucune ponderation ne peut compenser un planning invalide.
    """
    notes: list[str] = []

    gate_passed = result.has_solution
    if gate_passed:
        validation_errors = validate_schedule(instance, result.schedule)
        if validation_errors:
            gate_passed = False
            notes.append(
                f"validate_schedule a remonte {len(validation_errors)} erreur(s) ; "
                f"premiere : {validation_errors[0]}"
            )

    status_q = _STATUS_QUALITY.get(result.status, 0.0)
    gap_raw, gap_norm = _gap_normalized(instance, result)
    if instance.best_known_makespan is None:
        notes.append("best_known_makespan absent : gap metric a 0.5 par defaut")

    time_raw, time_norm = _solve_time_ratio_normalized(result, time_limit_s)
    util = _machine_utilization(instance, result)

    raw_values: dict[str, float] = {
        "status_quality": status_q,
        "gap_to_best_known": gap_raw,
        "solve_time_ratio": time_raw,
        "machine_utilization": util,
    }
    normalized_values: dict[str, float] = {
        "status_quality": status_q,
        "gap_to_best_known": gap_norm,
        "solve_time_ratio": time_norm,
        "machine_utilization": util,
    }

    metrics = [
        ConfidenceMetric(
            name=name,
            raw_value=raw_values[name],
            normalized=normalized_values[name],
            weight=max(0.0, float(weights.get(name, 0.0))),
        )
        for name in METRIC_NAMES
    ]

    if not gate_passed:
        return ConfidenceScore(overall=0.0, gate_passed=False, metrics=metrics, notes=notes)

    total_weight = sum(m.weight for m in metrics)
    if total_weight <= 0.0:
        notes.append("somme des poids = 0, score force a 0.0")
        return ConfidenceScore(overall=0.0, gate_passed=True, metrics=metrics, notes=notes)

    overall = sum(m.normalized * m.weight for m in metrics) / total_weight
    return ConfidenceScore(
        overall=min(1.0, max(0.0, overall)),
        gate_passed=True,
        metrics=metrics,
        notes=notes,
    )
