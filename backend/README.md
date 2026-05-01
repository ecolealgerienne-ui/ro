# Backend ro — SaaS d'ordonnancement (Phase 4)

NestJS 10 + Prisma 5 + PostgreSQL 16. **Single-tenant V1**, sans messaging
(BullMQ/Redis remplacés par DB-as-queue côté worker Python).

## État (Phase 4 — close, 5/5 jalons stabilisés)

| Jalon | Étape spec | Statut | Livrable |
|-------|------------|--------|----------|
| **J1** | 4.1 | ✅ | NestJS skeleton + Prisma + Postgres docker-compose + `GET /api/health` |
| **J2** | 4.4 | ✅ | Schema Prisma : 15 modèles + 4 enums, migration `init` (16 tables) |
| **J3** | 4.5 | ✅ | API CRUD workshops/machines/clients/orders + versioning automatique + rollback non-destructif |
| **J4** | 4.7 | ✅ | Bridge worker Python via DB-as-queue (`solve_jobs` polled toutes les 2 s, `FOR UPDATE SKIP LOCKED`) |
| **J5** | 4.8 | ✅ | Upload CSV multipart + bridge HTTP synchrone vers FastAPI Python + persistance `Anomaly` 3 niveaux |

**Hors V1** (différé Phase 7 prod) : multi-tenancy (4.2), auth Argon2id+JWT (4.3),
observabilité prod (Phase 7).

**Abandonné** (4.6) : queue BullMQ remplacée par DB-as-queue. Pour 5-7 design
partners, le poll 2 s suffit ; migration vers vraie queue déférable
(LISTEN/NOTIFY Postgres en option intermédiaire).

**Retro-fits Phase 5** (frontend Next.js consommateur) :
- `enableCors()` avec env `CORS_ORIGIN` (défaut `http://localhost:3001`) pour
  autoriser les requêtes cross-origin du frontend.
- Nouveau module `schedules` avec endpoint `GET /api/workshops/:wId/schedule`
  pour exposer le résultat planifié du worker Python au Gantt frontend.

Détails complets : [`../docs/phase-4-report.md`](../docs/phase-4-report.md) +
[`../docs/phase-5-report.md`](../docs/phase-5-report.md) (jalon J3 retro-fit).

## Stack

- Node.js 22+, npm 10+
- NestJS 10 (`@nestjs/common`, `@nestjs/core`, `@nestjs/platform-express`,
  `@nestjs/config`, `@nestjs/mapped-types`)
- Prisma 5 (`@prisma/client` + `prisma`)
- PostgreSQL 16 (via Docker Compose ou cluster système)
- TypeScript 5 strict (`noImplicitAny`, `strictNullChecks`,
  `forceConsistentCasingInFileNames`)
- `class-validator` + `class-transformer` (équivalent Pydantic côté API)
- `multer` (multipart upload pour J5)
- `jest` + `supertest` pour les tests e2e

## Démarrage rapide

```bash
# 1. Installer les dépendances
npm install

# 2. Démarrer Postgres
npm run db:up                     # Docker Compose
# ou utiliser un Postgres système écouter sur 5432

# 3. Copier l'env + appliquer la migration
cp .env.example .env
npm run prisma:migrate            # crée les 16 tables
npm run prisma:generate           # généré automatiquement par migrate, mais utile en cas de pull

# 4. Lancer le backend
npm run start:dev                 # mode dev avec watch
# ou
npm run build && npm run start:prod

# 5. Vérifier
curl http://localhost:3000/api/health
# → {"status":"ok","uptime_s":3,"database":"up","version":"0.1.0",...}
```

Pour utiliser le **flow complet** (CRUD + solve + preflight), il faut aussi
démarrer les 2 services Python (cf. `Architecture` ci-dessous).

## Endpoints exposés

Toutes les routes sont préfixées `/api`.

