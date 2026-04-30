"""Tests du module `src.core.simulation` (engine generique).

Couvre :
- Verdict ACCEPT pour planning sans violation
- Detection setup_ratio (WARN, REJECT)
- Detection micro_pauses au-dela du seuil
- Detection fragmentation job
- Coherence verdict <-> violations (model_validator)
- Configuration meca exposee + somme/coherence
"""

from __future__ import annotations

import pytest

from src.core.models import Job, Machine, Operation, WorkshopInstance
from src.core.simulation import (
    MachineMetrics,
    SimulationReport,
    SimulationVerdict,
    SimulationViolation,
    ViolationSeverity,
    simulate_schedule,
)
from src.core.solver import (
    ScheduleAssignment,
    SolverResult,
    SolverStatus,
)
from src.verticals.mech_workshop import MECH_SIMULATION_THRESHOLDS

DEFAULTS = {
    "micro_pause_threshold": 5,
    "max_setup_ratio": 0.30,
    "reject_setup_ratio": 0.50,
    "max_micro_pauses_per_machine": 3,
    "max_job_fragmentation": 0.30,
}


def _instance_two_ops(family_pair: tuple[int, int] = (0, 0)) -> WorkshopInstance:
    """Atelier : 1 machine, 2 jobs (1 op chacun, dur 5)."""
    return WorkshopInstance(
        name="two_ops",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(
                        job_id=0, sequence_idx=0, machine_id=0, duration=5, family_id=family_pair[0]
                    ),
                ],
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(
                        job_id=1, sequence_idx=0, machine_id=0, duration=5, family_id=family_pair[1]
                    ),
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
        transition_matrix=[[0, 100], [100, 0]],
    )


def _result(schedule: list[ScheduleAssignment], makespan: int) -> SolverResult:
    return SolverResult(
        instance_name="two_ops",
        status=SolverStatus.OPTIMAL,
        makespan=makespan,
        schedule=schedule,
        solve_time_seconds=0.1,
    )


# ---------- Cas nominal ----------


def test_clean_schedule_yields_accept() -> None:
    """2 ops collees, meme famille -> aucun setup, aucune pause -> ACCEPT."""
    instance = _instance_two_ops((0, 0))
    schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5),
        ScheduleAssignment(job_id=1, sequence_idx=0, machine_id=0, start=5, end=10),
    ]
    report = simulate_schedule(instance, _result(schedule, 10), **DEFAULTS)
    assert report.verdict is SimulationVerdict.ACCEPT
    assert report.violations == []
    assert report.machines[0].setup_ratio == 0.0
    assert report.machines[0].micro_pause_count == 0


# ---------- Setup ratio ----------


def test_high_setup_ratio_yields_warn() -> None:
    """Familles differentes -> setup 100, productive 10 -> ratio = 100/110 ~ 0.91 -> REJECT."""
    instance = _instance_two_ops((0, 1))
    schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5),
        ScheduleAssignment(job_id=1, sequence_idx=0, machine_id=0, start=105, end=110),
    ]
    report = simulate_schedule(instance, _result(schedule, 110), **DEFAULTS)
    assert report.verdict is SimulationVerdict.REJECT
    assert any(v.rule == "setup_ratio_critical" for v in report.violations)
    assert report.machines[0].setup_time == 100
    assert report.machines[0].family_transitions == 1


def test_moderate_setup_ratio_yields_warn_only() -> None:
    """Setup 4, productive 10 -> ratio = 4/14 ~ 0.286 -> sous seuil WARN."""
    instance = WorkshopInstance(
        name="moderate",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5, family_id=0)
                ],
            ),
            Job(
                job_id=1,
                operations=[
                    Operation(job_id=1, sequence_idx=0, machine_id=0, duration=5, family_id=1)
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
        transition_matrix=[[0, 4], [4, 0]],
    )
    schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5),
        ScheduleAssignment(job_id=1, sequence_idx=0, machine_id=0, start=9, end=14),
    ]
    report = simulate_schedule(instance, _result(schedule, 14), **DEFAULTS)
    assert report.verdict is SimulationVerdict.ACCEPT
    assert report.machines[0].setup_time == 4
    assert abs(report.machines[0].setup_ratio - 4 / 14) < 1e-9


# ---------- Micro-pauses ----------


def test_micro_pauses_exceeded_yields_warn() -> None:
    """5 ops avec 4 gaps de 2 unites (< threshold 5) -> 4 micro-pauses > 3 -> WARN."""
    instance = WorkshopInstance(
        name="micro_pauses",
        jobs=[
            Job(
                job_id=j,
                operations=[Operation(job_id=j, sequence_idx=0, machine_id=0, duration=3)],
            )
            for j in range(5)
        ],
        machines=[Machine(machine_id=0)],
    )
    schedule = []
    t = 0
    for j in range(5):
        schedule.append(
            ScheduleAssignment(job_id=j, sequence_idx=0, machine_id=0, start=t, end=t + 3)
        )
        t += 3 + 2
    report = simulate_schedule(instance, _result(schedule, t - 2), **DEFAULTS)
    assert report.verdict is SimulationVerdict.WARN
    assert any(v.rule == "micro_pauses_excess" for v in report.violations)
    assert report.machines[0].micro_pause_count == 4


