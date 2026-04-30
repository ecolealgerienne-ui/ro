"""Tests du module `benchmark_runner`.

Stratégie : utiliser une mini-instance JSSP synthétique (2×2 avec optimum 5)
posée dans un répertoire temporaire avec un `instances_metadata.csv` minimal.
Évite la dépendance aux fichiers Taillard réels et garde les tests rapides.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.core.solver import SolverStatus
from src.loaders.benchmark_runner import (
    BenchmarkRecord,
    run_batch,
    run_one,
    summarize,
    write_csv,
)


@pytest.fixture
def mini_data_dir(tmp_path: Path) -> Path:
    """Crée un dossier de test avec une instance 2×2 et ses métadonnées.

    Instance test_mini :
      Job 0 : M1(3) M2(2)  → 1-indexé dans le fichier
      Job 1 : M2(2) M1(2)
    Optimum connu = 5.
    """
    data_dir = tmp_path / "taillard"
    data_dir.mkdir()
    (data_dir / "test_mini").write_text(
        "+++++++++++++++++++++++++++++\n"
        "instance test_mini\n"
        "+++++++++++++++++++++++++++++\n"
        "Mini fixture\n"
        "2 2\n"
        "1 3 2 2\n"
        "2 2 1 2\n",
        encoding="utf-8",
    )
    (data_dir / "test_other").write_text(
        "2 2\n1 2 2 1\n2 1 1 2\n",
        encoding="utf-8",
    )
    (data_dir / "instances_metadata.csv").write_text(
        "name,n_jobs,n_machines,best_known_makespan,source_optimum\n"
        "test_mini,2,2,5,proven_optimal\n"
        "test_other,2,2,3,proven_optimal\n",
        encoding="utf-8",
    )
    return data_dir


# ----- BenchmarkRecord -----


def test_benchmark_record_csv_serialization() -> None:
    record = BenchmarkRecord(
        instance_name="ta01",
        n_jobs=15,
        n_machines=15,
        best_known_makespan=1231,
        found_makespan=1240,
        gap_percent=0.7311,
        status=SolverStatus.FEASIBLE,
        solve_time_seconds=121.45,
        objective_bound=1235.5,
    )
    row = record.as_csv_row()
    assert row["instance"] == "ta01"
    assert row["best_known"] == "1231"
    assert row["found"] == "1240"
    assert row["gap_percent"] == "0.73"
    assert row["time_seconds"] == "121.45"
    assert row["status"] == "FEASIBLE"


def test_benchmark_record_handles_no_solution() -> None:
    record = BenchmarkRecord(
        instance_name="x",
        n_jobs=10,
        n_machines=10,
        best_known_makespan=500,
        found_makespan=None,
        gap_percent=None,
        status=SolverStatus.UNKNOWN,
        solve_time_seconds=60.0,
    )
    row = record.as_csv_row()
    assert row["found"] == ""
    assert row["gap_percent"] == ""
    assert row["status"] == "UNKNOWN"


# ----- run_one (utilise vraiment le solver, instance triviale) -----


def test_run_one_returns_optimal_with_zero_gap(mini_data_dir: Path) -> None:
    record = run_one("test_mini", mini_data_dir, time_limit_seconds=5.0, num_workers=2)
    assert record.status == SolverStatus.OPTIMAL
    assert record.found_makespan == 5
    assert record.best_known_makespan == 5
    assert record.gap_percent == pytest.approx(0.0)
    assert record.solve_time_seconds >= 0.0


def test_run_one_missing_instance_raises(mini_data_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        run_one("does_not_exist", mini_data_dir, time_limit_seconds=2.0, num_workers=1)


# ----- run_batch -----


def test_run_batch_returns_records_in_order(mini_data_dir: Path) -> None:
    records = run_batch(
        ["test_mini", "test_other"],
        mini_data_dir,
        time_limit_seconds=5.0,
        num_workers=2,
    )
    assert [r.instance_name for r in records] == ["test_mini", "test_other"]
    assert all(r.status == SolverStatus.OPTIMAL for r in records)


def test_run_batch_invokes_callback(mini_data_dir: Path) -> None:
    received: list[BenchmarkRecord] = []
    run_batch(
        ["test_mini", "test_other"],
        mini_data_dir,
        time_limit_seconds=5.0,
        num_workers=2,
        on_record=received.append,
    )
    assert len(received) == 2
    assert received[0].instance_name == "test_mini"


# ----- write_csv -----


def test_write_csv_roundtrip(tmp_path: Path) -> None:
    records = [
        BenchmarkRecord(
            instance_name="ta01",
            n_jobs=15,
            n_machines=15,
            best_known_makespan=1231,
            found_makespan=1240,
            gap_percent=0.73,
            status=SolverStatus.FEASIBLE,
            solve_time_seconds=121.5,
        ),
        BenchmarkRecord(
            instance_name="ta02",
            n_jobs=15,
            n_machines=15,
            best_known_makespan=1244,
            found_makespan=1244,
            gap_percent=0.0,
            status=SolverStatus.OPTIMAL,
            solve_time_seconds=87.2,
        ),
    ]
    output = tmp_path / "results" / "out.csv"
    n = write_csv(records, output)
    assert n == 2
    assert output.exists()

    with output.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["instance"] == "ta01"
    assert rows[0]["found"] == "1240"
    assert rows[1]["status"] == "OPTIMAL"


# ----- summarize -----


def test_summarize_basic_stats() -> None:
    records = [
        BenchmarkRecord(
            instance_name="a",
            n_jobs=15,
            n_machines=15,
            best_known_makespan=100,
            found_makespan=100,
            gap_percent=0.0,
            status=SolverStatus.OPTIMAL,
            solve_time_seconds=10.0,
        ),
        BenchmarkRecord(
            instance_name="b",
            n_jobs=15,
            n_machines=15,
            best_known_makespan=100,
            found_makespan=104,
            gap_percent=4.0,
            status=SolverStatus.FEASIBLE,
            solve_time_seconds=20.0,
        ),
        BenchmarkRecord(
            instance_name="c",
            n_jobs=15,
            n_machines=15,
            best_known_makespan=100,
            found_makespan=None,
            gap_percent=None,
            status=SolverStatus.UNKNOWN,
            solve_time_seconds=30.0,
        ),
    ]
    stats = summarize(records)
    assert stats["count"] == 3
    assert stats["optimal_count"] == 1
    assert stats["feasible_count"] == 1
    assert stats["mean_gap_percent"] == pytest.approx(2.0)
    assert stats["max_gap_percent"] == pytest.approx(4.0)
    assert stats["mean_time_seconds"] == pytest.approx(20.0)


def test_summarize_empty() -> None:
    stats = summarize([])
    assert stats["count"] == 0
    assert stats["mean_gap_percent"] == 0.0
