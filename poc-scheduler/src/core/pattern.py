"""Bibliothèque de patterns CP-SAT — interface OOP (étape 1.1).

Chaque pattern est une classe encapsulant un type de contrainte CP-SAT. Les
classes sont instanciées et appliquées à un `cp_model.CpModel` via la méthode
`apply(model, **context)`. Le contexte (variables CP-SAT, paramètres
spécifiques) est passé en kwargs documentés par sous-classe.

Conventions :
- Toutes les classes héritent de `Pattern` (ABC).
- `name` est un identifiant unique servant à la registry et au logging.
- `description` est un texte court (français) pour l'introspection.
- `apply` ajoute des contraintes au modèle ; peut retourner une valeur utile
  (ex: variable makespan ou liste d'intervals).
- Toutes les validations métier (longueurs, indices, valeurs) sont dans `apply`
  pour échouer tôt avec un message clair.

Une registry `PATTERNS` permet l'introspection et l'usage par `JSSPSolver`.
Les fonctions de `src.core.patterns` sont conservées comme délégates de
compatibilité ; elles seront dépréciées en Phase 2.

Référence : `specs-techniques-v3.md` §5.3 (interface Pattern).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar


class Pattern(ABC):
    """Classe de base abstraite pour tous les patterns CP-SAT."""

    name: ClassVar[str]
    description: ClassVar[str] = ""

    @abstractmethod
    def apply(self, model: Any, **context: Any) -> Any:
        """Applique le pattern au modèle CP-SAT.

        Les kwargs attendus sont documentés par sous-classe. La méthode peut
        retourner une valeur utile (ex: variable makespan, liste d'intervals)
        ou None.
        """


# ---------- Patterns de base (étape 0.3) ----------


class NoOverlapMachinePattern(Pattern):
    """Empêche les opérations sur une même machine de se chevaucher."""

    name: ClassVar[str] = "no_overlap_machine"
    description: ClassVar[str] = "Contrainte NoOverlap pour les opérations d'une même machine."

    def apply(self, model: Any, *, intervals: Sequence[Any]) -> None:
        if len(intervals) > 1:
            model.add_no_overlap(list(intervals))


class PrecedenceInJobPattern(Pattern):
    """Force la précédence séquentielle dans la gamme d'un job."""

    name: ClassVar[str] = "precedence_in_job"
    description: ClassVar[str] = "end[i] <= start[i+1] dans la gamme d'un job."

    def apply(
        self,
        model: Any,
        *,
        end_vars: Sequence[Any],
        start_vars: Sequence[Any],
    ) -> None:
        if len(end_vars) != len(start_vars):
            raise ValueError(
                f"end_vars ({len(end_vars)}) et start_vars ({len(start_vars)}) "
                "doivent avoir la même longueur"
            )
        for i in range(len(end_vars) - 1):
            model.add(end_vars[i] <= start_vars[i + 1])


class MakespanObjectivePattern(Pattern):
    """Crée la variable makespan, l'égalité au max des fins, et minimise."""

    name: ClassVar[str] = "makespan_objective"
    description: ClassVar[str] = "Objectif minimisation makespan = max(end_vars)."

    def apply(self, model: Any, *, end_vars: Sequence[Any], horizon: int) -> Any:
        if not end_vars:
            raise ValueError("end_vars ne peut pas être vide")
        if horizon < 0:
            raise ValueError(f"horizon doit être ≥ 0, reçu {horizon}")
        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, list(end_vars))
        model.minimize(makespan)
        return makespan


# ---------- Patterns avancés (étape 0.6) ----------


