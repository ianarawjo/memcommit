"""Ownership and compatibility contracts for checkpoint and command restoration."""

from __future__ import annotations

import ast
from pathlib import Path

import memcommit.persistence.store as store_module
from memcommit.persistence.store.checkpoint import CheckpointStoreMixin
from memcommit.persistence.store.checkpoint import repository, revert
from memcommit.persistence.store.command_restoration import (
    CommandRestorationStoreMixin,
)
from memcommit.persistence.store.command_restoration import engine
from memcommit.persistence.store.command_restoration.handlers import (
    atomize,
    branch,
    merge,
    sever,
)
from memcommit.persistence.store.record_restore_checkpoint import (
    RecordRestoreCheckpointStoreMixin,
)


REPOSITORY_ROOT = Path(__file__).parents[1]
STORE_ROOT = REPOSITORY_ROOT / "src/memcommit/persistence/store"

EXPECTED_METHODS = {
    "checkpoint/repository.py": {
        "checkpoint",
        "checkpoint_context_batch",
        "_checkpoint_locked",
        "list_checkpoints",
        "_remove_checkpoint_uid_locked",
    },
    "checkpoint/revert.py": {
        "_context_for_restoration",
        "revert",
        "revert_checkpoint_unit",
        "_revert_locked",
    },
    "command_restoration/archive.py": {
        "_command_context_archive_path",
        "_load_command_context_archive",
        "list_command_context_archives",
    },
    "command_restoration/engine.py": {
        "restore_recent_context_command",
        "_restore_context_creation_command_locked",
        "_prepare_companion_session_restore",
        "_write_companion_session_restore",
    },
    "command_restoration/handlers/branch.py": {
        "_restore_branch_context_creation_command_locked",
    },
    "command_restoration/handlers/merge.py": {
        "_restore_merge_context_creation_command_locked",
    },
    "command_restoration/handlers/atomize.py": {
        "_restore_atomize_context_creation_command_locked",
    },
    "command_restoration/handlers/sever.py": {
        "_restore_sever_context_creation_command_locked",
    },
    "command_restoration/handlers/companion_sessions.py": {
        "_prepare_sever_command_restore",
        "_prepare_meld_command_restore",
        "_prepare_atomize_grounding_command_restore",
        "_prepare_update_command_restore",
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


def test_checkpoint_and_restoration_methods_have_one_owner() -> None:
    actual = {
        str(path.relative_to(STORE_ROOT)): _mixin_methods(path)
        for package in (STORE_ROOT / "checkpoint", STORE_ROOT / "command_restoration")
        for path in package.rglob("*.py")
        if path.name != "__init__.py"
    }
    assert actual == EXPECTED_METHODS
    all_methods = [method for methods in actual.values() for method in methods]
    assert len(all_methods) == len(set(all_methods)) == 24


def test_checkpoint_and_restoration_surfaces_preserve_composition() -> None:
    assert tuple(
        base.__module__.rsplit(".", 1)[-1] for base in CheckpointStoreMixin.__bases__
    ) == ("repository", "revert")
    assert tuple(
        base.__module__.rsplit(".", 1)[-1]
        for base in CommandRestorationStoreMixin.__bases__
    ) == (
        "archive",
        "engine",
        "branch",
        "merge",
        "atomize",
        "sever",
        "companion_sessions",
    )
    assert RecordRestoreCheckpointStoreMixin.__bases__ == (
        CheckpointStoreMixin,
        CommandRestorationStoreMixin,
    )


def test_checkpoint_does_not_depend_on_command_restoration() -> None:
    for path in (STORE_ROOT / "checkpoint").glob("*.py"):
        assert "command_restoration" not in path.read_text(encoding="utf-8")


def test_store_atomic_write_override_reaches_restore_owners(monkeypatch) -> None:
    marker = object()
    monkeypatch.setattr(store_module, "_write_json_atomic", marker)

    assert repository._write_json_atomic is marker
    assert revert._write_json_atomic is marker
    assert engine._write_json_atomic is marker
    assert atomize._write_json_atomic is marker
    assert branch._write_json_atomic is marker
    assert merge._write_json_atomic is marker
    assert sever._write_json_atomic is marker
