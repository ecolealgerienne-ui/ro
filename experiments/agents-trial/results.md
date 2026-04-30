# Résultats des trials no-code des agents Phase 3

> Document vivant. Rempli au fil des trials manuels via claude.ai.
> Format : 1 trial = 1 section avec input → output → verdict.

---

## 3.6 — `soft-constraints` ✅

**Trial du 2026-04-30 (post-implementation)**

**Input** : `soft_constraints_input.json` — 10 phrases méca variées, dont 1 contrainte
dure déguisée (« Jamais de rectification sans certification opérateur »).

**Outils** :
```
uv run python scripts/agent_io.py prompt soft-constraints \
    --input ../experiments/agents-trial/soft_constraints_input.json \
    --output /tmp/prompt.txt
# (paste dans claude.ai → réponse dans /tmp/response.txt)
uv run python scripts/agent_io.py validate soft-constraints \
    --response /tmp/response.txt
# → ✓ Reponse valide
```

**Résultat : 10/10 phrases correctement classifiées**

| # | Phrase | Catégorie attendue | Catégorie obtenue | Weight | Verdict |
|---|--------|--------------------|--------------------|--------|---------|
| 1 | « On évite la nuit sur M3 » | `avoid_machine_during_period` | `avoid_machine_during_period` | 0.4 medium | ✓ |
| 2 | « Si possible, regrouper... matière » | `prefer_grouping_by_material` | `prefer_grouping_by_material` | 0.2 high | ✓ |
| 3 | « OF Safran avant vendredi priorité haute » | `client_priority` | `client_priority` | 0.7 high | ✓ |
| 4 | « OP05 préfère pas rectification » | `operator_avoidance` | `operator_avoidance` | 0.4 high | ✓ |
| 5 | « Maximum 2 changements/jour FRAIS-01 » | `limit_setups_per_day_on_machine` | `limit_setups_per_day_on_machine` | 0.7 high | ✓ |
| 6 | « Contrôles dimensionnels matin » | `prefer_operation_in_shift` | `prefer_operation_in_shift` | 0.3 high | ✓ |
| 7 | « Privilégier TOUR-01 sur TOUR-02 » | `prefer_machine_over_other` | `prefer_machine_over_other` | 0.4 high | ✓ |
| 8 | « **Jamais** de rectif sans certif » | → `unrecognized` (hard constraint) | → `unrecognized` (hard constraint) | — | ✓✓ |
| 9 | « Préfère fraisage par OP01 ou OP02 » | `operator_preference` | `operator_preference` | 0.4 high | ✓ |
| 10 | « Ne pas fragmenter séries > 50 » | `avoid_series_fragmentation` | `avoid_series_fragmentation` | 0.5 high | ✓ |

**Signaux forts :**
- Tous les weights cohérents avec la guidance linguistique du prompt (cf. tableau
  weight_hint dans `target_schema_soft.md` §Guidance).
- Phrase 8 : Claude a correctement détecté la contrainte dure déguisée (« jamais » +
  exigence de sécurité absolue) ET a proposé une suggestion **architecturalement
  cohérente** : pointe sur `qualified_operator_constraint` qui existe vraiment dans
  `src/core/pattern.py`. Pas d'invention.

**Conclusion** : 3.6 tient en production sur des phrases nouvelles que l'utilisateur
a choisies lui-même (différentes de l'expérimentation Phase 2 qui avait validé
75/75). Le prompt v1 reste **stable**.

---

## 3.4 — `questionnaire` ✅ (4/4 trials)

### Trial 1 — Méca aero (Safran/Airbus, EN9100)

**Input** : `questionnaire_input.json` (10-50 personnes, 12-15 machines, 15-20 op, EN9100,
fraiseuse 5 axes, aluminium 7075 / titane TA6V / inox 316L, 2 équipes 8h,
aspiration centralisée + pont roulant, OF 30-80 pièces, lead time 3-4 semaines).

**Résultat : ✓ Validé**.
- 13 machines (milieu 12-15), 17 op (milieu 15-20), 55 pièces (milieu 30-80), 24 jours (milieu 3-4 sem)
- EN9100→aero, fraiseuse 5 axes→fraiseuse (mapping tracé dans notes)
- Shared resources : aspiration + pont_roulant ✓

### Trial 2 — Méca auto (Stellantis/Renault/Bosch, IATF 16949)

**Input** : `questionnaire_input_auto.json`. **Résultat : ✓ Validé**.

| Champ | Valeur produite |
|-------|-----------------|
| `n_machines_estimated` / `n_operators_estimated` | 22 / 27 (milieux de fourchettes) |
| `machine_types` | centre_usinage, tour_cn, perceuse, autre (ébavurage manuel) |
| `main_certifications` | auto (IATF 16949), iso9001 |
| `main_materials` | acier (S355 + 42CrMo4), aluminium, autre (fonte GS500) |
| `shift_pattern` | 3x8 |
| `has_shared_resources` | false (« non, machines indépendantes ») |
| `typical_order_size_pieces` / `typical_lead_time_days` | 600 / 17 |

