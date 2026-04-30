# Verdict — Expérimentation LLM extraction

> Synthèse stratégique de l'expérimentation pour le projet.
> Document à transmettre / consulter pour comprendre le résultat sans relire tous les détails.

**Date de clôture** : 2026-04-30
**Statut** : ✅ Risque levé — extraction LLM fiable sur le périmètre testé

---

## Question initiale

> Claude Sonnet sait-il extraire les données d'un atelier de mécanique de
> précision à partir d'un fichier ERP CSV imparfait, avec un comportement
> assez strict pour servir de socle au trust layer ?

## Réponse empirique : **OUI**

**45/45 critères validés sur 3 fixtures couvrant le spectre complet** :

| Fixture | Difficulté | Score |
|---------|------------|-------|
| F1 — cas propre | Baseline | 15/15 |
| F4 — anomalies réelles | Test du filet de sécurité | 15/15 |
| F3 — format ERP chaotique | Diversité réelle | 15/15 |

## Méthode

4 itérations dans Claude.ai (web, no-code), prompt ajusté entre v1 et v2 :

- **prompt_v1** : règles trop floues sur les anomalies → 14/15 sur F1 (sur-zèle, 2 faux positifs)
- **prompt_v2** : seuils numériques stricts + règle anti-zèle explicite → 15/15 sur F1, F3, F4

Total : ~30 minutes de chat. Coût : 0 €. Apprentissage : maximal.

## Pourquoi ça compte pour le projet

D'après `specs-fonctionnelles-v3.md` §3 (Module Data Quality), l'extraction est *"probablement 30-40% du travail de développement de l'agent d'extraction"*. C'était identifié comme un risque produit majeur (Phase 3.5).

**On vient de démontrer que ce n'est pas un risque structurel** — c'est de l'ingénierie de prompt, et le prompt qui marche existe (`prompt_v2.md`).

## Ce qu'on a découvert sur le comportement de Claude

### Forces (à exploiter)

1. **Tolérance extrême aux variations** : "42 CrMo 4", "Ti-6Al-4V", "AL-2017", "Aluminium 7075-T6" tous correctement normalisés sans instruction spécifique
2. **Mapping de colonnes ERP techniques** : NO_OF, DESIG_PIECE, POSTE_TRAVAIL, TPS_OP_MIN tous correctement interprétés
3. **Conversion multi-format** : DD/MM/YYYY et YYYY-MM-DD interchangeables
4. **Comportement strict par défaut** : avec un prompt précis, Claude préfère flagger qu'inventer
5. **Préservation des valeurs problématiques** : durations -30, 0, 2000 gardées telles quelles dans le JSON, pas silencieusement corrigées
6. **Détection 6/6 sur anomalies réelles** sans aucune fausse positive (F4)

### Biais à cadrer (validés sur prompt_v2)

1. **Sur-zèle "common sense industriel"** : Claude veut spontanément flagger une durée courte sur machine CN, même quand statistiquement normale
   → Cadré par seuils numériques stricts + règle anti-zèle explicite avec plages normales
2. **Connaissance implicite de la date du jour** : Claude utilise sa date interne pour `date_passee`
   → À gérer côté API en passant la date explicitement
3. **Choix non spécifiés sur OF doublons** : Claude fusionne intelligemment, mais le comportement doit être explicite
   → À spécifier dans le prompt système

## Implications pour la roadmap

### Court terme

- **Phase 3.5 (agent extraction code) est de-risquée**. On peut programmer l'agent en API quand on aura besoin, en reprenant `prompt_v2.md` comme base.
- **Le trust layer côté extraction (anomalies)** fonctionne déjà bien avec un prompt strict. Phase 2 sera concentrée sur le trust layer côté solveur (golden cases, score de confiance, simulation opérationnelle).

### Décisions stratégiques que ça permet

1. **On peut avancer sur le produit sans craindre que l'extraction soit le goulot d'étranglement.**
2. **Les Phases 3.x (LLM) deviennent moins risquées qu'estimé initialement** — on a montré qu'avec le bon cadrage, le LLM est fiable.
3. **Le vrai risque restant est de l'ordre du PMF**, pas du tech.

### Tests non faits (et raisons)

- **F2 (variations orthographiques pures)** : redondant avec F3 qui a couvert les variations dans un format ERP plus stressant.
- **F5 (volume 50-80 lignes)** : à tester en API, pas en chat. Les limites de contexte sont mieux mesurables côté API.

## Référentiels

- `prompt_v2.md` : **prompt de référence** à reprendre tel quel pour la Phase 3.5
- `target_schema.md` : structure de sortie validée
- `evaluation_grid.md` : grille de 15 critères à reprendre pour les tests automatiques

## Ce que ça ne dit pas

L'expérimentation valide :
- ✓ Extraction depuis CSV ERP avec variations standard
- ✓ Normalisation matières / opérations connues
- ✓ Détection d'anomalies basiques (durée, date, OF doublon)

Elle ne valide pas (à tester ultérieurement) :
- ✗ Extraction depuis Excel binaire `.xlsx` avec mise en forme (cellules fusionnées, multi-feuilles)
- ✗ OCR depuis PDF scannés (cas réel possible chez certains PME)
- ✗ Performance sur volume > 100 lignes (à tester en API)
- ✗ Robustesse face à des données sciemment trompeuses (adversarial)
- ✗ Coût en tokens sur des fichiers de 100-500 lignes (à mesurer en API)

Ces points ne bloquent pas la suite, mais sont à garder en tête pour la Phase 3.5.

---

*L'extraction LLM est solide. La discipline du prompt fait la différence.*
