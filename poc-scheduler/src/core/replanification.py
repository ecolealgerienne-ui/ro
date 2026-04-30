"""Replanification incrementale — freeze partiel + solution hint pour CP-SAT.

Module **vertical-agnostic**. Permet d'accelerer un re-solve apres petite
perturbation (ajout d'un OF, decalage d'une deadline, panne machine) en :

1. **Freeze partiel** : verrouiller les operations qui ne peuvent plus bouger
   (deja demarrees, deja terminees) via des contraintes d'egalite dures sur
   leur `start`. Sans freeze, le solveur pourrait remettre en cause des
   decisions deja appliquees physiquement, ce qui n'a pas de sens metier.

2. **Solution hint** : passer le planning precedent au solveur via
   `model.add_hint(var, value)`. CP-SAT s'en sert pour amorcer sa recherche
   plus efficacement. Pas garanti d'etre respecte (c'est un hint, pas une
   contrainte), mais accelere fortement la convergence sur petites
   perturbations.

Doctrine engine ↔ vertical :
- L'engine **derive automatiquement** freeze + hint depuis un `SolverResult`
  precedent + un timestamp `now` : ops avec `start <= now` -> freeze, ops
  futures -> hint. Cette logique est universelle (job_id, seq_idx, start).
- La verticale **peut etendre** via des regles metier (ex: en meca, freeze
  les setups en cours), mais pour V1 la derivation generique suffit.

Voir `JSSPSolver.solve(freeze=..., solution_hint=...)` pour l'integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    # Import paresseux pour eviter une dependance circulaire :
    # solver.py importe FreezeSpec/SolutionHintSpec/helpers depuis ce module.
    from src.core.solver import SolverResult


class FreezeSpec(BaseModel):
    """Operations dont le start est fixe (contrainte dure) lors du re-solve.

    Attributs :
        operation_starts: mapping `(job_id, sequence_idx) -> start_time`. Le
            solveur ajoutera `start_var == start_time` pour chaque entree.
    """

    model_config = ConfigDict(frozen=True)

    operation_starts: dict[tuple[int, int], int] = Field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.operation_starts

    def __len__(self) -> int:
        return len(self.operation_starts)


class SolutionHintSpec(BaseModel):
    """Hints CP-SAT pour orienter la recherche initiale du solveur.

    Attributs :
        operation_starts: mapping `(job_id, sequence_idx) -> start_time`. Le
            solveur appellera `model.add_hint(start_var, start_time)` pour
            chaque entree. Hints non garantis : si le hint conflicte avec
            d'autres contraintes, CP-SAT les ignore silencieusement.
    """

    model_config = ConfigDict(frozen=True)

    operation_starts: dict[tuple[int, int], int] = Field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.operation_starts

    def __len__(self) -> int:
        return len(self.operation_starts)


def derive_freeze_and_hint_from_previous(
    previous_result: SolverResult,
    *,
    now: int = 0,
) -> tuple[FreezeSpec, SolutionHintSpec]:
    """Derive `FreezeSpec` + `SolutionHintSpec` depuis un `SolverResult` precedent.

    Politique generique :
        - Operations avec `start <= now` (deja demarrees ou terminees) -> freeze.
        - Operations avec `start > now` (futures) -> hint.

    Args:
        previous_result: resultat d'un solving precedent (typiquement le
            schedule actuel en production).
        now: timestamp de reference. 0 = on ne freeze rien (toutes les ops
            sont futures). Pour un re-solve a chaud, passer le `now` reel.

    Returns:
        `(FreezeSpec, SolutionHintSpec)`. Les deux peuvent etre vides
        (previous_result sans schedule).

    Raises:
        ValueError: si `now` est negatif.
    """
    if now < 0:
        raise ValueError(f"now doit etre >= 0, recu {now}")

    freeze: dict[tuple[int, int], int] = {}
    hint: dict[tuple[int, int], int] = {}
    for a in previous_result.schedule:
        key = (a.job_id, a.sequence_idx)
        if a.start <= now:
            freeze[key] = a.start
        else:
            hint[key] = a.start
    return (
        FreezeSpec(operation_starts=freeze),
        SolutionHintSpec(operation_starts=hint),
    )


def apply_freeze(
    model: Any,
    op_vars: dict[tuple[int, int], dict[str, Any]],
    freeze: FreezeSpec,
) -> int:
    """Ajoute les contraintes de freeze au modele. Retourne le nombre applique.

    Les freezes pour des cles absentes de `op_vars` sont ignorees silencieusement
    (par exemple, si l'instance a evolue et que certaines ops ont disparu).
    """
    n_applied = 0
    for key, start_value in freeze.operation_starts.items():
        if key in op_vars:
            model.add(op_vars[key]["start"] == start_value)
            n_applied += 1
    return n_applied


def apply_solution_hint(
    model: Any,
    op_vars: dict[tuple[int, int], dict[str, Any]],
    hint: SolutionHintSpec,
) -> int:
    """Ajoute les hints CP-SAT au modele. Retourne le nombre applique.

    Les hints pour des cles absentes de `op_vars` sont ignores silencieusement.
    """
    n_applied = 0
    for key, start_value in hint.operation_starts.items():
        if key in op_vars:
            model.add_hint(op_vars[key]["start"], start_value)
            n_applied += 1
    return n_applied


__all__ = [
    "FreezeSpec",
    "SolutionHintSpec",
    "apply_freeze",
    "apply_solution_hint",
    "derive_freeze_and_hint_from_previous",
]
