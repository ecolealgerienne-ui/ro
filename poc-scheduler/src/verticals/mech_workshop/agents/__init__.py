"""Agents LLM specialises pour la verticale `mech_workshop`.

Chaque agent =
- un prompt template (dans `../prompts/`)
- un schema Pydantic de sortie (defini ici)
- une classe `Agent` qui rend le prompt et valide la reponse

Public API : 5 agents Phase 3.
"""

from src.verticals.mech_workshop.agents.conversational_edit import (
    ConversationalEditAgent,
    EditAction,
    EditActionKind,
    EditPlan,
)
from src.verticals.mech_workshop.agents.explanation import (
    ExplanationAgent,
    ExplanationKind,
    ExplanationOutput,
)
from src.verticals.mech_workshop.agents.extraction_csv import (
    AnomalyItem,
    CSVExtractionAgent,
    CSVExtractionOutput,
    ExtractedMachine,
    ExtractedOperation,
    ExtractedOrder,
)
from src.verticals.mech_workshop.agents.extraction_questionnaire import (
    QuestionnaireAgent,
    QuestionnaireAnswers,
    WorkshopSpec,
)
from src.verticals.mech_workshop.agents.soft_constraints_nl import (
    SoftConstraint,
    SoftConstraintCategory,
    SoftConstraintsAgent,
    SoftConstraintsOutput,
    UnrecognizedConstraint,
)

__all__ = [
    "AnomalyItem",
    "CSVExtractionAgent",
    "CSVExtractionOutput",
    "ConversationalEditAgent",
    "EditAction",
    "EditActionKind",
    "EditPlan",
    "ExplanationAgent",
    "ExplanationKind",
    "ExplanationOutput",
    "ExtractedMachine",
    "ExtractedOperation",
    "ExtractedOrder",
    "QuestionnaireAgent",
    "QuestionnaireAnswers",
    "SoftConstraint",
    "SoftConstraintCategory",
    "SoftConstraintsAgent",
    "SoftConstraintsOutput",
    "UnrecognizedConstraint",
    "WorkshopSpec",
]
