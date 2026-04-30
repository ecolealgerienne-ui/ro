"""Tests du module pre-flight.

Couvre :
- Mapping colonnes (heuristique regex)
- Détection séparateur CSV (`;`, `,`, `\\t`)
- Détection encoding (UTF-8, latin-1)
- Parsing dates multi-format → ISO
- Validation durations (entiers, négatifs, zéro, non-int)
- Champs requis vides
- Colonnes requises manquantes
- Détection doublons exacts
- Routage `should_call_llm` (bloquant / warning-only / majoritairement invalide)
"""

from __future__ import annotations

from datetime import date

import pytest

from src.preflight import (
    PreflightErrorType,
    Severity,
    run_preflight,
)


TODAY = date(2026, 4, 30)


# ---------- Cas propre baseline ----------


SIMPLE_CSV = """\
NO_OF;REF_CLIENT;DESIG_PIECE;MATERIAU;OPERATION_DESC;POSTE_TRAVAIL;TPS_OP_MIN;DATE_LIV
2026-001;Safran;Bague_pivot;Aluminium 7075;Tournage ebauche;TOUR-01;45;2026-05-15
2026-001;Safran;Bague_pivot;Aluminium 7075;Tournage finition;TOUR-01;30;2026-05-15
2026-002;PSA;Plaque;Acier 42CrMo4;Fraisage ebauche;FRAIS-02;55;2026-05-12
"""


def test_simple_csv_parses_cleanly() -> None:
    report = run_preflight(SIMPLE_CSV, today=TODAY)
    assert report.csv_parseable
    assert report.detected_separator == ";"
    assert report.rows_parsed == 3
    assert len(report.cleaned_rows) == 3
    assert report.blocking_count == 0
    assert report.warning_count == 0


def test_simple_csv_should_call_llm() -> None:
    report = run_preflight(SIMPLE_CSV, today=TODAY)
    should, reason = report.should_call_llm()
    assert should
    assert reason == "OK"


def test_simple_csv_column_mapping() -> None:
    report = run_preflight(SIMPLE_CSV, today=TODAY)
    assert report.column_mapping_suggested["NO_OF"] == "order_id"
    assert report.column_mapping_suggested["REF_CLIENT"] == "client"
    assert report.column_mapping_suggested["DESIG_PIECE"] == "piece_name"
    assert report.column_mapping_suggested["MATERIAU"] == "material"
    assert report.column_mapping_suggested["OPERATION_DESC"] == "operation_type"
    assert report.column_mapping_suggested["POSTE_TRAVAIL"] == "machine"
    assert report.column_mapping_suggested["TPS_OP_MIN"] == "duration_min"
    assert report.column_mapping_suggested["DATE_LIV"] == "deadline"


# ---------- Détection séparateur ----------


def test_detect_comma_separator() -> None:
    csv_comma = "OF,Client,Duree_min,Date_livraison\nOF1,Safran,30,2026-05-15"
    report = run_preflight(csv_comma, today=TODAY)
    assert report.csv_parseable
    assert report.detected_separator == ","


def test_detect_tab_separator() -> None:
    csv_tab = "OF\tClient\tDuree_min\tDate_livraison\nOF1\tSafran\t30\t2026-05-15"
    report = run_preflight(csv_tab, today=TODAY)
    assert report.csv_parseable
    assert report.detected_separator == "\t"


def test_no_separator_detected() -> None:
    """Une seule colonne sans séparateur courant → bloquant."""
    csv_bad = "single_column_with_no_separator\nvalue1\nvalue2"
    report = run_preflight(csv_bad, today=TODAY)
    assert not report.csv_parseable or len(report.cleaned_rows) == 0
    # On accepte deux comportements : soit séparateur non détecté, soit colonne requise manquante
    assert any(
        e.type
        in (
            PreflightErrorType.CSV_UNPARSEABLE,
            PreflightErrorType.COLUMN_REQUIRED_MISSING,
        )
        for e in report.errors
    )


