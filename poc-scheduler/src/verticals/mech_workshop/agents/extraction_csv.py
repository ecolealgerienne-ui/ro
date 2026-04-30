"""Agent 3.5 — extraction Excel/CSV ERP -> JSON workshop avec pre-flight.

Cet agent prend en entree un `PreflightReport` (deja produit par le module
`src.preflight`) et appelle Claude pour extraire :
- la liste des machines (avec type infere)
- la liste des OF (orders) avec leurs operations
- les anomalies semantiques (Niveau 2/3 spec V3 §3) que le pre-flight ne
  pouvait pas detecter (conflits inter-lignes, materiaux inconnus, etc.)

Le prompt v1 = `prompt_v3.md` valide empiriquement (15/15 sur fixture_04
+ pre-flight, ~33% prompt reduction vs v2). Reutilise tel quel.

Statut prompt : **valide empiriquement** (45/45 sur 3 fixtures, 15/15 sur F4
avec pre-flight).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agents.base import Agent
from src.preflight import PreflightReport, Severity

PROMPT_PATH: Final[Path] = Path(__file__).parent.parent / "prompts" / "extraction_csv_v1.md"
SCHEMA_PATH: Final[Path] = (
    Path(__file__).parent.parent / "prompts" / "extraction_csv_target_schema_v1.md"
)

MachineType = Literal[
    "tour",
    "fraiseuse",
    "centre_usinage",
    "rectifieuse",
    "perceuse",
    "machine_controle",
    "autre",
]


class ExtractedMachine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    type_inferred: MachineType


class ExtractedOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    sequence_idx: int = Field(..., ge=0)
    operation_type: str
    machine: str
    duration_min: int = Field(..., ge=0)


class ExtractedOrder(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    order_id: str
    client: str
    piece_name: str
    material_normalized: str
    deadline: str | None = None  # ISO YYYY-MM-DD
    operations: list[ExtractedOperation]


class AnomalyItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    type: str
    row_reference: str
    raw_value: str = ""
    description: str


class CSVExtractionOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    machines: list[ExtractedMachine]
    orders: list[ExtractedOrder]
    anomalies: list[AnomalyItem] = Field(default_factory=list)


class CSVExtractionAgent(Agent):
    """Agent extraction Excel/CSV ERP -> JSON workshop (post pre-flight)."""

    name: ClassVar[str] = "extraction_csv"
    output_schema: ClassVar[type[BaseModel]] = CSVExtractionOutput

    @classmethod
    def from_default_prompt(cls, provider: object) -> CSVExtractionAgent:
        return cls(provider=provider, prompt_template=PROMPT_PATH.read_text(encoding="utf-8"))  # type: ignore[arg-type]

    def render_prompt(self, **inputs: object) -> str:
        report = inputs.get("preflight_report")
        if not isinstance(report, PreflightReport):
            raise ValueError(f"{self.name} : input 'preflight_report' (PreflightReport) manquant")
        schema = self._load_schema_text()
        cleaned_csv = self._build_cleaned_csv(report)
        column_mapping_md = self._format_mapping(report.column_mapping_suggested)
        anomalies_md = self._format_warning_anomalies(report)

        prompt = self.prompt_template
        prompt = prompt.replace("{{SCHEMA}}", schema)
        prompt = prompt.replace("{{SEPARATOR}}", report.detected_separator or "?")
        prompt = prompt.replace("{{ENCODING}}", report.detected_encoding or "?")
        prompt = prompt.replace("{{COLUMN_MAPPING}}", column_mapping_md)
        prompt = prompt.replace("{{PREFLIGHT_ANOMALIES}}", anomalies_md)
        prompt = prompt.replace("{{TODAY}}", inputs.get("today_iso", "") or "")  # type: ignore[arg-type]
        prompt = prompt.replace("{{CSV}}", cleaned_csv)
        return prompt

    @staticmethod
    def _load_schema_text() -> str:
        if SCHEMA_PATH.exists():
            return SCHEMA_PATH.read_text(encoding="utf-8")
        # Fallback : schema brut en commentaire
        return "(target schema embedded inline in template)"

    @staticmethod
    def _format_mapping(mapping: Mapping[str, str]) -> str:
        if not mapping:
            return "_(aucun mapping detecte)_"
        lines = ["| Source | Canonique |", "|--------|-----------|"]
        lines.extend(f"| `{src}` | `{canon}` |" for src, canon in sorted(mapping.items()))
        return "\n".join(lines)

    @staticmethod
    def _format_warning_anomalies(report: PreflightReport) -> str:
        items = []
        for err in report.errors:
            if err.severity is not Severity.WARNING:
                continue
            items.append(
                {
                    "type": err.type.value,
                    "row_reference": (
                        f"ligne {err.row_index}" if err.row_index is not None else "global"
                    ),
                    "raw_value": err.raw_value or "",
                    "description": err.description,
                }
            )
        return json.dumps(items, ensure_ascii=False, indent=2)

    @staticmethod
    def _build_cleaned_csv(report: PreflightReport) -> str:
        if not report.cleaned_rows:
            return ""
        headers: Sequence[str] = list(report.cleaned_rows[0].cells.keys())
        sep = report.detected_separator or ";"
        lines = [sep.join(headers)]
        for row in report.cleaned_rows:
            lines.append(sep.join(row.cells.get(h, "") for h in headers))
        return "\n".join(lines)
