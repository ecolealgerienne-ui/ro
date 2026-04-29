"""Parser pour les instances JSSP du benchmark Taillard.

Format JSPLIB (https://github.com/tamy0612/JSPLIB) :

    +++++++++++++++++++++++++++++
    instance ta01
    +++++++++++++++++++++++++++++
    Taillard 15x15 instance 1 (Table 4, instance 1) ...
    15 15
     1 94 5 66 4 10 7 53 ...        <- job 0 : machine duration ×n_machines
     ...

Les machines sont 1-indexées dans le fichier source ; le parser normalise
à 0-indexé en interne.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.core.models import Job, Machine, Operation, WorkshopInstance

_logger = logging.getLogger(__name__)


def parse_taillard_file(path: Path) -> WorkshopInstance:
    """Parse un fichier Taillard au format JSPLIB.

    Args:
        path: Chemin vers le fichier (ex: `data/taillard/ta01`).

    Returns:
        Une `WorkshopInstance` sans `best_known_makespan` ni métadonnées
        (à enrichir via `attach_metadata`).

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ValueError: Si le format est invalide (dimensions, lignes manquantes,
            valeurs incohérentes).
    """
    if not path.exists():
        raise FileNotFoundError(f"Fichier Taillard introuvable : {path}")

    raw_lines = path.read_text(encoding="utf-8").splitlines()
    cleaned = [line.strip() for line in raw_lines if line.strip() and not line.strip().startswith("+")]

    if not cleaned:
        raise ValueError(f"Fichier vide ou uniquement des en-têtes : {path}")

    dims_idx = _find_dimensions_line(cleaned)
    n_jobs, n_machines = (int(x) for x in cleaned[dims_idx].split())

    expected_lines = dims_idx + 1 + n_jobs
    if len(cleaned) < expected_lines:
        raise ValueError(
            f"{path} : {n_jobs} jobs attendus mais seulement "
            f"{len(cleaned) - dims_idx - 1} lignes de données disponibles"
        )

    job_rows = cleaned[dims_idx + 1 : dims_idx + 1 + n_jobs]
    machine_offset = _detect_machine_indexing(job_rows, n_machines)

    jobs = [
        _parse_job_row(j, row, n_machines, machine_offset, source=path.name)
        for j, row in enumerate(job_rows)
    ]
    machines = [Machine(machine_id=m, name=f"M{m}") for m in range(n_machines)]

    return WorkshopInstance(
        name=path.stem,
        jobs=jobs,
        machines=machines,
        best_known_makespan=None,
        metadata={"source": "JSPLIB", "format": "taillard"},
    )


def _find_dimensions_line(lines: list[str]) -> int:
    """Localise la ligne `n_jobs n_machines`.

    Heuristique : première ligne contenant exactement deux entiers positifs
    raisonnables (≤ 1000 chacun).
    """
    for i, line in enumerate(lines):
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            a, b = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if 1 <= a <= 1000 and 1 <= b <= 1000:
            return i
    raise ValueError("Ligne de dimensions (n_jobs n_machines) introuvable")


def _detect_machine_indexing(job_rows: list[str], n_machines: int) -> int:
    """Détecte si les machines sont 0- ou 1-indexées dans le fichier.

    Returns:
        0 si 0-indexées, 1 si 1-indexées.

    Raises:
        ValueError: Si l'indexing est ambigu ou hors borne.
    """
    machine_indices: set[int] = set()
    for row in job_rows:
        values = list(map(int, row.split()))
        for k in range(0, len(values), 2):
            machine_indices.add(values[k])

    if not machine_indices:
        raise ValueError("Aucune valeur de machine trouvée dans les jobs")

    min_idx, max_idx = min(machine_indices), max(machine_indices)

    if min_idx == 1 and max_idx == n_machines:
        return 1
    if min_idx == 0 and max_idx == n_machines - 1:
        return 0
    raise ValueError(
        f"Indexing machines ambigu : min={min_idx}, max={max_idx}, n_machines={n_machines}"
    )


def _parse_job_row(
    job_id: int,
    row: str,
    n_machines: int,
    machine_offset: int,
    *,
    source: str,
) -> Job:
    """Parse une ligne de job (machine duration × n_machines)."""
    values = list(map(int, row.split()))
    if len(values) != 2 * n_machines:
        raise ValueError(
            f"{source}: job {job_id} : {len(values)} valeurs trouvées, "
            f"{2 * n_machines} attendues ({n_machines} paires machine/duration)"
        )
    operations = [
        Operation(
            job_id=job_id,
            sequence_idx=op_idx,
            machine_id=values[2 * op_idx] - machine_offset,
            duration=values[2 * op_idx + 1],
        )
        for op_idx in range(n_machines)
    ]
    return Job(job_id=job_id, operations=operations)


def load_metadata(csv_path: Path) -> dict[str, dict[str, str]]:
    """Charge le fichier `instances_metadata.csv`.

    Format attendu :
        name,n_jobs,n_machines,best_known_makespan,source_optimum

    Returns:
        Dict indexé par nom d'instance (ex: "ta01"), valeurs = autres colonnes
        en strings (à caster côté appelant).
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Métadonnées introuvables : {csv_path}")

    metadata: dict[str, dict[str, str]] = {}
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue
            metadata[name] = {k: v.strip() for k, v in row.items() if k}
    return metadata


def load_taillard_instance(name: str, data_dir: Path) -> WorkshopInstance:
    """Charge une instance Taillard avec ses métadonnées.

    Args:
        name: Nom de l'instance (ex: "ta01"). Cherche `data_dir/<name>` et
            `data_dir/instances_metadata.csv`.
        data_dir: Répertoire `data/taillard/`.

    Returns:
        `WorkshopInstance` enrichie de `best_known_makespan` si dispo.
    """
    instance_path = data_dir / name
    if not instance_path.exists():
        # Tolère l'extension .txt
        candidate = data_dir / f"{name}.txt"
        if candidate.exists():
            instance_path = candidate
        else:
            raise FileNotFoundError(
                f"Instance '{name}' introuvable dans {data_dir} (essayé {name} et {name}.txt)"
            )

    instance = parse_taillard_file(instance_path)

    metadata_path = data_dir / "instances_metadata.csv"
    if metadata_path.exists():
        all_meta = load_metadata(metadata_path)
        if name in all_meta:
            row = all_meta[name]
            best_known_str = row.get("best_known_makespan", "").strip()
            best_known = int(best_known_str) if best_known_str else None
            enriched_metadata = {**instance.metadata, **{k: v for k, v in row.items() if k != "name"}}
            return instance.model_copy(
                update={"best_known_makespan": best_known, "metadata": enriched_metadata}
            )
        _logger.warning("Aucune métadonnée trouvée pour %s dans %s", name, metadata_path)

    return instance
