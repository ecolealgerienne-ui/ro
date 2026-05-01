# ro — SaaS d'ordonnancement IA pour la sous-traitance mécanique de précision

> Monorepo regroupant le moteur d'ordonnancement (CP-SAT + agents LLM), le
> backend SaaS (NestJS + Prisma), le frontend chef d'atelier (Next.js +
> Tailwind + shadcn) et les artefacts produit (mockups, spécifications,
> journal d'avancement).

---

## Qu'est-ce qu'on fait ?

Une SaaS qui aide les chefs d'atelier de PME en mécanique de précision (5-25
machines, sous-traitance Safran/Stellantis/Bosch/aéro/médical) à **construire
leur planning de production** sans Excel.

Trois piliers techniques :

1. **Moteur d'ordonnancement OR-Tools CP-SAT** — solveur exact avec patterns
   industriels (setup-dependent, opérateurs qualifiés, ressources partagées,
   indisponibilités, soft constraints).
2. **Couche IA disciplinée** — 5 agents LLM cantonnés à
   extraction/explication/traduction NL ; aucun appel LLM ne génère de code
   solveur. Tool use natif Claude API, pas de MCP server.
3. **Trust layer** — score de confiance, simulation opérationnelle post-hoc,
   circuit breaker INFEASIBLE, MIS approximé, validation systématique humaine.

Le différenciateur produit n'est pas la techno IA, c'est l'**UX décisionnelle
accumulée** par les clients dans le produit (5ᵉ moat selon `docs/specs-fonctionnelles-v3.md` §10).

---

## Statut global

| Phase | Intitulé | Statut |
|-------|----------|--------|
| 0 | Validation OR-Tools (go/no-go projet) | ✅ stabilisée |
| 1 | Bibliothèque de patterns + objectifs composites | ✅ stabilisée (9/9 étapes) |
| 2 | Trust layer technique (sans LLM) | ✅ stabilisée — Gate 1 ✓ |
| 3 | Agents LLM (tool use natif Claude API) | ✅ stabilisée (3.3-3.8 ; 3.1/3.2 abandonnées MCP) |
| 4 | Backend SaaS + persistance | ✅ stabilisée V1 (5/5 jalons J1-J5) |
| 5 | Frontend chef d'atelier | ✅ stabilisée V1 (9/9 étapes, 7 jalons J1-J7, 10 routes Next.js) |
| 6 | PWA opérateur | ⬜ à faire |
| 7 | Observabilité, sécurité, production | ⬜ à faire (auth + multi-tenant ici) |
| 8 | Pilote design partners | ⬜ à faire |

Suivi détaillé par étape : [`docs/v0-status.md`](./docs/v0-status.md).

**Gates franchis** :
- **Gate 0** ✅ — OR-Tools CP-SAT validé sur Taillard (5/5 instances < 5 % gap, gap moyen 1.82 %)
- **Gate 1** ✅ — Trust layer 0 erreur silencieuse sur 20 ateliers méca synthétiques

---

## Structure du dépôt

