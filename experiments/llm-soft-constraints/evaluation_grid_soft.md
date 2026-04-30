# Grille d'évaluation — soft constraints

À remplir après chaque itération de prompt.

## Note par phrase (5 critères × 15 phrases = 75 points)

Pour chaque phrase, 5 critères à évaluer (1 pt par critère validé) :

| Phrase | Cat. | Params | Weight | Rationale | Conf. | **/5** |
|--------|------|--------|--------|-----------|-------|--------|
| 1 — éviter M3 nuit | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 2 — privilégier FRAIS-01 | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 3 — regrouper alu 7075 | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 4 — OP05 pas rectif | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 5 — Safran avant vendredi | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 6 — pas fragmenter >20 | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 7 — max 3 setups FRAIS-5X | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 8 — contrôles le matin | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 9 — **jamais** tournage nuit | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 10 — regrouper même client | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 11 — OP12 formation (complex) | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 12 — fraisage par OP01/OP02 | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 13 — pas titane+alu (inédit) | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 14 — médical priorité absolue | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| 15 — **certifié EN 9100** (dure) | ☐ | ☐ | ☐ | ☐ | ☐ | /5 |
| **Total** | | | | | | **/75** |

## Détail des 5 critères

| # | Critère | Validation |
|---|---------|------------|
| C1 | **Catégorie correcte** | La phrase est rangée dans la bonne catégorie OU dans `unrecognized` si attendu |
| C2 | **Paramètres extraits** | Les paramètres requis par la catégorie sont présents et correctement valués (ex: machine_reference="M3" pas "machine M3 ou M3") |
| C3 | **Weight cohérent** | weight_hint dans la fourchette attendue (±0.2) selon le langage utilisé |
| C4 | **Rationale cohérent** | weight_rationale référence explicitement le langage de la phrase (« on évite », « jamais », etc.). Pour phrases « jamais »/« toujours » : mention de contrainte dure |
| C5 | **Confidence appropriée** | high si catégorie évidente et paramètres sans ambiguïté, low si interprétation forcée |

## Score global

| Score | Verdict |
|-------|---------|
| ≥ 60/75 (80 %) | ✅ Risque levé — on peut industrialiser |
| 45–59 (60-79 %) | ⚠ Prompt à raffiner (v2) |
| < 45 (60 %) | ❌ Revoir catalogue, prompt, ou approche |

## Cas pièges spéciaux (à observer particulièrement)

### Phrase 9 — « jamais tournage la nuit »
**Comportement attendu** :
- Catégorie `avoid_machine_during_period` (pas `unrecognized`)
- weight_hint ∈ [0.9, 1.0]
- weight_rationale **doit mentionner** que c'est probablement une contrainte dure
- C'est important : Claude doit reconnaître que « jamais » est catégoriel sans pour autant rejeter la phrase

### Phrase 11 — « OP12 formation cette semaine »
**Comportement attendu** :
- Catégorie complexe (indisponibilité temporaire d'un opérateur, hors catalogue)
- Soit `operator_avoidance` avec mention temporelle (mais notre schéma n'a pas de champ time-bounded → C2 partiellement validé)
- Soit `unrecognized` avec `suggestion` invitant à reformuler en « OP12 indisponible cette semaine » et déclarer comme calendrier d'indispo
- Test du **jugement** de Claude — pas de réponse universelle

### Phrase 13 — « pas titane et alu même machine même jour »
**Comportement attendu** :
- Catégorie inédite (conflit matières)
- Soit `unrecognized` avec suggestion
- Soit `other` avec extracted_objects
- Test : Claude **n'invente pas** une catégorie qui n'existe pas

### Phrase 15 — « certifié EN 9100 pour fraisage 5 axes »
**Comportement attendu** :
- C'est une **contrainte dure** déguisée (qualification opérateur formelle)
- Doit aller dans `unrecognized` avec `reason` : « contrainte dure, hors périmètre soft »
- C'est le test critique : Claude **distingue** soft vs dure

## Observations qualitatives à logger

- **Cohérence inter-phrases** : Claude est-il cohérent dans son interprétation du même mot (« éviter ») entre phrases ?
- **Inventions** : a-t-il créé une catégorie hors catalogue ?
- **Verbosité** : a-t-il tenu la consigne « JSON uniquement » ?
- **Robustesse aux négations** : la phrase 4 (« préfère ne pas faire ») est-elle bien interprétée comme avoidance et pas preference inversée ?
