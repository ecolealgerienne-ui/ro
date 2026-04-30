"""Agent 3.6 — traduction NL -> soft constraints structurees.

Cet agent prend un ensemble de phrases en langage naturel exprimant des
preferences d'ordonnancement et produit une liste de `SoftConstraint`
typees, mappees a un catalogue ferme de 10 categories canoniques meca.

Le prompt v1 = `prompt_v1_soft.md` valide empiriquement (75/75 sur 15 phrases
incluant 4 cas pieges critiques, des l'iteration 1).

Statut prompt : **valide empiriquement** (75/75 iteration 1, voir
experiments/llm-soft-constraints/verdict.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agents.base import Agent

PROMPT_PATH: Final[Path] = Path(__file__).parent.parent / "prompts" / "soft_constraints_nl_v1.md"
SCHEMA_PATH: Final[Path] = (
    Path(__file__).parent.parent / "prompts" / "soft_constraints_nl_target_schema_v1.md"
)

SoftConstraintCategory = Literal[
    "avoid_machine_during_period",
    "prefer_grouping_by_material",
    "prefer_grouping_by_client",
    "operator_avoidance",
    "operator_preference",
    "prefer_machine_over_other",
    "client_priority",
    "avoid_series_fragmentation",
    "limit_setups_per_day_on_machine",
    "prefer_operation_in_shift",
    "other",
]
ConfidenceLevel = Literal["high", "medium", "low"]


class SoftConstraint(BaseModel):
    """Une preference d'ordonnancement structuree."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    natural_language: str = Field(..., min_length=1)
    category: SoftConstraintCategory
    parameters: dict[str, str | int | float | bool | list[str] | None] = Field(default_factory=dict)
    weight_hint: float = Field(..., ge=0.0, le=1.0)
    weight_rationale: str
    confidence: ConfidenceLevel


class UnrecognizedConstraint(BaseModel):
    """Une phrase non interpretable (ambigue ou hors catalogue)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    natural_language: str = Field(..., min_length=1)
    reason: str
    suggestion: str = ""


class SoftConstraintsOutput(BaseModel):
    """Sortie agregee de l'agent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    soft_constraints: list[SoftConstraint] = Field(default_factory=list)
    unrecognized: list[UnrecognizedConstraint] = Field(default_factory=list)


class SoftConstraintsAgent(Agent):
    """Traduit des phrases NL en `SoftConstraint`s pondérées."""

    name: ClassVar[str] = "soft_constraints_nl"
    output_schema: ClassVar[type[BaseModel]] = SoftConstraintsOutput

    @classmethod
    def from_default_prompt(cls, provider: object) -> SoftConstraintsAgent:
        return cls(provider=provider, prompt_template=PROMPT_PATH.read_text(encoding="utf-8"))  # type: ignore[arg-type]

    def render_prompt(self, **inputs: object) -> str:
        phrases = inputs.get("phrases")
        if not isinstance(phrases, list) or not all(isinstance(p, str) for p in phrases):
            raise ValueError(
                f"{self.name} : input 'phrases' (list[str]) manquant ou de mauvais type"
            )
        if not phrases:
            raise ValueError(f"{self.name} : 'phrases' ne peut pas etre vide")
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        phrases_block = "\n".join(f"- {p}" for p in phrases)

        prompt = self.prompt_template
        prompt = prompt.replace("{{SCHEMA}}", schema)
        prompt = prompt.replace("{{PHRASES}}", phrases_block)
        return prompt
