"""Worker DB-as-queue pour la Phase 4 J4.

Polle la table `solve_jobs` (status='pending'), verrouille atomiquement la
plus ancienne, execute le pipeline complet (`solve -> simulation -> score ->
decision`) et ecrit le resultat en DB. Cree un `Schedule` rattache a la
`Version` source.

Architecture sans messaging — voir `backend/README.md` :

    pending -> running (claim atomique via UPDATE ... FOR UPDATE SKIP LOCKED)
            -> done | failed (writeback du resultat)

Usage local :

    export DATABASE_URL="postgresql://ro_user:ro_dev_password@localhost:5432/ro_dev"
    uv run python scripts/db_worker.py --polling-interval 2

Pour arret propre : SIGINT (Ctrl+C) ou SIGTERM. Le worker termine le job en
cours puis sort.

Verticalite : ce worker utilise la calibration `mech_workshop` (poids
confiance + seuils simulation) car c'est la verticale active V1. Quand une
2e verticale arrivera, on resoudra par discriminant `Workshop.metadata` ou
une colonne dediee `vertical_kind`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import sys
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.core.pipeline import PipelineDecisionKind, run_pipeline
from src.core.snapshot_bridge import instance_from_snapshot
from src.verticals.mech_workshop import (
    MECH_CONFIDENCE_WEIGHTS,
    MECH_SIMULATION_THRESHOLDS,
)

logger = logging.getLogger("db_worker")


@dataclass(frozen=True)
class WorkerConfig:
    database_url: str
    polling_interval_s: float
    worker_id: str


# ---------- SQL ----------

CLAIM_SQL = """
UPDATE solve_jobs
SET status = 'running'::"SolveJobStatus",
    worker_id = %(worker_id)s,
    started_at = NOW(),
    heartbeat_at = NOW(),
    attempts = attempts + 1,
    updated_at = NOW()
