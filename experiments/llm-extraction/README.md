# Expérimentation — LLM extraction Excel/CSV → JSON workshop

> Hors POC code, hors API. Test no-code de la capacité de Claude à extraire des
> données d'atelier proprement à partir de fichiers CSV/Excel "ERP-style".

## Objectif

Valider une question critique du projet **avant de coder l'agent d'extraction** :
**Claude Sonnet sait-il extraire les données d'un atelier de mécanique de
précision à partir d'un fichier ERP, avec ses imperfections ?**

Si oui, on enferme le prompt en API + agent (Phase 3.5).
Si non, il faut repenser l'approche (templates ERP-spécifiques, OCR, etc.).

## Méthode

**Manuelle, dans Claude.ai (web).** Pas d'API, pas de code.

1. Ouvrir un nouveau chat sur claude.ai
2. Copier-coller le contenu de `prompt_v1.md` (en remplaçant `[SCHEMA]` par le contenu de `target_schema.md` et `[CSV]` par celui de la fixture)
3. Récupérer le JSON produit par Claude
4. Évaluer avec `evaluation_grid.md`
5. Logger l'itération dans `results.md`
6. Si un critère échoue, raffiner le prompt et créer `prompt_v2.md`, etc.
7. Une fois `prompt_vN.md` stable sur F1, passer à F2, F3, ...

## Critères de validation

Pour passer à la phase code (Phase 3.5) :
- **F1-F3** : ≥ 90 % de critères validés (cas propre + variations matière + format ERP)
- **F4** : anomalies effectivement flaggées (durée négative, etc.)
- **F5** : aucune hallucination sur volume réaliste (50-80 lignes)

Si F1 échoue → on a un problème fondamental, repenser.
Si F1-F3 passent mais F4 fait passer les anomalies silencieusement → critique pour le trust layer, à corriger absolument.

## Fichiers

| Fichier | Rôle |
|---------|------|
| `prompt_v1.md` | Prompt initial (à coller dans Claude) |
| `target_schema.md` | Schéma JSON cible (à inclure dans le prompt) |
| `fixture_01_simple.csv` | F1 — cas propre, 5 OF, 5 machines |
| `fixture_02_*.csv` | F2 et suivants — créés au fur et à mesure |
| `evaluation_grid.md` | Checklist d'évaluation par fixture |
| `results.md` | Journal d'itérations (à remplir) |

## Pourquoi pas l'API directement ?

Travailler dans le chat web :
- **Itération 10× plus rapide** sur le prompt
- **Zero engineering cost** (pas d'API key, pas de boucle de tests)
- **Découverte des biais et forces** du modèle avant de l'enfermer dans du code
- Le prompt qui marche en chat marchera en API (Sonnet est le même modèle)

Ce n'est qu'une fois que le prompt produit des résultats cohérents qu'on l'enferme dans une fonction agent en API.
