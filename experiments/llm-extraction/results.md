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

**Date** : 2026-04-30
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Prompt** : `prompt_v2.md`
**Fixture** : `fixture_04_anomalies.csv`

**Hypothèse à valider** : Claude détecte les 6 vraies anomalies SANS générer de fausses positives sur les cas-pièges.

### Output produit par Claude

8 OF dans `orders` (dont OF-2026-107 fusionné à partir des 2 lignes), 6 machines détectées, 6 anomalies bien typées.

### Évaluation : 15/15

**Détection : 6/6**
- `duree_negative` (OF-101, raw -30) ✓
- `duree_zero` (OF-102, raw 0) ✓
- `matiere_inconnue` (OF-103, "ZorglubMetal" préservée) ✓
- `date_passee` (OF-104, 2025-01-01) ✓
- `duree_excessive_interne` (OF-105, 2000 min) ✓
- `of_doublon_incoherent` (OF-107, description détaillée des différences) ✓

**Précision : 3/3 contrôles non-flaggés**
- OF-100 propre → absent de `anomalies` ✓
- OF-106 ébavurage 5 min → non flaggé ✓
- OF-106 marquage 2 min → non flaggé ✓

**Comportements remarquables**
1. Préservation parfaite : durations -30, 0, 2000 gardées telles quelles dans `operations` (T4)
2. ZorglubMetal préservé en `material_normalized` (n'a pas inventé une forme canonique)
3. Connaissance implicite de la date du jour (Claude écrit "antérieure à la date du jour 30/04/2026")
4. Comportement non spécifié sur OF-107 : Claude a **fusionné** les 2 lignes en 1 entrée avec 2 ops, en prenant les valeurs de la première ligne. Choix intelligent mais à expliciter pour l'API

**Apprentissages pour l'API (futur)**
- Passer la date courante explicitement en paramètre (ne pas dépendre de la connaissance implicite du modèle)
- Spécifier le comportement sur OF doublons (fusion / duplication / rejet)

---

## Itération 4 — `prompt_v2` × `fixture_03_erp_chaotic` (à venir)

**Date** : (à compléter)
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Prompt** : `prompt_v2.md`
**Fixture** : `fixture_03_erp_chaotic.csv`

**Hypothèse à valider** : Claude résiste à la diversité de format ERP réel (colonnes techniques, dates DD/MM/YYYY, formulations métier ERP-spécifiques).

### Défis de la fixture F3

| Variation | Test |
|-----------|------|
| Colonnes techniques | NO_OF, REF_CLIENT, DESIG_PIECE, MATERIAU, OPERATION_DESC, POSTE_TRAVAIL, TPS_OP_MIN, DATE_LIV |
| Format date | DD/MM/YYYY (`15/05/2026`) au lieu de YYYY-MM-DD |
| Variations matières | "Aluminium 7075-T6", "42 CrMo 4", "Ti-6Al-4V", "AL-2017" |
| Phrasings opérations | "Tournage Ebauche CN", "CMM Controle", "Fraisage 3 axes ebauche", "Percage M6", "Taraudage M6", "Fraisage 5-axes", "Tournage" (sans qualificatif), "Rectification cyl.", "Marquage gravure", "Lavage final" |
| Colonnes inutiles | PRIORITE, COMMENTAIRES |
| Machine inconnue | EXT-ANO-01 (anodisation externe, pas de prefix mappé) |

### Comportements attendus

- **Mapping colonnes** : Claude doit comprendre NO_OF→order_id, REF_CLIENT→client, DESIG_PIECE→piece_name, etc.
- **Conversion date** : "15/05/2026" → "2026-05-15"
- **Normalisations** :
  - "Aluminium 7075-T6" → `aluminium_7075`
  - "42 CrMo 4" → `acier_42CrMo4`
  - "Ti-6Al-4V" → `titane_TA6V`
  - "AL-2017" → `aluminium_2017`
  - "Tournage Ebauche CN" → `tournage_ebauche`
  - "CMM Controle" → `controle_dimensionnel`
  - "Tournage" (sans qualificatif) → ambigu : `tournage_ebauche` ? `tournage_finition` ? À surveiller
  - "Percage M6", "Taraudage M6" → `percage`, `taraudage`
  - "Fraisage 5-axes" → `fraisage_5axes`
  - "Marquage gravure" → `marquage`
  - "Lavage final" → `lavage`
- **Machine ambiguë** : EXT-ANO-01 → `autre` + anomalie `colonne_ambigue` (selon règle 6 du prompt)

### Cas particulier "Tournage" sans qualificatif

Aucune des deux formes canoniques (`tournage_ebauche`, `tournage_finition`) n'est strictement applicable. Comportements possibles :
- Choix arbitraire (tournage_ebauche par défaut) → risqué
- Choix par contexte (la pièce a aussi de la rectif → probablement de la finition) → intelligent
- Anomalie `operation_inconnue` → strict

À voir ce que Claude fait — informatif sur sa façon de raisonner.

### Output produit par Claude

```json
[à coller ici]
```

### Évaluation : __/15

(à remplir)

### Critères spécifiques F3

- **Mapping colonnes ERP** : 8 colonnes mappées correctement ?
- **Conversion date** : tous les `deadline` au format ISO ?
- **Robustesse normalisation** : matières et opérations correctement identifiées malgré les variations ?
- **Gestion EXT-ANO-01** : flagué proprement ou silencieusement classé "autre" ?

---

## Synthèse en cours

| Prompt | F1 | F2 | F3 | F4 | F5 | Notes |
|--------|----|----|----|----|----|-------|
| v1 | 14/15 | — | — | — | — | sur-zèle sur A3 |
| v2 | **15/15** | — | __/15 | **15/15** | — | seuils stricts + anti-zèle. F4 anomalies réelles parfait, F3 robustesse format à tester |

---

## Décisions prises

| Date | Décision | Raison |
|------|----------|--------|
| 2026-04-30 | Passer à prompt_v2 avec seuils stricts | Sur-zèle observé sur F1 — critique pour le trust layer |
| 2026-04-30 | F1 prompt_v2 = 15/15, sur-zèle éliminé | Confirme que le cadrage par seuils numériques fonctionne |
| 2026-04-30 | Ajout F4 pour tester la VRAIE détection | Vérifier qu'on n'a pas tué le filet de sécurité en réduisant le sur-zèle |
| 2026-04-30 | F4 prompt_v2 = 15/15 (6/6 anomalies + 0 fausse positive) | Filet de sécurité intact ; agent extraction validé sur cas extrêmes |
| 2026-04-30 | Ajout F3 (format ERP chaotique) | Dernier test avant clôture — robustesse à la diversité réelle des exports ERP |
| 2026-04-30 | Note pour l'API : passer la date courante explicitement | Claude a la date implicitement, dangereux à long terme |
| 2026-04-30 | Note pour l'API : spécifier comportement sur OF doublons | Claude fusionne intelligemment, mais le choix doit être explicite |
