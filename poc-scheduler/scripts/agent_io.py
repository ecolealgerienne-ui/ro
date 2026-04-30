"""CLI no-code pour tester les agents Phase 3 sans cle API.

Permet de :
1. Rendre le prompt d'un agent avec des inputs reels (commande `prompt`).
2. Valider une reponse Claude (recuperee manuellement) contre le schema
   Pydantic de l'agent (commande `validate`).

Workflow type :
    # 1. Generer le prompt
    uv run python scripts/agent_io.py prompt soft-constraints \\
        --input experiments/agents-trial/soft_constraints_input.json \\
        --output prompt.txt

    # 2. Coller `prompt.txt` dans claude.ai, sauvegarder la reponse JSON
    #    (le bloc ```json ... ``` ou le JSON brut) dans response.json

    # 3. Valider la reponse
    uv run python scripts/agent_io.py validate soft-constraints \\
        --response response.json

Pour l'agent `extraction-csv`, l'input doit etre un chemin CSV et le script
construit un PreflightReport sous le capot.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import click
from rich.console import Console

from src.llm import FakeLLMProvider, LLMParseError, extract_json_block
from src.preflight import run_preflight
from src.verticals.mech_workshop import (
    MECH_COLUMN_PATTERNS,
    MECH_REQUIRED_CANONICAL_FIELDS,
)
from src.verticals.mech_workshop.agents import (
    ConversationalEditAgent,
    CSVExtractionAgent,
    ExplanationAgent,
    QuestionnaireAgent,
    SoftConstraintsAgent,
)

AGENTS = {
    "questionnaire": QuestionnaireAgent,
    "extraction-csv": CSVExtractionAgent,
    "soft-constraints": SoftConstraintsAgent,
    "explanation": ExplanationAgent,
    "edit": ConversationalEditAgent,
}

console = Console()
stderr = Console(stderr=True)


def _build_agent(name: str):
    cls = AGENTS[name]
    fake = FakeLLMProvider(responses=["unused"])
    return cls.from_default_prompt(fake)


def _render_inputs(agent_name: str, raw: dict) -> dict:
    """Hooks specifiques pour traduire un JSON d'input en kwargs render_prompt."""
    if agent_name == "extraction-csv":
        # Cas special : on prend un chemin CSV et on lance preflight
        csv_path = Path(raw["csv_path"])
        today = date.fromisoformat(raw.get("today", date.today().isoformat()))
        report = run_preflight(
            csv_path,
            column_patterns=MECH_COLUMN_PATTERNS,
            required_canonical_fields=MECH_REQUIRED_CANONICAL_FIELDS,
            today=today,
        )
        if not report.should_call_llm()[0]:
            stderr.print(
                "[red]Pre-flight bloquant — pas d'appel LLM.[/] "
                "Lance `scripts/preflight_check.py` pour le detail."
            )
            sys.exit(1)
        return {"preflight_report": report, "today_iso": today.isoformat()}
    return raw


@click.group()
def cli() -> None:
    """CLI no-code pour les agents Phase 3."""


@cli.command()
@click.argument("agent_name", type=click.Choice(list(AGENTS.keys())))
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Fichier JSON contenant les inputs de l'agent.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Si fourni, ecrit le prompt dans ce fichier ; sinon stdout.",
)
def prompt(agent_name: str, input_path: Path, output_path: Path | None) -> None:
    """Rend le prompt d'un agent avec les inputs fournis. Ne hit PAS l'API."""
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        stderr.print(f"[red]Erreur : {input_path} doit contenir un objet JSON (dict).[/]")
        sys.exit(2)

    agent = _build_agent(agent_name)
    inputs = _render_inputs(agent_name, raw)
    rendered = agent.render_prompt(**inputs)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        stderr.print(
            f"[green]✓[/] Prompt {agent_name} ecrit dans {output_path} "
            f"({len(rendered):,} chars, ~{len(rendered) // 4:,} tokens)."
        )
    else:
        stderr.print(
            f"[dim]Prompt {agent_name} ({len(rendered):,} chars, ~{len(rendered) // 4:,} tokens)[/]"
        )
        click.echo(rendered)


@cli.command()
@click.argument("agent_name", type=click.Choice(list(AGENTS.keys())))
@click.option(
    "--response",
    "response_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Fichier contenant la reponse brute de Claude (texte ou JSON).",
)
def validate(agent_name: str, response_path: Path) -> None:
    """Valide une reponse Claude contre le schema Pydantic de l'agent."""
    raw_text = response_path.read_text(encoding="utf-8")
    cls = AGENTS[agent_name]
    schema_cls = cls.output_schema

    try:
        data = extract_json_block(raw_text)
    except LLMParseError as e:
        stderr.print(f"[red]✗ Pas de JSON parsable dans la reponse :[/] {e}")
        sys.exit(1)

    try:
        parsed = schema_cls.model_validate(data)
    except Exception as e:
        stderr.print(f"[red]✗ Reponse non conforme au schema {schema_cls.__name__} :[/]")
        stderr.print(str(e))
        sys.exit(1)

    console.print(f"[green]✓ Reponse valide[/] (schema {schema_cls.__name__}).")
    console.print()
    console.print(parsed.model_dump_json(indent=2))


if __name__ == "__main__":
    cli()
