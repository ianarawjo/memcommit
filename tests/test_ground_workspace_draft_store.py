from __future__ import annotations

import os

import pytest

from memcommit.ground_workspace_draft import (
    GroundWorkspaceDraft,
    GroundWorkspaceDraftError,
    GroundWorkspaceMemoryDraft,
    GroundWorkspaceRuleDraft,
    ground_workspace_draft_digest,
)
from memcommit.ground_workspace_draft_store import GroundWorkspaceDraftStore
from memcommit.store import ConcurrentContextUpdateError, MemoryStore


def _draft(name: str = "projects/ticker-ground") -> GroundWorkspaceDraft:
    return GroundWorkspaceDraft.create(
        workspace_name=name,
        goal="Find how real US ticker symbols are assigned.",
        understanding="Use actual US-listed companies.",
        question="Approve this Goal?",
        submitted_turns=("I want to understand real ticker assignment.",),
    )


def test_hidden_draft_round_trip_creates_no_context_or_checkpoint(
    isolated_store,
):
    store = MemoryStore()
    drafts = GroundWorkspaceDraftStore(store)
    draft = _draft()

    drafts.save(draft, expected_digest=None)

    assert drafts.load(draft.uid) == draft
    assert drafts.list() == (draft,)
    assert store.list_context_names() == []
    assert not (isolated_store / "contexts" / "projects").exists()
    assert (os.stat(drafts.path(draft.uid)).st_mode & 0o777) == 0o600
    assert (os.stat(drafts.directory).st_mode & 0o777) == 0o700


def test_hidden_draft_update_and_delete_require_exact_cas(isolated_store):
    store = MemoryStore()
    drafts = GroundWorkspaceDraftStore(store)
    original = _draft()
    drafts.save(original, expected_digest=None)
    revised = original.revise(
        workspace_name=original.workspace_name,
        goal="Explain how real US ticker symbols are assigned.",
        understanding="The Goal now asks for an explanation.",
        question="Keep this revision?",
        submitted_turns=(
            *original.submitted_turns,
            "Explain the assignment process too.",
        ),
        rule_drafts=(),
        memory_drafts=(),
    )

    with pytest.raises(ConcurrentContextUpdateError, match="changed"):
        drafts.save(revised, expected_digest="0" * 64)

    drafts.save(
        revised,
        expected_digest=ground_workspace_draft_digest(original),
    )
    assert drafts.load(original.uid) == revised

    with pytest.raises(ConcurrentContextUpdateError, match="changed"):
        drafts.delete(original.uid, expected_digest="0" * 64)

    drafts.delete(
        original.uid,
        expected_digest=ground_workspace_draft_digest(revised),
    )
    assert drafts.list() == ()


def test_hidden_drafts_reject_duplicate_save_locations(isolated_store):
    store = MemoryStore()
    drafts = GroundWorkspaceDraftStore(store)
    drafts.save(_draft(), expected_digest=None)

    with pytest.raises(ConcurrentContextUpdateError, match="Save Location"):
        drafts.save(_draft(), expected_digest=None)


def test_hidden_draft_preserves_multiline_turns_and_source_spans(
    isolated_store,
):
    source = "Apple Inc.\nuses AAPL."
    draft = GroundWorkspaceDraft.create(
        workspace_name="projects/ticker-ground",
        goal="Find how real US ticker symbols are assigned.",
        understanding="Use actual\nUS-listed companies.",
        question="Approve this Goal?",
        submitted_turns=("Apple Inc.\nuses AAPL.",),
        rule_drafts=(
            GroundWorkspaceRuleDraft(
                content="uses AAPL",
                rationale="Directly supplied.",
                origin="USER_EXACT",
                source_spans=(source,),
            ),
        ),
    )
    drafts = GroundWorkspaceDraftStore(MemoryStore())

    drafts.save(draft, expected_digest=None)

    assert drafts.load(draft.uid) == draft


def test_hidden_draft_revalidates_unresolved_agent_memory_boundary():
    with pytest.raises(GroundWorkspaceDraftError, match="disposition"):
        GroundWorkspaceMemoryDraft(
            content="Apple Inc. maps to AAPL.",
            expected="AAPL",
            rationale="Agent suggestion.",
            case_role="FIT",
            disposition="INCLUDE",
            rule_draft_index=0,
            origin="AGENT_SUGGESTED",
        )
