"""Persisted, UID-preserving translation-view CLI contracts."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import (
    AutoCheckpoint,
    Context,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.translate.runtime import plan_translation
from memcommit.application.operations.translate.view import (
    TRANSLATION_ORIGIN_MANUAL,
    TRANSLATION_REVIEW_UNREVIEWED,
    TRANSLATION_REVIEW_VERIFIED,
    TranslationCatalog,
    TranslationView,
    TranslationViewError,
    translation_catalog_record_digest,
    translation_view_record_digest,
)
from memcommit.application.operations.translate.view_store import (
    ConcurrentTranslationViewUpdateError,
    load_translation_catalog,
    load_translation_catalog_for_context,
    load_translation_view,
    save_translation_catalog,
    save_translation_view,
    translation_catalog_path,
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
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )


def _forbid_provider(monkeypatch) -> None:
    def forbidden():
        raise AssertionError("a saved translation view must be reused")

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
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

    catalog = load_translation_catalog(source.uid, "English")
    assert catalog is not None
    assert catalog.covers(store.load_direct(source.name))
    serialized = catalog.to_dict()
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
        "memcommit.application.operations.translate.runtime.uuid",
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
    path = translation_catalog_path(source.uid, "English")
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

    first_path = translation_catalog_path(source.uid, first_target)
    second_path = translation_catalog_path(source.uid, second_target)
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
    assert load_translation_catalog(source.uid, "English") is not None


def test_refresh_replaces_saved_view_and_later_calls_reuse_replacement(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    first_provider = PayloadProvider(prefix="OLD: ")
    _patch_provider(monkeypatch, first_provider)
    first = runner.invoke(app, ["translate", "--to", "English"])
    path = translation_catalog_path(source.uid, "English")
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
    path = translation_catalog_path(source.uid, "English")
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
    catalog = load_translation_catalog(source.uid, "English")
    assert catalog is not None
    assert catalog.covers(store.load_direct(source.name))


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
    assert load_translation_catalog(source.uid, "English") is not None


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
    assert load_translation_catalog(source.uid, "English") is not None


def test_yes_requires_materialization_while_explicit_in_place_applies_immediately(
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
    assert load_translation_catalog(source.uid, "English") is None

    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)
    applied = runner.invoke(
        app,
        ["translate", "--to", "English", "--in-place"],
    )

    assert applied.exit_code == 0
    assert "[y/N]" not in applied.output
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
    memory_ref = ops.embed_memory(
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
    catalog = load_translation_catalog(parent.uid, "English")
    assert catalog is not None
    serialized = json.dumps(catalog.to_dict(), ensure_ascii=False)
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
    path = translation_catalog_path(source.uid, "English")
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
    preserved = load_translation_catalog(source.uid, "English")
    assert preserved is not None
    assert not preserved.covers(store.load_direct(source.name))


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
    first_path = translation_catalog_path(first.uid, "English")
    assert first_path.exists()

    second = _saved_context(
        store,
        name="second-view-source",
        contents=("두 번째",),
    )
    _patch_provider(monkeypatch, PayloadProvider(prefix="SECOND: "))
    assert runner.invoke(app, ["translate"]).exit_code == 0
    second_path = translation_catalog_path(second.uid, "English")
    assert second_path.exists()

    store.delete(first.name)

    assert not first_path.exists()
    assert second_path.exists()
    assert load_translation_catalog(second.uid, "English") is not None


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


def _catalog_plan(
    context: Context,
    prefix: str,
    *,
    selector: str | None = None,
):
    return plan_translation(
        context,
        "ko",
        lambda: PayloadProvider(prefix=prefix),
        selector=selector,
        allocate_operation_uid=False,
    )


def test_catalog_refresh_replaces_provider_but_preserves_curated_override(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(
        store,
        contents=("English A", "English B"),
    )
    first_uid, second_uid = source.ordered_uids()
    initial = TranslationCatalog.from_plan(
        _catalog_plan(source, "OLD: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    curated = initial.with_curated(
        source,
        first_uid,
        "검수한 A",
        origin=TRANSLATION_ORIGIN_MANUAL,
        review_status=TRANSLATION_REVIEW_VERIFIED,
        updated_at="2026-01-02T00:00:00+00:00",
    )

    refreshed = TranslationCatalog.from_plan(
        _catalog_plan(source, "NEW: "),
        source,
        existing=curated,
        created_at="2026-01-03T00:00:00+00:00",
    )

    effective = {
        entry.source_uid: entry
        for entry in refreshed.effective_entries(source)
    }
    assert effective[first_uid].translated_content == "검수한 A"
    assert effective[first_uid].curated is True
    assert effective[first_uid].review_status == (
        TRANSLATION_REVIEW_VERIFIED
    )
    assert effective[second_uid].translated_content == "NEW: English B"
    assert effective[second_uid].curated is False
    first_record = refreshed.entry_for(first_uid)
    assert first_record is not None
    assert first_record.provider is not None
    assert first_record.provider.translated_content == "NEW: English A"
    assert TranslationCatalog.from_dict(refreshed.to_dict()) == refreshed


def test_empty_catalog_accepts_first_curated_translation_without_provider(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    source_uid = source.ordered_uids()[0]
    empty = TranslationCatalog.empty(
        source,
        "ko",
        created_at="2026-01-01T00:00:00+00:00",
    )

    curated = empty.with_curated(
        source,
        source_uid,
        "한국어",
        origin=TRANSLATION_ORIGIN_MANUAL,
        review_status=TRANSLATION_REVIEW_VERIFIED,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    source_digest = hashlib.sha256(
        source.memories[source_uid].content.encode("utf-8")
    ).hexdigest()
    save_translation_catalog(
        store,
        curated,
        expected_record_digest=None,
        required_source_digests={source_uid: source_digest},
    )

    loaded = load_translation_catalog(source.uid, "ko")
    assert loaded == curated
    assert loaded is not None
    effective = loaded.effective_entries(source)
    assert len(effective) == 1
    assert effective[0].translated_content == "한국어"
    assert effective[0].curated is True
    assert effective[0].review_status == TRANSLATION_REVIEW_VERIFIED


def test_catalog_source_edit_retains_stale_curated_and_uses_new_provider(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    source_uid = source.ordered_uids()[0]
    catalog = TranslationCatalog.from_plan(
        _catalog_plan(source, "OLD: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    ).with_curated(
        source,
        source_uid,
        "검수 번역",
        origin=TRANSLATION_ORIGIN_MANUAL,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    ops.edit(source, source_uid, "Changed English")

    refreshed = TranslationCatalog.from_plan(
        _catalog_plan(source, "NEW: "),
        source,
        existing=catalog,
        created_at="2026-01-03T00:00:00+00:00",
    )

    entry = refreshed.entry_for(source_uid)
    assert entry is not None and entry.curated is not None
    assert entry.curated.translated_content == "검수 번역"
    assert refreshed.stale_curated_uids(source) == (source_uid,)
    effective = refreshed.effective_entries(source)
    assert len(effective) == 1
    assert effective[0].translated_content == "NEW: Changed English"
    assert effective[0].curated is False


def test_catalog_verify_freezes_provider_and_reset_exposes_latest_provider(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    source_uid = source.ordered_uids()[0]
    generated = TranslationCatalog.from_plan(
        _catalog_plan(source, "FIRST: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )

    verified = generated.with_review_status(
        source,
        source_uid,
        TRANSLATION_REVIEW_VERIFIED,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    refreshed = TranslationCatalog.from_plan(
        _catalog_plan(source, "SECOND: "),
        source,
        existing=verified,
        created_at="2026-01-03T00:00:00+00:00",
    )
    effective = refreshed.effective_entries(source)[0]
    assert effective.translated_content == "FIRST: English"
    assert effective.review_status == TRANSLATION_REVIEW_VERIFIED

    reset = refreshed.without_curated(
        source,
        source_uid,
        updated_at="2026-01-04T00:00:00+00:00",
    )
    effective = reset.effective_entries(source)[0]
    assert effective.translated_content == "SECOND: English"
    assert effective.review_status == TRANSLATION_REVIEW_UNREVIEWED
    assert effective.curated is False


def test_catalog_lazy_migration_unifies_legacy_scopes_by_newest_entry(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(
        store,
        contents=("English A", "English B"),
    )
    first_uid = source.ordered_uids()[0]
    whole = TranslationView.from_plan(
        _catalog_plan(source, "WHOLE: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    selected = TranslationView.from_plan(
        _catalog_plan(source, "SELECTED: ", selector=first_uid),
        source,
        created_at="2026-01-02T00:00:00+00:00",
    )
    save_translation_view(store, whole, expected_record_digest=None)
    save_translation_view(store, selected, expected_record_digest=None)

    catalog, migrated = load_translation_catalog_for_context(source, "ko")

    assert migrated is True
    assert catalog is not None
    assert not translation_catalog_path(source.uid, "ko").exists()
    effective = {
        item.source_uid: item for item in catalog.effective_entries(source)
    }
    assert effective[first_uid].translated_content == (
        "SELECTED: English A"
    )
    assert len(effective) == 2


def test_catalog_lazy_migration_rejects_a_newer_legacy_write(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    source_uid = source.ordered_uids()[0]
    original = TranslationView.from_plan(
        _catalog_plan(source, "OLD: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    save_translation_view(store, original, expected_record_digest=None)
    migrated, is_legacy = load_translation_catalog_for_context(source, "ko")
    assert migrated is not None and is_legacy is True
    expected_legacy_digest = translation_catalog_record_digest(migrated)

    newer = TranslationView.from_plan(
        _catalog_plan(source, "NEW: ", selector=source_uid),
        source,
        created_at="2026-01-02T00:00:00+00:00",
    )
    save_translation_view(store, newer, expected_record_digest=None)

    with pytest.raises(
        ConcurrentTranslationViewUpdateError,
        match="legacy translation view changed",
    ):
        save_translation_catalog(
            store,
            migrated,
            expected_record_digest=None,
            expected_legacy_record_digest=expected_legacy_digest,
        )
    assert load_translation_catalog(source.uid, "ko") is None


def test_legacy_writer_rejects_a_catalog_created_after_its_read(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    legacy = TranslationView.from_plan(
        _catalog_plan(source, "OLD: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    save_translation_view(store, legacy, expected_record_digest=None)
    migrated, is_legacy = load_translation_catalog_for_context(source, "ko")
    assert migrated is not None and is_legacy is True
    save_translation_catalog(
        store,
        migrated,
        expected_record_digest=None,
        expected_legacy_record_digest=(
            translation_catalog_record_digest(migrated)
        ),
    )
    late_v1 = TranslationView.from_plan(
        _catalog_plan(source, "LATE: "),
        source,
        created_at="2026-01-02T00:00:00+00:00",
    )

    with pytest.raises(
        ConcurrentTranslationViewUpdateError,
        match="cannot be saved after its v2 catalog",
    ):
        save_translation_view(
            store,
            late_v1,
            expected_record_digest=translation_view_record_digest(legacy),
        )
    assert load_translation_catalog(source.uid, "ko") == migrated


def test_translate_prunes_removed_source_entries_from_catalog(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    source_uid = source.ordered_uids()[0]
    _patch_provider(monkeypatch, PayloadProvider(prefix="KO: "))
    assert runner.invoke(app, ["translate", "--to", "ko"]).exit_code == 0

    changed = store.load_for_update(source.name)
    ops.remove(changed, source_uid)
    store.save(changed)
    result = runner.invoke(app, ["translate", "--to", "ko"])

    assert result.exit_code == 0
    catalog = load_translation_catalog(source.uid, "ko")
    assert catalog is not None
    assert catalog.entry_for(source_uid) is None
    raw = translation_catalog_path(source.uid, "ko").read_text(
        encoding="utf-8"
    )
    assert source_uid not in raw


def test_catalog_store_cas_and_source_binding_allow_unrelated_context_change(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(
        store,
        contents=("English A", "English B"),
    )
    first_uid = source.ordered_uids()[0]
    catalog = TranslationCatalog.from_plan(
        _catalog_plan(source, "KO: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=None,
        expected_context_digest=catalog.entry_for(first_uid).provider.context_digest,
    )
    original_digest = translation_catalog_record_digest(catalog)

    concurrent = store.load_for_update(source.name)
    ops.add(concurrent, "Unrelated new Memory")
    store.save(concurrent)
    edited = catalog.with_curated(
        source,
        first_uid,
        "수동 번역",
        origin=TRANSLATION_ORIGIN_MANUAL,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    source_digest = hashlib.sha256(
        source.memories[first_uid].content.encode("utf-8")
    ).hexdigest()
    save_translation_catalog(
        store,
        edited,
        expected_record_digest=original_digest,
        required_source_digests={first_uid: source_digest},
    )

    loaded = load_translation_catalog(source.uid, "ko")
    assert loaded == edited
    with pytest.raises(
        ConcurrentTranslationViewUpdateError,
        match="catalog changed",
    ):
        save_translation_catalog(
            store,
            catalog,
            expected_record_digest=original_digest,
        )


def test_curated_save_rejects_an_unrelated_removed_catalog_source(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(
        store,
        contents=("English A", "English B"),
    )
    first_uid, second_uid = source.ordered_uids()
    catalog = TranslationCatalog.from_plan(
        _catalog_plan(source, "KO: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=None,
        expected_context_digest=(
            catalog.entry_for(first_uid).provider.context_digest
        ),
    )
    edited = catalog.with_curated(
        source,
        first_uid,
        "수동 A",
        origin=TRANSLATION_ORIGIN_MANUAL,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    concurrent = store.load_for_update(source.name)
    ops.remove(concurrent, second_uid)
    store.save(concurrent)

    with pytest.raises(
        ConcurrentTranslationViewUpdateError,
        match="source Memory was removed",
    ):
        save_translation_catalog(
            store,
            edited,
            expected_record_digest=translation_catalog_record_digest(catalog),
            required_source_digests={
                first_uid: hashlib.sha256(b"English A").hexdigest()
            },
        )
    assert load_translation_catalog(source.uid, "ko") == catalog


def test_translation_disk_schemas_reject_float_versions(isolated_store):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    view = TranslationView.from_plan(
        _catalog_plan(source, "KO: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    view_record = view.to_dict()
    view_record["schema_version"] = 1.0
    with pytest.raises(TranslationViewError, match="schema version"):
        TranslationView.from_dict(view_record)

    catalog = TranslationCatalog.from_plan(
        _catalog_plan(source, "KO: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    catalog_record = catalog.to_dict()
    catalog_record["schema_version"] = 2.0
    with pytest.raises(TranslationViewError, match="schema version"):
        TranslationCatalog.from_dict(catalog_record)


def test_catalog_provider_save_rejects_concurrent_source_frame_change(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    catalog = TranslationCatalog.from_plan(
        _catalog_plan(source, "KO: "),
        source,
        created_at="2026-01-01T00:00:00+00:00",
    )
    expected_context_digest = catalog.entries[0].provider.context_digest
    concurrent = store.load_for_update(source.name)
    ops.add(concurrent, "Changed during provider call")
    store.save(concurrent)

    with pytest.raises(
        ConcurrentTranslationViewUpdateError,
        match="Context changed",
    ):
        save_translation_catalog(
            store,
            catalog,
            expected_record_digest=None,
            expected_context_digest=expected_context_digest,
        )
    assert load_translation_catalog(source.uid, "ko") is None
