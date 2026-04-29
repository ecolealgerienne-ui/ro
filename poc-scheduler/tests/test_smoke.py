"""Smoke tests pour valider l'infrastructure."""

import src


def test_package_importable() -> None:
    assert src.__version__ == "0.1.0"


def test_pytest_wired_up() -> None:
    assert 1 + 1 == 2