# ---------- Fragmentation job ----------


def test_job_fragmentation_yields_warn() -> None:
    """Job avec 2 ops espacees : duree 10, span 100 -> frag 90 % > 30 % -> WARN."""
    instance = WorkshopInstance(
        name="frag",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5),
                    Operation(job_id=0, sequence_idx=1, machine_id=1, duration=5),
                ],
            ),
        ],
        machines=[Machine(machine_id=0), Machine(machine_id=1)],
    )
    schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5),
        ScheduleAssignment(job_id=0, sequence_idx=1, machine_id=1, start=95, end=100),
    ]
    report = simulate_schedule(instance, _result(schedule, 100), **DEFAULTS)
    assert report.verdict is SimulationVerdict.WARN
    assert any(v.rule == "job_fragmentation_high" for v in report.violations)
    assert abs(report.jobs[0].fragmentation_ratio - 0.9) < 1e-9


def test_clean_job_no_fragmentation() -> None:
    instance = WorkshopInstance(
        name="clean",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=5),
                    Operation(job_id=0, sequence_idx=1, machine_id=1, duration=5),
                ],
            ),
        ],
        machines=[Machine(machine_id=0), Machine(machine_id=1)],
    )
    schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5),
        ScheduleAssignment(job_id=0, sequence_idx=1, machine_id=1, start=5, end=10),
    ]
    report = simulate_schedule(instance, _result(schedule, 10), **DEFAULTS)
    assert report.verdict is SimulationVerdict.ACCEPT
    assert report.jobs[0].fragmentation_ratio == 0.0


# ---------- Garde-fou config ----------


def test_inconsistent_thresholds_raises() -> None:
    instance = _instance_two_ops()
    schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5),
        ScheduleAssignment(job_id=1, sequence_idx=0, machine_id=0, start=5, end=10),
    ]
    bad = {**DEFAULTS, "reject_setup_ratio": 0.10, "max_setup_ratio": 0.30}
    with pytest.raises(ValueError, match=r"reject_setup_ratio"):
        simulate_schedule(instance, _result(schedule, 10), **bad)


# ---------- model_validator du verdict ----------


def test_verdict_rejects_inconsistent_construction() -> None:
    """Verdict ACCEPT incompatible avec une violation REJECT -> erreur."""
    with pytest.raises(ValueError, match=r"verdict"):
        SimulationReport(
            verdict=SimulationVerdict.ACCEPT,
            machines=[
                MachineMetrics(
                    machine_id=0,
                    n_ops=1,
                    productive_time=5,
                    setup_time=0,
                    idle_time=0,
                    setup_ratio=0.0,
                    micro_pause_count=0,
                    family_transitions=0,
                ),
            ],
            jobs=[],
            violations=[
                SimulationViolation(
                    rule="x",
                    severity=ViolationSeverity.REJECT,
                    target="machine_0",
                    raw_value=1.0,
                    threshold=0.5,
                    description="forced",
                ),
            ],
        )


# ---------- Verticale méca ----------


def test_mech_thresholds_cover_required_keys() -> None:
    """La config meca expose les memes cles que celles attendues par simulate_schedule."""
    expected_keys = {
        "micro_pause_threshold",
        "max_setup_ratio",
        "reject_setup_ratio",
        "max_micro_pauses_per_machine",
        "max_job_fragmentation",
    }
    assert set(MECH_SIMULATION_THRESHOLDS.keys()) == expected_keys


def test_mech_thresholds_are_internally_consistent() -> None:
    assert (
        MECH_SIMULATION_THRESHOLDS["reject_setup_ratio"]
        >= MECH_SIMULATION_THRESHOLDS["max_setup_ratio"]
    )
    assert MECH_SIMULATION_THRESHOLDS["micro_pause_threshold"] > 0


def test_mech_config_used_via_kwargs_unpacking() -> None:
    """Verifie que la config peut etre passee via **MECH_SIMULATION_THRESHOLDS."""
    instance = _instance_two_ops((0, 0))
    schedule = [
        ScheduleAssignment(job_id=0, sequence_idx=0, machine_id=0, start=0, end=5),
        ScheduleAssignment(job_id=1, sequence_idx=0, machine_id=0, start=5, end=10),
    ]
    report = simulate_schedule(instance, _result(schedule, 10), **MECH_SIMULATION_THRESHOLDS)
    assert report.verdict is SimulationVerdict.ACCEPT
