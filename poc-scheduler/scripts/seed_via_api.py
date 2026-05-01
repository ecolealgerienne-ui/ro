#!/usr/bin/env python3
"""Seed via API + smoke test des endpoints backend.

Le script est rejouable : par défaut il reset la DB (DELETE tous les workshops,
cascade Prisma sur machines/clients/orders/...) puis seed un atelier vitrine.

Usage :
    uv run python scripts/seed_via_api.py                 # reset + seed
    uv run python scripts/seed_via_api.py reset           # reset seul
    uv run python scripts/seed_via_api.py seed            # seed seul (sans reset)
    uv run python scripts/seed_via_api.py seed --stress 5 # + 5 ateliers paramétriques

Sert aussi de smoke test E2E : chaque appel mesure latence + assert shape.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed_via_api")

DEFAULT_API_BASE = "http://localhost:3000/api"
HTTP_TIMEOUT_S = 30.0


# =====================================================================
# Client HTTP avec mesure latence + assertions shape
# =====================================================================


@dataclass
class ApiClient:
    """Wrapper httpx.Client typé avec mesure latence par endpoint.

    Toute requête non-2xx lève (raise_for_status) et logue le body. Les latences
    sont accumulées dans `latencies_ms` puis dumpées en fin de run.
    """

    base_url: str
    latencies_ms: list[tuple[str, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._client = httpx.Client(base_url=self.base_url, timeout=HTTP_TIMEOUT_S)

    def _do(self, method: str, path: str, *, expect: int, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        resp = self._client.request(method, path, **kwargs)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.latencies_ms.append((f"{method} {path}", elapsed_ms))

        if resp.status_code != expect:
            log.error(
                "HTTP %s %s -> %d (attendu %d) : %s",
                method,
                path,
                resp.status_code,
                expect,
                resp.text[:500],
            )
            resp.raise_for_status()
            # Si raise_for_status() ne lève pas (status 2xx ≠ expect), on lève manuellement.
            raise RuntimeError(f"HTTP {method} {path} status {resp.status_code} ≠ {expect}")

        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    def get(self, path: str, *, expect: int = 200) -> Any:
        return self._do("GET", path, expect=expect)

    def post(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        expect: int = 201,
    ) -> Any:
        kwargs: dict[str, Any] = {}
        if json_body is not None:
            kwargs["json"] = json_body
        if files is not None:
            kwargs["files"] = files
        return self._do("POST", path, expect=expect, **kwargs)

    def patch(self, path: str, json_body: dict[str, Any], *, expect: int = 200) -> Any:
        return self._do("PATCH", path, expect=expect, json=json_body)

    def delete(self, path: str, *, expect: int = 200) -> Any:
        return self._do("DELETE", path, expect=expect)

    def health_check(self) -> None:
        """GET /workshops comme readiness probe (route monte si DB OK)."""
        self._do("GET", "/workshops", expect=200)

    def close(self) -> None:
        self._client.close()


def assert_shape(obj: Any, required_keys: set[str], context: str) -> None:
    """Vérifie qu'un dict contient toutes les clés attendues."""
    if not isinstance(obj, dict):
        raise AssertionError(f"{context}: attendu dict, reçu {type(obj).__name__}")
    missing = required_keys - set(obj.keys())
    if missing:
        raise AssertionError(f"{context}: clés manquantes {sorted(missing)}")


# =====================================================================
# S0 — reset
# =====================================================================


def cmd_reset(api: ApiClient) -> int:
    """DELETE tous les workshops. Cascade Prisma supprime ressources + ordres.

    Exerce : GET /workshops, DELETE /workshops/:id (avec UUID Pipe).
    """
    log.info("=== Mode reset : nettoyage DB ===")
    workshops = api.get("/workshops")

    if not isinstance(workshops, list):
        log.error("GET /workshops devrait renvoyer une liste, reçu %s", type(workshops).__name__)
        return 1

    log.info("→ %d workshop(s) à supprimer", len(workshops))

    for ws in workshops:
        assert_shape(ws, {"id", "name"}, "GET /workshops item")
        api.delete(f"/workshops/{ws['id']}")
        log.info("  ✓ DELETE workshop %r (%s)", ws.get("name"), ws["id"])

    # Vérification : la liste doit être vide
    remaining = api.get("/workshops")
    if not isinstance(remaining, list) or len(remaining) != 0:
        log.error("Reset incomplet : %s workshops restants", len(remaining or []))
        return 1

    log.info("✓ Reset OK : 0 workshop restant")
    return 0


