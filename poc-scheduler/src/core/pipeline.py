"""Pipeline complet — orchestration `solve -> simulate -> score -> decide`.

Module **vertical-agnostic**. Agrege les 4 modules engine livres en Phase 2
(circuit breaker, simulation, scoring, plus le hard gate `validate_schedule`)
en une decision finale deterministe ACCEPT / WARN / REJECT.

Pipeline :

    instance --[circuit_breaker]--> CircuitBreakerResult
                                         |
                          outcome SOLVED ?
                          /        |        \\
                        oui      INFEAS.   EXHAUSTED
                         |         |          |
                  [simulation]   REJECT     REJECT
                  [score]
                       |
                  [decide]
                       |
                       v
                 PipelineDecision

Regle d'agregation (priorite descendante) :
    1. Si circuit_breaker outcome != SOLVED            -> REJECT
    2. Sinon si score.gate_passed == False             -> REJECT
    3. Sinon si simulation.verdict == REJECT           -> REJECT
    4. Sinon si simulation.verdict == WARN             -> WARN
    5. Sinon                                            -> ACCEPT

Aucune ponderation ne peut surclasser un signal "REJECT" : la doctrine est
qu'un seul garde-fou rouge suffit a refuser. C'est l'objet du Gate 1 :
< 1 erreur silencieuse / 100 ateliers tests.

Configuration : passer les calibrations de la verticale (poids scoring,
seuils simulation) via les parametres `confidence_weights` et
`simulation_thresholds` (typiquement
`MECH_CONFIDENCE_WEIGHTS` et `MECH_SIMULATION_THRESHOLDS`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.core.circuit_breaker import (
    DEFAULT_TIME_BUDGETS_S,
    CircuitBreakerOutcome,
    CircuitBreakerResult,
    solve_with_circuit_breaker,
)
from src.core.models import WorkshopInstance
from src.core.scoring import ConfidenceScore, score_solver_result
from src.core.simulation import (
    SimulationReport,
    SimulationVerdict,
    ViolationSeverity,
    simulate_schedule,
)


class PipelineDecisionKind(StrEnum):
    ACCEPT = "ACCEPT"
    WARN = "WARN"
    REJECT = "REJECT"


class PipelineDecision(BaseModel):
    """Decision finale agregee + raisons humaines."""

    model_config = ConfigDict(frozen=True)

    kind: PipelineDecisionKind
    reasons: list[str] = Field(default_factory=list)


class PipelineReport(BaseModel):
    """Rapport complet d'execution du pipeline."""

    model_config = ConfigDict(frozen=True)

    instance_name: str
    circuit_breaker: CircuitBreakerResult
    simulation: SimulationReport | None = Field(
        default=None, description="None si circuit_breaker outcome != SOLVED."
    )
    score: ConfidenceScore | None = Field(
        default=None, description="None si circuit_breaker outcome != SOLVED."
    )
    decision: PipelineDecision


def _decide(
    cb: CircuitBreakerResult,
    simulation: SimulationReport | None,
    score: ConfidenceScore | None,
) -> PipelineDecision:
    """Agrege les 3 signaux en une decision finale, par priorite descendante."""
    reasons: list[str] = []

    if cb.outcome is not CircuitBreakerOutcome.SOLVED:
        mis = cb.mis_summary or "(MIS non disponible)"
        reasons.append(
            f"Circuit breaker : outcome {cb.outcome.value}, "
            f"{cb.n_attempts} tentative(s). {mis}"
        )
        return PipelineDecision(kind=PipelineDecisionKind.REJECT, reasons=reasons)

    assert simulation is not None and score is not None  # garanti par le if au-dessus

    if not score.gate_passed:
        first_note = score.notes[0] if score.notes else "(sans detail)"
        reasons.append(f"Score gate failed : {first_note}")
        return PipelineDecision(kind=PipelineDecisionKind.REJECT, reasons=reasons)

    if simulation.verdict is SimulationVerdict.REJECT:
        n_critical = sum(
            1 for v in simulation.violations if v.severity is ViolationSeverity.REJECT
        )
        reasons.append(
            f"Simulation REJECT : {n_critical} violation(s) critique(s) sur "
            f"{len(simulation.violations)} totale(s)"
        )
        return PipelineDecision(kind=PipelineDecisionKind.REJECT, reasons=reasons)

    if simulation.verdict is SimulationVerdict.WARN:
        reasons.append(
            f"Simulation WARN : {len(simulation.violations)} avertissement(s). "
            f"Score {score.overall:.2f}"
        )
        return PipelineDecision(kind=PipelineDecisionKind.WARN, reasons=reasons)

    reasons.append(
        f"Score {score.overall:.2f}, status {cb.final_result.status.value}, "
        f"{cb.n_attempts} tentative(s), 0 violation"
    )
    return PipelineDecision(kind=PipelineDecisionKind.ACCEPT, reasons=reasons)


def run_pipeline(
    instance: WorkshopInstance,
    *,
    confidence_weights: Mapping[str, float],
    simulation_thresholds: Mapping[str, float],
    time_budgets_s: Sequence[float] = DEFAULT_TIME_BUDGETS_S,
    mis_extractor: Callable[[WorkshopInstance], str] | None = None,
    num_workers: int = 8,
) -> PipelineReport:
    """Execute le pipeline complet pour une instance donnee.

    Args:
        instance: instance JSSP a resoudre.
        confidence_weights: poids des metriques de confiance (ex:
            `MECH_CONFIDENCE_WEIGHTS`).
        simulation_thresholds: seuils de simulation operationnelle (ex:
            `MECH_SIMULATION_THRESHOLDS`).
        time_budgets_s: budgets temps croissants pour le circuit breaker
            (defaut : 10 s / 30 s / 60 s).
        mis_extractor: callable optionnel pour extraction MIS (Phase 1.8).
        num_workers: workers CP-SAT par tentative.

    Returns:
        `PipelineReport` complet : trace circuit breaker, simulation et score
        si pertinents, decision finale + raisons.
    """
    cb_kwargs: dict[str, object] = {
        "time_budgets_s": tuple(time_budgets_s),
        "num_workers": num_workers,
    }
    if mis_extractor is not None:
        cb_kwargs["mis_extractor"] = mis_extractor

    cb = solve_with_circuit_breaker(instance, **cb_kwargs)  # type: ignore[arg-type]

    simulation: SimulationReport | None = None
    score: ConfidenceScore | None = None

    if cb.outcome is CircuitBreakerOutcome.SOLVED:
        simulation = simulate_schedule(
            instance, cb.final_result, **simulation_thresholds
        )
        # Le budget effectif = celui de la derniere tentative
        final_budget = cb.attempts[-1].time_limit_s
        score = score_solver_result(
            instance,
            cb.final_result,
            weights=confidence_weights,
            time_limit_s=final_budget,
        )

    decision = _decide(cb, simulation, score)
    return PipelineReport(
        instance_name=instance.name,
        circuit_breaker=cb,
        simulation=simulation,
        score=score,
        decision=decision,
    )
