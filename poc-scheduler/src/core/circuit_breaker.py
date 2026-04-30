"""Circuit breaker INFEASIBLE — sortie deterministe en cas d'echec solveur.

Module **vertical-agnostic**. Orchestre une suite finie de tentatives de
resolution avec budgets temps croissants, puis bascule sur l'extraction MIS
(Minimal Infeasible Subset) en cas d'echec.

Design :
- 3 tentatives par defaut (budgets en secondes, croissants).
- Si l'une des tentatives retourne FEASIBLE/OPTIMAL -> outcome SOLVED, on s'arrete.
- Si CP-SAT prouve l'infaisabilite (status INFEASIBLE) -> on s'arrete au plus tot
  (inutile de retenter avec plus de temps, le solveur a la preuve).
- Si toutes les tentatives retournent UNKNOWN ou MODEL_INVALID -> outcome
  EXHAUSTED, on appelle l'extracteur MIS pour fournir un diagnostic.

Garantie : aucune boucle infinie. Le nombre de tentatives est borne par
`len(time_budgets_s)`.

L'extracteur MIS reel sera livre en Phase 1.8 (`extraction MIS approximee +
generation actions correctives`). Ici on accepte n'importe quel callable
respectant la signature `(WorkshopInstance) -> str`. Defaut : un stub qui
documente l'absence d'extracteur.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import WorkshopInstance
from src.core.solver import JSSPSolver, SolverResult, SolverStatus


class AttemptKind(StrEnum):
    """Type d'une tentative dans la sequence du circuit breaker."""

    INITIAL = "INITIAL"
    RETRY = "RETRY"


class Attempt(BaseModel):
    """Trace d'une tentative individuelle."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(..., ge=0, description="Position dans la sequence (0-indexed).")
    kind: AttemptKind
    time_limit_s: float = Field(..., gt=0.0)
    status: SolverStatus
    makespan: int | None
    solve_time_s: float = Field(..., ge=0.0)


class CircuitBreakerOutcome(StrEnum):
    """Verdict final du circuit breaker."""

    SOLVED = "SOLVED"
    INFEASIBLE = "INFEASIBLE"
    EXHAUSTED = "EXHAUSTED"


class CircuitBreakerResult(BaseModel):
    """Resultat agrege du circuit breaker."""

    model_config = ConfigDict(frozen=True)

    outcome: CircuitBreakerOutcome
    final_result: SolverResult
    attempts: list[Attempt]
    mis_summary: str | None = Field(
        default=None,
        description="Resume de l'extraction MIS, peuple ssi outcome != SOLVED.",
    )

    @property
    def n_attempts(self) -> int:
        return len(self.attempts)


DEFAULT_TIME_BUDGETS_S: Final[tuple[float, ...]] = (10.0, 30.0, 60.0)


def _default_mis_extractor(_instance: WorkshopInstance) -> str:
    """Stub par defaut : pas d'extraction MIS. Phase 1.8 fournira la vraie."""
    return (
        "Extraction MIS non disponible (extracteur par defaut). "
        "Phase 1.8 livrera `extract_mis_approximate(instance)`. "
        "En attendant, fournir un extracteur custom via `mis_extractor=`."
    )


def solve_with_circuit_breaker(
    instance: WorkshopInstance,
    *,
    time_budgets_s: Sequence[float] = DEFAULT_TIME_BUDGETS_S,
    mis_extractor: Callable[[WorkshopInstance], str] = _default_mis_extractor,
    num_workers: int = 8,
) -> CircuitBreakerResult:
    """Lance le solveur avec une suite finie de tentatives, bascule MIS au besoin.

    Args:
        instance: instance JSSP (potentiellement industrielle).
        time_budgets_s: budgets temps croissants. Doit contenir au moins 1 valeur ;
            valeurs strictement positives.
        mis_extractor: callable invoque sur outcome INFEASIBLE ou EXHAUSTED, pour
            produire un diagnostic actionnable. Defaut : stub documente.
        num_workers: workers CP-SAT par tentative. Constant entre tentatives.

    Returns:
        `CircuitBreakerResult` avec outcome, trace des tentatives, dernier
        `SolverResult`, et `mis_summary` si pertinent.

    Raises:
        ValueError: si `time_budgets_s` est vide ou contient des valeurs <= 0.
    """
    if not time_budgets_s:
        raise ValueError("time_budgets_s ne peut pas etre vide")
    if any(b <= 0 for b in time_budgets_s):
        raise ValueError(f"time_budgets_s : valeurs > 0 requises, reçu {list(time_budgets_s)}")

    attempts: list[Attempt] = []
    last_result: SolverResult | None = None

    for idx, budget in enumerate(time_budgets_s):
        solver = JSSPSolver(time_limit_seconds=budget, num_workers=num_workers)
        result = solver.solve(instance)
        last_result = result
        attempts.append(
            Attempt(
                index=idx,
                kind=AttemptKind.INITIAL if idx == 0 else AttemptKind.RETRY,
                time_limit_s=budget,
                status=result.status,
                makespan=result.makespan,
                solve_time_s=result.solve_time_seconds,
            )
        )
        if result.has_solution:
            return CircuitBreakerResult(
                outcome=CircuitBreakerOutcome.SOLVED,
                final_result=result,
                attempts=attempts,
                mis_summary=None,
            )
        if result.status is SolverStatus.INFEASIBLE:
            mis = mis_extractor(instance)
            return CircuitBreakerResult(
                outcome=CircuitBreakerOutcome.INFEASIBLE,
                final_result=result,
                attempts=attempts,
                mis_summary=mis,
            )

    assert last_result is not None  # garanti par time_budgets_s non vide
    mis = mis_extractor(instance)
    return CircuitBreakerResult(
        outcome=CircuitBreakerOutcome.EXHAUSTED,
        final_result=last_result,
        attempts=attempts,
        mis_summary=mis,
    )