# =====================================================================
# S2 — Atelier vitrine "Mécanique Précision SAS"
# =====================================================================
#
# Données alignées avec mockups/data.js (PME méca précision Saint-Étienne).
# 8 machines / 4 clients / 25 OFs. Gamme V1 simplifiée : 1 opération par OF
# (la durée totale du mockup tient sur la machine cible). Le solveur consomme
# ces 25 jobs sans difficulté → bon démo + smoke test du flow versioning + solve.

SHOWCASE_WORKSHOP = {
    "name": "Mécanique Précision SAS",
    "city": "Saint-Étienne (42)",
    "certifications": ["EN 9100", "IATF 16949"],
    # Quart 8h-18h, lun-ven, 6 opérateurs.
    "shiftStart": 480,
    "shiftEnd": 1080,
    "workdays": [1, 2, 3, 4, 5],
    "nOperators": 6,
}

# (machineIdInt, name, type) — index entier stable consommé par le solveur.
SHOWCASE_MACHINES: list[tuple[int, str, str]] = [
    (0, "Tour CN-1", "Tour CN"),
    (1, "Tour CN-2", "Tour CN"),
    (2, "Tour CN-3", "Tour CN"),
    (3, "Tour CN-4 (axe C)", "Tour CN"),
    (4, "Tour CN-5 (axe C)", "Tour CN"),
    (5, "Fraiseuse FR-1 (5 axes)", "Fraiseuse"),
    (6, "Fraiseuse FR-2 (5 axes)", "Fraiseuse"),
    (7, "Rectifieuse RC-1", "Rectifieuse"),
]

# (name, tier, certifications)
SHOWCASE_CLIENTS: list[tuple[str, int, list[str]]] = [
    ("Safran", 1, ["EN 9100"]),
    ("Stellantis", 2, ["IATF 16949"]),
    ("ProtoLab", 3, []),
    ("Bosch", 2, ["IATF 16949"]),
]

# (orderRef, clientName, partRef, machineIdInt, durationHours)
# 25 OFs extraits du mockup (jour/début non transmis : c'est le solveur qui place).
SHOWCASE_ORDERS: list[tuple[str, str, str, int, float]] = [
    ("OF-2026-0847", "Safran", "Bague aube TBP", 2, 3.5),
    ("OF-2026-0848", "Safran", "Carter HP étage 4", 5, 5.0),
    ("OF-2026-0849", "Safran", "Disque turbine HP", 7, 7.0),
    ("OF-2026-0851", "Stellantis", "Pignon différentiel", 0, 4.0),
    ("OF-2026-0852", "Stellantis", "Pignon différentiel", 1, 4.0),
    ("OF-2026-0853", "Stellantis", "Couronne dent.", 0, 5.5),
    ("OF-2026-0854", "Stellantis", "Couronne dent.", 1, 5.5),
    ("OF-2026-0855", "ProtoLab", "Proto coque ITER", 6, 4.5),
    ("OF-2026-0856", "ProtoLab", "Bride hydraulique", 5, 3.0),
    ("OF-2026-0858", "Bosch", "Axe transmission", 3, 6.0),
    ("OF-2026-0859", "Bosch", "Axe transmission", 3, 6.0),
    ("OF-2026-0860", "Safran", "Bague aube TBP", 2, 3.5),
    ("OF-2026-0861", "Stellantis", "Pignon BV6", 4, 4.5),
    ("OF-2026-0862", "Stellantis", "Pignon BV6", 4, 4.5),
    ("OF-2026-0863", "Stellantis", "Bride moteur", 6, 5.0),
    ("OF-2026-0864", "ProtoLab", "Proto coque ITER", 6, 4.5),
    ("OF-2026-0865", "Safran", "Carter HP étage 4", 5, 5.0),
    ("OF-2026-0866", "Stellantis", "Pignon différentiel", 1, 4.0),
    ("OF-2026-0867", "Bosch", "Bague intermédiaire", 0, 5.0),
    ("OF-2026-0868", "ProtoLab", "Bride hydraulique", 5, 3.0),
    ("OF-2026-0869", "Bosch", "Axe transmission", 3, 6.0),
    ("OF-2026-0870", "Safran", "Disque turbine HP", 7, 7.0),
    ("OF-2026-0871", "Stellantis", "Couronne dent.", 0, 5.5),
    ("OF-2026-0872", "Stellantis", "Bride moteur", 6, 5.0),
    ("OF-2026-0873", "ProtoLab", "Proto coque ITER", 6, 4.5),
]


