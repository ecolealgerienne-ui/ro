# Fixture v1 — 15 phrases types à tester

> Phrases telles qu'un chef d'atelier les dirait spontanément. Couvre :
> cas évidents, cas avec paramètres complexes, cas ambigus, et cas pièges
> (contrainte dure déguisée, catégorie non listée, négations doubles).

À copier-coller dans la zone `{{PHRASES}}` du prompt.

---

```
1. On évite de faire tourner la machine M3 la nuit.

2. Privilégier la machine FRAIS-01 sur FRAIS-02 quand les deux sont libres.

3. Regrouper si possible les pièces en aluminium 7075.

4. L'opérateur OP05 préfère ne pas faire de rectification.

5. Les OF Safran doivent finir avant le vendredi.

6. Éviter de fragmenter les séries de plus de 20 pièces.

7. Maximum 3 changements de production par jour sur la fraiseuse 5 axes.

8. Les contrôles dimensionnels de préférence le matin.

9. On ne lance jamais de tournage la nuit.

10. Si possible, regrouper les commandes du même client le même jour.

11. OP12 est en formation cette semaine, à éviter sur les pièces critiques.

12. On préfère que les opérations de fraisage soient faites par OP01 ou OP02.

13. Évitons de mettre du titane sur la même machine que de l'aluminium dans la même journée.

14. Les pièces médicales en priorité absolue sur le reste.

15. Il faut être certifié EN 9100 pour faire du fraisage 5 axes.
```

---

## Comportement attendu (référentiel d'évaluation)

| # | Phrase | Catégorie attendue | Notes |
|---|--------|---------------------|-------|
| 1 | « éviter M3 la nuit » | `avoid_machine_during_period` | weight ~0.4 (« on évite »), period_type=night |
| 2 | « privilégier FRAIS-01 sur FRAIS-02 » | `prefer_machine_over_other` | weight ~0.4 (« privilégier ») |
| 3 | « regrouper aluminium 7075 » | `prefer_grouping_by_material` | weight ~0.2 (« si possible »), material=aluminium 7075 |
| 4 | « OP05 préfère pas rectif » | `operator_avoidance` | weight ~0.4, op=OP05, type=rectification |
| 5 | « OF Safran avant vendredi » | `client_priority` | priority=high, client=Safran, deadline_hint="avant vendredi" |
| 6 | « pas fragmenter > 20 pièces » | `avoid_series_fragmentation` | weight ~0.5, min_series_size=20 |
| 7 | « max 3 setups/jour FRAIS-5X » | `limit_setups_per_day_on_machine` | weight ~0.6-0.8 (« maximum » est strict) |
| 8 | « contrôles dim. matin » | `prefer_operation_in_shift` | weight ~0.3, operation=controle_dimensionnel, shift=morning |
| 9 | « **jamais** tournage la nuit » | `avoid_machine_during_period` | weight 0.95-1.0, **rationale doit signaler** que c'est probablement une contrainte dure |
| 10 | « regrouper commandes même client même jour » | `prefer_grouping_by_client` | weight ~0.2, time_window=same_day |
| 11 | « OP12 formation cette semaine » | **catégorie complexe** : indispo temporaire (n'existe pas dans le catalogue) → soit `operator_avoidance` partiel, soit `unrecognized` avec suggestion | Test du jugement |
| 12 | « fraisage par OP01 ou OP02 » | `operator_preference` | weight ~0.4, operation=fraisage, preferred=[OP01, OP02] |
| 13 | « pas titane et alu même machine même jour » | **catégorie inédite** : conflit matières-machine | Probablement `unrecognized` ou `other` selon jugement |
| 14 | « pièces médicales priorité absolue » | `client_priority` | priority=critical, client=médical (interprété comme un secteur, pas un nom de client précis) |
| 15 | « certifié EN 9100 pour fraisage 5 axes » | **CONTRAINTE DURE** déguisée | Doit aller dans `unrecognized` avec mention « contrainte dure » |

## Critères d'évaluation par phrase

Pour chaque phrase :
- ☐ **Catégorie** correcte (ou `unrecognized` justifié pour les phrases ambiguës)
- ☐ **Paramètres** correctement extraits (références préservées : M3 reste M3)
- ☐ **Weight_hint** dans la fourchette attendue (±0.2)
- ☐ **Rationale** cohérent avec le langage (mention « contrainte dure » sur phrases catégorielles)
- ☐ **Confidence** raisonnable (high/medium/low)

## Score sur 15 (chacune notée pass/fail sur l'ensemble des 5 critères)

- **≥ 12/15** : risque levé, on peut industrialiser
- **8-11/15** : prompt à raffiner (v2)
- **< 8/15** : revoir l'approche (catégories trop complexes, ou phrases mal choisies, ou catalogue insuffisant)