### Health
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/health` | Status, uptime, état DB, version |

### Workshops + ressources nested
| Méthode | Route | Description |
|---------|-------|-------------|
| POST/GET | `/workshops` | Créer / lister |
| GET/PATCH/DELETE | `/workshops/:id` | Détail / modifier / supprimer (cascade) |
| POST/GET | `/workshops/:wId/machines` | Créer / lister machines |
| GET/PATCH/DELETE | `/workshops/:wId/machines/:id` | Détail / modifier / supprimer |
| POST/GET | `/workshops/:wId/clients` | Créer / lister clients (tier 1/2/3) |
| GET/PATCH/DELETE | `/workshops/:wId/clients/:id` | Détail / modifier / supprimer |
| POST/GET | `/workshops/:wId/orders` | Créer / lister OFs (gamme = 1+ ops) |
| GET/PATCH/DELETE | `/workshops/:wId/orders/:id` | Détail / modifier / supprimer |

### Versioning
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/workshops/:wId/versions` | Liste versions (DESC, sans snapshot) |
| GET | `/workshops/:wId/versions/:n` | Détail v`n` (avec snapshot) |
| POST | `/workshops/:wId/versions/:n/rollback` | Crée une nouvelle version au sommet avec le snapshot de v`n` |

### Schedule (résultat planifié — retro-fit Phase 5 J3)
| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/workshops/:wId/schedule?versionId=...` | Schedule de la version active (défaut) ou spécifique. Retourne 200 + `null` si pas encore solvé, 404 si version invalide. |

### Solve jobs (DB-as-queue → worker Python J4)
| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/workshops/:wId/solve-jobs` | Crée un solve pending (`versionId?` + `config?`) |
| GET | `/workshops/:wId/solve-jobs` | Liste 50 derniers (poll côté UI) |
| GET | `/workshops/:wId/solve-jobs/:id` | Détail (status / score / verdict / result) |
| DELETE | `/workshops/:wId/solve-jobs/:id` | Annule un job pending uniquement |

### Preflight sessions (HTTP sync → service Python J5)
| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/workshops/:wId/preflight-sessions` | Multipart upload CSV → anomalies persistées |
| GET | `/workshops/:wId/preflight-sessions` | Liste 50 derniers |
| GET | `/workshops/:wId/preflight-sessions/:id` | Détail + anomalies (groupées par niveau) |
| PATCH | `/workshops/:wId/preflight-sessions/:id/anomalies/:anomalyId` | Status `pending` → `resolved` / `ignored` / `excluded` + résolution texte |

## Architecture (sans messaging)

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

**Deux patterns coexistent** selon le cas d'usage :

- **DB-as-queue** pour les solves (10-60 s) : le backend écrit `solve_jobs.status='pending'`,
  le worker Python `FOR UPDATE SKIP LOCKED` le claim atomiquement, exécute le pipeline,
  écrit le résultat. Multi-workers safe sans Redis. Latence ~2 s.
- **HTTP synchrone** pour le pre-flight (~1 s) : le backend uploade vers
  `http://preflight-service:8001/preflight` (FastAPI), reçoit le `PreflightReport`
  JSON, persiste anomalies. Pas de polling overhead.

Pour démarrer les 2 services Python associés, voir
[`../poc-scheduler/README.md`](../poc-scheduler/README.md).

## Versioning automatique

**Discipline V1** : chaque mutation CRUD (Workshop, Machine, Client, Order)
crée une nouvelle `Version` dans la même transaction Prisma. La Version
contient un snapshot JSON aggregé (`Workshop` + `machines` + `operators` +
`sharedRes` + `unavailability` + `clients` + `orders` + `jobs` + `operations` +
`softConstraints`).

```ts
// Exemple : ajout d'une machine crée la version automatiquement
return this.prisma.$transaction(async (tx) => {
  const machine = await tx.machine.create({ data: ... });
  await this.versions.createSnapshotInTransaction(
    tx, workshopId, `Ajout machine "${machine.name}"`,
  );
  return machine;
});
```

**Rollback non-destructif** : `POST /versions/:n/rollback` crée une **nouvelle**
version au sommet avec le snapshot de la version cible. L'historique des
versions intermédiaires reste intact (`is_active = false`, mais les rows
restent en DB).

