"""Query-only Context behavior and non-disclosure contracts."""

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import AutoCheckpoint, QueryContextRef
from memcommit.query_provider import QueryProviderError
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)
SECRET = "Contractors may enter Lab Seven only after 18:00."


def _attach_query_source(
    store: MemoryStore,
    *,
    parent_name: str = "facilities-reference",
    source_name: str = "contractor-agreements",
) -> tuple[QueryContextRef, str]:
    parent = ops.init(parent_name)
    source = store.create_query_source(source_name, SECRET)
    ref = ops.reference_query_context(source_name, source.uid, parent)
    store.save(
        parent,
        AutoCheckpoint(
            command="test setup",
            args={"name": source_name},
            description="Attached a query-only source",
        ),
    )
    store.set_current(parent_name)
    return ref, source.uid


def test_query_ref_round_trip_is_pointer_only_in_context_and_checkpoints(
    isolated_store,
):
    store = MemoryStore()
    ref, source_uid = _attach_query_source(store)

    parent_file = isolated_store / "contexts" / "facilities-reference" / "context.json"
    parent_data = json.loads(parent_file.read_text())
    assert parent_data["memories"][ref.uid] == {
        "type": "query_context_ref",
        "uid": ref.uid,
        "name": "contractor-agreements",
        "target_source_uid": source_uid,
        "provider": "codex_chatgpt",
    }

    normal_store_text = "\n".join(
        path.read_text()
        for path in (isolated_store / "contexts").rglob("*.json")
    )
    assert SECRET not in normal_store_text

    loaded = store.load("facilities-reference").memories[ref.uid]
    assert isinstance(loaded, QueryContextRef)
    assert loaded.target_source_uid == source_uid


