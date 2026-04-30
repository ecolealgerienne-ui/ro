"""Smoke tests pour valider l'infrastructure."""

import src


def test_package_importable() -> None:
    assert src.__version__ == "0.1.0"


def test_core_modules_importable() -> None:
    """Verifie que les modules cles de l'engine sont importables sans erreur."""
    from src.core import (  # noqa: F401
        circuit_breaker,
        clustering,
        mis,
        models,
        objectives,
        pattern,
        pipeline,
        replanification,
        scoring,
        simulation,
        soft_constraints,
        solver,
    )
