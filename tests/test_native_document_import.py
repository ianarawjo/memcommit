"""Native file imports share validation and ordinary publication semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from memcommit.application.operations.resource_import.documents.application import (
    import_context_from_documents,
    import_memory_from_document,
)
from memcommit.application.operations.resource_import.documents.codec import (
    read_document,
)
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.core.context import Context, Memory, MemoryRef
from memcommit.persistence.store import MemoryStore


ROOT_UID = "10000000-0000-4000-8000-000000000001"
CHILD_UID = "10000000-0000-4000-8000-000000000002"
MEMORY_UID = "20000000-0000-4000-8000-000000000001"


def _write(path: Path, record) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def _tree(tmp_path):
    root = Context(ROOT_UID, "campus")
    child = Context(CHILD_UID, "campus/access")
    memory = Memory(MEMORY_UID, "한글\n  Keep exact spacing.  ")
    root.add(memory)
    root.add(child)
    child.add(
        MemoryRef(
            uid="30000000-0000-4000-8000-000000000001",
            target_context_uid=root.uid,
            target_context_name=root.name,
            target_memory_uid=memory.uid,
            target=memory,
        )
    )
    source = tmp_path / "input"
    _write(source / "campus/context.json", root.to_dict())
    _write(source / "campus/access/context.json", child.to_dict())
    _write(source / "campus/checkpoints/ignored.json", {"unrelated": True})
    return source


def test_file_tree_import_preserves_identity_order_rewrites_refs_and_records_receipt(
    isolated_store, tmp_path
):
    source = _tree(tmp_path)
    store = MemoryStore()
    store.save(Context("current-uid", "current"))
    store.set_current("current")
    before = {p: p.read_bytes() for p in source.rglob("*.json")}
    result = import_context_from_documents(
        source, source_name="campus", target_name="copy", recursive=True
    )
    assert set(result.target_contexts) == {"copy", "copy/access"}
    copied = store.load_direct("copy")
    assert copied.uid == ROOT_UID
    assert copied.to_dict()["order"] == [MEMORY_UID, CHILD_UID]
    assert copied.memories[MEMORY_UID].content == "한글\n  Keep exact spacing.  "
    assert copied.memories[CHILD_UID].name == "copy/access"
    ref = next(store.load_direct("copy/access").iter_items())
    assert ref.target_context_name == "copy"
    assert ref.target_context_uid == ROOT_UID
    assert store.current_context_name() == "current"
    checkpoint = store.list_checkpoints("copy")[0]
    assert checkpoint["command"] == "import"
    assert checkpoint["args"]["source_kind"] == "JSON_FILE"
    assert len(checkpoint["args"]["source_sha256"]) == 64
    assert "input" not in str(checkpoint["args"])
    assert all(p.read_bytes() == value for p, value in before.items())


def test_native_memory_cli_uses_canonical_relative_destination(
    isolated_store, tmp_path
):
    from memcommit.adapters.console.entrypoint import app

    store = MemoryStore()
    store.save(Context("target-id", "campus/access"))
    store.set_current("campus/access")
    path = _write(
        tmp_path / "memory.json", Memory(MEMORY_UID, "  exact\ntext  ").to_dict()
    )
    args = ["import", "memory", "--from", str(path), "--into", "."]
    runner = CliRunner(mix_stderr=False)
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.stderr or first.output
    assert "campus/access" in first.output
    assert (
        store.load_direct("campus/access").memories[MEMORY_UID].content
        == "  exact\ntext  "
    )
    second = runner.invoke(app, args)
    assert second.exit_code == 1
    assert "already exists" in second.stderr
    assert len(store.list_checkpoints("campus/access")) == 1


def test_native_context_cli_accepts_a_single_file_without_profile_registration(
    isolated_store, tmp_path
):
    from memcommit.adapters.console.entrypoint import app

    path = _write(tmp_path / "context.json", Context(ROOT_UID, "campus").to_dict())
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        app, ["import", "context", "--from", str(path), "--as", "copy"]
    )
    assert result.exit_code == 0, result.stderr or result.output
    assert MemoryStore().load_direct("copy").uid == ROOT_UID
    assert MemoryStore().current_context_name() is None
    mixed = runner.invoke(
        app, ["import", "context", "--from", str(path), "--from-profile", "anything"]
    )
    assert mixed.exit_code == 1
    assert "Unsupported option" in mixed.stderr


def test_open_references_and_implicit_multi_context_input_fail_without_publication(
    isolated_store, tmp_path
):
    source = _tree(tmp_path)
    with pytest.raises(ValueError, match="Multiple Context documents"):
        import_context_from_documents(source)
    with pytest.raises(ProfileError, match="outside the import set"):
        import_context_from_documents(source, source_name="campus")
    assert MemoryStore().list_context_names() == []


def test_context_identity_collision_at_another_name_prevents_all_new_contexts(
    isolated_store, tmp_path
):
    source = _tree(tmp_path)
    store = MemoryStore()
    store.save(Context(CHILD_UID, "occupied"))
    with pytest.raises(ProfileError, match="already exists"):
        import_context_from_documents(source, recursive=True)
    assert store.list_context_names() == ["occupied"]


def test_second_context_io_failure_rolls_back_entire_file_import(
    isolated_store, tmp_path, monkeypatch
):
    source = _tree(tmp_path)
    original = MemoryStore._save_locked
    calls = 0

    def fail_second(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected native import write failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second)
    with pytest.raises(OSError, match="injected"):
        import_context_from_documents(source, recursive=True)
    assert MemoryStore().list_context_names() == []
    assert not list(isolated_store.rglob("context.json"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record.update(name="../escape"),
        lambda record: record.update(order=[]),
        lambda record: record.update(order=[MEMORY_UID, MEMORY_UID]),
        lambda record: record["memories"][MEMORY_UID].update(uid="wrong"),
        lambda record: record["memories"][MEMORY_UID].update(type="unknown"),
        lambda record: record["memories"][MEMORY_UID].update(type="granted_memory_ref"),
        lambda record: record["memories"][MEMORY_UID].update(type="query_context_ref"),
        lambda record: record.update(extra="silently dropped?"),
        lambda record: record["memories"][MEMORY_UID].update(content=123),
    ],
)
def test_malformed_or_authority_bearing_documents_publish_nothing(
    isolated_store, tmp_path, mutate
):
    context = Context(ROOT_UID, "campus")
    context.add(Memory(MEMORY_UID, "original"))
    record = context.to_dict()
    mutate(record)
    path = _write(tmp_path / "context.json", record)
    with pytest.raises((ValueError, TypeError)):
        import_context_from_documents(path)
    assert MemoryStore().list_context_names() == []


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text('{"type":"memory","uid":"one","uid":"two","content":"x"}')
    with pytest.raises(ValueError, match="Duplicate"):
        read_document(path)


def test_wrong_memory_selector_or_document_kind_never_mutates_target(
    isolated_store, tmp_path
):
    store = MemoryStore()
    store.save(Context(ROOT_UID, "target"))
    store.set_current("target")
    path = _write(tmp_path / "memory.json", Memory(MEMORY_UID, "x").to_dict())
    with pytest.raises(ValueError, match="does not match"):
        import_memory_from_document(path, memory_selector="wrong")
    _write(path, Context(CHILD_UID, "source").to_dict())
    with pytest.raises(ValueError, match="standalone"):
        import_memory_from_document(path)
    assert not store.load_direct("target").memories