class SequenceDependentSetupPattern(Pattern):
    """No-overlap avec setup time dépendant de la séquence (familles de pièces).

    Encodage **circuit-based** (Phase 1.1.opt) : une contrainte `add_circuit`
    par machine impose une permutation hamiltonienne sur les ops, avec un
    nœud dummy source/sink. Chaque arc `i -> j` actif déclenche
    `start[j] >= end[i] + transition[fam_i][fam_j]`.

    Cet encodage est strictement équivalent en sémantique à l'ancien encodage
    par paires disjonctives, mais donne au solveur la structure « routing /
    permutation » explicite, ce qui active sa propagation spécialisée
    (élimination de sous-tours sur le graphe résiduel). En pratique : passe
    de 30 % de feasibility à ≥ 80 % en 60 s sur le benchmark 1.1d (10 ateliers
    mixed, mode `setup`).

    Référence : exemple officiel OR-Tools `jobshop_with_setup_times_sat.py`.
    """

    name: ClassVar[str] = "no_overlap_with_setup"
    description: ClassVar[str] = (
        "Circuit hamiltonien par machine + transitions matrice inter-familles."
    )

    def __init__(self, *, name_prefix: str = "seq") -> None:
        self.name_prefix = name_prefix

    def apply(
        self,
        model: Any,
        *,
        starts: Sequence[Any],
        ends: Sequence[Any],
        family_ids: Sequence[int],
        transition_matrix: Sequence[Sequence[int]],
    ) -> None:
        n = len(starts)
        if n != len(ends):
            raise ValueError(f"starts ({n}) et ends ({len(ends)}) doivent avoir la même longueur")
        if n != len(family_ids):
            raise ValueError(
                f"starts ({n}) et family_ids ({len(family_ids)}) doivent avoir la même longueur"
            )
        if n <= 1:
            return

        n_families = len(transition_matrix)
        for row in transition_matrix:
            if len(row) != n_families:
                raise ValueError(
                    f"transition_matrix doit être carrée ({n_families}×{n_families}), "
                    f"ligne de taille {len(row)} trouvée"
                )
            for v in row:
                if v < 0:
                    raise ValueError(f"transition_matrix : valeurs négatives interdites, vu {v}")

        for fid in family_ids:
            if not 0 <= fid < n_families:
                raise ValueError(f"family_id {fid} hors borne (matrice {n_families}×{n_families})")

        # Encodage circuit : noeud 0 = dummy source/sink, noeuds 1..n = ops.
        # Arc literal `lit_ij` => "op (j-1) suit directement op (i-1)".
        # add_circuit impose un cycle hamiltonien passant par tous les noeuds.
        arcs: list[tuple[int, int, Any]] = []

        # Arcs source -> op (op_i est le premier de la machine)
        for i in range(n):
            lit = model.new_bool_var(f"{self.name_prefix}_src_to_{i}")
            arcs.append((0, i + 1, lit))

        # Arcs op -> sink (op_i est le dernier de la machine)
        for i in range(n):
            lit = model.new_bool_var(f"{self.name_prefix}_{i}_to_sink")
            arcs.append((i + 1, 0, lit))

        # Arcs op_i -> op_j (succession directe), enforce setup transition
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                lit = model.new_bool_var(f"{self.name_prefix}_{i}_to_{j}")
                arcs.append((i + 1, j + 1, lit))
                fam_i = family_ids[i]
                fam_j = family_ids[j]
                setup_ij = transition_matrix[fam_i][fam_j]
                model.add(starts[j] >= ends[i] + setup_ij).only_enforce_if(lit)

        model.add_circuit(arcs)


