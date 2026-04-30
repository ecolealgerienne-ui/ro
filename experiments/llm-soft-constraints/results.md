# Journal d'expérimentations — soft constraints

> Une entrée par itération de prompt. Logger les observations qualitatives,
> pas seulement le score.

---

## Itération 1 — `prompt_v1_soft` × `fixture_phrases_v1`

**Date** : 2026-04-30
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Prompt** : `prompt_v1_soft.md`
**Fixture** : `fixture_phrases_v1.md`

### Output produit par Claude

12 entrées dans `soft_constraints` (les 12 phrases mappées) + 3 entrées dans `unrecognized` (phrases 11, 13, 15). Toutes les classifications correctes, toutes les anomalies traitées avec jugement.

### Évaluation : 75/75 ✓

| Phrase | C1 Cat. | C2 Params | C3 Weight | C4 Rationale | C5 Conf. | /5 |
|--------|--------|-----------|-----------|--------------|----------|-----|
| 1 — éviter M3 nuit | ✓ | ✓ | ✓ (0.4) | ✓ | ✓ medium | 5 |
| 2 — privilégier FRAIS-01 | ✓ | ✓ | ✓ (0.4) | ✓ | ✓ high | 5 |
| 3 — regrouper alu 7075 | ✓ | ✓ | ✓ (0.2) | ✓ | ✓ high | 5 |
| 4 — OP05 pas rectif | ✓ | ✓ | ✓ (0.4) | ✓ | ✓ high | 5 |
| 5 — Safran avant vendredi | ✓ | ✓ | ✓ (0.7) | ✓ | ✓ high | 5 |
| 6 — pas fragmenter >20 | ✓ | ✓ | ✓ (0.5) | ✓ | ✓ high | 5 |
| 7 — max 3 setups FRAIS-5X | ✓ | ✓ | ✓ (0.7) | ✓ | ✓ medium | 5 |
| 8 — contrôles le matin | ✓ | ✓ | ✓ (0.3) | ✓ | ✓ high | 5 |
| **9 — jamais tournage nuit** | ✓ | ✓ | ✓ (0.95) | ✓ contrainte dure flaguée | ✓ medium | **5** |
| 10 — regrouper même client | ✓ | ✓ | ✓ (0.2) | ✓ | ✓ high | 5 |
| **11 — OP12 formation** | ✓ unrecognized + suggestion calendrier | N/A | N/A | N/A | N/A | **5** |
| 12 — fraisage par OP01/OP02 | ✓ | ✓ | ✓ (0.4) | ✓ | ✓ high | 5 |
| **13 — pas titane+alu** | ✓ unrecognized + suggestion catégorie | N/A | N/A | N/A | N/A | **5** |
| 14 — médical priorité abs. | ✓ | ✓ | ✓ (0.95) | ✓ confirmation demandée | ✓ medium | 5 |
| **15 — certifié EN 9100** | ✓ unrecognized + pattern qualified_operator | N/A | N/A | N/A | N/A | **5** |
| **Total** | | | | | | **75/75** |

### Observations qualitatives

**Ce qui a fonctionné**
- Sortie JSON pur, pas de prose autour
- Calibration des poids très précise — toutes les valeurs dans la fourchette ±0.2 attendue
- Confidence honnête (medium quand un paramètre est interprété, high sinon)
- Préservation des références d'origine (M3, OP05, FRAIS-01) sans normalisation prématurée
- Distinction soft vs dure maîtrisée (phrase 9 flaggée vs phrase 15 rejetée)

**Comportements remarquables**

1. **Anti-zèle nuancé sur "jamais" (phrase 9)** : Claude n'a ni rejeté la phrase ni l'a incluse silencieusement avec un poids modéré. Il a choisi la 3e voie : *"je l'inclus avec weight_hint=0.95 ET je flag dans le rationale que ça ressemble à une contrainte dure, en attente d'arbitrage"*. C'est exactement la posture du trust layer.

2. **Suggestion auto de nouvelle catégorie (phrase 13)** : sans qu'on lui demande, Claude propose une catégorie qui pourrait être ajoutée au catalogue : `avoid_material_cooccurrence_on_machine`. Il enrichit le système au lieu de le contourner.

3. **Lien architectural automatique (phrase 15)** : la suggestion *"Déclarer formellement en contrainte dure via le pattern `qualified_operator_constraint`"* fait le lien avec un pattern qui existe DÉJÀ dans notre code POC (`src/core/pattern.py::QualifiedOperatorPattern`). Claude raisonne avec la cohérence architecturale.

4. **Contextualisation médicale (phrase 14)** : interprète "médical" comme un secteur potentiellement plutôt qu'un nom de client précis, et signale la nécessité de confirmer avec le chef d'atelier. Pas d'inférence forcée.

**Cas pièges spéciaux**

- Phrase 9 (« jamais ») : ✓ traité comme prévu, weight 0.95 + rationale signale contrainte dure
- Phrase 11 (formation temporaire) : ✓ unrecognized + suggestion d'utiliser le calendrier opérateur
- Phrase 13 (matières clash) : ✓ unrecognized + suggestion de nouvelle catégorie
- Phrase 15 (contrainte dure) : ✓ unrecognized + pointe vers pattern existant

**Cohérence inter-phrases** : excellente. Le mot "éviter" produit weight ~0.4-0.5 dans toutes les phrases, "si possible" → 0.2, "doivent" → 0.7. Pas de variation arbitraire.

**Verbosité** : zéro. Sortie JSON pur, "uniquement le JSON" respecté.

### Pas besoin de prompt_v2

Le score 75/75 dès l'itération 1 indique que :
- Le catalogue de 11 catégories est suffisamment couvrant
- Le prompt strict avec règles d'anti-invention fonctionne
- Le pattern "OK + flag pour les cas limites" est correctement compris

Aucun raffinement nécessaire. **Le risque "NL → soft constraints" est levé empiriquement.**

---

## Synthèse en cours

| Prompt | Score | Notes |
|--------|-------|-------|
| v1 | **75/75** | parfait dès le 1er essai — aucun raffinement nécessaire |

---

## Décisions prises

| Date | Décision | Raison |
|------|----------|--------|
| 2026-04-30 | **Risque NL → soft constraints levé** | 75/75 sur 15 phrases incluant 4 cas pièges critiques. Claude maîtrise la classification + paramètres + calibration de poids + distinction soft/dure |
| 2026-04-30 | Catégorie suggérée par Claude à intégrer | `avoid_material_cooccurrence_on_machine` (depuis phrase 13) — utile pour l'industrie où les contaminations matières sont un vrai sujet |
| 2026-04-30 | Lien direct à `QualifiedOperatorPattern` confirmé | Le LLM identifie spontanément quelle phrase relève d'un pattern dur existant — réduit le besoin de routage explicite côté code |
