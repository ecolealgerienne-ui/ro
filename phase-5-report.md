# Rapport d'avancement Phase 5 — Frontend chef d'atelier

> Document narratif complémentaire à `v0-status.md` (tracker structuré).
> Documente les résultats concrets, décisions techniques et métriques de chaque jalon.
> Mis à jour à chaque étape stabilisée.

**Snapshot : 2026-05-01 — Phase 5 ✅ stabilisée (9/9 étapes)**

---

## Synthèse

| Indicateur | Valeur |
|------------|--------|
| Phase courante | 5 — Frontend chef d'atelier |
| Étapes stabilisées | **9/9** (5.1 + 5.2 + 5.3 + 5.4 + 5.5 + 5.6 + 5.7 + 5.8 + 5.9) |
| Jalons internes | **7** (J1 → J7), un commit + smoke test par jalon |
| Routes Next.js | **10** (`/`, `/health`, `/onboarding`, `/workshops/[id]`, `/gantt`, `/conversation`, `/infeasibility`, `/preflight`, `/preflight/[sessionId]`, `/versions`) |
| Composants React | ~30 (5 dashboard + 4 gantt + 3 conversation + 2 preflight + 4 versions + 4 onboarding + ui shadcn + sidebar) |
| Stack | Next.js 15 App Router + React 19 + TS strict + Tailwind 3.4 + shadcn/ui + TanStack Query 5 |
| Retro-fits backend | 2 (CORS allow-origin + endpoint `GET /api/workshops/:wId/schedule`) |
| Smoke tests E2E | 7 (un par jalon) |
| Mockups V0 → pages réelles | **8/8** convertis (5 quotidien + 3 onboarding) |

---

## Repositionnement préliminaire

**Décision 2026-05-01** : Phase 5 livrée avec scope V1 conscient.

| Aspect | V1 livrée | V2 différée |
|--------|-----------|-------------|
| Auth | ❌ pas d'auth (cohérent avec backend Phase 4 V1) | Phase 7 prod : Argon2id + JWT + refresh |
| Multi-tenant UI | ❌ workshop sélectionné par UUID dans URL | Phase 7 prod : workspace switcher tenant-aware |
| LLM live conversationnel | ❌ scénarios scriptés V1 | Endpoint backend dédié pour appeler agents Phase 3 (`SoftConstraintsAgent`, `ExplanationAgent`) |
| Lib Gantt | ✅ custom CSS (DHTMLX/Bryntum payants écartés) | À revoir si scaling > 500 OFs |
| Onboarding arborescent | ✅ ~15 essentielles + 3 conditionnelles | Spec V3 §4 prévoit 80-150 questions, le reste vient en mini-questionnaires V2 |
| Mini-questionnaires contextuels | ✅ banner placeholder V1 | Déclencheurs dynamiques + persistance backend des réponses |

Le découpage interne en **7 jalons J1-J7** correspond aux étapes effectivement
livrées, chacune commitée et smoke-testée séparément.

---

## Jalon J1 (5.1) — Foundation + healthcheck ✅

**Objectif** : foundation Next.js, validation que la stack tient + page healthcheck
qui interroge le backend.

**Livrables**
- `frontend/` : Next.js 15 App Router + React 19 + TS strict (`noImplicitAny`,
  `strictNullChecks`, `forceConsistentCasingInFileNames`)
- Tailwind 3.4 + shadcn/ui (composants manuels, pas de CLI car environnement
  non-interactif) : `Button`, `Card`, `Badge` (variants `tier1/2/3/success/warning`),
  `Separator`
