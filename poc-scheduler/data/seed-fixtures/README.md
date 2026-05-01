# seed-fixtures — exemples de CSV pour tester le preflight

3 fichiers prêts à uploader via l'IHM (route `/workshops/<id>/preflight`)
ou directement sur l'API (`POST /api/workshops/<id>/preflight-sessions`).
Reflètent les 3 niveaux d'anomalies du module preflight méca.

| Fichier | Contenu | Anomalies attendues |
|---------|---------|---------------------|
| `clean.csv` | 8 colonnes canoniques (`order_id`, `client`, `piece_name`, `material`, `operation_type`, `machine`, `duration_min`, `deadline`), valeurs propres | 0 anomalie — import 8/8 |
| `realistic.csv` | En-têtes synonymes ERP (`no_of`, `ref_client`, `duree_min`…) + ~10 % valeurs douteuses (durée `"3h30"`, client manquant, durée 1440 min) | 1 probable / surprising — import 9 ou 10/10 |
| `broken.csv` | Colonne `duration_min` absente | 1 certain bloquant — import 0/3 |

## Régénération

Ces fixtures sont aussi régénérées automatiquement à chaque exécution de
`scripts/seed_via_api.py`. Le contenu canonique des builders est dans
`scripts/seed_via_api.py::_build_clean_csv()` etc.

Pour régénérer manuellement :
```bash
uv run python scripts/seed_via_api.py seed   # crée vitrine + (re)génère les CSVs
```

## Format attendu

Les patterns regex acceptés pour chaque colonne canonique sont définis dans
`src/verticals/mech_workshop/preflight_config.py` (`MECH_COLUMN_PATTERNS`).
Pour ajouter un synonyme : éditer ce fichier puis relancer la suite tests.
