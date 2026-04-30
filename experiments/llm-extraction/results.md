# Journal d'expérimentations — LLM extraction

> Une entrée par itération de prompt. Logger même les échecs : ils sont utiles pour comprendre où le modèle bute.

---

## Itération 1 — `prompt_v1` × `fixture_01_simple`

**Date** : 2026-04-30
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Prompt** : `prompt_v1.md`
**Fixture** : `fixture_01_simple.csv`

### Output produit par Claude

JSON structurellement parfait — copié dans `results-iteration-01-output.json` pour archivage.

Résumé : 8 machines détectées (correctes), 5 OF avec 15 opérations totales correctement normalisées, 4 matières correctement mappées (aluminium_7075, acier_42CrMo4, titane_TA6V, acier_inox_316L). Sortie JSON pure, pas de texte parasite.

### Évaluation : 14/15

**Critères techniques (4/4)**
- T1 JSON valide : ✓
- T2 Schéma respecté : ✓
- T3 Aucune hallucination : ✓ (8 machines listées = 8 machines du CSV, exactement)
- T4 Aucune valeur modifiée silencieusement : ✓

**Critères d'extraction (5/5)**
- E1 5 OF présentes : ✓
- E2 8 machines détectées : ✓
- E3 15 opérations parsées : ✓
- E4 Ordre opérations respecté : ✓ (sequence_idx croît correctement)
- E5 Type de machine inféré correct : ✓ (TOUR→tour, FRAIS-5X→fraiseuse, RECT→rectifieuse, etc.)

**Critères de normalisation (2/2 évaluables)**
- N1 Matières normalisées : ✓
- N2 Opérations normalisées : ✓ ("Controle 3D"→`controle_dimensionnel`, "Fraisage 5 axes"→`fraisage_5axes`)
- N3 Valeurs inconnues préservées : N/A (F1 propre)

**Critères d'anomalies (0/1 évaluable)**
- A1 Anomalies évidentes flaggées : N/A (F1 propre)
- A2 Anomalies subtiles flaggées : N/A
- A3 Pas de fausses anomalies : ✗ — **2 fausses positives**

### Détail du seul échec — A3 (sur-zèle)

Claude a flaggé 2 anomalies non sollicitées :
1. "Durée 5 min ébavurage sur FRAIS-02 — inhabituellement basse"
2. "Durée 3 min marquage sur FRAIS-01 — inhabituellement basse"

Référentiel `OPERATION_BASE_TIMES_MIN` (générateur) :
- Ébavurage : moyenne 10 min, std 4 → 5 min = -1.25σ, dans la fourchette normale
- Marquage : moyenne 3 min, std 1 → 3 min = exactement la moyenne

Claude a appliqué un "common sense industriel" implicite ("durée courte sur machine CN = suspect") au-delà des seuils numériques explicites du prompt. La règle "Valeurs aberrantes (durée > 24h sur op CN, durée < 1 min sur usinage)" était trop vague et a laissé de la place à l'intuition.

### Observations qualitatives

**Ce qui a fonctionné** :
- Sortie JSON pure (Claude a respecté "uniquement le JSON, pas de texte avant ni après")
- Normalisation parfaite — aucune ambiguïté manquée
- Hallucinations zéro — aucune machine ou OF inventée
- Inférence machine_type robuste sur tous les préfixes

**Ce qui a surpris** :
- Sur-zèle marqué dès F1 (cas propre) — confirme que le trust layer doit absolument cadrer ce comportement
- Le faux positif sur le marquage (3 min = pile la moyenne) montre que Claude n'a même pas regardé la cohérence statistique, juste l'intuition "court sur machine CN = louche"

**Ce qu'il faut retenir** :
- Le prompt doit donner des **seuils chiffrés explicites**, pas des règles qualitatives
- Lister explicitement les opérations à durées normalement courtes pour court-circuiter le sur-zèle

### Pistes de raffinement → `prompt_v2`

1. Remplacer la règle vague "Valeurs aberrantes" par des seuils numériques stricts par catégorie d'anomalie
2. Ajouter une règle anti-zèle explicite avec fourchettes normales par opération
3. Garder le reste tel quel — il fonctionne