# ---------- Mapping colonnes ----------


def test_column_mapping_handles_french_simple() -> None:
    csv = "OF;Client;Duree_min;Date_livraison\nOF1;Safran;30;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert report.column_mapping_suggested.get("OF") == "order_id"
    assert report.column_mapping_suggested.get("Duree_min") == "duration_min"


def test_required_column_missing_blocks() -> None:
    """Pas de colonne mappable vers `duration_min` → bloquant global."""
    csv = "OF;Client;Date_livraison\nOF1;Safran;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert report.csv_parseable
    assert report.has_blocking_errors
    assert any(
        e.type == PreflightErrorType.COLUMN_REQUIRED_MISSING for e in report.errors
    )
    should, reason = report.should_call_llm()
    assert not should
    assert "duration_min" in reason or "Erreur globale" in reason


# ---------- Validation durations ----------


def test_duration_negative_is_warning_not_blocking() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;-30;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert report.csv_parseable
    assert len(report.cleaned_rows) == 1  # ligne préservée
    warnings = [
        e for e in report.errors if e.type == PreflightErrorType.DURATION_NEGATIVE_OR_ZERO
    ]
    assert len(warnings) == 1
    assert warnings[0].severity == Severity.WARNING
    assert warnings[0].raw_value == "-30"


def test_duration_zero_is_warning() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;0;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 1
    warnings = [
        e for e in report.errors if e.type == PreflightErrorType.DURATION_NEGATIVE_OR_ZERO
    ]
    assert len(warnings) == 1


def test_duration_not_int_is_blocking() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;abc;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 0
    blocking = [e for e in report.errors if e.type == PreflightErrorType.DURATION_NOT_INT]
    assert len(blocking) == 1
    assert blocking[0].severity == Severity.BLOCKING


def test_duration_decimal_with_comma_parses() -> None:
    """Permettre les "30,0" comme entier 30."""
    csv = "OF;Duree_min;Date_livraison\nOF1;30,0;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 1


def test_duration_decimal_non_integer_is_blocking() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;30.5;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert any(e.type == PreflightErrorType.DURATION_NOT_INT for e in report.errors)


# ---------- Validation dates ----------


def test_date_iso_kept_as_is() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;30;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert report.cleaned_rows[0].cells["Date_livraison"] == "2026-05-15"


def test_date_dd_mm_yyyy_converted_to_iso() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;30;15/05/2026"
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 1
    assert report.cleaned_rows[0].cells["Date_livraison"] == "2026-05-15"


def test_date_yyyy_slash_mm_slash_dd_converted() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;30;2026/05/15"
    report = run_preflight(csv, today=TODAY)
    assert report.cleaned_rows[0].cells["Date_livraison"] == "2026-05-15"


def test_date_in_past_is_warning() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;30;2025-01-01"
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 1  # ligne préservée
    warnings = [e for e in report.errors if e.type == PreflightErrorType.DATE_IN_PAST]
    assert len(warnings) == 1
    assert warnings[0].severity == Severity.WARNING


def test_date_unparseable_is_blocking() -> None:
    csv = "OF;Duree_min;Date_livraison\nOF1;30;not-a-date"
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 0
    blocking = [e for e in report.errors if e.type == PreflightErrorType.DATE_UNPARSEABLE]
    assert len(blocking) == 1


# ---------- Champs requis ----------


def test_empty_required_field_is_blocking() -> None:
    csv = "OF;Duree_min;Date_livraison\n;30;2026-05-15"
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 0
    assert any(
        e.type == PreflightErrorType.REQUIRED_FIELD_EMPTY
        and e.severity == Severity.BLOCKING
        for e in report.errors
    )


# ---------- Doublons exacts ----------


