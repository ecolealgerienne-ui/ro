# Rapport d'avancement Phase 2 — Trust layer technique (sans LLM)

> Document narratif complémentaire à `v0-status.md` (tracker structuré).
> Documente les résultats concrets, décisions techniques et métriques de chaque étape.
> Mis à jour à chaque étape stabilisée.

**Snapshot : 2026-04-30 — Phase 2.1 (harness + 15 cases pilotes), 2.2 ✅, 2.3 ✅**

---

## Synthèse

| Indicateur | Valeur |
|------------|--------|
| Phase courante | 2 — Trust layer technique (sans LLM) |
| Étapes Phase 2 stabilisées | **2/5** (2.2 ✅ scoring, 2.3 ✅ simulation) |
| Étape en cours | **2.1 🟡** — harness golden cases + 15 pilotes livrés, extension à 100 différée |
| Étapes restantes | **2/5** (2.4 circuit breaker, 2.5 pipeline complet) |
| Tests automatisés | **228 passants** (5 skipped Taillard non téléchargés) — ~120 s |
| Architecture | **Multi-vertical** formalisée (engine ↔ vertical, refactor commit `8e505e3`) |

---

## Pré-requis architectural — Refactor multi-vertical

**Décision préliminaire** : avant d'attaquer la Phase 2 sur le fond, séparer
strictement le moteur générique du code métier d'une verticale.

**Livrables**
- `src/core/` + `src/preflight/` + `src/loaders/` = moteur générique, vertical-agnostic.
- `src/verticals/mech_workshop/` = première verticale (distributions, generator, adapter, configs).
- Pattern engine ↔ vertical : l'engine fournit le **mécanisme**, la verticale fournit la **calibration**.
- Règles d'imports + garde-fou grep documentés dans `CONTRIBUTING.md §8`.

**Justification** : sans cette discipline, le code se serait calcifié sur la
verticale méca, et porter un 2e marché (santé, éducation, services techniques)
aurait nécessité un fork. Le coût marginal de la discipline est faible
maintenant ; il aurait été dissuasif plus tard.

**Tests d'avant/après** : 188 passants → 188 passants, 0 régression. Ruff clean.

---

## Étape 2.1 — Bibliothèque de golden cases (engine-level)

**Objectif** : 100 cas-tests versionnés pour couvrir la discipline anti-régression
sur les patterns engine, suite pytest qui les rejoue en < 2 min.

**Livrables (étape 1 = harness + 5 pilotes)**
- `tests/golden_cases/_schema.py` — Pydantic strict (`extra="forbid"`), garde-fou
  cohérence `id` ↔ nom de fichier.
- `tests/golden_cases/_runner.py` — loader YAML + exécuteur solveur.
- `tests/golden_cases/cases/` — 5 cas pilotes (1 par catégorie engine).
- `tests/test_golden_cases.py` — pytest paramétré.

**Livrables (étape 2 = extension à 15 cases)**
- 2 cas supplémentaires par catégorie : 3 baseline_jssp, 3 setup, 3 calendar,
  3 operator, 3 shared_resource.
- Tous les optimums analytiquement connus, bornes `min == max` strictes.

**Métriques**
- 16 tests / **0.6 s** runtime (large marge sur le budget 2 min pour 100 cas)
- 5 catégories engine couvertes, chacune avec 3 variations significatives
- Schéma YAML lisible humainement, validé Pydantic au chargement

**Statut** : 🟡 en cours.

**Reste à faire pour atteindre 100 cases** : 3 leviers prévus
1. **Hand-crafted ciblé** (~25-30 cases) pour edge cases non couverts.
2. **Taillard auto-import** (~80 instances avec `best_known_makespan` connu) avec
   assertions souples (`status` + `makespan_max = best_known + 5%`).
3. **Régression-driven** : chaque bug capturé devient un golden case.

**Hors scope (dérogations documentées)**
- Cas INFEASIBLE → différés à Phase 2.4 (circuit breaker), où le horizon
  dynamique rend la construction de scénarios infeasible plus naturelle.
- Cas réalistes méca → `tests/verticals/mech_workshop/golden_cases/` (à venir).

---

## Étape 2.2 — Module score de confiance ✅

**Objectif** : un score [0, 1] qui résume la confiance qu'on peut accorder à
n'importe quel résultat solver, calculable de façon déterministe.

**Livrables**
- `src/core/scoring.py` — engine générique :
  - 4 métriques universelles, normalisées dans [0, 1] (1 = bon) :
    - `status_quality` : OPTIMAL=1.0, FEASIBLE=0.7, UNKNOWN=0.3, INFEASIBLE=0.0
    - `gap_to_best_known` : `1 - min(gap %, 100 %) / 100 %` ; 0.5 si non mesurable
    - `solve_time_ratio` : `1 - sqrt(t / time_limit)`
    - `machine_utilization` : `busy_time / (makespan × n_machines)`
  - **Hard gate** `validate_schedule` : si invalide → `overall = 0.0`
  - Agrégation : moyenne pondérée par les poids fournis par la verticale.
- `src/verticals/mech_workshop/scoring_config.py` — `MECH_CONFIDENCE_WEIGHTS` :
  40 % util / 30 % status / 20 % gap / 10 % time, justification documentée.
- `tests/test_scoring.py` — 13 tests dont intégration solveur réel sur baseline 3×3.

**Métriques**
- 13 tests / < 1 s runtime
- Score validé sur cas baseline 3×3 (OPTIMAL, util 100 %, time 0.1 s) : **> 0.85**

**Statut** : ✅ stabilisée le 2026-04-30.

---

## Étape 2.3 — Module simulation opérationnelle ✅

**Objectif** : capturer les signaux qu'un chef d'atelier humain refuserait,
au-delà du makespan que le solveur minimise.

