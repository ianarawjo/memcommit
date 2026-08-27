"""Shared Find/Query search over durable profile-local activity evidence."""

import json

from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.search.command import (
    _collect_find_frame_candidates,
    _load_find_frame_roots,
)
from memcommit.core.context import AutoCheckpoint
from memcommit.application.operations.meld.model import MeldSession
from memcommit.application.operations.rationale.cache import (
    CachedRationaleInference,
    save_rationale_inference,
)
from memcommit.application.operations.search.model import SearchArtifact
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class _QueryAnswerProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "ordinary query"
        payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
        artifact_alias = next(
            item["alias"]
            for item in payload["complete_frozen_corpus"]
            if item["type"] == "artifact" and "advisor1" in item["content"]
        )
        return json.dumps(
            {
                "outcome_kind": "ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "Advisor 1 and Advisor 2 were merged into this Context.",
                        "source_aliases": [artifact_alias],
                    }
                ],
            }
        )


def _saved_meld_trace(store: MemoryStore):
    ctx = ops.init("workspace")
    ops.add(ctx, "Merged proposal result")
    store.save(
        ctx,
        auto_checkpoint=AutoCheckpoint(
            command="meld",
            args={"target": "workspace"},
            description="Melded advisor1 and advisor2 into workspace",
        ),
    )
    store.set_current(ctx.name)
    return ctx


def test_find_frame_includes_checkpoint_trace_artifacts(isolated_store):
    store = MemoryStore()
    ctx = _saved_meld_trace(store)
    roots = _load_find_frame_roots(
        store,
        store.load(ctx.name),
        recursive=True,
        resolve_embeds=True,
    )

    candidates = _collect_find_frame_candidates(
        store,
        roots,
        recursive=True,
        include_artifacts=True,
    )

    artifacts = [
        candidate.item
        for candidate in candidates
        if isinstance(candidate.item, SearchArtifact)
    ]
    assert len(artifacts) == 1
    assert artifacts[0].artifact_kind == "trace"
    assert "advisor1 and advisor2" in artifacts[0].content


def test_query_single_argument_answers_from_ordinary_search_artifact(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _saved_meld_trace(store)
    provider = _QueryAnswerProvider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.query.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["query", "What changed when advisor1 and advisor2 were merged?"],
    )

    assert result.exit_code == 0
    assert "Advisor 1 and Advisor 2 were merged" in result.output
    # Compact Query References omit kind; the retained checkpoint content is
    # the visible proof that the artifact crossed the search boundary.
    assert "Melded advisor1 and advisor2 into workspace" in result.output


def test_find_frame_includes_retained_meld_and_rationale_artifacts(
    isolated_store,
):
    store = MemoryStore()
    left = ops.init("advisor1")
    ops.add(left, "Advisor one guidance")
    right = ops.init("advisor2")
    ops.add(right, "Advisor two guidance")
    target = ops.init("workspace")
    for context in (left, right, target):
        store.save(context)
    store.set_current(target.name)

    store.save_meld_session(
        MeldSession.create_symmetric(left, right, target),
        expected_session_digest=None,
    )
    memory = ops.add(target, "Combined proposal")
    store.save(target)
    save_rationale_inference(
        target.uid,
        memory.uid,
        "c" * 64,
        CachedRationaleInference(
            explanation=(
                "The merged proposal assigns ownership by following the prior "
                "guidance; no material uncertainty remains."
            ),
            support_memory_uids=(memory.uid,),
        ),
    )

    roots = _load_find_frame_roots(
        store,
        store.load(target.name),
        recursive=True,
        resolve_embeds=True,
    )
    candidates = _collect_find_frame_candidates(
        store,
        roots,
        recursive=True,
        include_artifacts=True,
    )
    kinds = {
        candidate.item.artifact_kind
        for candidate in candidates
        if isinstance(candidate.item, SearchArtifact)
    }

    assert {"meld_session", "rationale"} <= kinds
    assert "query_session" not in kinds


def test_unrelated_invalid_meld_session_does_not_block_search_artifacts(
    isolated_store,
):
    store = MemoryStore()
    selected = ops.init("selected")
    ops.add(selected, "Current selected evidence")
    unrelated = ops.init("unrelated")
    for context in (selected, unrelated):
        store.save(context)
    store._meld_session_path(unrelated.uid).parent.mkdir(parents=True, exist_ok=True)
    store._meld_session_path(unrelated.uid).write_text("{", encoding="utf-8")

    roots = _load_find_frame_roots(
        store,
        store.load(selected.name),
        recursive=True,
        resolve_embeds=True,
    )
    candidates = _collect_find_frame_candidates(
        store,
        roots,
        recursive=True,
        include_artifacts=True,
    )

    assert any(
        candidate.context_name == selected.name
        and candidate.item.content == "Current selected evidence"
        for candidate in candidates
    )