def test_exact_duplicate_detected_as_warning() -> None:
    csv = """\
OF;Duree_min;Date_livraison
OF1;30;2026-05-15
OF1;30;2026-05-15
"""
    report = run_preflight(csv, today=TODAY)
    assert len(report.cleaned_rows) == 2
    duplicates = [
        e for e in report.errors if e.type == PreflightErrorType.OF_DUPLICATE_EXACT
    ]
    assert len(duplicates) == 1
    assert duplicates[0].severity == Severity.WARNING


def test_non_exact_doublon_not_flagged() -> None:
    """OF identique mais valeurs différentes : pas un doublon exact."""
    csv = """\
OF;Duree_min;Date_livraison
OF1;30;2026-05-15
OF1;25;2026-05-15
"""
    report = run_preflight(csv, today=TODAY)
    duplicates = [
        e for e in report.errors if e.type == PreflightErrorType.OF_DUPLICATE_EXACT
    ]
    assert len(duplicates) == 0


# ---------- Routage should_call_llm ----------


def test_should_call_llm_blocks_on_majority_invalid() -> None:
    """Plus de 50% des lignes invalides → bloquant."""
    csv = """\
OF;Duree_min;Date_livraison
OF1;abc;2026-05-15
OF2;def;2026-05-15
OF3;30;2026-05-15
"""
    report = run_preflight(csv, today=TODAY)
    should, reason = report.should_call_llm()
    assert not should
    assert "50%" in reason or "invalides" in reason


def test_should_call_llm_passes_on_warnings_only() -> None:
    """Que des warnings → on continue vers le LLM."""
    csv = """\
OF;Duree_min;Date_livraison
OF1;-30;2026-05-15
OF2;30;2025-01-01
OF3;30;2026-05-15
"""
    report = run_preflight(csv, today=TODAY)
    should, reason = report.should_call_llm()
    assert should
    assert reason == "OK"
    assert report.warning_count == 2


# ---------- Cas plus réalistes (proches des fixtures) ----------


def test_f3_like_chaotic_format() -> None:
    """Reprend la structure de fixture_03 mais en mini : colonnes ERP techniques + DD/MM/YYYY."""
    csv = """\
NO_OF;REF_CLIENT;DESIG_PIECE;MATERIAU;OPERATION_DESC;POSTE_TRAVAIL;TPS_OP_MIN;DATE_LIV;PRIORITE
2026-201;CLI-AERO-A;Bague_v2;Aluminium 7075-T6;Tournage Ebauche CN;TOUR-01;55;15/05/2026;1
2026-201;CLI-AERO-A;Bague_v2;Aluminium 7075-T6;Tournage Finition;TOUR-01;35;15/05/2026;1
2026-202;CLI-AUTO-B;Plaque;42 CrMo 4;Fraisage ebauche;FRAIS-02;65;12/05/2026;2
"""
    report = run_preflight(csv, today=TODAY)
    assert report.csv_parseable
    assert report.blocking_count == 0
    assert report.warning_count == 0
    assert len(report.cleaned_rows) == 3
    # Date convertie
    assert report.cleaned_rows[0].cells["DATE_LIV"] == "2026-05-15"
    # PRIORITE non mappée à un canonique → laissé tel quel mais pas dans le mapping
    assert "PRIORITE" not in report.column_mapping_suggested


def test_f4_like_with_real_anomalies() -> None:
    """Reprend la structure de fixture_04 : mix anomalies + cas propres."""
    csv = """\
OF;Duree_min;Date_livraison
OF-100;30;2026-05-15
OF-101;-30;2026-05-12
OF-102;0;2026-05-18
OF-104;30;2025-01-01
"""
    report = run_preflight(csv, today=TODAY)
    assert report.csv_parseable
    # 4 lignes parsées, toutes en cleaned_rows (durée négative et zéro = warning, pas bloquant)
    assert report.rows_parsed == 4
    assert len(report.cleaned_rows) == 4
    assert report.blocking_count == 0
    # 3 warnings : -30, 0, date passée
    types = {e.type for e in report.errors}
    assert PreflightErrorType.DURATION_NEGATIVE_OR_ZERO in types
    assert PreflightErrorType.DATE_IN_PAST in types
