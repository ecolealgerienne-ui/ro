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

## 3.4 — `questionnaire` ⬜

**À tester.** Voir commandes ci-dessous.

---

## 3.5 — `extraction-csv` ✅ (validé en Phase 2)

Déjà validé empiriquement en Phase 2 (45/45 sur 3 fixtures, 15/15 avec preflight).
Pas de nouveau trial nécessaire à ce stade.

---

## 3.7 — `explanation` ⬜

**À tester** sur les 2 modes :
- `placement` : `explanation_placement_input.json`
- `infeasibility` : `explanation_infeasibility_input.json`

---

## 3.8 — `edit` ⬜

**À tester.** Cas piège attendu : la fixture demande à la fois un changement de
priorité ET une réassignation conditionnelle ("si TOUR-01 trop chargé"). On veut
voir Claude produire 2 actions distinctes OU demander une clarification sur la
condition.

---

## Synthèse des risques restants

| Agent | Statut empirique | Risque résiduel | Décision |
|-------|------------------|-----------------|----------|
| 3.4 questionnaire | Non testé | Moyen — onboarding critique | À valider sur 5+ trials |
| 3.5 extraction CSV | ✅ 45/45 + 15/15 | Faible | Tient |
| 3.6 soft constraints | ✅ 75/75 + 10/10 | Faible | Tient |
| 3.7 explanation | Non testé | Moyen — UX critique | À valider sur 5+ trials par mode |
| 3.8 edit | Non testé | Moyen — contrôle modifs | À valider sur 5+ trials |
