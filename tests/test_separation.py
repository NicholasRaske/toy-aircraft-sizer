"""The aircraft must never depend on the workshop.

``aerosizer`` runs in a field on a Raspberry Pi with no network. ``tools``
runs on a development machine and may pull in AeroSandbox, CasADi, matplotlib
and anything else convenient.

That separation is a promise, and a promise nobody checks is a promise that
quietly breaks. One stray import is all it would take, and the failure would
not show up until an install on the target hardware.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_DIRECTORY = Path(__file__).parent.parent / "aerosizer"

# Everything the shipped package is allowed to import from outside itself.
PERMITTED_THIRD_PARTY: frozenset[str] = frozenset()

FORBIDDEN_AT_RUNTIME = ("aerosandbox", "casadi", "matplotlib", "numpy", "scipy", "tools")


def _imported_modules(source: Path) -> set[str]:
    """Top-level names imported by a module, however they are spelled."""
    imported = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def _package_sources() -> list[Path]:
    return sorted(PACKAGE_DIRECTORY.glob("*.py"))


def test_there_is_something_to_check():
    assert _package_sources(), "no package sources found to check"


@pytest.mark.parametrize("source", _package_sources(), ids=lambda path: path.name)
def test_the_shipped_package_imports_nothing_heavy(source):
    """No development dependency may reach the aircraft.

    AeroSandbox is a build-time tool. It generates data that ships as JSON;
    it must never be needed to read that data back.
    """
    offenders = _imported_modules(source) & set(FORBIDDEN_AT_RUNTIME)

    assert not offenders, f"{source.name} imports {sorted(offenders)}, which cannot ship"


@pytest.mark.parametrize("source", _package_sources(), ids=lambda path: path.name)
def test_the_shipped_package_uses_only_the_standard_library(source):
    """Stronger than the blocklist: nothing third-party at all, by default.

    If a runtime dependency ever becomes genuinely necessary, add it to
    PERMITTED_THIRD_PARTY deliberately -- and then vendor a wheel for it,
    because a Pi in a field cannot download one.
    """
    import sys

    imported = _imported_modules(source)
    third_party = {
        name
        for name in imported
        if name not in sys.stdlib_module_names
        and name != "aerosizer"
        and name not in PERMITTED_THIRD_PARTY
    }

    assert not third_party, f"{source.name} imports third-party {sorted(third_party)}"
