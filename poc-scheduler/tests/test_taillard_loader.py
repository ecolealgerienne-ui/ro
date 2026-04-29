"""Tests du parser Taillard.

Stratégie : le test principal utilise un fichier mini synthétique au format
JSPLIB, écrit dans un répertoire temporaire. Les tests sur fichiers réels
(ta01, ta31, ta51) sont skippés si le dossier `data/taillard/` n'a pas été
peuplé via le script de téléchargement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.loaders.taillard import (
    load_metadata,
    load_taillard_instance,
    parse_taillard_file,
)

# ----- Fixtures -----

MINI_TAILLARD_CONTENT = """\
+++++++++++++++++++++++++++++
instance test_mini
+++++++++++++++++++++++++++++
Test 3x3 instance for unit tests
3 3
 1 3 2 2 3 1
 2 4 3 1 1 5
 3 2 1 4 2 3
"""

# ta01 dimensions et premier job (extrait de la spec JSPLIB)
TA01_LIKE_HEADER = """\
+++++++++++++++++++++++++++++
instance ta01_like
+++++++++++++++++++++++++++++
Smaller fixture mimicking JSPLIB style
2 4
1 10 2 20 3 15 4 5
4 8 3 12 2 7 1 9
"""

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_DATA_DIR = REPO_ROOT / "data" / "taillard"


@pytest.fixture
def mini_instance_file(tmp_path: Path) -> Path:
    p = tmp_path / "test_mini"
    p.write_text(MINI_TAILLARD_CONTENT, encoding="utf-8")
    return p


@pytest.fixture
def ta01_like_file(tmp_path: Path) -> Path:
    p = tmp_path / "ta01_like"
    p.write_text(TA01_LIKE_HEADER, encoding="utf-8")
    return p


# ----- Tests sur fichiers synthétiques -----


def test_parse_mini_instance_dimensions(mini_instance_file: Path) -> None:
    instance = parse_taillard_file(mini_instance_file)
    assert instance.name == "test_mini"
    assert instance.n_jobs == 3
    assert instance.n_machines == 3


def test_parse_mini_instance_operations(mini_instance_file: Path) -> None:
    instance = parse_taillard_file(mini_instance_file)
    job0 = instance.jobs[0]
    # Source : "1 3 2 2 3 1" → 1-indexé donc machines 0, 1, 2 après normalisation
    assert [op.machine_id for op in job0.operations] == [0, 1, 2]
    assert [op.duration for op in job0.operations] == [3, 2, 1]
    job1 = instance.jobs[1]
    assert [op.machine_id for op in job1.operations] == [1, 2, 0]
    assert [op.duration for op in job1.operations] == [4, 1, 5]


def test_parse_assigns_correct_job_and_sequence_idx(mini_instance_file: Path) -> None:
    instance = parse_taillard_file(mini_instance_file)
    for job in instance.jobs:
        for idx, op in enumerate(job.operations):
            assert op.job_id == job.job_id
            assert op.sequence_idx == idx


def test_parse_creates_machines(mini_instance_file: Path) -> None:
    instance = parse_taillard_file(mini_instance_file)
    machine_ids = [m.machine_id for m in instance.machines]
    assert machine_ids == [0, 1, 2]


def test_parse_ta01_like(ta01_like_file: Path) -> None:
    instance = parse_taillard_file(ta01_like_file)
    assert instance.n_jobs == 2
    assert instance.n_machines == 4
    assert instance.jobs[0].operations[0].machine_id == 0
    assert instance.jobs[0].operations[0].duration == 10


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_taillard_file(tmp_path / "nope")


def test_empty_file_raises(tmp_path: Path) -> None:
    p = tmp_path / "empty"
    p.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="vide"):
        parse_taillard_file(p)


def test_truncated_file_raises(tmp_path: Path) -> None:
    p = tmp_path / "trunc"
    p.write_text("3 3\n 1 3 2 2 3 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="3 jobs attendus"):
        parse_taillard_file(p)


def test_wrong_row_length_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad"
    p.write_text("2 3\n 1 3 2 2\n 1 3 2 2 3 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="valeurs trouvées"):
        parse_taillard_file(p)


def test_zero_indexed_machines(tmp_path: Path) -> None:
    p = tmp_path / "zero_idx"
    p.write_text("2 2\n0 5 1 7\n1 3 0 4\n", encoding="utf-8")
    instance = parse_taillard_file(p)
    assert instance.jobs[0].operations[0].machine_id == 0
    assert instance.jobs[0].operations[1].machine_id == 1


# ----- Tests métadonnées -----


def test_metadata_csv_loads() -> None:
    csv_path = REAL_DATA_DIR / "instances_metadata.csv"
    metadata = load_metadata(csv_path)
    assert "ta01" in metadata
    assert metadata["ta01"]["best_known_makespan"] == "1231"
    assert metadata["ta01"]["source_optimum"] == "proven_optimal"


def test_metadata_csv_covers_all_80_taillard() -> None:
    csv_path = REAL_DATA_DIR / "instances_metadata.csv"
    metadata = load_metadata(csv_path)
    expected = {f"ta{i:02d}" for i in range(1, 81)}
    assert set(metadata.keys()) >= expected


def test_load_metadata_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_metadata(tmp_path / "nope.csv")


# ----- Tests sur fichiers réels (skip si non téléchargés) -----


@pytest.mark.parametrize("name", ["ta01", "ta31", "ta51"])
def test_real_taillard_instance_parses(name: str) -> None:
    path = REAL_DATA_DIR / name
    if not path.exists():
        pytest.skip(
            f"{path} non présent — lancer "
            f"`uv run python scripts/download_benchmarks.py taillard` pour télécharger"
        )
    instance = load_taillard_instance(name, REAL_DATA_DIR)
    assert instance.name == name
    assert instance.n_jobs > 0
    assert instance.n_machines > 0
    # Vérifie que toutes les opérations référencent des machines existantes
    machine_ids = {m.machine_id for m in instance.machines}
    for job in instance.jobs:
        for op in job.operations:
            assert op.machine_id in machine_ids
    # Métadonnées attendues
    assert instance.best_known_makespan is not None
    assert instance.best_known_makespan > 0
