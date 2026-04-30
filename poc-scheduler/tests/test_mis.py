"""Tests du module `src.core.mis` (engine generique).

Couvre :
- Cas FEASIBLE : pas d'extraction, notes informatives
- Cas instance vide
- MIS singleton sur unavailability (cas pilote)
- MIS singleton sur shared_resource
- MIS singleton sur job
- Rendering `to_summary` lisible
- `default_mis_extractor` retourne un str exploitable
- Critere de sortie 1.8 : >= 80% MIS pertinent sur 20 cas INFEASIBLE (slow)
"""

from __future__ import annotations

import pytest

from src.core.mis import (
    MISElementKind,
    MISReport,
    default_mis_extractor,
    extract_mis_approximate,
)
from src.core.models import (
    Job,
    Machine,
    MachineUnavailabilitySpec,
    Operation,
    SharedResourceSpec,
    WorkshopInstance,
)
from src.core.solver import SolverStatus

# ---------- Helpers ----------


def _feasible_3x3() -> WorkshopInstance:
    """Instance OPTIMAL connue : 3 jobs x 3 machines, dur 3, opt = 9."""
    return WorkshopInstance(
        name="mis_feasible_3x3",
        jobs=[
            Job(
                job_id=j,
                operations=[
                    Operation(job_id=j, sequence_idx=i, machine_id=(j + i) % 3, duration=3)
                    for i in range(3)
                ],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=m) for m in range(3)],
    )


def _infeasible_unavail_singleton() -> WorkshopInstance:
    """1 op dur 10, unavailability fragmentant la timeline.

    horizon naif = 10 + 5 + 10 = 25.
    Periodes [(0,5), (10,20)] decoupent en creneaux [5,10] (5) et [20,25] (5).
    Aucun creneau de 10 contigu -> INFEASIBLE.
    Retirer n'importe laquelle des deux periodes -> FEASIBLE.
    """
    return WorkshopInstance(
        name="mis_unavail_singleton",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=10),
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
        machine_unavailability=[
            MachineUnavailabilitySpec(machine_id=0, periods=[(0, 5), (10, 20)]),
        ],
    )


def _infeasible_job_singleton() -> WorkshopInstance:
    """2 jobs : un job "court" toujours faisable + un job "long" qui rend infeasible.

    Job 0 (court) : 1 op dur 4 sur machine 0.
    Job 1 (long) : 1 op dur 100 sur machine 0.
    Unavailability machine 0 : [(5, 200)] (bloque 195 unites).
    horizon = 4 + 100 + 195 = 299.
    Avec j1 : il faut un creneau de 100 dans [0,5] U [200,299]. [200,299]=99 trop court,
    [0,5]=5 trop court -> INFEASIBLE.
    Sans j1 : seul j0 dur 4 sur [0,5] -> FEASIBLE.
    Sans j0 : meme probleme avec j1 (plus restrictif) -> reste INFEASIBLE.
    => MIS singleton = job 1.
    """
    return WorkshopInstance(
        name="mis_job_singleton",
        jobs=[
            Job(
                job_id=0,
                operations=[Operation(job_id=0, sequence_idx=0, machine_id=0, duration=4)],
            ),
            Job(
                job_id=1,
                operations=[Operation(job_id=1, sequence_idx=0, machine_id=0, duration=100)],
            ),
        ],
        machines=[Machine(machine_id=0)],
        machine_unavailability=[
            MachineUnavailabilitySpec(machine_id=0, periods=[(5, 200)]),
        ],
    )


# ---------- Cas FEASIBLE / vide ----------


def test_feasible_instance_returns_no_elements() -> None:
    instance = _feasible_3x3()
    report = extract_mis_approximate(instance, time_limit_per_attempt=2.0)
    assert isinstance(report, MISReport)
    assert report.initial_status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert report.elements == []
    assert not report.is_singleton_mis
    assert report.notes
    assert any("INFEASIBLE" in n for n in report.notes)


