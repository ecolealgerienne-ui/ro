# Rapport d'avancement Phase 4 — Backend SaaS + persistance

> Document narratif complémentaire à `v0-status.md` (tracker structuré).
> Documente les résultats concrets, décisions techniques et métriques de chaque jalon.
> Mis à jour à chaque étape stabilisée.

**Snapshot : 2026-04-30 — Phase 4 ✅ stabilisée (V1, sans auth/multi-tenant)**

---

## Synthèse

| Indicateur | Valeur |
|------------|--------|
| Phase courante | 4 — Backend SaaS + persistance |
| Étapes stabilisées | **5/8** (4.1 ✅ + 4.4 ✅ + 4.5 ✅ + 4.7 ✅ + 4.8 ✅) |
| Étapes abandonnées | **1/8** (4.6 — BullMQ remplacé par DB-as-queue) |
| Étapes différées Phase 7 prod | **2/8** (4.2 multi-tenant + 4.3 auth) |
| Tests e2e backend | **11 passants** (jest + supertest, ~5 s) |
| Smoke tests E2E | **2/2** (CRUD + versioning, et upload CSV → anomalies) |
| Migration DB | 1 (`init` — 16 tables côté Postgres) |
| Stack | NestJS 10 + Prisma 5 + PostgreSQL 16 + FastAPI + psycopg v3 |

---

## Repositionnement préliminaire — Abandon de BullMQ + report auth/multi-tenant

**Décision 2026-04-30** : Phase 4 retravaillée par rapport à la spec initiale.

| Étape spec | V1 livrée | Justification |
|------------|-----------|---------------|
| 4.6 BullMQ + queue solving | ❌ abandonnée → DB-as-queue (table `solve_jobs` polled par worker Python) | Évite Redis/BullMQ pour 5-7 design partners ; suffit < ~10 solves/min. Migration vers vraie queue déférable (LISTEN/NOTIFY Postgres, ou Redis si throughput le justifie). |
| 4.2 multi-tenancy | ⏸️ différée Phase 7 | V1 single-tenant : un atelier = une instance Docker. Schéma actuel n'empêche pas l'ajout futur (toutes les tables ont déjà un `workshop_id` discriminant). |
| 4.3 auth (Argon2id, JWT) | ⏸️ différée Phase 7 | Pas pertinent pour un pilote DP en réseau privé. À traiter en Phase 7 sécurité prod. |

Le découpage interne en **5 jalons J1-J5** correspond aux étapes effectivement livrées,
chacune commitée et smoke-testée séparément.

---

## Jalon J1 (4.1) — Setup NestJS + Prisma + Postgres ✅

**Objectif** : foundation, healthcheck, conteneurisation Postgres.

**Livrables**
- `backend/` : repo NestJS 10 + Prisma 5 + Postgres 16 (Docker Compose ou cluster
  système).
- Strict TypeScript (`noImplicitAny`, `strictNullChecks`), eslint + prettier,
  scripts npm cohérents (`start:dev`, `build`, `typecheck`, `test:e2e`,
  `prisma:migrate`, `db:up`).
- `PrismaModule` + `PrismaService` (lifecycle `onModuleInit` / `onModuleDestroy`).
- `HealthModule` : `GET /api/health` retourne
  `{ status, uptime_s, database, version, timestamp }`. Le check `database` fait
  un `SELECT 1` Prisma — un Postgres down passe en `degraded`.
- `docker-compose.yml` : Postgres 16-alpine + `pg_isready` healthcheck + volume
  persistant.

**Smoke test E2E**
```
npm install → prisma migrate dev --name init → 16 tables Postgres
npm run build → npm run start:prod → curl /api/health
{"status":"ok","uptime_s":2,"database":"up","version":"0.1.0",...}
```

**Décisions structurantes**
- Naming DB : tables `snake_case` au pluriel (`workshops`, `solve_jobs`),
  colonnes `snake_case` mappées via `@map()` aux propriétés `camelCase` Prisma.
- Strict mode TypeScript dès le J1 — pas de tech-debt sur les types après coup.
- Pas de cluster système : Docker Compose seul (le repo doit être autonome). En
  dev local sur poste, tout `npm run db:up` suffit.

---

## Jalon J2 (4.4) — Schema Prisma complet ✅

**Objectif** : modèle de données aligné avec `poc-scheduler/src/core/models.py` (Pydantic
engine) + spec V3 §3.2.

**15 modèles + 4 enums livrés**

