"""Shared Find/Query search over durable profile-local activity evidence."""

import json
import uuid

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.find import (
    _collect_find_frame_candidates,
    _load_find_frame_roots,
)
from memcommit.context import AutoCheckpoint
from memcommit.meld import MeldSession
from memcommit.query_sessions import QuerySessionBinding, QuerySessionStore
from memcommit.rationale_cache import (
    CachedRationaleInference,
    save_rationale_inference,
)
from memcommit.search import SearchArtifact
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class _QueryAnswerProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation == "find":
            payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
            selected = next(
                candidate["candidate_id"]
                for candidate in payload["candidates"]
                if "advisor1" in candidate.get("content", "")
            )
            return json.dumps(
                {
                    "matches": [{"candidate_id": selected}],
                    "related_query": "",
                    "related_matches": [],
                }
            )
        assert operation == "find answer"
        visible_alias = output_schema["properties"]["visible_sources"]["items"][
            "enum"
        ][0]
        return json.dumps(
            {
                "visible_text": "Advisor 1 and Advisor 2 were merged into this Context.",
                "visible_sources": [visible_alias],
                "context_text": "No additional same-Context evidence was needed.",
                "context_sources": [],
                "outside_text": "Other Contexts were not checked.",
                "outside_sources": [],
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
        "memcommit.commands.query.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["query", "What changed when advisor1 and advisor2 were merged?"],
    )

    assert result.exit_code == 0
    assert "Advisor 1 and Advisor 2 were merged" in result.output
    assert "artifact" in result.output
    assert "Melded advisor1 and advisor2 into workspace" in result.output


def test_find_frame_includes_visible_query_meld_and_rationale_sessions(
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

    query_store = QuerySessionStore(store.store_dir)
    session, digest = query_store.load_or_start(
        "prior-question",
        QuerySessionBinding(
            grant_uid=str(uuid.uuid4()),
            grant_revision=1,
            grant_digest="a" * 64,
            grantee_profile_uid=str(uuid.uuid4()),
            authority_profile_uid=str(uuid.uuid4()),
            attachment_context_uid=target.uid,
            attachment_context_name=target.name,
            resource_uid=str(uuid.uuid4()),
            resource_name="guidelines",
            public_name="guidelines",
            requested_name="guidelines",
            language="en",
            source_digest="b" * 64,
        ),
    )
    assert digest is None
    query_store.append_turn(
        session,
        expected_record_digest=None,
        question="What did the prior guidance say?",
        answer="It required an explicit owner.",
    )
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
            best_supported_reading="The merged proposal assigns ownership.",
            contextual_flow="The ownership rule follows the prior guidance.",
            support_memory_uids=(memory.uid,),
            unresolved=(),
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

    assert {"query_session", "meld_session", "rationale"} <= kinds
