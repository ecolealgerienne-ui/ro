"""Golden cases — bibliothèque de cas-tests versionnés pour le moteur générique.

Ce dossier contient EXCLUSIVEMENT des cas engine-level (vertical-agnostic).
Les cas réalistes méca vivent dans `tests/verticals/mech_workshop/golden_cases/`
(à venir). Voir `CONTRIBUTING.md` §8 pour la discipline d'architecture.

Structure :
    cases/                  Fichiers YAML (1 fichier = 1 cas)
    _schema.py              Modèles Pydantic du format YAML
    _runner.py              Loader + exécuteur d'un cas

Le runner pytest est dans `tests/test_golden_cases.py` (paramétré sur tous
les .yaml du dossier `cases/`).

Catégories couvertes :
    - baseline_jssp     JSSP pur, optimum connu
    - setup             Setup-dependent (transition_matrix)
    - calendar          machine_unavailability
    - operator          qualified_operator_ids + n_operators
    - shared_resource   SharedResourceSpec
"""
