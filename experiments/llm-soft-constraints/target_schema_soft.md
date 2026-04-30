# Schéma JSON cible — soft constraints

Structure attendue de la sortie de Claude.

## Format

```json
{
  "soft_constraints": [
    {
      "natural_language": "On évite de faire tourner la machine M3 la nuit",
      "category": "avoid_machine_during_period",
      "parameters": {
        "machine_reference": "M3",
        "period_type": "night",
        "period_start_hour": 20,
        "period_end_hour": 6
      },
      "weight_hint": 0.5,
      "weight_rationale": "« on évite » = préférence modérée, pas une interdiction absolue",
      "confidence": "high"
    }
  ],
  "unrecognized": [
    {
      "natural_language": "...",
      "reason": "Ne mappe à aucune catégorie connue — paramètres ambigus",
      "suggestion": "Reformuler avec un objet concret (machine, matière, opérateur)"
    }
  ]
}
```

## Champs `soft_constraints[*]`

| Champ | Type | Description |
|-------|------|-------------|
| `natural_language` | string | Phrase originale, copiée telle quelle |
| `category` | enum (voir liste) | Catégorie canonique |
| `parameters` | object | Dépend de la catégorie (voir détail par catégorie) |
| `weight_hint` | float [0.1, 1.0] | Force de la préférence — voir guidance |
| `weight_rationale` | string | Explication courte du poids choisi (basée sur le langage) |
| `confidence` | enum: `high`, `medium`, `low` | Confiance de Claude dans son interprétation |

## Catégories canoniques

### `avoid_machine_during_period`
*"Éviter de faire tourner la machine X la nuit / le weekend / pendant la pause"*

Paramètres :
- `machine_reference` (string) : nom ou ID de la machine
- `period_type` (string) : `night` | `weekend` | `lunch_break` | `custom`
- `period_start_hour` (int 0-23, optionnel)
- `period_end_hour` (int 0-23, optionnel)

### `prefer_grouping_by_material`
*"Regrouper si possible les pièces de la même matière X"*

Paramètres :
- `material_reference` (string, optionnel) : si une matière spécifique est mentionnée ; sinon vide = toutes matières

### `prefer_grouping_by_client`
*"Si possible, regrouper les commandes du même client le même jour"*

Paramètres :
- `client_reference` (string, optionnel)
- `time_window` (string, optionnel) : `same_day` | `same_week`

### `operator_avoidance`
*"L'opérateur OP05 préfère ne pas faire de rectification"*

Paramètres :
- `operator_reference` (string)
- `operation_type_avoided` (string)

### `operator_preference`
*"On préfère que les opérations de fraisage soient faites par OP01 ou OP02"*

Paramètres :
- `operation_type_preferred` (string)
- `preferred_operator_references` (list of strings)

### `prefer_machine_over_other`
*"Privilégier la machine FRAIS-01 sur FRAIS-02 quand les deux sont libres"*

Paramètres :
- `preferred_machine_reference` (string)
- `over_machine_reference` (string)

### `client_priority`
*"Les OF Safran doivent finir avant le vendredi"* / *"Pièces médicales en priorité absolue"*

Paramètres :
- `client_reference` (string)
- `priority_level` (enum: `low` / `medium` / `high` / `critical`)
- `deadline_hint` (string, optionnel) : phrase brute si une deadline est mentionnée (ne pas convertir en date)

### `avoid_series_fragmentation`
*"Éviter de fragmenter les séries de plus de N pièces"*

Paramètres :
- `min_series_size` (int) : nombre de pièces au-delà duquel ne pas fragmenter

### `limit_setups_per_day_on_machine`
*"Maximum N changements de production par jour sur la machine X"*

Paramètres :
- `machine_reference` (string)
- `max_setups_per_day` (int)

### `prefer_operation_in_shift`
*"Les contrôles dimensionnels de préférence le matin"*

Paramètres :
- `operation_type` (string)
- `preferred_shift` (enum: `morning` / `afternoon` / `night`)

### `other`
*Pour les phrases qui ne mappent à aucune catégorie ci-dessus mais semblent quand même être une soft constraint identifiable*

Paramètres :
- `description_normalisee` (string) : reformulation neutre par Claude
- `extracted_objects` (list of strings) : entités identifiées (machines, matières, etc.)

## Guidance pour `weight_hint`

| Plage | Sémantique | Exemples linguistiques |
|-------|-----------|------------------------|
| 0.1–0.2 | Préférence légère | « si possible », « idéalement », « préférablement » |
| 0.3–0.5 | Préférence modérée | « on évite », « on préfère », « plutôt que » |
| 0.6–0.8 | Préférence forte | « important de », « il faut éviter », « éviter absolument » |
| 0.9–1.0 | Quasi-obligatoire | « jamais », « toujours », « sous aucun prétexte » |

⚠️ Si une phrase utilise une formulation **catégorielle** (« jamais », « toujours »), **signaler dans `weight_rationale`** que c'est probablement une **contrainte dure** (à modéliser hors soft constraints) et utiliser quand même weight_hint = 0.95-1.0.

## Champ `unrecognized[*]`

Pour les phrases qui ne peuvent **pas** être interprétées de façon fiable :

| Champ | Type | Description |
|-------|------|-------------|
| `natural_language` | string | Phrase originale |
| `reason` | string | Pourquoi non interprétable |
| `suggestion` | string | Reformulation suggérée pour être interprétable |

**Règle d'or** : préférer `unrecognized` à une mauvaise classification. **Ne jamais inventer** une catégorie.
