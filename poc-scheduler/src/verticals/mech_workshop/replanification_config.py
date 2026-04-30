"""Calibration de la replanification pour la verticale `mech_workshop`.

Le moteur generique (`src.core.replanification` + `src.core.soft_constraints`)
fournit le mecanisme de replanification (freeze, hint, stabilite tier-ponderee) ;
ce module fournit les **valeurs metier** specifiques a la sous-traitance
mecanique de precision.

Convention tier (1.5) :
- Tier 1 = critique (aero certifie, medical, donneur strategique avec
  penalites de retard contractuelles importantes)
- Tier 2 = standard sous-traitance (auto, sous-ensembles industriels)
- Tier 3 = opportuniste (petites series, depannage, prototypes sans
  contrainte d'engagement)

Justification des poids (a recalibrer apres pilotes design partners) :

- Tier 1 = 10× : un OF aero rate-deadline coute typiquement 10 a 20× plus
  cher en penalite que une bavure de planning sur du Tier 3. Le facteur 10
  est conservateur (10× du Tier 3) sans etre extreme.
- Tier 2 = 3× : zone moyenne. Auto/IATF a des engagements de delai mais
  rarement penalisants au point d'ecraser le reste.
- Tier 3 = 1× : reference, on accepte de bouger ces OF pour absorber les
  contraintes des superieurs.

→ "Deplacer un Tier 1 coute 10× plus qu'un Tier 3" (critere de sortie 1.5).

Compatibilite avec `Job.criticality` :
- Job.criticality = 1, 2 ou 3 (None = pas de tier assigne, poids defaut 1).
- Ce mapping est passe a `build_composite_soft_penalties(stability_tier_weights=...)`
  ou directement a `tier_weighted_stability_var(weight_per_tier=...)`.
"""

from __future__ import annotations

from typing import Final

MECH_TIER_WEIGHTS: Final[dict[int, int]] = {
    1: 10,  # Tier 1 — critique (aero, medical, donneur strategique)
    2: 3,   # Tier 2 — standard (auto, industriel)
    3: 1,   # Tier 3 — opportuniste (reference)
}
