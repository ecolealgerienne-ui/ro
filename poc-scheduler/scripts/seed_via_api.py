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
import logging
import sys
import time
from dataclasses import dataclass, field
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
# S1 — seed (skeleton, à compléter S2-S5)
# =====================================================================


def cmd_seed(api: ApiClient, *, stress: int = 0) -> int:
    """Crée l'atelier vitrine, génère CSVs, déclenche un solve.

    Sera complété progressivement :
      S2 atelier vitrine "Mécanique Précision SAS"
      S3 stress mode (--stress N)
      S4 fixtures CSV + upload preflight
      S5 trigger solve + wait + vérif Schedule
    """
    log.info("=== Mode seed (stress=%d) ===", stress)
    log.warning("seed: stub — implémentation S2-S5 à venir")
    _ = api  # placeholder, on l'utilisera très bientôt
    return 0


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
