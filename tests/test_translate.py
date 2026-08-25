"""Translation planning, privacy, application, provenance, and CLI contracts."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.provenance import build_trace
from memcommit.query_provider import QueryProviderError
from memcommit.store import ConcurrentContextUpdateError, MemoryStore
from memcommit.operations.translate.runtime import (
    TRANSLATE_CORPUS_CHAR_LIMIT,
    TRANSLATION_TARGET_CHAR_LIMIT,
    TranslateError,
    apply_translation,
    default_translation_context_name,
    derive_translation_context,
    plan_translation,
)


runner = CliRunner(mix_stderr=False)
HIDDEN_QUERY_CONTENT = "query-only ceiling: 4.2 million"


class PayloadProvider:
    """Return a caller-supplied response after recording the strict payload."""

    def __init__(self, responder=None):
        self.responder = responder or self._default_response
        self.calls = []

    @staticmethod
    def _default_response(payload):
        return {
            "translations": [
                {
                    "candidate_id": memory["candidate_id"],
                    "translated_content": f"EN: {memory['content']}",
                }
                for memory in payload["memories"]
            ]
        }

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(
            prompt.split("TRANSLATE PAYLOAD:\n", 1)[1]
        )
        self.calls.append((prompt, operation, output_schema, payload))
        response = self.responder(payload)
        if isinstance(response, str):
            return response
        return json.dumps(response, ensure_ascii=False)


def _saved_context(
    store: MemoryStore,
    name: str = "translation-test",
    contents: tuple[str, ...] = ("첫 번째", "두 번째"),
) -> Context:
    ctx = ops.init(name)
    for content in contents:
        ops.add(ctx, content)
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": name},
            description=f"Initialized '{name}' for translation test",
        ),
    )
    store.set_current(name)
    return ctx


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr(
        "memcommit.commands.translate.connect_codex_chatgpt_provider",
        lambda: provider,
    )


def test_cli_auto_types_explicit_context_without_switching_current(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("translate/source")
    ops.add(source, "첫 번째")
    ops.add(source, "두 번째")
    current = ops.init("translate/current")
    for context in (source, current):
        store.save(context)
    store.set_current(current.name)
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(app, ["translate", source.name])

    assert result.exit_code == 0, result.output
    assert "Translation view: 'translate/source'" in result.output
    assert len(provider.calls) == 1
    assert len(provider.calls[0][3]["memories"]) == 2
    assert store.current_context_name() == current.name


def test_cli_auto_types_bare_memory_and_finds_its_owner(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("translate/source")
    selected = ops.add(source, "선택된 메모리")
    ops.add(source, "선택되지 않은 메모리")
    current = ops.init("translate/current")
    for context in (source, current):
        store.save(context)
    store.set_current(current.name)
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(app, ["translate", selected.uid[:7]])

    assert result.exit_code == 0, result.output
    assert "Translation view: 'translate/source'" in result.output
    assert len(provider.calls) == 1
    assert [
        memory["content"] for memory in provider.calls[0][3]["memories"]
    ] == [selected.content]
    assert store.current_context_name() == current.name


def test_explicit_noncurrent_materialization_fails_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("translate/source")
    ops.add(source, "원문")
    current = ops.init("translate/current")
    for context in (source, current):
        store.save(context)
    store.set_current(current.name)
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        ["translate", source.name, "--save-as", "translate/result", "--yes"],
    )

    assert result.exit_code == 1
    assert "requires the selected Source to be the current Context" in result.stderr
    assert provider.calls == []
    assert not store.context_exists("translate/result")


def test_plan_uses_one_call_and_restores_context_order_from_model_ids():
    ctx = ops.init("ordered")
    first = ops.add(ctx, "도서관 후문은 닫힌다.")
    second = ops.add(ctx, "정문은 오후 5시에 닫힌다.")

    def reversed_response(payload):
        return {
            "translations": [
                {
                    "candidate_id": payload["memories"][1]["candidate_id"],
                    "translated_content": "The main entrance closes at 5 p.m.",
                },
                {
                    "candidate_id": payload["memories"][0]["candidate_id"],
                    "translated_content": "The library's rear entrance is closed.",
                },
            ]
        }

    provider = PayloadProvider(reversed_response)
    plan = plan_translation(ctx, "English", lambda: provider)

    assert len(provider.calls) == 1
    prompt, operation, schema, payload = provider.calls[0]
    assert operation == "translate"
    assert payload["target_language"] == "English"
    assert [item["candidate_id"] for item in payload["memories"]] == [
        "m000001",
        "m000002",
    ]
    assert first.uid not in prompt
    assert second.uid not in prompt
    assert schema["properties"]["translations"]["minItems"] == 2
    assert [proposal.source_uid for proposal in plan.proposals] == [
        first.uid,
        second.uid,
    ]
    assert [
        proposal.translated_content for proposal in plan.proposals
    ] == [
        "The library's rear entrance is closed.",
        "The main entrance closes at 5 p.m.",
    ]
    assert ctx.ordered_uids() == [first.uid, second.uid]


def test_plan_passes_a_descriptive_semantic_target_without_normalizing_it():
    ctx = ops.init("semantic-target")
    ops.add(ctx, "계약은 서명한 날부터 유효하다.")
    target = (
        "plain Canadian English for a newcomer; preserve legal terminology"
    )
    provider = PayloadProvider()

    plan = plan_translation(ctx, target, lambda: provider)

    prompt, _, _, payload = provider.calls[0]
    assert payload["target_language"] == target
    assert plan.target_language == target
    assert "user-authored semantic translation specification" in prompt
    assert "locale, dialect, register, audience, or terminology" in prompt


def test_semantic_target_json_framing_is_preserved_at_the_length_limit():
    ctx = ops.init("semantic-target-boundary")
    ops.add(ctx, "원문")
    prefix = 'English; preserve literal terminology {"key":"value"}; '
    target = prefix + ("x" * (TRANSLATION_TARGET_CHAR_LIMIT - len(prefix)))
    provider = PayloadProvider()

    plan = plan_translation(ctx, target, lambda: provider)

    prompt, _, _, payload = provider.calls[0]
    encoded_payload = prompt.split("TRANSLATE PAYLOAD:\n", 1)[1]
    assert len(target) == TRANSLATION_TARGET_CHAR_LIMIT
    assert json.loads(encoded_payload)["target_language"] == target
    assert payload["target_language"] == target
    assert plan.target_language == target


def test_apply_preserves_sources_and_inserts_each_copy_immediately_after_source():
    ctx = ops.init("paired")
    first = ops.add(ctx, "첫 번째")
    second = ops.add(ctx, "두 번째")
    plan = plan_translation(ctx, "English", PayloadProvider)

    result = apply_translation(ctx, plan)

    first_result, second_result = [
        translation.result for translation in result.translations
    ]
    assert ctx.ordered_uids() == [
        first.uid,
        first_result.uid,
        second.uid,
        second_result.uid,
    ]
    assert ctx.memories[first.uid] is first
    assert ctx.memories[second.uid] is second
    assert first.content == "첫 번째"
    assert second.content == "두 번째"
    assert first_result.content == "EN: 첫 번째"
    assert second_result.content == "EN: 두 번째"


def test_read_only_plan_cannot_materialize_without_an_operation_identity():
    ctx = ops.init("view-only-plan")
    ops.add(ctx, "원문")
    plan = plan_translation(
        ctx,
        "English",
        PayloadProvider,
        allocate_operation_uid=False,
    )

    assert plan.operation_uid is None
    with pytest.raises(TranslateError, match="operation identity"):
        apply_translation(ctx, plan)


def test_exactly_unchanged_translation_still_creates_a_distinct_occurrence():
    ctx = ops.init("proper-name")
    source = ops.add(ctx, "NFC")

    provider = PayloadProvider(
        lambda payload: {
            "translations": [
                {
                    "candidate_id": payload["memories"][0]["candidate_id"],
                    "translated_content": "NFC",
                }
            ]
        }
    )
    result = apply_translation(
        ctx,
        plan_translation(ctx, "English", lambda: provider),
    )

    translated = result.translations[0].result
    assert translated.uid != source.uid
    assert translated.content == source.content
    assert ctx.ordered_uids() == [source.uid, translated.uid]


def test_derived_context_replaces_sources_at_their_exact_direct_slots():
    source = ops.init("source")
    first = ops.add(source, "첫 번째")
    reference = MemoryRef(
        uid="reference-item",
        target_context_uid="reference-context",
        target_context_name="reference",
        target_memory_uid="reference-memory",
    )
    source.add(reference)
    second = ops.add(source, "두 번째")
    plan = plan_translation(source, "English", PayloadProvider)

    result = derive_translation_context(source, plan, "source-en")
    translated_uids = [
        translation.result.uid for translation in result.translations
    ]

    assert source.ordered_uids() == [first.uid, reference.uid, second.uid]
    assert result.baseline.ordered_uids() == [
        first.uid,
        reference.uid,
        second.uid,
    ]
    assert result.context.ordered_uids() == [
        translated_uids[0],
        reference.uid,
        translated_uids[1],
    ]
    assert [
        result.context.memories[uid].content
        for uid in translated_uids
    ] == ["EN: 첫 번째", "EN: 두 번째"]
    assert isinstance(
        result.context.memories[reference.uid],
        MemoryRef,
    )
    assert result.checkpoint_args()["schema_version"] == 2
    assert source.to_dict()["memories"][first.uid]["content"] == "첫 번째"


def test_legacy_derived_context_name_helper_remains_readable():
    assert (
        default_translation_context_name("task-123", "English")
        == "task-123-en"
    )
    assert (
        default_translation_context_name("task-123", "Canadian French")
        == "task-123-canadian-french"
    )
    assert (
        default_translation_context_name("task-123", "en/CA")
        == "task-123-en-ca"
    )


def test_selector_accepts_one_unique_memory_and_rejects_other_item_types():
    ctx = ops.init("selection")
    selected = Memory(uid="selected-memory", content="선택됨")
    other = Memory(uid="other-memory", content="제외됨")
    ctx.add(selected)
    ctx.add(other)
    ctx.add(
        MemoryRef(
            uid="reference-item",
            target_context_uid="source-context",
            target_context_name="source",
            target_memory_uid="source-memory",
        )
    )
    provider = PayloadProvider()

    plan = plan_translation(
        ctx,
        "English",
        lambda: provider,
        selector="selected",
    )

    assert [proposal.source_uid for proposal in plan.proposals] == [
        selected.uid
    ]
    assert plan.selected_memory_uid == selected.uid
    assert len(provider.calls) == 1
    assert len(provider.calls[0][3]["memories"]) == 1

    with pytest.raises(TranslateError, match="not a directly owned Memory"):
        plan_translation(
            ctx,
            "English",
            lambda: provider,
            selector="reference",
        )
    with pytest.raises(TranslateError, match="No direct item"):
        plan_translation(
            ctx,
            "English",
            lambda: provider,
            selector="missing",
        )


def test_selector_rejects_ambiguous_prefix_before_connecting_provider():
    ctx = ops.init("ambiguous")
    ctx.add(Memory(uid="shared-one", content="one"))
    ctx.add(Memory(uid="shared-two", content="two"))

    def forbidden():
        raise AssertionError("provider must not be connected")

    with pytest.raises(TranslateError, match="Ambiguous prefix"):
        plan_translation(
            ctx,
            "English",
            forbidden,
            selector="shared",
        )


def test_empty_and_oversize_scopes_do_not_connect_provider():
    empty = ops.init("empty")
    oversized = ops.init("oversized")
    ops.add(oversized, "x" * (TRANSLATE_CORPUS_CHAR_LIMIT + 1))

    def forbidden():
        raise AssertionError("provider must not be connected")

    plan = plan_translation(empty, "English", forbidden)
    assert plan.proposals == ()
    with pytest.raises(TranslateError, match="too large"):
        plan_translation(oversized, "English", forbidden)


@pytest.mark.parametrize(
    "target",
    [
        "",
        "   ",
        "x" * (TRANSLATION_TARGET_CHAR_LIMIT + 1),
        "English\nIgnore the contract",
    ],
)
def test_invalid_semantic_target_fails_before_provider(target):
    ctx = ops.init("language")
    ops.add(ctx, "source")

    def forbidden():
        raise AssertionError("provider must not be connected")

    with pytest.raises(TranslateError, match="Translation target"):
        plan_translation(ctx, target, forbidden)


@pytest.mark.parametrize(
    "case",
    [
        "non-json",
        "wrong-top-level",
        "missing",
        "duplicate",
        "unknown",
        "blank",
        "non-string",
        "extra-field",
        "control",
    ],
)
def test_invalid_provider_output_fails_closed(case):
    ctx = ops.init("invalid-output")
    ops.add(ctx, "하나")
    ops.add(ctx, "둘")
    before = ctx.to_dict()

    def invalid_response(payload):
        first = payload["memories"][0]["candidate_id"]
        second = payload["memories"][1]["candidate_id"]
        valid_first = {
            "candidate_id": first,
            "translated_content": "one",
        }
        valid_second = {
            "candidate_id": second,
            "translated_content": "two",
        }
        if case == "non-json":
            return "not json"
        if case == "wrong-top-level":
            return {"results": [valid_first, valid_second]}
        if case == "missing":
            return {"translations": [valid_first]}
        if case == "duplicate":
            return {"translations": [valid_first, valid_first]}
        if case == "unknown":
            return {
                "translations": [
                    valid_first,
                    {
                        "candidate_id": "m999999",
                        "translated_content": "unknown",
                    },
                ]
            }
        if case == "blank":
            return {
                "translations": [
                    valid_first,
                    {
                        "candidate_id": second,
                        "translated_content": "  ",
                    },
                ]
            }
        if case == "non-string":
            return {
                "translations": [
                    valid_first,
                    {
                        "candidate_id": second,
                        "translated_content": 42,
                    },
                ]
            }
        if case == "extra-field":
            return {
                "translations": [
                    valid_first,
                    {**valid_second, "explanation": "not allowed"},
                ]
            }
        assert case == "control"
        return {
            "translations": [
                valid_first,
                {
                    "candidate_id": second,
                    "translated_content": "unsafe\u001b[2J",
                },
            ]
        }

    with pytest.raises(TranslateError):
        plan_translation(
            ctx,
            "English",
            lambda: PayloadProvider(invalid_response),
        )
    assert ctx.to_dict() == before


def test_apply_rejects_a_stale_complete_direct_frame_without_partial_change():
    ctx = ops.init("stale")
    source = ops.add(ctx, "source")
    plan = plan_translation(ctx, "English", PayloadProvider)
    ops.add(ctx, "concurrent")
    before_apply = ctx.to_dict()

    with pytest.raises(TranslateError, match="stale"):
        apply_translation(ctx, plan)

    assert ctx.to_dict() == before_apply
    assert ctx.memories[source.uid].content == "source"


def test_cli_save_as_creates_derived_context_with_recorded_translation_lineage(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    original = _saved_context(store, contents=("후문은 닫힌다.", "정문은 열린다."))
    source_uids = original.ordered_uids()
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)
    source_before = original.to_dict()
    source_checkpoints = len(store.list_checkpoints(original.name))

    result = runner.invoke(
        app,
        [
            "translate",
            "--to",
            "English",
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert "Created translated Context 'translation-test-en'" in result.output
    assert "switched to it" in result.output
    assert len(provider.calls) == 1
    assert store.current_context_name() == "translation-test-en"
    assert store.load_direct(original.name).to_dict() == source_before
    assert len(store.list_checkpoints(original.name)) == source_checkpoints

    loaded = store.load_direct("translation-test-en")
    translated_uids = loaded.ordered_uids()
    assert not set(translated_uids) & set(source_uids)
    assert [
        loaded.memories[uid].content for uid in translated_uids
    ] == ["EN: 후문은 닫힌다.", "EN: 정문은 열린다."]
    checkpoints = store.list_checkpoints(loaded.name)
    assert len(checkpoints) == 2
    checkpoint = checkpoints[0]
    translated_record = loaded.to_dict()
    baseline_record = checkpoints[1]["snapshot"]
    assert checkpoint["command"] == "translate"
    assert checkpoint["args"]["schema_version"] == 2
    assert checkpoint["args"]["target_language"] == "English"
    assert [
        record["source_uid"]
        for record in checkpoint["args"]["translations"]
    ] == source_uids
    assert [
        record["result_uid"]
        for record in checkpoint["args"]["translations"]
    ] == translated_uids

    trace = build_trace(store, loaded, translated_uids[0])
    translated_events = [
        event for event in trace.events if event.kind == "TRANSLATED"
    ]
    assert len(translated_events) == 1
    assert translated_events[0].evidence == "RECORDED"
    assert translated_events[0].before[0].uid == source_uids[0]
    assert translated_events[0].after[0].uid == translated_uids[0]
    assert translated_events[0].reason_codes == ("TRANSLATION",)
    assert trace.originals[0].uid == source_uids[0]
    assert [state.uid for state in trace.current] == [
        translated_uids[0],
    ]
    assert set(trace.component_uids) == {
        source_uids[0],
        translated_uids[0],
    }
    assert not trace.warnings

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert store.load_direct(loaded.name).to_dict() == baseline_record

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert store.load_direct(loaded.name).to_dict() == translated_record
    assert [
        entry["command"] for entry in store.list_checkpoints(loaded.name)[:4]
    ] == ["redo", "undo", "translate", "init"]


def test_cli_in_place_is_an_explicit_legacy_sibling_mode(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    source_uid = source.ordered_uids()[0]
    source_before = source.to_dict()
    _patch_provider(monkeypatch, PayloadProvider())

    result = runner.invoke(app, ["translate", "--in-place", "--yes"])

    assert result.exit_code == 0
    assert "Added 1 translated Memory" in result.output
    assert store.current_context_name() == source.name
    loaded = store.load_direct(source.name)
    assert [
        item.content
        for item in loaded.iter_items()
        if isinstance(item, Memory)
    ] == ["원문", "EN: 원문"]
    checkpoint = store.list_checkpoints(source.name)[0]
    assert checkpoint["args"]["schema_version"] == 1
    assert checkpoint["args"]["translations"][0]["source_uid"] == source_uid
    translated = loaded.to_dict()

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert store.load_direct(source.name).to_dict() == source_before

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert store.load_direct(source.name).to_dict() == translated
    assert [
        entry["command"] for entry in store.list_checkpoints(source.name)[:3]
    ] == ["redo", "undo", "translate"]


def test_cli_save_as_overrides_the_derived_context_name(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    _patch_provider(monkeypatch, PayloadProvider())

    result = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "study/english-version",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert store.current_context_name() == "study/english-version"
    assert store.load_direct(source.name).memories
    translated = store.load_direct("study/english-version")
    assert [
        item.content
        for item in translated.iter_items()
        if isinstance(item, Memory)
    ] == ["EN: 원문"]


def test_cli_save_as_location_can_be_edited_from_materialization_review(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    _patch_provider(monkeypatch, PayloadProvider())

    result = runner.invoke(
        app,
        ["translate", "--save-as", "study/draft"],
        input="e\nstudy/final\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert "SAVE LOCATION" in result.output
    assert store.current_context_name() == "study/final"
    assert not store.context_exists("study/draft")
    assert store.load_direct(source.name).memories


def test_cli_save_as_partial_context_replaces_only_the_selected_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("첫 번째", "두 번째"))
    selected_uid, other_uid = source.ordered_uids()
    _patch_provider(monkeypatch, PayloadProvider())

    result = runner.invoke(
        app,
        [
            "translate",
            selected_uid[:8],
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    translated = store.load_direct("translation-test-en")
    assert selected_uid not in translated.memories
    assert other_uid in translated.memories
    assert [
        item.content
        for item in translated.iter_items()
        if isinstance(item, Memory)
    ] == ["EN: 첫 번째", "두 번째"]


def test_cli_rejects_destination_collision_and_conflicting_modes_pre_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    store.create_context(ops.init("translation-test-en"))
    store.set_current(source.name)

    def forbidden():
        raise AssertionError("provider must not be connected")

    monkeypatch.setattr(
        "memcommit.commands.translate.connect_codex_chatgpt_provider",
        forbidden,
    )
    collision = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )
    conflicting = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "another",
            "--in-place",
            "--yes",
        ],
    )

    assert collision.exit_code == 1
    assert "already exists" in collision.stderr
    assert conflicting.exit_code == 1
    assert "cannot be used together" in conflicting.stderr
    assert store.current_context_name() == source.name


def test_cli_default_target_is_english_and_saves_a_non_mutating_view(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    before = store.load_direct(ctx.name).to_dict()
    checkpoint_count = len(store.list_checkpoints(ctx.name))
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(app, ["translate"])

    assert result.exit_code == 0
    assert "English" in result.output
    assert "Saved translation view" in result.output
    assert ctx.ordered_uids()[0][:8] in result.output
    assert store.load_direct(ctx.name).to_dict() == before
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count
    assert not store.context_exists("translation-test-en")


def test_cli_empty_context_is_provider_free(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _saved_context(store, contents=())

    def forbidden():
        raise AssertionError("provider must not be connected")

    monkeypatch.setattr(
        "memcommit.commands.translate.connect_codex_chatgpt_provider",
        forbidden,
    )
    result = runner.invoke(app, ["translate"])

    assert result.exit_code == 0
    assert "no directly owned Memories" in result.output
    assert not store.context_exists("translation-test-en")


def test_cli_provider_failure_leaves_context_and_history_unchanged(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    before = store.load_direct(ctx.name).to_dict()
    checkpoint_count = len(store.list_checkpoints(ctx.name))

    class FailingProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            raise QueryProviderError("provider unavailable")

    _patch_provider(monkeypatch, FailingProvider())
    result = runner.invoke(app, ["translate"])

    assert result.exit_code == 1
    assert "provider unavailable" in result.stderr
    assert store.load_direct(ctx.name).to_dict() == before
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count
    assert not store.context_exists("translation-test-en")


def test_cli_without_current_context_is_provider_free(
    isolated_store,
    monkeypatch,
):
    def forbidden():
        raise AssertionError("provider must not be connected")

    monkeypatch.setattr(
        "memcommit.commands.translate.connect_codex_chatgpt_provider",
        forbidden,
    )
    result = runner.invoke(app, ["translate"])

    assert result.exit_code == 1
    assert "No current context" in result.stderr


def test_cli_save_failure_leaves_persisted_context_and_history_unchanged(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    before = store.load_direct(ctx.name).to_dict()
    checkpoint_count = len(store.list_checkpoints(ctx.name))
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)
    original_save = MemoryStore.save

    def fail_translate_save(
        self,
        candidate,
        auto_checkpoint=None,
        **kwargs,
    ):
        if (
            auto_checkpoint is not None
            and auto_checkpoint.command == "translate"
        ):
            raise OSError("simulated save failure")
        return original_save(self, candidate, auto_checkpoint)

    monkeypatch.setattr(MemoryStore, "save", fail_translate_save)
    result = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )

    assert result.exit_code == 1
    assert "simulated save failure" in result.stderr
    assert "preserved for manual inspection" in result.stderr
    assert store.load_direct(ctx.name).to_dict() == before
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count
    preserved = store.load_direct("translation-test-en")
    assert [
        item.content
        for item in preserved.iter_items()
        if isinstance(item, Memory)
    ] == ["원문"]
    assert len(store.list_checkpoints(preserved.name)) == 1
    assert store.current_context_name() == ctx.name


def test_cli_detects_concurrent_context_change_after_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    checkpoint_count = len(store.list_checkpoints(ctx.name))

    def mutate_then_respond(payload):
        concurrent = store.load_for_update(ctx.name)
        ops.add(concurrent, "concurrent")
        store.save(
            concurrent,
            AutoCheckpoint(
                command="add",
                args={},
                description="Concurrent test update",
            ),
        )
        return PayloadProvider._default_response(payload)

    _patch_provider(monkeypatch, PayloadProvider(mutate_then_respond))
    result = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )

    assert result.exit_code == 1
    assert "changed" in result.stderr
    loaded = store.load_direct(ctx.name)
    assert [
        item.content
        for item in loaded.iter_items()
        if isinstance(item, Memory)
    ] == ["원문", "concurrent"]
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count + 1
    assert store.list_checkpoints(ctx.name)[0]["command"] == "add"
    assert not store.context_exists("translation-test-en")


def test_cli_does_not_publish_destination_if_source_changes_before_creation(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)
    original_derive = ops.derive_translation_context

    def derive_then_save_concurrently(candidate, plan, destination_name):
        result = original_derive(candidate, plan, destination_name)
        concurrent = store.load_direct(ctx.name)
        ops.add(concurrent, "saved while translated Context was created")
        store.save(
            concurrent,
            AutoCheckpoint(
                command="add",
                args={},
                description="Concurrent source save",
            ),
        )
        return result

    monkeypatch.setattr(
        "memcommit.operations.translate.materialization.derive_translation_context",
        derive_then_save_concurrently,
    )
    result = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )

    assert result.exit_code == 1
    assert "source Context changed" in result.stderr
    loaded = store.load_direct(ctx.name)
    assert [
        item.content
        for item in loaded.iter_items()
        if isinstance(item, Memory)
    ] == ["원문", "saved while translated Context was created"]
    assert store.list_checkpoints(ctx.name)[0]["command"] == "add"
    assert not store.context_exists("translation-test-en")
    assert store.current_context_name() == ctx.name


def test_cli_preserves_destination_referenced_during_final_switch_race(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    store.save(ops.init("other"))
    store.save(ops.init("consumer"))
    store.set_current(source.name)
    _patch_provider(monkeypatch, PayloadProvider())
    original_set_current_if = MemoryStore.set_current_context_if

    def reference_then_switch(
        self,
        expected,
        destination_name,
        *,
        expected_context_uid,
        expected_context_digest,
    ):
        destination = self.load(destination_name)
        consumer = self.load_for_update("consumer")
        ops.embed(destination, consumer)
        self.save(consumer)
        self.set_current("other")
        return original_set_current_if(
            self,
            expected,
            destination_name,
            expected_context_uid=expected_context_uid,
            expected_context_digest=expected_context_digest,
        )

    monkeypatch.setattr(
        MemoryStore,
        "set_current_context_if",
        reference_then_switch,
    )

    result = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )

    assert result.exit_code == 1
    assert "preserved for manual inspection" in result.stderr
    assert store.current_context_name() == "other"
    assert store.context_exists("translation-test-en")
    consumer = store.load_direct("consumer")
    embedded = consumer.memories[
        next(iter(consumer.memories))
    ]
    assert isinstance(embedded, Context)
    assert embedded.name == "translation-test-en"


def test_stale_ordinary_writer_cannot_erase_a_completed_translation(
    isolated_store,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    stale_writer = store.load_direct(ctx.name)
    current = store.load_direct(ctx.name)
    applied = apply_translation(
        current,
        plan_translation(current, "English", PayloadProvider),
    )
    store.save(
        current,
        AutoCheckpoint(
            command="translate",
            args=applied.checkpoint_args(),
            description="Completed translation before stale writer",
        ),
        expected_context_digest=applied.plan.context_digest,
    )
    ops.add(stale_writer, "stale later addition")

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="changed before it could be saved",
    ):
        store.save(
            stale_writer,
            AutoCheckpoint(
                command="add",
                args={},
                description="Stale writer",
            ),
        )

    loaded = store.load_direct(ctx.name)
    assert [
        item.content
        for item in loaded.iter_items()
        if isinstance(item, Memory)
    ] == ["원문", "EN: 원문"]
    assert store.list_checkpoints(ctx.name)[0]["command"] == "translate"


def test_cli_translates_supported_legacy_context_without_explicit_order(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    context_path = store._context_file(ctx.name)
    legacy_record = json.loads(context_path.read_text(encoding="utf-8"))
    legacy_record.pop("order")
    context_path.write_text(
        json.dumps(legacy_record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "translation-test-en",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    source = store.load_direct(ctx.name)
    assert [
        item.content
        for item in source.iter_items()
        if isinstance(item, Memory)
    ] == ["원문"]
    loaded = store.load_direct("translation-test-en")
    assert [
        item.content
        for item in loaded.iter_items()
        if isinstance(item, Memory)
    ] == ["EN: 원문"]
    assert store.list_checkpoints(loaded.name)[0]["command"] == "translate"


def test_direct_only_cli_preserves_refs_query_only_and_embedded_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    source_memory = ops.add(source, "referenced secret")
    store.save(source)
    child = ops.init("child")
    ops.add(child, "nested secret")
    store.save(child)
    hidden = store.create_query_source(
        "restricted-source",
        HIDDEN_QUERY_CONTENT,
    )
    parent = ops.init("parent")
    owned = ops.add(parent, "직접 소유")
    memory_ref = ops.embed_memory(source_memory, source, parent)
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
            description="Initialized mixed parent",
        ),
    )
    store.set_current(parent.name)

    def forbidden(*args, **kwargs):
        raise AssertionError("translate opened query-only source content")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)
    provider = PayloadProvider()
    _patch_provider(monkeypatch, provider)

    result = runner.invoke(
        app,
        [
            "translate",
            "--save-as",
            "parent-en",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    prompt, _, _, payload = provider.calls[0]
    assert [record["content"] for record in payload["memories"]] == [
        "직접 소유"
    ]
    assert "referenced secret" not in prompt
    assert "nested secret" not in prompt
    assert HIDDEN_QUERY_CONTENT not in prompt
    assert store.load_direct(parent.name).ordered_uids() == [
        owned.uid,
        memory_ref.uid,
        query_ref.uid,
        child.uid,
    ]
    loaded = store.load_direct("parent-en")
    ordered = loaded.ordered_uids()
    assert ordered[0] != owned.uid
    assert isinstance(loaded.memories[ordered[0]], Memory)
    assert loaded.memories[ordered[0]].content == "EN: 직접 소유"
    assert ordered[1:] == [memory_ref.uid, query_ref.uid, child.uid]
    assert isinstance(loaded.memories[memory_ref.uid], MemoryRef)
    assert isinstance(loaded.memories[query_ref.uid], QueryContextRef)
    assert isinstance(loaded.memories[child.uid], Context)


def test_trace_rejects_forged_translation_mapping_and_falls_back_to_snapshot(
    isolated_store,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    plan = plan_translation(ctx, "English", PayloadProvider)
    applied = apply_translation(ctx, plan)
    args = applied.checkpoint_args()
    args["translations"][0]["result_sha256"] = "0" * 64
    store.save(
        ctx,
        AutoCheckpoint(
            command="translate",
            args=args,
            description="Forged translation evidence",
        ),
    )

    result_uid = applied.translations[0].result.uid
    trace = build_trace(store, store.load_direct(ctx.name), result_uid)

    assert not any(event.kind == "TRANSLATED" for event in trace.events)
    assert any(event.kind == "CREATED" for event in trace.events)
    assert any(
        "invalid translation lineage metadata" in warning
        for warning in trace.warnings
    )


def test_trace_rejects_forged_derived_baseline_digest(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("원문",))
    derived = derive_translation_context(
        source,
        plan_translation(source, "English", PayloadProvider),
        "translation-test-en",
    )
    store.create_context(
        derived.baseline,
        AutoCheckpoint(
            command="init",
            args={
                "name": derived.baseline.name,
                "source_context": {
                    "uid": source.uid,
                    "name": source.name,
                },
                "memory_uids": source.ordered_uids(),
            },
            description="Derived translation baseline",
        ),
    )
    derived.context._store_digest = derived.baseline._store_digest
    args = derived.checkpoint_args()
    args["destination_context"]["baseline_digest"] = "0" * 64
    store.save(
        derived.context,
        AutoCheckpoint(
            command="translate",
            args=args,
            description="Forged derived translation evidence",
        ),
    )

    result_uid = derived.translations[0].result.uid
    trace = build_trace(
        store,
        store.load_direct(derived.context.name),
        result_uid,
    )

    assert not any(event.kind == "TRANSLATED" for event in trace.events)
    assert any(event.kind == "CREATED" for event in trace.events)
    assert any(
        "invalid translation lineage metadata" in warning
        for warning in trace.warnings
    )


def test_trace_rejects_pointer_reordering_hidden_in_derived_translation(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("mixed-source")
    first = ops.add(source, "첫 번째")
    pointer = QueryContextRef(
        uid="query-pointer",
        name="opaque",
        target_source_uid="opaque-source",
        provider="codex",
    )
    source.add(pointer)
    second = ops.add(source, "두 번째")
    store.save(
        source,
        AutoCheckpoint(command="init", args={}, description="source"),
    )
    derived = derive_translation_context(
        source,
        plan_translation(source, "English", PayloadProvider),
        "mixed-source-en",
    )
    store.create_context(
        derived.baseline,
        AutoCheckpoint(
            command="init",
            args={
                "name": derived.baseline.name,
                "source_context": {
                    "uid": source.uid,
                    "name": source.name,
                },
                "memory_uids": [first.uid, second.uid],
            },
            description="Derived translation baseline",
        ),
    )
    derived.context._store_digest = derived.baseline._store_digest
    translated_uids = [
        translation.result.uid for translation in derived.translations
    ]
    derived.context.order = [
        pointer.uid,
        translated_uids[0],
        translated_uids[1],
    ]
    store.save(
        derived.context,
        AutoCheckpoint(
            command="translate",
            args=derived.checkpoint_args(),
            description="Translation with hidden pointer reorder",
        ),
    )

    trace = build_trace(
        store,
        store.load_direct(derived.context.name),
        translated_uids[0],
    )

    assert not any(event.kind == "TRANSLATED" for event in trace.events)
    assert any(
        "invalid translation lineage metadata" in warning
        for warning in trace.warnings
    )


def test_trace_rejects_forged_full_context_digest(
    isolated_store,
):
    store = MemoryStore()
    ctx = _saved_context(store, contents=("원문",))
    applied = apply_translation(
        ctx,
        plan_translation(ctx, "English", PayloadProvider),
    )
    args = applied.checkpoint_args()
    args["source_context"]["digest"] = "0" * 64
    store.save(
        ctx,
        AutoCheckpoint(
            command="translate",
            args=args,
            description="Forged Context digest",
        ),
    )

    result_uid = applied.translations[0].result.uid
    trace = build_trace(store, store.load_direct(ctx.name), result_uid)

    assert not any(event.kind == "TRANSLATED" for event in trace.events)
    assert any(
        "invalid translation lineage metadata" in warning
        for warning in trace.warnings
    )


def test_trace_rejects_pointer_change_hidden_inside_translation_checkpoint(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("pointer-source")
    target = ops.add(source, "target")
    store.save(source)
    ctx = ops.init("pointer-parent")
    ops.add(ctx, "원문")
    reference = ops.embed_memory(target, source, ctx)
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": ctx.name},
            description="Initialized pointer parent",
        ),
    )
    plan = plan_translation(ctx, "English", PayloadProvider)
    applied = apply_translation(ctx, plan)
    reference.target_context_name = "different-pointer-target"
    store.save(
        ctx,
        AutoCheckpoint(
            command="translate",
            args=applied.checkpoint_args(),
            description="Translation with hidden pointer mutation",
        ),
    )

    result_uid = applied.translations[0].result.uid
    trace = build_trace(store, store.load_direct(ctx.name), result_uid)

    assert not any(event.kind == "TRANSLATED" for event in trace.events)
    assert any(
        "invalid translation lineage metadata" in warning
        for warning in trace.warnings
    )


def test_help_inventory_classifies_translate(isolated_store):
    result = runner.invoke(app, ["help"])

    assert result.exit_code == 0
    assert any(
        line.startswith("translate ")
        and "Generate and save a reusable translated view" in line
        for line in result.output.splitlines()
    )