```
ro/
├── README.md                          # ce fichier (point d'entrée GitHub)
├── CONTRIBUTING.md                    # conventions de travail
│
├── docs/                              # Toute la doc (sauf README + CONTRIBUTING)
│   ├── v0-status.md                   # tracker structuré par étape
│   ├── phase-{0,1,2,3,4,5}-report.md  # rapports narratifs par phase
│   ├── specs-fonctionnelles-v3.md     # spec produit
│   ├── specs-techniques-v3.md         # spec architecture
│   ├── specs-poc-scripts-v1.md        # spec scripts POC
│   └── guide-entretiens-decouverte-phase0.md
│
├── poc-scheduler/                     # Moteur Python (Phases 0-3)
│   ├── src/
│   │   ├── core/                      # Engine générique (vertical-agnostic)
│   │   ├── preflight/                 # Pre-flight CSV générique
│   │   ├── loaders/                   # Loaders Taillard, benchmark
│   │   ├── llm/                       # Couche LLM générique
│   │   ├── agents/                    # Base abstraite des agents LLM
│   │   └── verticals/
│   │       └── mech_workshop/         # Verticale méca (calibration + agents)
│   ├── scripts/
│   │   ├── db_worker.py               # Worker DB-as-queue (J4)
│   │   └── preflight_service.py       # Service FastAPI (J5)
│   ├── tests/                         # 382 tests
│   └── pyproject.toml
│
├── backend/                           # Backend SaaS (Phase 4)
│   ├── prisma/schema.prisma           # 15 modèles + 4 enums
│   ├── src/
│   │   ├── workshops/  machines/  clients/  orders/   # CRUD nested
│   │   ├── versions/                                  # versioning automatique
│   │   ├── solve-jobs/                                # POST → DB-as-queue
│   │   ├── preflight-sessions/                        # multipart upload + bridge HTTP
│   │   ├── schedules/                                 # GET schedule (rétro-fit J3 frontend)
│   │   └── health/  prisma/
│   ├── test/                          # 11 tests e2e jest+supertest
│   ├── docker-compose.yml             # Postgres 16
│   └── package.json
│
├── frontend/                          # Frontend chef d'atelier (Phase 5)
│   ├── app/                           # Next.js App Router
│   │   ├── page.tsx                   # landing + sélecteur workshop
│   │   ├── health/page.tsx
│   │   ├── onboarding/page.tsx        # wizard install J0 (J7)
│   │   └── workshops/[id]/
│   │       ├── page.tsx               # Dashboard (J2)
│   │       ├── gantt/page.tsx         # Gantt custom CSS (J3)
│   │       ├── conversation/page.tsx  # Chat scénarios scriptés (J4)
│   │       ├── infeasibility/page.tsx # Diagnostic MIS + actions (J4)
│   │       ├── preflight/             # Upload CSV + 3 niveaux anomalies (J5)
│   │       └── versions/page.tsx      # Timeline + diff + rollback (J6)
│   ├── components/                    # ~30 composants modulaires
│   │   ├── ui/                        # shadcn (button, card, badge, separator)
│   │   ├── dashboard/  gantt/  conversation/  preflight/  versions/  onboarding/
│   │   └── app-sidebar.tsx
│   ├── lib/api/                       # Client + types miroirs Prisma + 11 hooks TanStack
│   └── package.json
│
└── mockups/                           # Mockups UX HTML statique (jetables)
    ├── index.html                     # Dashboard chef d'atelier
    ├── gantt.html  conversation.html  infeasibility.html  versioning.html
    ├── onboarding-{1,2,3}-*.html      # Parcours J0 install
    └── data.js  layout.js  README.md
```

---

## Démarrage rapide (5 services en local)

