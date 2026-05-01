# Frontend ro — chef d'atelier (Phase 5)

Next.js 15 (App Router) + TypeScript strict + Tailwind 3 + shadcn/ui +
TanStack Query. **Sans auth V1** (cohérent avec backend, différé Phase 7).

## État (Phase 5 — en cours, J1+J2 livrés)

| Jalon | Étape spec | Statut | Livrable |
|-------|------------|--------|----------|
| **J1** | 5.1 | ✅ | Skeleton Next.js 15 + Tailwind + shadcn/ui + TanStack Query + page `/health` |
| **J2** | 5.4 | ✅ | Dashboard `/workshops/[id]` (KPI + alertes + mini-Gantt) |
| J3 | 5.5 | ⬜ | Gantt interactif complet (couleurs tier, freeze, side panel OF) |
| J4 | 5.6 + 5.9 | ⬜ | Conversation + validation + module infaisabilité |
| J5 | 5.7 | ⬜ | Upload CSV + UX 3 niveaux d'anomalies |
| J6 | 5.8 | ⬜ | Versioning (timeline + diff + rollback) |
| J7 | 5.2 + 5.3 | ⬜ | Onboarding arborescent (le plus complexe, en fin) |

## Stack

- Node.js 20+, npm 10+
- Next.js 15 (App Router) + React 19
- TypeScript 5 strict
- Tailwind 3.4 + shadcn/ui (config manuelle, pas de CLI)
- TanStack Query 5 (fetch backend, refetch intervals)
- `class-variance-authority` + `clsx` + `tailwind-merge` (variants)
- `prettier-plugin-tailwindcss` (tri des classes)

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
(cf. [`../backend/README.md`](../backend/README.md)). Sans backend, la page
landing affichera l'erreur "Backend injoignable".

## Pages livrées

| Route | Description |
|-------|-------------|
| `/` | Landing — liste des workshops (ouvre dashboard sur clic) + lien vers `/health` |
| `/health` | Healthcheck backend + DB (refresh 5s) |
| `/workshops/[id]` | Dashboard chef d'atelier (KPI + alertes + mini-Gantt) |
| `/workshops/[id]/...` | À venir : `/gantt`, `/conversation`, `/preflight`, `/versions` (J3-J6) |

## Conventions

- **Strict TypeScript** : `strict: true`, `noImplicitAny`, `strictNullChecks`
- **Path alias** : `@/*` → racine du projet (`@/components/...`, `@/lib/...`)
- **Composants shadcn** dans `components/ui/` (manuels, pas via CLI car
  l'environnement ne supporte pas l'interactif)
- **Server Components par défaut**, `'use client'` uniquement quand nécessaire
  (interactivité, hooks TanStack Query, etc.)
- **API client** : `lib/api/client.ts` (typed `fetch`), `lib/api/types.ts`
  (miroirs Prisma maintenus à la main), `lib/api/hooks.ts` (TanStack Query)
- **Pas d'auth V1** — l'utilisateur ouvre directement les workshops par UUID

## Structure

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── components.json           # config shadcn (références aliases)
├── .env.example
├── app/
│   ├── layout.tsx            # root layout + QueryProvider
│   ├── page.tsx              # landing (/)
│   ├── globals.css           # tailwind base + couleurs tier
│   ├── health/page.tsx
│   └── workshops/[id]/
│       ├── layout.tsx        # AppSidebar
│       └── page.tsx          # Dashboard
├── components/
│   ├── ui/                   # shadcn (button, card, badge, separator)
│   ├── app-sidebar.tsx       # nav latérale
│   └── dashboard/
│       ├── kpi-card.tsx
│       ├── alerts-list.tsx
│       └── mini-gantt.tsx
└── lib/
    ├── utils.ts              # cn() helper
    ├── query-provider.tsx
    └── api/
        ├── client.ts         # fetch wrapper + ApiError
        ├── types.ts          # types miroirs Prisma
        └── hooks.ts          # useWorkshop / useOrders / useVersions / useSolveJobs
```

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:3000/api` | URL du backend NestJS |

## Scripts

| Script | Effet |
|--------|-------|
| `npm run dev` | Dev server avec HMR (port 3001) |
| `npm run build` | Build production |
| `npm run start` | Serveur production (port 3001) |
| `npm run typecheck` | `tsc --noEmit` strict |
| `npm run lint` | ESLint via `next lint` |
| `npm run format` | Prettier (avec tri des classes Tailwind) |

## Smoke test

```bash
# 1. Démarrer Postgres + backend (depuis ../backend/)
cd ../backend && npm run db:up && npm run start:dev

# 2. Démarrer le frontend
cd ../frontend && npm run dev

# 3. Tester
open http://localhost:3001/                  # landing
open http://localhost:3001/health            # backend health
open http://localhost:3001/workshops/<uuid>  # dashboard d'un workshop
```

## Liens

- [`../README.md`](../README.md) : vue d'ensemble du monorepo
- [`../backend/README.md`](../backend/README.md) : backend NestJS qui sert l'API
- [`../mockups/`](../mockups/) : mockups HTML statiques (sources d'inspiration UX)
- [`../specs-fonctionnelles-v3.md`](../specs-fonctionnelles-v3.md) §5 : spec UX chef d'atelier
- [`../v0-status.md`](../v0-status.md) : tracker d'avancement
