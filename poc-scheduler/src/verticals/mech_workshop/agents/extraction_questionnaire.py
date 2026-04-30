"""Agent 3.4 — extraction questionnaire arborescent → spec structuree.

Cet agent prend les reponses brutes d'un questionnaire d'onboarding (dict
plat fourni par l'UI Phase 5.2) et produit un `WorkshopSpec` Pydantic.

Le questionnaire arborescent lui-meme est un sujet UI/UX traite en Phase 5 ;
ici on traite uniquement la traduction `dict de reponses -> WorkshopSpec`.

Statut prompt : **non valide empiriquement** — design partner needed.
Le scaffolding est en place, le prompt v1 doit etre itere avec de vrais
chefs d'atelier.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agents.base import Agent

PROMPT_PATH: Final[Path] = (
    Path(__file__).parent.parent / "prompts" / "extraction_questionnaire_v1.md"
)

ShiftPattern = Literal["1x8", "2x8", "3x8", "autre"]
MachineType = Literal[
    "tour_cn",
    "fraiseuse",
    "centre_usinage",
    "rectifieuse",
    "perceuse",
    "machine_controle",
    "autre",
]
Certification = Literal["aero", "auto", "medical", "iso9001", "autre"]
Material = Literal["aluminium", "acier", "inox", "titane", "autre"]
SharedResourceKind = Literal[
    "aspiration",
    "alim_400v",
    "pont_roulant",
    "controle_dimensionnel",
    "autre",
]


class WorkshopSpec(BaseModel):
    """Spec structuree produite a partir des reponses du questionnaire."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workshop_name: str = Field(..., min_length=1)
    n_machines_estimated: int = Field(..., ge=1, le=100)
    n_operators_estimated: int = Field(..., ge=1, le=200)
    machine_types: list[MachineType] = Field(default_factory=list)
    main_certifications: list[Certification] = Field(default_factory=list)
    main_materials: list[Material] = Field(default_factory=list)
    shift_pattern: ShiftPattern
    has_shared_resources: bool
    shared_resources_kinds: list[SharedResourceKind] = Field(default_factory=list)
    typical_order_size_pieces: int = Field(..., ge=1)
    typical_lead_time_days: int = Field(..., ge=1)
    notes: str = ""


class QuestionnaireAnswers(BaseModel):
    """Wrapper typage faible pour les reponses brutes du questionnaire UI."""

    model_config = ConfigDict(frozen=True)

    answers: dict[str, str | int | float | bool | list[str] | None]


class QuestionnaireAgent(Agent):
    """Traduit les reponses du questionnaire d'onboarding en `WorkshopSpec`."""

    name: ClassVar[str] = "extraction_questionnaire"
    output_schema: ClassVar[type[BaseModel]] = WorkshopSpec

    @classmethod
    def from_default_prompt(cls, provider: object) -> QuestionnaireAgent:
        return cls(provider=provider, prompt_template=PROMPT_PATH.read_text(encoding="utf-8"))  # type: ignore[arg-type]

    def render_prompt(self, **inputs: object) -> str:
        answers = inputs.get("answers")
        if not isinstance(answers, dict):
            raise ValueError(f"{self.name} : input 'answers' (dict) manquant ou de mauvais type")
        return self.prompt_template.replace(
            "{{ANSWERS_JSON}}", json.dumps(answers, ensure_ascii=False, indent=2)
        )
