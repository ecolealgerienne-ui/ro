"""Modèles Pydantic du module pre-flight.

Voir `__init__.py` pour le contexte général.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """Sévérité d'une erreur pre-flight.

    - `BLOCKING` : la ligne (ou le fichier) ne peut pas continuer telle quelle ;
      retournée à l'utilisateur, exclue du `cleaned_rows`.
    - `WARNING` : signalée mais la ligne reste exploitable. Sera incluse dans
      les anomalies finales (post-flight) et présentée au LLM pour contextualiser.
    - `INFO` : trace, pas une erreur. Utile pour le journal d'apprentissage.
    """

    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class PreflightErrorType(StrEnum):
    """Catalogue exhaustif des types d'erreurs détectables en pre-flight.

    Aligné avec les anomalies "Niveau 1" de `specs-fonctionnelles-v3.md` §3.
    """

    # Erreurs de fichier (bloquantes au niveau global)
    CSV_UNPARSEABLE = "csv_unparseable"
    ENCODING_MISMATCH = "encoding_mismatch"
    COLUMN_REQUIRED_MISSING = "column_required_missing"

    # Erreurs de ligne (bloquantes pour la ligne)
    DURATION_NOT_INT = "duration_not_int"
    DATE_UNPARSEABLE = "date_unparseable"
    REQUIRED_FIELD_EMPTY = "required_field_empty"

    # Anomalies de ligne (warnings — ligne préservée)
    DURATION_NEGATIVE_OR_ZERO = "duration_negative_or_zero"
    DATE_IN_PAST = "date_in_past"
    OF_DUPLICATE_EXACT = "of_duplicate_exact"


class PreflightError(BaseModel):
    """Une erreur ou anomalie détectée pendant le pre-flight."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: PreflightErrorType
    severity: Severity
    row_index: int | None = Field(
        default=None,
        description="Index 0-indexé de la ligne dans le CSV source (None pour erreurs globales fichier)",
    )
    column: str | None = Field(default=None, description="Colonne concernée si applicable")
    raw_value: str | None = Field(default=None, description="Valeur originale problématique")
    description: str


class CleanedRow(BaseModel):
    """Une ligne ayant passé toutes les validations bloquantes.

    Les valeurs sont **partiellement normalisées** :
    - dates converties en ISO `YYYY-MM-DD`
    - durations en `int`
    - autres champs en strings non modifiés (la normalisation sémantique est
      laissée au LLM)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_index: int = Field(..., ge=0, description="Index 0-indexé dans le CSV source")
    cells: dict[str, str] = Field(
        ...,
        description="Cellules cleaned, clés = noms de colonnes originaux du CSV",
    )


class PreflightReport(BaseModel):
    """Résultat complet d'un pre-flight."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    csv_parseable: bool
    detected_separator: str | None = None
    detected_encoding: str | None = None

    column_mapping_suggested: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping source_column → champ canonique (ex: 'NO_OF' → 'order_id')",
    )

    rows_parsed: int = Field(default=0, ge=0)
    errors: list[PreflightError] = Field(default_factory=list)
    cleaned_rows: list[CleanedRow] = Field(default_factory=list)

    @property
    def has_blocking_errors(self) -> bool:
        return any(e.severity == Severity.BLOCKING for e in self.errors)

    @property
    def blocking_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == Severity.BLOCKING)

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == Severity.WARNING)

    def errors_for_row(self, row_index: int) -> list[PreflightError]:
        return [e for e in self.errors if e.row_index == row_index]

    def should_call_llm(self) -> tuple[bool, str]:
        """Détermine si on doit continuer vers le LLM.

        Ordre de check (du plus structurant au plus granulaire) :
        1. CSV non parsable → on ne peut rien faire
        2. Erreur globale fichier (ex: colonne requise manquante) → message plus informatif
           que "aucune ligne valide", donc traité avant
        3. Aucune ligne nettoyée disponible → cas résiduel
        4. Majorité de lignes invalides → probablement un problème de format global

        Returns:
            (should_continue, reason)
        """
        if not self.csv_parseable:
            return False, "CSV non parsable — corriger l'export ERP"
        # Erreur globale fichier (colonne requise manquante) traitée avant "aucune ligne valide"
        # car le message est plus actionnable pour l'utilisateur.
        global_blocking = [
            e for e in self.errors if e.severity == Severity.BLOCKING and e.row_index is None
        ]
        if global_blocking:
            return False, f"Erreur globale fichier : {global_blocking[0].description}"
        if not self.cleaned_rows:
            return False, "Aucune ligne valide après pre-flight"
        # Si > 50% des lignes parsées sont en erreur bloquante → format probablement faux
        if self.rows_parsed > 0 and self.blocking_count > self.rows_parsed * 0.5:
            return (
                False,
                f"Plus de 50% des lignes invalides ({self.blocking_count}/{self.rows_parsed})",
            )
        return True, "OK"