def _seed_showcase_workshop(api: ApiClient) -> dict[str, Any]:
    """Crée l'atelier vitrine + machines + clients + 25 OFs.

    Retourne un dict {workshop, machines_by_int, clients_by_name, orders} pour
    réutilisation par les étapes suivantes (S4 preflight, S5 solve).
    """
    log.info("=== Seed atelier vitrine : %s ===", SHOWCASE_WORKSHOP["name"])

    workshop = api.post("/workshops", json_body=SHOWCASE_WORKSHOP)
    assert_shape(workshop, {"id", "name", "createdAt"}, "POST /workshops")
    wid = workshop["id"]
    log.info("  ✓ workshop %s créé (%s)", workshop["name"], wid)

    # --- Machines (8) ---
    machines_by_int: dict[int, dict[str, Any]] = {}
    for mid_int, name, mtype in SHOWCASE_MACHINES:
        m = api.post(
            f"/workshops/{wid}/machines",
            json_body={"name": name, "type": mtype, "machineIdInt": mid_int},
        )
        assert_shape(m, {"id", "machineIdInt", "name"}, "POST /machines")
        machines_by_int[mid_int] = m
    log.info("  ✓ %d machines créées", len(machines_by_int))

    # --- Clients (4) ---
    clients_by_name: dict[str, dict[str, Any]] = {}
    for cname, tier, certs in SHOWCASE_CLIENTS:
        c = api.post(
            f"/workshops/{wid}/clients",
            json_body={"name": cname, "tier": tier, "certifications": certs},
        )
        assert_shape(c, {"id", "name", "tier"}, "POST /clients")
        clients_by_name[cname] = c
    log.info("  ✓ %d clients créés", len(clients_by_name))

    # --- Ordres (25) ---
    orders: list[dict[str, Any]] = []
    for order_ref, cname, part_ref, mid_int, dur_h in SHOWCASE_ORDERS:
        client = clients_by_name[cname]
        machine = machines_by_int[mid_int]
        body = {
            "clientId": client["id"],
            "orderRef": order_ref,
            "partRef": part_ref,
            "operations": [
                {
                    "sequenceIdx": 0,
                    "machineId": machine["id"],
                    "durationMin": int(dur_h * 60),
                }
            ],
        }
        o = api.post(f"/workshops/{wid}/orders", json_body=body)
        assert_shape(o, {"id", "orderRef", "status"}, "POST /orders")
        orders.append(o)
    log.info("  ✓ %d ordres de fabrication créés", len(orders))

    # Sanity check via GET pour valider le retour de liste cohérent.
    listed = api.get(f"/workshops/{wid}/orders")
    if not isinstance(listed, list) or len(listed) != len(SHOWCASE_ORDERS):
        log.error(
            "GET /orders : attendu %d items, reçu %s", len(SHOWCASE_ORDERS), len(listed or [])
        )
        raise AssertionError("seed showcase : count orders incohérent")

    return {
        "workshop": workshop,
        "machines_by_int": machines_by_int,
        "clients_by_name": clients_by_name,
        "orders": orders,
    }


