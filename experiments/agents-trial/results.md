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

## 3.4 — `questionnaire` ✅

**Trial du 2026-04-30**

**Input** : `questionnaire_input.json` — réponses onboarding type PME aero
(10-50 personnes, 12-15 machines, 15-20 op, EN9100, fraiseuse 5 axes,
aluminium 7075 / titane TA6V / inox 316L, 2 équipes 8h, aspiration centralisée
+ pont roulant, OF 30-80 pièces, lead time 3-4 semaines, donneur Safran).

**Résultat : ✓ Validé** (toutes les valeurs cohérentes avec les inputs)

| Champ | Valeur produite | Verdict |
|-------|-----------------|---------|
| `workshop_name` | "Atelier mécanique de précision" | ✓ générique mais valide |
| `n_machines_estimated` | 13 (milieu de fourchette 12-15) | ✓ |
| `n_operators_estimated` | 17 (milieu de fourchette 15-20) | ✓ |
| `machine_types` | tour_cn, fraiseuse, rectifieuse | ✓ 3/3 mappés |
| `main_certifications` | aero, iso9001 | ✓ EN9100 → aero |
| `main_materials` | aluminium, inox, titane | ✓ 3/3 normalisés (7075/316L/TA6V → enum) |
| `shift_pattern` | 2x8 | ✓ |
| `has_shared_resources` | true | ✓ |
| `shared_resources_kinds` | aspiration, pont_roulant | ✓ 2/2 mappés |
| `typical_order_size_pieces` | 55 (milieu de fourchette 30-80) | ✓ |
| `typical_lead_time_days` | 24 (milieu de fourchette 3-4 semaines) | ✓ |
| `notes` | Détaille chaque approximation, mentions Safran/Airbus, mapping fraiseuse 5 axes → fraiseuse, EN9100 → aero | ✓ excellent |

**Signaux forts** :
- Les enums fermés sont respectés (matériaux, certifications, shifts) sans inventer de valeur.
- Les valeurs estimées au milieu de fourchette sont **explicitement signalées** dans `notes` — comportement honnête et auditable.
- Les valeurs hors enum (« fraiseuse 5 axes ») sont **mappées au plus proche + tracées dans notes** plutôt que basculées en `autre`. Choix défendable.

**Conclusion** : 3.4 tient sur cet input. À reproduire sur 4-5 autres profils PME (méca auto, médical, sous-traitance hors aero) avant de basculer en ✅ stabilisée.

---

---

## 3.5 — `extraction-csv` ✅ (validé en Phase 2)

Déjà validé empiriquement en Phase 2 (45/45 sur 3 fixtures, 15/15 avec preflight).
Pas de nouveau trial nécessaire à ce stade.

---

## 3.7 — `explanation` ⚠️ — itération de prompt nécessaire

**Trial du 2026-04-30 (2 essais)**

### Essai 1 — `placement` : ✗ ÉCHEC validation

**Input** : `explanation_placement_input.json` (OF Safran sur TOUR-01 le 2026-05-12).

**Erreur** :
```
1 validation error for ExplanationOutput
kind
  Field required [type=missing, ...]
```

**Diagnostic** : Claude a omis le champ `kind` dans sa réponse JSON, malgré la
présence du champ dans le schéma fourni. Le prompt v1 n'était pas assez strict
sur l'obligation de copier `kind` depuis le contexte.

**Fix appliqué** (commit suivant) : prompt v1 mis à jour — règle 5 renforcée
explicitement : « `kind` est **obligatoire** et doit être copié exactement
depuis "Type d'explication demandée". Ne pas omettre. » Ajout d'une mention en
tête de la section "Tâche" : « Une réponse sans `kind` sera rejetée par le
validateur. »

### Essai 2 — `infeasibility` : ✓ Validé

**Input** : `explanation_infeasibility_input.json` (saturation FRAIS-02 + MIS).

**Sortie** :
- `summary` (1 phrase) : explique en français pro la saturation de FRAIS-02 et
  l'absence de fraiseuse alternative qualifiée aluminium 7075. **0 jargon
  solveur**.
- `reasons` (3) : charge 105 % FRAIS-02, 14 h cumulées sur 4 OF Safran, pas
  de fraiseuse alternative qualifiée alu.
- `actions_suggested` (3) : reporter un OF, qualifier une fraiseuse, sous-traiter.
- `kind` = "infeasibility" ✓

**Verdict essai 2** : excellent. Cohérent avec l'input, actionable, sans jargon.

**Conclusion** : prompt à itérer (fait) puis re-tester `placement`. Reste 🔵 jusqu'à
re-validation des deux modes.

---

---

## 3.8 — `edit` ✅ avec observation

**Trial du 2026-04-30**

**Input** : `conversational_edit_input.json` — *« Mets l'OF 2026-007 Safran en
priorité haute et bascule-le sur TOUR-02 si TOUR-01 est trop chargé »*. Cas
piège : 2 instructions dont une **conditionnelle** (« si trop chargé »).

**Résultat : ✓ Validé** (2 actions distinctes produites)

| Action | kind | target | Verdict |
|--------|------|--------|---------|
| 1 | `set_order_priority` | OF-2026-007 | ✓ priorité medium → high, rationale clair |
| 2 | `reassign_operation_machine` | OF-2026-007 | ✓ TOUR-01 → TOUR-02, condition_applied tracée |

`needs_clarification = false`, `user_request_normalized` reformule la demande
proprement.

**Comportement notable** : Claude a **interprété la condition floue** « si trop
chargé » plutôt que de demander clarification. Il a calculé que TOUR-01 à 87 %
vs TOUR-02 à 42 % satisfait la condition, et a tracé cette interprétation dans
`params.condition_applied`.

**Verdict** : valide, mais le **comportement pro-actif** mérite d'être observé
sur d'autres trials. Cas où on aurait préféré une clarification : si TOUR-01
était à 51 % et TOUR-02 à 49 %, est-ce que Claude aurait quand même tranché ?

**Suggestion d'évolution** (à voir plus tard) : ajouter dans le prompt un
paragraphe sur la **gestion des conditions floues** — par défaut interpréter
si l'écart est significatif (> 30 % par exemple), sinon demander clarification.

**Conclusion** : 3.8 reste 🔵 le temps de tester 2-3 autres demandes
conversationnelles, notamment des cas où la condition n'est pas tranchable.

---

---

## Synthèse des risques restants

| Agent | Statut empirique | Risque résiduel | Décision |
|-------|------------------|-----------------|----------|
| 3.4 questionnaire | ✓ 1/1 trial OK (1 input PME aero) | Faible-moyen | À reproduire sur 4-5 profils variés (auto, médical, hors aero) |
| 3.5 extraction CSV | ✅ 45/45 + 15/15 | Faible | Tient |
| 3.6 soft constraints | ✅ 75/75 + 10/10 | Faible | Tient |
| 3.7 explanation | ⚠️ 1 fail (kind manquant) + 1 OK | Moyen | Prompt durci. Re-tester `placement` après le fix. Puis valider sur 5+ trials par mode. |
| 3.8 edit | ✓ 1/1 trial OK avec observation (interprétation pro-active des conditions floues) | Moyen | À reproduire sur 4-5 demandes incluant un cas "condition non tranchable" |

## Itérations de prompt à faire

| Date | Agent | Itération | Raison |
|------|-------|-----------|--------|
| 2026-04-30 | 3.7 explanation | v1 → v1.1 (règle 5 renforcée + mention obligatoire `kind` en tête de Tâche) | Trial 1 placement : Claude a omis `kind` |
