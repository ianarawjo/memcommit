"""Persisted, UID-preserving translation-view CLI contracts."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import (
    AutoCheckpoint,
    Context,
)
from memcommit.store import MemoryStore
from memcommit.translate import plan_translation
from memcommit.translation_view import (
    TranslationView,
    translation_view_record_digest,
)
from memcommit.translation_view_store import (
    ConcurrentTranslationViewUpdateError,
    load_translation_view,
    save_translation_view,
    translation_view_path,
)


runner = CliRunner(mix_stderr=False)
HIDDEN_QUERY_CONTENT = "query-only translation-view secret"


class PayloadProvider:
    """Return deterministic translations while retaining the strict payload."""

    def __init__(self, prefix: str = "EN: ", responder=None):
        self.prefix = prefix
        self.responder = responder
        self.calls = []

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(
            prompt.split("TRANSLATE PAYLOAD:\n", 1)[1]
        )
        self.calls.append((prompt, operation, output_schema, payload))
        if self.responder is not None:
            response = self.responder(payload)
        else:
            response = {
                "translations": [
                    {
                        "candidate_id": item["candidate_id"],
                        "translated_content": (
                            f"{self.prefix}{item['content']}"
                        ),
                    }
                    for item in payload["memories"]
                ]
            }
        return json.dumps(response, ensure_ascii=False)


def _saved_context(
    store: MemoryStore,
    name: str = "translation-view-test",
    contents: tuple[str, ...] = ("첫 번째", "두 번째"),
) -> Context:
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": name},
            description=f"Initialized '{name}' for translation-view test",
        ),
    )
    store.set_current(name)
    return context


def _patch_provider(monkeypatch, provider) -> None:
    monkeypatch.setattr(
        "memcommit.commands.translate.connect_codex_chatgpt_provider",
        lambda: provider,
    )


def _forbid_provider(monkeypatch) -> None:
    def forbidden():
        raise AssertionError("a saved translation view must be reused")

    monkeypatch.setattr(
        "memcommit.commands.translate.connect_codex_chatgpt_provider",
        forbidden,
    )


def test_default_saves_uid_preserving_view_without_materializing_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store)
    source_uids = source.ordered_uids()
    source_before = store.load_direct(source.name).to_dict()
    checkpoints_before = store.list_checkpoints(source.name)
    contexts_before = store.list_context_names()
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(app, ["translate", "--to", "English"])

    assert result.exit_code == 0
    assert len(provider.calls) == 1
    assert "EN: 첫 번째" in result.output
    assert "EN: 두 번째" in result.output
    assert all(
        f"[{source_uid[:8]}]" in result.output
        for source_uid in source_uids
    )
    assert "->" not in result.output
    assert store.current_context_name() == source.name
    assert store.list_context_names() == contexts_before
    assert not store.context_exists("translation-view-test-en")
    assert store.load_direct(source.name).to_dict() == source_before
    assert store.list_checkpoints(source.name) == checkpoints_before

    view = load_translation_view(source.uid, "English")
    assert view is not None
    assert view.matches(store.load_direct(source.name))
    serialized = view.to_dict()
    assert all(
        source_uid in json.dumps(serialized)
        for source_uid in source_uids
    )
    # A view is another representation of each source occurrence, not a new
    # Memory occurrence with translation lineage of its own.
    serialized_text = json.dumps(serialized)
    assert '"uid"' not in serialized_text
    assert "operation_uid" not in serialized_text
    assert "result_uid" not in serialized_text


def test_default_view_does_not_allocate_a_translation_operation_uid(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _saved_context(store, contents=("원문",))
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    def forbidden_operation_uid():
        raise AssertionError(
            "read-only translation views must not allocate operation UIDs"
        )

    monkeypatch.setattr(
        "memcommit.translate.uuid",
        SimpleNamespace(uuid4=forbidden_operation_uid),
    )

    result = runner.invoke(app, ["translate", "--to", "English"])

    assert result.exit_code == 0
    assert len(provider.calls) == 1
    assert "EN: 원문" in result.output


def test_repeat_reuses_exact_saved_view_without_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    provider = PayloadProvider(prefix="FIRST: ")
    _patch_provider(monkeypatch, provider)
    first = runner.invoke(app, ["translate", "--to", "English"])
    path = translation_view_path(source.uid, "English")
    saved_before = path.read_bytes()
    _forbid_provider(monkeypatch)

    repeated = runner.invoke(app, ["translate", "--to", "English"])

    assert first.exit_code == 0
    assert repeated.exit_code == 0
    assert "FIRST: 원문" in repeated.output
    assert len(provider.calls) == 1
    assert path.read_bytes() == saved_before
    assert store.current_context_name() == source.name
    assert store.list_context_names() == [source.name]


def test_semantically_similar_targets_use_distinct_exact_view_keys(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    first_target = "plain Canadian English for a newcomer"
    second_target = "Plain Canadian English for a newcomer"

    first_provider = PayloadProvider(prefix="FIRST: ")
    _patch_provider(monkeypatch, first_provider)
    first = runner.invoke(
        app,
        ["translate", "--to", first_target],
    )

    second_provider = PayloadProvider(prefix="SECOND: ")
    _patch_provider(monkeypatch, second_provider)
    second = runner.invoke(
        app,
        ["translate", "--to", second_target],
    )

    first_path = translation_view_path(source.uid, first_target)
    second_path = translation_view_path(source.uid, second_target)
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert len(first_provider.calls) == 1
    assert len(second_provider.calls) == 1
    assert first_provider.calls[0][3]["target_language"] == first_target
    assert second_provider.calls[0][3]["target_language"] == second_target
    assert first_path != second_path
    assert first_path.exists()
    assert second_path.exists()

    _forbid_provider(monkeypatch)
    repeated = runner.invoke(
        app,
        ["translate", "--to", first_target],
    )
    assert repeated.exit_code == 0
    assert "FIRST: 원문" in repeated.output
    assert "SECOND: 원문" not in repeated.output


def test_target_is_trimmed_before_exact_view_lookup(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    provider = PayloadProvider(prefix="CANONICAL: ")
    _patch_provider(monkeypatch, provider)

    first = runner.invoke(app, ["translate", "--to", "English"])
    _forbid_provider(monkeypatch)
    padded = runner.invoke(app, ["translate", "--to", "  English  "])

    assert first.exit_code == 0
    assert padded.exit_code == 0
    assert len(provider.calls) == 1
    assert "CANONICAL: 원문" in padded.output
    assert load_translation_view(source.uid, "English") is not None


def test_refresh_replaces_saved_view_and_later_calls_reuse_replacement(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    first_provider = PayloadProvider(prefix="OLD: ")
    _patch_provider(monkeypatch, first_provider)
    first = runner.invoke(app, ["translate", "--to", "English"])
    path = translation_view_path(source.uid, "English")
    old_record = path.read_bytes()

    refreshed_provider = PayloadProvider(prefix="NEW: ")
    _patch_provider(monkeypatch, refreshed_provider)
    refreshed = runner.invoke(
        app,
        ["translate", "--to", "English", "--refresh"],
    )

    assert first.exit_code == 0
    assert refreshed.exit_code == 0
    assert len(first_provider.calls) == 1
    assert len(refreshed_provider.calls) == 1
    assert "NEW: 원문" in refreshed.output
    assert path.read_bytes() != old_record

    _forbid_provider(monkeypatch)
    reused = runner.invoke(app, ["translate", "--to", "English"])
    assert reused.exit_code == 0
    assert "NEW: 원문" in reused.output
    assert "OLD: 원문" not in reused.output


def test_source_change_invalidates_and_regenerates_saved_view(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("기존",))
    initial_provider = PayloadProvider(prefix="OLD: ")
    _patch_provider(monkeypatch, initial_provider)
    initial = runner.invoke(app, ["translate", "--to", "English"])
    path = translation_view_path(source.uid, "English")
    old_record = path.read_bytes()

    changed = store.load_for_update(source.name)
    added = ops.add(changed, "추가")
    store.save(
        changed,
        AutoCheckpoint(
            command="add",
            args={},
            description="Changed source after translating it",
        ),
    )
    regenerated_provider = PayloadProvider(prefix="NEW: ")
    _patch_provider(monkeypatch, regenerated_provider)

    regenerated = runner.invoke(app, ["translate", "--to", "English"])

    assert initial.exit_code == 0
    assert regenerated.exit_code == 0
    assert len(regenerated_provider.calls) == 1
    payload = regenerated_provider.calls[0][3]
    assert [item["content"] for item in payload["memories"]] == [
        "기존",
        "추가",
    ]
    assert f"[{added.uid[:8]}]" in regenerated.output
    assert "NEW: 기존" in regenerated.output
    assert "NEW: 추가" in regenerated.output
    assert path.read_bytes() != old_record
    view = load_translation_view(source.uid, "English")
    assert view is not None
    assert view.matches(store.load_direct(source.name))


def test_save_as_materializes_saved_view_only_at_explicit_boundary(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    source_uid = source.ordered_uids()[0]
    source_before = store.load_direct(source.name).to_dict()
    source_checkpoints = store.list_checkpoints(source.name)
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)
    viewed = runner.invoke(app, ["translate", "--to", "English"])
    _forbid_provider(monkeypatch)

    materialized = runner.invoke(
        app,
        [
            "translate",
            "--to",
            "English",
            "--save-as",
            "study/english",
            "--yes",
        ],
    )

    assert viewed.exit_code == 0
    assert materialized.exit_code == 0
    assert len(provider.calls) == 1
    assert store.current_context_name() == "study/english"
    assert store.load_direct(source.name).to_dict() == source_before
    assert store.list_checkpoints(source.name) == source_checkpoints
    destination = store.load_direct("study/english")
    destination_uids = destination.ordered_uids()
    assert source_uid not in destination_uids
    assert [
        destination.memories[uid].content for uid in destination_uids
    ] == ["EN: 원문"]
    assert store.list_checkpoints(destination.name)[0]["command"] == (
        "translate"
    )
    assert load_translation_view(source.uid, "English") is not None


def test_declined_materialization_keeps_view_but_creates_no_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "translate",
            "--to",
            "English",
            "--save-as",
            "declined-english",
        ],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "remains saved" in result.output
    assert store.current_context_name() == source.name
    assert not store.context_exists("declined-english")
    assert load_translation_view(source.uid, "English") is not None


def test_yes_requires_materialization_while_explicit_in_place_remains(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    source_uid = source.ordered_uids()[0]
    source_before = store.load_direct(source.name).to_dict()
    checkpoints_before = store.list_checkpoints(source.name)
    _forbid_provider(monkeypatch)

    rejected = runner.invoke(app, ["translate", "--yes"])

    assert rejected.exit_code == 1
    assert "--yes" in rejected.stderr
    assert "--save-as" in rejected.stderr
    assert "--in-place" in rejected.stderr
    assert store.load_direct(source.name).to_dict() == source_before
    assert store.list_checkpoints(source.name) == checkpoints_before
    assert load_translation_view(source.uid, "English") is None

    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)
    applied = runner.invoke(
        app,
        ["translate", "--to", "English", "--in-place", "--yes"],
    )

    assert applied.exit_code == 0
    loaded = store.load_direct(source.name)
    loaded_uids = loaded.ordered_uids()
    assert loaded_uids[0] == source_uid
    assert loaded_uids[1] != source_uid
    assert [
        loaded.memories[uid].content for uid in loaded_uids
    ] == ["원문", "EN: 원문"]
    assert store.current_context_name() == source.name
    assert store.list_checkpoints(source.name)[0]["command"] == "translate"


def test_view_sends_only_direct_memories_and_preserves_mixed_pointers(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    referenced = ops.init("referenced")
    referenced_memory = ops.add(referenced, "referenced secret")
    store.save(referenced)
    child = ops.init("child")
    ops.add(child, "nested secret")
    store.save(child)
    hidden = store.create_query_source(
        "restricted-source",
        HIDDEN_QUERY_CONTENT,
    )
    parent = ops.init("mixed")
    owned = ops.add(parent, "직접 소유")
    memory_ref = ops.reference_memory(
        referenced_memory,
        referenced,
        parent,
    )
    query_ref = ops.reference_query_context(
        "restricted-source",
        hidden.uid,
        parent,
    )
    ops.embed(child, parent)
    store.save(
        parent,
        AutoCheckpoint(
            command="init",
            args={"name": parent.name},
            description="Initialized mixed translation-view source",
        ),
    )
    store.set_current(parent.name)
    parent_before = store.load_direct(parent.name).to_dict()

    def forbidden(*args, **kwargs):
        raise AssertionError("translate opened a query-only source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(app, ["translate", "--to", "English"])

    assert result.exit_code == 0
    assert len(provider.calls) == 1
    prompt, _, _, payload = provider.calls[0]
    assert [item["content"] for item in payload["memories"]] == [
        "직접 소유"
    ]
    assert "referenced secret" not in prompt
    assert "nested secret" not in prompt
    assert HIDDEN_QUERY_CONTENT not in prompt
    assert "referenced secret" not in result.output
    assert "nested secret" not in result.output
    assert HIDDEN_QUERY_CONTENT not in result.output
    assert store.load_direct(parent.name).to_dict() == parent_before
    assert store.load_direct(parent.name).ordered_uids() == [
        owned.uid,
        memory_ref.uid,
        query_ref.uid,
        child.uid,
    ]
    view = load_translation_view(parent.uid, "English")
    assert view is not None
    serialized = json.dumps(view.to_dict(), ensure_ascii=False)
    assert owned.uid in serialized
    assert memory_ref.uid not in serialized
    assert query_ref.uid not in serialized
    assert child.uid not in serialized


def test_concurrent_source_change_does_not_replace_prior_saved_view(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    initial_provider = PayloadProvider(prefix="STABLE: ")
    _patch_provider(monkeypatch, initial_provider)
    initial = runner.invoke(app, ["translate", "--to", "English"])
    path = translation_view_path(source.uid, "English")
    stable_record = path.read_bytes()

    def mutate_then_respond(payload):
        concurrent = store.load_for_update(source.name)
        ops.add(concurrent, "provider 호출 중 추가")
        store.save(
            concurrent,
            AutoCheckpoint(
                command="add",
                args={},
                description="Concurrent source change during refresh",
            ),
        )
        return {
            "translations": [
                {
                    "candidate_id": item["candidate_id"],
                    "translated_content": f"RACING: {item['content']}",
                }
                for item in payload["memories"]
            ]
        }

    racing_provider = PayloadProvider(responder=mutate_then_respond)
    _patch_provider(monkeypatch, racing_provider)
    refreshed = runner.invoke(
        app,
        ["translate", "--to", "English", "--refresh"],
    )

    assert initial.exit_code == 0
    assert refreshed.exit_code == 1
    assert "changed" in refreshed.stderr.lower()
    assert len(racing_provider.calls) == 1
    # The older view is now stale, but it remains the last complete record;
    # a failed refresh must never publish a translation of an obsolete frame.
    assert path.read_bytes() == stable_record
    preserved = load_translation_view(source.uid, "English")
    assert preserved is not None
    assert not preserved.matches(store.load_direct(source.name))


def test_context_deletion_removes_only_its_source_bound_translation_views(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = _saved_context(
        store,
        name="first-view-source",
        contents=("첫 번째",),
    )
    _patch_provider(monkeypatch, PayloadProvider(prefix="FIRST: "))
    assert runner.invoke(app, ["translate"]).exit_code == 0
    first_path = translation_view_path(first.uid, "English")
    assert first_path.exists()

    second = _saved_context(
        store,
        name="second-view-source",
        contents=("두 번째",),
    )
    _patch_provider(monkeypatch, PayloadProvider(prefix="SECOND: "))
    assert runner.invoke(app, ["translate"]).exit_code == 0
    second_path = translation_view_path(second.uid, "English")
    assert second_path.exists()

    store.delete(first.name)

    assert not first_path.exists()
    assert second_path.exists()
    assert load_translation_view(second.uid, "English") is not None


def test_stale_view_writer_cannot_overwrite_a_newer_same_source_refresh(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    old_view = TranslationView.from_plan(
        plan_translation(
            source,
            "English",
            lambda: PayloadProvider(prefix="OLD: "),
            allocate_operation_uid=False,
        ),
        source,
    )
    save_translation_view(
        store,
        old_view,
        expected_record_digest=None,
    )
    old_digest = translation_view_record_digest(old_view)

    new_view = TranslationView.from_plan(
        plan_translation(
            source,
            "English",
            lambda: PayloadProvider(prefix="NEW: "),
            allocate_operation_uid=False,
        ),
        source,
    )
    save_translation_view(
        store,
        new_view,
        expected_record_digest=old_digest,
    )

    with pytest.raises(
        ConcurrentTranslationViewUpdateError,
        match="slot changed",
    ):
        save_translation_view(
            store,
            old_view,
            expected_record_digest=old_digest,
        )

    saved = load_translation_view(source.uid, "English")
    assert saved is not None
    assert saved.entries[0].translated_content == "NEW: 원문"