# =====================================================================
# S3 — Stress mode : N ateliers paramétriques via générateur synthétique
# =====================================================================


def _seed_stress_workshop(api: ApiClient, *, idx: int, seed: int) -> dict[str, Any]:
    """Crée un atelier paramétrique via le générateur méca synthétique.

    Petit gabarit (5-6 machines, 20-30 jobs) pour tester la montée en charge
    multi-tenant simulée sans saturer le solveur. Réexerce les mêmes endpoints
    que la vitrine.
    """
    # Import différé : générateur lourd (pandas, numpy), pas nécessaire en mode reset.
    from src.verticals.mech_workshop.generator import GenerationParams, generate_workshop

    params = GenerationParams(
        n_machines_min=5,
        n_machines_max=6,
        n_operators_min=4,
        n_operators_max=5,
        n_jobs_min=20,
        n_jobs_max=30,
        operations_per_job_min=1,
        operations_per_job_max=2,
        seed=seed,
    )
    synth = generate_workshop(params)

    name = f"Atelier stress #{idx + 1} (seed={seed})"
    body = {
        "name": name,
        "city": "Synthétique",
        "shiftStart": 480,
        "shiftEnd": 480 + params.daily_work_minutes,
        "workdays": list(range(1, params.days_per_week + 1)),
        "nOperators": len(synth.operators),
    }
    workshop = api.post("/workshops", json_body=body)
    wid = workshop["id"]

    # --- Machines ---
    machines_by_int: dict[int, dict[str, Any]] = {}
    for m in synth.machines:
        created = api.post(
            f"/workshops/{wid}/machines",
            json_body={
                "name": m.name,
                "type": m.machine_type,
                "machineIdInt": m.machine_id,
            },
        )
        machines_by_int[m.machine_id] = created

    # --- Clients : déduplique sur le nom ---
    client_names = sorted({o.client for o in synth.orders})
    clients_by_name: dict[str, dict[str, Any]] = {}
    for cname in client_names:
        # tier = celui du premier ordre rencontré pour ce client
        tier = next(o.client_tier for o in synth.orders if o.client == cname)
        c = api.post(
            f"/workshops/{wid}/clients",
            json_body={"name": cname, "tier": tier},
        )
        clients_by_name[cname] = c

    # --- Ordres : 1ère machine compatible par op (V1 simplifiée). ---
    n_orders = 0
    for synth_order in synth.orders:
        ops_dto = [
            {
                "sequenceIdx": op.sequence_idx,
                "machineId": machines_by_int[op.compatible_machine_ids[0]]["id"],
                "durationMin": op.estimated_duration_min,
            }
            for op in synth_order.operations
        ]
        api.post(
            f"/workshops/{wid}/orders",
            json_body={
                "clientId": clients_by_name[synth_order.client]["id"],
                "orderRef": synth_order.order_id,
                "partRef": f"{synth_order.material} part",
                "deadline": synth_order.deadline.isoformat(),
                "operations": ops_dto,
            },
        )
        n_orders += 1

    log.info(
        "  ✓ %s : %d machines, %d clients, %d OFs",
        name,
        len(machines_by_int),
        len(clients_by_name),
        n_orders,
    )
    return {"workshop": workshop, "n_orders": n_orders}


# =====================================================================
# S1 — cmd_seed (orchestre S2-S5)
# =====================================================================


