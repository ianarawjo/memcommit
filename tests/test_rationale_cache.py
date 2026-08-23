"""Semantic-provenance ``mem rationale`` and legacy-cache compatibility tests."""

from __future__ import annotations

import hashlib
import json
import uuid

from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.rationale as rationale_module
import memcommit.store as store_module
from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Memory
from memcommit.rationale_cache import (
    CachedRationaleInference,
    load_rationale_inference,
    rationale_inference_input_digest,
    rationale_inference_path,
    save_rationale_inference,
)
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def _setup_context(name: str = "rationale-provenance"):
    store = MemoryStore()
    context = ops.init(name)
    target = ops.add(context, "기록된 이유를 확인할 대상 Memory다.")
    ops.add(context, "Rationale이 열지 않아야 할 주변 Memory다.")
    store.save(context)
    store.set_current(context.name)
    return store, context, target


def _forbid_legacy_cache(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("provenance-only rationale touched inference cache")

    monkeypatch.setattr(rationale_module, "load_rationale_inference", forbidden)
    monkeypatch.setattr(rationale_module, "save_rationale_inference", forbidden)


def test_cli_is_provenance_only_and_never_reads_or_writes_inference_cache(
    isolated_store,
    monkeypatch,
):
    _, context, target = _setup_context()
    digest = rationale_inference_input_digest(
        context_uid=context.uid,
        selected_memory_uid=target.uid,
        prompt="legacy prompt that must stay unread",
        output_schema={"type": "object"},
    )
    save_rationale_inference(
        context.uid,
        target.uid,
        digest,
        CachedRationaleInference(
            explanation="LEGACY APPARENT PURPOSE MUST NOT RENDER",
            support_memory_uids=(),
        ),
    )
    _forbid_legacy_cache(monkeypatch)

    result = invoke("rationale", target.uid)
    structured = invoke("rationale", target.uid, "--json")

    assert result.exit_code == 0, result.output
    assert structured.exit_code == 0, structured.output
    assert "PROVENANCE\n" in result.output
    assert "retained" in result.output
    assert "APPARENT PURPOSE" not in result.output
    assert "LEGACY APPARENT" not in result.output
    payload = json.loads(structured.output)
    assert payload["inference"] is None
    assert payload["inference_cached"] is False
    assert payload["inference_status"] == "NOT_REQUESTED"
    assert payload["fallback_evidence"] == []
    assert payload["character_budgets"]["inference_source"] == 0
    assert payload["character_budgets"]["inference_limit"] == 0


def test_inference_options_are_removed_from_rationale_help(isolated_store):
    help_result = invoke("rationale", "--help")
    recorded_only = invoke("rationale", "--recorded-only")
    refresh = invoke("rationale", "--refresh")

    assert help_result.exit_code == 0, help_result.output
    assert "--recorded-only" not in help_result.output
    assert "--refresh" not in help_result.output
    assert recorded_only.exit_code == 2
    assert refresh.exit_code == 2


def test_natural_provenance_projection_uses_the_requested_word_limit(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("rationale-long-provenance")
    source = ops.add(
        context,
        "다듬기 요청을 받으면 문서 전체를 다시 작성하고 인용 표시도 정리한다.",
    )
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="긴 Memory 추가"),
    )
    source_position = context.ordered_uids().index(source.uid)
    context.remove(source.uid)
    target = Memory(
        uid="10000000-0000-4000-8000-000000000001",
        content=(
            "다듬기 요청을 받으면 기존 구조와 인용 표시를 보존하고, "
            "명시된 표현만 수정한다."
        ),
    )
    context.add(target, position=source_position)
    reason = (
        "초기 검토에서는 요청 범위가 모호해 문서 전체가 다시 작성될 가능성이 있었다. "
        "그래서 구조와 인용 표시를 보존하고 명시적으로 지적된 표현만 수정한다는 "
        "경계를 남겼다. 이 기록은 이후의 다듬기 요청에서도 변경 범위를 일관되게 "
        "판단하고, 검토자가 원하지 않은 내용 삭제나 재구성을 피하기 위한 근거로 "
        "사용된다."
    )
    store.save(
        context,
        AutoCheckpoint(
            command="atomize",
            args={
                "trace": {
                    "schema_version": 1,
                    "operation_id": "long-rationale-operation",
                    "changes": [
                        {
                            "kind": "SPLIT",
                            "source_uids": [source.uid],
                            "result_uids": [target.uid],
                            "reason": reason,
                            "reason_codes": ["A01_ONE_FOCUS"],
                        }
                    ],
                }
            },
            description="긴 기록 이유 적용",
        ),
    )
    store.set_current(context.name)
    _forbid_legacy_cache(monkeypatch)

    result = invoke("rationale", target.uid, "--limit", "4", "--unit", "words")
    structured = invoke(
        "rationale",
        target.uid,
        "--limit",
        "4",
        "--unit",
        "words",
        "--json",
    )

    assert result.exit_code == 0, result.output
    assert structured.exit_code == 0, structured.output
    payload = json.loads(structured.output)
    projection = payload["provenance_projection"]
    assert projection["unit"] == "words"
    assert projection["limit"] == 4
    assert projection["length"] <= 4
    assert projection["ruleset_version"] == "rationale-natural-provenance-v5"
    lines = result.output.splitlines()
    heading = "PROVENANCE"
    provenance = lines[lines.index(heading) + 1].strip()
    assert len(provenance.split()) <= 4
    assert provenance == "Recorded provenance."
    assert reason not in result.output
    assert "APPARENT PURPOSE" not in result.output


def test_query_only_source_is_not_opened_by_provenance_only_rationale(
    isolated_store,
    monkeypatch,
):
    secret = "QUERY-ONLY SECRET MUST NOT ENTER RATIONALE"
    store = MemoryStore()
    context = ops.init("rationale-query-boundary")
    target = ops.add(context, "이 직접 Memory의 기록 이유를 보여준다.")
    source = store.create_query_source("restricted", secret)
    ops.reference_query_context("restricted", source.uid, context)
    ops.add(context, "보이는 직접 Memory")
    store.save(context)
    store.set_current(context.name)

    def forbidden(*args, **kwargs):
        raise AssertionError("rationale opened a query-only source")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)

    result = invoke("rationale", target.uid)

    assert result.exit_code == 0, result.output
    assert secret not in result.output
    assert not rationale_inference_path(context.uid, target.uid).exists()


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
        explanation="A legacy validated inference retained for compatibility.",
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
    assert (
        load_rationale_inference(
            context_uid,
            selected_uid,
            digest,
        )
        == inference
    )

    other_root = tmp_path / "other-profile"
    monkeypatch.setattr(store_module, "STORE_DIR", other_root)
    second = rationale_inference_path(context_uid, selected_uid)
    assert second.is_relative_to(other_root)
    assert second.name == first.name
    assert (
        load_rationale_inference(
            context_uid,
            selected_uid,
            digest,
        )
        is None
    )


def test_context_delete_removes_a_legacy_rationale_inference_cache(
    isolated_store,
):
    store, context, target = _setup_context("rationale-cache-delete")
    digest = rationale_inference_input_digest(
        context_uid=context.uid,
        selected_memory_uid=target.uid,
        prompt="legacy deletion prompt",
        output_schema={"type": "object"},
    )
    save_rationale_inference(
        context.uid,
        target.uid,
        digest,
        CachedRationaleInference(
            explanation="Delete this compatibility record with its Context.",
            support_memory_uids=(),
        ),
    )
    cache_path = rationale_inference_path(context.uid, target.uid)
    assert cache_path.is_file()

    store.delete(context.name)

    assert not cache_path.exists()