Voir `src/versions/versions.service.ts` pour le détail.

## Validation Pydantic-like côté API

Le `ValidationPipe` global est configuré avec :
```ts
new ValidationPipe({
  whitelist: true,            // strip les champs inconnus
  forbidNonWhitelisted: true, // → HTTP 400 si champ inconnu (équivalent extra="forbid")
  transform: true,            // class-transformer
})
```

Conséquence : un POST `{"name":"X","unknownField":42}` retourne 400, exactement
comme côté Python avec `ConfigDict(extra="forbid")`. Source de vérité unique des
contrats : les DTO de chaque module.

## Conventions de code

- **Strict TypeScript** : `noImplicitAny`, `strictNullChecks`,
  `forceConsistentCasingInFileNames`.
- **Naming DB** : tables `snake_case` au pluriel (`workshops`, `solve_jobs`),
  colonnes `snake_case` mappées via `@map()` aux propriétés `camelCase` Prisma.
- **IDs** : UUID v4 (`@db.Uuid`) partout. Identifiants entiers métier
  (`machine_id_int`, `job_id_int`) conservés pour rester cohérent avec l'engine
  Python qui parle en indices entiers (cf. `src.core.models.Machine.machine_id`).
- **Single-tenant V1** : pas de colonne `tenant_id`. À ajouter en Phase 7
  via migration ; toutes les tables ont déjà un `workshop_id` discriminant qui
  rend l'évolution simple.
- **Erreurs typées** : 400 (validation), 404 (not found), 409 (conflit),
  502 (upstream Python erreur), 503 (upstream Python injoignable).

## Tests

```bash
npm run test:e2e           # 11 tests jest+supertest, ~5s
npm run typecheck          # tsc --noEmit (strict)
npm run lint               # eslint --max-warnings=0
npm run format:check       # prettier --check
```

Couverture e2e (jalon J3 + tests cross-cutting) :
- Workshop create → v1 active
- Reject extra field (HTTP 400)
- Machine create → v2, machineIdInt auto-assigné
- Reject machineIdInt dupliqué (HTTP 409)
- Order create avec gamme 2 ops → v3
- Reject sequence_idx non contigus (HTTP 400)
- Reject machine d'un autre workshop (HTTP 400)
- Rollback crée nouvelle version sans détruire l'historique
- Reject rollback vers version active (HTTP 409)
- Reject rollback vers version inexistante (HTTP 404)
- Snapshot inclut machines + orders + clients

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `DATABASE_URL` | (cf. `.env.example`) | URL Postgres avec `?schema=public` |
| `PORT` | 3000 | Port HTTP du backend |
| `NODE_ENV` | development | mode |
| `LOG_LEVEL` | debug | niveau Nest Logger |
| `PREFLIGHT_SERVICE_URL` | `http://localhost:8001` | URL du service FastAPI Python (J5) |
| `CORS_ORIGIN` | `http://localhost:3001` | Origins CORS autorisées (séparateur virgule). Phase 5 retro-fit pour le frontend Next.js. Verrouillage strict en Phase 7 prod (liste blanche par tenant). |

## Liens

- [`../README.md`](../README.md) : vue d'ensemble du monorepo
- [`../docs/phase-4-report.md`](../docs/phase-4-report.md) : rapport narratif détaillé Phase 4
- [`../docs/phase-5-report.md`](../docs/phase-5-report.md) : rapport Phase 5 (mentionne le retro-fit J3 `/schedule` + CORS)
- [`../docs/v0-status.md`](../docs/v0-status.md) : tracker d'avancement
- [`../frontend/`](../frontend/) : frontend Next.js qui consomme l'API
- [`../poc-scheduler/`](../poc-scheduler/) : moteur Python + worker DB + service preflight
- [`../poc-scheduler/src/core/models.py`](../poc-scheduler/src/core/models.py) :
  modèles Pydantic source de vérité (alignement schéma Prisma)
- [`../docs/specs-techniques-v3.md`](../docs/specs-techniques-v3.md) §3.2 : spec modèle de
  données SaaS
