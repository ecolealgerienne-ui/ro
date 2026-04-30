# Spec technique V3 — SaaS d'ordonnancement IA pour la sous-traitance mécanique PME

> Document technique complémentaire à la spec fonctionnelle V3
> Cible : architecture de la V1 du produit
> Note : ce document décrit les choix techniques implicites dans la spec fonctionnelle. Toute décision non couverte ici reste à arbitrer en phase d'exécution.

---

## Table des matières

1. [Architecture globale](#1-architecture-globale)
2. [Stack technologique](#2-stack-technologique)
3. [Modèle de données](#3-modèle-de-données-postgresql)
4. [Architecture des agents LLM](#4-architecture-des-agents-llm)
5. [Couche LLM — Tool use natif Claude API](#5-couche-llm--tool-use-natif-claude-api) *(ex « Serveur MCP », repositionné 2026-04-30)*
6. [Le moteur OR-Tools (CP-SAT)](#6-le-moteur-or-tools-cp-sat)
7. [Le module Data Quality](#7-le-module-data-quality)
8. [Le trust layer technique](#8-le-trust-layer-technique)
9. [Le frontend](#9-le-frontend)
10. [La PWA opérateur](#10-la-pwa-opérateur)
11. [Sécurité et multi-tenancy](#11-sécurité-et-multi-tenancy)
12. [Observabilité et monitoring](#12-observabilité-et-monitoring)
13. [Déploiement et infrastructure](#13-déploiement-et-infrastructure)
14. [Performance et SLA cibles](#14-performance-et-sla-cibles)

---

## 1. Architecture globale

### 1.1 Vue d'ensemble

L'architecture suit un pattern de **monolithe modulaire avec un microservice spécialisé**. C'est volontairement simple en V1 — pas de microservices distribués, pas de Kubernetes, pas de service mesh.

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Next.js (SaaS)                  │
│              Frontend PWA tactile (opérateur)               │
└─────────────────────────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Backend monolithe NestJS (API)                 │
│   Auth · Multi-tenant · Versioning · Orchestration          │
└─────────────────────────────────────────────────────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
   ┌──────────┐          ┌──────────┐          ┌──────────┐
   │PostgreSQL│          │  Redis   │          │ BullMQ   │
   │multi-tnt │          │  cache   │          │  queues  │
   └──────────┘          └──────────┘          └──────────┘
                                                     │
                                                     ▼
                          ┌──────────────────────────────────┐
                          │  Microservice Python (Solver)    │
                          │  CP-SAT · Patterns · Simulation  │
                          │  Agents LLM · Serveur MCP        │
                          └──────────────────────────────────┘
                                            │
                                            ▼
                                ┌──────────────────────┐
                                │   LLM API externe    │
                                │  Claude / Mistral    │
                                └──────────────────────┘
```

### 1.2 Découpage des responsabilités

| Composant | Responsabilité |
|-----------|----------------|
| Frontend Next.js | UI principale chef d'atelier, dashboard, Gantt, conversation |
| PWA tactile | Saisie opérateur (scan QR, déclarations, photos) |
| Backend NestJS | API REST, auth, multi-tenant, versioning, orchestration jobs |
| PostgreSQL | Stockage transactionnel multi-tenant + historique snapshots |
| Redis | Cache + sessions + rate limiting |
| BullMQ | Queue des jobs async (solving, simulation, validation) |
| Microservice Python | Logique CP-SAT, patterns, simulation, agents LLM, serveur MCP |
| LLM API | Inférence externe (Claude primaire, Mistral fallback) |

### 1.3 Communication inter-services

- **Frontend ↔ Backend** : REST + Server-Sent Events pour les updates temps réel (avancement solving)
- **Backend ↔ Microservice Python** : HTTP REST sur réseau privé + queue BullMQ pour les jobs longs
- **Backend ↔ PostgreSQL** : Prisma ORM
- **Microservice Python ↔ LLM API** : SDK officiel Anthropic + abstraction MCP

---

## 2. Stack technologique

### 2.1 Backend principal (NestJS)

| Composant | Choix | Justification |
|-----------|-------|---------------|
| Runtime | Node.js 20 LTS | Stable, écosystème mature |
| Framework | NestJS 10 | Maîtrise existante, structure modulaire |
| ORM | Prisma | Multi-tenant, migrations, type-safe |
| Auth | Auth.js (NextAuth) ou WorkOS | Email+password en V1, SSO en V2 |
| Validation | class-validator + Zod | Schémas partagés frontend/backend |
| Queue | BullMQ | Mature, intégration Redis simple |
| Tests | Jest + Supertest | Standard NestJS |
| Documentation API | OpenAPI auto-générée via NestJS | Pour le frontend, pas exposée publiquement V1 |

### 2.2 Microservice Python

| Composant | Choix | Justification |
|-----------|-------|---------------|
| Runtime | Python 3.11+ | Requis par MCP SDK et OR-Tools |
| Framework HTTP | FastAPI | Async natif, OpenAPI auto, validation Pydantic |
| Solver | OR-Tools `ortools>=9.10` (CP-SAT) | Choix structurant V3 |
| MCP SDK | `mcp>=1.5.0` | SDK Python officiel |
| LLM client | `anthropic` (SDK officiel) + `mistralai` | Provider primaire + fallback |
| Data manipulation | pandas + numpy | Pour Data Quality, clustering |
| Clustering | scikit-learn | KMeans / hiérarchique pour familles de pièces |
| Fuzzy matching | rapidfuzz | Performance Levenshtein |
| Tests | pytest + pytest-asyncio | Standard Python |

### 2.3 Frontend

| Composant | Choix | Justification |
|-----------|-------|---------------|
| Framework | Next.js 15 (App Router) | SSR, écosystème React |
| UI | TailwindCSS + shadcn/ui | Production rapide |
| Gantt | DHTMLX Gantt ou Bryntum | Maturité industrielle, fonctionnalités attendues |
| State | Zustand ou TanStack Query | Léger, suffisant V1 |
| PWA | next-pwa + service worker custom | Offline-first pour la PWA opérateur |

### 2.4 Infrastructure

| Composant | V1 | Évolution V2-V3 |
|-----------|----|----|
| Hébergement | VPS Hetzner ou Scaleway | Migration cloud hyperscaler si besoin |
| Container | Docker Compose | Kubernetes en année 2-3 |
| Reverse proxy | Traefik | Maîtrise existante |
| TLS | Let's Encrypt via Traefik | Maîtrise existante |
| Stockage objet | S3-compatible (OVH, Scaleway) | Pour photos, exports, snapshots |
| Monitoring | Grafana + Prometheus + Loki | Stack open source standard |
| Error tracking | Sentry | Self-hosted possible |

---

## 3. Modèle de données (PostgreSQL)

### 3.1 Multi-tenancy

**Stratégie : tenant_id sur chaque table**, pas de schéma par client.

- Plus simple à opérer en V1
- Suffisant jusqu'à plusieurs centaines de clients
- Migration vers schéma-par-tenant possible plus tard si besoin

Toute requête passe par un middleware Prisma qui injecte le `tenant_id` du contexte d'authentification.

### 3.2 Tables principales

```sql
-- Comptes et utilisateurs
tenants (id, name, country, created_at, plan, status)
users (id, tenant_id, email, password_hash, role, last_login)

-- Atelier et ressources
workshop_models (id, tenant_id, name, version, parent_version_id, created_at)
machines (id, tenant_id, model_id, name, type, calendar_json, shared_resources)
operators (id, tenant_id, model_id, name, qualifications_json, availability_json)
part_families (id, tenant_id, model_id, name, members_count, transition_matrix_id)
part_family_members (id, family_id, part_reference, attributes_json)
transition_matrices (id, tenant_id, model_id, families_count, matrix_json)

-- Ordres de fabrication
orders (id, tenant_id, model_id, reference, client, priority_tier, deadline, status)
order_operations (id, order_id, sequence, operation_type, machine_constraint, duration_min)

-- Soft constraints
soft_constraints (id, tenant_id, model_id, natural_language_rule, weight, active)

-- Plannings et solving
solve_jobs (id, tenant_id, model_id, status, started_at, finished_at, confidence_score)
schedule_results (id, job_id, gantt_data_json, kpi_json, simulation_metrics_json)
schedule_assignments (id, schedule_id, operation_id, machine_id, operator_id, start, end)

-- Versioning et snapshots (critique)
model_snapshots (id, tenant_id, model_id, version, snapshot_json, created_at, reason)

-- Data Quality
import_sessions (id, tenant_id, file_path, status, total_rows, clean_rows, anomaly_rows)
import_anomalies (id, session_id, row_id, level, field, raw_value, suggested_value, status)

-- Validation et trust layer
test_cases (id, tenant_id, name, scenario_json, expected_outcome, criticality)
test_case_runs (id, test_case_id, model_id, status, deviation_score)

-- Audit et explicabilité
agent_interactions (id, tenant_id, user_id, agent_type, input, output, tokens_in, tokens_out, model)
infeasibility_reports (id, tenant_id, job_id, mis_json, nl_explanation, suggested_actions_json)
```

### 3.3 Stratégie de versioning

Chaque modification structurante du modèle d'atelier crée une nouvelle entrée dans `model_snapshots` avec :
- Le snapshot complet sérialisé en JSON
- La référence au snapshot parent
- La raison de la création (manuel, auto-pré-solve, après-import)

Les outils MCP `get_model_snapshot`, `diff_models`, `rollback_model` opèrent sur cette table.

**Rétention :** snapshots conservés 12 mois minimum, archivés en stockage objet au-delà.

### 3.4 Performance

- Index sur `tenant_id` partout
- Index composites sur les colonnes filtrées fréquemment
- Partitionnement de `agent_interactions` par mois (croissance rapide attendue)
- TTL sur les snapshots de 12 mois pour limiter la taille

---

## 4. Architecture des agents LLM

### 4.1 Choix de provider

**Provider primaire : Claude Sonnet** (via API Anthropic)
- Meilleur en suivi strict d'instructions et utilisation d'outils MCP
- SDK officiel mature

**Fallback : Mistral Large** (via API européenne)
- Souveraineté
- Coût de portabilité faible si prompts standardisés

**Architecture défensive :**
- Abstraction par-dessus les SDKs (interface `LLMProvider` commune)
- Tests de non-régression multi-modèles automatisés (suite de prompts → comparaison sorties)
- Configuration par tenant possible (un client peut imposer Mistral pour souveraineté)

### 4.2 Agent d'extraction et préparation

**Rôle :** transformer du langage naturel ou des données semi-structurées en structures de données validées.

**Cas d'usage :**
- Extraction de données depuis le questionnaire arborescent
- Data cleaning et fuzzy matching post-import
- Traduction de préférences en soft constraints
- Modifications conversationnelles ("priorité 1 sur Safran")

**Pattern technique :**
- Tool calling structuré (fonction par opération MCP)
- Validation Pydantic systématique des outputs
- Retry max 3 sur erreur de validation (pas plus)
- Logging exhaustif pour debug

### 4.3 Agent d'explication et validation

**Rôle :** transformer des résultats techniques en langage naturel pour le chef d'atelier.

**Cas d'usage :**
- Explication du placement d'une opération
- Traduction d'un INFEASIBLE + MIS en explication métier
- Communication des cas d'incertitude détectés
- Résumé d'un planning complet

**Pattern technique :**
- Pas de tool calling, juste génération de texte structuré
- Templates de prompts par type d'explication
- Limite stricte de tokens en sortie (pour contrôle des coûts)
- Cache Redis sur les explications similaires (clé = hash du résultat input)

### 4.4 Anti-hallucination et safety

**Règles strictes :**

1. **Aucun appel direct à `eval` ou exec()** sur output LLM, jamais
2. **Schéma JSON imposé** sur tous les outputs avec validation Pydantic stricte
3. **Whitelist d'outils** par contexte (l'agent ne voit que les outils légitimes pour sa tâche)
4. **Timeout** par appel (60s max)
5. **Budget tokens** par session (kill au-delà)
6. **Pas de tool LLM qui modifie le code** des patterns CP-SAT — c'est figé en codebase

### 4.5 Coûts cibles

| Phase | Tokens input | Tokens output | Coût Sonnet |
|-------|--------------|---------------|-------------|
| Onboarding complet | ~50K | ~20K | ~2-5€ |
| Replanification simple | ~5K | ~2K | ~0.10€ |
| Modification conversationnelle | ~3K | ~1K | ~0.05€ |
| Explication détaillée | ~2K | ~3K | ~0.05€ |

**Cible mensuelle par client en croisière :** 10-40€.

---

## 5. Couche LLM — Tool use natif Claude API

> **⚠️ Décision 2026-04-30 — Repositionnement** : la version V3 initiale prévoyait un **serveur MCP**. Cette approche est **abandonnée** : pour une SaaS B2B où le backend orchestre lui-même les appels Claude API (les deux bouts du dialogue LLM ↔ outils sont sous notre contrôle), MCP est un protocole de transport qui ajoute de la complexité sans valeur produit. Le **tool use natif de l'API Claude** couvre tous les besoins, est plus portable (Mistral / GPT en fallback), et concentre l'effort sur ce qui compte : les **workflows agents** (extraction, traduction NL → soft constraints, explication INFEASIBLE, modifications conversationnelles).
>
> Les sections §5.1 à §5.4 ci-dessous décrivent encore l'ancienne approche MCP. Elles seront réécrites en début de Phase 3 effective. **Ce qui reste pertinent dès maintenant** :
>
> - **§5.2 — la liste fonctionnelle des "outils"** : les 14 tools listés correspondent aux capacités que les agents devront exposer à Claude. Ils deviennent des fonctions Python du backend, déclarées en `tools=[...]` dans les appels API, pas des outils MCP.
> - **§5.3 — la bibliothèque de patterns CP-SAT** : reste valide telle quelle, déjà en partie implémentée dans `src/core/pattern.py`.
> - **§5.4 — la protection contre l'auto-pilote LLM** : reste valide, juste à porter au niveau de la couche tool use plutôt qu'au niveau du serveur MCP.
>
> Voir le **journal des décisions** dans `v0-status.md` (entrée 2026-04-30 — "Repositionnement Phase 3 : abandon du serveur MCP") pour le détail du raisonnement.

---

### 5.1 Implémentation

- SDK officiel Python `mcp>=1.5.0`
- Serveur exposé en HTTP interne sur le réseau privé Docker
- Pas exposé publiquement en V1
- Authentification par token de session du tenant

### 5.2 Outils exposés (V1)

#### Modélisation (6 outils)
```python
create_workshop_model(workshop_name: str, description: str) -> ModelId
add_machine(model_id, name, type, calendar, shared_resources) -> MachineId
add_operator(model_id, name, qualifications, availability) -> OperatorId
add_orders_from_excel(model_id, file_path) -> ImportSessionId
apply_pattern(model_id, pattern_name, parameters) -> Result
add_soft_constraint(model_id, natural_language_rule, weight_hint) -> ConstraintId
```

#### Versioning (3 outils)
```python
get_model_snapshot(model_id, version: int = -1) -> Snapshot
diff_models(model_id_v1, model_id_v2) -> Diff
rollback_model(model_id, version) -> Result
```

#### Exécution et explication (5 outils)
```python
solve_schedule(model_id, horizon, objective_weights, freeze_horizon) -> JobId
get_solution(job_id) -> Solution | Status
explain_decision(job_id, operation_id) -> NLExplanation
analyze_infeasibility(model_id, mis_result) -> Explanation + Actions
validate_against_test_cases(model_id) -> ValidationReport
run_operational_simulation(job_id) -> SimulationMetrics
```

### 5.3 Patterns CP-SAT (bibliothèque interne)

**Structure :** chaque pattern est une classe Python testée exhaustivement.

```python
class Pattern(ABC):
    name: str
    parameters_schema: BaseModel  # Pydantic
    
    def apply(self, model: cp_model.CpModel, params: dict) -> None: ...
    def validate(self, params: dict) -> ValidationResult: ...
    def get_test_cases(self) -> list[TestCase]: ...
```

**Patterns V1 (couverture des contraintes dures) :**
- `NoOverlapWithSetup` — sequence-dependent setup via transition matrix
- `QualifiedOperatorConstraint` — opérateur qualifié par type d'opération
- `CalendarAvailability` — disponibilité machines et opérateurs
- `PrecedenceChain` — précédence entre opérations d'un même OF
- `SharedResourceExclusion` — partage de ressources (aspiration, alimentation)
- `WeightedTardinessObjective` — minimisation des retards pondérés
- `MakespanObjective` — minimisation du makespan
- `StabilityObjective` — pénalisation des changements vs planning précédent

**Couverture cible V1 :** 80% des cas d'usage de l'ICP. Les 20% restants sont rejetés ou orientés vers conseil expert.

### 5.4 Protection contre l'auto-pilote LLM

Critique : aucun outil MCP ne permet au LLM de :
- Créer un nouveau pattern (réservé au code)
- Modifier le code d'un pattern existant
- Désactiver un mécanisme du trust layer
- Bypass la validation par cas-tests

Ces protections sont au niveau du serveur MCP lui-même, pas au niveau du prompt LLM.

---

## 6. Le moteur OR-Tools (CP-SAT)

### 6.1 Choix structurant

**OR-Tools CP-SAT en direct, pas MiniZinc.**

Justifications :
- Performance brute supérieure
- API Python s'intègre proprement dans un SaaS production
- Contrôle fin (search strategy, hints, callbacks) essentiel pour le produit
- LNS natif performant — pas de réimplémentation

### 6.2 Architecture du module solver

```
solver/
├── patterns/              # Bibliothèque de patterns
│   ├── base.py
│   ├── no_overlap_setup.py
│   ├── qualified_operator.py
│   └── ...
├── builder/               # Construction du modèle
│   ├── model_builder.py
│   └── objective_builder.py
├── runner/                # Exécution
│   ├── solver_runner.py   # Wrap CP-SAT avec timeout, callbacks
│   └── strategies.py      # Search strategies
├── calibration/           # Calibration dynamique des poids
│   └── weight_calibrator.py
├── simulation/            # Simulation opérationnelle
│   └── operational_sim.py
├── infeasibility/         # MIS et explications
│   └── mis_extractor.py
└── tests/
    ├── unit/
    ├── integration/
    └── golden_cases/      # Les 100-200 cas-tests de référence
```

### 6.3 Calibration dynamique des poids

**Problème :** sans normalisation, l'objectif composite a un problème d'ordre de grandeur.

**Solution :**

```python
def calibrate_weights(model_instance, user_priorities):
    """
    user_priorities = {"tardiness": 0.5, "makespan": 0.2, "stability": 0.3}
    """
    # Pré-résolution rapide pour estimer les ordres de grandeur
    sample = quick_estimate(model_instance, time_limit=5)
    
    scales = {
        "tardiness": estimate_tardiness_scale(sample),
        "makespan": estimate_makespan_scale(sample),
        "stability": estimate_stability_scale(sample)
    }
    
    # Normalisation
    normalized_weights = {
        k: user_priorities[k] / scales[k] 
        for k in user_priorities
    }
    
    return normalized_weights
```

### 6.4 Stratégie de replanification

Trois mécanismes combinés systématiquement :

1. **Freeze partiel** des opérations en cours et de l'horizon court (4-8h)
2. **Solution hint** CP-SAT injectant la solution précédente
3. **Objectif composite** avec terme de stabilité pondéré par criticité

```python
stability_term = sum(
    is_moved[op] * criticality[op.order] * temporal_displacement[op]
    for op in operations
)
```

Avec criticité par tier client : Tier 1 = poids 10, Tier 2 = poids 5, Tier 3 = poids 1.

### 6.5 Clustering automatique des familles

**Algorithme :** clustering hiérarchique agglomératif sur features extraites des nomenclatures.

**Features utilisées :**
- Matière (one-hot encoded)
- Forme géométrique (categorisation simple)
- Outillage requis (set d'outils)
- Temps de cycle (numérique normalisé)
- Type d'opérations dans la gamme (set)

**Cible :** 5-15 familles pour 100-200 pièces.

**UX :** le client valide/ajuste les familles proposées avant que la matrice de transition soit générée.

### 6.6 Gestion de l'INFEASIBLE

**Étape 1 : circuit breaker.** Après 3 tentatives en boucle (LLM modifie soft constraints, re-solve, échoue), bascule sur l'analyse formelle.

**Étape 2 : extraction du MIS.**

```python
from ortools.sat.python import cp_model

solver = cp_model.CpSolver()
solver.parameters.enumerate_all_solutions = False

# CP-SAT ne fournit pas de MIS direct, mais on peut l'approximer
# via un solveur dédié comme `assumptions` ou via une heuristique de retrait
def extract_mis(model, hard_constraints):
    """Approximation MIS par retrait progressif."""
    minimal_set = list(hard_constraints)
    for c in list(minimal_set):
        # Tente de résoudre sans cette contrainte
        if is_feasible_without(model, c):
            minimal_set.remove(c)
    return minimal_set
```

**Étape 3 : traduction NL** par l'agent d'explication, avec génération de 2-3 actions correctives.

---

## 7. Le module Data Quality

### 7.1 Pipeline d'import

```
Excel/CSV upload
    ↓
Détection format (Sage / Cegid / Clipper / libre)
    ↓
Parsing structuré (pandas)
    ↓
Normalisation références (rapidfuzz + dictionnaire métier + historique tenant)
    ↓
Détection aberrations (3 niveaux)
    ↓
Création ImportSession + ImportAnomalies
    ↓
Dashboard utilisateur pour validation
    ↓
Application au model_id cible
```

### 7.2 Détection des formats

**Heuristiques :** présence de colonnes spécifiques, patterns de nommage, structure de l'header.

**Stratégie :** mapping configurable par tenant. Première fois qu'un client importe, le système propose un mapping et le mémorise.

### 7.3 Fuzzy matching des références

**Bibliothèque :** rapidfuzz (performance C++).

**Algorithme :**
1. Recherche exacte dans le dictionnaire tenant (historique)
2. Si non trouvé, recherche fuzzy (Levenshtein normalisé > 0.85)
3. Si match unique → proposition
4. Si plusieurs matches → exposition à l'utilisateur pour choix
5. Mémorisation de la décision pour les imports futurs

**Dictionnaire métier de base :** matières standard (aluminium, inox, acier, titane avec leurs grades), opérations canoniques de mécanique de précision. Enrichi par tenant.

### 7.4 Détection des aberrations

**Règles déterministes (Niveau 1) :**
- Temps = 0 sur opération qui en exige
- Durée négative
- Référence inexistante après fuzzy matching
- Date dans le passé pour un OF futur
- Quantité ≤ 0

**Règles statistiques (Niveau 2) :**
- Valeur > 3 sigmas de l'historique de la même opération chez ce tenant
- Cohérence inter-champs (durée totale incohérente avec somme des opérations)
- Patterns inhabituels (ratio temps de réglage / temps de cycle)

**Règles d'apprentissage (Niveau 3) :**
- Tracking dans `import_anomalies` même si non bloquant
- Enrichissement des seuils statistiques au fil du temps

### 7.5 Dashboard utilisateur

UX cible :

```
Import du 12/03/2026 — fichier OF_Mars.xlsx
─────────────────────────────────────────────
✓ 122 OF importés sans problème
⚠ 5 OF nécessitent votre validation
✗ 3 OF bloqués (corrections obligatoires)

⚠ Anomalies probables (5)
─────────────────────────────────────────────
OF-2024-1234  Temps de réglage: 5 min  (historique: 25-45 min)
              [Confirmer] [Corriger]

OF-2024-1240  Référence matière: ALU 7075-T6
              Suggestion: Aluminium 7075-T6 (basé sur 47 imports)
              [Accepter suggestion] [Ignorer]
...

✗ Erreurs bloquantes (3)
─────────────────────────────────────────────
OF-2024-1255  Durée d'opération: -120 min
              Cette ligne ne peut pas être importée.
              [Corriger]
```

---

## 8. Le trust layer technique

### 8.1 Composants

| Composant | Implémentation | Quand |
|-----------|----------------|-------|
| Score de confiance | Module Python avec heuristiques pondérées | Avant remontée client |
| Validation cas-tests | Suite pytest customisée (golden tests) | Après chaque génération de modèle |
| Simulation opérationnelle | Module Python sur le résultat solver | Après chaque solve |
| Circuit breaker | Compteur de retries avec bascule | En cas d'INFEASIBLE répété |
| Validation humaine | UX dans le frontend | Toujours, par design |

### 8.2 Score de confiance

```python
def compute_confidence_score(context):
    factors = {
        "uncommon_pattern_combinations": detect_uncommon_combinations(context),
        "test_case_coverage": run_relevant_test_cases(context),
        "solution_robustness": gap_to_second_best(context),
        "problem_complexity": estimate_complexity(context),
        "data_quality_anomalies_count": count_unconfirmed_anomalies(context),
    }
    
    weights = load_calibrated_weights()  # affinés au fil du temps
    score = sum(weights[k] * factors[k] for k in factors)
    
    return ConfidenceScore(value=score, factors=factors)
```

**Seuils :**
- Score > 0.85 : remontée automatique au client
- Score 0.65-0.85 : remontée avec mise en garde explicite
- Score < 0.65 : ne remonte pas, déclenche revue + questions ciblées au client

### 8.3 Cas-tests internes (golden cases)

**Structure :**

```python
@dataclass
class GoldenCase:
    name: str
    description: str
    workshop_setup: dict
    orders: list[dict]
    expected_outcome: ExpectedOutcome
    criticality: Literal["low", "medium", "high", "critical"]
    related_patterns: list[str]
```

**Cible V1 :** 100-200 cas, dont :
- 30 cas basiques (sanity checks)
- 50 cas par pattern principal
- 30 cas combinaisons de patterns
- 20 cas edge cases industriels (machine tombée, opérateur absent, urgence client)
- 20 cas INFEASIBLE intentionnels

**Exécution :** suite pytest qui tourne automatiquement en CI + à chaque génération de modèle client (uniquement les cas pertinents pour les patterns activés).

### 8.4 Simulation opérationnelle

```python
@dataclass
class OperationalMetrics:
    fragmentation_score: float        # OF d'une famille séparés
    transitions_per_operator: float   # Changements machine moyens
    micro_pauses_count: int           # Pauses < 15min
    redeployment_amplitude: float     # Distance moyenne re-déploiement
    setup_to_useful_ratio: float      # Temps réglage / temps utile
    
    def is_acceptable(self, thresholds) -> bool:
        return all(
            getattr(self, k) <= v for k, v in thresholds.items()
        )
```

**Si non acceptable :** soit le planning est rejeté avec retry et contraintes supplémentaires injectées dans la fonction objectif, soit remontée au chef d'atelier avec mise en garde.

**Calibration des seuils :** par tenant, basée sur l'historique accepté/rejeté par le client.

### 8.5 Circuit breaker

```python
class InfeasibilityCircuitBreaker:
    MAX_LLM_RETRIES = 3
    
    def handle_infeasible(self, job_id, model_id, attempt):
        if attempt < self.MAX_LLM_RETRIES:
            # Tente une modification soft via LLM
            return self.llm_attempt_fix(model_id)
        else:
            # Bascule sur analyse formelle
            mis = extract_mis(model_id)
            explanation = self.explanation_agent.translate_mis(mis)
            actions = self.generate_corrective_actions(mis)
            return InfeasibilityReport(mis, explanation, actions)
```

---

## 9. Le frontend

### 9.1 Pages principales V1

| Route | Fonction |
|-------|----------|
| `/login` | Authentification |
| `/onboarding` | Questionnaire arborescent progressif |
| `/dashboard` | Vue chef d'atelier (KPI + alertes) |
| `/schedule` | Gantt interactif avec modification conversationnelle |
| `/import` | Module Data Quality (upload + validation) |
| `/model/history` | Versioning et rollback |
| `/conversation` | Interface chat avec l'agent |
| `/settings` | Configuration tenant |

### 9.2 Composant Gantt

**Choix :** DHTMLX Gantt en V1 (licence commerciale ~3K€/an, fonctionnalités attendues).

**Fonctionnalités exposées :**
- Vue jour / semaine / horizon configurable
- Drag-and-drop pour réordonner manuellement
- Code couleur par criticité client
- Marquage des opérations gelées (freeze)
- Indicateurs de retard prévisible
- Hover : détails opération + agent d'explication

### 9.3 Modification conversationnelle

```
┌─────────────────────────────────────────────┐
│  Conversation avec le planificateur         │
├─────────────────────────────────────────────┤
│                                             │
│  Vous : Mets l'OF Safran-1234 en priorité 1│
│         et lance la replanification         │
│                                             │
│  Système : Je vais :                        │
│  - Augmenter la priorité de OF Safran-1234  │
│    de Tier 2 à Tier 1                       │
│  - Lancer une replanification avec freeze   │
│    sur les 8 prochaines heures              │
│                                             │
│  [Confirmer] [Modifier] [Annuler]           │
│                                             │
└─────────────────────────────────────────────┘
```

**Pattern :** validation systématique avant action. Pas d'auto-exécution même pour les commandes simples.

### 9.4 Stratégie d'état

- TanStack Query pour les fetches API + cache
- Server-Sent Events pour les updates live (avancement solve)
- Pas de Redux/Zustand global en V1 — état local par page suffit

---

## 10. La PWA opérateur

### 10.1 Architecture

- Next.js avec `next-pwa`
- Service worker pour offline-first
- IndexedDB pour stockage local
- Sync différée à la reconnexion

### 10.2 Écrans (3 seulement)

#### Écran 1 : Mes OF du jour
Liste priorisée des opérations à faire, avec scan QR pour démarrer.

#### Écran 2 : Déclaration
- Début opération (timestamp + opérateur)
- Fin opération (timestamp + quantité produite)
- Signalement problème (catégorie + photo + commentaire libre)

#### Écran 3 : Statut
État de l'OF en cours, prochaines opérations prévues, alertes.

### 10.3 Offline-first

**Strategy :** stale-while-revalidate côté lecture, queue de mutations côté écriture.

```javascript
// Pseudo-code
async function declareOperation(data) {
  if (navigator.onLine) {
    return await api.declare(data);
  } else {
    return await offlineQueue.enqueue('declare', data);
  }
}

window.addEventListener('online', async () => {
  await offlineQueue.flush();
});
```

**Conflits :** last-write-wins en V1. Cas de conflit réel rares (un opérateur unique par opération).

### 10.4 Hardware cible

- Tablette Android low-cost (Samsung Galaxy Tab A ou équivalent, ~200€)
- Pas d'iOS en V1
- Pas de scanner QR externe (caméra suffit)

---

## 11. Sécurité et multi-tenancy

### 11.1 Multi-tenant

- `tenant_id` injecté dans le contexte de session
- Middleware Prisma qui filtre toutes les requêtes
- Tests de non-régression dédiés (un user A ne peut pas voir les données d'un tenant B)

### 11.2 Authentification

**V1 :** email + mot de passe (Argon2id pour le hash).

**V2 :** SSO via WorkOS si demandé par un prospect entreprise.

### 11.3 Sessions

- JWT short-lived (15 min) + refresh token (30 jours)
- Refresh tokens en HTTP-only secure cookie
- Révocation possible côté serveur (table `revoked_tokens` Redis)

### 11.4 Secrets management

- Variables d'environnement en V1 (chiffrées au repos sur le serveur)
- Vault HashiCorp ou AWS Secrets Manager en V2 si justifié

### 11.5 Données sensibles

**Pas de PII fortes** dans le produit en V1 (pas de numéros SS, pas de coordonnées bancaires côté client).

**RGPD :**
- Mention dans CGU
- Right to be forgotten via suppression complète des données tenant
- Export des données possible (JSON)
- Logs purgés à 90 jours

### 11.6 Sécurité des appels LLM

- Aucune donnée client sensible dans les prompts si possible
- Anonymisation automatique des références client (Safran → Client_A) pour les appels LLM
- Pas de fine-tuning sur données client en V1

---

## 12. Observabilité et monitoring

### 12.1 Logs

**Stack :** Loki + Promtail + Grafana.

**Catégories :**
- Logs techniques (erreurs, warnings)
- Logs business (jobs lancés, plannings produits, anomalies détectées)
- Logs LLM (prompts, completions, tokens, coûts) — table dédiée `agent_interactions`

**Rétention :**
- Logs techniques : 30 jours
- Logs business : 12 mois
- Logs LLM : 12 mois (audit + amélioration)

### 12.2 Métriques

**Stack :** Prometheus + Grafana.

**Métriques business critiques :**
- Nombre de plannings produits par jour par tenant
- Score de confiance moyen
- Taux de remontée auto vs revue manuelle
- Temps moyen de solving par taille de problème
- Taux d'INFEASIBLE
- Coût LLM par tenant par jour

**Métriques techniques :**
- Latence API (p50, p95, p99)
- Throughput
- Erreurs par endpoint
- Utilisation CPU/RAM/disque
- Taille queue BullMQ

### 12.3 Alerting

**Critères critiques (page immédiate) :**
- Solveur down > 5 min
- Taux d'erreur API > 5%
- Score de confiance moyen < 0.5 sur la dernière heure (signal de drift)
- Coût LLM > 2x la moyenne (anomalie)

**Critères warning (notification non-urgente) :**
- Latence API p99 > 2s
- Queue BullMQ > 100 jobs en attente
- Anomalies Data Quality > 30% sur un import

### 12.4 Tracing

**Stack :** OpenTelemetry vers Tempo (Grafana stack).

**Spans tracés :**
- Solve complet (du déclenchement au résultat livré)
- Agents LLM (avec input/output tokens)
- Patterns appliqués
- Validation cas-tests
- Simulation opérationnelle

---

## 13. Déploiement et infrastructure

### 13.1 Environnements

| Environnement | Usage |
|---------------|-------|
| Local | Dev (Docker Compose) |
| Staging | Tests d'intégration, démos commerciales |
| Production | Clients réels |

### 13.2 CI/CD

**Pipeline GitHub Actions :**

```yaml
build:
  - Lint + type check
  - Unit tests backend
  - Unit tests frontend
  - Tests microservice Python (pytest + golden cases)
  - Build Docker images

test:
  - Tests d'intégration (docker-compose)
  - Tests E2E Playwright sur staging

deploy:
  - Manuel pour production V1
  - Automatique pour staging
```

### 13.3 Topologie production

**V1 (un seul serveur) :**
- 1 VPS Hetzner CCX33 (8 vCPU, 32GB RAM, 240GB SSD) — environ 80€/mois
- Tout en Docker Compose
- PostgreSQL + Redis sur le même serveur
- Backups quotidiens vers stockage objet OVH/Scaleway

**V2 (séparation) :**
- 2 VPS app + 1 VPS DB managé
- Stockage objet pour photos/exports
- CDN pour assets frontend

### 13.4 Backups et DR

**Backups :**
- PostgreSQL : pg_basebackup + WAL archiving toutes les 5 min
- Stockage objet : versioning activé
- Test de restore mensuel obligatoire

**RPO cible V1 :** 5 minutes.
**RTO cible V1 :** 4 heures.

---

## 14. Performance et SLA cibles

### 14.1 Performances solver

| Taille problème | Temps cible (95e percentile) |
|-----------------|------------------------------|
| < 50 OF, 5 machines | < 10 secondes |
| 50-200 OF, 5-15 machines | < 60 secondes |
| 200-500 OF, 15-25 machines | < 3 minutes |
| > 500 OF | hors périmètre V1 |

**Stratégie en cas de timeout :**
- Solution faisable retournée même si non optimale
- Indication explicite "solution faisable, optimisation partielle"
- Proposition de relancer avec horizon réduit

### 14.2 Performances API

| Endpoint | Latence cible (p95) |
|----------|---------------------|
| Lecture (dashboard, Gantt) | < 200 ms |
| Écriture simple | < 500 ms |
| Solve (async) | déclenchement < 100 ms, callback selon temps solver |
| LLM (conversation) | < 5 secondes pour première réponse |

### 14.3 Disponibilité

**SLA cible V1 :** 99% (≈ 7h de downtime acceptable par mois).

**SLA cible V2 :** 99.5%.

**Maintenance :** fenêtre hebdomadaire annoncée, hors heures de production atelier (samedi 22h-2h).

### 14.4 Scalabilité cible

**V1 :** capable de servir 60 clients simultanément sans dégradation perceptible.

**V2 (avec séparation infrastructure) :** 500 clients.

**Au-delà de 500 :** repenser l'architecture (microservices, sharding DB).

---

## Annexe — Décisions non couvertes par cette V1

Les sujets suivants ne sont **volontairement pas tranchés** dans cette V1 et restent à arbitrer en phase d'exécution :

- Choix exact entre DHTMLX Gantt et Bryntum (à décider après essais commerciaux)
- Stack monitoring détaillée (Grafana Cloud vs self-hosted)
- Stratégie précise de prompt engineering pour les agents (à itérer avec les premiers clients)
- Format exact des golden cases (YAML vs JSON vs Python)
- Politique exacte de rate limiting
- Stratégie de cache LLM (clé exacte, TTL)
- Détails du fine-tuning éventuel sur dataset client (V2+)

Ces choix sont délibérément reportés pour ne pas sur-engineer en phase de découverte produit.

---

*Fin du document — Spec technique V3*