def cmd_seed(api: ApiClient, *, stress: int = 0) -> int:
    """Orchestre S2 (vitrine), S3 (stress), S4 (CSVs), S5 (solve)."""
    log.info("=== Mode seed (stress=%d) ===", stress)

    seeded = _seed_showcase_workshop(api)
    log.info(
        "✓ Atelier vitrine prêt : %s (%d machines, %d clients, %d OFs)",
        seeded["workshop"]["name"],
        len(seeded["machines_by_int"]),
        len(seeded["clients_by_name"]),
        len(seeded["orders"]),
    )

    if stress > 0:
        log.info("=== Stress mode : %d ateliers paramétriques ===", stress)
        for i in range(stress):
            _seed_stress_workshop(api, idx=i, seed=1000 + i)
        log.info("✓ %d ateliers stress générés", stress)

    _upload_preflight_fixtures(api, workshop_id=seeded["workshop"]["id"])

    _trigger_solve_and_wait(api, workshop_id=seeded["workshop"]["id"])

    return 0


# =====================================================================
# S5 — Trigger solve + poll + GET schedule
# =====================================================================


SOLVE_TIMEOUT_S = 60.0
SOLVE_POLL_INTERVAL_S = 1.5


def _trigger_solve_and_wait(api: ApiClient, *, workshop_id: str) -> None:
    """Crée un SolveJob, polle son statut, vérifie le Schedule créé.

    Le worker Python (scripts/db_worker.py) doit tourner en parallèle pour
    consommer le job. S'il est down, le statut reste `pending` et on timeout
    proprement avec un warning.
    """
    log.info("=== S5 : trigger solve + wait ===")

    job = api.post(f"/workshops/{workshop_id}/solve-jobs", json_body={})
    assert_shape(job, {"id", "status"}, "POST /solve-jobs")
    job_id = job["id"]
    log.info("  ✓ SolveJob %s créé (status=%s)", job_id, job["status"])

    deadline = time.monotonic() + SOLVE_TIMEOUT_S
    last_status = job["status"]

    while time.monotonic() < deadline:
        time.sleep(SOLVE_POLL_INTERVAL_S)
        current = api.get(f"/workshops/{workshop_id}/solve-jobs/{job_id}")
        assert_shape(current, {"status"}, "GET /solve-jobs/:id")

        if current["status"] != last_status:
            log.info("  → status: %s → %s", last_status, current["status"])
            last_status = current["status"]

        if current["status"] in {"done", "failed", "cancelled"}:
            break
    else:
        log.warning(
            "  ⚠ timeout après %.0fs, status=%s — db_worker tourne ?",
            SOLVE_TIMEOUT_S,
            last_status,
        )
        return

    if last_status != "done":
        log.warning("  ⚠ solve terminé en status=%s (attendu 'done')", last_status)
        return

    # Schedule créé : GET pour vérifier
    schedule = api.get(f"/workshops/{workshop_id}/schedule")
    if schedule is None:
        log.warning("  ⚠ GET /schedule retourne null malgré status=done")
        return

    assert_shape(schedule, {"versionNumber"}, "GET /schedule")
    n_assignments = len(schedule.get("assignments") or [])
    log.info(
        "  ✓ Schedule v%s récupéré : %d assignments, makespan=%s",
        schedule.get("versionNumber"),
        n_assignments,
        schedule.get("makespanMin"),
    )


# =====================================================================
# S4 — Fixtures CSV preflight (clean / realistic / broken)
# =====================================================================
#
# 3 CSVs forgés à la main pour exercer les 3 niveaux d'anomalies pré-flight :
#   - clean    : 8 colonnes canoniques, valeurs propres → aucune anomalie
#   - realistic: synonymes + ~10 % valeurs litigieuses → "probables" + "surprising"
#   - broken   : colonne `duration_min` manquante → anomalie "certain" bloquante
#
# Les fixtures sont aussi écrites sur disque dans data/seed-fixtures/ pour
# inspection manuelle / tests de régression.

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "seed-fixtures"


