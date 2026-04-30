"""Abstraction `LLMProvider` + implementations.

Contrat minimal volontairement simple :
    `complete(messages) -> str`

Les fonctionnalites avancees (streaming, tool use natif via API) seront
ajoutees au cas par cas si un agent en a besoin. Pour l'instant tous les
agents Phase 3 fonctionnent en single-shot prompt -> JSON.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Final

from src.llm.types import Message, Role

_DEFAULT_MODEL: Final[str] = "claude-sonnet-4-5"
_DEFAULT_MAX_TOKENS: Final[int] = 4096


class LLMProvider(ABC):
    """Contrat minimal d'un provider LLM."""

    @abstractmethod
    def complete(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = 0.0,
    ) -> str:
        """Envoie une conversation et retourne le texte de la reponse.

        Args:
            messages: historique complet (premier = user ou system).
            max_tokens: limite de tokens dans la reponse.
            temperature: 0.0 = deterministe, 1.0 = creatif. Default 0.0.

        Returns:
            Texte brut de la reponse (premier text-block s'il y en a plusieurs).
        """


class FakeLLMProvider(LLMProvider):
    """Provider deterministe pour les tests.

    Initialise avec :
    - une liste de reponses canned (consommees dans l'ordre), OU
    - un callable `(messages) -> str` qui calcule la reponse.

    Trace les appels dans `self.calls` pour assertions.
    """

    def __init__(
        self,
        responses: Sequence[str] | Callable[[Sequence[Message]], str],
    ) -> None:
        self._responses_iter = iter(responses) if isinstance(responses, Sequence) else None
        self._responder = responses if callable(responses) else None
        if self._responses_iter is None and self._responder is None:
            raise ValueError("FakeLLMProvider : responses doit etre Sequence ou Callable")
        self.calls: list[list[Message]] = []

    def complete(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append(list(messages))
        if self._responder is not None:
            return self._responder(messages)
        try:
            assert self._responses_iter is not None
            return next(self._responses_iter)
        except StopIteration as e:
            raise RuntimeError("FakeLLMProvider : plus de reponses canned disponibles") from e


class ClaudeAPIProvider(LLMProvider):
    """Provider via le SDK officiel `anthropic`.

    Necessite la variable d'environnement `ANTHROPIC_API_KEY` (ou la passer
    explicitement). Importe `anthropic` paresseusement pour permettre
    l'execution des tests sans la dep installee.
    """

    def __init__(
        self,
        *,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
    ) -> None:
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover (dep est en main, deja installee)
            raise ImportError(
                "Le SDK `anthropic` n'est pas installe. `uv sync` apres l'avoir "
                "ajoute aux dependances."
            ) from e

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY non defini. Soit en variable d'environnement, "
                "soit passe a l'initialisation : ClaudeAPIProvider(api_key=...)."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model

    def complete(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = 0.0,
    ) -> str:
        # L'API Anthropic separe le system prompt du reste
        system_parts = [m.content for m in messages if m.role is Role.SYSTEM]
        chat_messages = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role is not Role.SYSTEM
        ]
        kwargs: dict[str, object] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
            "temperature": temperature,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)

        response = self._client.messages.create(**kwargs)  # type: ignore[arg-type]

        # Concat tous les text-blocks ; ignore les blocks d'autre type
        # (tool_use, etc. — pas utilises a ce stade).
        texts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                texts.append(block.text)  # type: ignore[attr-defined]
        return "".join(texts)
