# Design — Pipeline d'extraction Pre-flight + LLM + Post-flight

> Spec interne pour la Phase 3.5 (agent extraction code).
> Formalise la séparation des responsabilités entre code déterministe et LLM,
> issue de l'observation que beaucoup de checks "anomalies" ne nécessitent pas
> de LLM (durée < 0, date invalide, etc.).

**Statut** : design, pas encore implémenté.
**Référentiel produit** : `specs-fonctionnelles-v3.md` §3 (Module Data Quality, logique 3 niveaux).

---

## Pourquoi cette architecture

Pendant l'expérimentation no-code (`results.md`), on a observé que Claude Sonnet, même bien cadré par `prompt_v2`, doit consacrer une partie de son raisonnement à des vérifications triviales : durée négative, date dans le passé, OF doublon exact, format de date.

**Ces vérifications sont 100 % déterministes — un script Python les fait mieux, plus vite, gratuitement.**

Garder ces vérifications côté LLM coûte :
- Tokens (≈ 30-50 % du prompt sert à expliquer les seuils numériques)
- Latence (les bonnes réponses passent par un round-trip LLM)
- Risque de drift (variations de comportement selon la version du modèle)
- Surface d'attaque pour hallucinations

Le bon pattern : **chaque couche fait ce qu'elle fait le mieux**.

---

## Pipeline complet en 4 étages

```
┌─────────────┐
│  CSV brut   │  (Excel/CSV exporté ERP)
└──────┬──────┘
       ▼
┌─────────────────────────────────────────────────┐
│  [1] PRE-FLIGHT  (Python déterministe, 0€)      │
│                                                  │
│  • Parsing CSV (séparateur, encoding)           │
│  • Validation format des champs                 │
│  • Détection anomalies Niveau 1                 │
│  • Conversion dates → ISO                       │
│  • Mapping colonnes évidentes (heuristique)     │
│                                                  │
│  → produit `PreflightReport`                    │
└──────────────┬───────────────────────────────────┘
               ▼
       ┌──────────────┐
       │  [2] Décision │
       └──────┬────────┘
              │
       ┌──────┴────────┐
       │               │
   bloquant ?       OK / warning
       │               │
       ▼               ▼
   Retour user    ┌────────────────────────────────────────┐
   (pas de LLM)   │  [3] LLM CLAUDE  (sémantique uniquement)│
                  │                                         │
                  │  Input : CSV nettoyé + PreflightReport  │
                  │                                         │
                  │  • Mapping colonnes ambiguës            │
                  │  • Normalisation matières (fuzzy)       │
                  │  • Normalisation opérations (fuzzy)     │
                  │  • Inférence type machine inconnue      │
                  │  • Anomalies sémantiques (OF doublon    │
                  │    incohérent, opération ambiguë)       │
                  │                                         │
                  │  → produit `WorkshopExtraction` JSON    │
                  └────────────────┬────────────────────────┘
                                   ▼
                  ┌────────────────────────────────────────┐
                  │  [4] POST-FLIGHT  (Python)             │
                  │                                         │
                  │  • Validation Pydantic stricte du JSON  │
                  │  • Cohérence inter-référentielle        │
                  │  • Fusion des anomalies pre-flight +    │
                  │    LLM dans le rapport final            │
                  │                                         │
                  │  → produit `WorkshopInstance` final     │
                  └────────────────────────────────────────┘
```

---

## [1] Pre-flight — Responsabilités

### Inputs
- Le fichier CSV/Excel brut (ou son chemin)
- Optionnellement : la date courante (sinon `datetime.now()`)

### Sorties
```python
class PreflightReport(BaseModel):
    csv_parseable: bool
    detected_separator: Literal[",", ";", "\t", "|"]
    detected_encoding: str  # utf-8, latin-1, cp1252...

    column_mapping_suggested: dict[str, str]
    # ex: {"NO_OF": "order_id", "REF_CLIENT": "client", ...}
    # produit par heuristique simple (regex sur noms de colonnes connus)

    rows_parsed: int
    rows_with_errors: list[PreflightError]

    cleaned_csv: str | None
    # CSV ré-écrit sans les lignes bloquantes, avec dates ISO
    # None si parsing du CSV a échoué
```

### Types d'erreurs détectées (Niveau 1 — anomalies certaines)

