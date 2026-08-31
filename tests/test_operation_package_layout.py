"""Canonical flat physical layout for catalog-classified operations."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from memcommit.operation_catalog.families import OPERATION_FAMILY_BY_OPERATION


REPOSITORY = Path(__file__).resolve().parents[1]
APPLICATION = REPOSITORY / "src" / "memcommit" / "application" / "operations"
CONSOLE = REPOSITORY / "src" / "memcommit" / "adapters" / "console" / "commands"

OPERATION_PACKAGES = {
    "status": "status",
    "pwd": "pwd",
    "contexts": "contexts",
    "list": "list",
    "show": "show",
    "switch": "switch",
    "checkout": "checkout",
    "rename": "rename",
    "init": "init",
    "add": "add",
    "copy": "copy",
    "branch": "branch",
    "import": "resource_import",
    "reference": "reference",
    "embed": "embed",
    "find": "find",
    "search": "search",
    "query": "query",
    "summarize": "summarize",
    "compare": "compare",
    "edit": "edit",
    "move": "move",
    "replace": "replace",
    "chunk": "chunk",
    "delete": "delete",
    "clear": "clear",
    "merge": "merge",
    "update": "update",
    "atomize": "atomize",
    "distill": "distill",
    "elaborate": "elaborate",
    "makemore": "makemore",
    "forget": "forget",
    "sever": "sever",
    "meld": "meld",
    "translate": "translate",
    "find-duplicates": "find_duplicates",
    "find-redundancies": "find_redundancies",
    "find-ambiguities": "find_ambiguities",
    "find-conflicts": "find_conflicts",
    "audit": "audit",
    "dedup": "dedup",
    "dedun": "dedun",
    "resolve": "resolve",
    "fit": "fit",
    "check-conformance": "check_conformance",
    "impact": "impact",
    "review": "review",
    "ground": "ground",
    "log": "log",
    "diff": "diff",
    "trace": "trace",
    "rationale": "rationale",
    "checkpoint": "checkpoint",
    "undo": "undo",
    "redo": "redo",
    "revert": "revert",
    "profile": "profile",
    "share": "share",
    "lock": "lock",
    "unlock": "unlock",
    "help": "help",
    "provider": "provider",
    "config": "config",
    "init-study": "init_study",
    "eval": "eval",
}

FORMER_FAMILY_PACKAGES = {
    "browse_navigate",
    "create_copy_connect",
    "search_explain",
    "direct_changes",
    "semantic_updates",
    "translation",
    "quality_resolution",
    "operation_lifecycle",
    "ground_workbench",
    "history_recovery",
    "profiles",
    "sharing_protection",
    "system_study_tools",
}


def _module(root: str, package: str) -> str:
    return f"{root}.{package}"


def _root_packages(root: Path) -> set[str]:
    return {
        path.name
        for path in root.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }


def test_application_and_console_expose_one_flat_package_per_catalog_operation() -> None:
    assert set(OPERATION_PACKAGES) == set(OPERATION_FAMILY_BY_OPERATION)
    for package in OPERATION_PACKAGES.values():
        assert (APPLICATION / package / "__init__.py").is_file()
        assert (CONSOLE / package / "__init__.py").is_file()
        assert import_module(
            _module("memcommit.application.operations", package)
        ).__name__ == _module("memcommit.application.operations", package)
        assert import_module(
            _module("memcommit.adapters.console.commands", package)
        ).__name__ == _module("memcommit.adapters.console.commands", package)


def test_catalog_families_do_not_create_physical_operation_wrappers() -> None:
    packages = set(OPERATION_PACKAGES.values())
    assert _root_packages(APPLICATION) == packages
    # Remove remains a console compatibility spelling for Delete; it is not a
    # second catalog operation or an application package.
    assert _root_packages(CONSOLE) == packages | {"remove"}
    assert not (_root_packages(APPLICATION) & FORMER_FAMILY_PACKAGES)
    assert not (_root_packages(CONSOLE) & FORMER_FAMILY_PACKAGES)


def test_cross_operation_support_lives_outside_operation_roots() -> None:
    assert (
        REPOSITORY
        / "src/memcommit/application/capabilities/memory_transfer/application.py"
    ).is_file()
    assert (
        REPOSITORY
        / "src/memcommit/application/capabilities/save_context_from_selection/source_resolution.py"
    ).is_file()
    assert (
        REPOSITORY
        / "src/memcommit/adapters/console/terminal/components/retrieve_answer_save/save_panel.py"
    ).is_file()
    assert (
        REPOSITORY / "src/memcommit/adapters/console/diagnostics/dev/command.py"
    ).is_file()
    assert not (APPLICATION / "copy_and_move").exists()
    assert not (CONSOLE / "dev").exists()