| Domaine | Modèles |
|---------|---------|
| Atelier | `Workshop`, `Machine`, `Operator`, `SharedResource`, `MachineUnavailability` |
| Donneurs d'ordre | `Client` (tier 1/2/3), `Order` + `OrderStatus` enum |
| Solving | `Job` (1 ordre = 1 job V1), `Operation` (avec `family_id`, `qualified_operator_ids`), `SolveJob` + `SolveJobStatus` enum, `Schedule` |
| Soft constraints | `SoftConstraint` (catégorie + parameters JSON + weight_hint + raw_nl_text pour audit) |
| Versioning | `Version` (avec `parent_version_id` lineage + snapshot JSON + `is_active`) |
| Data Quality | `PreflightSession`, `Anomaly` + `AnomalyLevel`/`AnomalyStatus` enums |

**Décisions de mapping**
- **Indices entiers conservés** : `Machine.machineIdInt`, `Operator.operatorIdInt`,
  `Job.jobIdInt`. Les UUID Prisma servent pour les FK ; les indices entiers
  servent au solveur Python (cohérent avec `src.core.models.Machine.machine_id`).
  Le bridge (J4) traduit UUID → entier au moment du solve.
- **Versioning embarqué** : `Version.snapshot` est un JSON aggregate complet (pas
  de tables versionnées séparées). V1 : simple, audit complet. V2 si la taille
  devient un sujet : éclater en tables versionnées.
- **DB-as-queue préparée** : `SolveJob` a déjà `worker_id` + `heartbeat_at` pour
  J4 (claim atomique + détection workers morts).

**Migration**
- `prisma migrate dev --name init` → 16 tables côté Postgres (15 modèles +
  `_prisma_migrations`).

---

## Jalon J3 (4.5) — API CRUD + versioning automatique ✅

**Objectif** : 4 modules CRUD avec versioning embarqué dans toute mutation.

**Livrables**
```
backend/src/
├── workshops/        # POST/GET/GET-id/PATCH/DELETE /api/workshops
├── machines/         # nested /api/workshops/:wId/machines (machineIdInt auto)
├── clients/          # nested /api/workshops/:wId/clients (tier 1/2/3)
├── orders/           # nested /api/workshops/:wId/orders (Order + Job + Operations cascade)
└── versions/         # nested /api/workshops/:wId/versions + rollback
```

**`VersionsService` partagé** — c'est le cœur du jalon. Méthode
`createSnapshotInTransaction(tx, workshopId, message, author)` :
1. Construit le snapshot agrégé via `Workshop.findUnique({ include: ... })`
2. Désactive l'ex-active (`isActive: false`)
3. Calcule `versionNumber = max + 1` (contrainte unique pour multi-workers safe)
4. Insère la nouvelle Version avec `parentVersionId = ex-active.id`

Chaque CRUD service appelle ce helper **dans la même transaction** :
```ts
return this.prisma.$transaction(async (tx) => {
  const created = await tx.machine.create({ data: ... });
  await this.versions.createSnapshotInTransaction(
    tx, workshopId, `Ajout machine "${created.name}"`,
  );
  return created;
});
```
Garantie atomique : la mutation et la version sont commitées ensemble, ou rien.

**Rollback non-destructif** : `POST /api/workshops/:id/versions/:n/rollback` crée
une nouvelle version au sommet avec le snapshot de la version cible. L'historique
reste intact.

**Discipline DTO** : `class-validator` + global `ValidationPipe({ whitelist: true,
forbidNonWhitelisted: true })` rejettent toute clé inconnue avec HTTP 400 —
équivalent Pydantic `extra="forbid"` côté Python.

**Tests e2e (11 passants en ~5 s)**
- Workshop create → v1 active
- Reject extra field (HTTP 400)
- Machine create → v2, machineIdInt auto-assigné à 0
- Reject machineIdInt dupliqué (HTTP 409)
- Order create avec gamme 2 ops → v3
- Reject sequence_idx non contigus (HTTP 400)
- Reject machine d'un autre workshop (HTTP 400)
- Rollback crée nouvelle version sans détruire historique
- Reject rollback vers version active (HTTP 409)
- Reject rollback vers version inexistante (HTTP 404)
- Snapshot inclut machines + orders + clients

**Smoke test manuel**
```
Workshop → 3 machines → 1 client Safran → 1 OF gamme 2 ops → 6 versions auto
→ PATCH workshop → v7 → rollback v1 → v8 active, historique v1-v7 intact.
```

---

## Jalon J4 (4.7) — Bridge backend ↔ worker Python via DB-as-queue ✅

**Objectif** : remplacer BullMQ/Redis par un poll DB côté Python. Architecture
sans messaging.

**`poc-scheduler/src/core/snapshot_bridge.py`** (engine générique) — bridge
JSON Prisma ↔ `WorkshopInstance` Pydantic. Traduit `machineId` UUID →
`machine_id_int` entier (clé attendue par le solveur). Résout `criticality` par
fallback : `Order.criticality` → `Client.tier` → `None`. Gère shared_resources,
unavailability, transition_matrix.

