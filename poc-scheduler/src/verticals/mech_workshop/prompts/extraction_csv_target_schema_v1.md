# Schéma JSON cible

Forme attendue de la sortie de Claude. À inclure dans le prompt comme référence.

## Structure

```json
{
  "machines": [
    {
      "name": "TOUR-01",
      "type_inferred": "tour"
    }
  ],
  "orders": [
    {
      "order_id": "OF-2026-001",
      "client": "Safran",
      "piece_name": "Bague_pivot",
      "material_normalized": "aluminium_7075",
      "deadline": "2026-05-15",
      "operations": [
        {
          "sequence_idx": 0,
          "operation_type": "tournage_ebauche",
          "machine": "TOUR-01",
          "duration_min": 45
        }
      ]
    }
  ],
  "anomalies": [
    {
      "type": "duree_negative",
      "row_reference": "OF-2026-007 ligne 15",
      "raw_value": "-30",
      "description": "Durée négative interdite, à confirmer ou corriger"
    }
  ]
}
```

## Spécifications par champ

### `machines`
Liste des machines uniques rencontrées dans le CSV.

| Champ | Type | Description |
|-------|------|-------------|
| `name` | string | Identifiant tel qu'il apparaît dans le CSV (ex: "TOUR-01") |
| `type_inferred` | string | Type métier déduit du nom : `tour`, `fraiseuse`, `centre_usinage`, `rectifieuse`, `perceuse`, `machine_controle`, `autre` |

### `orders`
Une entrée par OF (ordre de fabrication). Toutes les lignes du CSV avec le même `OF` sont regroupées.

| Champ | Type | Description |
|-------|------|-------------|
| `order_id` | string | Identifiant tel qu'il apparaît dans le CSV |
| `client` | string | Nom du client tel qu'il apparaît |
| `piece_name` | string | Nom de la pièce |
| `material_normalized` | string | Forme canonique snake_case de la matière (voir liste ci-dessous) |
| `deadline` | string ISO 8601 (`YYYY-MM-DD`) | Date de livraison |
| `operations` | list | Gamme opératoire dans l'ordre du CSV |

### `operations`
Une entrée par ligne du CSV pour cet OF.

| Champ | Type | Description |
|-------|------|-------------|
| `sequence_idx` | int (0-indexé) | Position dans la gamme |
| `operation_type` | string | Forme canonique (voir liste ci-dessous) |
| `machine` | string | Nom de la machine (doit exister dans `machines`) |
| `duration_min` | int | Durée en minutes |

### `anomalies`
Liste des problèmes détectés. **Vide si tout est propre.** Ne JAMAIS corriger silencieusement — toujours signaler ici.

| Champ | Type | Description |
|-------|------|-------------|
| `type` | string | Catégorie : `duree_negative`, `duree_zero_sur_op_cn`, `matiere_inconnue`, `machine_absente`, `date_invalide`, `colonne_ambigue`, `valeur_aberrante`, `autre` |
| `row_reference` | string | Identifiant de la ligne concernée |
| `raw_value` | string | Valeur problématique trouvée |
| `description` | string | Explication courte en français |

## Listes canoniques

### Matières
| Forme normalisée | Variantes acceptées |
|------------------|---------------------|
| `aluminium_2017` | "Alu 2017", "AL-2017", "Aluminium 2017" |
| `aluminium_7075` | "Alu 7075", "AL-7075", "Aluminium 7075", "7075-T6", "Aluminium 7075-T6" |
| `acier_inox_316L` | "Inox 316L", "Inox 316", "316L", "Acier inox 316L" |
| `acier_inox_304` | "Inox 304", "304", "Acier inox 304" |
| `acier_42CrMo4` | "42CrMo4", "Acier 42CrMo4", "42 CrMo 4" |
| `titane_TA6V` | "Titane TA6V", "TA6V", "Ti-6Al-4V", "Ti6Al4V" |
| `laiton_CuZn40` | "Laiton CuZn40", "CuZn40", "Laiton" |
| `bronze` | "Bronze" |
| `plastique_technique` | "Plastique", "PEEK", "POM", "PA66" |

Si la matière ne correspond à aucune des formes ci-dessus → garder la forme originale **et** créer une anomalie `matiere_inconnue`.

### Opérations
Liste canonique exhaustive :
- `tournage_ebauche`
- `tournage_finition`
- `fraisage_ebauche`
- `fraisage_finition`
- `fraisage_5axes`
- `percage`
- `taraudage`
- `rectification_cylindrique`
- `rectification_plane`
- `controle_dimensionnel`
- `ebavurage`
- `marquage`
- `lavage`
- `traitement_thermique_externe`
- `anodisation_externe`

Mappings courants :
- "Tournage ebauche", "tour ebauche", "Tournage Ebauche" → `tournage_ebauche`
- "Fraisage 5 axes", "Fraisage 5-axes", "Fraisage cinq axes" → `fraisage_5axes`
- "Controle 3D", "CMM", "Contrôle dimensionnel" → `controle_dimensionnel`

Si l'opération ne correspond à aucune forme canonique → garder la forme originale **et** créer une anomalie.