| Type | Détection | Action |
|------|-----------|--------|
| `csv_unparseable` | Le fichier ne parse avec aucun séparateur connu | Bloquant — retour utilisateur immédiat |
| `encoding_mismatch` | Caractères corrompus détectés | Warning — proposer ré-encodage |
| `column_required_missing` | Aucune colonne ne mappe vers `order_id` ou `duration_min` | Bloquant |
| `duration_not_int` | Durée ne parse pas en entier | Bloquant pour cette ligne |
| `duration_negative_or_zero` | Durée ≤ 0 | Niveau 1 — ligne marquée mais préservée pour LLM (qui pourra contextualiser) |
| `date_unparseable` | Date ne match aucun format connu (ISO, DD/MM/YYYY, MM/DD/YYYY, etc.) | Bloquant pour cette ligne |
| `date_in_past` | Date < `datetime.now()` | Niveau 1 — flagué, préservé |
| `required_field_empty` | OF ou client vide | Bloquant pour cette ligne |
| `of_duplicate_exact` | Lignes parfaitement identiques (toutes les colonnes égales) | Warning — déduplication automatique |

### Heuristiques de mapping colonnes

Détection par regex sur le nom de la colonne, insensible à la casse :

```python
COLUMN_PATTERNS: dict[str, list[str]] = {
    "order_id": [r"^(no_)?of$", r"^order_id$", r"^num(_of)?$", r"^reference$"],
    "client": [r"^client$", r"^ref_client$", r"customer", r"donneur"],
    "piece_name": [r"^desig", r"^piece$", r"^part_name$", r"libelle"],
    "material": [r"^materia", r"^matiere$", r"^mat$"],
    "operation_type": [r"^operation", r"^op_desc", r"^op_libelle"],
    "machine": [r"^machine$", r"^poste", r"^workstation$"],
    "duration_min": [r"^duree", r"^tps_op", r"^temps", r"^duration"],
    "deadline": [r"^date_liv", r"^deadline", r"^echeance"],
}
```

Si une colonne mappe vers plusieurs cibles → ambiguïté → **on n'inclut pas dans le mapping** et on laisse le LLM décider.

Si aucune colonne ne mappe vers une cible **requise** (`order_id`, `duration_min`) → bloquant.

### Conversion de dates

Liste des formats acceptés (par ordre de tentative) :
```python
DATE_FORMATS = [
    "%Y-%m-%d",          # 2026-05-15
    "%d/%m/%Y",          # 15/05/2026
    "%d-%m-%Y",          # 15-05-2026
    "%Y/%m/%d",          # 2026/05/15
    "%d.%m.%Y",          # 15.05.2026
    "%m/%d/%Y",          # 05/15/2026 (US, dernier essai)
]
```

Si succès → date convertie en ISO `YYYY-MM-DD` dans le `cleaned_csv`.
Si échec → `date_unparseable` dans `rows_with_errors`.

### Ce que pre-flight NE FAIT PAS

- Pas de normalisation matières ou opérations (sémantique → LLM)
- Pas de détection de doublon incohérent (sémantique → LLM)
- Pas d'inférence de type machine pour préfixes inconnus (sémantique → LLM)
- Pas de jugement sur la "raisonnabilité" d'une durée (zone grise → LLM)
- Pas de modification silencieuse des valeurs (toujours préserver, toujours flagger)

---

## [2] Décision — Logique de routage

```python
def should_call_llm(report: PreflightReport) -> tuple[bool, str]:
    """Retourne (should_continue, reason)."""
    if not report.csv_parseable:
        return False, "CSV non parsable — corriger l'export ERP"

    if not report.cleaned_csv:
        return False, "Aucune ligne valide après pre-flight"

    blocking_errors = [e for e in report.rows_with_errors if e.severity == "bloquant"]
    if len(blocking_errors) > report.rows_parsed * 0.5:
        return False, f"Plus de 50% des lignes invalides ({len(blocking_errors)}/{report.rows_parsed})"

    # Tout le reste : on continue, le LLM gérera le sémantique
    return True, "OK"
```