**`poc-scheduler/scripts/db_worker.py`** (verticale `mech_workshop` V1) — worker
psycopg v3 :
1. **Poll** `solve_jobs WHERE status='pending'` toutes les 2 s (configurable).
2. **Claim atomique** : `UPDATE ... SET status='running' WHERE id = (SELECT id ...
   FOR UPDATE SKIP LOCKED)` — multi-workers safe sans Redis. `SKIP LOCKED`
   signifie : si un autre worker tient déjà la ligne, on saute.
3. **Récupère la Version source** (active si non spécifiée dans `SolveJob.versionId`).
4. **Exécute le pipeline** complet : circuit breaker → simulation → score →
   décision, avec calibration `mech_workshop` (`MECH_CONFIDENCE_WEIGHTS` +
   `MECH_SIMULATION_THRESHOLDS`).
5. **Upsert Schedule** (assignments JSON + makespan_min, unique par `version_id`).
6. **Writeback SolveJob** : `status='done'`, `result` JSON complet,
   `confidence_score` (0-100, `int(round(overall * 100))`), `simulation_verdict`
   (ACCEPT/WARN/REJECT). Si erreur → `status='failed'` + `error_message`.

CLI : `--polling-interval`, `--worker-id`, `--database-url`, `--log-level`.
SIGINT/SIGTERM = arrêt propre après job courant.

**Backend `solve-jobs` module** :
- `POST /api/workshops/:id/solve-jobs` : crée `SolveJob` (status pending, version
  active par défaut si non spécifiée).
- `GET /api/workshops/:id/solve-jobs` : liste 50 derniers.
- `GET /api/workshops/:id/solve-jobs/:id` : détail (peut être polled par UI).
- `DELETE /api/workshops/:id/solve-jobs/:id` : annule un job pending uniquement.
- DTO `CreateSolveJobDto` : `versionId?` + `config` optionnels (`time_budgets_s`
  1-5 valeurs entre 0.1-600 s, `num_workers` 1-32).

**Smoke test E2E**
```
Workshop "Test J4" + 2 machines (CN-1, FR-1) + client Safran T1 +
2 OFs (gamme 2 ops chacun)
→ POST /solve-jobs (pending)
→ worker pickup en ~2 s
→ status=done, score=82/100, verdict=ACCEPT, decision=ACCEPT, makespan=55 min
→ 4 ScheduleAssignment persistées en DB.
```

**Pourquoi DB-as-queue plutôt que BullMQ**
- 1 dépendance infra en moins (Redis).
- Atomicité gratuite : mêmes contraintes ACID que les autres tables.
- Multi-workers safe via `FOR UPDATE SKIP LOCKED` Postgres standard.
- Latence : ~2 s de poll vs. push instantané. Pour des solves de 10-60 s,
  négligeable.
- Évolution : LISTEN/NOTIFY Postgres en option intermédiaire si on veut le push
  sans Redis.

---

## Jalon J5 (4.8) — Data Quality + upload CSV + bridge HTTP synchrone ✅

**Objectif** : exposer `src/preflight/` (Phase 2) au backend via HTTP synchrone,
persister anomalies et permettre la validation 3 niveaux côté UI.

**Pourquoi synchrone (pas DB-as-queue comme J4)** : le pre-flight est rapide
(~1 s pour 500 lignes — parsing CSV + fuzzy match), un appel bloquant suffit.
Pas besoin du polling overhead.

**`poc-scheduler/scripts/preflight_service.py`** — mini service uvicorn +
FastAPI (port 8001 par défaut).
- `GET /health` → `{ status: 'ok', version }`
- `POST /preflight` (multipart) → `PreflightReport` JSON
- Réutilise `MECH_COLUMN_PATTERNS` + `MECH_REQUIRED_CANONICAL_FIELDS` de la
  verticale méca. Aucune logique dupliquée — wrapper fin sur
  `src.preflight.run_preflight`.

**Backend `preflight-sessions` module** :
- `POST /api/workshops/:id/preflight-sessions` : multipart upload via
  `FileInterceptor` (`@nestjs/platform-express`), limite 5 Mio (couvre un CSV
  ERP de 50 000 lignes ~3-4 Mio).
- `PreflightClientService` : forwarde via `fetch` natif Node 22 vers le service
  Python. Erreurs typées (503 service injoignable, 502 erreur upstream).
- `PreflightSessionsService` : persistance atomique
  `PreflightSession` + `Anomaly[]` dans une transaction, avec hash sha256 du
  fichier pour audit.
- Routes annexes : `GET` liste/détail, `PATCH .../anomalies/:anomalyId`
  (status `pending` → `resolved` / `ignored` / `excluded` + résolution texte).

