# Frontend ro — chef d'atelier (Phase 5 close)

Next.js 15 (App Router) + React 19 + TypeScript strict + Tailwind 3.4 +
shadcn/ui + TanStack Query 5. **Sans auth V1** (cohérent avec backend, différé
Phase 7).

## État (Phase 5 — close, 9/9 étapes stabilisées)

| Jalon | Étape spec | Statut | Livrable |
|-------|------------|--------|----------|
| **J1** | 5.1 | ✅ | Skeleton Next.js 15 + Tailwind + shadcn/ui + TanStack Query + page `/health` |
| **J2** | 5.4 | ✅ | Dashboard `/workshops/[id]` (KPI + alertes + mini-Gantt) |
| **J3** | 5.5 | ✅ | Gantt interactif `/gantt` (custom CSS, freeze, side panel OF) |
| **J4** | 5.6 + 5.9 | ✅ | Conversation `/conversation` (scénarios scriptés V1 + carte de validation systématique) + Infaisabilité `/infeasibility` (parse MIS + actions correctives) |
| **J5** | 5.7 | ✅ | Upload CSV `/preflight` + UX 3 niveaux d'anomalies `/preflight/[sessionId]` |
| **J6** | 5.8 | ✅ | Versioning `/versions` (timeline + diff + rollback non-destructif) |
| **J7** | 5.2 + 5.3 | ✅ | Onboarding arborescent `/onboarding` (8 steps + branchement conditionnel) + banner contextuel V1 |

Détails complets : [`../phase-5-report.md`](../phase-5-report.md).

**V2 différée** (post-Phase 5) :
- Endpoint backend `POST /api/workshops/:id/conversations` qui invoque les
  agents Phase 3 (LLM live, remplace les scénarios scriptés du J4)
- Calendar mapping Gantt vue J/H absolue (utilise `shiftStart` + `workdays`)
- Drag-drop dans Gantt (couplé avec validation systématique)
- Mini-questionnaires post-J0 dynamiques (déclencheurs + persistance backend)
- Diff JSON profond entre snapshots (V1 = compteurs + summary regex)

## Stack

- Node.js 20+ (testé Node 22), npm 10+
- Next.js 15 App Router + React 19
- TypeScript 5 strict (`noImplicitAny`, `strictNullChecks`,
  `forceConsistentCasingInFileNames`)
