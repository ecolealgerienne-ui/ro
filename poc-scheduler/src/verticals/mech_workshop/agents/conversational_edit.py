"""Agent 3.8 — modifications conversationnelles.

L'utilisateur formule une demande en langage naturel (« priorite 1 sur Safran »,
« bascule l'OF 2026-001 sur TOUR-02 »). L'agent produit un **plan d'actions
structurees** que le backend appliquera apres validation humaine.

Doctrine (specs-techniques-v3 §5.4) : l'agent NE MODIFIE RIEN. Il propose un
plan auditable. Le backend valide et applique.

Statut prompt : **non valide empiriquement** — design partner needed sur
10 modifications types (critere 3.8 v0-status).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.agents.base import Agent

PROMPT_PATH: Final[Path] = Path(__file__).parent.parent / "prompts" / "conversational_edit_v1.md"

EditActionKind = Literal[
    "set_client_priority",
    "reassign_operation_machine",
    "shift_deadline",
    "freeze_order",
    "release_order",
    "set_order_priority",
    "other",
]


class EditAction(BaseModel):
    """Une action atomique du plan, appliquee par le backend."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: EditActionKind
    target: str = Field(..., min_length=1)
    params: dict[str, str | int | float | bool | list[str] | None] = Field(default_factory=dict)
    rationale: str = Field(..., min_length=1)


class EditPlan(BaseModel):
    """Plan d'actions propose par l'agent, validable par un humain."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actions: list[EditAction] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str = ""
    user_request_normalized: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_clarification_consistency(self) -> EditPlan:
        if self.needs_clarification:
            if not self.clarification_question.strip():
                raise ValueError("needs_clarification=True mais clarification_question vide")
            if self.actions:
                raise ValueError(
                    "needs_clarification=True doit etre accompagne de actions=[] "
                    f"(trouve {len(self.actions)} actions)"
                )
        else:
            if not self.actions:
                raise ValueError(
                    "needs_clarification=False mais actions=[] : plan vide non autorise"
                )
        return self


class ConversationalEditAgent(Agent):
    """Traduit une demande NL en `EditPlan` auditable."""

    name: ClassVar[str] = "conversational_edit"
    output_schema: ClassVar[type[BaseModel]] = EditPlan

    @classmethod
    def from_default_prompt(cls, provider: object) -> ConversationalEditAgent:
        return cls(provider=provider, prompt_template=PROMPT_PATH.read_text(encoding="utf-8"))  # type: ignore[arg-type]

    def render_prompt(self, **inputs: object) -> str:
        user_request = inputs.get("user_request")
        instance_summary = inputs.get("instance_summary", {})
        if not isinstance(user_request, str) or not user_request.strip():
            raise ValueError(f"{self.name} : input 'user_request' (str non vide) manquant")
        if not isinstance(instance_summary, dict):
            raise ValueError(
                f"{self.name} : input 'instance_summary' (dict) manquant ou de mauvais type"
            )
        prompt = self.prompt_template
        prompt = prompt.replace("{{USER_REQUEST}}", user_request)
        prompt = prompt.replace(
            "{{INSTANCE_SUMMARY_JSON}}",
            json.dumps(instance_summary, ensure_ascii=False, indent=2, default=str),
        )
        return prompt
