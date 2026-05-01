# Rapport d'avancement Phase 3 — Agents LLM (tool use natif Claude API)

> Document narratif complémentaire à `v0-status.md` (tracker structuré).
> Documente les résultats concrets, décisions techniques et métriques de chaque étape.
> Mis à jour à chaque étape stabilisée.

**Snapshot : 2026-04-30 — Phase 3 ✅ stabilisée (3.3-3.8), 3.1/3.2 ❌ abandonnées (MCP)**

---

## Synthèse

| Indicateur | Valeur |
|------------|--------|
| Phase courante | 3 — Agents LLM (tool use natif Claude API) |
| Étapes stabilisées | **6/8** (3.3 ✅ + 3.4 ✅ + 3.5 ✅ + 3.6 ✅ + 3.7 ✅ + 3.8 ✅) |
| Étapes abandonnées | **2/8** (3.1 et 3.2 — MCP server, voir journal des décisions) |
| Trials réels Phase 3 | **13 trials** sur les 5 agents (12 ✓ + 1 fail attrapé par Pydantic et corrigé) |
| Tests automatisés | **279 passants** (5 skipped Taillard) — ~120 s |
| Lignes ajoutées (Phase 3) | ~1500 (src/llm + src/agents + 5 agents méca + 7 prompts + tests) |

---

## Repositionnement préliminaire — Abandon du serveur MCP

**Décision 2026-04-30** : MCP server retiré du scope (cf. `v0-status.md` journal). Pour
une SaaS B2B où le backend orchestre lui-même les appels Claude API, MCP est un
protocole de transport qui ajoute de la complexité sans valeur produit. Le tool use
natif de l'API Claude couvre tous les besoins.

**Étapes 3.1 et 3.2 marquées ❌ abandonnées.**

**Section 5 de `specs-techniques-v3.md`** : un bandeau de décision en tête signale le
repositionnement. La réécriture profonde des sous-sections est différée — la liste
fonctionnelle des 14 outils (§5.2) reste pertinente (ils deviennent des fonctions
Python du backend).

---

## Étape 3.3 — Couche LLM générique ✅

**Objectif** : abstraction provider permettant de tester les agents sans clé API et
de basculer Mistral / GPT le cas échéant.

**Livrables**
- `src/llm/types.py` — `Message`, `Role` (Pydantic strict).
- `src/llm/parsing.py` — `extract_json_block` (cascade fence → balanced-braces →
  fallback ; gère prose autour, accolades dans strings, JSON invalide → `LLMParseError`).
- `src/llm/provider.py` :
  - `LLMProvider` ABC, contrat minimal `complete(messages, *, max_tokens, temperature) -> str`.
  - `FakeLLMProvider` : initialisé avec une liste de réponses canned ou un callable.
    Trace les appels dans `self.calls` pour assertions. Utilisé partout en test.
  - `ClaudeAPIProvider` : SDK officiel `anthropic`. Extrait le system prompt des
    messages, concat les text-blocks de la réponse, ignore les autres types de blocks
    (préparation pour tool use natif si besoin plus tard).

**Tests** : 14 tests dont validation des cascades de parsing, traces d'appels,
épuisement de réponses canned, providers callables.

**Statut** : ✅ stabilisée le 2026-04-30.

---

## Étape 3.4 — Agent extraction questionnaire 🔵

**Objectif** : traduire les réponses brutes d'un questionnaire d'onboarding (UI
Phase 5.2 — dict plat) en `WorkshopSpec` Pydantic strict.

**Livrables**
- `src/verticals/mech_workshop/prompts/extraction_questionnaire_v1.md` — prompt v1
  (template).
- `src/verticals/mech_workshop/agents/extraction_questionnaire.py` :
  - `WorkshopSpec` Pydantic : `workshop_name`, `n_machines_estimated`,
    `n_operators_estimated`, `machine_types`, `main_certifications`,
    `main_materials`, `shift_pattern` (1x8/2x8/3x8/autre), `has_shared_resources`,
    `shared_resources_kinds`, `typical_order_size_pieces`, `typical_lead_time_days`,
    `notes`. Tous les enums fermés via `Literal[...]`, `extra="forbid"`.
  - `QuestionnaireAgent` : substitue `{{ANSWERS_JSON}}` dans le template, valide la
    sortie avec `WorkshopSpec.model_validate`.

