"""Loader + exécuteur d'un golden case.

Convention : chaque `.yaml` du dossier `cases/` est un cas indépendant. Le
nom de fichier (sans extension) doit matcher le champ `id` du YAML — vérifié
au chargement.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.core.solver import JSSPSolver, SolverResult
from tests.golden_cases._schema import GoldenCase

CASES_DIR: Path = Path(__file__).parent / "cases"


def discover_case_files() -> list[Path]:
    """Liste triée des fichiers YAML de cas (pour ordre déterministe en CI)."""
    return sorted(CASES_DIR.glob("*.yaml"))


def load_case(yaml_path: Path) -> GoldenCase:
    """Charge un cas depuis un fichier YAML, valide schéma et cohérence id↔nom."""
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(
            f"{yaml_path.name} : racine YAML doit être un mapping, vu {type(raw).__name__}"
        )
    case = GoldenCase.model_validate(raw)
    if case.id != yaml_path.stem:
        raise ValueError(
            f"{yaml_path.name} : id YAML '{case.id}' ne match pas le nom de fichier '{yaml_path.stem}'"
        )
    return case


def run_case(case: GoldenCase) -> SolverResult:
    """Exécute le solver sur l'instance du cas. Marge de 5s sur la limite YAML."""
    solver = JSSPSolver(time_limit_seconds=case.expected.solve_time_s_max + 5.0)
    return solver.solve(case.instance)
