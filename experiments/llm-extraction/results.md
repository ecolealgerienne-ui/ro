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

5 OF correctement mappées depuis colonnes NO_OF / REF_CLIENT / DESIG_PIECE / MATERIAU / OPERATION_DESC / POSTE_TRAVAIL / TPS_OP_MIN / DATE_LIV. 9 machines distinctes (incluant EXT-ANO-01). 13 opérations totales. Dates `15/05/2026` correctement converties en `2026-05-15`. 2 anomalies flaggées : `colonne_ambigue` sur EXT-ANO-01 et `operation_inconnue` sur "Tournage" sans qualificatif.

### Évaluation : 15/15

**Critères techniques (4/4)** : JSON valide, schéma respecté, aucune hallucination, valeurs préservées.

**Critères d'extraction (5/5)** : 5 OF, 9 machines uniques, 13 opérations, ordre OK, types corrects (incluant EXT-ANO-01 → autre).

**Critères de normalisation (3/3)** :
- Matières atypiques toutes parsées : "42 CrMo 4" → `acier_42CrMo4`, "Ti-6Al-4V" → `titane_TA6V`, "AL-2017" → `aluminium_2017`, "Aluminium 7075-T6" → `aluminium_7075`
- Opérations ERP-spécifiques : "CMM Controle" → `controle_dimensionnel`, "Fraisage 3 axes ebauche" → `fraisage_ebauche`, "Percage M6" → `percage`, "Marquage gravure" → `marquage`, "Lavage final" → `lavage`, "Anodisation externe" → `anodisation_externe`
- "Tournage" sans qualificatif : préservé tel quel + anomalie `operation_inconnue` (comportement strict, optimal)