def test_empty_instance_is_handled() -> None:
    """Un WorkshopInstance sans job retourne un MISReport non analyse."""
    instance = WorkshopInstance(
        name="mis_empty",
        jobs=[],
        machines=[Machine(machine_id=0)],
    )
    report = extract_mis_approximate(instance, time_limit_per_attempt=1.0)
    assert report.initial_status is SolverStatus.UNKNOWN
    assert report.elements == []
    assert any("vide" in n.lower() for n in report.notes)


# ---------- MIS singletons ----------


def test_singleton_unavailability_is_detected() -> None:
    """Cas pilote 1.8 : retirer une periode d'unavailability rend FEASIBLE."""
    instance = _infeasible_unavail_singleton()
    report = extract_mis_approximate(instance, time_limit_per_attempt=2.0)

    assert report.initial_status is SolverStatus.INFEASIBLE
    assert report.is_singleton_mis
    # Les deux periodes sont individuellement responsables.
    unavail_elements = [
        e for e in report.elements if e.kind is MISElementKind.MACHINE_UNAVAILABILITY
    ]
    assert len(unavail_elements) >= 1
    assert all("machine_0" in e.identifier for e in unavail_elements)
    # Une action corrective remove_unavailability est suggeree.
    assert any(a.action_kind == "remove_unavailability" for a in report.suggested_actions)


def test_singleton_job_is_detected() -> None:
    """Retirer le job 'long' rend l'instance FEASIBLE -> MIS singleton sur ce job."""
    instance = _infeasible_job_singleton()
    report = extract_mis_approximate(instance, time_limit_per_attempt=2.0)

    assert report.initial_status is SolverStatus.INFEASIBLE
    job_elements = [e for e in report.elements if e.kind is MISElementKind.JOB]
    assert len(job_elements) >= 1
    # Le job 1 (long, dur 100) doit etre identifie.
    assert any(e.identifier == "job_1" for e in job_elements)
    assert any(a.action_kind == "defer_job" for a in report.suggested_actions)


def test_singleton_shared_resource_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """La branche SR du deletion-based detecte un SR singleton.

    Note : avec le solveur actuel, `horizon = sum_durations + sum_unavail` et la
    capacite de la SR n'entre pas dans le calcul du horizon. Construire une
    instance ou la SR seule cause INFEASIBLE est structurellement hardu (un
    schedule sequentiel rentre toujours dans le horizon). On simule donc le
    solveur via monkeypatch : initial INFEASIBLE, instance modifiee (SR retiree)
    -> FEASIBLE. Le test verifie que la branche `_remove_shared_resource` du
    `extract_mis_approximate` produit l'element + l'action attendus.
    """
    from src.core import mis as mis_mod
    from src.core.solver import JSSPSolver, SolverResult

    instance = WorkshopInstance(
        name="mis_shared_resource",
        jobs=[
            Job(
                job_id=j,
                operations=[Operation(job_id=j, sequence_idx=0, machine_id=j, duration=5)],
            )
            for j in range(3)
        ],
        machines=[Machine(machine_id=m) for m in range(3)],
        shared_resources=[
            SharedResourceSpec(
                resource_name="cabine_metrologie",
                machine_ids=[0, 1, 2],
                max_concurrent=1,
            ),
        ],
    )

    def fake_solve(self: JSSPSolver, inst: WorkshopInstance) -> SolverResult:
        # Initial : INFEASIBLE. Instance modifiee (sans SR) : FEASIBLE.
        if not inst.shared_resources:
            return SolverResult(
                instance_name=inst.name,
                status=SolverStatus.FEASIBLE,
                makespan=15,
                schedule=[],
                solve_time_seconds=0.01,
            )
        return SolverResult(
            instance_name=inst.name,
            status=SolverStatus.INFEASIBLE,
            makespan=None,
            schedule=[],
            solve_time_seconds=0.01,
        )

    monkeypatch.setattr(mis_mod.JSSPSolver, "solve", fake_solve)

    report = extract_mis_approximate(instance, time_limit_per_attempt=1.0)

    assert report.initial_status is SolverStatus.INFEASIBLE
    sr_elements = [e for e in report.elements if e.kind is MISElementKind.SHARED_RESOURCE]
    assert len(sr_elements) == 1
    assert sr_elements[0].identifier == "shared_resource_cabine_metrologie"
    assert any(a.action_kind == "increase_capacity" for a in report.suggested_actions)


