"""Canonical physical layout for catalog-classified operation packages."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
APPLICATION = REPOSITORY / "src" / "memcommit" / "application" / "operations"
CONSOLE = REPOSITORY / "src" / "memcommit" / "adapters" / "console" / "commands"

OPERATION_PATHS = {
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
    "log": "history_recovery/inspection/log",
    "diff": "history_recovery/inspection/diff",
    "trace": "history_recovery/inspection/trace",
    "rationale": "history_recovery/inspection/rationale",
    "checkpoint": "history_recovery/recovery/checkpoint",
    "undo": "history_recovery/recovery/undo",
    "redo": "history_recovery/recovery/redo",
    "revert": "history_recovery/recovery/revert",
}

FORMER_APPLICATION_PACKAGES = {
    operation.replace("-", "_")
    for operation in OPERATION_PATHS
    if operation != "impact"
}
FORMER_APPLICATION_PACKAGES.remove("check_conformance")
FORMER_APPLICATION_PACKAGES.add("conformance")


def _module(root: str, relative: str) -> str:
    return root + "." + relative.replace("/", ".")


def test_application_and_console_share_the_catalog_family_topology() -> None:
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
    for package in FORMER_APPLICATION_PACKAGES:
        assert not (APPLICATION / package).exists()
    for operation in OPERATION_PATHS:
        assert not (CONSOLE / operation.replace("-", "_")).exists()
    assert (CONSOLE / "direct_changes" / "remove" / "__init__.py").is_file()
    assert not (CONSOLE / "remove").exists()
