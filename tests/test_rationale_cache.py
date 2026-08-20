"""Durable, exact-input cache contracts for ``mem rationale`` inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unicodedata
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
        semantic_values = [
            payload["target"]["content"],
            *(candidate["content"] for candidate in candidates),
        ]
        saved_analysis = payload["saved_analysis"]
        if saved_analysis is not None:
            semantic_values.extend(
                (
                    saved_analysis["interpretation"],
                    saved_analysis["clarification"],
                    saved_analysis["reason"],
                    saved_analysis["question"],
                    *(item["text"] for item in saved_analysis["readings"]),
                )
            )
        normalized = {
            unicodedata.normalize("NFC", value).strip()
            for value in semantic_values
            if value.strip()
        }
        expected_limit = min(480, sum(map(len, normalized)) - 1)
        assert (
            output_schema["properties"]["explanation"]["maxLength"]
            == expected_limit
        )
        explanation = f"{self.label}: context supports it."
        assert len(explanation) <= expected_limit
        return json.dumps(
            {
                "explanation": explanation,
                "support_ids": [candidates[0]["candidate_id"]],
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
        if self.mode == "over-character-limit":
            assert output_schema is not None
            explanation_limit = output_schema["properties"]["explanation"][
                "maxLength"
            ]
            assert isinstance(explanation_limit, int)
            return json.dumps(
                {
                    "explanation": "P" * (explanation_limit + 1),
                    "support_ids": [],
                }
            )
        if self.mode == "multiple-paragraphs":
            return json.dumps(
                {
                    "explanation": "POISON first.\nPOISON second.",
                    "support_ids": [],
                }
            )
        if self.mode == "control-character":
            return json.dumps(
                {
                    "explanation": "POISON\u0000control",
                    "support_ids": [],
                }
            )
        assert self.mode == "invalid-output"
        return json.dumps(
            {
                "explanation": "POISON reading follows a POISON flow.",
                "support_ids": ["unknown-candidate"],
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
    assert "ORIGINAL: context" in first.output
    assert len(provider.calls) == 1
    assert rationale_inference_path(ctx.uid, target.uid).is_file()

    _forbid_provider(monkeypatch)
    reused = invoke("rationale", target.uid)
    structured = invoke("rationale", target.uid, "--json")

    assert reused.exit_code == 0, reused.output
    assert "ORIGINAL: context" in reused.output
    assert "· cached" in reused.output
    assert structured.exit_code == 0, structured.output
    payload = json.loads(structured.output)
    assert payload["inference_cached"] is True
    assert payload["inference"]["explanation"] == (
        "ORIGINAL: context supports it."
    )
    budgets = payload["character_budgets"]
    explanation = payload["inference"]["explanation"]
    assert len(explanation) <= budgets["inference_limit"]
    assert budgets["inference_limit"] < budgets["inference_source"]


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
    assert "REFRESHED: context" in refreshed.output
    assert "· cached" not in refreshed.output
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
    assert payload["inference"]["explanation"] == (
        "REFRESHED: context supports it."
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
    assert "AFTER: context" in result.output
    assert "· cached" not in result.output
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
        "explanation",
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
    assert "REPAIRED: context" in result.output
    assert "POISON" not in result.output
    assert len(repair.calls) == 1

    _forbid_provider(monkeypatch)
    reused = invoke("rationale", target.uid)
    assert reused.exit_code == 0, reused.output
    assert "REPAIRED: context" in reused.output
    assert "· cached" in reused.output


@pytest.mark.parametrize(
    "failure_mode",
    [
        "provider-failure",
        "invalid-output",
        "over-character-limit",
        "multiple-paragraphs",
        "control-character",
    ],
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
    assert payload["inference"]["explanation"] == (
        "PRESERVED: context supports it."
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


def test_tiny_semantic_frame_skips_provider_and_emits_only_status(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("rationale-tiny-evidence")
    target, _neighbor = ops.add_many(ctx, ["A", "B"])
    store.save(ctx)
    store.set_current(ctx.name)
    _forbid_provider(monkeypatch)

    result = invoke("rationale", target.uid)
    structured = invoke("rationale", target.uid, "--json")

    assert result.exit_code == 0, result.output
    assert "INFERENCE — insufficient evidence" in result.output
    assert "available semantic evidence" not in result.output
    assert structured.exit_code == 0, structured.output
    payload = json.loads(structured.output)
    assert payload["inference_status"] == "INSUFFICIENT_EVIDENCE"
    budgets = payload["character_budgets"]
    assert budgets["inference_source"] == 2
    assert budgets["inference_limit"] == 1
    assert budgets["provenance_limit"] < budgets["provenance_source"]
    assert not rationale_inference_path(ctx.uid, target.uid).exists()


def test_nfc_equivalent_evidence_counts_once_before_provider_planning(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("rationale-nfc-budget")
    target, _neighbor = ops.add_many(ctx, ["e\u0301", "é"])
    store.save(ctx)
    store.set_current(ctx.name)
    _forbid_provider(monkeypatch)

    result = invoke("rationale", target.uid, "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["inference_status"] == "INSUFFICIENT_EVIDENCE"
    assert payload["character_budgets"]["inference_source"] == 1
    assert payload["character_budgets"]["inference_limit"] == 0


def test_inference_minimum_boundary_skips_15_but_accepts_16_characters(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    below = ops.init("rationale-below-minimum")
    below_target, _ = ops.add_many(below, ["12345678", "abcdefgh"])
    store.save(below)
    store.set_current(below.name)
    _forbid_provider(monkeypatch)

    rejected = invoke("rationale", below_target.uid, "--json")

    assert rejected.exit_code == 0, rejected.output
    rejected_payload = json.loads(rejected.output)
    assert rejected_payload["inference_status"] == "INSUFFICIENT_EVIDENCE"
    assert rejected_payload["character_budgets"]["inference_source"] == 16
    assert rejected_payload["character_budgets"]["inference_limit"] == 15

    accepted = ops.init("rationale-at-minimum")
    accepted_target, _ = ops.add_many(accepted, ["12345678", "abcdefghi"])
    store.save(accepted)
    store.set_current(accepted.name)
    calls: list[int] = []

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "rationale inference"
            assert output_schema is not None
            limit = output_schema["properties"]["explanation"]["maxLength"]
            calls.append(limit)
            candidate = json.loads(prompt.split(RATIONALE_MARKER, 1)[1])[
                "candidates"
            ][0]
            return json.dumps(
                {
                    "explanation": "0123456789ABCDEF",
                    "support_ids": [candidate["candidate_id"]],
                }
            )

    _patch_provider(monkeypatch, Provider())
    accepted_result = invoke("rationale", accepted_target.uid, "--json")

    assert accepted_result.exit_code == 0, accepted_result.output
    accepted_payload = json.loads(accepted_result.output)
    assert calls == [16]
    assert accepted_payload["inference_status"] == "AVAILABLE"
    assert accepted_payload["character_budgets"]["inference_source"] == 17
    assert accepted_payload["character_budgets"]["inference_limit"] == 16
    assert accepted_payload["inference"]["explanation"] == "0123456789ABCDEF"


def test_terminal_escaping_cannot_expand_visible_inference_past_its_limit(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("rationale-terminal-escape")
    target, _ = ops.add_many(ctx, ["12345678", "abcdefghi"])
    store.save(ctx)
    store.set_current(ctx.name)

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            candidate = json.loads(prompt.split(RATIONALE_MARKER, 1)[1])[
                "candidates"
            ][0]
            return json.dumps(
                {
                    "explanation": "123456789012345\u202e",
                    "support_ids": [candidate["candidate_id"]],
                }
            )

    _patch_provider(monkeypatch, Provider())

    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert "\u202e" not in result.output
    lines = result.output.splitlines()
    inference_index = lines.index("INFERENCE — within Context, not recorded")
    visible_explanation = lines[inference_index + 2].strip()
    assert len(visible_explanation) <= 16


def test_absolute_480_character_boundary_accepts_exact_and_rejects_one_more(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("rationale-absolute-boundary")
    target, _ = ops.add_many(ctx, ["T" * 300, "N" * 300])
    store.save(ctx)
    store.set_current(ctx.name)
    limits: list[int] = []

    class ExactProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert output_schema is not None
            limit = output_schema["properties"]["explanation"]["maxLength"]
            limits.append(limit)
            candidate = json.loads(prompt.split(RATIONALE_MARKER, 1)[1])[
                "candidates"
            ][0]
            return json.dumps(
                {
                    "explanation": "X" * limit,
                    "support_ids": [candidate["candidate_id"]],
                }
            )

    _patch_provider(monkeypatch, ExactProvider())
    exact = invoke("rationale", target.uid, "--json")

    assert exact.exit_code == 0, exact.output
    exact_payload = json.loads(exact.output)
    assert limits == [480]
    assert len(exact_payload["inference"]["explanation"]) == 480
    cache_path = rationale_inference_path(ctx.uid, target.uid)
    cached_before = cache_path.read_bytes()

    too_long = BadRationaleProvider("over-character-limit")
    _patch_provider(monkeypatch, too_long)
    rejected = invoke("rationale", target.uid, "--refresh", "--json")

    assert rejected.exit_code == 0, rejected.output
    rejected_payload = json.loads(rejected.output)
    assert rejected_payload["inference"] is None
    assert rejected_payload["inference_status"] == "UNAVAILABLE"
    assert cache_path.read_bytes() == cached_before

    _forbid_provider(monkeypatch)
    reused = invoke("rationale", target.uid, "--json")
    assert reused.exit_code == 0, reused.output
    assert len(json.loads(reused.output)["inference"]["explanation"]) == 480


def test_oversized_context_reduces_candidates_and_keeps_output_at_480(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("rationale-oversized-context")
    contents = ["Large target."] + [
        f"{index:03d}" + (chr(65 + index % 26) * 9_997)
        for index in range(105)
    ]
    target, *_ = ops.add_many(ctx, contents)
    store.save(ctx)
    store.set_current(ctx.name)
    observed: dict[str, object] = {}

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert output_schema is not None
            payload = json.loads(prompt.split(RATIONALE_MARKER, 1)[1])
            observed["candidate_count"] = len(payload["candidates"])
            observed["context_scope"] = payload["context_scope"]
            observed["limit"] = output_schema["properties"]["explanation"][
                "maxLength"
            ]
            return json.dumps(
                {
                    "explanation": "L" * 480,
                    "support_ids": [payload["candidates"][0]["candidate_id"]],
                }
            )

    _patch_provider(monkeypatch, Provider())
    structured = invoke("rationale", target.uid, "--json")

    assert structured.exit_code == 0, structured.output
    payload = json.loads(structured.output)
    assert 0 < observed["candidate_count"] < 105
    assert observed["context_scope"].startswith("nearest readable subtree")
    assert observed["limit"] == 480
    assert len(payload["inference"]["explanation"]) == 480
    assert any("nearest-Memory subset" in item for item in payload["warnings"])


def test_long_provenance_projection_is_capped_at_320_characters(
    isolated_store,
    monkeypatch,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    ctx = ops.init("rationale-long-provenance")
    target = ops.add(ctx, "Initial " + ("A" * 240))
    store.save(
        ctx,
        AutoCheckpoint(command="add", args={}, description="Added long Memory"),
    )
    for index in range(12):
        content = f"Revision {index:02d} " + (chr(66 + index) * 240)
        ops.edit(ctx, target.uid, content)
        store.save(
            ctx,
            AutoCheckpoint(
                command="edit",
                args={"uid": target.uid, "content": content},
                description=f"Long revision {index:02d}",
            ),
        )
    store.set_current(ctx.name)
    _forbid_provider(monkeypatch)

    result = invoke("rationale", target.uid, "--recorded-only")
    structured = invoke(
        "rationale",
        target.uid,
        "--recorded-only",
        "--json",
    )

    assert result.exit_code == 0, result.output
    assert structured.exit_code == 0, structured.output
    payload = json.loads(structured.output)
    budgets = payload["character_budgets"]
    assert budgets["provenance_source"] > 320
    assert budgets["provenance_limit"] == 320
    lines = result.output.splitlines()
    provenance = lines[lines.index("PROVENANCE") + 1].strip()
    assert len(provenance) <= 320
    assert "INFERENCE — not requested" in result.output


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
    assert "UNCACHED: context" in result.output
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
    assert "LEGACY: context" in result.output
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
        explanation=(
            "A bounded reading follows the available contextual flow, while "
            "the author's intent remains unknown."
        ),
        support_memory_uids=(support_uid,),
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
