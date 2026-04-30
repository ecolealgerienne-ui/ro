# Journal d'expérimentations — LLM extraction

> Une entrée par itération de prompt. Logger même les échecs : ils sont utiles pour comprendre où le modèle bute.

---

## Itération 1 — `prompt_v1` × `fixture_01_simple`

**Date** : (à compléter)
**Modèle** : Claude Sonnet 4.6 (web claude.ai)
**Prompt** : `prompt_v1.md`
**Fixture** : `fixture_01_simple.csv`

### Procédure

1. Ouvrir un nouveau chat sur claude.ai
2. Coller le contenu de `prompt_v1.md`
3. Remplacer `{{SCHEMA}}` par le contenu de `target_schema.md`
4. Remplacer `{{CSV}}` par le contenu de `fixture_01_simple.csv`
5. Envoyer
6. Récupérer le JSON produit ci-dessous

### Output produit par Claude

```json
[à coller ici]
```

### Évaluation (sur 15 — voir `evaluation_grid.md`)

**Critères techniques (4)**
- T1 JSON valide : ☐
- T2 Schéma respecté : ☐
- T3 Aucune hallucination : ☐
- T4 Aucune valeur modifiée silencieusement : ☐

**Critères d'extraction (5)**
- E1 Toutes les 5 OF présentes : ☐
- E2 Toutes les 7 machines détectées (TOUR-01, TOUR-02, FRAIS-01, FRAIS-02, FRAIS-5X-01, PERC-01, CMM-01, RECT-01) : ☐ (note : le compte attendu est 8)
- E3 15 opérations parsées : ☐
- E4 Ordre opérations respecté : ☐
- E5 Type de machine inféré correct : ☐

**Critères de normalisation (3)**
- N1 Matières normalisées (aluminium_7075, acier_42CrMo4, titane_TA6V, acier_inox_316L) : ☐
- N2 Opérations normalisées (tournage_ebauche, fraisage_5axes, controle_dimensionnel, etc.) : ☐
- N3 Valeurs inconnues préservées + anomalie : N/A (F1 propre)

**Critères d'anomalies (3)**
- A1 Anomalies évidentes flaggées : N/A (F1 propre, donc `anomalies` doit être vide)
- A2 Anomalies subtiles flaggées : N/A
- A3 Pas de fausses anomalies : ☐ (`anomalies` doit être [])

**Score** : __/15

### Observations qualitatives

- **Ce qui a fonctionné** :
  - 

- **Ce qui a échoué ou surpris** :
  - 

- **Comportements à relever** (verbosité, refus, format inattendu) :
  - 

### Pistes de raffinement pour `prompt_v2`

- 
- 

---

## Itération 2 — `prompt_v?` × `fixture_??`

(Reproduire le template ci-dessus)

---

## Synthèse en cours

| Prompt | F1 | F2 | F3 | F4 | F5 | Notes |
|--------|----|----|----|----|----|-------|
| v1 | __/15 | — | — | — | — | premier essai |

---

## Décisions prises

| Date | Décision | Raison |
|------|----------|--------|
| | | |
