"""Configuration pre-flight pour la verticale `mech_workshop`.

Fournit les `column_patterns`, `canonical_fields` et `required_canonical_fields`
spécifiques à la mécanique de précision (CSV ERP type Sage X3, Cegid, Clipper).

Ce module est consommé par `src.preflight.run_preflight()` qui est lui-même
agnostique vis-à-vis de la verticale.

Pour ajouter une verticale, créer un module similaire avec ses propres
patterns (ex: `verticals/sante_blocs/preflight_config.py` aurait des
patterns sur `patient_id`, `bloc_operatoire`, `chirurgien`, etc.).
"""

from __future__ import annotations

from typing import Final

# Champs canoniques attendus dans la sortie finale (post-LLM) de la verticale méca.
MECH_CANONICAL_FIELDS: Final[tuple[str, ...]] = (
    "order_id",
    "client",
    "piece_name",
    "material",
    "operation_type",
    "machine",
    "duration_min",
    "deadline",
)

# Champs canoniques sans lesquels le pre-flight méca ne peut pas continuer.
MECH_REQUIRED_CANONICAL_FIELDS: Final[frozenset[str]] = frozenset({"order_id", "duration_min"})

# Patterns regex (insensibles à la casse) par champ canonique.
# Ordre interne : spécifique → générique.
MECH_COLUMN_PATTERNS: Final[dict[str, tuple[str, ...]]] = {
    "order_id": (
        r"^no_of$",
        r"^num_of$",
        r"^of$",
        r"^order_?id$",
        r"^reference_of$",
        r"^numero(_of)?$",
    ),
    "client": (
        r"^ref_client$",
        r"^client$",
        r"^customer$",
        r"^donneur(_d_ordre)?$",
    ),
    "piece_name": (
        r"^desig(_piece)?$",
        r"^designation$",
        r"^piece(_name)?$",
        r"^part_?name$",
        r"^libelle_piece$",
    ),
    "material": (
        r"^materi(au|al)$",
        r"^matiere$",
        r"^mat(_ref)?$",
    ),
    "operation_type": (
        r"^operation(_desc)?$",
        r"^op_desc$",
        r"^op_libelle$",
        r"^operation_type$",
    ),
    "machine": (
        r"^poste(_travail)?$",
        r"^machine$",
        r"^workstation$",
        r"^ressource$",
    ),
    "duration_min": (
        r"^duree(_min|_op)?$",
        r"^tps_op(_min)?$",
        r"^temps(_op)?$",
        r"^duration(_min)?$",
    ),
    "deadline": (
        r"^date_liv(raison)?$",
        r"^deadline$",
        r"^echeance$",
        r"^date_due$",
    ),
}
