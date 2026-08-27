"""Ownership contracts for the interface-owned Impact route registry."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
LEGACY_MODULE = "memcommit.adapters.console.commands.impact.registry"
OWNER_MODULE = "memcommit.adapters.interfaces.cli.impact_registry"


@pytest.mark.parametrize(
    "first,second",
    ((LEGACY_MODULE, OWNER_MODULE), (OWNER_MODULE, LEGACY_MODULE)),
)
def test_legacy_and_owner_imports_share_module_and_objects_in_either_order(
    first: str,
    second: str,
) -> None:
    program = (
        "import importlib\n"
        f"first = importlib.import_module({first!r})\n"
        f"second = importlib.import_module({second!r})\n"
        "assert first is second\n"
        "for name in second.__all__:\n"
        "    assert getattr(first, name) is getattr(second, name)\n"
        "assert first.IMPACT_ROUTES is second.IMPACT_ROUTES\n"
    )

    subprocess.run([sys.executable, "-c", program], cwd=ROOT, check=True)


def test_legacy_path_is_the_owner_module_object() -> None:
    legacy = importlib.import_module(LEGACY_MODULE)
    owner = importlib.import_module(OWNER_MODULE)

    assert legacy is owner
    assert legacy.IMPACT_ROUTES is owner.IMPACT_ROUTES
    assert legacy.ImpactLifecycle is owner.ImpactLifecycle
    assert legacy.ImpactRoute is owner.ImpactRoute
    assert legacy.ImpactRouteRegistry is owner.ImpactRouteRegistry


def test_route_order_lifecycle_and_help_are_unchanged() -> None:
    registry = importlib.import_module(OWNER_MODULE)

    assert tuple(
        (route.name, route.lifecycle.value, route.help)
        for route in registry.IMPACT_ROUTES.routes
    ) == (
        (
            "atomize",
            "PREPARE_DURABLE",
            "Preview or reopen one Context's saved Atomize analysis.",
        ),
        (
            "forget",
            "PREPARE_PROCESS_LOCAL",
            "Preview complete in-place Forget decisions without applying them.",
        ),
        (
            "distill",
            "PREPARE_PROCESS_LOCAL",
            "Preview the Rules Distill would add to an existing Target.",
        ),
        (
            "elaborate",
            "PREPARE_PROCESS_LOCAL",
            "Preview the unverified Memories Elaborate would add.",
        ),
        (
            "resolve",
            "PREPARE_PROCESS_LOCAL",
            "Preview one exact verified Resolve candidate without applying it.",
        ),
        (
            "meld",
            "OPEN_SAVED",
            "Inspect one saved Meld assessment.",
        ),
        (
            "sever",
            "OPEN_SAVED",
            "Inspect one saved Sever result.",
        ),
        (
            "update",
            "PREPARE_OR_OPEN",
            "Preview a directional Update or inspect one saved Update plan.",
        ),
    )


def test_legacy_facade_contains_no_implementation() -> None:
    path = PACKAGE / "commands" / "impact" / "registry.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "sys"
            and target.value.attr == "modules"
            for target in node.targets
        )
        for node in tree.body
    )


def test_impact_command_imports_the_interface_owner() -> None:
    source = (PACKAGE / "commands" / "impact" / "command.py").read_text(
        encoding="utf-8"
    )

    assert (
        "from memcommit.adapters.interfaces.cli.impact_registry import IMPACT_ROUTES" in source
    )
    assert "from memcommit.adapters.console.commands.impact.registry import IMPACT_ROUTES" not in source