**Critères d'anomalies (3/3)** :
- A1 N/A (pas d'anomalies évidentes type durée négative dans F3)
- A2 ✓ : Claude a détecté EXT-ANO-01 (machine hors préfixe → `colonne_ambigue`) et "Tournage" ambigu (`operation_inconnue`)
- A3 ✓ : pas de fausses anomalies (durées 4, 6, 8 min sur marquage/lavage/taraudage non flaggées — règle anti-zèle respectée)

### Performances remarquables

1. **Mapping colonnes ERP techniques 100 %** — NO_OF, REF_CLIENT, DESIG_PIECE, MATERIAU, OPERATION_DESC, POSTE_TRAVAIL, TPS_OP_MIN, DATE_LIV tous correctement interprétés. Colonnes inutiles PRIORITE et COMMENTAIRES ignorées proprement.

2. **Conversion date DD/MM/YYYY → YYYY-MM-DD** sans souci.

3. **Tolérance aux notations matières atypiques** : "42 CrMo 4" (espaces), "Ti-6Al-4V" (notation chimique), "AL-2017" (abréviation) tous parsés correctement vers leurs formes canoniques.

4. **Comportement strict sur "Tournage" sans qualificatif** : Claude n'a pas deviné — gardé tel quel + anomalie. Exactement le comportement attendu pour le trust layer.

5. **EXT-ANO-01 traité selon règle 6 du prompt** : `type_inferred: "autre"` + anomalie `colonne_ambigue`. Aucune dérive.

### Apprentissages

- Le prompt_v2 résiste à la diversité réelle des exports ERP
- Claude est **strict par défaut** : préfère flagger en cas d'ambiguïté plutôt que deviner — comportement souhaité
- Les listes de variations dans le schéma ne sont pas exhaustives mais Claude généralise correctement (ex: "AL-2017" non listé explicitement → mappé vers `aluminium_2017`)

---

## Itération 5 — `prompt_v3` + pre-flight × `fixture_04_anomalies` (à venir)

**Date** : (à compléter)
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Pipeline** : `preflight (Python) → prompt_v3 → Claude → JSON`
**Fixture** : `fixture_04_anomalies.csv`

**Hypothèse à valider** : avec le pre-flight en amont, on conserve le score 15/15 sur F4 tout en réduisant le prompt de ~30 % et en éliminant ~50 % de l'effort de détection d'anomalies côté LLM.

### Procédure

```bash
# Génère le prompt complet et l'écrit dans un fichier
cd ~/ro/poc-scheduler
uv run python scripts/llm_prompt_builder.py \
    ../experiments/llm-extraction/fixture_04_anomalies.csv \
    --today 2026-04-30 \
    --output /tmp/prompt_f4_v3.txt

# Le fichier est prêt à coller dans Claude.ai
```

### Anomalies attendues dans le rendu final

**Pré-détectées par pre-flight (Python, déjà dans `anomalies` quand le LLM démarre) — 3** :
- `duration_negative_or_zero` ligne 1 (raw -30)
- `duration_negative_or_zero` ligne 2 (raw 0)
- `date_in_past` ligne 4 (raw 2025-01-01)

**À détecter par LLM (sémantique) — 3** :
- `matiere_inconnue` (OF-103, ZorglubMetal)
- `duree_excessive_interne` (OF-105, 2000 min)
- `of_doublon_incoherent` (OF-107, valeurs incohérentes)

**Total dans `anomalies` final** : 6 (mêmes 6 que les itérations précédentes — comportement préservé).

### Cas-pièges (NE doivent PAS être flaggés par le LLM)

- OF-100 propre
- OF-106 ébavurage 5 min (déjà filtré par anti-zèle dans v2/v3)
- OF-106 marquage 2 min

### Output produit par Claude

8 OF correctement extraits (OF-107 fusionné comme dans l'itération 3, comportement identique). 6 machines uniques. 10 opérations totales. **6 anomalies dans `anomalies` final** :
- 3 issues du pre-flight (copiées telles quelles, mêmes `type`, `row_reference`, `description`)
- 3 sémantiques détectées par le LLM (matiere_inconnue ZorglubMetal, duree_excessive_interne 2000min, of_doublon_incoherent OF-107)

### Évaluation : 15/15

Tous les critères passent — y compris les nouveaux spécifiques à cette itération :

- **A1 (pre-flight présentes)** ✓ : 3/3 anomalies pre-flight présentes dans `anomalies`, format préservé
- **A2 (sémantiques détectées)** ✓ : 3/3 anomalies sémantiques trouvées, types corrects
- **Pas de redétection** ✓ : aucun doublon dans `anomalies` (pas de `duration_negative` redécouvert par le LLM en plus de l'injection)
- **A3 (pas de fausses anomalies)** ✓ : ébavurage 5min et marquage 2min non flaggés (anti-zèle préservé)

### Comportements remarquables

1. **Préservation littérale des anomalies pre-flight** : Claude a copié les 3 entrées exactement comme elles apparaissaient dans le bloc `{{PREFLIGHT_ANOMALIES}}`, sans paraphrase ni modification. Mêmes `description` au mot près ("Durée -30 ≤ 0").

2. **Choix OF-107 documenté** : Claude écrit "opérations regroupées sous les valeurs de la première occurrence, à arbitrer" — utile pour l'audit, et aligne avec le comportement spontané déjà observé en itération 3.

3. **Matière inconnue avec note explicite** : "valeur originale conservée dans material_normalized" — Claude explique son comportement, transparence appréciable.

4. **Aucune dérive** : pas une seule anomalie inventée, pas une seule modification silencieuse. Le contrat pre-flight ↔ LLM est respecté à la lettre.

### Apprentissages

- **Le pattern fonctionne** : on peut diviser le travail entre code déterministe (Niveau 1) et LLM (sémantique) sans perte de qualité.
- **Claude obéit aux instructions structurées** : la section "Pre-flight déjà effectué" est traitée comme un input à honorer, pas comme une suggestion.
- **Le format `{{VARIABLE}}` est ergonomique** pour les templates substitués par script.

### Comparaison F4 v2 vs F4 v3+preflight

| Métrique | v2 (itération 3) | v3 + preflight (itération 5) |
|----------|------------------|------------------------------|
| Score | 15/15 | 15/15 |
| Anomalies à détecter par LLM | 6 | 3 |
| Anomalies pré-injectées | 0 | 3 |
| Tokens prompt approx. | ~3000 | ~2000 (-33 %) |
| Risque de re-détection | N/A | 0 (testé) |

**Le pattern est validé.** À industrialiser pour la Phase 3.5 (agent extraction code).

---

# 🏁 Bilan global — expérimentation clôturée définitivement

| Test | Prompt | Score | Verdict |
|------|--------|-------|---------|
| F1 propre | v1 | 14/15 | sur-zèle détecté → v2 |
| **F1 propre** | **v2** | **15/15** | cas idéal validé |
| **F4 anomalies** | **v2** | **15/15** | filet de sécurité validé |
| **F3 ERP chaotique** | **v2** | **15/15** | robustesse format validée |

**45/45 critères validés sur 3 fixtures couvrant le spectre complet.**

## Conclusion

**Le risque "extraction LLM" est entièrement levé.** Claude Sonnet 4.6 sait extraire et normaliser des données d'atelier ERP avec un comportement strict et fiable, à condition d'être cadré par un prompt précis (seuils numériques explicites, règle anti-zèle, listes canoniques).

`prompt_v2.md` est le prompt de référence à reprendre dans la Phase 3.5 (agent extraction code).

## Tests non effectués (et pourquoi)

- **F2 (variations orthographiques pures)** : la robustesse aux variations a été démontrée en F3 (notations atypiques de matières et opérations). F2 aurait été redondant.
- **F5 (volume réaliste 50-80 lignes)** : test de scalabilité à faire en API, pas en chat — l'API a des limites de contexte plus claires et c'est là qu'on testera le volume.

## Apprentissages capitalisés pour l'API (Phase 3.5)

À spécifier dans le prompt système de l'agent :

1. **Passer la date courante explicitement** dans le prompt — ne pas dépendre de la connaissance implicite du modèle
2. **Spécifier le comportement OF doublons** : fusion intelligente (comme F4) ? duplication ? rejet ? À choisir explicitement
3. **Comportement opérations sans qualificatif** : flagger en `operation_inconnue` (comme Claude l'a fait spontanément) — comportement à confirmer
4. **Comportement machines hors préfixe** : `autre` + `colonne_ambigue` validé empiriquement
5. **Tolérance multi-locale** : Claude gère DD/MM/YYYY et YYYY-MM-DD sans instruction spécifique
6. **Tolérance variations matières** : "42 CrMo 4", "Ti-6Al-4V", "AL-2017" tous parsés — pas besoin d'enrichir la liste canonique du prompt

## Voir aussi

- `verdict.md` : synthèse stratégique pour le projet
- `prompt_v2.md` : prompt de référence à reprendre en Phase 3.5

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
| 2026-04-30 | F3 prompt_v2 = 15/15 | Robustesse format ERP réel validée — clôture de l'expérimentation |
| 2026-04-30 | Expérimentation clôturée — risque LLM extraction levé | 45/45 sur 3 fixtures couvrant le spectre. prompt_v2 référence pour Phase 3.5 |
| 2026-04-30 | Réouverture pour ajouter pre-flight + prompt_v3 | Application du pattern "code déterministe avant LLM". Module `src/preflight/` intégré, prompt allégé. À tester avec itération 5. |
| 2026-04-30 | F4 prompt_v3 + preflight = 15/15 | Pattern validé empiriquement. Pre-flight + LLM réussit la même qualité avec 33 % moins de prompt et 50 % moins d'effort de détection LLM. |
