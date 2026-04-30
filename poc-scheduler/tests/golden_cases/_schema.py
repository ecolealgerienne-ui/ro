"""Schéma Pydantic d'un golden case (format YAML).

Un golden case est une instance de scheduling + un ensemble d'attentes vérifiables
par le runner. Le YAML est validé strictement (`extra="forbid"`) : tout champ
inconnu fait échouer le chargement, ce qui évite les fautes de frappe silencieuses.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.models import WorkshopInstance

GoldenCategory = Literal[
    "baseline_jssp",
    "setup",
    "calendar",
    "operator",
    "shared_resource",
]

ExpectedStatus = Literal[
    "OPTIMAL",
    "FEASIBLE",
    "INFEASIBLE",
    "UNKNOWN",
]


class ExpectedOutcome(BaseModel):
    """Attentes vérifiables sur un `SolverResult`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status_in: list[ExpectedStatus] = Field(
        ..., min_length=1, description="Statuts CP-SAT acceptés."
    )
    makespan_min: int | None = Field(
        default=None, ge=0, description="Borne inférieure stricte (≥) sur le makespan."
    )
    makespan_max: int | None = Field(
        default=None, ge=0, description="Borne supérieure stricte (≤) sur le makespan."
    )
    solve_time_s_max: float = Field(
        default=10.0,
        gt=0.0,
        description="Temps de résolution max accepté (secondes).",
    )

    @model_validator(mode="after")
    def _check_makespan_window(self) -> ExpectedOutcome:
        if (
            self.makespan_min is not None
            and self.makespan_max is not None
            and self.makespan_min > self.makespan_max
        ):
            raise ValueError(
                f"makespan_min ({self.makespan_min}) > makespan_max ({self.makespan_max})"
            )
        return self


class GoldenCase(BaseModel):
    """Un golden case = une instance + des attentes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Identifiant unique (= nom du fichier YAML).")
    description: str = Field(..., min_length=1)
    category: GoldenCategory
    instance: WorkshopInstance
    expected: ExpectedOutcome