def _build_clean_csv() -> str:
    headers = [
        "order_id",
        "client",
        "piece_name",
        "material",
        "operation_type",
        "machine",
        "duration_min",
        "deadline",
    ]
    rows = [
        [
            "OF-2026-1001",
            "Safran",
            "Bague aube TBP",
            "Inconel 718",
            "tournage",
            "CN-3",
            "210",
            "2026-05-20",
        ],
        [
            "OF-2026-1002",
            "Safran",
            "Carter HP",
            "Inconel 718",
            "fraisage",
            "FR-1",
            "300",
            "2026-05-22",
        ],
        [
            "OF-2026-1003",
            "Stellantis",
            "Pignon différentiel",
            "Acier 16MnCr5",
            "tournage",
            "CN-1",
            "240",
            "2026-05-19",
        ],
        [
            "OF-2026-1004",
            "Stellantis",
            "Couronne dent.",
            "Acier 16MnCr5",
            "tournage",
            "CN-2",
            "330",
            "2026-05-21",
        ],
        [
            "OF-2026-1005",
            "ProtoLab",
            "Proto coque ITER",
            "Aluminium 7075",
            "fraisage",
            "FR-2",
            "270",
            "2026-05-23",
        ],
        [
            "OF-2026-1006",
            "Bosch",
            "Axe transmission",
            "Acier 42CrMo4",
            "tournage",
            "CN-4",
            "360",
            "2026-05-21",
        ],
        [
            "OF-2026-1007",
            "Safran",
            "Disque turbine HP",
            "Inconel 718",
            "rectification",
            "RC-1",
            "420",
            "2026-05-25",
        ],
        [
            "OF-2026-1008",
            "Bosch",
            "Bague intermédiaire",
            "Acier 42CrMo4",
            "tournage",
            "CN-1",
            "300",
            "2026-05-22",
        ],
    ]
    return _rows_to_csv(headers, rows)


def _build_realistic_csv() -> str:
    """En-têtes synonymes ERP + ~10 % de valeurs douteuses."""
    headers = [
        "no_of",  # synonyme order_id
        "ref_client",  # synonyme client
        "designation",  # synonyme piece_name
        "matiere",  # synonyme material
        "operation_desc",  # synonyme operation_type
        "poste",  # synonyme machine
        "duree_min",  # synonyme duration_min
        "date_liv",  # synonyme deadline
    ]
    rows = [
        [
            "OF-2026-2001",
            "Safran",
            "Bague aube TBP",
            "Inconel 718",
            "tournage",
            "CN-3",
            "210",
            "2026-05-20",
        ],
        [
            "OF-2026-2002",
            "Safran",
            "Carter HP",
            "Inconel 718",
            "fraisage",
            "FR-1",
            "300",
            "2026-05-22",
        ],
        # Anomalie probable : durée formattée "3h30" au lieu de minutes.
        ["OF-2026-2003", "Stellantis", "Pignon", "Acier", "tournage", "CN-1", "3h30", "2026-05-19"],
        [
            "OF-2026-2004",
            "Stellantis",
            "Couronne",
            "Acier",
            "tournage",
            "CN-2",
            "330",
            "2026-05-21",
        ],
        # Anomalie probable : client manquant.
        ["OF-2026-2005", "", "Proto ITER", "Alu 7075", "fraisage", "FR-2", "270", "2026-05-23"],
        ["OF-2026-2006", "Bosch", "Axe", "42CrMo4", "tournage", "CN-4", "360", "2026-05-21"],
        [
            "OF-2026-2007",
            "Safran",
            "Disque turbine",
            "Inconel",
            "rectif",
            "RC-1",
            "420",
            "2026-05-25",
        ],
        # Anomalie surprising : durée extrême (24 h sur une op).
        ["OF-2026-2008", "Bosch", "Bague", "Acier", "tournage", "CN-1", "1440", "2026-05-22"],
        [
            "OF-2026-2009",
            "Stellantis",
            "Pignon BV6",
            "Acier",
            "tournage",
            "CN-5",
            "270",
            "2026-05-24",
        ],
        [
            "OF-2026-2010",
            "ProtoLab",
            "Bride hydraulique",
            "Alu",
            "fraisage",
            "FR-1",
            "180",
            "2026-05-26",
        ],
    ]
    return _rows_to_csv(headers, rows)


