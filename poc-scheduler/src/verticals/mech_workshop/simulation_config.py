"""Calibration de la simulation operationnelle pour la verticale `mech_workshop`.

Le moteur generique (`src.core.simulation`) calcule des metriques universelles ;
ce module fournit les **seuils metier** specifiques a la sous-traitance
mecanique de precision.

Justification des seuils (a recalibrer apres pilotes design partners) :

- `micro_pause_threshold = 5` : en sous-traitance meca, une pause < 5 min
  entre deux operations sur la meme machine est consideree comme du temps
  de basculement non-productif (l'operateur ne peut rien faire d'utile).
  Au-dela de 5 min, c'est une vraie pause exploitable.

- `max_setup_ratio = 0.30` : seuil WARN. Au-dela de 30 % de setup sur une
  machine, l'utilisation reelle est probablement decevante : signale qu'il
  faudrait regrouper les pieces de meme famille.

- `reject_setup_ratio = 0.50` : seuil REJECT. Plus de la moitie du temps
  passe en setup -> planning non viable, le solveur a probablement loupe
  un regroupement evident.

- `max_micro_pauses_per_machine = 3` : tolerance pour quelques pauses
  techniques (changement d'outil, controle qualite). Au-dela, fragmentation
  excessive du planning machine.

- `max_job_fragmentation = 0.30` : un OF (= 1 piece) ne devrait pas passer
  plus de 30 % de son span en attente entre operations. Au-dela, on a un
  risque qualite (refroidissement, oxydation, traçabilite).

Tous en entiers / float. Les unites de temps sont coherentes avec celles
du `WorkshopInstance` (typiquement minutes pour la meca).
"""

from __future__ import annotations

from typing import Final

MECH_SIMULATION_THRESHOLDS: Final[dict[str, float]] = {
    "micro_pause_threshold": 5,
    "max_setup_ratio": 0.30,
    "reject_setup_ratio": 0.50,
    "max_micro_pauses_per_machine": 3,
    "max_job_fragmentation": 0.30,
}
