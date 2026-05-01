# Tour guidé — démo end-to-end de **ro**

Ce document explique, pas à pas, comment faire le tour de toutes les
fonctionnalités du produit **ro** à partir de l'atelier vitrine "Mécanique
Précision SAS" généré par le script de seed. Il s'adresse aussi bien à un
développeur qui rejoint le projet qu'à un utilisateur métier (chef d'atelier,
ARO, dirigeant de PME) qui découvre l'IHM. L'accent est mis sur le **pourquoi
métier** de chaque écran, pas seulement sur le clic à effectuer.

---

## 1. Contexte produit

**ro** est un SaaS d'ordonnancement assisté par IA pour les **PME de
sous-traitance mécanique de précision** (typiquement aéro, auto, médical,
défense — clients donneurs d'ordre type Safran, Stellantis, Bosch, ITER).

Le problème métier qu'on résout : dans une PME méca-précision de 5-30 machines,
le chef d'atelier passe **2 à 6 heures par semaine** à replanifier le carnet de
commandes en Excel ou en tête, parce que le réel bouge en permanence (panne
machine, OF urgent, opérateur absent, retard fournisseur). Les ERP de marché
(Sage X3, Cegid, Clipper) gèrent les achats et la facturation, mais sont
notoirement faibles côté capacité finie / ordonnancement temps-réel.

**ro** propose :

- Un **moteur d'ordonnancement** OR-Tools CP-SAT qui place les opérations sur
  les machines en respectant les contraintes (deadlines, opérateurs qualifiés,
  ressources partagées, indisponibilités, freeze 8 h, tier client).
- Une **IHM tactile** pour piloter sans Excel : Gantt, KPIs, alertes,
  conversation en français pour ajuster les contraintes.
- Une **discipline de versioning** (chaque modification crée une version, on
  peut rollback) qui rassure le métier sur le caractère réversible.
- Un **module preflight** qui valide la qualité d'un CSV ERP avant import,
  avec 3 niveaux d'anomalies (certain / probable / surprising).

L'atelier vitrine reproduit fidèlement les caractéristiques d'une PME-cible :
**Mécanique Précision SAS, Saint-Étienne, certifications EN 9100 + IATF 16949,
8 machines (5 tours CN, 2 fraiseuses 5 axes, 1 rectifieuse), 4 clients
(Safran T1, Stellantis T2, Bosch T2, ProtoLab T3), 25 OFs sur 5 jours**.

---

## 2. Démarrer la stack locale

Cinq services à lancer dans 5 terminaux différents (architecture sans
messaging, voir `docs/specs-techniques-v3.md` §3 et `docs/phase-4-report.md`).

```bash
# Terminal 1 — Postgres (via Docker, Phase 4)
cd backend
docker compose up -d
# Vérifie : `docker compose ps` → postgres running, healthy

# Terminal 2 — Backend NestJS (port 3000)
cd backend
npm install
npm run prisma:generate
npm run prisma:migrate    # (au premier démarrage uniquement)
npm run start:dev
# Attends "Backend ro démarré sur http://localhost:3000/api"

# Terminal 3 — Worker Python DB-as-queue
cd poc-scheduler
uv sync
export DATABASE_URL="postgresql://ro_user:ro_dev_password@localhost:5432/ro_dev"
uv run python scripts/db_worker.py --polling-interval 2
# Le worker poll la table solve_jobs toutes les 2 s

# Terminal 4 — Service preflight FastAPI (port 8001)
cd poc-scheduler
uv run uvicorn scripts.preflight_service:app --port 8001

# Terminal 5 — Frontend Next.js (port 3001)
cd frontend
npm install
npm run dev
# Ouvre http://localhost:3001
```

> **Pourquoi 5 services ?** Séparation des responsabilités : Postgres gère la
> persistance et la queue ; le backend NestJS expose l'API et applique les
> règles métier ; le worker Python exécute les solves longs (10-60 s) sans
> bloquer l'API ; le service preflight expose le module Python d'analyse CSV
> sous forme d'endpoint synchrone ; le frontend est une SPA qui ne parle qu'au
> backend.

---

## 3. Peupler la base : un seul script

Une fois les 5 services lancés, dans un 6ᵉ terminal :

```bash
cd poc-scheduler
uv run python scripts/seed_via_api.py
```

Ce script (`scripts/seed_via_api.py`) :

1. **Reset** : DELETE de tous les workshops existants (cascade Prisma sur
   machines, clients, ordres, versions). Idempotent — tu peux le rejouer à
   l'infini sans accumuler de données.
2. **Crée** l'atelier vitrine + 8 machines + 4 clients + 25 OFs via l'API
   REST (pas d'INSERT direct en DB → ça teste aussi le backend).
3. **Génère 3 CSVs de démo** dans `poc-scheduler/data/seed-fixtures/`
   (`clean.csv`, `realistic.csv`, `broken.csv`) et les uploade via le module
   preflight.
4. **Déclenche un solve** : POST sur `/solve-jobs`, attend que le worker
   Python finisse (~1 s pour 25 OFs), vérifie que le Schedule est créé.

À la fin tu dois voir un récap latence (50 appels HTTP, ~900 ms total).
Si une erreur apparaît, vérifie que les 5 services tournent (le script logue
clairement quel endpoint a échoué).

---

## 4. Tour de l'IHM

Ouvre `http://localhost:3001` dans le navigateur.

### 4.1 Page d'accueil — `/`

**Ce que tu vois** : la liste des ateliers configurés. Après le seed, un seul
atelier est visible : "Mécanique Précision SAS" avec le résumé `8 machines
· 25 OF · v38 versions`.

**Pourquoi c'est là** : ro est multi-atelier dès le V1 — un dirigeant peut
gérer plusieurs sites depuis le même compte. La carte donne en un coup d'œil
la santé de chaque atelier (combien d'OFs, combien de versions historisées).

**Action** : clique "Ouvrir →" pour entrer dans le dashboard.

> **Note** : si tu as gardé un onglet ouvert avec une URL contenant un ancien
> UUID d'atelier (avant un reset), tu verras la page d'erreur "Cet atelier
> n'existe plus" avec un bouton retour. C'est volontaire — un commit récent
> a remplacé un message d'erreur dead-end par cette UX.

### 4.2 Dashboard atelier — `/workshops/<id>`

**Ce que tu vois** :

- **En-tête** : nom + ville + certifications (EN 9100 + IATF 16949) +
  6 opérateurs.
- **4 KPIs** :
  - *Statut planning* : v38 actif (vert) ou — (gris).
  - *OF planifiés* : 25, ventilés par tier (3 T1 critique / 14 T2 standard /
    8 T3 opportuniste).
  - *Machines* : 8.
  - *Score de confiance* : 87/100 + verdict simulation (ACCEPT/WARN/REJECT).
- **Bandeau alertes** : alertes contextuelles (solve en cours, simulation
  WARN, présence d'OF Tier 1).
- **Mini-Gantt** : aperçu condensé des 25 affectations.
- **3 cartes d'action** : démarrer une conversation IA, importer un CSV ERP,
  consulter l'historique des versions.

**Pourquoi c'est là** : c'est l'écran de prise de température matinale d'un
chef d'atelier. En 30 secondes il sait si le planning de la journée tient,
combien d'OFs Tier 1 sont en cours (= visibilité sur les engagements aéro à
forte pénalité contractuelle), et si l'IA détecte un risque opérationnel
(verdict simulation).

**Pourquoi le score de confiance** : un planning peut être *mathématiquement*
optimal mais *opérationnellement* fragile (trop de fragmentations
machine/jour, freeze 8 h trop serré, dépendance forte à un opérateur unique
qualifié). Le score de confiance — calculé sur 4 métriques — chiffre cette
fragilité de 0 à 100. En-dessous de 60, le métier doit reprendre la main.

### 4.3 Gantt complet — `/workshops/<id>/gantt`

**Ce que tu vois** : le planning détaillé sur ~5 jours, machine par machine,
en horizontal. Chaque rectangle est une opération, coloré par client (rouge
Safran, orange Stellantis, ambre Bosch, gris ProtoLab). Au-dessus : barre de
filtres (par client, par machine, par tier) et bouton "Replanifier".

**Filtres et freeze 8h** :
- Le freeze 8 h est une règle métier critique : les opérations qui
  *commencent* dans les 8 prochaines heures sont considérées comme
  "engagées" et ne peuvent plus bouger (changeover préparé, opérateur
  briefé). Le toggle freeze grise visuellement cette zone.
- Cliquer sur un rectangle ouvre le panneau détail à droite : OF, client,
  durée, machine, deadline, opérateurs qualifiés.

**Pourquoi c'est là** : le Gantt est l'écran le plus consulté dans la
journée. Il remplace l'Excel à colonnes-jours qui traîne dans 80 % des PME
méca précision. Le code couleur par client est métier-significant :
visuellement on voit immédiatement si la "ligne Safran" est saturée ou s'il
reste de la capacité Bosch.

**Action conseillée** : clique "Replanifier" → on observe le solve dans la
section suivante.

### 4.4 Replanifier — déclencher un solve

**Ce qui se passe sous le capot** quand tu cliques "Replanifier" :

1. Le frontend POST `/api/workshops/<id>/solve-jobs`. Le backend insère une
   ligne `solve_jobs` avec `status=pending` et retourne immédiatement.
2. Le worker Python (terminal 3) poll cette table toutes les 2 s avec
   `FOR UPDATE SKIP LOCKED` (pattern DB-as-queue). Il claim le job, passe
   son statut à `running`.
3. Le worker reconstitue un `WorkshopInstance` Pydantic à partir du snapshot
   JSON de la version active, lance le pipeline complet (CP-SAT + simulation
   + scoring + circuit breaker) et upserte le `Schedule`.
4. Le frontend, qui poll `/solve-jobs/<id>` toutes les 1.5 s, voit le statut
   passer `pending` → `running` → `done` et rafraîchit le Gantt.

**Durée typique** sur l'atelier vitrine : ~1 s (25 OFs, 1 op chacun).
Sur un atelier à 200 OFs et 8 ops par OF, le solve peut prendre 30-60 s.

**Pourquoi DB-as-queue et pas Redis/BullMQ** : éviter une 6ᵉ infra à
opérer. Postgres gère 10 jobs/s en queue sans transpirer, et la transaction
locks des données + jobs garde la cohérence. Voir
`docs/specs-techniques-v3.md` §3.4 pour la rationale architecturale.

### 4.5 Preflight (import CSV) — `/workshops/<id>/preflight`

**Ce que tu vois** : un formulaire d'upload + la liste des sessions
preflight passées (avec leurs anomalies en compteur).

**À tester avec les 3 fixtures** dans `poc-scheduler/data/seed-fixtures/`
(commitées dans le repo, voir leur README) :

#### a) `clean.csv` — le cas heureux

8 colonnes canoniques propres (`order_id`, `client`, `piece_name`,
`material`, `operation_type`, `machine`, `duration_min`, `deadline`).
Tu uploades, tu vois "0 anomalie, 8/8 lignes importables". Bouton "Importer"
disponible.

**Pourquoi c'est rare** : en pratique, presque aucun export ERP n'est aussi
propre. Ce fichier sert de référence et permet de valider que le pipeline
fonctionne.

#### b) `realistic.csv` — le cas du quotidien

10 lignes, en-têtes synonymes ERP type Sage X3 (`no_of`, `ref_client`,
`duree_min`…) que le pipeline reconnaît automatiquement via les regex de
`MECH_COLUMN_PATTERNS`. Mais 2-3 valeurs douteuses :
- une ligne avec durée `"3h30"` au lieu de minutes (est-ce 3 min 30, 3 h 30,
  ou 330 ?) → anomalie **probable** : on demande à l'utilisateur ou un LLM
  de trancher.
- une ligne avec `client` vide → anomalie **probable**.
- une ligne avec durée `1440` minutes (= 24 h) → anomalie **surprising** :
  c'est techniquement valide mais inhabituel, on prévient sans bloquer.

**Pourquoi 3 niveaux** :
- *certain* : le système est sûr que c'est faux (ex: durée négative,
  colonne obligatoire absente). Bloquant.
- *probable* : forte présomption d'erreur, mais on laisse l'humain
  trancher. Non-bloquant après validation.
- *surprising* : juste hors-norme, signalé pour transparence. Ack only.

Cette discipline évite le piège des "warnings que personne ne lit" — chaque
niveau a une UX et une politique d'escalade différentes.

#### c) `broken.csv` — le cas catastrophe

3 lignes avec colonne `duration_min` totalement absente. Anomalie **certain**
bloquante. Le bouton "Importer" est désactivé tant que ce n'est pas corrigé.

**Pourquoi un fichier broken volontairement** : on veut s'assurer que le
système refuse fermement et explique clairement, plutôt que d'accepter un
import partiel qui pollue ensuite la planification.

### 4.6 Versions & rollback — `/workshops/<id>/versions`

**Ce que tu vois** : la timeline des versions historisées de l'atelier,
avec auteur, date, message, OF count, makespan. La version active est
marquée en vert ("v38 actif").

Chaque mutation backend (création OF, modification machine, solve,
correction preflight) crée automatiquement une version qui snapshot l'état
complet de l'atelier au format JSON. C'est implémenté via
`VersionsService.createSnapshotInTransaction` appelé depuis chaque service
mutator.

**Action** : clique "Comparer" entre v37 et v38 → on voit le diff (ex:
+25 OFs, +Schedule fraîchement solvé). Bouton "Restaurer cette version"
sur n'importe quelle version inactive.

**Pourquoi c'est central métier** : un chef d'atelier qui hésite à appliquer
une recommandation IA aura beaucoup moins peur s'il sait qu'il peut revenir
en un clic à l'état d'avant. C'est aussi un audit trail compliance utile en
contexte EN 9100 / IATF 16949 (traçabilité des décisions de planning).

### 4.7 Conversation IA — `/workshops/<id>/conversation`

**Ce que tu vois** : une interface de chat avec un assistant IA qui
comprend des instructions en français naturel.

**Scénarios scriptés V1** (le LLM live arrive en V2) :
- *"Priorité 1 sur Safran cette semaine, j'ai une visite client jeudi."*
- *"Bloque la rectifieuse RC-1 vendredi de 14 h à 18 h pour maintenance."*
- *"Décale les OFs Stellantis non-critiques à la semaine prochaine."*

L'assistant analyse l'impact (combien d'OFs déplacés, gain/perte de
makespan, conflits éventuels), affiche un **diff avant/après lisible**, et
propose une carte de validation "Appliquer cette modification ?" qui crée
une nouvelle version si acceptée, ou est jetée si refusée.

**Pourquoi c'est différenciant** : le métier ne sait pas (et n'a pas envie
d'apprendre) à manipuler des contraintes solveur. La conversation traduit
une intention métier ("on rend Safran prioritaire") en pondérations CP-SAT
(boost du `priority_weight` du client tier 1, ou bascule en mode
hard-priority). C'est le canal principal qui fait passer ro d'un outil
d'optimisation à un copilote.

### 4.8 Infaisabilité — `/workshops/<id>/infeasibility`

**Quand cette page apparaît** : si un solve renvoie `INFEASIBLE` (le solveur
n'arrive pas à placer tous les OFs malgré 3 budgets temps croissants), le
circuit breaker extrait un **MIS** (Minimal Infeasible Subset) : le plus
petit sous-ensemble de contraintes qui rend le problème infaisable.

**Ce que tu vois** : la page liste 1 à 3 causes plausibles (formulées en
français métier, pas en jargon CP-SAT) avec pour chacune une **action
corrective proposée** :
- *"Indispo CN-3 vendredi 14-18 h bloque 2 OFs Safran avec deadline lundi"*
  → action : reporter la maintenance.
- *"OF-2026-0892 (45 h sur FR-2) trop long pour la fenêtre restante"* →
  action : décaler à la semaine prochaine.
- Plus une **alternative dégradée** : "ignorer la priorité Tier 1" avec
  estimation d'impact.

**Pourquoi c'est précieux** : 90 % des outils d'ordonnancement crashent ou
renvoient un message technique sur infaisabilité. ro reformule en
contraintes métier et propose des leviers actionnables — chaque levier
correspond à une mutation API que l'utilisateur peut déclencher en un clic.

### 4.9 Onboarding — `/onboarding`

**Ce que tu vois** : un wizard de 15 questions essentielles découpé en
3 étapes (atelier → ressources → premier import) qui crée un atelier
vierge.

**Pourquoi 15 questions** : on a calibré ce nombre pour rester sous
10 minutes de saisie tout en collectant le strict minimum pour qu'un solve
soit possible (machines, opérateurs, calendrier, premier CSV). C'est la
porte d'entrée du produit pour un nouveau client.

**Action conseillée pour la démo** : laisse l'atelier vitrine en l'état et
crée un 2ᵉ atelier à blanc via l'onboarding pour montrer le parcours
greenfield. Tu peux ensuite le supprimer (ou le garder, le seed le
nettoiera au prochain run).

### 4.10 Healthcheck — `/health`

Page de diagnostic minimaliste : ping backend, ping DB, version de chaque
service. Utile en démo quand un service tombe — on identifie en 5 secondes
lequel.

---

## 5. Stress-test : générer plusieurs ateliers

Pour démontrer la scalabilité multi-tenant simulée :

```bash
cd poc-scheduler
uv run python scripts/seed_via_api.py seed --stress 5
```

Crée 5 ateliers paramétriques additionnels (5-6 machines, 20-30 OFs chacun)
via le générateur synthétique méca. La page d'accueil les liste tous —
clique sur n'importe lequel pour valider que le solve marche aussi sur des
configurations qu'on n'a pas curées à la main.

**Pourquoi c'est utile** : en démo investisseur ou prospect multi-sites, on
montre 6 ateliers actifs simultanément. Au-delà de la démo, c'est aussi un
test de charge léger qui valide qu'on tient le coup sur des configurations
variées.

---

## 6. Cheat-sheet des commandes

| Action | Commande |
|--------|----------|
| Reset DB seul (sans seed) | `uv run python scripts/seed_via_api.py reset` |
| Seed seul (sans reset, ajout) | `uv run python scripts/seed_via_api.py seed` |
| Reset + seed (default, **idempotent**) | `uv run python scripts/seed_via_api.py` |
| + N ateliers stress | `uv run python scripts/seed_via_api.py seed --stress N` |
| Lancer le worker Python | `uv run python scripts/db_worker.py --polling-interval 2` |
| Lancer le service preflight | `uv run uvicorn scripts.preflight_service:app --port 8001` |
| Pre-flight CLI seul (sans IHM) | `uv run python scripts/preflight_check.py <csv>` |
| Suite de tests rapide | `uv run pytest -m "not slow"` (~ 65 s) |
| Suite complète | `uv run pytest` (~ 110 s, 382 tests) |

---

## 7. Pour aller plus loin

- **Specs produit** : `docs/specs-fonctionnelles-v3.md`.
- **Specs techniques** : `docs/specs-techniques-v3.md` (modèle de données,
  archi DB-as-queue, contrats API).
- **Rapports phase par phase** : `docs/phase-{0,1,2,3,4,5}-report.md` —
  contexte, décisions et trade-offs de chaque jalon livré.
- **Conventions de contribution** : `CONTRIBUTING.md` — discipline
  multi-verticale (engine ↔ verticale méca), règles frontend Next.js,
  workflow git.
- **Suivi d'avancement** : `docs/v0-status.md` — état par phase, journal
  des décisions.

---

## 8. Récap : que démontre cet exemple ?

En faisant le tour ci-dessus tu as utilisé, dans l'ordre :

- Le seed script idempotent (reset + 25 OFs vitrine + 3 CSVs preflight + 1 solve).
- 5 services qui dialoguent sans messaging (Postgres, NestJS, worker
  Python, FastAPI preflight, Next.js).
- Un pipeline d'ordonnancement complet (solve → simulation → scoring →
  circuit breaker → MIS).
- Un module preflight 3 niveaux d'anomalies sur 3 fichiers CSV de qualité
  variable.
- Le versioning automatique avec rollback.
- La conversation IA pour ajuster en français.
- L'écran d'infaisabilité avec actions correctives.
- L'onboarding 15 questions.

C'est l'intégralité du parcours utilisateur V1 (Phases 0 à 5 closes), sur
une PME-cible réaliste. Si quelque chose ne marche pas pendant la démo,
relance le seed — il remet tout d'aplomb en moins de 2 secondes.
