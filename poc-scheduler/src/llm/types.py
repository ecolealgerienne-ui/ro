"""Types primitifs pour la couche LLM."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """Un message dans une conversation LLM."""

    model_config = ConfigDict(frozen=True)

    role: Role
    content: str = Field(..., min_length=1)