WHERE id = (
    SELECT id FROM solve_jobs
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING id, workshop_id, version_id, config;
"""

# Recupere la Version active si version_id est NULL
PICK_VERSION_SQL = """
SELECT id, version_number, snapshot
FROM versions
WHERE workshop_id = %(workshop_id)s
  AND ( (%(version_id)s::uuid IS NOT NULL AND id = %(version_id)s::uuid)
        OR (%(version_id)s::uuid IS NULL AND is_active = true) )
LIMIT 1;
"""

WRITE_DONE_SQL = """
UPDATE solve_jobs
SET status = 'done'::"SolveJobStatus",
    result = %(result)s::jsonb,
    confidence_score = %(score)s,
    simulation_verdict = %(verdict)s,
    finished_at = NOW(),
    heartbeat_at = NOW(),
    version_id = %(version_id)s::uuid,
    updated_at = NOW()
WHERE id = %(job_id)s::uuid;
"""

WRITE_FAILED_SQL = """
UPDATE solve_jobs
SET status = 'failed'::"SolveJobStatus",
    error_message = %(error)s,
    finished_at = NOW(),
    heartbeat_at = NOW(),
    updated_at = NOW()
WHERE id = %(job_id)s::uuid;
"""

UPSERT_SCHEDULE_SQL = """
INSERT INTO schedules (id, version_id, makespan_min, assignments, created_at)
VALUES (gen_random_uuid(), %(version_id)s::uuid, %(makespan)s, %(assignments)s::jsonb, NOW())
ON CONFLICT (version_id) DO UPDATE
  SET makespan_min = EXCLUDED.makespan_min,
      assignments = EXCLUDED.assignments;
"""


# ---------- Worker ----------


class Worker:
    def __init__(self, config: WorkerConfig) -> None:
        self.config = config
        self._stop = False

    def request_stop(self, *_: Any) -> None:
        logger.info("signal recu, arret apres job courant")
        self._stop = True

    def run(self) -> None:
        logger.info(
            "worker demarre id=%s polling=%.1fs",
            self.config.worker_id,
            self.config.polling_interval_s,
        )
        while not self._stop:
            try:
                self._tick()
            except Exception:
                logger.exception("erreur dans la boucle worker")
                time.sleep(self.config.polling_interval_s)
            else:
                time.sleep(self.config.polling_interval_s)
        logger.info("worker arrete proprement")

    def _tick(self) -> None:
        with psycopg.connect(self.config.database_url, row_factory=dict_row) as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(CLAIM_SQL, {"worker_id": self.config.worker_id})
                row = cur.fetchone()
                if row is None:
                    return
                job_id = str(row["id"])
                workshop_id = str(row["workshop_id"])
                version_id = row.get("version_id")
                config = row.get("config") or {}

            logger.info("job claim id=%s workshop=%s", job_id, workshop_id)
            try:
                version_row = self._pick_version(conn, workshop_id, version_id)
                snapshot = version_row["snapshot"]
                resolved_version_id = str(version_row["id"])

                report = self._run_pipeline(snapshot, config)

                schedule_payload = self._serialize_schedule(report)
                makespan = self._extract_makespan(report)

                with conn.transaction(), conn.cursor() as cur:
                    if schedule_payload is not None and makespan is not None:
                        cur.execute(
                            UPSERT_SCHEDULE_SQL,
                            {
                                "version_id": resolved_version_id,
                                "makespan": makespan,
                                "assignments": json.dumps(schedule_payload),
                            },
                        )
                    cur.execute(
                        WRITE_DONE_SQL,
                        {
                            "job_id": job_id,
                            "result": json.dumps(self._serialize_report(report)),
                            "score": (
                                int(round(report.score.overall * 100)) if report.score else None
                            ),
                            "verdict": (
                                report.simulation.verdict.value if report.simulation else None
                            ),
                            "version_id": resolved_version_id,
                        },
                    )
                logger.info(
                    "job done id=%s decision=%s score=%s",
                    job_id,
                    report.decision.kind.value,
                    (int(round(report.score.overall * 100)) if report.score else None),
                )
            except Exception as e:
                logger.exception("job failed id=%s", job_id)
                with conn.transaction(), conn.cursor() as cur:
                    cur.execute(
                        WRITE_FAILED_SQL,
                        {"job_id": job_id, "error": f"{type(e).__name__}: {e}"[:1000]},
                    )

    def _pick_version(
        self,
        conn: psycopg.Connection[Any],
        workshop_id: str,
        version_id: Any,
    ) -> Mapping[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                PICK_VERSION_SQL,
                {
                    "workshop_id": workshop_id,
                    "version_id": str(version_id) if version_id else None,
                },
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Aucune version disponible pour workshop {workshop_id}")
            return row

    def _run_pipeline(self, snapshot: Mapping[str, Any], config: Mapping[str, Any]):
        instance = instance_from_snapshot(snapshot)
        if not instance.jobs:
            raise RuntimeError("Aucun OF planifiable dans cette version")

        time_budgets = config.get("time_budgets_s") if isinstance(config, dict) else None
        if not isinstance(time_budgets, (list, tuple)) or not time_budgets:
            time_budgets = (5.0, 15.0, 30.0)
        num_workers = (
            int(config["num_workers"])
            if isinstance(config, dict) and config.get("num_workers")
            else 4
        )

        return run_pipeline(
            instance,
            confidence_weights=MECH_CONFIDENCE_WEIGHTS,
            simulation_thresholds=MECH_SIMULATION_THRESHOLDS,
            time_budgets_s=tuple(float(b) for b in time_budgets),
            num_workers=num_workers,
        )

    def _serialize_report(self, report: Any) -> dict[str, Any]:
        return report.model_dump(mode="json")

    def _extract_makespan(self, report: Any) -> int | None:
        cb = report.circuit_breaker
        if cb.final_result is None:
            return None
        ms = cb.final_result.makespan
        return int(ms) if ms is not None else None

    def _serialize_schedule(self, report: Any) -> list[dict[str, Any]] | None:
        if report.decision.kind not in (PipelineDecisionKind.ACCEPT, PipelineDecisionKind.WARN):
            return None
        cb = report.circuit_breaker
        if cb.final_result is None or not cb.final_result.schedule:
            return None
        return [
            {
                "job_id": int(a.job_id),
                "sequence_idx": int(a.sequence_idx),
                "machine_id": int(a.machine_id),
                "start": int(a.start),
                "end": int(a.end),
            }
            for a in cb.final_result.schedule
        ]


# ---------- main ----------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker DB-as-queue pour solve_jobs")
    parser.add_argument(
        "--polling-interval",
        type=float,
        default=2.0,
        help="intervalle de poll en secondes (defaut 2.0)",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="identifiant lisible du worker (defaut: hostname-pid-uuid8)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL"),
        help="URL Postgres (defaut: variable d'environnement DATABASE_URL)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="niveau de log Python (defaut: INFO)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    if not args.database_url:
        logger.error("DATABASE_URL absent (--database-url ou env)")
        return 2

    worker_id = args.worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    config = WorkerConfig(
        database_url=args.database_url,
        polling_interval_s=args.polling_interval,
        worker_id=worker_id,
    )

    worker = Worker(config)
    signal.signal(signal.SIGINT, worker.request_stop)
    signal.signal(signal.SIGTERM, worker.request_stop)

    worker.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
