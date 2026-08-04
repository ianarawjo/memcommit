"""Durable, exact-input cache contracts for ``mem rationale`` inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.rationale as rationale_module
import memcommit.store as store_module
from memcommit.cli import app
from memcommit.query_provider import QueryProviderError
from memcommit.rationale_cache import (
    CachedRationaleInference,
    load_rationale_inference,
    rationale_inference_input_digest,
    rationale_inference_path,
    save_rationale_inference,
)
from memcommit.store import MemoryStore


runner = CliRunner()
RATIONALE_MARKER = "RATIONALE PAYLOAD:\n"


def invoke(*args: str):
    return runner.invoke(app, list(args))


class RationaleProvider:
    def __init__(self, label: str):
        self.label = label
        self.calls: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "rationale inference"
        assert output_schema is not None
        payload = json.loads(prompt.split(RATIONALE_MARKER, 1)[1])
        self.calls.append(payload)
        candidates = payload["candidates"]
        assert isinstance(candidates, list) and candidates
        return json.dumps(
            {
                "best_supported_reading": f"{self.label} reading",
                "contextual_flow": f"{self.label} flow",
                "support_ids": [candidates[0]["candidate_id"]],
                "unresolved": [],
            }
        )


class BadRationaleProvider:
    def __init__(self, mode: str):
        self.mode = mode
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        if self.mode == "provider-failure":
            raise QueryProviderError("rationale provider unavailable")
        assert self.mode == "invalid-output"
        return json.dumps(
            {
                "best_supported_reading": "POISON reading",
                "contextual_flow": "POISON flow",
                "support_ids": ["unknown-candidate"],
                "unresolved": [],
            }
        )


def _patch_provider(monkeypatch, provider) -> None:
    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_codex_chatgpt_provider",
        lambda: provider,
    )


def _forbid_provider(monkeypatch) -> None:
    def forbidden():
        raise AssertionError("the rationale provider must not be connected")

    monkeypatch.setattr(
        "memcommit.commands.rationale.connect_codex_chatgpt_provider",
        forbidden,
    )


def _setup_context(name: str = "rationale-cache"):
    store = MemoryStore()
    ctx = ops.init(name)
    target, first, second = ops.add_many(
        ctx,
        ["Target fragment.", "First direct neighbor.", "Second neighbor."],
    )
    store.save(ctx)
    store.set_current(ctx.name)
    return store, ctx, target, first, second


def test_identical_cli_input_reuses_cache_and_reports_it_in_text_and_json(
    isolated_store,
    monkeypatch,
):
    _, ctx, target, _, _ = _setup_context()
    provider = RationaleProvider("ORIGINAL")
    _patch_provider(monkeypatch, provider)

    first = invoke("rationale", target.uid)

    assert first.exit_code == 0, first.output
    assert "ORIGINAL reading" in first.output
    assert len(provider.calls) == 1
    assert rationale_inference_path(ctx.uid, target.uid).is_file()

    _forbid_provider(monkeypatch)
    reused = invoke("rationale", target.uid)
    structured = invoke("rationale", target.uid, "--json")

    assert reused.exit_code == 0, reused.output
    assert "ORIGINAL reading" in reused.output
    assert "Reused cached inference for unchanged input" in reused.output
    assert structured.exit_code == 0, structured.output
    payload = json.loads(structured.output)
    assert payload["inference_cached"] is True
    assert payload["inference"]["best_supported_reading"] == (
        "ORIGINAL reading"
    )


def test_refresh_replaces_cache_and_conflicts_with_recorded_only(
    isolated_store,
    monkeypatch,
):
    _, _, target, _, _ = _setup_context()
    original = RationaleProvider("ORIGINAL")
    _patch_provider(monkeypatch, original)
    assert invoke("rationale", target.uid).exit_code == 0

    replacement = RationaleProvider("REFRESHED")
    _patch_provider(monkeypatch, replacement)
    refreshed = invoke("rationale", target.uid, "--refresh")

    assert refreshed.exit_code == 0, refreshed.output
    assert "REFRESHED reading" in refreshed.output
    assert "Reused cached inference" not in refreshed.output
    assert len(replacement.calls) == 1

    _forbid_provider(monkeypatch)
    reused = invoke("rationale", target.uid, "--json")
    incompatible = invoke(
        "rationale",
        target.uid,
        "--refresh",
        "--recorded-only",
    )

    assert reused.exit_code == 0, reused.output
    payload = json.loads(reused.output)
    assert payload["inference_cached"] is True
    assert payload["inference"]["best_supported_reading"] == (
        "REFRESHED reading"
    )
    assert incompatible.exit_code == 1
    assert "cannot be combined with --recorded-only" in incompatible.output


@pytest.mark.parametrize(
    "change",
    ["target-content", "candidate-content", "add", "order"],
)
def test_direct_memory_input_changes_invalidate_the_latest_slot(
    isolated_store,
    monkeypatch,
    change,
):
    store, ctx, target, first, second = _setup_context(
        f"rationale-cache-{change}"
    )
    initial = RationaleProvider("BEFORE")
    _patch_provider(monkeypatch, initial)
    assert invoke("rationale", target.uid).exit_code == 0

    current = store.load_direct(ctx.name)
    if change == "target-content":
        ops.edit(current, target.uid, "Changed target fragment.")
    elif change == "candidate-content":
        ops.edit(current, first.uid, "Changed direct neighbor.")
    elif change == "add":
        ops.add(current, "New direct neighbor.")
    else:
        current.order = [second.uid, target.uid, first.uid]
    store.save(current)

    current_provider = RationaleProvider("AFTER")
    _patch_provider(monkeypatch, current_provider)
    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert "AFTER reading" in result.output
    assert "Reused cached inference" not in result.output
    assert len(current_provider.calls) == 1


def _replace_nested_key(value: object, key: str, replacement: object) -> int:
    count = 0
    if isinstance(value, dict):
        if key in value:
            value[key] = replacement
            count += 1
        for child in value.values():
            count += _replace_nested_key(child, key, replacement)
    elif isinstance(value, list):
        for child in value:
            count += _replace_nested_key(child, key, replacement)
    return count


def _corrupt_cache(path: Path, mode: str) -> None:
    if mode == "malformed":
        path.write_text("{not valid JSON: POISON", encoding="utf-8")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    if mode == "duplicate-key":
        encoded = json.dumps(data, ensure_ascii=False)
        first_key = next(iter(data))
        path.write_text(
            "{"
            + json.dumps(first_key)
            + ":"
            + json.dumps("POISON")
            + ","
            + encoded[1:],
            encoding="utf-8",
        )
        return

    assert mode == "unknown-support"
    assert _replace_nested_key(
        data,
        "support_memory_uids",
        ["missing-memory-POISON"],
    ) == 1
    assert _replace_nested_key(
        data,
        "best_supported_reading",
        "POISON reading",
    ) == 1
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize(
    "corruption",
    ["malformed", "duplicate-key", "unknown-support"],
)
def test_invalid_cache_is_never_rendered_and_a_fresh_result_repairs_it(
    isolated_store,
    monkeypatch,
    corruption,
):
    _, ctx, target, _, _ = _setup_context(
        f"rationale-corrupt-{corruption}"
    )
    original = RationaleProvider("ORIGINAL")
    _patch_provider(monkeypatch, original)
    assert invoke("rationale", target.uid).exit_code == 0
    path = rationale_inference_path(ctx.uid, target.uid)
    _corrupt_cache(path, corruption)

    repair = RationaleProvider("REPAIRED")
    _patch_provider(monkeypatch, repair)
    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert "REPAIRED reading" in result.output
    assert "POISON" not in result.output
    assert len(repair.calls) == 1

    _forbid_provider(monkeypatch)
    reused = invoke("rationale", target.uid)
    assert reused.exit_code == 0, reused.output
    assert "REPAIRED reading" in reused.output
    assert "Reused cached inference" in reused.output


@pytest.mark.parametrize(
    "failure_mode",
    ["provider-failure", "invalid-output"],
)
def test_failed_or_invalid_provider_result_is_not_cached(
    isolated_store,
    monkeypatch,
    failure_mode,
):
    _, ctx, target, _, _ = _setup_context(
        f"rationale-bad-{failure_mode}"
    )
    provider = BadRationaleProvider(failure_mode)
    _patch_provider(monkeypatch, provider)

    result = invoke("rationale", target.uid, "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["inference"] is None
    assert payload["inference_cached"] is False
    assert "POISON" not in result.output
    assert provider.calls == 1
    assert not rationale_inference_path(ctx.uid, target.uid).exists()


@pytest.mark.parametrize(
    "failure_mode",
    ["provider-failure", "invalid-output"],
)
def test_failed_refresh_preserves_the_previous_cache(
    isolated_store,
    monkeypatch,
    failure_mode,
):
    _, ctx, target, _, _ = _setup_context(
        f"rationale-refresh-{failure_mode}"
    )
    original = RationaleProvider("PRESERVED")
    _patch_provider(monkeypatch, original)
    assert invoke("rationale", target.uid).exit_code == 0
    path = rationale_inference_path(ctx.uid, target.uid)
    before = path.read_bytes()

    failing = BadRationaleProvider(failure_mode)
    _patch_provider(monkeypatch, failing)
    refreshed = invoke("rationale", target.uid, "--refresh", "--json")

    assert refreshed.exit_code == 0, refreshed.output
    payload = json.loads(refreshed.output)
    assert payload["inference"] is None
    assert payload["inference_cached"] is False
    assert "POISON" not in refreshed.output
    assert path.read_bytes() == before

    _forbid_provider(monkeypatch)
    reused = invoke("rationale", target.uid, "--json")
    assert reused.exit_code == 0, reused.output
    payload = json.loads(reused.output)
    assert payload["inference_cached"] is True
    assert payload["inference"]["best_supported_reading"] == (
        "PRESERVED reading"
    )


def test_recorded_only_does_not_read_write_or_render_an_existing_cache(
    isolated_store,
    monkeypatch,
):
    _, ctx, target, _, _ = _setup_context()
    provider = RationaleProvider("CACHED")
    _patch_provider(monkeypatch, provider)
    assert invoke("rationale", target.uid).exit_code == 0
    path = rationale_inference_path(ctx.uid, target.uid)
    before = path.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("recorded-only must not access inference cache")

    monkeypatch.setattr(
        rationale_module,
        "load_rationale_inference",
        forbidden,
    )
    monkeypatch.setattr(
        rationale_module,
        "save_rationale_inference",
        forbidden,
    )
    _forbid_provider(monkeypatch)

    result = invoke("rationale", target.uid, "--recorded-only", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["inference"] is None
    assert payload["inference_cached"] is False
    assert path.read_bytes() == before


def test_cache_publication_failure_keeps_the_valid_inference_available(
    isolated_store,
    monkeypatch,
):
    _, _, target, _, _ = _setup_context("rationale-cache-write-failure")
    provider = RationaleProvider("UNCACHED")
    _patch_provider(monkeypatch, provider)

    def unavailable(*args, **kwargs):
        raise OSError("simulated cache storage failure")

    monkeypatch.setattr(
        rationale_module,
        "save_rationale_inference",
        unavailable,
    )

    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert "UNCACHED reading" in result.output
    assert "not cached because cache storage was unavailable" in result.output
    assert len(provider.calls) == 1


def test_legacy_context_identity_disables_cache_without_blocking_inference(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("rationale-cache-legacy")
    ctx.uid = "legacy-context-identity"
    target, _ = ops.add_many(ctx, ["Legacy target.", "Visible support."])
    store.save(ctx)
    store.set_current(ctx.name)
    provider = RationaleProvider("LEGACY")
    _patch_provider(monkeypatch, provider)

    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert "LEGACY reading" in result.output
    assert "caching is unavailable for this Context" in result.output
    assert len(provider.calls) == 1


def test_cache_path_hashes_arbitrary_memory_uid_and_uses_runtime_store_root(
    isolated_store,
    monkeypatch,
    tmp_path,
):
    context_uid = str(uuid.uuid4())
    selected_uid = "../legacy/Memory uid with spaces/기억"
    support_uid = str(uuid.uuid4())
    digest = rationale_inference_input_digest(
        context_uid=context_uid,
        selected_memory_uid=selected_uid,
        prompt="exact provider prompt",
        output_schema={"type": "object"},
    )
    inference = CachedRationaleInference(
        best_supported_reading="A bounded reading.",
        contextual_flow="A bounded contextual flow.",
        support_memory_uids=(support_uid,),
        unresolved=("Intent remains unknown.",),
    )

    save_rationale_inference(
        context_uid,
        selected_uid,
        digest,
        inference,
    )
    first = rationale_inference_path(context_uid, selected_uid)

    assert first.is_relative_to(isolated_store)
    assert hashlib.sha256(selected_uid.encode("utf-8")).hexdigest() in first.name
    assert selected_uid not in str(first)
    assert load_rationale_inference(
        context_uid,
        selected_uid,
        digest,
    ) == inference

    other_root = tmp_path / "other-profile"
    monkeypatch.setattr(store_module, "STORE_DIR", other_root)
    second = rationale_inference_path(context_uid, selected_uid)
    assert second.is_relative_to(other_root)
    assert second.name == first.name
    assert load_rationale_inference(
        context_uid,
        selected_uid,
        digest,
    ) is None


def test_query_only_source_is_neither_opened_nor_copied_into_cache(
    isolated_store,
    monkeypatch,
):
    secret = "QUERY-ONLY SECRET MUST NOT ENTER RATIONALE CACHE"
    store = MemoryStore()
    ctx = ops.init("rationale-query-boundary")
    target = ops.add(ctx, "Explain this direct fragment.")
    source = store.create_query_source("restricted", secret)
    ops.reference_query_context("restricted", source.uid, ctx)
    ops.add(ctx, "Visible direct support only.")
    store.save(ctx)
    store.set_current(ctx.name)

    def forbidden(*args, **kwargs):
        raise AssertionError("rationale opened a query-only source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)
    provider = RationaleProvider("VISIBLE")
    _patch_provider(monkeypatch, provider)

    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert secret not in result.output
    assert secret not in json.dumps(provider.calls)
    cached = rationale_inference_path(ctx.uid, target.uid).read_text(
        encoding="utf-8"
    )
    assert secret not in cached


def test_context_delete_removes_its_rationale_inference_cache(
    isolated_store,
    monkeypatch,
):
    store, ctx, target, _, _ = _setup_context()
    provider = RationaleProvider("DELETE-ME")
    _patch_provider(monkeypatch, provider)
    assert invoke("rationale", target.uid).exit_code == 0
    path = rationale_inference_path(ctx.uid, target.uid)
    assert path.is_file()

    store.delete(ctx.name)

    assert not path.exists()