- TanStack Query 5 avec `QueryProvider` (retry intelligent skip 4xx) + DevTools dev
- API client typé `lib/api/client.ts` (`fetch` natif Node 22 + `ApiError`)
- Types miroirs Prisma `lib/api/types.ts` (maintenus à la main, pas d'OpenAPI V1)
- 3 pages : `/` (landing avec liste workshops), `/health` (refresh 5s sur
  `/api/health`), `/workshops/[id]` (placeholder pour J2)

**Smoke test E2E**
```
npm install → typecheck OK → build OK
4 routes générées
curl /health, /, /workshops/[uuid] → tous HTTP 200
```

**Décisions structurantes**
- Pas d'auth V1 (cohérent avec backend, différée Phase 7)
- shadcn/ui en composants manuels (config `components.json` + copie inline) car
  l'env CI/dev ne supporte pas les CLI interactifs
- Tailwind 3.4 (vs. 4 en alpha) pour stabilité shadcn

---

## Jalon J2 (5.4) — Dashboard chef d'atelier ✅

**Objectif** : page d'accueil quotidien avec KPI, alertes, mini-Gantt.

**Livrables**
- Hooks TanStack Query : `useWorkshop`, `useOrders`, `useVersions`, `useSolveJobs`
  (avec refetch interval 2s si pending/running détecté)
- `AppSidebar` : nav 5 entrées (Dashboard, Planning, Conversation, Imports,
  Historique) + version active en pied
- `app/workshops/[id]/page.tsx` orchestre :
  - Header : nom workshop + certifs + boutons actions
  - 4 KPI cards : statut planning (active version), OF avec breakdown tier
    T1/T2/T3, machines + versions count, score de confiance (tone success
    >=80, warning >=60)
  - `AlertsList` (3 sévérités critique/majeur/info, alimentée par solve-jobs
    running et nb OF Tier 1 actifs)
  - `MiniGantt` placeholder (V1, vrai Gantt en J3)
  - 3 quick actions vers `/conversation`, `/preflight`, `/versions`

**Smoke test E2E**
```
Backend seed : workshop + 2 machines + 1 client Safran T1 + 1 OF
curl /workshops/[uuid] HTTP 200, données réelles côté API
```

---

## Jalon J3 (5.5) — Gantt interactif complet ✅

**Objectif** : Gantt par machine × time avec couleurs tier, freeze, side panel
OF cliquable.

**Backend retro-fit** : nouveau module `schedules` avec
`GET /api/workshops/:wId/schedule?versionId=...` (défaut version active, 200 +
null si pas solvé, 404 si version invalide).

**Frontend**
- Hooks `useSchedule(workshopId, versionId?)` + `useTriggerSolve(workshopId)`
  (mutation avec invalidation cache solve-jobs + schedule)
- `components/gantt/` :
  - `types.ts` : helpers `buildOpViews` (jointure assignments × orders pour
    enrichir avec orderRef/client/tier), `applyFilters`, `uniqueClients`
  - `gantt-chart.tsx` : grille machines × time, ticks 60/120 min selon
    makespan, blocs OFs colorés par tier (T1 wine #7f1d1d, T2 orange #c2410c,
    T3 slate #475569), zone freeze 8h overlay bleu clair, click bloc → handler,
    ring amber sur bloc sélectionné
  - `op-detail-panel.tsx` : side panel right (w-96) avec détail OF
    (orderRef, client + tier badge, machine, durée, explication placement)
    + 4 actions qui ouvrent conversation pré-remplie (J4)
  - `gantt-filters.tsx` : selects client/tier/machine + toggle "Zone freeze"
  - `gantt-legend.tsx` : légende couleurs tier
- `app/workshops/[id]/gantt/page.tsx` orchestre, empty state avec bouton
  "Lancer le premier solve" si pas de Schedule, footer avec compteurs +
  badge "Version active"

**Décisions structurantes**
- **Custom CSS** plutôt que lib (DHTMLX/Bryntum payant écartés, frappe-gantt et
  react-calendar-timeline customisation coûteuse). Le mockup V0 a montré que
  la grille `position: absolute` avec `left = start * px_per_min` est lisible
  jusqu'à ~100 OFs.
- **Échelle minutes (depuis 0)** pour V1 : c'est ce que retourne le solveur.
  Le calendar mapping `shiftStart` + `workdays` → vue J/H absolue arrive V2.

**Smoke test E2E**
```
Setup : 2 OFs Safran T1 / Bosch T2 sur 2 machines
POST /solve-jobs → worker Python pickup en ~2s
Resolve : schedule.makespanMin=100, 4 assignments persistées
GET /gantt HTTP 200, version active=true
```

---

## Jalon J4 (5.6 + 5.9) — Conversation + Infaisabilité + linking Gantt ✅

**Décision V1** : pas d'intégration LLM live. Les agents Phase 3
(`SoftConstraintsAgent`, `ExplanationAgent`, etc.) existent côté Python mais
leur invocation depuis le frontend nécessitera un endpoint backend dédié
(`POST /api/workshops/:id/conversations`) en V2. Pour la validation DP, les
scénarios scriptés suffisent à valider l'**UX décisionnelle**.

**Conversation `/workshops/[id]/conversation`**
- Layout 60/40 (chat à gauche, preview impact à droite)
- 4 scenarios scriptés V1 (priorité Safran, décaler OF, geler, prochaine
  échéance) + fallback générique
- **Carte de validation jaune systématique** avant toute action — principe
  directeur "chef d'atelier garde le dernier mot" (specs V3 §6)
- `PreviewPanel` : metrics avec deltas tonifiés (good/bad/neutral) + liste
  OF impactés avec tier badge + garanties
- Suggestion chips, support multi-lignes (Enter envoyer, Shift+Enter newline),
  query param `?q=` pour pré-remplissage depuis Gantt

**Infaisabilité `/workshops/[id]/infeasibility`**
- Liste les `solve_jobs` en `failed`, `decision.kind=REJECT`, ou
  `circuit_breaker.outcome=INFEASIBLE`
- Pour le solve sélectionné : bandeau rouge avec error_message + durée,
  trace transparente du circuit breaker (3 retries, status par tentative,
  extraction MIS si applicable)
- Parse robuste du `mis_summary` text via regex sur le format
  `[KIND] identifier : description` + actions correctives associées (3 types :
  MACHINE_UNAVAILABILITY 🔧, JOB 📦, SHARED_RESOURCE 🔗)
- Actions correctives cliquables → ouvrent conversation pré-remplie
- Mode dégradé "Ignorer Tier 1 strict" qui relance un solve

**Linking Gantt → Conversation**
- Les 4 boutons disabled de `OpDetailPanel` (geler/forcer/expliquer/reporter)
  deviennent des liens vers `/conversation?q=...` pré-remplie avec `{ref}`
  substitué.

**Smoke test E2E**
```
6 routes en HTTP 200 dont /conversation?q=Priorité Safran (prefill OK)
```

---

## Jalon J5 (5.7) — Module Data Quality (upload CSV + 3 niveaux anomalies) ✅

**Objectif** : upload CSV ERP → preflight 3 niveaux → validation par anomaly.
Aucun nouveau code backend (J5 Phase 4 déjà livré).

**Hooks TanStack Query**
- `usePreflightSessions` (liste 50 dernières)
- `usePreflightSession` (détail + anomalies)
- `useUploadPreflight` (multipart `FormData` via fetch direct)
- `useUpdateAnomaly` (PATCH status + résolution texte)

**Composants**
- `UploadZone` : drag-drop + clic + validation taille 5 Mio + extension
  `.csv/.tsv` + auto-redirect vers détail après upload réussi
- `AnomalyRow` : code + ligne + colonne (font-mono) + raw_value rose +
  suggestion + status badge + 3 actions inline si pending (✓ Résoudre avec
  input texte de résolution, Ignorer, Exclure)

**Pages**
- `/workshops/[id]/preflight` : drop zone + liste sessions historiées
  avec badge "Clean" / "N anomalie(s)"
- `/workshops/[id]/preflight/[sessionId]` : 3 tabs colorés (🔴 certain
  bloquant / 🟠 probable / 🔵 surprising), description par tab, footer
  dynamique "N corrections obligatoires avant solve" si pending certain > 0

**Smoke test E2E**
```
Upload CSV 3 lignes via curl multipart
Backend forwarde à FastAPI Python
3 anomalies persistées (1 certain + 2 probable)
GET /preflight HTTP 200, GET /preflight/[id] HTTP 200
```

---

## Jalon J6 (5.8) — UX Versioning (timeline + diff + rollback) ✅

**Objectif** : visualiser l'historique des versions du workshop, comparer
2 versions, faire un rollback non-destructif.

**Hooks**
- `useVersionDetail(workshopId, versionNumber)` (avec snapshot complet)
- `useRollback(workshopId)` (mutation avec invalidation cache complète
  `['workshops', workshopId]`)

**Helper engine-générique** : `compareSnapshots(a, b)` produit `metrics`
(6 KPIs avec deltas tonifiés : Machines/Clients/OFs total + breakdown tier
T1/T2/T3) + `summary` (changements détaillés via regex sur OFs ajoutés/
supprimés, machines, certifs, opérateurs).

**Composants**
- `VersionsTimeline` : liste DESC, click = cible / Shift+click = base, badges
  colorés ACTIVE (emerald) / cible (indigo) / base (amber)
- `DiffPanel` : 6 metrics avec deltas (avant/après + delta tonifié) + summary
  bullet list
- `RollbackCard` : carte de validation systématique jaune (réutilise
  `ValidationCard` de J4), bouton désactivé si version base = active (le
  backend renvoie 409)

**Smoke test E2E**
```
Workshop avec 7 versions historiées
GET /versions HTTP 200
POST rollback v6 → nouvelle v8 active "Rollback vers v6"
Historique des 7 versions intact (pas de delete)
```

---

## Jalon J7 (5.2 + 5.3) — Onboarding arborescent + banner contextuel ✅

**Spec V3 §4** prévoit 80-150 questions dans l'arbre dont chaque DP voit
15-25. **V1 simplifié à ~15 essentielles + 3 conditionnelles**. Les 60+
questions pointues (matrice setup-times, qualifications opérateurs détaillées,
indispos récurrentes) restent V2 dans les mini-questionnaires post-J0.

**Schéma 8 steps** (`components/onboarding/schema.ts`)
- `identity` (nom + ville) → `certifications` (multi-select EN 9100/IATF/ISO)
- `team` (n_op + horaires + jours) → `machines` (liste répétée nom + type)
- `clients` (avec tier 1/2/3) → `setup_dependent` (radio + branche)
- `family_count` (conditionnel : skip si setup_dependent != 'yes')
- `pain_point` (textarea libre, optionnel)

Chaque step a `validate(data)` + optionnel `skipIf(data)` pour l'arborescence.

**Composants wizard**
- `ProgressBar` (dots + pourcentage + bar animée)
- `WhyPanel` (panneau "Pourquoi cette question ?" + carte verte "Onboarding
  progressif" qui désamorce l'objection "80 questions au J0")
- 8 step components dédiés (`IdentityStep`, `CertificationsStep`, `TeamStep`,
  `MachinesStep`, `ClientsStep`, `SetupStep` avec branch hint, `FamilyCountStep`,
  `PainPointStep`)

**Submit handler** (`components/onboarding/submit.ts`)
```ts
async function submitOnboarding(data): Promise<workshopId> {
  // 1. POST /workshops (atelier de base)
  // 2. POST /workshops/:id/machines (séquentiel pour préserver machineIdInt)
  // 3. POST /workshops/:id/clients (avec tier)
  return workshop.id;
}
```
Redirect automatique vers `/workshops/[id]` après création.

**Mini-questionnaires V1 placeholder** (`ProgressiveOnboardingBanner`)
- Apparaît sur le dashboard si l'atelier a entre 25 et 35 jours d'âge
- Contenu statique : "5 questions contextuelles pour affiner le solveur"
- Bouton disabled (V2) — V2 : déclencheurs dynamiques + persistance backend

**Landing améliorée** : bouton "+ Nouvel atelier" + empty state CTA
"Démarrer l'onboarding".

**Smoke test E2E**
```
GET /onboarding HTTP 200
Simulation submit (curl direct API) :
  - POST workshop (Test J7 Onboarding, Paris, 3 op, 2x8 lun-ven)
  - POST 2 machines
  - POST 2 clients
  → 5 versions auto-générées par le versioning embarqué
GET /workshops/[uuid] HTTP 200
```

---

## Architecture finale Phase 5

```
┌───────────────────────────────────────────────────────────────────┐
│  Frontend Next.js 15 (port 3001)                                  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  /onboarding (J7)                                           │  │
│  │  /workshops/[id] dashboard (J2)                             │  │
│  │     ├── /gantt (J3) — custom CSS                            │  │
│  │     ├── /conversation (J4) — scenarios scriptés V1          │  │
│  │     ├── /infeasibility (J4) — parse mis_summary             │  │
│  │     ├── /preflight + /[sessionId] (J5) — multipart upload   │  │
│  │     └── /versions (J6) — timeline + diff + rollback         │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  Stack : React 19 + TS strict + Tailwind + shadcn + TanStack Query │
└───────────────────────────────────────────────────────────────────┘
                              ↓ HTTP (CORS allow http://localhost:3001)
┌───────────────────────────────────────────────────────────────────┐
│  Backend NestJS (port 3000)                                       │
│  + retro-fits Phase 5 :                                           │
│     - CORS enableCors() avec CORS_ORIGIN env                      │
│     - GET /api/workshops/:wId/schedule (J3 needs)                 │
└───────────────────────────────────────────────────────────────────┘
                  ↓ SQL                          ↓ HTTP / poll(2s)
        ┌──────────────────┐         ┌──────────────────┐
        │  PostgreSQL 16   │         │  FastAPI + Worker│
        │                  │         │  Python          │
        └──────────────────┘         └──────────────────┘
```

**5 services applicatifs au total** (4 de Phase 4 + 1 frontend). Tout est local
sans cluster, sans Redis, sans messaging externe.

---

## Démarrage local (5 terminaux)

```bash
# 1. Postgres (idempotent)
cd backend && npm run db:up

# 2. Backend NestJS
cd backend && CORS_ORIGIN=http://localhost:3001 npm run start:dev
# → http://localhost:3000/api

# 3. Worker solves Python
cd poc-scheduler
export DATABASE_URL="postgresql://ro_user:ro_dev_password@localhost:5432/ro_dev"
uv run python scripts/db_worker.py --polling-interval 2

# 4. Service preflight Python
cd poc-scheduler
uv run uvicorn scripts.preflight_service:app --port 8001

# 5. Frontend Next.js
cd frontend && npm run dev
# → http://localhost:3001
```

---

## Métriques globales Phase 5

| Indicateur | Valeur |
|------------|--------|
| Lignes TypeScript ajoutées (frontend/) | ~3 500 |
| Routes Next.js générées | 10 (1 statique + 9 dynamiques côté serveur) |
| Build size First Load JS | ~102 kB shared + 6-9 kB par page |
| Composants React | ~30 |
| Hooks TanStack Query | 11 (Workshop, Orders, Versions, Solve-jobs, Schedule, Preflight x4, VersionDetail, Rollback, TriggerSolve, UploadPreflight, UpdateAnomaly) |
| Mockups V0 → pages réelles | 8/8 (100%) |
| Smoke tests E2E | 7 (un par jalon) |
| Décisions structurantes | 5 (V1 sans auth, custom CSS Gantt, scenarios scriptés vs LLM live, scope onboarding 15+3 vs 80+, mockups jetables) |

---

## Synthèse des décisions structurantes Phase 5

| Décision | Raison | Impact |
|----------|--------|--------|
| Pas d'auth V1 | Cohérent avec backend, pilotes DP en réseau privé | Tout flow accessible directement par UUID, no friction démo |
| Custom CSS Gantt | DHTMLX/Bryntum payants écartés, OSS customisation coûteuse | UX pleinement contrôlée, code prévisible, scaling à V2 si besoin |
| Scenarios scriptés conversation | Endpoint backend LLM = effort important, pas critique pour valider l'UX | UX décisionnelle validable avec DP avant d'engager le backend LLM |
| Onboarding ~15 essentielles + 3 conditionnelles | Spec V3 §4 prévoit 80-150 mais 15-25 par DP, le reste = V2 mini-questionnaires | Install J0 testable, scope V1 réaliste |
| Mockups V0 jetables | UX validée AVANT d'écrire la vraie stack Next.js | Itérations UX sans coût technique, repère les problèmes tôt |
| TanStack Query refetch interval intelligent | Les solve-jobs polling s'aligne sur le worker DB-as-queue Python | UI temps quasi-réel sans WebSocket V1 |
| API client `fetch` natif Node 22 | Pas d'axios, pas d'OpenAPI generator V1 | 0 dep réseau, types miroirs Prisma maintenus à la main |
| Composants shadcn manuels | Env CI/dev non-interactif | Composants copiés inline dans `components/ui/`, pas de `npx shadcn add` |

---

## Restantes à traiter

| Phase | Statut | Quand |
|-------|--------|-------|
| 6 — PWA opérateur | ⬜ | Post-Phase 5, tablette atelier offline-first |
| 7 — Sécurité prod | ⬜ | Auth Argon2id + JWT + multi-tenant + observabilité Loki/Grafana/Tempo + Hetzner |
| 8 — Pilotes DP | ⬜ | Onboarding 5-7 design partners, Gate 2 PMF |

V2 spécifiques Phase 5 (à reprendre quand pertinent) :
- Endpoint backend `POST /api/workshops/:id/conversations` qui invoque les
  agents Phase 3 (live LLM)
- Calendar mapping Gantt vue J/H (utilise `shiftStart` + `workdays` du
  Workshop)
- Drag-drop dans Gantt (couplé avec validation systématique)
- Mini-questionnaires post-J0 dynamiques (déclencheurs + persistance backend)
- Diff JSON profond entre snapshots (V1 = compteurs + summary regex)

---

*Mis à jour à chaque transition de jalon stabilisée.*
