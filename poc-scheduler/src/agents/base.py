"""Base abstraite des agents single-shot prompt -> JSON Pydantic.

Hypotheses sous-jacentes :
- Un appel LLM par requete utilisateur (pas de tool use natif a ce stade).
- Le prompt est rendu via substitution `{{KEY}}`.
- La sortie LLM est attendue en JSON parsable, validee par un schema Pydantic.

Pour les agents multi-turn (questionnaire) ou avec tool use, on derivera
une autre base le moment venu — pour l'instant les 5 agents Phase 3
fonctionnent en single-shot.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from src.llm.parsing import extract_json_block
from src.llm.provider import LLMProvider
from src.llm.types import Message, Role


class AgentResult(BaseModel):
    """Reponse structuree d'un agent single-shot."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    parsed: BaseModel
    raw_response: str
    n_llm_calls: int = 1


class Agent(ABC):
    """Base d'un agent LLM single-shot prompt -> JSON Pydantic.

    Les sous-classes :
    - definissent `name` et `output_schema` (ClassVars).
    - implementent `render_prompt(**inputs) -> str` pour la substitution
      des variables dans `prompt_template`.
    - heritent automatiquement de `run(...)` qui :
        1. rend le prompt,
        2. appelle le provider,
        3. extrait JSON,
        4. valide via `output_schema.model_validate`,
        5. retourne un `AgentResult`.

    Erreurs propagees :
    - `LLMParseError` (du parsing) si la reponse n'est pas du JSON parsable.
    - `pydantic.ValidationError` si le JSON ne respecte pas le schema.
    """

    name: ClassVar[str]
    output_schema: ClassVar[type[BaseModel]]

    def __init__(self, provider: LLMProvider, *, prompt_template: str) -> None:
        if not prompt_template.strip():
            raise ValueError(f"{type(self).__name__} : prompt_template vide")
        self.provider = provider
        self.prompt_template = prompt_template

    @abstractmethod
    def render_prompt(self, **inputs: object) -> str:
        """Substitue les variables du template avec les inputs et retourne le prompt final."""

    def run(self, **inputs: object) -> AgentResult:
        prompt = self.render_prompt(**inputs)
        messages = [Message(role=Role.USER, content=prompt)]
        raw = self.provider.complete(messages)
        data = extract_json_block(raw)
        parsed = self.output_schema.model_validate(data)
        return AgentResult(parsed=parsed, raw_response=raw)