**Livrables**
- `src/core/simulation.py` — engine générique :
  - **Métriques machine** : productive/setup/idle time, setup_ratio,
    micro_pause_count, family_transitions.
  - **Métriques job** : duration_sum, span, fragmentation_ratio.
  - **Verdict** : `ACCEPT` / `WARN` / `REJECT`, cohérence garantie par
    `model_validator` (impossible de construire un report incohérent).
  - **Violations déclaratives** : `setup_ratio_high`, `setup_ratio_critical`,
    `micro_pauses_excess`, `job_fragmentation_high`.
- `src/verticals/mech_workshop/simulation_config.py` — `MECH_SIMULATION_THRESHOLDS` :
  - `micro_pause_threshold = 5` min
  - `max_setup_ratio = 0.30` (WARN), `reject_setup_ratio = 0.50` (REJECT)
  - `max_micro_pauses_per_machine = 3`
  - `max_job_fragmentation = 0.30`
  - Justification métier de chaque seuil documentée en docstring.
- `tests/test_simulation.py` — 11 tests couvrant ACCEPT, WARN, REJECT, garde-fous.

**Métriques**
- 11 tests / < 1 s runtime
- Verdict confirmé sur scénarios calibrés : setup 100/110 → REJECT, setup 4/14 → ACCEPT,
  4 micro-pauses (> 3) → WARN, fragmentation 90 % (> 30 %) → WARN.

**Statut** : ✅ stabilisée le 2026-04-30.

---

## Métriques cumulées Phase 2

| Étape | Tests ajoutés | Runtime ajouté | Statut |
|-------|--------------:|----------------|--------|
| Refactor multi-vertical | 0 | 0 | (préliminaire) |
| 2.1 — golden cases | 16 (15 cases + harness) | 0.6 s | 🟡 |
| 2.2 — scoring | 13 | < 1 s | ✅ |
| 2.3 — simulation | 11 | < 1 s | ✅ |
| **Total Phase 2** | **40** | **~ 3 s** | 2/5 |

Suite de tests globale : **228 passants** (vs 188 à l'ouverture Phase 2).

---

## Décisions techniques marquantes

| Date | Décision | Justification |
|------|----------|---------------|
| 2026-04-30 | Refactor multi-vertical avant d'attaquer Phase 2 sur le fond | Sans cette discipline, le code méca aurait pollué le moteur. Coût marginal faible maintenant, dissuasif plus tard. |
| 2026-04-30 | Phase 2.1 livrée en 2 étapes (harness + 5, extension à 15) plutôt que 100 d'un coup | Le coût n'est pas le runtime mais le temps humain de design (chaque cas demande un optimum analytique). 15 cases valident le harness à plus grande échelle, suite à étendre progressivement par 3 leviers (hand-crafted, Taillard auto, régression-driven). |
| 2026-04-30 | Cas INFEASIBLE différés à 2.4 | Le horizon dynamique du solveur rend la construction propre d'un cas infeasible non-trivial ; on en aura besoin de toute façon en 2.4 (circuit breaker), où il sera conçu dans le bon contexte. |
| 2026-04-30 | Pattern engine ↔ vertical confirmé 3 fois (preflight, scoring, simulation) | La discipline tient. Toute future verticale (santé, éducation, services techniques) suivra le même schéma. |
| 2026-04-30 | Hard gate `validate_schedule` dans le scoring | Aucune pondération ne peut compenser un planning invalide. Mieux vaut un score 0 explicite qu'une confiance trompeuse. |
| 2026-04-30 | Verdict `SimulationReport` validé par `model_validator` | Garantit qu'un report ne peut pas être construit avec un verdict ACCEPT alors qu'il contient des violations REJECT. Le bug est attrapé à la construction, pas au runtime tardif. |

---

## Risques identifiés

| Risque | Probabilité | Impact | Atténuation |
|--------|-------------|--------|-------------|
| Extension à 100 golden cases plus longue que prévu (chaque cas = travail manuel d'optimum analytique) | Élevée | Faible | Mix hand-crafted ciblé + Taillard auto + régression-driven. Pas bloquant pour avancer. |
| Calibration méca des seuils (scoring + simulation) inadaptée vs réalité PME | Moyenne | Moyen | À recalibrer post-pilotes (Phase 8). Les seuils sont déjà documentés et isolés dans la verticale, donc ajustables sans toucher l'engine. |
| Circuit breaker INFEASIBLE (2.4) plus complexe que prévu si MIS extraction bug | Moyenne | Moyen | 2.4 prévu après stabilisation 2.1-2.3. MIS approximé déjà prévu en Phase 1.8, peut être fait en parallèle. |
| Pipeline complet (2.5) révèle incohérences entre 2.2 et 2.3 (un score haut sur un planning rejeté par simulation) | Moyenne | Moyen | Précisément l'objet de 2.5 : forcer la cohérence engine. La doctrine simple = simulation REJECT prime sur score haut. |

---

## Prochaines étapes

### Restant Phase 2

1. **Phase 2.4** — Circuit breaker INFEASIBLE (3 retries → bascule MIS) — pure engine
2. **Phase 2.5** — Pipeline complet `solving → validation → simulation → score → décision` — orchestration

### Gate 1 (fin Phase 2)

**Critère** : < 1 erreur silencieuse / 100 ateliers tests.

Une "erreur silencieuse" = un planning que le solveur déclare OPTIMAL ou
FEASIBLE mais qui violerait `validate_schedule`, ou que la simulation rejette
sans que le score le signale. Les 3 garde-fous (`validate_schedule` hard gate,
`SimulationVerdict.REJECT`, score gate) doivent converger.

---

*Mis à jour à chaque étape stabilisée.*
