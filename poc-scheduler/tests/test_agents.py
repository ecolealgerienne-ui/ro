"""Tests des 5 agents Phase 3 avec FakeLLMProvider.

Couvre, pour chaque agent :
- rendering du prompt (substitution des variables OK)
- parsing + validation Pydantic d'une reponse canned valide
- erreur si reponse non-JSON
- erreur si reponse JSON ne respectant pas le schema
- contraintes specifiques au schema (validators metier)

Ne hit PAS l'API Claude. Tous les tests sont deterministes via FakeLLMProvider.
Tests live API (avec ANTHROPIC_API_KEY) marques separement avec
@pytest.mark.live_api (skipped en CI sauf var d'env).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.llm import FakeLLMProvider, LLMParseError
from src.preflight import CleanedRow, PreflightReport
from src.verticals.mech_workshop.agents import (
    ConversationalEditAgent,
    CSVExtractionAgent,
    EditPlan,
    ExplanationAgent,
    ExplanationOutput,
    QuestionnaireAgent,
    SoftConstraintsAgent,
    SoftConstraintsOutput,
    WorkshopSpec,
)
from src.verticals.mech_workshop.agents.extraction_csv import CSVExtractionOutput

# ---------- 3.4 — extraction questionnaire ----------


def test_questionnaire_agent_parses_valid_response() -> None:
    canned = json.dumps(
        {
            "workshop_name": "Atelier Demo",
            "n_machines_estimated": 12,
            "n_operators_estimated": 18,
            "machine_types": ["tour_cn", "fraiseuse"],
            "main_certifications": ["aero", "iso9001"],
            "main_materials": ["aluminium", "titane"],
            "shift_pattern": "2x8",
            "has_shared_resources": True,
            "shared_resources_kinds": ["aspiration"],
            "typical_order_size_pieces": 50,
            "typical_lead_time_days": 21,
            "notes": "Pilote design partner aero.",
        }
    )
    provider = FakeLLMProvider(responses=[f"```json\n{canned}\n```"])
    agent = QuestionnaireAgent.from_default_prompt(provider)
    out = agent.run(answers={"size": "10-50", "certif": "aero"}).parsed
    assert isinstance(out, WorkshopSpec)
    assert out.workshop_name == "Atelier Demo"
    assert out.shift_pattern == "2x8"


def test_questionnaire_agent_renders_answers_in_prompt() -> None:
    provider = FakeLLMProvider(responses=["{}"])
    agent = QuestionnaireAgent.from_default_prompt(provider)
    rendered = agent.render_prompt(answers={"machines_count": 12, "certif": "aero"})
    assert "machines_count" in rendered
    assert "12" in rendered
    assert "aero" in rendered
    assert "{{ANSWERS_JSON}}" not in rendered


def test_questionnaire_agent_rejects_invalid_inputs() -> None:
    provider = FakeLLMProvider(responses=["{}"])
    agent = QuestionnaireAgent.from_default_prompt(provider)
    with pytest.raises(ValueError, match=r"answers"):
        agent.run()


# ---------- 3.5 — extraction CSV ----------


def _minimal_preflight_report() -> PreflightReport:
    return PreflightReport(
        csv_parseable=True,
        detected_separator=";",
        detected_encoding="utf-8",
        column_mapping_suggested={"OF": "order_id", "Duree_min": "duration_min"},
        rows_parsed=1,
        cleaned_rows=[
            CleanedRow(raw_index=0, cells={"OF": "OF-001", "Duree_min": "30"}),
        ],
        errors=[],
    )


def test_csv_extraction_agent_parses_valid_response() -> None:
    canned = json.dumps(
        {
            "machines": [{"name": "TOUR-01", "type_inferred": "tour"}],
            "orders": [
                {
                    "order_id": "OF-001",
                    "client": "Safran",
                    "piece_name": "Bague",
                    "material_normalized": "aluminium_7075",
                    "deadline": "2026-06-01",
                    "operations": [
                        {
                            "sequence_idx": 0,
                            "operation_type": "tournage",
                            "machine": "TOUR-01",
                            "duration_min": 30,
                        }
                    ],
                }
            ],
            "anomalies": [],
        }
    )
    provider = FakeLLMProvider(responses=[f"```json\n{canned}\n```"])
    agent = CSVExtractionAgent.from_default_prompt(provider)
    out = agent.run(preflight_report=_minimal_preflight_report()).parsed
    assert isinstance(out, CSVExtractionOutput)
    assert out.machines[0].name == "TOUR-01"
    assert out.orders[0].operations[0].duration_min == 30


def test_csv_extraction_agent_substitutes_preflight_data() -> None:
    provider = FakeLLMProvider(responses=["{}"])
    agent = CSVExtractionAgent.from_default_prompt(provider)
    rendered = agent.render_prompt(preflight_report=_minimal_preflight_report())
    assert "OF-001" in rendered  # cleaned_row content
    assert "order_id" in rendered  # column mapping
    assert "{{CSV}}" not in rendered
    assert "{{COLUMN_MAPPING}}" not in rendered


def test_csv_extraction_agent_rejects_non_preflight_input() -> None:
    provider = FakeLLMProvider(responses=["{}"])
    agent = CSVExtractionAgent.from_default_prompt(provider)
    with pytest.raises(ValueError, match=r"preflight_report"):
        agent.run(preflight_report={"not": "a real report"})


# ---------- 3.6 — soft constraints NL ----------


def test_soft_constraints_agent_parses_valid_response() -> None:
    canned = json.dumps(
        {
            "soft_constraints": [
                {
                    "natural_language": "On evite la nuit sur M3",
                    "category": "avoid_machine_during_period",
                    "parameters": {"machine_reference": "M3", "period_type": "night"},
                    "weight_hint": 0.5,
                    "weight_rationale": "« on evite » = preference moderee",
                    "confidence": "medium",
                }
            ],
            "unrecognized": [],
        }
    )
    provider = FakeLLMProvider(responses=[canned])
    agent = SoftConstraintsAgent.from_default_prompt(provider)
    out = agent.run(phrases=["On evite la nuit sur M3"]).parsed
    assert isinstance(out, SoftConstraintsOutput)
    assert len(out.soft_constraints) == 1
    assert out.soft_constraints[0].weight_hint == 0.5
    assert out.soft_constraints[0].category == "avoid_machine_during_period"


def test_soft_constraints_agent_rejects_empty_phrases() -> None:
    provider = FakeLLMProvider(responses=["{}"])
    agent = SoftConstraintsAgent.from_default_prompt(provider)
    with pytest.raises(ValueError, match=r"vide"):
        agent.run(phrases=[])


def test_soft_constraints_agent_rejects_invalid_category() -> None:
    canned = json.dumps(
        {
            "soft_constraints": [
                {
                    "natural_language": "x",
                    "category": "invalid_category_not_in_enum",
                    "parameters": {},
                    "weight_hint": 0.5,
                    "weight_rationale": "y",
                    "confidence": "low",
                }
            ],
            "unrecognized": [],
        }
    )
    provider = FakeLLMProvider(responses=[canned])
    agent = SoftConstraintsAgent.from_default_prompt(provider)
    with pytest.raises(ValidationError):
        agent.run(phrases=["test"])


def test_soft_constraints_agent_handles_unrecognized() -> None:
    canned = json.dumps(
        {
            "soft_constraints": [],
            "unrecognized": [
                {
                    "natural_language": "phrase ambigue",
                    "reason": "Ne mappe a aucune categorie",
                    "suggestion": "Reformuler avec un objet concret",
                }
            ],
        }
    )
    provider = FakeLLMProvider(responses=[canned])
    agent = SoftConstraintsAgent.from_default_prompt(provider)
    out = agent.run(phrases=["phrase ambigue"]).parsed
    assert len(out.unrecognized) == 1


# ---------- 3.7 — explanation ----------


def test_explanation_agent_placement() -> None:
    canned = json.dumps(
        {
            "summary": "L'OF Safran-001 a ete place le 15 mai sur TOUR-01.",
            "reasons": [
                "Seule machine qualifiee pour aluminium 7075",
                "Disponibilite la plus proche de la deadline",
            ],
            "actions_suggested": [],
            "kind": "placement",
        }
    )
    provider = FakeLLMProvider(responses=[f"```json\n{canned}\n```"])
    agent = ExplanationAgent.from_default_prompt(provider)
    out = agent.run(
        kind="placement",
        context={"order_id": "Safran-001", "machine": "TOUR-01", "start": "2026-05-15"},
    ).parsed
    assert isinstance(out, ExplanationOutput)
    assert out.kind == "placement"
    assert len(out.reasons) == 2


def test_explanation_agent_infeasibility() -> None:
    canned = json.dumps(
        {
            "summary": "Pas de planning trouve : la machine FRAIS-02 est saturee.",
            "reasons": ["FRAIS-02 a 100 % de charge sur la semaine demandee"],
            "actions_suggested": [
                "Decaler la livraison de l'OF-007",
                "Sous-traiter a un partenaire",
            ],
            "kind": "infeasibility",
        }
    )
    provider = FakeLLMProvider(responses=[f"```json\n{canned}\n```"])
    agent = ExplanationAgent.from_default_prompt(provider)
    out = agent.run(
        kind="infeasibility",
        context={"mis_summary": "FRAIS-02 capacite epuisee semaine 20"},
    ).parsed
    assert out.kind == "infeasibility"
    assert len(out.actions_suggested) >= 1


def test_explanation_agent_rejects_bad_kind() -> None:
    provider = FakeLLMProvider(responses=["{}"])
    agent = ExplanationAgent.from_default_prompt(provider)
    with pytest.raises(ValueError, match=r"placement.*infeasibility"):
        agent.run(kind="random", context={})


def test_explanation_agent_rejects_too_many_reasons() -> None:
    canned = json.dumps(
        {
            "summary": "X",
            "reasons": ["a", "b", "c", "d", "e", "f"],  # 6 > max 5
            "actions_suggested": [],
            "kind": "placement",
        }
    )
    provider = FakeLLMProvider(responses=[canned])
    agent = ExplanationAgent.from_default_prompt(provider)
    with pytest.raises(ValidationError):
        agent.run(kind="placement", context={"x": 1})


# ---------- 3.8 — conversational edit ----------


def test_conversational_edit_agent_parses_valid_plan() -> None:
    canned = json.dumps(
        {
            "actions": [
                {
                    "kind": "set_client_priority",
                    "target": "Safran",
                    "params": {"priority_level": "high"},
                    "rationale": "Demande explicite de l'utilisateur",
                }
            ],
            "needs_clarification": False,
            "clarification_question": "",
            "user_request_normalized": "Mettre Safran en priorite haute",
        }
    )
    provider = FakeLLMProvider(responses=[f"```json\n{canned}\n```"])
    agent = ConversationalEditAgent.from_default_prompt(provider)
    out = agent.run(
        user_request="priorite 1 sur Safran",
        instance_summary={"clients": ["Safran", "PSA"]},
    ).parsed
    assert isinstance(out, EditPlan)
    assert out.actions[0].kind == "set_client_priority"
    assert not out.needs_clarification


def test_conversational_edit_agent_clarification_path() -> None:
    canned = json.dumps(
        {
            "actions": [],
            "needs_clarification": True,
            "clarification_question": "Quel client cibles-tu (Safran ou PSA) ?",
            "user_request_normalized": "Augmenter priorite (client ambigu)",
        }
    )
    provider = FakeLLMProvider(responses=[canned])
    agent = ConversationalEditAgent.from_default_prompt(provider)
    out = agent.run(user_request="augmente la priorite", instance_summary={"clients": []}).parsed
    assert out.needs_clarification
    assert out.clarification_question.endswith("?")
    assert out.actions == []


def test_conversational_edit_rejects_inconsistent_clarification() -> None:
    """needs_clarification=True mais actions non vides -> validator refuse."""
    canned = json.dumps(
        {
            "actions": [
                {
                    "kind": "other",
                    "target": "x",
                    "params": {},
                    "rationale": "y",
                }
            ],
            "needs_clarification": True,
            "clarification_question": "?",
            "user_request_normalized": "z",
        }
    )
    provider = FakeLLMProvider(responses=[canned])
    agent = ConversationalEditAgent.from_default_prompt(provider)
    with pytest.raises(ValidationError):
        agent.run(user_request="x", instance_summary={})


def test_conversational_edit_rejects_empty_plan() -> None:
    canned = json.dumps(
        {
            "actions": [],
            "needs_clarification": False,
            "clarification_question": "",
            "user_request_normalized": "x",
        }
    )
    provider = FakeLLMProvider(responses=[canned])
    agent = ConversationalEditAgent.from_default_prompt(provider)
    with pytest.raises(ValidationError):
        agent.run(user_request="x", instance_summary={})


# ---------- Generic : LLMParseError propagation ----------


def test_agent_propagates_parse_error_on_garbage_response() -> None:
    provider = FakeLLMProvider(responses=["this is not JSON at all, total prose"])
    agent = SoftConstraintsAgent.from_default_prompt(provider)
    with pytest.raises(LLMParseError):
        agent.run(phrases=["test"])
