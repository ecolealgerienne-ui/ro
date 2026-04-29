# Benchmark Taillard

80 instances JSSP de référence introduites par E. Taillard (1993).

## Source

- **Mirror utilisé** : [JSPLIB](https://github.com/tamy0612/JSPLIB) (format texte simple)
- **URL des fichiers bruts** : `https://raw.githubusercontent.com/tamy0612/JSPLIB/master/instances/<name>`
- **Nommage** : `ta01` à `ta80` (sans extension)

## Tailles

| Range       | n_jobs × n_machines | Difficulté |
|-------------|---------------------|-----------|
| ta01–ta10   | 15 × 15             | Optima prouvés |
| ta11–ta20   | 20 × 15             | Best known |
| ta21–ta30   | 20 × 20             | Best known |
| ta31–ta40   | 30 × 15             | Best known |
| ta41–ta50   | 30 × 20             | Best known |
| ta51–ta60   | 50 × 15             | Best known |
| ta61–ta70   | 50 × 20             | Best known |
| ta71–ta80   | 100 × 20            | Best known (très dur) |

## Téléchargement

Depuis `poc-scheduler/` :

```bash
# Tout télécharger (80 instances)
uv run python scripts/download_benchmarks.py taillard

# Sous-ensemble
uv run python scripts/download_benchmarks.py taillard --range ta01-ta10

# Re-télécharger (écrase l'existant)
uv run python scripts/download_benchmarks.py taillard --force
```

Les fichiers sont gitignored — chaque utilisateur du repo retélécharge.

## Format JSPLIB

Chaque fichier suit la structure suivante :

```
+++++++++++++++++++++++++++++
instance ta01
+++++++++++++++++++++++++++++
Taillard 15x15 instance 1 (Table 4, instance 1) ...
15 15
 1 94 5 66 4 10 7 53 ...
 ...
```

- Lignes commençant par `+` : décoration, ignorées
- 1 ligne de description, ignorée par le parser
- 1 ligne `n_jobs n_machines`
- `n_jobs` lignes, chacune avec `2 × n_machines` entiers : `machine_id duration machine_id duration ...`
- Machines **1-indexées** dans le fichier — le parser normalise à 0-indexé en interne

## Métadonnées (`instances_metadata.csv`)

Schéma :

| Colonne | Description |
|---------|-------------|
| `name` | Identifiant (`ta01`, ...) |
| `n_jobs` | Nombre de jobs |
| `n_machines` | Nombre de machines |
| `best_known_makespan` | Meilleur makespan connu publiquement |
| `source_optimum` | `proven_optimal` ou `best_known` |

⚠️ Les valeurs `best_known` sont issues de la littérature et peuvent être
obsolètes. Pour le benchmarking strict (étape 0.4), vérifier contre
[optimizizer.com/TA.php](https://optimizizer.com/TA.php) — la référence
communautaire la plus à jour.

## Source pour les optima

- [E. Taillard, 1993, "Benchmarks for basic scheduling problems"](http://mistic.heig-vd.ch/taillard/problemes.dir/ordonnancement.dir/ordonnancement.html)
- [Optimizer JSP best-known values](https://optimizizer.com/TA.php)
