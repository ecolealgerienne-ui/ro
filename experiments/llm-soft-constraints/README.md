# Expérimentation — LLM traduction NL → soft constraints

> Test no-code : Claude Sonnet sait-il traduire des préférences exprimées en
> langage naturel par un chef d'atelier en règles formelles utilisables par le
> solveur CP-SAT ?

## Contexte

D'après `specs-fonctionnelles-v3.md` §2.3, la **3ème catégorie de contraintes** du produit (la nouveauté V3) est la couche soft constraints qui capte les préférences exprimées en langage naturel :

- *"On préfère éviter de faire tourner la machine X la nuit"*
- *"Cet opérateur peut dépanner mais on évite"*
- *"Regrouper si possible les pièces de la même matière"*

Le produit doit traduire ces phrases en pondérations dans la fonction objectif du solveur, sans toucher à la modélisation dure. **C'est le rôle du LLM** d'après la spec.

## Question à valider

Claude peut-il, à partir d'une phrase libre du chef d'atelier :
1. Identifier la **catégorie** de la contrainte (parmi un catalogue fini)
2. Extraire les **paramètres** concrets (machine, matière, opérateur, etc.)
3. Estimer un **poids** cohérent (préférence légère / forte / quasi-impérative)
4. **Reconnaître l'échec** si la phrase ne mappe à aucune catégorie connue (ne pas inventer)

## Méthode

Identique à `experiments/llm-extraction/` :
1. Coller `prompt_v1_soft.md` dans Claude.ai (web, nouveau chat)
2. Remplacer `{{SCHEMA}}` par `target_schema_soft.md`
3. Remplacer `{{PHRASES}}` par les phrases de la fixture
4. Évaluer la sortie avec `evaluation_grid_soft.md`
5. Logger dans `results.md`
6. Itérer le prompt si nécessaire

## Critère de succès

Pour considérer le risque levé :
- ≥ 80 % des phrases correctement catégorisées
- ≥ 80 % des paramètres correctement extraits
- ≥ 80 % des poids dans la fourchette attendue (±0.2)
- Aucune **invention** : phrases ambiguës doivent aller dans `unrecognized`, pas dans une catégorie au hasard

## Pourquoi c'est important

Si Claude réussit ce test, on a démontré que l'**interface conversationnelle entre chef d'atelier et solveur** est viable. C'est ce qui distingue le produit d'un APS classique :
- **APS classique** : le chef d'atelier doit apprendre à formaliser ses préférences
- **Notre produit** : il les exprime naturellement, le LLM les structure

## Si Claude échoue

Si < 60 % de réussite :
- On contraint plus le format (catégories plus précises)
- On enrichit le prompt avec des exemples (few-shot)
- En dernier recours : on impose une UI semi-structurée (dropdown catégorie + paramètres) et le LLM ne sert qu'à l'extraction des params

## Fichiers

| Fichier | Rôle |
|---------|------|
| `prompt_v1_soft.md` | Prompt initial à coller dans Claude |
| `target_schema_soft.md` | Schéma JSON cible avec catégories canoniques |
| `fixture_phrases_v1.md` | Set de phrases de test (12-15 cas) |
| `evaluation_grid_soft.md` | Grille d'évaluation par phrase |
| `results.md` | Journal des itérations |
