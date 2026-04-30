"""Soft constraints — penalites ponderees agregees a l'objectif CP-SAT.

Module **vertical-agnostic**. Fournit le mecanisme generique pour combiner le
makespan et un ensemble de penalites soft dans une fonction objectif unique :

    minimise(makespan_weight * makespan + sum(weight_i * penalty_i))

Doctrine :
- Une **soft constraint** = une preference d'ordonnancement, qui n'est pas
  obligatoire mais penalisee si violee (cf. specs §7.2 et agent 3.6 NL→soft).
- Une **hard constraint** = obligatoire, encodee directement dans le modele
  (NoOverlap, Precedence, etc.). Une violation = INFEASIBLE.
- Les soft constraints sont **traduites par la verticale** en penalty terms
  via `src/verticals/<vertical>/soft_translators.py`. Cet engine ne connait
  aucune categorie metier.

Le pattern WeightedObjectivePattern remplace MakespanObjectivePattern lorsqu'il
y a au moins 1 soft penalty. S'il n'y en a aucune, comportement identique.

Note importante sur l'extraction du makespan apres solving :
- Avec MakespanObjectivePattern, `solver.objective_value` == makespan.
- Avec WeightedObjectivePattern, `solver.objective_value` == somme ponderee.
  Le solver doit utiliser `solver.value(makespan_var)` pour recuperer le
  makespan brut. Le pattern retourne donc la `IntVar` makespan pour permettre
  cette extraction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

from src.core.pattern import Pattern


@dataclass(frozen=True)
class SoftPenaltyVar:
    """Une penalite soft prete a etre integree dans l'objectif.

    Attributs :
        label   : identifiant lisible (pour tracing / debugging post-solving).
        weight  : poids entier strictement positif (CP-SAT n'aime pas les floats
                  dans l'objectif). La verticale convertit les `weight_hint`
                  flottants de `SoftConstraintsAgent` en entiers (typiquement
                  `int(weight_hint * 100)`).
        var     : `cp_model.IntVar` representant la penalite (>= 0). La
                  semantique exacte (compte, overlap, lateness, etc.) depend
                  du translator metier qui l'a produite.
    """

    label: str
    weight: int
    var: Any  # cp_model.IntVar — Any car SDK CP-SAT non typé


class WeightedObjectivePattern(Pattern):
    """Objectif combinant makespan + somme ponderee de penalites soft.

    Si `soft_penalties` est vide, equivalent a `MakespanObjectivePattern`.
    """

    name: ClassVar[str] = "weighted_objective"
    description: ClassVar[str] = "Minimise makespan_weight * makespan + sum(weight_i * penalty_i)."

    def apply(
        self,
        model: Any,
        *,
        end_vars: Sequence[Any],
        horizon: int,
        soft_penalties: Sequence[SoftPenaltyVar] = (),
        makespan_weight: int = 1,
    ) -> Any:
        """Construit l'objectif et le minimise. Retourne la `IntVar` makespan.

        Args:
            model: `cp_model.CpModel`.
            end_vars: variables de fin de chaque dernier op de chaque job.
            horizon: borne sup theorique du makespan.
            soft_penalties: liste de `SoftPenaltyVar` produites par les
                translators de la verticale. Peut etre vide.
            makespan_weight: poids du makespan dans la somme ponderee. Defaut 1.
                Augmenter pour rendre le makespan dominant ; diminuer pour
                privilegier les soft.

        Returns:
            La `IntVar` makespan, pour extraction post-solving via
            `solver.value(makespan_var)`.
        """
        if not end_vars:
            raise ValueError("end_vars ne peut pas etre vide")
        if horizon < 0:
            raise ValueError(f"horizon doit etre >= 0, recu {horizon}")
        if makespan_weight < 1:
            raise ValueError(f"makespan_weight doit etre >= 1, recu {makespan_weight}")
        for sp in soft_penalties:
            if sp.weight < 1:
                raise ValueError(
                    f"SoftPenaltyVar '{sp.label}' : weight doit etre >= 1, recu {sp.weight}"
                )

        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, list(end_vars))

        if not soft_penalties:
            model.minimize(makespan_weight * makespan)
            return makespan

        # Somme ponderee : makespan + Sum(w_i * penalty_i)
        terms: list[Any] = [makespan_weight * makespan]
        terms.extend(sp.weight * sp.var for sp in soft_penalties)
        model.minimize(sum(terms))
        return makespan