**Mapping sévérité Python → DB**
| `src.preflight.Severity` | `AnomalyLevel` DB | UI 3 niveaux spec V3 §3 |
|--------------------------|-------------------|--------------------------|
| `BLOCKING` | `certain` | Niveau 1 — bloquant, doit être corrigé |
| `WARNING` | `probable` | Niveau 2 — à valider une par une |
| `INFO` | `surprising` | Niveau 3 — ack only |

**Variable d'env** : `PREFLIGHT_SERVICE_URL` (défaut `http://localhost:8001`).

**Smoke test E2E**
```
CSV de 3 lignes :
  OF-001 | 30   | 2026-12-31  ← OK
  OF-002 | -15  | 2026-12-31  ← duration_negative_or_zero (warning)
  OF-003 | abc  | 2024-01-01  ← duration_not_int (blocking) + date_in_past (warning)

→ POST /preflight-sessions (multipart)
→ PreflightSession créée avec sha256
→ 3 anomalies persistées : 1 certain + 2 probable
→ Fuzzy mapping colonnes auto : NO_OF → order_id, DUREE_MIN → duration_min, DEADLINE → deadline
→ PATCH anomaly status pending → resolved + résolution texte.
```

---

## Architecture finale Phase 4 (sans messaging)

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  Frontend    │ ──HTTP─→│  Backend     │ ──SQL──→│  PostgreSQL  │
│  (Phase 5)   │         │  NestJS      │         │   16-alpine  │
└──────────────┘         │  Prisma      │         └──────────────┘
                         └──────┬───────┘                ▲
                                │                        │
                         multipart/form-data       poll(2s) FOR UPDATE
                                │                       SKIP LOCKED
                                ▼                        │
                         ┌──────────────┐         ┌──────────────┐
                         │  FastAPI     │         │ Worker Python│
                         │  /preflight  │         │  scripts/    │
                         │  (port 8001) │         │  db_worker.py│
                         └──────────────┘         └──────────────┘
                         (sync, ~1s)              (async, 10-60s)
```

**4 services applicatifs + 1 base** :
1. `backend/` (NestJS, port 3000)
2. `poc-scheduler/scripts/db_worker.py` (Python, polling 2 s)
3. `poc-scheduler/scripts/preflight_service.py` (FastAPI, port 8001)
4. PostgreSQL 16 (port 5432, via Docker Compose ou cluster système)

**Pas de Redis. Pas de BullMQ. Pas de queue externe.** Pour 5-7 design partners
V1, c'est largement suffisant. Migration future déférable.

---

## Démarrage local (4 terminaux)

```bash
# 1. Postgres
cd backend && npm run db:up

# 2. Backend
cd backend && npm run start:dev    # http://localhost:3000/api

# 3. Worker solves
cd poc-scheduler
export DATABASE_URL="postgresql://ro_user:ro_dev_password@localhost:5432/ro_dev"
uv run python scripts/db_worker.py --polling-interval 2

# 4. Service preflight
cd poc-scheduler
uv run uvicorn scripts.preflight_service:app --port 8001
```

Healthchecks :
- `curl http://localhost:3000/api/health` → backend
- `curl http://localhost:8001/health` → service preflight
- Worker : log `worker demarre id=<host>-<pid>-<uuid8> polling=2.0s`

---

## Restantes à traiter (post-pilotes)

| Étape | Statut | Quand |
|-------|--------|-------|
| 4.2 multi-tenancy | ⏸️ | Phase 7 prod — schéma déjà compatible (`workshop_id` discriminant) |
| 4.3 auth (Argon2id, JWT) | ⏸️ | Phase 7 prod — pour les pilotes V1, accès réseau privé |

---

## Synthèse des décisions structurantes Phase 4

| Décision | Raison | Impact |
|----------|--------|--------|
| Abandon BullMQ → DB-as-queue | Évite Redis, suffit pour 5-7 DP | 1 dépendance infra en moins, pattern multi-worker via `FOR UPDATE SKIP LOCKED` |
| Pre-flight en HTTP sync (pas DB poll) | Latence ~1 s, pas besoin de queue | 2 patterns coexistent dans le repo : poll (long), HTTP (court) — choix par cas d'usage |
| Versioning : snapshot JSON aggregate | Simple, audit complet, rollback non-destructif | V2 si taille devient un sujet : tables versionnées |
| Single-tenant V1 | Pilotes DP en réseau privé | `workshop_id` discriminant déjà partout, ajout `tenant_id` futur sans migration lourde |
| `class-validator` strict (`whitelist + forbidNonWhitelisted`) | Aligner avec `extra="forbid"` côté Python | API rejette les typos / champs inconnus en HTTP 400 |
| Indices entiers `machineIdInt` etc. | Solveur Python parle en indices entiers | Bridge UUID → entier au moment du solve, conversion isolée dans `snapshot_bridge.py` |

---

*Mis à jour à chaque transition de jalon stabilisée.*
