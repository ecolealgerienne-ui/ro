"""Runner pytest pour la bibliotheque de golden cases (engine-level).

Charge tous les `.yaml` du dossier `tests/golden_cases/cases/`, execute le
solveur sur chaque cas, verifie statut + bornes de makespan + temps de
resolution.

Voir `tests/golden_cases/__init__.py` pour le contexte.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.golden_cases._runner import discover_case_files, load_case, run_case

CASE_FILES: list[Path] = discover_case_files()


def test_at_least_one_case_present() -> None:
    """Garde-fou : refuse de passer en vert si la bibliotheque est vide."""
    assert CASE_FILES, "Aucun .yaml dans tests/golden_cases/cases/"


@pytest.mark.parametrize("case_path", CASE_FILES, ids=lambda p: p.stem)
def test_golden_case(case_path: Path) -> None:
    case = load_case(case_path)
    result = run_case(case)

    assert result.status.value in case.expected.status_in, (
        f"[{case.id}] statut {result.status.value} non dans {case.expected.status_in}"
    )

    if case.expected.makespan_max is not None:
        assert result.makespan is not None, f"[{case.id}] makespan attendu mais None"
        assert result.makespan <= case.expected.makespan_max, (
            f"[{case.id}] makespan {result.makespan} > max {case.expected.makespan_max}"
        )

    if case.expected.makespan_min is not None:
        assert result.makespan is not None, f"[{case.id}] makespan attendu mais None"
        assert result.makespan >= case.expected.makespan_min, (
            f"[{case.id}] makespan {result.makespan} < min {case.expected.makespan_min}"
        )

    assert result.solve_time_seconds <= case.expected.solve_time_s_max, (
        f"[{case.id}] solve_time {result.solve_time_seconds:.2f}s > "
        f"max {case.expected.solve_time_s_max}s"
    )
