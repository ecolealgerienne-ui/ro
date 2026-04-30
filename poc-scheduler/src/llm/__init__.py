"""Couche LLM — abstraction provider + parsing.

Module **vertical-agnostic**. Decouple le code applicatif (les agents) des
SDKs LLM concrets. Permet :

- de tester les agents avec un `FakeLLMProvider` deterministe (sans appel API)
- de basculer Claude / Mistral / GPT en changeant 1 ligne d'instanciation
- d'eviter le lock-in Anthropic-MCP (decision 2026-04-30)

Public API :
    LLMProvider           ABC, contrat minimal `complete(messages) -> str`
    FakeLLMProvider       implementation deterministe pour tests
    ClaudeAPIProvider     implementation via SDK officiel `anthropic`
    Message, Role         types
    extract_json_block    helper de parsing robuste (ignore texte autour)

Voir `src/agents/` pour les agents qui consomment cette couche.
"""

from src.llm.parsing import LLMParseError, extract_json_block
from src.llm.provider import (
    ClaudeAPIProvider,
    FakeLLMProvider,
    LLMProvider,
)
from src.llm.types import Message, Role

__all__ = [
    "ClaudeAPIProvider",
    "FakeLLMProvider",
    "LLMParseError",
    "LLMProvider",
    "Message",
    "Role",
    "extract_json_block",
]