def _build_broken_csv() -> str:
    """Colonne duration_min manquante → anomalie certain (bloquante)."""
    headers = ["order_id", "client", "piece_name", "machine"]
    rows = [
        ["OF-2026-3001", "Safran", "Bague TBP", "CN-3"],
        ["OF-2026-3002", "Stellantis", "Pignon", "CN-1"],
        ["OF-2026-3003", "Bosch", "Axe", "CN-4"],
    ]
    return _rows_to_csv(headers, rows)


def _rows_to_csv(headers: list[str], rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return buf.getvalue()


def _upload_preflight_fixtures(api: ApiClient, *, workshop_id: str) -> None:
    """Génère les 3 fixtures, les écrit sur disque, puis upload via l'API."""
    log.info("=== S4 : 3 fixtures CSV preflight ===")
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    fixtures: list[tuple[str, str, str]] = [
        ("clean.csv", _build_clean_csv(), "aucune anomalie attendue"),
        ("realistic.csv", _build_realistic_csv(), "~10 % anomalies probables/surprising"),
        ("broken.csv", _build_broken_csv(), "duration_min manquant → certain bloquant"),
    ]

    for name, content, expectation in fixtures:
        path = FIXTURES_DIR / name
        path.write_text(content, encoding="utf-8")
        log.info(
            "  fixture écrite : %s (%s)", path.relative_to(FIXTURES_DIR.parent.parent), expectation
        )

        try:
            session = api.post(
                f"/workshops/{workshop_id}/preflight-sessions",
                files={"file": (name, content.encode("utf-8"), "text/csv")},
            )
            assert_shape(session, {"id"}, "POST /preflight-sessions")
            log.info(
                "  ✓ session %s : status=%s, %d anomalies",
                session["id"],
                session.get("status"),
                len(session.get("anomalies", []) or []),
            )
        except httpx.HTTPError as e:
            # Le service preflight Python (port 8001) peut être down sans empêcher
            # le reste du seed (workshop déjà créé). On loggue et on continue.
            log.warning("  ⚠ upload %s échoué : %s — preflight_service tourne ?", name, e)


# =====================================================================
# main
# =====================================================================


def _print_latency_recap(api: ApiClient) -> None:
    if not api.latencies_ms:
        return
    log.info("--- Récap latence : top 5 plus lents ---")
    top = sorted(api.latencies_ms, key=lambda kv: -kv[1])[:5]
    for label, ms in top:
        log.info("  %6.1f ms  %s", ms, label)
    total_ms = sum(ms for _, ms in api.latencies_ms)
    log.info("--- %d appels HTTP, total %.0f ms ---", len(api.latencies_ms), total_ms)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed via API + smoke test des endpoints backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Default (sans subcommand) : reset + seed (rejouable infiniment).\n"
            "Le backend doit tourner sur --api-base (défaut http://localhost:3000/api)."
        ),
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help=f"URL backend (défaut: {DEFAULT_API_BASE})",
    )

    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("reset", help="DELETE tous les workshops")
    seed_parser = sub.add_parser("seed", help="Crée atelier vitrine + CSVs + solve")
    seed_parser.add_argument(
        "--stress",
        type=int,
        default=0,
        help="Nombre d'ateliers stress-test paramétriques additionnels",
    )

    args = parser.parse_args(argv)

    api = ApiClient(args.api_base)

    try:
        api.health_check()
    except httpx.HTTPError as e:
        log.error("Backend injoignable sur %s : %s", args.api_base, e)
        api.close()
        return 2

    rc = 0
    try:
        if args.cmd == "reset":
            rc = cmd_reset(api)
        elif args.cmd == "seed":
            rc = cmd_seed(api, stress=args.stress)
        else:
            rc = cmd_reset(api)
            if rc == 0:
                rc = cmd_seed(api, stress=0)
    except (httpx.HTTPError, AssertionError, RuntimeError) as e:
        log.error("Echec : %s", e)
        rc = 1
    finally:
        _print_latency_recap(api)
        api.close()

    return rc


if __name__ == "__main__":
    sys.exit(main())
