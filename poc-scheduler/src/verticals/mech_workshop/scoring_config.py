"""Calibration du score de confiance pour la verticale `mech_workshop`.

Le moteur generique (`src.core.scoring`) calcule des metriques universelles ;
ce module fournit la **ponderation metier** specifique a la sous-traitance
mecanique de precision.

Justification des poids (a recalibrer apres pilotes design partners) :

- `machine_utilization` (40 %) : critere n*1 en sous-traitance meca. Une
  machine CN qui dort = du capex perdu. Le chef d'atelier juge avant tout
  sur ce signal.
- `status_quality` (30 %) : OPTIMAL vs FEASIBLE change la confiance dans
  le plan, mais pas autant que l'utilisation des machines (FEASIBLE peut
  suffire si l'utilisation est bonne).
- `gap_to_best_known` (20 %) : signal utile quand on dispose d'une borne
  de reference, mais souvent absent en production (pas de benchmark
  intrinseque a chaque atelier).
- `solve_time_ratio` (10 %) : moins critique. Un solve qui prend 50 s
  reste acceptable s'il donne un bon plan.

Poids destines a etre passes a `score_solver_result(weights=...)`. Somme
non-normalisee : la fonction de scoring divise par la somme.
"""

from __future__ import annotations

from typing import Final

MECH_CONFIDENCE_WEIGHTS: Final[dict[str, float]] = {
    "machine_utilization": 0.40,
    "status_quality": 0.30,
    "gap_to_best_known": 0.20,
    "solve_time_ratio": 0.10,
}
