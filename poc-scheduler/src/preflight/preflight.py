"""Logique principale du module pre-flight.

Voir `__init__.py` pour le contexte général.
Voir `experiments/llm-extraction/preflight-design.md` pour le design détaillé.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Final

from src.preflight.models import (
    CleanedRow,
    PreflightError,
    PreflightErrorType,
    PreflightReport,
    Severity,
)

_logger = logging.getLogger(__name__)


# ---------- Constantes ----------


# Champs canoniques attendus dans la sortie finale (post-LLM).
# Ils servent de cibles au mapping heuristique pre-flight.
CANONICAL_FIELDS: Final[tuple[str, ...]] = (
    "order_id",
    "client",
    "piece_name",
    "material",
    "operation_type",
    "machine",
    "duration_min",
    "deadline",
)

# Champs canoniques sans lesquels le pre-flight ne peut pas continuer.
REQUIRED_CANONICAL_FIELDS: Final[frozenset[str]] = frozenset({"order_id", "duration_min"})

# Patterns regex (insensibles à la casse) par champ canonique.
# Ordre interne : spécifique → générique.
COLUMN_PATTERNS: Final[dict[str, tuple[str, ...]]] = {
    "order_id": (
        r"^no_of$",
        r"^num_of$",
        r"^of$",
        r"^order_?id$",
        r"^reference_of$",
        r"^numero(_of)?$",
    ),
    "client": (
        r"^ref_client$",
        r"^client$",
        r"^customer$",
        r"^donneur(_d_ordre)?$",
    ),
    "piece_name": (
        r"^desig(_piece)?$",
        r"^designation$",
        r"^piece(_name)?$",
        r"^part_?name$",
        r"^libelle_piece$",
    ),
    "material": (
        r"^materi(au|al)$",
        r"^matiere$",
        r"^mat(_ref)?$",
    ),
    "operation_type": (
        r"^operation(_desc)?$",
        r"^op_desc$",
        r"^op_libelle$",
        r"^operation_type$",
    ),
    "machine": (
        r"^poste(_travail)?$",
        r"^machine$",
        r"^workstation$",
        r"^ressource$",
    ),
    "duration_min": (
        r"^duree(_min|_op)?$",
        r"^tps_op(_min)?$",
        r"^temps(_op)?$",
        r"^duration(_min)?$",
    ),
    "deadline": (
        r"^date_liv(raison)?$",
        r"^deadline$",
        r"^echeance$",
        r"^date_due$",
    ),
}

# Formats de date acceptés (par ordre de tentative).
# Le dernier (US) est essayé en dernier pour éviter d'interpréter 03/04 comme avril plutôt que mars.
DATE_FORMATS: Final[tuple[str, ...]] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%m/%d/%Y",
)

# Encodings tentés en cascade quand on lit un fichier sans connaissance préalable.
ENCODINGS_FALLBACK: Final[tuple[str, ...]] = ("utf-8-sig", "utf-8", "latin-1", "cp1252")

# Séparateurs CSV courants pour détection automatique.
CANDIDATE_SEPARATORS: Final[tuple[str, ...]] = (";", ",", "\t", "|")


# ---------- Détection format ----------


def _detect_encoding(raw_bytes: bytes) -> tuple[str, bool]:
    """Tente plusieurs encodings, retourne (encoding_retenu, mismatch_detected).

    `mismatch_detected = True` signale qu'un encoding non-utf8 a dû être utilisé,
    indiquant des caractères potentiellement perdus.
    """
    for enc in ENCODINGS_FALLBACK:
        try:
            raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
        else:
            return enc, enc not in ("utf-8-sig", "utf-8")
    return "latin-1", True


def _detect_separator(content: str) -> str | None:
    """Détecte le séparateur CSV en comptant les occurrences sur la première ligne.

    Le séparateur retenu est celui qui apparaît le plus de fois sur la première
    ligne ET aussi (cohérent) sur la deuxième ligne. Si aucun candidat ne marche
    de façon stable, retourne None.
    """
    lines = content.splitlines()
    if len(lines) < 2:
        # Pas assez de lignes pour vérifier la cohérence ; tente le plus fréquent
        if not lines:
            return None
        first = lines[0]
        counts = {sep: first.count(sep) for sep in CANDIDATE_SEPARATORS}
        best = max(counts, key=lambda s: counts[s])
        return best if counts[best] >= 1 else None

    first, second = lines[0], lines[1]
    candidates: list[tuple[str, int]] = []
    for sep in CANDIDATE_SEPARATORS:
        c1 = first.count(sep)
        c2 = second.count(sep)
        if c1 >= 1 and c1 == c2:
            candidates.append((sep, c1))
    if not candidates:
        # Fallback : le plus fréquent en ligne 1
        counts = {sep: first.count(sep) for sep in CANDIDATE_SEPARATORS}
        best = max(counts, key=lambda s: counts[s])
        return best if counts[best] >= 1 else None
    # Choisit le candidat avec le plus d'occurrences (probablement le bon).
    candidates.sort(key=lambda x: -x[1])
    return candidates[0][0]


# ---------- Mapping colonnes ----------


def _suggest_column_mapping(headers: Sequence[str]) -> dict[str, str]:
    """Heuristique regex pour mapper les colonnes source vers les champs canoniques.

    Retourne uniquement les mappings sans ambiguïté. Si une colonne source matche
    plusieurs cibles, ou plusieurs sources matchent une même cible, l'ambiguïté
    est laissée au LLM (champs non inclus).
    """
    matches: dict[str, list[str]] = {}  # source_header → [canonical_targets]
    for header in headers:
        normalized = header.strip().lower().replace(" ", "_")
        targets: list[str] = []
        for canonical, patterns in COLUMN_PATTERNS.items():
            if any(re.fullmatch(p, normalized) for p in patterns):
                targets.append(canonical)
        if targets:
            matches[header] = targets

    # Inverse : canonical → [source_headers]
    reverse: dict[str, list[str]] = {}
    for source, targets in matches.items():
        for tgt in targets:
            reverse.setdefault(tgt, []).append(source)

    mapping: dict[str, str] = {}
    for source, targets in matches.items():
        if len(targets) == 1 and len(reverse[targets[0]]) == 1:
            mapping[source] = targets[0]
    return mapping


# ---------- Validation lignes ----------


def _parse_int_strict(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        # tente float puis cast
        try:
            f = float(value.replace(",", "."))
        except ValueError:
            return None
        if f != int(f):
            return None
        return int(f)


def _parse_date_iso(value: str) -> str | None:
    """Tente de convertir une chaîne en date ISO `YYYY-MM-DD`.

    Returns None si aucun format ne match.
    """
    value = value.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            d = datetime.strptime(value, fmt).date()
        except ValueError:
            continue
        else:
            return d.isoformat()
    return None


def _validate_row(
    row_index: int,
    raw_row: dict[str, str],
    column_mapping: dict[str, str],
    today: date,
) -> tuple[CleanedRow | None, list[PreflightError]]:
    """Valide une ligne et retourne soit la ligne nettoyée + warnings, soit None + erreurs."""
    errors: list[PreflightError] = []
    cleaned_cells: dict[str, str] = {}
    is_blocking = False

    inverse_mapping = {v: k for k, v in column_mapping.items()}

    for canonical in REQUIRED_CANONICAL_FIELDS:
        source = inverse_mapping.get(canonical)
        if source is None:
            # Erreur globale traitée ailleurs ; ici on ne peut juste pas valider.
            continue
        value = (raw_row.get(source) or "").strip()
        if not value:
            errors.append(
                PreflightError(
                    type=PreflightErrorType.REQUIRED_FIELD_EMPTY,
                    severity=Severity.BLOCKING,
                    row_index=row_index,
                    column=source,
                    raw_value=value,
                    description=f"Champ requis '{canonical}' (colonne '{source}') vide",
                )
            )
            is_blocking = True

    # Validation durée si colonne mappée
    duration_source = inverse_mapping.get("duration_min")
    if duration_source is not None:
        raw_duration = (raw_row.get(duration_source) or "").strip()
        if raw_duration:
            parsed = _parse_int_strict(raw_duration)
            if parsed is None:
                errors.append(
                    PreflightError(
                        type=PreflightErrorType.DURATION_NOT_INT,
                        severity=Severity.BLOCKING,
                        row_index=row_index,
                        column=duration_source,
                        raw_value=raw_duration,
                        description=f"Durée '{raw_duration}' ne parse pas en entier",
                    )
                )
                is_blocking = True
            elif parsed <= 0:
                # Anomalie WARNING : durée préservée pour contexte LLM
                errors.append(
                    PreflightError(
                        type=PreflightErrorType.DURATION_NEGATIVE_OR_ZERO,
                        severity=Severity.WARNING,
                        row_index=row_index,
                        column=duration_source,
                        raw_value=raw_duration,
                        description=f"Durée {parsed} ≤ 0",
                    )
                )

    # Validation date si colonne mappée
    deadline_source = inverse_mapping.get("deadline")
    if deadline_source is not None:
        raw_deadline = (raw_row.get(deadline_source) or "").strip()
        if raw_deadline:
            parsed_date = _parse_date_iso(raw_deadline)
            if parsed_date is None:
                errors.append(
                    PreflightError(
                        type=PreflightErrorType.DATE_UNPARSEABLE,
                        severity=Severity.BLOCKING,
                        row_index=row_index,
                        column=deadline_source,
                        raw_value=raw_deadline,
                        description=f"Date '{raw_deadline}' ne match aucun format connu",
                    )
                )
                is_blocking = True
            else:
                # Conversion ISO appliquée
                cleaned_cells[deadline_source] = parsed_date
                # Vérification date passée
                deadline_date = date.fromisoformat(parsed_date)
                if deadline_date < today:
                    errors.append(
                        PreflightError(
                            type=PreflightErrorType.DATE_IN_PAST,
                            severity=Severity.WARNING,
                            row_index=row_index,
                            column=deadline_source,
                            raw_value=raw_deadline,
                            description=f"Deadline {parsed_date} antérieure à la date du jour ({today.isoformat()})",
                        )
                    )

    if is_blocking:
        return None, errors

    # Construction des cellules nettoyées : tout ce qui n'est pas déjà transformé
    # est gardé tel quel.
    for col, val in raw_row.items():
        if col not in cleaned_cells:
            cleaned_cells[col] = (val or "").strip()

    return CleanedRow(raw_index=row_index, cells=cleaned_cells), errors


# ---------- Détection doublons exacts ----------


def _detect_exact_duplicates(rows: list[CleanedRow]) -> list[PreflightError]:
    """Détecte les paires de lignes identiques sur toutes les colonnes."""
    errors: list[PreflightError] = []
    seen: dict[tuple[tuple[str, str], ...], int] = {}
    for row in rows:
        key = tuple(sorted(row.cells.items()))
        if key in seen:
            errors.append(
                PreflightError(
                    type=PreflightErrorType.OF_DUPLICATE_EXACT,
                    severity=Severity.WARNING,
                    row_index=row.raw_index,
                    description=f"Ligne identique à la ligne {seen[key]} sur toutes les colonnes",
                )
            )
        else:
            seen[key] = row.raw_index
    return errors


# ---------- Entrée principale ----------


def run_preflight(
    content_or_path: str | bytes | Path,
    *,
    today: date | None = None,
) -> PreflightReport:
    """Exécute le pre-flight sur un CSV.

    Args:
        content_or_path: Soit le contenu textuel du CSV, soit `bytes` brut, soit
            un `Path` vers le fichier.
        today: Date de référence pour le check `date_in_past`. Défaut = aujourd'hui.

    Returns:
        `PreflightReport` complet (toujours, même en cas d'erreur globale).
    """
    if today is None:
        today = date.today()

    # 1. Récupération du contenu et détection encoding
    if isinstance(content_or_path, Path):
        try:
            raw_bytes = content_or_path.read_bytes()
        except OSError as e:
            return PreflightReport(
                csv_parseable=False,
                errors=[
                    PreflightError(
                        type=PreflightErrorType.CSV_UNPARSEABLE,
                        severity=Severity.BLOCKING,
                        description=f"Impossible de lire le fichier : {e}",
                    )
                ],
            )
        encoding, mismatch = _detect_encoding(raw_bytes)
        try:
            content = raw_bytes.decode(encoding)
        except UnicodeDecodeError as e:
            return PreflightReport(
                csv_parseable=False,
                detected_encoding=encoding,
                errors=[
                    PreflightError(
                        type=PreflightErrorType.CSV_UNPARSEABLE,
                        severity=Severity.BLOCKING,
                        description=f"Échec de décodage avec {encoding} : {e}",
                    )
                ],
            )
    elif isinstance(content_or_path, bytes):
        encoding, mismatch = _detect_encoding(content_or_path)
        try:
            content = content_or_path.decode(encoding)
        except UnicodeDecodeError as e:
            return PreflightReport(
                csv_parseable=False,
                detected_encoding=encoding,
                errors=[
                    PreflightError(
                        type=PreflightErrorType.CSV_UNPARSEABLE,
                        severity=Severity.BLOCKING,
                        description=f"Échec de décodage avec {encoding} : {e}",
                    )
                ],
            )
    else:
        encoding, mismatch = "utf-8", False
        content = content_or_path

    errors: list[PreflightError] = []
    if mismatch:
        errors.append(
            PreflightError(
                type=PreflightErrorType.ENCODING_MISMATCH,
                severity=Severity.WARNING,
                description=f"Encodage non-UTF-8 utilisé : {encoding}. Risque de caractères corrompus.",
            )
        )

    # 2. Détection séparateur
    separator = _detect_separator(content)
    if separator is None:
        errors.append(
            PreflightError(
                type=PreflightErrorType.CSV_UNPARSEABLE,
                severity=Severity.BLOCKING,
                description="Aucun séparateur CSV détecté (testés : ; , \\t |)",
            )
        )
        return PreflightReport(
            csv_parseable=False,
            detected_encoding=encoding,
            errors=errors,
        )

    # 3. Parsing CSV
    try:
        reader = csv.DictReader(io.StringIO(content), delimiter=separator)
        headers = reader.fieldnames or []
        if not headers:
            errors.append(
                PreflightError(
                    type=PreflightErrorType.CSV_UNPARSEABLE,
                    severity=Severity.BLOCKING,
                    description="Aucun en-tête détecté",
                )
            )
            return PreflightReport(
                csv_parseable=False,
                detected_separator=separator,
                detected_encoding=encoding,
                errors=errors,
            )
        rows_raw = list(reader)
    except csv.Error as e:
        errors.append(
            PreflightError(
                type=PreflightErrorType.CSV_UNPARSEABLE,
                severity=Severity.BLOCKING,
                description=f"Erreur de parsing CSV : {e}",
            )
        )
        return PreflightReport(
            csv_parseable=False,
            detected_separator=separator,
            detected_encoding=encoding,
            errors=errors,
        )

    # 4. Mapping colonnes
    column_mapping = _suggest_column_mapping(headers)
    inverse = {v: k for k, v in column_mapping.items()}
    missing_required = REQUIRED_CANONICAL_FIELDS - set(inverse.keys())
    if missing_required:
        for canonical in sorted(missing_required):
            errors.append(
                PreflightError(
                    type=PreflightErrorType.COLUMN_REQUIRED_MISSING,
                    severity=Severity.BLOCKING,
                    description=(
                        f"Aucune colonne mappée vers '{canonical}'. "
                        f"En-têtes vus : {headers}. "
                        "Ajouter une colonne avec un nom reconnu ou ajuster les patterns."
                    ),
                )
            )
        # On ne valide pas les lignes — il manque trop d'info pour les valider.
        return PreflightReport(
            csv_parseable=True,
            detected_separator=separator,
            detected_encoding=encoding,
            column_mapping_suggested=column_mapping,
            rows_parsed=len(rows_raw),
            errors=errors,
        )

    # 5. Validation ligne par ligne
    cleaned_rows: list[CleanedRow] = []
    for idx, raw_row in enumerate(rows_raw):
        cleaned, row_errors = _validate_row(idx, raw_row, column_mapping, today)
        errors.extend(row_errors)
        if cleaned is not None:
            cleaned_rows.append(cleaned)

    # 6. Détection doublons exacts (sur les lignes ayant passé)
    errors.extend(_detect_exact_duplicates(cleaned_rows))

    return PreflightReport(
        csv_parseable=True,
        detected_separator=separator,
        detected_encoding=encoding,
        column_mapping_suggested=column_mapping,
        rows_parsed=len(rows_raw),
        errors=errors,
        cleaned_rows=cleaned_rows,
    )