**Tests** : 3 tests avec `FakeLLMProvider` (parsing valide, rendering du prompt,
rejet d'inputs manquants).

**Validation empirique** :
- **4/4 trials** réels via `agent_io.py` + claude.ai, profils méca très variés :
  - Trial 1 : aero (Safran/Airbus, EN9100, 12-15 machines) ✓
  - Trial 2 : auto (Stellantis/Renault/Bosch, IATF 16949, 20-25 machines, 3x8) ✓
  - Trial 3 : médical (Smith&Nephew, ISO 13485, traçabilité unitaire) ✓
  - Trial 4 : polyvalent sans certif (atelier 12 personnes, prototypes + petites séries) ✓
- Comportement cohérent à travers les 4 profils : enums respectés, estimations
  milieu de fourchette tracées, gestion `autre` pour les inputs hors enum,
  honnêteté signalée par Claude (« à confirmer » sur tour parallèle conventionnel).

**Limites d'enum identifiées** (à traiter post-pilotes design partners) :
- `machine_types` : ajouter `tour_conventionnel`
- `shared_resources_kinds` : ajouter `salle_blanche`
- `main_materials` : ajouter `plastique` ou `peek`

Ces ajustements sont **localisés dans la verticale méca**, n'impactent pas
l'engine.

**Statut** : ✅ stabilisée le 2026-04-30.

---

## Étape 3.5 — Agent extraction Excel/CSV ✅

**Objectif** : extraire un workshop structuré depuis un fichier ERP CSV pré-flighté.

**Livrables**
- `src/verticals/mech_workshop/prompts/extraction_csv_v1.md` — copie de
  `experiments/llm-extraction/prompt_v3.md` (validé 45/45).
- `src/verticals/mech_workshop/prompts/extraction_csv_target_schema_v1.md` —
  copie de `experiments/llm-extraction/target_schema.md`.
- `src/verticals/mech_workshop/agents/extraction_csv.py` :
  - Schémas Pydantic : `ExtractedMachine`, `ExtractedOperation`, `ExtractedOrder`,
    `AnomalyItem`, `CSVExtractionOutput`. `MachineType` en enum fermé.
  - `CSVExtractionAgent` : prend un `PreflightReport` en entrée (chaîne avec
    `src.preflight`), substitue `{{COLUMN_MAPPING}}`, `{{PREFLIGHT_ANOMALIES}}`,
    `{{CSV}}` (cleaned rows), `{{SEPARATOR}}`, `{{ENCODING}}`, `{{TODAY}}`,
    `{{SCHEMA}}`.

**Tests** : 3 tests avec `FakeLLMProvider`.

**Validation empirique** (déjà acquise en expérimentation) :
- Prompt v3 + preflight : 15/15 sur fixture_04 (anomalies réelles).
- Prompt v2 : 45/45 sur 3 fixtures (F1 propre, F3 ERP chaotique, F4 anomalies).

**Statut** : ✅ stabilisée le 2026-04-30.

---

## Étape 3.6 — Traduction soft constraints NL ✅

**Objectif** : traduire des phrases NL exprimant des préférences d'ordonnancement
en `SoftConstraint`s pondérées et catégorisées.

**Livrables**
- `src/verticals/mech_workshop/prompts/soft_constraints_nl_v1.md` — copie de
  `experiments/llm-soft-constraints/prompt_v1_soft.md`.
- `src/verticals/mech_workshop/prompts/soft_constraints_nl_target_schema_v1.md` —
  copie de `experiments/llm-soft-constraints/target_schema_soft.md`.
- `src/verticals/mech_workshop/agents/soft_constraints_nl.py` :
  - `SoftConstraintCategory` : 10 catégories canoniques en `Literal[...]`
    (`avoid_machine_during_period`, `prefer_grouping_by_material`, …, `other`).
  - `ConfidenceLevel` : `high` / `medium` / `low`.
  - `SoftConstraint` Pydantic : `natural_language`, `category`, `parameters` (libre),
    `weight_hint` (0-1), `weight_rationale`, `confidence`.
  - `UnrecognizedConstraint` Pydantic : `natural_language`, `reason`, `suggestion`.
  - `SoftConstraintsOutput` Pydantic : `soft_constraints` + `unrecognized`.
  - `SoftConstraintsAgent` : substitue `{{SCHEMA}}` et `{{PHRASES}}`, valide.

**Tests** : 4 tests avec `FakeLLMProvider` dont validation `extra="forbid"` sur
catégorie hors enum, gestion `unrecognized`, rejet de phrases vides.

**Validation empirique** :
- Phase 2 (expérimentation) : 75/75 dès iteration 1 sur 15 phrases incluant 4 cas
  pièges critiques (« jamais » catégoriel, formation temporaire, catégorie inédite,
  contrainte dure déguisée).
- Phase 3 (trial production via `agent_io.py` + claude.ai) : **10/10** sur 10 phrases
  méca nouvelles, dont la phrase piège « Jamais de rectif sans certif » correctement
  basculée en `unrecognized` avec suggestion pointant sur le pattern existant
  `qualified_operator_constraint`. Voir `experiments/agents-trial/results.md`.

**Statut** : ✅ stabilisée le 2026-04-30, **reproductibilité confirmée** sur inputs nouveaux.

---

## Étape 3.7 — Agent explication NL 🔵

**Objectif** : produire une explication en français professionnel d'atelier d'un
placement OF ou d'une infaisabilité, sans jargon solveur.

**Livrables**
- `src/verticals/mech_workshop/prompts/explanation_v1.md` — prompt v1 unifié pour
  les deux modes (`placement` / `infeasibility`), interdit le jargon (makespan,
  no-overlap, MIS, CP-SAT…).
- `src/verticals/mech_workshop/agents/explanation.py` :
  - `ExplanationKind` : `Literal["placement", "infeasibility"]`.
  - `ExplanationOutput` Pydantic : `summary` (1 phrase), `reasons` (≤5),
    `actions_suggested` (≤3), `kind`.
  - `ExplanationAgent` : substitue `{{KIND}}` et `{{CONTEXT_JSON}}`.

**Tests** : 4 tests dont rejet de `kind` invalide et de listes trop longues.

**Validation empirique** : **3/3 trials OK** après 1 itération de prompt.
- Trial 1 — `placement` (prompt v1) : ✗ **ÉCHEC** (Claude a omis `kind`).
- Itération v1 → v1.1 : règle 5 renforcée + mention en tête de Tâche.
- Trial 2 — `infeasibility` (prompt v1) : ✓ Summary clair, 3 reasons, 3 actions.
- Trial 3 — `placement` (prompt v1.1, re-test) : ✓ Validé, `kind` correctement
  présent, exploit de la donnée context (« 3 jours de marge »).

**Signal positif** : la `ValidationError` Pydantic a attrapé le bug du prompt v1
qui serait passé silencieusement sans le schéma strict. Validation de la
doctrine "Pydantic strict + validators métier" en conditions réelles.

**Statut** : ✅ stabilisée le 2026-04-30 (avec prompt v1.1).

---

## Étape 3.8 — Modifications conversationnelles 🔵

**Objectif** : traduire un ordre conversationnel (« priorité 1 sur Safran »,
« décale la livraison Bosch ») en plan d'actions structuré et auditable, **sans
jamais l'appliquer directement** (validation humaine obligatoire).

**Livrables**
- `src/verticals/mech_workshop/prompts/conversational_edit_v1.md` — prompt v1.
- `src/verticals/mech_workshop/agents/conversational_edit.py` :
  - `EditActionKind` : 7 catégories canoniques (`set_client_priority`,
    `reassign_operation_machine`, `shift_deadline`, `freeze_order`, `release_order`,
    `set_order_priority`, `other`).
  - `EditAction` Pydantic : `kind`, `target`, `params` libre, `rationale`.
  - `EditPlan` Pydantic : `actions`, `needs_clarification`, `clarification_question`,
    `user_request_normalized`. **Validator métier** garantit la cohérence
    `needs_clarification == True ⇔ actions == []` ET `clarification_question` non vide.
  - `ConversationalEditAgent` : substitue `{{USER_REQUEST}}` et
    `{{INSTANCE_SUMMARY_JSON}}`.

**Tests** : 4 tests dont path clarification, rejet d'incohérences, rejet de plan
vide sans clarification.

**Validation empirique** : **2/2 trials OK avec comportement discriminant confirmé**.
- Trial 1 — Condition tranchable (87 % vs 42 %) : ✓ 2 actions distinctes
  (set_order_priority + reassign), `condition_applied` tracée. Claude
  interprète proactivement.
- Trial 2 — Condition non tranchable (51 % vs 49 %, 2 OF Bosch) : ✓
  `needs_clarification=true` + question fermée précise sur quel(s) OF
  basculer. Claude **bascule en clarification** quand l'ambiguïté est réelle.

**Signal très fort** : le comportement de Claude est **discriminant** selon le
contexte. Avec écart significatif → tranche. Avec écart serré + cible
ambiguë → demande clarification. Le prompt v1 gère bien les deux cas sans
itération nécessaire. Le validator Pydantic
`needs_clarification ⇔ actions==[]` validé en conditions réelles.

**Statut** : ✅ stabilisée le 2026-04-30.

---

## Métriques cumulées Phase 3

| Étape | Type | Tests auto | Trials réels | Statut |
|-------|------|-----------:|--------------|--------|
| 3.1 + 3.2 | MCP server | 0 | — | ❌ abandonnée |
| 3.3 | Couche LLM (provider, parsing) | 14 | — | ✅ |
| 3.4 | Agent questionnaire | 3 | 4/4 (aero, auto, médical, polyvalent) | ✅ |
| 3.5 | Agent extraction CSV | 3 | déjà 45/45 + 15/15 (Phase 2) | ✅ |
| 3.6 | Agent soft constraints NL | 4 | 1 trial Phase 3 (10/10 phrases) | ✅ |
| 3.7 | Agent explication | 4 | 3/3 (1 fail attrapé → fix → re-test OK) | ✅ |
| 3.8 | Agent édition conversationnelle | 4 | 2/2 (tranchable + non tranchable) | ✅ |
| **Total Phase 3** | | **32 tests auto** | **13 trials réels** | **6 ✅ + 2 ❌** |

Suite globale : **279 passants** (vs 246 ouverture Phase 3).

---

## Décisions techniques marquantes

| Date | Décision | Justification |
|------|----------|---------------|
| 2026-04-30 | Abandon du serveur MCP | SaaS B2B : tool use natif suffit, MCP = surcoût + lock-in Anthropic. Voir journal v0-status. |
| 2026-04-30 | Tous les agents sont **single-shot prompt → JSON** à ce stade | Suffit pour les 5 use cases. Tool use natif Claude API ajouté plus tard si un agent en a besoin. |
| 2026-04-30 | Schémas Pydantic stricts (`extra="forbid"`, `frozen=True`, validators métier) | Toute déviation du LLM lève une `ValidationError` claire. Pas de "à peu près". |
| 2026-04-30 | `FakeLLMProvider` partout en tests | 0 appel API en CI, déterministe. Tests live API gated par `ANTHROPIC_API_KEY` à venir. |
| 2026-04-30 | Helper `extract_json_block` en cascade | Les LLMs entourent leur JSON de prose malgré les instructions. Parsing robuste plutôt que prompt strict. |
| 2026-04-30 | Réutilisation de `prompt_v3.md` (3.5) et `prompt_v1_soft.md` (3.6) tels quels | Validés empiriquement. Pas de réécriture. |

---

## Risques identifiés

| Risque | Probabilité | Impact | Atténuation |
|--------|-------------|--------|-------------|
| Prompts 3.4 / 3.7 / 3.8 nécessitent plusieurs itérations avec design partners | Élevée | Faible | Le scaffolding (schéma + agent) est en place. Les itérations de prompt sont localisées, pas de refonte structurelle. |
| `ClaudeAPIProvider` non testé end-to-end (pas de clé API en CI) | Élevée | Faible | Code minimaliste (10 lignes). À valider manuellement à la première utilisation. Rest API stable. |
| Bascule Mistral non testée | Élevée | Moyen | À implémenter quand le besoin apparaîtra (fallback prod). L'abstraction `LLMProvider` est prête. |
| Coût LLM en production | Moyenne | Moyen | Cache de réponses sur prompts identiques + monitoring tokens en Phase 7.2 (métriques business). |
| Hallucinations malgré validation Pydantic | Faible | Élevé | Validators métier dans les schémas + règle anti-zèle dans les prompts (déjà validée empiriquement sur 3.5/3.6). |

---

## Prochaines étapes

### Phase 3 ✅ — entièrement stabilisée

13 trials réels, 12 ✓ et 1 fail attrapé par Pydantic puis corrigé. Tous les
prompts tiennent en conditions réelles. Limites d'enum identifiées
(`tour_conventionnel`, `salle_blanche`, `plastique`/`peek`) et localisées dans
la verticale méca, à traiter post-pilotes design partners.

### Bilan méthodologique

La doctrine **« scaffolding générique + Pydantic strict + validation no-code »**
est validée comme méthodologie de dev d'agents LLM :
- Le scaffolding (LLMProvider, Agent base, schémas Pydantic) est livré en 1
  session, sans clé API.
- Les prompts sont itérés via le workflow no-code (`prompt` → claude.ai →
  `validate`) pour un coût marginal (≈ 5 min/trial).
- Les bugs de prompt sont attrapés à la `ValidationError` Pydantic plutôt qu'en
  prod silencieusement (ex: `kind` manquant 3.7 trial 1).
- Les comportements pro-actifs / clarifiants de Claude sont observés et tracés
  (ex: discriminant 3.8 sur conditions tranchables/non tranchables).

À reproduire pour toute nouvelle verticale (santé, éducation, services
techniques) : créer les agents, les prompts, valider en no-code, brancher API
en production.

### Phases ouvrables ensuite

1. **Phase 4** — Backend SaaS + persistance (NestJS + Prisma + PostgreSQL).
2. **Phase 1.6** — Soft constraints en pénalités (côté solver, complément de 3.6
   qui produit la spec NL → JSON).
3. **Phase 1.1.opt** — Migration setup pattern (prioritaire avant scale réel).

---

*Mis à jour à chaque étape stabilisée.*
