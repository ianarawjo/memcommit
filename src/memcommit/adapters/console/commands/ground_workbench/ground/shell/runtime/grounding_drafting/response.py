"""Freeze one ASK or PROPOSE response into blank-Ground drafting values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.adapters.console.commands.ground_workbench.ground.shell.proposal import (
    GroundShellContextSuggestion,
    GroundShellMemoryDraft,
    GroundShellNewContextSuggestion,
    GroundShellProposal,
    GroundShellRuleDraft,
    _field,
    _freeze_context_suggestions,
    _freeze_memory_drafts,
    _freeze_new_context_suggestions,
    _freeze_proposal,
    _freeze_rule_drafts,
    _required_text,
    _response_kind,
)


@dataclass(frozen=True)
class GroundingDraftResponse:
    """Validated semantic output from one conversation-driven drafting turn."""

    kind: Literal["ASK", "PROPOSE"]
    understanding: str
    question: str
    context_suggestions: tuple[GroundShellContextSuggestion, ...]
    new_context_suggestions: tuple[GroundShellNewContextSuggestion, ...]
    rule_drafts: tuple[GroundShellRuleDraft, ...]
    memory_drafts: tuple[GroundShellMemoryDraft, ...]
    proposal: GroundShellProposal | None


def freeze_grounding_response(
    response: object,
    *,
    planned_ground_name: str | None,
    context_catalog_count: int,
) -> GroundingDraftResponse:
    """Validate provider output before it gains process-local UI authority."""

    kind = _response_kind(response)
    understanding = _required_text(
        _field(response, "understanding"),
        "understanding",
    )
    question = _required_text(
        _field(response, "question"),
        "question",
    )
    contexts = _freeze_context_suggestions(response)
    new_contexts = _freeze_new_context_suggestions(response)
    if planned_ground_name is not None and (contexts or new_contexts):
        raise ValueError(
            "Chat response added Context recommendations after the exact "
            "Ground Save Location was fixed."
        )
    rules = _freeze_rule_drafts(response)
    memories = _freeze_memory_drafts(
        response,
        rule_draft_count=len(rules),
    )
    if bool(contexts) != bool(context_catalog_count):
        raise ValueError("Chat response has invalid Context suggestions.")
    proposal = (
        None
        if kind == "ASK"
        else _freeze_proposal(
            response,
            expected_ground_name=planned_ground_name,
        )
    )
    return GroundingDraftResponse(
        kind=kind,
        understanding=understanding,
        question=question,
        context_suggestions=contexts,
        new_context_suggestions=new_contexts,
        rule_drafts=rules,
        memory_drafts=memories,
        proposal=proposal,
    )
