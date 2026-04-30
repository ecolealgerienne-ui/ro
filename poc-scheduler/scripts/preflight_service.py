"""Mini service HTTP synchrone exposant `src/preflight/run_preflight`.

Phase 4 J5 — bridge backend NestJS -> Python pour le pre-flight CSV. Pas de
DB-as-queue ici : le pre-flight est rapide (parsing + fuzzy match, < 1s pour
500 lignes), un appel HTTP synchrone est suffisant.

Endpoints :
  GET  /health            -> { status: 'ok', version: '...' }
  POST /preflight         -> recoit un CSV multipart, retourne PreflightReport JSON

Usage local :
    uv run uvicorn scripts.preflight_service:app --host 0.0.0.0 --port 8001

Verticalite : ce service utilise la calibration `mech_workshop`
(MECH_COLUMN_PATTERNS + MECH_REQUIRED_CANONICAL_FIELDS) car c'est la verticale
active V1. Une 2e verticale s'ajoutera via un parametre `vertical_kind` dans la
requete (ou un sous-domaine /preflight/{vertical}).
"""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.preflight import run_preflight
from src.verticals.mech_workshop.preflight_config import (
    MECH_COLUMN_PATTERNS,
    MECH_REQUIRED_CANONICAL_FIELDS,
)

app = FastAPI(
    title="ro preflight service",
    version="0.1.0",
    description="Bridge HTTP synchrone vers src/preflight pour le backend NestJS.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/preflight")
async def preflight_endpoint(
    file: UploadFile = File(...),  # noqa: B008 — pattern idiomatique FastAPI
) -> JSONResponse:
    """Execute un pre-flight sur le CSV uploade.

    Args:
        file: fichier CSV uploade en multipart/form-data.

    Returns:
        `PreflightReport` serialise (champs `csv_parseable`, `errors`,
        `cleaned_rows`, `column_mapping_suggested`, etc.).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Fichier vide")

    report = run_preflight(
        raw,
        column_patterns=MECH_COLUMN_PATTERNS,
        required_canonical_fields=MECH_REQUIRED_CANONICAL_FIELDS,
        today=date.today(),
    )
    payload = report.model_dump(mode="json")
    payload["filename"] = file.filename
    return JSONResponse(payload)


__all__ = ["app"]