---

## Itération 2 — `prompt_v2` × `fixture_01_simple`

**Date** : 2026-04-30
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Prompt** : `prompt_v2.md`
**Fixture** : `fixture_01_simple.csv`

**Hypothèse à valider** : avec les seuils explicites + règle anti-zèle, `anomalies` doit être `[]` sur F1.

### Output produit par Claude

JSON structurellement identique à l'itération 1, mais **`anomalies: []`** (les 2 fausses positives sont éliminées).

### Évaluation : 15/15

Tous les critères passent désormais, dont **A3** (pas de fausses anomalies).

### Observations

- Les seuils numériques stricts ont fonctionné comme attendu
- La règle anti-zèle avec plages normales explicites a court-circuité le "common sense industriel" qui causait les faux positifs
- Pas de régression sur les autres critères — prompt_v2 ≥ prompt_v1 partout
- **Hypothèse validée** : on peut réduire le sur-zèle sans perte de qualité

### Question ouverte → F4

A-t-on tué la VRAIE détection en réduisant le sur-zèle ? À tester avec `fixture_04_anomalies.csv`.

---

## Itération 3 — `prompt_v2` × `fixture_04_anomalies` (à venir)

**Date** : (à compléter)
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Prompt** : `prompt_v2.md`
**Fixture** : `fixture_04_anomalies.csv`

**Hypothèse à valider** : Claude détecte les 6 vraies anomalies SANS générer de fausses positives sur les cas-pièges.

### Anomalies attendues (6)

| Ligne | Type attendu | Description |
|-------|--------------|-------------|
| OF-2026-101 | `duree_negative` | Durée -30 min |
| OF-2026-102 | `duree_zero` | Durée 0 sur tournage_finition |
| OF-2026-103 | `matiere_inconnue` | "ZorglubMetal" hors liste canonique |
| OF-2026-104 | `date_passee` | deadline 2025-01-01 (avant aujourd'hui) |
| OF-2026-105 | `duree_excessive_interne` | 2000 min > 1440 min sur fraisage_5axes |
| OF-2026-107 | `of_doublon_incoherent` | Même OF avec client/pièce/matière différents |

### Cas-pièges (NE doivent PAS être flaggés — 3)

| Ligne | Pourquoi pas anomalie |
|-------|----------------------|
| OF-2026-100 | OF parfaitement propre, control case |
| OF-2026-106 ébavurage 5 min | Plage normale 5-30 min |
| OF-2026-106 marquage 2 min | Plage normale 1-10 min |

### Comportements attendus sur OF-2026-103 (matière inconnue)

- `material_normalized` doit garder la valeur originale `ZorglubMetal` (pas inventer)
- L'OF doit quand même apparaître dans `orders`
- Une anomalie `matiere_inconnue` listée

### Output produit par Claude

```json
[à coller ici]
```

### Évaluation : __/15

(remplir après test)

### Critères spécifiques F4

- **Détection** : 6/6 vraies anomalies trouvées ?
- **Précision** : 0 fausses positives ? (les 3 cas-pièges)
- **Type d'anomalie correct** ? (chaque anomalie a le bon `type` selon la liste)

---

## Synthèse en cours

| Prompt | F1 | F2 | F3 | F4 | F5 | Notes |
|--------|----|----|----|----|----|-------|
| v1 | 14/15 | — | — | — | — | sur-zèle sur A3 |
| v2 | **15/15** | — | — | __/15 | — | seuils stricts, à tester sur F4 |

---

## Décisions prises

| Date | Décision | Raison |
|------|----------|--------|
| 2026-04-30 | Passer à prompt_v2 avec seuils stricts | Sur-zèle observé sur F1 — critique pour le trust layer |
| 2026-04-30 | F1 prompt_v2 = 15/15, sur-zèle éliminé | Confirme que le cadrage par seuils numériques fonctionne |
| 2026-04-30 | Ajout F4 pour tester la VRAIE détection | Vérifier qu'on n'a pas tué le filet de sécurité en réduisant le sur-zèle |
