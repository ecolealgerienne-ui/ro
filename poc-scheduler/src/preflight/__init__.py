"""Module pre-flight — vérifications déterministes avant appel LLM.

Référentiel : `experiments/llm-extraction/preflight-design.md` (étape A).

Pipeline :
    CSV brut → run_preflight() → PreflightReport
                                    ├─ has_blocking_errors → on bloque
                                    └─ sinon → input pour le LLM (Phase 3.5)

Public API :
    - run_preflight(content_or_path, today=None) → PreflightReport
    - PreflightReport (Pydantic, exposé)
    - PreflightError, PreflightErrorType, Severity
    - CleanedRow (lignes ayant passé la validation niveau 1)

Le pre-flight prend en charge les anomalies "Niveau 1" de la spec V3 §3 :
durées non-entières / négatives / nulles, dates non-parsables / dans le passé,
champs requis manquants, doublons exacts, encoding/séparateur CSV.

Il NE prend PAS en charge :
- normalisation matières / opérations (sémantique → LLM)
- doublons incohérents (sémantique → LLM)
- inférence de type machine pour préfixes inconnus (sémantique → LLM)
"""

from src.preflight.models import (
    CleanedRow,
    PreflightError,
    PreflightErrorType,
    PreflightReport,
    Severity,
)
from src.preflight.preflight import (
    CANONICAL_FIELDS,
    COLUMN_PATTERNS,
    DATE_FORMATS,
    REQUIRED_CANONICAL_FIELDS,
    run_preflight,
)

__all__ = [
    "CANONICAL_FIELDS",
    "COLUMN_PATTERNS",
    "CleanedRow",
    "DATE_FORMATS",
    "PreflightError",
    "PreflightErrorType",
    "PreflightReport",
    "REQUIRED_CANONICAL_FIELDS",
    "Severity",
    "run_preflight",
]
