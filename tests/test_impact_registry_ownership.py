"""Ownership contracts for the command-owned Impact route registry."""

from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
OWNER_MODULE = "memcommit.adapters.console.commands.impact.registry"


def test_registry_is_owned_only_by_the_impact_command_package() -> None:
    owner_path = (
        PACKAGE / "adapters" / "console" / "commands" / "impact" / "registry.py"
    )
    retired_path = PACKAGE / "adapters" / "interfaces" / "cli" / "impact_registry.py"

    assert owner_path.is_file()
    assert not retired_path.exists()
    assert importlib.import_module(OWNER_MODULE).__name__ == OWNER_MODULE


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
            "Preview one append-only same-UID Memory revision.",
        ),
        (
            "makemore",
            "PREPARE_PROCESS_LOCAL",
            "Preview the unverified Memories Makemore would add.",
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


def test_impact_command_imports_its_sibling_registry() -> None:
    source = (
        PACKAGE / "adapters" / "console" / "commands" / "impact" / "command.py"
    ).read_text(encoding="utf-8")

    assert (
        "from memcommit.adapters.console.commands.impact.registry import IMPACT_ROUTES"
        in source
    )
    assert "memcommit.adapters.interfaces.cli.impact_registry" not in source


def test_production_code_does_not_reference_the_retired_interface_path() -> None:
    references = []
    for path in (PACKAGE / "adapters").rglob("*.py"):
        if "memcommit.adapters.interfaces.cli.impact_registry" in path.read_text(
            encoding="utf-8"
        ):
            references.append(path.relative_to(ROOT).as_posix())

    assert references == []