class QualifiedOperatorPattern(Pattern):
    """Chaque opération assignée à un opérateur qualifié unique ; pas deux ops pour un même opérateur en parallèle."""

    name: ClassVar[str] = "qualified_operator"
    description: ClassVar[str] = (
        "Affectation opérateurs qualifiés via intervals optionnels + no_overlap."
    )

    def __init__(self, *, name_prefix: str = "qual") -> None:
        self.name_prefix = name_prefix

    def apply(
        self,
        model: Any,
        *,
        starts: Sequence[Any],
        ends: Sequence[Any],
        durations: Sequence[int],
        qualifications: Sequence[Sequence[int]],
        n_operators: int,
    ) -> None:
        n_ops = len(starts)
        if not (n_ops == len(ends) == len(durations) == len(qualifications)):
            raise ValueError(
                f"starts/ends/durations/qualifications doivent avoir la même longueur, "
                f"reçu {n_ops}/{len(ends)}/{len(durations)}/{len(qualifications)}"
            )
        if n_operators < 0:
            raise ValueError(f"n_operators doit être ≥ 0, reçu {n_operators}")

        operator_intervals: dict[int, list[Any]] = {k: [] for k in range(n_operators)}

        for i in range(n_ops):
            qualified = list(qualifications[i])
            if not qualified:
                raise ValueError(f"Opération {i} sans opérateur qualifié")
            if any(k < 0 or k >= n_operators for k in qualified):
                raise ValueError(
                    f"Opération {i} : operator_id hors borne dans {qualified} "
                    f"(n_operators={n_operators})"
                )

            presence_vars: list[Any] = []
            for k in qualified:
                present = model.new_bool_var(f"{self.name_prefix}_op{i}_to_op{k}")
                presence_vars.append(present)
                opt_interval = model.new_optional_interval_var(
                    starts[i], durations[i], ends[i], present, f"{self.name_prefix}_int_op{i}_op{k}"
                )
                operator_intervals[k].append(opt_interval)

            model.add_exactly_one(presence_vars)

        for k in range(n_operators):
            if len(operator_intervals[k]) > 1:
                model.add_no_overlap(operator_intervals[k])


class SharedResourceExclusionPattern(Pattern):
    """Limite N opérations actives simultanément sur une ressource partagée."""

    name: ClassVar[str] = "shared_resource_exclusion"
    description: ClassVar[str] = "Cumulative à demande unitaire et capacité = max_concurrent."

    def apply(
        self,
        model: Any,
        *,
        intervals: Sequence[Any],
        max_concurrent: int,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError(f"max_concurrent doit être ≥ 1, reçu {max_concurrent}")
        if len(intervals) <= max_concurrent:
            return
        demands = [1] * len(intervals)
        model.add_cumulative(list(intervals), demands, max_concurrent)


class UnavailableIntervalsPattern(Pattern):
    """Génère des intervals fixes pour des plages d'indisponibilité (calendrier)."""

    name: ClassVar[str] = "unavailable_intervals"
    description: ClassVar[str] = "Intervals fixes (start, end) à fusionner avec un no_overlap."

    def __init__(self, *, name_prefix: str = "unavail") -> None:
        self.name_prefix = name_prefix

    def apply(
        self,
        model: Any,
        *,
        periods: Sequence[tuple[int, int]],
    ) -> list[Any]:
        intervals: list[Any] = []
        for k, (start, end) in enumerate(periods):
            if start < 0 or end < 0:
                raise ValueError(f"Période {k} : bornes négatives ({start}, {end})")
            if start >= end:
                raise ValueError(f"Période {k} : start ({start}) doit être < end ({end})")
            s_var = model.new_int_var(start, start, f"{self.name_prefix}_{k}_s")
            e_var = model.new_int_var(end, end, f"{self.name_prefix}_{k}_e")
            intervals.append(
                model.new_interval_var(s_var, end - start, e_var, f"{self.name_prefix}_{k}_i")
            )
        return intervals


# ---------- Registry ----------


PATTERNS: dict[str, type[Pattern]] = {
    NoOverlapMachinePattern.name: NoOverlapMachinePattern,
    PrecedenceInJobPattern.name: PrecedenceInJobPattern,
    MakespanObjectivePattern.name: MakespanObjectivePattern,
    SequenceDependentSetupPattern.name: SequenceDependentSetupPattern,
    QualifiedOperatorPattern.name: QualifiedOperatorPattern,
    SharedResourceExclusionPattern.name: SharedResourceExclusionPattern,
    UnavailableIntervalsPattern.name: UnavailableIntervalsPattern,
}


def get_pattern(name: str) -> Pattern:
    """Instancie un pattern par son nom (lookup dans la registry)."""
    cls = PATTERNS.get(name)
    if cls is None:
        raise KeyError(f"Pattern '{name}' inconnu. Disponibles : {sorted(PATTERNS.keys())}")
    return cls()


def list_patterns() -> list[str]:
    """Retourne les noms de tous les patterns enregistrés."""
    return sorted(PATTERNS.keys())