- Tailwind 3.4 + shadcn/ui (config manuelle, composants copiés inline car
  l'environnement ne supporte pas le CLI interactif `npx shadcn add`)
- TanStack Query 5 (queries + mutations + DevTools dev only)
- `class-variance-authority` + `clsx` + `tailwind-merge` (variants shadcn)
- `prettier-plugin-tailwindcss` (tri auto des classes)
- `@radix-ui/react-slot` + `@radix-ui/react-separator` (primitives shadcn)
- `lucide-react` (icônes optionnelles)

Pas d'axios, pas d'OpenAPI generator V1 : `fetch` natif Node 22 + types
miroirs Prisma maintenus à la main dans `lib/api/types.ts`.

## Démarrage rapide

```bash
# 1. Installer les dépendances
npm install

# 2. Copier l'env (pointe sur le backend NestJS local)
cp .env.example .env.local

# 3. Lancer le dev
npm run dev               # http://localhost:3001
```

Prérequis : le **backend NestJS** doit tourner sur `http://localhost:3000`
avec CORS allow-origin sur `http://localhost:3001` :

```bash
# Côté backend (dans ../backend/)
CORS_ORIGIN=http://localhost:3001 npm run start:dev
```

Pour le **flow complet** (Gantt + Conversation + Preflight), il faut aussi
démarrer le worker Python + service preflight FastAPI (cf.
[`../poc-scheduler/README.md`](../poc-scheduler/README.md)).

## Routes livrées (10 au total)

| Route | Jalon | Description |
|-------|-------|-------------|
| `/` | J1 | Landing — liste des workshops + bouton "+ Nouvel atelier" + lien `/health` |
| `/health` | J1 | Healthcheck backend + DB (refresh 5s, badges status/database/uptime) |
| `/onboarding` | J7 | Wizard install J0 — 8 steps, ~15 questions essentielles + 3 conditionnelles, submit crée Workshop + machines + clients |
| `/workshops/[id]` | J2 | Dashboard chef d'atelier — 4 KPI (statut, OF tier, machines, score), alertes 3 sévérités, mini-Gantt, banner onboarding progressif |
| `/workshops/[id]/gantt` | J3 | Gantt interactif — grille machines × time, blocs colorés par tier T1/T2/T3, zone freeze 8h, side panel OF avec actions |
| `/workshops/[id]/conversation` | J4 | Chat scénarios scriptés V1 + **carte de validation systématique** + preview impact (metrics deltas + OF impactés) |
| `/workshops/[id]/infeasibility` | J4 | Liste solve-jobs en échec, trace circuit breaker (3 retries), parse `mis_summary` → causes structurées, actions correctives → conversation pré-remplie |
| `/workshops/[id]/preflight` | J5 | Drop zone CSV + liste sessions historiées (badges Clean/N anomalies) |
| `/workshops/[id]/preflight/[sessionId]` | J5 | 3 tabs (🔴 certain / 🟠 probable / 🔵 surprising), 3 actions par anomaly (Résoudre/Ignorer/Exclure), footer dynamique gating |
| `/workshops/[id]/versions` | J6 | Timeline + diff (6 metrics tonifiés) + rollback non-destructif avec validation systématique |

Toutes les routes `/workshops/[id]/*` partagent le layout avec `AppSidebar`
(6 entrées nav).

## Architecture (5 services en local)

```
┌──────────────────────┐
│  Frontend Next.js 15 │  ← TU ES ICI
│  (port 3001)         │
└──────────┬───────────┘
           │ HTTP (CORS allow-origin localhost:3001)
           ▼
┌──────────────────────┐         ┌──────────────┐
│  Backend NestJS      │ ──SQL──→│  PostgreSQL  │
│  (port 3000)         │         │   16-alpine  │
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
```

Détails dans [`../README.md`](../README.md) section Architecture +
[`../phase-{4,5}-report.md`](../phase-5-report.md).

## Conventions

- **Strict TypeScript** : `strict: true`, `noImplicitAny`, `strictNullChecks`,
  `forceConsistentCasingInFileNames`. `npm run typecheck` doit passer
  silencieusement.
- **Path alias** : `@/*` → racine du projet (`@/components/...`, `@/lib/...`)
- **Server Components par défaut**, `'use client'` uniquement quand nécessaire
  (interactivité, hooks TanStack Query, state local)
- **Composants shadcn** dans `components/ui/` (manuels, pas via CLI car
  l'environnement ne supporte pas l'interactif). Si tu ajoutes un composant,
  copie depuis [ui.shadcn.com](https://ui.shadcn.com) en respectant les paths
  des aliases.
- **API client** : `lib/api/client.ts` (typed `fetch` + `ApiError`),
  `lib/api/types.ts` (miroirs Prisma maintenus à la main, **synchroniser à la
  main** si le schéma backend change), `lib/api/hooks.ts` (TanStack Query)
- **Pas d'auth V1** — l'utilisateur ouvre directement les workshops par UUID
  dans l'URL
- **Refetch interval intelligent** : `useSolveJobs` poll toutes les 2 s **si**
  un job pending/running est détecté, sinon désactivé (économise les requêtes)
- **Validation systématique** avant action — composant `ValidationCard`
  réutilisable (J4 + J6 rollback)

## Structure

```
frontend/
├── package.json
├── tsconfig.json                 # strict TS + path alias @/*
├── next.config.mjs
├── tailwind.config.ts            # CSS variables shadcn (slate base)
├── postcss.config.mjs
├── components.json               # config shadcn
├── .env.example                  # NEXT_PUBLIC_API_URL
├── app/
│   ├── layout.tsx                # root layout + Inter font + QueryProvider
│   ├── page.tsx                  # landing /
│   ├── globals.css               # tailwind base + couleurs tier
│   ├── health/page.tsx
│   ├── onboarding/page.tsx       # wizard J0 install (J7)
│   └── workshops/[id]/
│       ├── layout.tsx            # AppSidebar
│       ├── page.tsx              # Dashboard (J2)
│       ├── gantt/page.tsx        # Gantt (J3)
│       ├── conversation/page.tsx # Chat + validation (J4)
│       ├── infeasibility/page.tsx # MIS diagnostic (J4)
│       ├── preflight/
│       │   ├── page.tsx          # Liste + upload (J5)
│       │   └── [sessionId]/page.tsx # Détail anomalies (J5)
│       └── versions/page.tsx     # Timeline + diff + rollback (J6)
├── components/
│   ├── ui/                       # shadcn (button, card, badge, separator)
│   ├── app-sidebar.tsx
│   ├── dashboard/                # kpi-card, alerts-list, mini-gantt, progressive-onboarding-banner
│   ├── gantt/                    # gantt-chart, op-detail-panel, gantt-filters, gantt-legend, types
│   ├── conversation/             # validation-card, scenarios.ts, preview-panel
│   ├── preflight/                # upload-zone, anomaly-row
│   ├── versions/                 # versions-timeline, diff-panel, rollback-card, compare.ts
│   └── onboarding/               # progress-bar, why-panel, steps, schema, submit
└── lib/
    ├── utils.ts                  # cn() helper (clsx + tailwind-merge)
    ├── query-provider.tsx        # QueryClient + DevTools
    └── api/
        ├── client.ts             # fetch wrapper + ApiError
        ├── types.ts              # types miroirs Prisma maintenus main
        └── hooks.ts              # 11 hooks TanStack Query
```

## Hooks TanStack Query (11 au total)

| Hook | Type | Usage |
|------|------|-------|
| `useWorkshops` | query | Liste workshops (landing) |
| `useWorkshop` | query | Détail workshop avec machines + clients |
| `useOrders` | query | Liste OFs avec client + job |
| `useVersions` | query | Liste versions DESC sans snapshot |
| `useVersionDetail` | query | Version avec snapshot complet |
| `useSchedule` | query | Schedule de la version active ou spécifique |
| `useSolveJobs` | query | Liste solve-jobs avec refetch 2s si pending |
| `usePreflightSessions` | query | Liste sessions preflight |
| `usePreflightSession` | query | Détail session + anomalies |
| `useTriggerSolve` | mutation | POST solve-job + invalidation cache |
| `useRollback` | mutation | POST rollback + invalidation cache complète |
| `useUploadPreflight` | mutation | Multipart FormData upload |
| `useUpdateAnomaly` | mutation | PATCH status anomaly |

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:3000/api` | URL du backend NestJS |

## Scripts

| Script | Effet |
|--------|-------|
| `npm run dev` | Dev server avec HMR (port 3001) |
| `npm run build` | Build production (génère 10 routes) |
| `npm run start` | Serveur production (port 3001) |
| `npm run typecheck` | `tsc --noEmit` strict |
| `npm run lint` | ESLint via `next lint` |
| `npm run format` | Prettier (avec tri des classes Tailwind) |
| `npm run format:check` | Prettier check (sans modifier) |

## Smoke test E2E

```bash
# 1. Démarrer les 4 services backend (depuis racine du repo)
cd backend && npm run db:up
cd backend && CORS_ORIGIN=http://localhost:3001 npm run start:dev &
cd poc-scheduler && DATABASE_URL=... uv run python scripts/db_worker.py &
cd poc-scheduler && uv run uvicorn scripts.preflight_service:app --port 8001 &

# 2. Démarrer le frontend
cd frontend && npm run dev

# 3. Parcours complet
open http://localhost:3001/onboarding         # crée un atelier
# Wizard 8 steps → submit → redirect /workshops/[id]
open http://localhost:3001/workshops/[uuid]/gantt          # planning
open http://localhost:3001/workshops/[uuid]/conversation   # chat + validation
open http://localhost:3001/workshops/[uuid]/preflight      # upload CSV
open http://localhost:3001/workshops/[uuid]/versions       # rollback
open http://localhost:3001/workshops/[uuid]/infeasibility  # diagnostic
```

## Liens

- [`../README.md`](../README.md) : vue d'ensemble du monorepo
- [`../phase-5-report.md`](../phase-5-report.md) : rapport narratif détaillé
  Phase 5 (7 jalons J1-J7, 8 décisions structurantes)
- [`../backend/README.md`](../backend/README.md) : backend NestJS qui sert l'API
- [`../poc-scheduler/README.md`](../poc-scheduler/README.md) : moteur Python +
  worker DB-as-queue + service FastAPI preflight
- [`../mockups/`](../mockups/) : mockups HTML statiques V0 (jetables, archivés
  en référence)
- [`../specs-fonctionnelles-v3.md`](../specs-fonctionnelles-v3.md) §5 : spec
  UX chef d'atelier
- [`../v0-status.md`](../v0-status.md) : tracker d'avancement par étape
