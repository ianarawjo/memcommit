"""Ownership contracts for application-owned Impact route classification."""

from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
OWNER_MODULE = "memcommit.application.operations.impact.model"
ADAPTER_MODULE = "memcommit.adapters.console.commands.impact.registry"


def test_route_catalog_is_owned_by_the_impact_application_package() -> None:
    owner_path = (
        PACKAGE
        / "application"
        / "operations"
        / "impact"
        / "model.py"
    )
    adapter_path = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "impact"
        / "registry.py"
    )

    assert owner_path.is_file()
    assert adapter_path.is_file()
    assert importlib.import_module(OWNER_MODULE).__name__ == OWNER_MODULE
    assert importlib.import_module(ADAPTER_MODULE).__name__ == ADAPTER_MODULE


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


def test_impact_command_installs_the_application_catalog_through_its_adapter() -> None:
    source = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "impact"
        / "command.py"
    ).read_text(encoding="utf-8")

    assert "install_impact_routes" in source
    assert "IMPACT_ROUTES.install" not in source


def test_console_registry_does_not_restate_application_route_records() -> None:
    source = (
        PACKAGE
        / "adapters"
        / "console"
        / "commands"
        / "impact"
        / "registry.py"
    ).read_text(encoding="utf-8")

    assert "ImpactRoute(" not in source
    assert "from memcommit.application.operations.impact" in source
