# Agents trial — workflow no-code de validation

> Permet de tester les 5 agents Phase 3 **sans clé API**, en passant par
> [claude.ai](https://claude.ai/) gratuit (copy-paste manuel).

## Pré-requis

- Compte claude.ai (free ou pro)
- Repo cloné, `cd poc-scheduler && uv sync` OK

## Workflow type (3 étapes)

### 1. Générer le prompt

```bash
cd poc-scheduler

uv run python scripts/agent_io.py prompt soft-constraints \
    --input ../experiments/agents-trial/soft_constraints_input.json \
    --output /tmp/prompt.txt
```

Affiche un résumé sur stderr (taille en chars + estimation tokens) et écrit
le prompt complet dans `/tmp/prompt.txt`.

### 2. Coller dans claude.ai

```bash
# Linux WSL
cat /tmp/prompt.txt | xclip -sel clip

# macOS
cat /tmp/prompt.txt | pbcopy
```

Puis Ctrl+V dans une nouvelle conversation claude.ai. Sauvegarder la
**réponse complète** de Claude dans `/tmp/response.txt` (peu importe le
format — fence ```` ```json ```` ou JSON brut, le validateur extrait robustement).

### 3. Valider

```bash
uv run python scripts/agent_io.py validate soft-constraints \
    --response /tmp/response.txt
```

Sortie :
- `✓ Reponse valide` → le JSON respecte le schéma Pydantic, l'agent peut
  consommer cette réponse en production
- `✗ Pas de JSON parsable` → la réponse Claude n'a pas pu être extraite
- `✗ Reponse non conforme au schema` → JSON valide mais champs manquants /
  types incorrects / valeurs hors enum / validators métier en échec

## Agents disponibles

| Nom CLI | Agent Python | Input attendu | Validé empiriquement ? |
|---------|--------------|---------------|------------------------|
| `questionnaire` | `QuestionnaireAgent` (3.4) | dict de réponses du questionnaire | ❌ — à valider sur 10 cas |
| `extraction-csv` | `CSVExtractionAgent` (3.5) | chemin CSV (preflight auto) | ✅ 45/45 (Phase 2) |
| `soft-constraints` | `SoftConstraintsAgent` (3.6) | liste de phrases NL | ✅ 75/75 (Phase 2) |
| `explanation` | `ExplanationAgent` (3.7) | `kind` + `context` | ❌ — à valider sur 30 cas |
| `edit` | `ConversationalEditAgent` (3.8) | `user_request` + `instance_summary` | ❌ — à valider sur 10 cas |

## Fixtures de démarrage

Ce dossier contient un input de démonstration par agent :

- `questionnaire_input.json` — questionnaire onboarding type PME méca
- `extraction_csv_input.json` — pointe vers `fixture_04_anomalies.csv`
- `soft_constraints_input.json` — 10 phrases méca variées
- `explanation_placement_input.json` — placement OF Safran sur TOUR-01
- `explanation_infeasibility_input.json` — saturation FRAIS-02 + MIS summary
- `conversational_edit_input.json` — « priorité OF Safran + bascule TOUR-02 »

Adapte / clone selon les cas que tu veux faire tourner.

## Validation de masse (quand on aura le temps)

Pour un agent donné, tester N inputs différents et tracer les résultats :

```bash
mkdir -p /tmp/trial-soft-constraints
for i in 1 2 3; do
    uv run python scripts/agent_io.py prompt soft-constraints \
        --input fixtures_$i.json --output /tmp/trial-soft-constraints/prompt_$i.txt
    # → coller chaque prompt manuellement, sauver la réponse
    uv run python scripts/agent_io.py validate soft-constraints \
        --response /tmp/trial-soft-constraints/response_$i.txt
done
```

## Pourquoi pas d'appel API direct ?

Coût + temps d'itération. Tant qu'on n'a pas de design partner pilote, le
workflow no-code via claude.ai gratuit est suffisant pour itérer les
prompts.

Quand on aura besoin d'automatiser : ajouter `ANTHROPIC_API_KEY` à
l'environnement, instancier `ClaudeAPIProvider` au lieu de `FakeLLMProvider`
dans le code applicatif. L'abstraction `LLMProvider` ne change pas.
