"""Verticales — code spécifique à un métier donné.

Le code dans ce dossier mappe les concepts génériques du moteur
(`src/core/`, `src/preflight/`) vers les concepts d'un métier précis.

Chaque sous-dossier représente UNE verticale. La règle d'or :

    Le moteur (`src/core/`, `src/preflight/`) ne dépend JAMAIS d'une verticale.
    Une verticale peut dépendre du moteur.
    Une verticale ne dépend PAS d'une autre verticale.

Verticales actuelles :

    - `mech_workshop/` : sous-traitance mécanique de précision (premier marché)

Verticales futures envisagées (pour info, non implémentées) :

    - `chaudronnerie/` : tôlerie, métallerie
    - `plasturgie/` : transformation plastique
    - `services_techniques/` : maintenance industrielle, plombiers, électriciens
    - `sante_blocs/` : ordonnancement blocs opératoires
    - `education_edt/` : emplois du temps lycées/universités

Pour ajouter une verticale, voir `CONTRIBUTING.md` §8 (Architecture multi-verticale).
"""
