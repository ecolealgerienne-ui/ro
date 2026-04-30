# Grille d'évaluation par fixture

Une checklist par itération de prompt. À cocher après chaque test dans Claude.

---

## Critères techniques (4)

| # | Critère | Comment vérifier |
|---|---------|------------------|
| T1 | **JSON syntaxiquement valide** | Coller dans `python -c "import json,sys;json.loads(sys.stdin.read())"` ou `jq .` |
| T2 | **Schéma respecté** (champs requis présents) | `machines`, `orders`, `anomalies` racine ; champs requis par item |
| T3 | **Aucune hallucination** | Comparer `machines` et `orders` à ce qui est explicitement dans le CSV |
| T4 | **Aucune valeur silencieusement modifiée** | Durées et dates correspondent exactement au CSV (sauf normalisation explicite) |

## Critères d'extraction (5)

| # | Critère | Comment vérifier |
|---|---------|------------------|
| E1 | **Toutes les OF distinctes du CSV présentes** | Compter les `OF-...` distincts dans le CSV vs `len(orders)` |
| E2 | **Toutes les machines uniques détectées** | Compter les valeurs distinctes de la colonne Machine |
| E3 | **Toutes les opérations parsées** (aucune ligne perdue) | Sum des `len(operations)` = nombre total de lignes du CSV |
| E4 | **Ordre des opérations cohérent** | `sequence_idx` croît dans l'ordre des lignes du CSV pour chaque OF |
| E5 | **`type_inferred` correct** sur les machines | TOUR-* → tour, FRAIS-* → fraiseuse, etc. |

## Critères de normalisation (3)

| # | Critère | Comment vérifier |
|---|---------|------------------|
| N1 | **Matières normalisées correctement** | "Aluminium 7075" → `aluminium_7075`, etc. |
| N2 | **Opérations normalisées correctement** | "Tournage ebauche" → `tournage_ebauche`, etc. |
| N3 | **Valeurs inconnues préservées + anomalie** | Si une matière n'est pas dans la liste canonique, forme originale gardée + anomalie |

## Critères d'anomalies (3)

| # | Critère | Comment vérifier |
|---|---------|------------------|
| A1 | **Anomalies évidentes flaggées** | Durée négative, durée nulle sur op CN, machine absente |
| A2 | **Anomalies subtiles flaggées** | Durée hors normes (> 24h, < 1 min), date dans le passé, OF doublon |
| A3 | **Pas de fausses anomalies** | Aucune anomalie sur cas propres |

---

## Score consolidé par fixture

```
Total : T1+T2+T3+T4 + E1+E2+E3+E4+E5 + N1+N2+N3 + A1+A2+A3 = 15
```

| Fixture | T1 | T2 | T3 | T4 | E1 | E2 | E3 | E4 | E5 | N1 | N2 | N3 | A1 | A2 | A3 | **/15** |
|---------|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|---------|
| F1 simple | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | /15 |
| F2 ortho | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | /15 |
| F3 ERP | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | /15 |
| F4 anomalies | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | /15 |
| F5 volume | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | /15 |

---

## Seuils de validation

- **Critère par critère** : doit être ✓ pour considérer un point validé
- **Score par fixture** : ≥ 13/15 = OK, 10-12 = à raffiner, < 10 = problème majeur
- **Pour passer à la phase code** :
  - F1 ≥ 14/15 (cas propre doit être quasi-parfait)
  - F2-F4 ≥ 12/15
  - F5 ≥ 10/15 (volume = tolérance plus large)
  - Et **A1 = ✓ sur F4** (anomalies évidentes flaggées) — non-négociable pour le trust layer

## Notes pour évaluer rapidement

1. Lance F1 d'abord, attends-toi à un ~14/15
2. Si T1 (JSON valide) échoue → priorité à corriger le prompt avant d'aller plus loin
3. Si A1 (anomalies évidentes) échoue → c'est rouge, le trust layer est compromis
4. Si E5 (type machine inféré) faillit → ajoute des exemples dans le prompt
5. Hallucinations T3 = pire scenario, à diagnostiquer en priorité
