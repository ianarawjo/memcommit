"""CLI contracts for editable, same-UID translation catalogs."""

from __future__ import annotations

import hashlib
import json

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import AutoCheckpoint
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.memory_history_construction import (
    reconstruct_memory_history,
)
from memcommit.persistence.store import MemoryStore
from memcommit.core.memory_translation import (
    TRANSLATION_ORIGIN_IMPORTED,
    TRANSLATION_ORIGIN_MANUAL,
    TRANSLATION_REVIEW_UNREVIEWED,
    TRANSLATION_REVIEW_VERIFIED,
)
from memcommit.persistence.store.translation_catalog import load_translation_catalog


runner = CliRunner(mix_stderr=False)


class _Provider:
    def __init__(self, prefix: str):
        self.prefix = prefix
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        payload = json.loads(prompt.split("TRANSLATE PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "translations": [
                    {
                        "candidate_id": item["candidate_id"],
                        "translated_content": self.prefix + item["content"],
                    }
                    for item in payload["memories"]
                ]
            },
            ensure_ascii=False,
        )


def _source(store: MemoryStore):
    context = ops.init("source")
    memory = ops.add(context, "Canonical English")
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": context.name},
            description="Initialized translation catalog test source",
        ),
    )
    store.set_current(context.name)
    return context, memory


def test_set_and_verify_change_only_the_same_uid_sidecar(
    isolated_store,
):
    store = MemoryStore()
    context, memory = _source(store)
    source_before = store.load_direct(context.name).to_dict()
    checkpoints_before = store.list_checkpoints(context.name)

    set_result = runner.invoke(
        app,
        ["translate", memory.uid, "--to", "ko", "--set", "한국어 번역"],
    )
    verify_result = runner.invoke(
        app,
        ["translate", memory.uid, "--to", "ko", "--verify"],
    )

    assert set_result.exit_code == 0
    assert verify_result.exit_code == 0
    assert store.load_direct(context.name).to_dict() == source_before
    assert store.list_checkpoints(context.name) == checkpoints_before
    catalog = load_translation_catalog(context.uid, "ko")
    assert catalog is not None
    entry = catalog.entry_for(memory.uid)
    assert entry is not None and entry.curated is not None
    assert entry.curated.translated_content == "한국어 번역"
    assert entry.curated.origin == TRANSLATION_ORIGIN_MANUAL
    assert entry.curated.review_status == TRANSLATION_REVIEW_VERIFIED


def test_provider_refresh_never_overwrites_verified_curated_text(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, memory = _source(store)
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--set", "검수 번역"],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--verify"],
        ).exit_code
        == 0
    )
    provider = _Provider("PROVIDER: ")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    refreshed = runner.invoke(
        app,
        ["translate", memory.uid, "--to", "ko", "--refresh"],
    )

    assert refreshed.exit_code == 0
    assert provider.calls == 1
    assert "검수 번역" in refreshed.output
    assert "PROVIDER: Canonical English" not in refreshed.output
    catalog = load_translation_catalog(context.uid, "ko")
    assert catalog is not None
    entry = catalog.entry_for(memory.uid)
    assert entry is not None
    assert entry.provider is not None
    assert entry.curated is not None
    assert entry.curated.review_status == TRANSLATION_REVIEW_VERIFIED


def test_export_edit_import_is_source_hash_bound_and_atomic(
    isolated_store,
    tmp_path,
):
    store = MemoryStore()
    context, memory = _source(store)
    exported = tmp_path / "ko.json"

    result = runner.invoke(
        app,
        ["translate", "--to", "ko", "--export", str(exported)],
    )
    payload = json.loads(exported.read_text(encoding="utf-8"))
    payload["translations"][0]["translated_content"] = "가져온 번역"
    payload["translations"][0]["review_status"] = "VERIFIED"
    imported = tmp_path / "ko-import.json"
    imported.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    applied = runner.invoke(
        app,
        ["translate", "--to", "ko", "--input", str(imported)],
    )

    assert result.exit_code == 0
    assert applied.exit_code == 0
    catalog = load_translation_catalog(context.uid, "ko")
    assert catalog is not None
    entry = catalog.entry_for(memory.uid)
    assert entry is not None and entry.curated is not None
    assert entry.curated.translated_content == "가져온 번역"
    assert entry.curated.origin == TRANSLATION_ORIGIN_IMPORTED
    assert entry.curated.review_status == TRANSLATION_REVIEW_VERIFIED
    assert (
        payload["translations"][0]["source_sha256"]
        == hashlib.sha256(memory.content.encode("utf-8")).hexdigest()
    )

    stale_payload = json.loads(imported.read_text(encoding="utf-8"))
    stale_payload["translations"][0]["source_sha256"] = "0" * 64
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps(stale_payload), encoding="utf-8")
    rejected = runner.invoke(
        app,
        ["translate", "--to", "ko", "--input", str(stale)],
    )
    assert rejected.exit_code == 1
    preserved = load_translation_catalog(context.uid, "ko")
    assert preserved == catalog