Pas de LLM si :
- CSV non-parsable du tout
- Plus de 50 % des lignes ont des erreurs bloquantes (signal qu'il y a un problème de format global, pas individuel)

---

## [3] LLM Claude — Responsabilités réduites

### Inputs (vs aujourd'hui)
- `cleaned_csv` (sans les lignes invalides format)
- `column_mapping_suggested` (déjà fait par heuristique)
- `preflight_anomalies` (déjà détectées, à inclure dans `anomalies`)
- Le `target_schema.md` et la liste canonique
- La date courante explicite

### Tâches restantes
1. **Confirmer/corriger le mapping** suggéré par pre-flight
2. **Normaliser** matières et opérations (fuzzy matching sémantique)
3. **Inférer le type machine** pour les préfixes inconnus
4. **Détecter les anomalies sémantiques** :
   - OF doublons incohérents (champs différents pour même OF)
   - Opérations ambiguës (sans qualificatif)
   - Matières inconnues (hors liste canonique)

### Réduction attendue de prompt

Le `prompt_v2.md` actuel fait ≈ 100 lignes de règles. Avec pre-flight :
- Section "Anomalies à signaler obligatoirement" : peut être réduite de 11 types à 4 (ceux qui restent sémantiques)
- Section "Anti-zèle" : conservée (concerne la normalisation)
- Section "Type de machine" : conservée
- Estimation : **prompt réduit de 30-40 %**

### Fusion d'anomalies en post-flight

Le LLM ne re-détecte PAS les anomalies déjà flagguées par pre-flight. Le post-flight les fusionne :

```python
final_anomalies = preflight_report.anomalies + llm_response.anomalies
```

Cela évite la duplication et garantit la cohérence.

---

## [4] Post-flight — Validation finale

### Vérifications
1. **Validation Pydantic stricte** du JSON LLM
2. **Cohérence inter-référentielle** :
   - Toutes les machines référencées par les opérations existent dans `machines`
   - Tous les `family_id` (si setup actif) sont dans la borne de la matrice
   - Tous les `qualified_operator_ids` sont < `n_operators`
3. **Fusion anomalies** pre-flight + LLM
4. **Conversion** vers `WorkshopInstance` (le type Pydantic existant en `src/core/models.py`)

### Erreurs post-flight
Si le LLM retourne du JSON invalide ou incohérent → **retry** avec le message d'erreur. Maximum 2 retries (Phase 3.x — pattern circuit breaker à appliquer).

Si retry échoue → erreur bloquante remontée à l'utilisateur.

---

## Bénéfices attendus

| Métrique | Sans pre-flight | Avec pre-flight | Gain |
|----------|-----------------|------------------|------|
| Tokens prompt | ~3000 | ~2000 | -33 % |
| Tokens output (anomalies) | ~500-1500 | ~200-500 | -60 % |
| Latence p50 | 8-15s | 5-10s | -33 % |
| Risque hallucination | Élevé sur anomalies triviales | Réduit | qualitatif |
| Coût par client/mois | 10-40 € | 6-25 € | -30 % |

(Estimations à valider en Phase 3.5 mesurée.)

---

## Lien avec la spec V3 et la logique 3 niveaux

| Niveau spec V3 | Prise en charge | Action |
|----------------|-----------------|--------|
| **Niveau 1** — anomalies certaines | **Pre-flight Python** | Bloquante ou flag automatique |
| **Niveau 2** — anomalies probables | **LLM** | Flag + suggestion contextuelle |
| **Niveau 3** — surprenantes mais possibles | **LLM + journal** | Tracé pour apprentissage |

Le pre-flight implémente exactement le Niveau 1 que la spec préconise, et libère le LLM pour les Niveaux 2 et 3 où sa valeur ajoutée est réelle.

---

## Ce qui reste à valider avant Phase 3.5

1. **POC pre-flight** (étape B suggérée) : prototype Python validé sur les fixtures F1, F3, F4
2. **Prompt v3** (étape C) : prompt allégé qui assume le pre-flight comme entrée
3. **Re-test avec pipeline complet** : pre-flight + LLM v3 → vérifier que les scores 15/15 tiennent
4. **Mesure réelle de réduction de tokens** : baseline v2 vs v3+pre-flight

Ces étapes ne sont pas urgentes mais à faire avant de coder l'agent en Phase 3.5.

---

*Conçu suite à l'observation pertinente : "certains tests on peut les faire nous-mêmes". C'est la bonne discipline d'ingénierie LLM en 2026.*