def test_normal_load_never_opens_query_source(isolated_store, monkeypatch):
    store = MemoryStore()
    ref, _ = _attach_query_source(store)

    def forbidden(*args, **kwargs):
        raise AssertionError("normal Context load opened a query source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)

    loaded = store.load("facilities-reference")
    assert isinstance(loaded.memories[ref.uid], QueryContextRef)


def test_query_source_is_not_a_switchable_or_listed_context(isolated_store):
    store = MemoryStore()
    _attach_query_source(store)

    assert store.list_context_names() == ["facilities-reference"]
    assert not store.context_exists("contractor-agreements")

    switched = runner.invoke(app, ["switch", "contractor-agreements"])
    contexts = runner.invoke(app, ["contexts"])
    assert switched.exit_code == 1
    assert "contractor-agreements" not in contexts.output


def test_ls_show_and_status_reveal_metadata_but_not_source(isolated_store):
    store = MemoryStore()
    ref, _ = _attach_query_source(store)

    results = [
        runner.invoke(app, ["ls"]),
        runner.invoke(app, ["ls", "-R"]),
        runner.invoke(app, ["show"]),
        runner.invoke(app, ["show", ref.uid[:8]]),
        runner.invoke(app, ["status"]),
    ]

    assert all(result.exit_code == 0 for result in results)
    combined = "\n".join(result.output for result in results)
    assert "contractor-agreements" in combined
    assert "query-only" in combined
    assert SECRET not in combined
    assert "[query   " in results[0].output
    assert "Ask with: mem query" in results[3].output


def test_query_authenticates_before_reading_source(isolated_store, monkeypatch):
    store = MemoryStore()
    _attach_query_source(store)
    opened = False

    def unavailable(provider):
        raise QueryProviderError("not logged in")

    def track_open(*args, **kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("source was opened before authentication")

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        unavailable,
    )
    monkeypatch.setattr(MemoryStore, "load_query_source", track_open)

    result = runner.invoke(
        app,
        ["query", "contractor-agreements", "When may contractors enter?"],
    )

    assert result.exit_code == 1
    assert "not logged in" in result.stderr
    assert opened is False


def test_query_returns_provider_answer_without_checkpointing(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _attach_query_source(store)
    checkpoints_before = store.list_checkpoints("facilities-reference")
    calls = []

    class FakeProvider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "They may enter only after 18:00."

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda provider: FakeProvider(),
    )

    question = "When may contractors enter?"
    result = runner.invoke(
        app,
        ["query", "contractor-agreements", question],
    )

    assert result.exit_code == 0
    assert result.output == "They may enter only after 18:00.\n"
    assert calls == [("contractor-agreements", SECRET, question)]
    assert store.list_checkpoints("facilities-reference") == checkpoints_before
    persisted_text = "\n".join(
        path.read_text()
        for path in (isolated_store / "contexts").rglob("*.json")
    )
    assert question not in persisted_text
    assert result.output.strip() not in persisted_text


def test_query_rejects_an_ordinary_context_item(isolated_store, monkeypatch):
    store = MemoryStore()
    child = ops.init("ordinary")
    parent = ops.init("parent")
    ops.embed(child, parent)
    store.save(child)
    store.save(parent)
    store.set_current("parent")

    monkeypatch.setattr(
        "memcommit.commands.query.connect_query_provider",
        lambda provider: pytest.fail("provider should not be connected"),
    )

    result = runner.invoke(app, ["query", "ordinary", "Question?"])

    assert result.exit_code == 1
    assert "not a query-only Context" in result.stderr


def test_branch_merge_remove_and_revert_keep_only_the_pointer(isolated_store):
    store = MemoryStore()
    ref, source_uid = _attach_query_source(store)
    source_checkpoint = store.list_checkpoints("facilities-reference")[0]["uid"]

    branch = ops.branch(store.load("facilities-reference"), "study-copy")
    branch_ref = branch.memories[ref.uid]
    assert isinstance(branch_ref, QueryContextRef)
    assert branch_ref is not ref
    assert branch_ref.target_source_uid == source_uid

    target = ops.init("merge-target")
    first_added = ops.merge(branch, target)
    second_added = ops.merge(store.load("facilities-reference"), target)
    assert len(first_added) == 1
    assert second_added == []

    parent = store.load("facilities-reference")
    removed = ops.remove(parent, ref.uid)
    assert isinstance(removed, QueryContextRef)
    store.save(
        parent,
        AutoCheckpoint(
            command="remove",
            args={"uid": ref.uid},
            description="Removed query reference",
        ),
    )
    assert store.load_query_source(
        source_uid,
        expected_name="contractor-agreements",
    ).content == SECRET

    store.revert("facilities-reference", source_checkpoint)
    restored = store.load("facilities-reference").memories[ref.uid]
    assert isinstance(restored, QueryContextRef)
    assert restored.target_source_uid == source_uid


def test_merge_rejects_context_like_name_conflict_before_mutating_target(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    query_source = store.create_query_source("shared-name", SECRET)
    query_ref = ops.reference_query_context(
        "shared-name",
        query_source.uid,
        source,
    )
    target = ops.init("target")
    ordinary = ops.init("shared-name")
    ops.embed(ordinary, target)

    with pytest.raises(ValueError, match="already exists"):
        ops.merge(source, target)

    assert list(target.iter_items()) == [ordinary]
    assert query_ref.uid not in target.memories


def test_dev_install_adds_pointer_without_switching_or_storing_path(
    isolated_store,
    tmp_path,
):
    assert runner.invoke(app, ["init", "facilities-reference"]).exit_code == 0
    assert runner.invoke(app, ["init", "researcher-working"]).exit_code == 0
    source_path = tmp_path / "agreements.md"
    source_path.write_text(SECRET)

    result = runner.invoke(
        app,
        [
            "dev",
            "query-source",
            "install",
            "contractor-agreements",
            "--from",
            str(source_path),
            "--into",
            "facilities-reference",
        ],
    )

    store = MemoryStore()
    assert result.exit_code == 0
    assert store.current_context_name() == "researcher-working"
    ref = next(iter(store.load("facilities-reference").iter_items()))
    assert isinstance(ref, QueryContextRef)
    assert store.load_query_source(
        ref.target_source_uid,
        expected_name=ref.name,
    ).content == SECRET

    context_text = "\n".join(
        path.read_text()
        for path in (isolated_store / "contexts").rglob("*.json")
    )
    assert SECRET not in context_text
    assert str(source_path) not in context_text


def test_dev_install_rolls_back_source_if_parent_save_fails(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "facilities-reference"]).exit_code == 0
    source_path = tmp_path / "source.md"
    source_path.write_text(SECRET)
    original_save = MemoryStore.save

    def fail_query_ref_save(self, ctx, auto_checkpoint=None):
        if any(isinstance(item, QueryContextRef) for item in ctx.iter_items()):
            raise OSError("simulated write failure")
        return original_save(self, ctx, auto_checkpoint)

    monkeypatch.setattr(MemoryStore, "save", fail_query_ref_save)

    result = runner.invoke(
        app,
        [
            "dev",
            "query-source",
            "install",
            "contractor-agreements",
            "--from",
            str(source_path),
            "--into",
            "facilities-reference",
        ],
    )

    assert result.exit_code == 1
    assert list((isolated_store / "query-sources").iterdir()) == []
    assert list(MemoryStore().load("facilities-reference").iter_items()) == []


def test_dev_install_rolls_back_parent_if_checkpoint_fails(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    assert runner.invoke(app, ["init", "facilities-reference"]).exit_code == 0
    source_path = tmp_path / "source.md"
    source_path.write_text(SECRET)
    original_checkpoint = MemoryStore.checkpoint

    def fail_install_checkpoint(self, ctx, *args, **kwargs):
        if kwargs.get("command") == "dev query-source install":
            raise OSError("simulated checkpoint failure")
        return original_checkpoint(self, ctx, *args, **kwargs)

    monkeypatch.setattr(MemoryStore, "checkpoint", fail_install_checkpoint)

    result = runner.invoke(
        app,
        [
            "dev",
            "query-source",
            "install",
            "contractor-agreements",
            "--from",
            str(source_path),
            "--into",
            "facilities-reference",
        ],
    )

    store = MemoryStore()
    assert result.exit_code == 1
    assert list(store.load("facilities-reference").iter_items()) == []
    assert list((isolated_store / "query-sources").iterdir()) == []
    assert [
        checkpoint["command"]
        for checkpoint in store.list_checkpoints("facilities-reference")
    ] == ["init"]


def test_query_source_uid_cannot_escape_hidden_store(isolated_store, tmp_path):
    store = MemoryStore()
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep")

    with pytest.raises(ValueError, match="canonical UUID"):
        store.load_query_source("../../sentinel", expected_name="anything")

    assert sentinel.read_text() == "keep"