def test_reset_reveals_provider_layer_without_changing_memory(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, memory = _source(store)
    provider = _Provider("자동: ")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["translate", "--to", "ko"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--set", "수동"],
        ).exit_code
        == 0
    )

    reset = runner.invoke(
        app,
        ["translate", memory.uid, "--to", "ko", "--reset"],
    )

    assert reset.exit_code == 0
    assert "자동: Canonical English" in reset.output
    catalog = load_translation_catalog(context.uid, "ko")
    assert catalog is not None
    entry = catalog.entry_for(memory.uid)
    assert entry is not None and entry.provider is not None
    assert entry.curated is None
    assert store.load_direct(context.name).memories[memory.uid].content == (
        "Canonical English"
    )


def test_curated_catalog_is_not_applied_without_provenance_contract(
    isolated_store,
):
    store = MemoryStore()
    _, memory = _source(store)
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--set", "수동"],
        ).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        ["translate", "--to", "ko", "--save-as", "derived", "--yes"],
    )

    assert result.exit_code == 1
    assert "Curated or mixed" in result.stderr
    assert not store.context_exists("derived")


def test_verified_provider_catalog_is_not_applied_as_untouched_batch(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _, memory = _source(store)
    provider = _Provider("자동: ")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["translate", "--to", "ko"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--verify"],
        ).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        ["translate", "--to", "ko", "--save-as", "derived", "--yes"],
    )

    assert result.exit_code == 1
    assert "Curated or mixed" in result.stderr
    assert not store.context_exists("derived")


def test_unchanged_export_import_preserves_provider_provenance(
    isolated_store,
    monkeypatch,
    tmp_path,
):
    store = MemoryStore()
    context, memory = _source(store)
    provider = _Provider("자동: ")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["translate", "--to", "ko"]).exit_code == 0
    before = load_translation_catalog(context.uid, "ko")
    assert before is not None
    exported = tmp_path / "unchanged.json"
    assert (
        runner.invoke(
            app,
            ["translate", "--to", "ko", "--export", str(exported)],
        ).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        ["translate", "--to", "ko", "--input", str(exported)],
    )

    assert result.exit_code == 0
    assert "Imported 0 changed" in result.output
    after = load_translation_catalog(context.uid, "ko")
    assert after == before
    entry = after.entry_for(memory.uid)
    assert entry is not None and entry.provider is not None
    assert entry.curated is None


def test_import_rejects_a_stale_exported_catalog_revision(
    isolated_store,
    monkeypatch,
    tmp_path,
):
    _, memory = _source(MemoryStore())
    provider = _Provider("자동: ")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(app, ["translate", "--to", "ko"]).exit_code == 0
    exported = tmp_path / "stale-catalog.json"
    assert (
        runner.invoke(
            app,
            ["translate", "--to", "ko", "--export", str(exported)],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--verify"],
        ).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        ["translate", "--to", "ko", "--input", str(exported)],
    )

    assert result.exit_code == 1
    assert "different catalog revision" in result.stderr


def test_import_rejects_non_integer_schema_and_non_string_review_status(
    isolated_store,
    tmp_path,
):
    _source(MemoryStore())
    exported = tmp_path / "base.json"
    assert (
        runner.invoke(
            app,
            ["translate", "--to", "ko", "--export", str(exported)],
        ).exit_code
        == 0
    )
    payload = json.loads(exported.read_text(encoding="utf-8"))

    payload["schema_version"] = True
    bool_schema = tmp_path / "bool-schema.json"
    bool_schema.write_text(json.dumps(payload), encoding="utf-8")
    result = runner.invoke(
        app,
        ["translate", "--to", "ko", "--input", str(bool_schema)],
    )
    assert result.exit_code == 1
    assert "Unsupported translation import schema" in result.stderr

    payload["schema_version"] = 2
    payload["translations"][0]["review_status"] = []
    list_status = tmp_path / "list-status.json"
    list_status.write_text(json.dumps(payload), encoding="utf-8")
    result = runner.invoke(
        app,
        ["translate", "--to", "ko", "--input", str(list_status)],
    )
    assert result.exit_code == 1
    assert "entry is invalid" in result.stderr


def test_unverify_rebinds_review_status_to_current_text(
    isolated_store,
):
    store = MemoryStore()
    context, memory = _source(store)
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--set", "번역"],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["translate", memory.uid, "--to", "ko", "--verify"],
        ).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        ["translate", memory.uid, "--to", "ko", "--unverify"],
    )

    assert result.exit_code == 0
    catalog = load_translation_catalog(context.uid, "ko")
    assert catalog is not None
    entry = catalog.entry_for(memory.uid)
    assert entry is not None and entry.curated is not None
    assert entry.curated.review_status == TRANSLATION_REVIEW_UNREVIEWED
    assert entry.curated.reviewed_content_sha256 is None


def test_long_semantic_target_remains_recorded_in_applied_trace(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, memory = _source(store)
    provider = _Provider("Translated: ")
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.translate.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    target = (
        "plain Canadian English for a newcomer; preserve institutional "
        "terminology, modal force, exceptions, and uncertainty"
    )
    assert len(target) > 80

    result = runner.invoke(
        app,
        ["translate", "--to", target, "--in-place", "--yes"],
    )

    assert result.exit_code == 0
    loaded = store.load_direct(context.name)
    result_uid = next(uid for uid in loaded.ordered_uids() if uid != memory.uid)
    trace = reconstruct_memory_history(store, loaded, result_uid)
    translated = [event for event in trace.events if event.kind == "TRANSLATED"]
    assert len(translated) == 1
    assert translated[0].evidence == "RECORDED"
    assert not trace.warnings
