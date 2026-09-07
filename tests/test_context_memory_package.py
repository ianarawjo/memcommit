"""Ownership and compatibility contracts for Context/Memory persistence."""

from __future__ import annotations

import ast
from pathlib import Path

import memcommit.persistence.store as store_module
from memcommit.persistence.store.context_memory import ContextMemoryStoreMixin
from memcommit.persistence.store.context_memory import (
    creation,
    lifecycle,
    rename,
    saving,
)


REPOSITORY_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src/memcommit/persistence/store/context_memory"

EXPECTED_METHODS = {
    "catalog_model.py": set(),
    "checkpoint_frame_mapping.py": set(),
    "current.py": {
        "_read_state",
        "_write_state",
        "current_context_name",
        "context_navigation_target",
        "set_current",
        "set_current_context_if",
        "set_current_virtual_context_if",
    },
    "models.py": set(),
    "records.py": set(),
    "addressing.py": {
        "_assert_context_storage_root",
        "_context_dir",
        "_context_file",
        "_checkpoints_dir",
    },
    "catalog_scan.py": {
        "_catalog_diagnostic",
        "_scan_context_record_paths",
        "scan_context_catalog",
        "list_context_names",
    },
    "context_creation_availability.py": {
        "context_exists",
        "_assert_context_storage_available",
        "assert_context_creatable",
    },
    "loading.py": {
        "_load_direct_memory",
        "load",
        "load_without_attached_reads",
        "load_direct",
        "load_for_update",
        "load_current",
        "load_current_direct",
        "_read_direct_context_records_strict",
        "load_direct_context_graph_strict",
        "locked_context_snapshot",
        "locked_context_snapshots",
    },
    "rename.py": {
        "_read_context_graph_for_rename",
        "_assert_rename_destination_available",
        "_context_graph_digest_for_rename",
        "_read_translation_records_for_rename",
        "_read_meld_records_for_rename",
        "_prepare_context_rename_locked",
        "_rename_lock_names",
        "plan_context_rename",
        "_commit_context_rename_locked",
        "rename_contexts",
        "_rename_contexts_command_locked",
    },
    "saving.py": {
        "save",
        "_save_command_locked",
        "save_context_command_batch",
        "save_meld_target",
        "_save_meld_target_command_locked",
        "save_context_with_sources",
        "_assert_source_bindings_locked",
        "_save_locked",
    },
    "creation.py": {
        "create_context",
        "create_context_with_sources",
        "create_branch_context",
        "create_branch_contexts",
        "create_missing_contexts",
        "_create_missing_contexts_command_locked",
    },
    "lifecycle.py": {
        "_prune_empty_namespace_dirs",
        "_context_lifecycle_events_dir",
        "_ensure_context_lifecycle_events_dir",
        "_context_lifecycle_ledger_lock",
        "_write_context_lifecycle_event",
        "_remove_context_lifecycle_event",
        "list_context_lifecycle_events",
        "_context_deletion_event_locked",
        "delete",
        "delete_context_if",
        "_delete_locked",
    },
    "lifecycle_model.py": set(),
    "query_source.py": {
        "_canonical_query_source_uid",
        "_query_source_dir",
        "_query_source_file",
        "create_query_source",
        "create_bilingual_query_source",
        "load_query_source",
        "delete_query_source",
    },
}


def _class_methods(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for class_node in tree.body
        if isinstance(class_node, ast.ClassDef) and class_node.name.endswith("Mixin")
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_context_memory_methods_have_one_focused_owner() -> None:
    assert not PACKAGE_ROOT.with_suffix(".py").exists()
    actual = {
        path.name: _class_methods(path)
        for path in PACKAGE_ROOT.glob("*.py")
        if path.name != "__init__.py"
    }
    assert actual == EXPECTED_METHODS
    all_methods = [method for methods in actual.values() for method in methods]
    assert len(all_methods) == len(set(all_methods)) == 72


def test_context_memory_surface_composes_the_focused_mixins() -> None:
    assert tuple(
        base.__module__.rsplit(".", 1)[-1] for base in ContextMemoryStoreMixin.__bases__
    ) == (
        "current",
        "addressing",
        "catalog_scan",
        "context_creation_availability",
        "loading",
        "rename",
        "saving",
        "creation",
        "lifecycle",
        "query_source",
    )


def test_store_atomic_write_overrides_reach_defining_modules(monkeypatch) -> None:
    json_marker = object()
    bytes_marker = object()
    fsync_marker = object()
    monkeypatch.setattr(store_module, "_write_json_atomic", json_marker)
    monkeypatch.setattr(store_module, "_write_bytes_atomic", bytes_marker)
    monkeypatch.setattr(store_module, "_fsync_directory", fsync_marker)

    assert creation._write_json_atomic is json_marker
    assert lifecycle._write_json_atomic is json_marker
    assert rename._write_json_atomic is json_marker
    assert saving._write_json_atomic is json_marker
    assert creation._write_bytes_atomic is bytes_marker
    assert rename._write_bytes_atomic is bytes_marker
    assert lifecycle._fsync_directory is fsync_marker
