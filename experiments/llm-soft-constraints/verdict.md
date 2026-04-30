# Verdict — Expérimentation NL → soft constraints

> Synthèse stratégique. À transmettre / consulter sans relire les détails.

**Date de clôture** : 2026-04-30
**Statut** : ✅ Risque levé — traduction NL → règles formelles validée

---

## Question initiale

> Claude Sonnet sait-il traduire les préférences exprimées en langage naturel
> par un chef d'atelier en règles formelles utilisables par le solveur (catégorie
> + paramètres + poids), avec la discipline de distinguer soft constraint vs
> contrainte dure et de ne pas inventer de catégorie hors catalogue ?

## Réponse empirique : **OUI, dès l'itération 1**

**75/75 critères validés** sur 15 phrases couvrant le spectre — incluant 4 cas pièges critiques.

| Phrase | Type de cas | Comportement attendu | Comportement observé |
|--------|-------------|----------------------|----------------------|
| 1-8, 10, 12, 14 | Cas évidents | Catégorie + params + poids correct | ✓ tous validés |
| 9 — « **jamais** tournage nuit » | Soft « catégorielle » | Inclure + flag contrainte dure | ✓ weight 0.95 + rationale explicite |
| 11 — « OP12 formation **cette semaine** » | Indispo temporaire | unrecognized + suggestion calendrier | ✓ exact |
| 13 — « pas titane+alu **même machine** » | Catégorie inédite | unrecognized + suggestion nouvelle catégorie | ✓ Claude propose `avoid_material_cooccurrence_on_machine` |
| 15 — « **certifié EN 9100** » | Contrainte dure déguisée | unrecognized + pointer vers pattern dur | ✓ Claude pointe vers `qualified_operator_constraint` (pattern qui existe dans notre code !) |

## Méthode

1 itération dans Claude.ai (web, no-code), prompt unique. Coût : 0 €. Durée : ~10 minutes.

## Pourquoi ça compte stratégiquement

D'après `specs-fonctionnelles-v3.md` §2.3, la **3ème catégorie de contraintes** (soft constraints en NL) est ce qui distingue le produit d'un APS classique. La spec dit :

> *Le LLM traduit ces phrases en pondérations qui rentrent dans la fonction objectif sous forme de pénalités.*

**On vient de prouver que c'est faisable** avec un catalogue de catégories précis et un prompt strict. C'est l'**interface conversationnelle** entre chef d'atelier et solveur qui est validée, pas juste l'extraction.

## Ce qu'on a découvert

### Forces (confirmées)

1. **Maîtrise du catalogue fini** : Claude n'invente jamais une catégorie, même quand la phrase semble "presque" mapper. Il préfère `unrecognized` avec suggestion.

2. **Calibration des poids cohérente** : « si possible » → 0.2, « on évite » → 0.4, « il faut » → 0.7, « jamais » → 0.95. Mappage stable inter-phrases.

3. **3e voie sur les cas limites** : pour « jamais », Claude n'a ni rejeté ni inclus silencieusement. Il a inclus AVEC un flag explicite "probablement contrainte dure". C'est la posture qu'on veut pour le trust layer.

4. **Suggestions architecturalement cohérentes** : la phrase 15 (« certifié EN 9100 ») a été pointée vers `qualified_operator_constraint` — le pattern existant DANS NOTRE CODE. Claude raisonne avec la structure du système, pas seulement avec sa connaissance générale.

5. **Préservation des références** : OP05, FRAIS-01, M3, "aluminium 7075" — gardés tels quels. Pas de normalisation prématurée (qui sera faite ailleurs).

6. **Auto-enrichissement du catalogue** : phrase 13 fait suggérer une nouvelle catégorie utile à ajouter (`avoid_material_cooccurrence_on_machine`). Le système peut grandir grâce à l'usage.

### Limites observées

1. **Phrase 9 — référence machine vs opération** : la phrase « jamais tournage la nuit » a été classée en `avoid_machine_during_period` avec `machine_reference: null`, alors que sémantiquement c'est plutôt « avoid_operation_type_during_period ». Cas glissant — pourrait être amélioré en ajoutant cette catégorie au catalogue.

2. **Confidence honnête mais perfectible** : medium peut signifier des choses différentes (paramètre par défaut interprété vs référence ambiguë). Pas critique mais à raffiner pour le post-flight.

## Implications pour la roadmap

### Court terme

- **Phase 1.6 (soft constraints en pénalités) est de-risquée** sur la couche LLM. Reste à coder le pont entre catégorie LLM → pattern CP-SAT (par catégorie : `avoid_machine_during_period` → fonction qui ajoute des intervals fixes pour les heures de nuit + pénalité dans l'objectif).

- **Le catalogue v1 est viable**. À enrichir progressivement avec les catégories suggérées par Claude (`avoid_material_cooccurrence_on_machine` notamment).

### Moyen terme

- **L'interface conversationnelle est faisable**. Un chef d'atelier pourra dire « on évite la machine M3 la nuit » et le système la traduira en pondération objectif sans intervention manuelle.

- **Le pattern preflight + catalogue + LLM** se généralise : on peut appliquer la même architecture à d'autres cas LLM du produit (modifications conversationnelles Phase 3.8, explications INFEASIBLE Phase 1.8).

## Référentiels pour Phase 1.6 et 3.x

- `prompt_v1_soft.md` — prompt de référence (validé tel quel sur 15 phrases)
- `target_schema_soft.md` — catalogue 11 catégories + guidance weights
- `evaluation_grid_soft.md` — 75 critères pour évaluer toute itération future

## Ce que ça ne dit pas

Cette expérimentation valide :
- ✓ Classification dans un catalogue fini
- ✓ Extraction de paramètres simples
- ✓ Calibration de poids
- ✓ Distinction soft / dure
- ✓ Reconnaissance d'échec (unrecognized)

Elle ne valide pas (à tester ultérieurement) :
- ✗ Cohérence sur **plusieurs centaines** de phrases (test à scale)
- ✗ Performance sur **dialecte régional** ou jargon atelier très spécifique
- ✗ Modifications conversationnelles ("on annule la phrase précédente, on remplace par...")
- ✗ Cohérence quand le contexte de l'atelier réel est passé (pas qu'un catalogue abstrait)
- ✗ Coût en tokens à l'échelle (à mesurer en API)

Mais ces points ne bloquent pas — ils relèvent de l'industrialisation Phase 1.6 / 3.x.

---

## Conclusion globale (les 2 expérimentations LLM)

| Risque tech LLM | Score | Statut |
|-----------------|-------|--------|
| Extraction CSV ERP → JSON | 75/75 (3 fixtures + preflight) | ✅ |
| NL → soft constraints | 75/75 (15 phrases) | ✅ |

**Tous les risques tech LLM majeurs identifiés sont levés empiriquement.**

Le projet est désormais **tech-de-risqué** sur tous les fronts critiques :
- Solveur OR-Tools (Phase 0) ✓
- Pipeline E2E generator → solver (Phase 0.7) ✓
- Architecture pattern (Phase 1.1) ✓
- Pre-flight + LLM extraction (expérimentation 1) ✓
- LLM traduction NL (expérimentation 2) ✓

**Les vrais risques restants sont de nature produit** :
- PMF / wedge / segment cible
- Acceptation par les chefs d'atelier en réel
- Mécanisme de vente / cycle d'adoption
- Concurrence / positionnement

Aucun ne se résout en codant.

---

*La discipline du prompt + le catalogue fini + la préservation des références constituent un pattern industrialisable pour tous les usages LLM du projet.*