# ---------- Rendering ----------


def test_to_summary_describes_singletons() -> None:
    instance = _infeasible_unavail_singleton()
    report = extract_mis_approximate(instance, time_limit_per_attempt=2.0)
    summary = report.to_summary()
    assert "INFEASIBLE" in summary
    assert "machine_0" in summary
    assert "Actions correctives" in summary


def test_to_summary_on_feasible_instance() -> None:
    instance = _feasible_3x3()
    report = extract_mis_approximate(instance, time_limit_per_attempt=1.0)
    summary = report.to_summary()
    assert "non infaisable" in summary.lower() or "infeasible" in summary.lower()


def test_default_mis_extractor_returns_summary_string() -> None:
    instance = _infeasible_unavail_singleton()
    text = default_mis_extractor(instance)
    assert isinstance(text, str)
    assert "INFEASIBLE" in text


def test_max_attempts_bound_is_respected() -> None:
    """Le garde-fou max_attempts borne le nombre de re-solves."""
    instance = _infeasible_unavail_singleton()
    report = extract_mis_approximate(
        instance,
        time_limit_per_attempt=1.0,
        max_attempts=1,  # ne tester qu'un seul candidat
    )
    assert report.n_attempts <= 1
    assert any("max_attempts" in n for n in report.notes)


# ---------- Critere de sortie : >= 80% MIS pertinent sur 20 cas INFEASIBLE ----------


def _generate_infeasible_unavail_case(seed: int) -> WorkshopInstance:
    """Genere un cas INFEASIBLE singleton-unavailability deterministe.

    Variation : longueur du job, position des periodes. On garde la propriete
    qu'aucune periode supprimee individuellement ne laisse un creneau >= duration
    dans le meme alignement, mais l'unavail est globalement bloquante.
    """
    duration = 6 + (seed % 5)  # entre 6 et 10
    # Deux trous qui decoupent la timeline en creneaux trop courts.
    # horizon = duration + (gap1) + (gap2)
    return WorkshopInstance(
        name=f"mis_bench_{seed}",
        jobs=[
            Job(
                job_id=0,
                operations=[
                    Operation(job_id=0, sequence_idx=0, machine_id=0, duration=duration),
                ],
            ),
        ],
        machines=[Machine(machine_id=0)],
        machine_unavailability=[
            MachineUnavailabilitySpec(
                machine_id=0,
                periods=[
                    (0, duration - 2),
                    (duration - 1, 2 * duration - 3),
                ],
            ),
        ],
    )


@pytest.mark.slow
def test_mis_relevant_on_at_least_80pct_of_infeasible_cases() -> None:
    """Critere de sortie 1.8 : MIS pertinent (>=1 element ou note explicite) sur >=80%
    des 20 cas INFEASIBLE intentionnels.

    'Pertinent' = soit un element singleton est identifie, soit une note explique
    pourquoi (limite max_attempts, MIS combinatoire). Le report doit toujours
    refleter `initial_status=INFEASIBLE`.
    """
    n_cases = 20
    n_relevant = 0
    n_with_singleton = 0

    for seed in range(n_cases):
        instance = _generate_infeasible_unavail_case(seed)
        report = extract_mis_approximate(instance, time_limit_per_attempt=2.0)
        assert report.initial_status is SolverStatus.INFEASIBLE, (
            f"Cas {seed} attendu INFEASIBLE, recu {report.initial_status}"
        )
        if report.is_singleton_mis:
            n_with_singleton += 1
            n_relevant += 1
        elif report.notes:
            n_relevant += 1

    ratio_singleton = n_with_singleton / n_cases
    ratio_relevant = n_relevant / n_cases
    assert ratio_relevant >= 0.80, (
        f"Critere 1.8 : MIS pertinent attendu >=80%, obtenu {ratio_relevant:.0%} "
        f"(singletons : {n_with_singleton}/{n_cases})"
    )
    # Le cas pilote unavailability doit etre detecte tres souvent.
    assert ratio_singleton >= 0.80, (
        f"MIS singleton attendu >=80% sur cas pilotes, obtenu {ratio_singleton:.0%}"
    )
