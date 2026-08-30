"""Ownership and composition contracts for operation persistence."""

from __future__ import annotations

import ast
from pathlib import Path

import memcommit.persistence.store as store_module
from memcommit.persistence.operations.atomize import state_repository as atomize
from memcommit.persistence.operations.meld import state_repository as meld
from memcommit.persistence.operations.review import state_repository as review
from memcommit.persistence.operations.update import state_repository as update
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.context_memory import current
from memcommit.persistence.store.infrastructure import atomic_io


REPOSITORY_ROOT = Path(__file__).parents[1]
STORE_ROOT = REPOSITORY_ROOT / "src/memcommit/persistence/store"
OPERATIONS_ROOT = REPOSITORY_ROOT / "src/memcommit/persistence/operations"
INFRASTRUCTURE_ROOT = STORE_ROOT / "infrastructure"

EXPECTED_METHODS = {
    "store/infrastructure/paths.py": {
        "__init__",
        "store_dir",
        "contexts_dir",
        "state_file",
        "query_sources_dir",
        "impact_plan_file",
        "staged_update_file",
        "review_session_file",
        "review_session_history_dir",
        "review_session_sources_dir",
        "command_context_archives_dir",
        "atomize_analyses_dir",
        "atomize_workbenches_dir",
        "atomize_session_history_dir",
        "meld_sessions_dir",
        "meld_session_history_dir",
        "meld_resolution_branches_dir",
        "meld_choice_branches_dir",
    },
    "store/infrastructure/protection.py": {
        "write_protection_registry",
        "write_protection_state",
        "profile_write_guard",
        "_assert_profile_write_allowed",
        "_protected_context_message",
        "_protected_memory_message",
        "_assert_context_record_change_allowed",
        "_assert_context_deletion_allowed",
        "_revalidate_protection_target",
        "set_context_write_protection",
        "set_context_namespace_write_protection",
        "set_profile_write_protection",
        "set_memory_write_protection",
    },
    "store/infrastructure/locking.py": {
        "_context_graph_lock",
        "_context_write_lock",
        "_context_write_locks",
        "_command_write_lock",
        "_state_write_lock",
        "_update_session_write_lock",
        "_atomize_session_write_lock",
        "_meld_resolution_branch_write_lock",
    },
    "store/context_memory/current.py": {
        "_read_state",
        "_write_state",
        "current_context_name",
        "context_navigation_target",
        "set_current",
        "set_current_context_if",
        "set_current_virtual_context_if",
    },
    "operations/update/state_repository.py": {
        "_load_update_session",
        "_save_update_session",
        "load_impact_plan",
        "save_impact_plan",
        "load_staged_update",
        "save_staged_update",
        "_save_active_terminal_update",
        "apply_staged_update",
        "_apply_staged_update_command_locked",
    },
    "operations/review/state_repository.py": {
        "_load_review_session",
        "load_review_session",
        "_review_session_history_path",
        "_review_session_source_path",
        "load_review_session_source",
        "_retain_review_session_source",
        "load_review_session_history",
        "list_review_sessions",
        "load_review_session_by_uid",
        "save_review_session",
    },
    "operations/meld/state_repository.py": {
        "_meld_choice_branches_path",
        "load_meld_choice_branches",
        "save_meld_choice_branches",
        "_meld_resolution_branch_path",
        "load_meld_resolution_branch",
        "save_meld_resolution_branch",
        "_meld_session_path",
        "_meld_session_history_path",
        "_archive_meld_session_locked",
        "load_meld_session_history",
        "list_meld_session_history",
        "load_meld_session",
        "save_meld_session",
        "create_meld_target_with_session",
        "delete_meld_session",
    },
    "operations/atomize/state_repository.py": {
        "_atomize_analysis_path",
        "load_atomize_analysis",
        "save_atomize_analysis",
        "_save_atomize_analysis_locked",
        "delete_atomize_analysis",
        "_atomize_workbench_path",
        "load_atomize_workbench",
        "save_atomize_workbench",
        "_save_atomize_workbench_locked",
        "delete_atomize_workbench",
        "_atomize_session_history_path",
        "archive_atomize_session",
        "delete_atomize_session_history",
        "load_atomize_session_history",
        "list_atomize_session_history",
    },
}


def _mixin_methods(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for class_node in tree.body
        if isinstance(class_node, ast.ClassDef) and class_node.name.endswith("Mixin")
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_operation_persistence_methods_have_one_focused_owner() -> None:
    assert not (STORE_ROOT / "operation_state").exists()
    paths = (
        tuple(
            path
            for path in INFRASTRUCTURE_ROOT.glob("*.py")
            if path.name not in {"__init__.py", "atomic_io.py"}
        )
        + (STORE_ROOT / "context_memory/current.py",)
        + tuple(OPERATIONS_ROOT.glob("*/state_repository.py"))
    )
    actual = {
        str(path.relative_to(REPOSITORY_ROOT / "src/memcommit/persistence")): (
            _mixin_methods(path)
        )
        for path in paths
    }
    assert actual == EXPECTED_METHODS
    all_methods = [method for methods in actual.values() for method in methods]
    assert len(all_methods) == len(set(all_methods)) == 95


def test_memory_store_composes_operation_repositories_in_dependency_order() -> None:
    assert tuple(
        base.__module__.rsplit(".", 1)[-1] for base in MemoryStore.__bases__
    ) == (
        "paths",
        "protection",
        "locking",
        "context_memory",
        "state_repository",
        "state_repository",
        "state_repository",
        "state_repository",
        "record_restore_checkpoint",
    )


def test_context_persistence_does_not_depend_on_operation_repositories() -> None:
    paths = (
        tuple((STORE_ROOT / "context_memory").glob("*.py"))
        + tuple((STORE_ROOT / "checkpoint").rglob("*.py"))
        + tuple((STORE_ROOT / "command_restoration").rglob("*.py"))
        + (STORE_ROOT / "record_restore_checkpoint.py",)
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "persistence.operations" not in source


def test_store_atomic_write_override_reaches_operation_modules(monkeypatch) -> None:
    marker = object()
    monkeypatch.setattr(store_module, "_write_json_atomic", marker)

    assert atomic_io._write_json_atomic is marker
    assert atomize._write_json_atomic is marker
    assert current._write_json_atomic is marker
    assert meld._write_json_atomic is marker
    assert review._write_json_atomic is marker
    assert update._write_json_atomic is marker
