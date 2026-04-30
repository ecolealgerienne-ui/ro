"""Agent 3.7 — explication NL d'un placement OF ou d'un INFEASIBLE.

Deux modes via le champ `kind` :
- `placement` : un OF a ete place a un instant T sur une machine M ; expliquer
  pourquoi (qualifications, deadline, regroupement, etc.).
- `infeasibility` : le solveur n'a pas trouve de planning ; expliquer la
  cause probable (calendrier, capacites, conflits) et suggerer des actions.

Statut prompt : **non valide empiriquement** — design partner needed sur
30 cas types (critere de sortie 3.7 v0-status).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agents.base import Agent

PROMPT_PATH: Final[Path] = Path(__file__).parent.parent / "prompts" / "explanation_v1.md"

ExplanationKind = Literal["placement", "infeasibility"]


class ExplanationOutput(BaseModel):
    """Explication structuree, francais professionnel d'atelier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = Field(..., min_length=1)
    reasons: list[str] = Field(..., max_length=5)
    actions_suggested: list[str] = Field(default_factory=list, max_length=3)
    kind: ExplanationKind


class ExplanationAgent(Agent):
    """Genere une explication NL d'un placement ou d'une infaisabilite."""

    name: ClassVar[str] = "explanation"
    output_schema: ClassVar[type[BaseModel]] = ExplanationOutput

    @classmethod
    def from_default_prompt(cls, provider: object) -> ExplanationAgent:
        return cls(provider=provider, prompt_template=PROMPT_PATH.read_text(encoding="utf-8"))  # type: ignore[arg-type]

    def render_prompt(self, **inputs: object) -> str:
        kind = inputs.get("kind")
        context = inputs.get("context")
        if kind not in ("placement", "infeasibility"):
            raise ValueError(
                f"{self.name} : kind doit etre 'placement' ou 'infeasibility', recu {kind!r}"
            )
        if not isinstance(context, dict):
            raise ValueError(f"{self.name} : input 'context' (dict) manquant ou de mauvais type")
        prompt = self.prompt_template
        prompt = prompt.replace("{{KIND}}", str(kind))
        prompt = prompt.replace(
            "{{CONTEXT_JSON}}", json.dumps(context, ensure_ascii=False, indent=2, default=str)
        )
        return prompt
