"""Module pre-flight — vérifications déterministes avant appel LLM.

Moteur **vertical-agnostic** : il ne connaît AUCUNE verticale métier. Les
patterns de colonnes et champs canoniques requis sont fournis par la verticale
appelante (ex: `src.verticals.mech_workshop.preflight_config`).

Référentiel : `experiments/llm-extraction/preflight-design.md` (étape A).

Pipeline :
    CSV brut → run_preflight(..., column_patterns, required_canonical_fields)
             → PreflightReport
                ├─ has_blocking_errors → on bloque
                └─ sinon → input pour le LLM (Phase 3.5)

Public API :
    - run_preflight(content_or_path, *, column_patterns,
                    required_canonical_fields, today=None) → PreflightReport
    - PreflightReport (Pydantic, exposé)
    - PreflightError, PreflightErrorType, Severity
    - CleanedRow (lignes ayant passé la validation niveau 1)
    - DATE_FORMATS (formats date acceptés, génériques)

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
from src.preflight.preflight import DATE_FORMATS, run_preflight

__all__ = [
    "DATE_FORMATS",
    "CleanedRow",
    "PreflightError",
    "PreflightErrorType",
    "PreflightReport",
    "Severity",
    "run_preflight",
]
