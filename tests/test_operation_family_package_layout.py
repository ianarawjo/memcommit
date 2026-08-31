"""Canonical physical layout for catalog-classified operation packages."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from memcommit.operation_catalog.families import OPERATION_FAMILY_BY_OPERATION


REPOSITORY = Path(__file__).resolve().parents[1]
APPLICATION = REPOSITORY / "src" / "memcommit" / "application" / "operations"
CONSOLE = REPOSITORY / "src" / "memcommit" / "adapters" / "console" / "commands"

OPERATION_PATHS = {
    "status": "browse_navigate/status",
    "pwd": "browse_navigate/pwd",
    "contexts": "browse_navigate/contexts",
    "list": "browse_navigate/list",
    "show": "browse_navigate/show",
    "switch": "browse_navigate/switch",
    "checkout": "browse_navigate/checkout",
    "rename": "browse_navigate/rename",
    "init": "create_copy_connect/init",
    "add": "create_copy_connect/add",
    "copy": "create_copy_connect/copy",
    "branch": "create_copy_connect/branch",
    "import": "create_copy_connect/resource_import",
    "reference": "create_copy_connect/reference",
    "embed": "create_copy_connect/embed",
    "find": "search_explain/retrieve_answer/find",
    "search": "search_explain/retrieve_answer/search",
    "query": "search_explain/retrieve_answer/query",
    "summarize": "search_explain/synthesize/summarize",
    "compare": "search_explain/synthesize/compare",
    "edit": "direct_changes/edit",
    "move": "direct_changes/move",
    "replace": "direct_changes/replace",
    "chunk": "direct_changes/chunk",
    "delete": "direct_changes/delete",
    "clear": "direct_changes/clear",
    "merge": "direct_changes/merge",
    "update": "semantic_updates/foundation/update",
    "atomize": "semantic_updates/derive/atomize",
    "distill": "semantic_updates/derive/distill",
    "elaborate": "semantic_updates/derive/elaborate",
    "makemore": "semantic_updates/derive/makemore",
    "forget": "semantic_updates/curate_integrate/forget",
    "sever": "semantic_updates/curate_integrate/sever",
    "meld": "semantic_updates/curate_integrate/meld",
    "translate": "translation/translate",
    "find-duplicates": "quality_resolution/diagnose/find_duplicates",
    "find-redundancies": "quality_resolution/diagnose/find_redundancies",
    "find-ambiguities": "quality_resolution/diagnose/find_ambiguities",
    "find-conflicts": "quality_resolution/diagnose/find_conflicts",
    "audit": "quality_resolution/diagnose/audit",
    "dedup": "quality_resolution/repair/dedup",
    "dedun": "quality_resolution/repair/dedun",
    "resolve": "quality_resolution/repair/resolve",
    "fit": "quality_resolution/validate/fit",
    "check-conformance": "quality_resolution/validate/check_conformance",
    "impact": "operation_lifecycle/impact",
    "review": "operation_lifecycle/review",
    "ground": "ground_workbench/ground",
    "log": "history_recovery/inspection/log",
    "diff": "history_recovery/inspection/diff",
    "trace": "history_recovery/inspection/trace",
    "rationale": "history_recovery/inspection/rationale",
    "checkpoint": "history_recovery/recovery/checkpoint",
    "undo": "history_recovery/recovery/undo",
    "redo": "history_recovery/recovery/redo",
    "revert": "history_recovery/recovery/revert",
    "profile": "profiles/profile",
    "share": "sharing_protection/share",
    "lock": "sharing_protection/lock",
    "unlock": "sharing_protection/unlock",
    "help": "system_study_tools/help",
    "provider": "system_study_tools/provider",
    "config": "system_study_tools/config",
    "init-study": "system_study_tools/init_study",
    "eval": "system_study_tools/eval",
}

FAMILY_PACKAGES = {
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


def _module(root: str, relative: str) -> str:
    return root + "." + relative.replace("/", ".")


def test_application_and_console_share_the_catalog_family_topology() -> None:
    assert set(OPERATION_PATHS) == set(OPERATION_FAMILY_BY_OPERATION)
    for relative in OPERATION_PATHS.values():
        assert (APPLICATION / relative / "__init__.py").is_file()
        assert (CONSOLE / relative / "__init__.py").is_file()
        assert import_module(
            _module("memcommit.application.operations", relative)
        ).__name__ == _module("memcommit.application.operations", relative)
        assert import_module(
            _module("memcommit.adapters.console.commands", relative)
        ).__name__ == _module("memcommit.adapters.console.commands", relative)


def test_moved_flat_operation_packages_are_absent() -> None:
    application_packages = {
        path.name
        for path in APPLICATION.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    console_packages = {
        path.name
        for path in CONSOLE.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert application_packages == FAMILY_PACKAGES
    assert console_packages == FAMILY_PACKAGES
    assert (CONSOLE / "direct_changes" / "remove" / "__init__.py").is_file()


def test_cross_family_and_non_operation_support_lives_outside_operation_roots() -> None:
    assert (
        REPOSITORY
        / "src/memcommit/application/capabilities/memory_transfer/application.py"
    ).is_file()
    assert (
        REPOSITORY / "src/memcommit/adapters/console/diagnostics/dev/command.py"
    ).is_file()
    assert not (APPLICATION / "copy_and_move").exists()
    assert not (APPLICATION / "resource_import").exists()
    assert not (CONSOLE / "dev").exists()