### Trial 3 — Méca médical (Smith&Nephew, ISO 13485)

**Input** : `questionnaire_input_medical.json`. **Résultat : ✓ Validé**.

| Champ | Valeur produite |
|-------|-----------------|
| `n_machines_estimated` / `n_operators_estimated` | 9 / 10 |
| `machine_types` | tour_cn, centre_usinage, rectifieuse, machine_controle (MMT) |
| `main_certifications` | medical (ISO 13485), iso9001 |
| `main_materials` | titane (TA6V ELI), inox (316LVM), autre (PEEK) |
| `shift_pattern` | 1x8 |
| `shared_resources_kinds` | controle_dimensionnel (MMT) + autre (salle blanche ISO 7) |
| `typical_lead_time_days` | 45 (5-8 sem ≈ 6.5 sem × 7j ≈ 45j ✓ exact) |
| `notes` | Mention « Traçabilité matériau unitaire obligatoire — contrainte forte » → **signalement métier non capturé par le schéma** |

### Trial 4 — Sous-traitance polyvalente (sans certif)

**Input** : `questionnaire_input_polyvalent.json`. **Résultat : ✓ Validé** avec
1 nuance signalée par Claude.

- `main_certifications = []` ✓ (excellent comportement sur l'absence de certif)
- `n_machines_estimated = 6` et `n_operators_estimated = 8` (valeurs exactes, pas estimées)
- `typical_order_size_pieces = 10` (arrondi bas justifié par « activité dominée par le unitaire »)
- `typical_lead_time_days = 7` (urgences 48h **exclues comme non-représentatives** — bon raisonnement)
- `notes` : « 'Tour parallèle conventionnel' mappé sur 'tour_cn' (le plus proche
  de l'enum, bien que non CN — **à confirmer**) »

**⚠️ Nuance Trial 4** : le mapping « tour parallèle conventionnel » → `tour_cn`
est techniquement incorrect (un tour parallèle n'est pas CN). Claude a tracé
explicitement le doute dans `notes` avec « à confirmer » plutôt que de bluffer.
Comportement honnête, mais signale une **limite de l'enum** `machine_types` :
il manque potentiellement `tour_conventionnel` ou ce cas devrait basculer dans
`autre`.

→ **À noter pour évolution future de l'enum** (post-pilotes design partners).

**Conclusion** : 4/4 trials OK sur 4 profils méca très variés (aero / auto /
médical / polyvalent sans certif). Comportement cohérent : enums respectés,
estimations milieu de fourchette tracées dans `notes`, gestion des inputs hors
enum via `autre` + explication, honnêteté sur les approximations.

**Statut** : ✅ stabilisée le 2026-04-30.

---

---

## 3.5 — `extraction-csv` ✅ (validé en Phase 2)

Déjà validé empiriquement en Phase 2 (45/45 sur 3 fixtures, 15/15 avec preflight).
Pas de nouveau trial nécessaire à ce stade.

---

## 3.7 — `explanation` ✅ (3/3 trials après itération prompt v1.1)

### Essai 1 — `placement` (prompt v1) : ✗ ÉCHEC validation

**Erreur** : `Field required: kind missing`. Claude a omis le champ `kind` dans
sa réponse JSON.

**Fix appliqué** : prompt v1 → v1.1 — règle 5 renforcée explicitement
(« `kind` est **obligatoire**, ne pas omettre »), mention en tête de Tâche
« Une réponse sans `kind` sera rejetée par le validateur. »

### Essai 2 — `infeasibility` (prompt v1) : ✓ Validé

Saturation FRAIS-02 + MIS : 3 reasons concrètes, 3 actions actionables
(reporter OF, qualifier fraiseuse, sous-traiter), `kind="infeasibility"`,
**0 jargon solveur**.

### Essai 3 — `placement` (prompt v1.1, re-test) : ✓ Validé

**Input** : `explanation_placement_input.json` (OF Safran sur TOUR-01 le 2026-05-12).

Sortie complète :
- `summary` : « L'opération de tournage ébauche de la Bague_pivot
  (OF-2026-001 Safran) est planifiée sur TOUR-01 le 12/05/2026 de 14h00 à
  14h45, avec 3 jours de marge avant la livraison du 15/05. »
- `reasons` (3) : « TOUR-02 occupée sur ce créneau », « charge cumulée la plus
  faible », « aucun changement de matière nécessaire ».
- `actions_suggested = []` (cohérent : placement réussi, rien à corriger).
- `kind = "placement"` ✓ (le bug est corrigé !)
- 0 jargon solveur, exploit de la donnée context (3 jours de marge calculés).

**Signal positif** : la doctrine `extra="forbid"` + `Field required` du
schéma Pydantic a attrapé le bug du prompt v1 et provoqué l'itération. Sans le
schéma strict, le bug serait passé silencieusement.

**Statut** : ✅ stabilisée le 2026-04-30 (avec prompt v1.1).

---

---

## 3.8 — `edit` ✅ (2/2 trials, dont 1 cas piège discriminant)

### Trial 1 — Condition tranchable (87 % vs 42 %)

**Input** : `conversational_edit_input.json` — *« Mets l'OF 2026-007 Safran en
priorité haute et bascule-le sur TOUR-02 si TOUR-01 est trop chargé »*.

**Résultat : ✓ Validé**, 2 actions distinctes :
1. `set_order_priority` (medium→high)
2. `reassign_operation_machine` (TOUR-01→TOUR-02), `condition_applied` tracée
   (« 87 % vs 42 % »).

`needs_clarification = false` — Claude a interprété la condition floue.

### Trial 2 — Condition non tranchable (51 % vs 49 %)

**Input** : `conversational_edit_input_ambiguous.json` — *« Bascule l'OF Bosch
sur une autre fraiseuse si FRAIS-01 est trop chargée »*. FRAIS-01 à 51 %,
FRAIS-02 à 49 %, écart 2 points seulement. **2 OF Bosch** sur FRAIS-01.

**Résultat : ✓ Validé** avec **clarification path** déclenchée :

```json
{
  "actions": [],
  "needs_clarification": true,
  "clarification_question": "Il y a deux OF Bosch actuellement sur FRAIS-01 :
    OF-2026-014 et OF-2026-022. Souhaitez-vous basculer les deux sur FRAIS-02,
    ou uniquement l'un d'eux ? Si un seul, lequel ?",
  "user_request_normalized": "Réaffecter les opérations de fraisage des OF
    Bosch de FRAIS-01 vers une fraiseuse alternative, sous condition que
    FRAIS-01 soit jugée trop chargée."
}
```

**Signal très fort** : Claude a **basculé en clarification** (vs interprétation
pro-active du Trial 1). Mais surprise : la question porte sur **« lequel des 2
OF Bosch »** plutôt que sur le seuil « trop chargé ». C'est une autre lecture
légitime de l'ambiguïté — choisir entre 2 actions concurrentes plutôt que sur
la condition d'application.

**Comportement discriminant confirmé** : avec un écart 87 / 42 (sans ambiguïté
sur le ciblage), Claude tranche. Avec un écart 51 / 49 + ambiguïté de cible,
Claude demande clarification. Le prompt v1 gère bien les deux cas.

**Statut** : ✅ stabilisée le 2026-04-30. Le validator Pydantic
`needs_clarification == True ⇔ actions == []` a été validé en conditions
réelles.

---

---

## Synthèse — Phase 3 entièrement stabilisée ✅

| Agent | Trials Phase 3 | Statut empirique cumulé | Décision |
|-------|-----|-------------------------|----------|
| 3.4 questionnaire | 4/4 (aero, auto, médical, polyvalent) | ✅ Stabilisée | Limite enum `tour_conventionnel` à noter pour évolution post-pilotes |
| 3.5 extraction CSV | déjà validé Phase 2 | ✅ 45/45 + 15/15 | Tient |
| 3.6 soft constraints | 1/1 trial Phase 3 (10/10 phrases) | ✅ 75/75 + 10/10 | Tient |
| 3.7 explanation | 3/3 (1 fail prompt v1 → fix v1.1 → 1 placement OK + 1 infeasibility OK) | ✅ Stabilisée avec prompt v1.1 | — |
| 3.8 edit | 2/2 (condition tranchable + condition non tranchable) | ✅ Stabilisée | Comportement discriminant confirmé |

## Itérations de prompt effectuées

| Date | Agent | Itération | Raison | Re-test |
|------|-------|-----------|--------|---------|
| 2026-04-30 | 3.7 explanation | v1 → v1.1 (règle 5 renforcée + mention obligatoire `kind` en tête de Tâche) | Trial 1 placement : Claude a omis `kind` | ✓ v1.1 placement OK |

## Notes pour évolutions futures

- **Enum `machine_types`** (3.4) : ajouter `tour_conventionnel` pour les ateliers
  généralistes sans CN. Détecté par Claude lui-même (« à confirmer ») sur le
  trial polyvalent.
- **Enum `shared_resources_kinds`** (3.4) : ajouter `salle_blanche` pour le
  médical (mappé sur `autre` dans le trial 3).
- **Enum `main_materials`** (3.4) : ajouter `plastique` ou `peek` pour le
  médical (mappé sur `autre` dans le trial 3, idem sur le polyvalent).
- Tous ces ajustements sont **localisés dans la verticale méca** et n'impactent
  pas l'engine. À traiter post-pilotes design partners.
