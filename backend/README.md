# Backend ro — SaaS d'ordonnancement (Phase 4)

NestJS + Prisma + PostgreSQL. **Single-tenant V1**, sans messaging
(BullMQ/Redis remplacés par un poll DB côté worker Python).

## État (Phase 4)

| Jalon | Statut | Contenu |
|-------|--------|---------|
| **J1** — Foundation | ✅ | NestJS skeleton, Prisma client, Postgres docker-compose, `/api/health` |
| **J2** — Schema | ✅ | 14 modèles Prisma (Workshop, Machine, Operator, SharedResource, Unavailability, Client, Order, Job, Operation, SoftConstraint, Version, SolveJob, Schedule, PreflightSession, Anomaly) |
| **J3** — CRUD + versioning | ⬜ | API REST workshops/machines/orders, versioning embarqué |
| **J4** — Python worker | ⬜ | `poc-scheduler/scripts/db_worker.py` qui poll `solve_jobs` |
| **J5** — Data Quality | ⬜ | Upload CSV + intégration `src/preflight/` + écriture Anomaly |

**Hors V1** (différé Phase 7) : multi-tenancy, auth, observabilité prod.

## Stack

- Node.js 22+, npm 10+
- NestJS 10
- Prisma 5
- PostgreSQL 16 (via Docker Compose)
- TypeScript strict

## Démarrage rapide

```bash
# 1. Installer les dépendances
npm install

# 2. Démarrer Postgres
npm run db:up

# 3. Copier l'env + générer le client Prisma
cp .env.example .env
npm run prisma:generate

# 4. Appliquer la migration
npm run prisma:migrate
# (à la première exécution, accepter le nom "init")

# 5. Lancer le backend en mode dev
npm run start:dev

# 6. Vérifier le healthcheck
curl http://localhost:3000/api/health
# → {"status":"ok","uptime_s":3,"database":"up","version":"0.1.0",...}
```

## Architecture sans messaging

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  Frontend    │ ──HTTP─→│  Backend     │ ──SQL──→│  PostgreSQL  │
│  (Phase 5)   │         │  NestJS      │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
                                                          ▲
                                                          │ poll(2s)
                                                  ┌──────────────┐
                                                  │ Python worker│
                                                  │ poc-scheduler│
                                                  └──────────────┘
```

Le worker Python (J4 à venir) lit `solve_jobs` où `status='pending'`,
prend le plus ancien, met `status='running'`, exécute le pipeline
`solve → simulation → score → décision`, écrit le résultat dans
`solve_jobs.result` + crée une `Version` + un `Schedule`. Pas de Redis,
pas de BullMQ.

## Conventions de code

- **Strict TypeScript** : `strict: true`, `noImplicitAny`, `strictNullChecks`.
- **Naming DB** : tables `snake_case` au pluriel (`workshops`, `solve_jobs`),
  colonnes `snake_case` mappées via `@map()` aux propriétés `camelCase` Prisma.
- **IDs** : UUID v4 partout. Identifiants entiers métier (`machine_id_int`,
  `job_id_int`) conservés pour rester cohérent avec l'engine Python qui parle
  en indices entiers.
- **Single-tenant V1** : pas de colonne `tenant_id`. À ajouter en Phase 7
  via migration ; le schéma actuel ne bloque pas cette évolution.

## Liens vers le reste du repo

- `../poc-scheduler/` : moteur Python (engine + verticale méca + agents)
- `../poc-scheduler/src/core/models.py` : modèles Pydantic source de vérité
- `../specs-techniques-v3.md §3.2` : modèle de données SaaS spec
- `../v0-status.md` : tracker d'avancement
