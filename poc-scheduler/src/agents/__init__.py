"""Couche agents — orchestration LLM cantonnee a extraction / explication.

Module **vertical-agnostic**. Fournit la base `Agent` que les verticales
specialisent avec leur prompt + leur schema Pydantic de sortie.

Doctrine (specs-techniques-v3 §5.4) : aucun agent ne genere de code OR-Tools,
ne modifie un pattern, ne desactive un mecanisme du trust layer. La couche
LLM est cantonnee a la traduction NL <-> structures Pydantic strictes.

Voir `src/verticals/<vertical>/agents/` pour les agents concrets.
"""

from src.agents.base import Agent, AgentResult

__all__ = ["Agent", "AgentResult"]