**Prérequis** : Python 3.11+ (via [`uv`](https://docs.astral.sh/uv/)),
Node 20+ (via `nvm`), Docker (pour Postgres) ou Postgres 16 système.

```bash
# Terminal 1 — Postgres via Docker
cd backend && npm install && npm run db:up

# Terminal 2 — Backend NestJS
cd backend && cp .env.example .env && npm run prisma:migrate
CORS_ORIGIN=http://localhost:3001 npm run start:dev
# → http://localhost:3000/api/health

# Terminal 3 — Worker solves Python (DB-as-queue)
cd poc-scheduler && uv sync
export DATABASE_URL="postgresql://ro_user:ro_dev_password@localhost:5432/ro_dev"
uv run python scripts/db_worker.py --polling-interval 2

# Terminal 4 — Service preflight Python (FastAPI sync)
cd poc-scheduler
uv run uvicorn scripts.preflight_service:app --port 8001
# → http://localhost:8001/health

# Terminal 5 — Frontend Next.js
cd frontend && npm install && cp .env.example .env.local && npm run dev
# → http://localhost:3001
```

**Mockups V0** (jetables, archivés en référence) :
`cd mockups && python3 -m http.server 8080` puis
[http://localhost:8080/index.html](http://localhost:8080/index.html).

Voir [`backend/README.md`](./backend/README.md),
[`frontend/README.md`](./frontend/README.md) et
[`poc-scheduler/README.md`](./poc-scheduler/README.md) pour les détails.

---

## Architecture (Phase 5 V1, sans messaging)

```
┌──────────────────────┐
│  Frontend Next.js 15 │
│  (port 3001)         │
│  + TanStack Query    │
└──────────┬───────────┘
           │ HTTP (CORS allow-origin)
           ▼
┌──────────────────────┐         ┌──────────────┐
│  Backend NestJS      │ ──SQL──→│  PostgreSQL  │
│  (port 3000)         │         │   16-alpine  │
│  + Prisma            │         └──────────────┘
└──────┬───────────────┘                ▲
       │                                │
multipart/form-data            poll(2s) FOR UPDATE
       │                              SKIP LOCKED
       ▼                                │
┌──────────────┐                ┌──────────────┐
│  FastAPI     │                │ Worker Python│
│  /preflight  │                │  scripts/    │
│  (port 8001) │                │  db_worker.py│
└──────────────┘                └──────────────┘
(sync, ~1s)                     (async, 10-60s)
```

**Pas de Redis. Pas de BullMQ. Pas de queue externe.**

Pour les solves longs (10-60 s), DB-as-queue avec `FOR UPDATE SKIP LOCKED`
Postgres = multi-workers safe sans Redis. Pour le pre-flight rapide (~1 s),
HTTP synchrone direct vers FastAPI. Pour le frontend → backend, fetch
classique avec CORS allow-origin V1 (verrouillage par tenant Phase 7).

Détails dans [`docs/phase-4-report.md`](./docs/phase-4-report.md) (backend) et
[`docs/phase-5-report.md`](./docs/phase-5-report.md) (frontend).

---

## Conventions clés

- **Architecture multi-verticale** : `src/core/` (engine) ↔ `src/verticals/<nom>/`
  (calibration métier). Aucun import croisé. Discipline détaillée dans
  [`CONTRIBUTING.md` §8](./CONTRIBUTING.md).
- **Pydantic strict partout** : `frozen=True`, `extra="forbid"`, `model_validator`.
- **Class-validator strict côté backend** : `whitelist + forbidNonWhitelisted`
  (équivalent Pydantic).
- **Versioning automatique** : chaque mutation backend crée une nouvelle Version
  avec snapshot JSON complet. Rollback non-destructif.
- **Verticalité testée 11 fois consécutives** : pattern engine ↔ vertical tient
  à 92 % (cf. audit Sprint 1, commit `278845c`).

---

## Points de référence pour les développeurs

| Question | Document |
|----------|----------|
| Comment démarrer le projet ? | Ce README, sections « Démarrage rapide » |
| Quel est l'avancement actuel ? | [`docs/v0-status.md`](./docs/v0-status.md) |
| Pourquoi cette décision ? | Journal des décisions dans `docs/v0-status.md` ou `phase-X-report.md` |
| Quelles sont les conventions ? | [`CONTRIBUTING.md`](./CONTRIBUTING.md) |
| Comment marche le moteur ? | [`poc-scheduler/README.md`](./poc-scheduler/README.md) |
| Comment marche le backend ? | [`backend/README.md`](./backend/README.md) |
| Comment marche le frontend ? | [`frontend/README.md`](./frontend/README.md) |
| À quoi ressemblait l'UX initiale ? | [`mockups/README.md`](./mockups/README.md) (8 écrans HTML, jetables) |
| Quelle est la spec produit ? | [`docs/specs-fonctionnelles-v3.md`](./docs/specs-fonctionnelles-v3.md) |
| Quelle est la spec technique ? | [`docs/specs-techniques-v3.md`](./docs/specs-techniques-v3.md) |

---

## Métriques actuelles

| Indicateur | Valeur |
|------------|--------|
| Tests Python (poc-scheduler) | **382 passants** (~110 s) |
| Tests e2e backend | **11 passants** (~5 s) |
| Lignes de code applicatif | ~12k Python + ~6.5k TypeScript (3k backend + 3.5k frontend) |
| Phases complètes | **6/9** (0, 1, 2, 3, 4, 5) |
| Routes Next.js générées | **10** (1 statique + 9 server-rendered) |
| Composants React | ~30 (dashboard, gantt, conversation, preflight, versions, onboarding, ui shadcn) |
| Hooks TanStack Query | **11** (queries + mutations) |
| Tables Postgres | **15** (+ migrations Prisma) |
| Endpoints REST exposés | **~32** (workshops, machines, clients, orders, versions, solve-jobs, preflight-sessions, schedule, health) |
| Services applicatifs en local | **5** (Postgres + backend NestJS + worker Python + FastAPI preflight + frontend Next.js) |
