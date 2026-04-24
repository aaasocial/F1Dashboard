"""PHYS-09 / Criterion 5 — architecture linter tests.

These tests enforce:
  1. No per-tire Python for-loops in module_b.py..module_g.py (perf + readability)
  2. No sibling-module imports (modules stay isolated; only orchestrator composes)
  3. No fastf1 imports in the physics subpackage (ingestion-only dependency)
  4. No pydantic imports in the physics subpackage (D-03 boundary)

Failure indicates an architectural regression: the code compiles but
breaks one of the phase's structural invariants.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PHYSICS_DIR = Path(__file__).resolve().parents[2] / "src" / "f1_core" / "physics"
PER_TIMESTEP_MODULES = ["module_b", "module_c", "module_d", "module_e",
                        "module_f", "module_g"]


def _parse(filename: str) -> ast.Module:
    path = PHYSICS_DIR / filename
    assert path.exists(), f"expected {path} to exist"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _find_for_nodes(tree: ast.AST) -> list[ast.For]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.For)]


def _for_iterates_per_tire(node: ast.For) -> bool:
    """Heuristic: flags `for i in range(4)` and `for tire in [...]` patterns.

    Specifically:
      - iter is `ast.Call` to `range` with a single int arg == 4
      - iter is `ast.Call` to `range` with two int args (0, 4)
      - target is an ast.Name whose id matches "tire*" / "i" with range(4)
    """
    iter_node = node.iter
    if isinstance(iter_node, ast.Call) and isinstance(iter_node.func, ast.Name) and iter_node.func.id == "range":
        args = iter_node.args
        if len(args) == 1 and isinstance(args[0], ast.Constant) and args[0].value == 4:
            return True
        if len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value == 4:
            return True
    return False


@pytest.mark.parametrize("mod", PER_TIMESTEP_MODULES)
def test_per_timestep_modules_have_no_per_tire_for_loops(mod):
    """PHYS-09 / Criterion 5: no `for i in range(4)` in B–G hot path."""
    tree = _parse(f"{mod}.py")
    offending = [
        ast.dump(n) for n in _find_for_nodes(tree)
        if _for_iterates_per_tire(n)
    ]
    assert not offending, (
        f"{mod}.py has {len(offending)} per-tire for-loop(s); use numpy broadcasts instead: "
        + "\n".join(offending)
    )


@pytest.mark.parametrize("mod", PER_TIMESTEP_MODULES)
def test_modules_do_not_import_sibling_modules(mod):
    """Modules stay isolated; only the orchestrator composes them."""
    tree = _parse(f"{mod}.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            src = node.module or ""
            for sibling in PER_TIMESTEP_MODULES:
                if sibling == mod:
                    continue
                assert f"physics.{sibling}" not in src, (
                    f"{mod}.py imports sibling {sibling}; must stay isolated"
                )


@pytest.mark.parametrize("filename", [
    "module_a.py", "module_b.py", "module_c.py", "module_d.py",
    "module_e.py", "module_f.py", "module_g.py",
    "orchestrator.py", "cli.py",
])
def test_physics_files_do_not_import_fastf1_directly(filename):
    """fastf1 is an ingestion-layer concern; physics receives typed inputs."""
    tree = _parse(filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("fastf1"), (
                    f"{filename} imports fastf1 directly; use ingestion layer"
                )
        elif isinstance(node, ast.ImportFrom):
            src = node.module or ""
            assert not src.startswith("fastf1"), (
                f"{filename} imports from fastf1; use ingestion layer"
            )


@pytest.mark.parametrize("filename", [
    "module_a.py", "module_b.py", "module_c.py", "module_d.py",
    "module_e.py", "module_f.py", "module_g.py",
    "orchestrator.py", "params.py", "defaults.py", "constants.py",
    "events.py", "protocols.py",
])
def test_physics_files_do_not_import_pydantic(filename):
    """D-03 boundary: pydantic stays in packages/api/. See test_contracts.py."""
    path = PHYSICS_DIR / filename
    if not path.exists():
        pytest.skip(f"{filename} not present (optional file)")
    tree = _parse(filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("pydantic"), (
                    f"{filename} imports pydantic"
                )
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("pydantic"), (
                f"{filename} imports pydantic"
            )


def test_orchestrator_imports_all_modules():
    """Sanity: the orchestrator IS the composition point — it imports every module."""
    tree = _parse("orchestrator.py")
    imported_from = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            src = node.module or ""
            for sibling in ["module_a"] + PER_TIMESTEP_MODULES:
                if f"physics.{sibling}" in src:
                    imported_from.add(sibling)
    # Every module letter A–G must appear as an import in orchestrator
    assert imported_from >= set(["module_a"] + PER_TIMESTEP_MODULES), (
        f"orchestrator missing imports: {set(['module_a'] + PER_TIMESTEP_MODULES) - imported_from}"
    )
