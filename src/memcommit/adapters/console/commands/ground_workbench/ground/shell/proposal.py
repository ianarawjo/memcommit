"""Frozen proposal contracts and validation for the blank-Ground shell."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.adapters.console.terminal.components.command_editor.model import CommandReview
from memcommit.adapters.console.terminal.components.command_editor.rendering import (
    format_exact_command,
)
from memcommit.application.operations.ground_workbench.ground.contracts import (
    GroundError,
    validate_ground_contract_name,
    validate_ground_goal,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name


_CONTEXT_SUGGESTION_ROLES = {
    "MAIN",
    "ALTERNATIVE",
}


class GroundInterpreter(Protocol):
    """A semantic adapter that returns an ASK or PROPOSE object."""

    def __call__(self, text: str) -> object: ...


@dataclass(frozen=True)
class GroundShellContextSuggestion:
    """One display-only Context hypothesis returned by the interpreter."""

    context_name: str
    role: str
    reason: str


@dataclass(frozen=True)
class GroundShellNewContextSuggestion:
    """One display-only fresh Context name; never an implicit init."""

    context_name: str
    reason: str


@dataclass(frozen=True)
class GroundShellRuleDraft:
    """One unsaved, process-local Rule preview."""

    content: str
    rationale: str
    origin: str
    source_spans: tuple[str, ...]


@dataclass(frozen=True)
class GroundShellMemoryDraft:
    """One unsaved input-to-output Case preview."""

    content: str
    expected: str
    rationale: str
    case_role: str
    disposition: str
    rule_draft_index: int
    origin: str
    source_spans: tuple[str, ...]


@dataclass(frozen=True)
class GroundShellProposal:
    """The immutable Ground creation fields displayed for approval."""

    ground_name: str
    goal: str
    understanding: str
    question: str
    context_suggestions: tuple[GroundShellContextSuggestion, ...] = ()
    new_context_suggestions: tuple[
        GroundShellNewContextSuggestion, ...
    ] = ()
    rule_drafts: tuple[GroundShellRuleDraft, ...] = ()
    memory_drafts: tuple[GroundShellMemoryDraft, ...] = ()


class GroundApplier(Protocol):
    """An execution adapter for one already-approved structured proposal."""

    def __call__(self, proposal: GroundShellProposal) -> object: ...


@dataclass(frozen=True)
class GroundShellResult:
    """Terminal outcome of one blank-Ground shell."""

    status: Literal["APPLIED", "CANCELLED", "BACK_TO_PICKER"]
    proposal: GroundShellProposal | None = None
    actual_output: str | None = None
    submitted_turns: tuple[str, ...] = ()
    selected_context_names: tuple[str, ...] = ()
    new_context_name_hint: str | None = None


def proposal_argv(proposal: GroundShellProposal) -> tuple[str, ...]:
    """Build the only command shape this initial shell can approve."""
    return (
        "mem",
        "ground",
        proposal.ground_name,
        "--goal",
        proposal.goal,
    )


def format_proposal_command(proposal: GroundShellProposal) -> str:
    """Render exact POSIX argv for review; never execute it as a shell line."""
    return format_exact_command(_proposal_review(proposal))


def _proposal_review(
    proposal: GroundShellProposal,
    *,
    has_local_new_context: bool = False,
) -> CommandReview:
    if has_local_new_context:
        new_context_effect = "New Context plan: reviewed with this Ground"
    elif proposal.new_context_suggestions:
        new_context_effect = (
            "New Context suggestion: not selected"
        )
    else:
        new_context_effect = "New Context plan: none"
    return CommandReview(
        argv=proposal_argv(proposal),
        effects=(
            f"Ground: CREATE {proposal.ground_name}",
            "Goal: SET",
            "Rules and Ground Memories: none in this draft",
            new_context_effect,
            "Other Contexts will not be edited by this command",
        ),
    )


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Chat response has no {label}.")
    return value.strip()


def _command_text(value: object, label: str) -> str:
    text = _required_text(value, label)
    if any(unicodedata.category(character) == "Cc" for character in text):
        raise ValueError(
            f"Chat response {label} contains a control character."
        )
    return text


def _response_kind(value: object) -> str:
    raw = _field(value, "kind")
    raw = getattr(raw, "value", raw)
    if not isinstance(raw, str):
        raise ValueError("Chat response has no ASK or PROPOSE kind.")
    kind = raw.upper()
    if kind not in {"ASK", "PROPOSE"}:
        raise ValueError("Chat response kind must be ASK or PROPOSE.")
    return kind


def _freeze_proposal(
    response: object,
    *,
    expected_ground_name: str | None = None,
) -> GroundShellProposal:
    nested = _field(response, "proposal")
    source = nested if nested is not None else response
    understanding = _field(response, "understanding")
    if understanding is None:
        understanding = _field(source, "understanding")
    question = _field(response, "question")
    if question is None:
        question = _field(source, "question")
    proposed_ground_name = _command_text(
        _field(source, "ground_name"),
        "Ground name",
    )
    if expected_ground_name is None:
        ground_name = validate_ground_contract_name(proposed_ground_name)
    else:
        ground_name = validate_portable_context_name(expected_ground_name)
        if proposed_ground_name != ground_name:
            raise ValueError(
                "Chat response changed the exact Ground Save Location."
            )
    try:
        goal = validate_ground_goal(
            _command_text(_field(source, "goal"), "Goal"),
            label="Ground goal",
        )
    except GroundError as error:
        raise ValueError(str(error)) from error
    rule_drafts = _freeze_rule_drafts(response)
    return GroundShellProposal(
        ground_name=ground_name,
        goal=goal,
        understanding=_required_text(understanding, "understanding"),
        question=_required_text(question, "question"),
        context_suggestions=_freeze_context_suggestions(response),
        new_context_suggestions=(
            _freeze_new_context_suggestions(response)
        ),
        rule_drafts=rule_drafts,
        memory_drafts=_freeze_memory_drafts(
            response,
            rule_draft_count=len(rule_drafts),
        ),
    )


def _freeze_context_suggestions(
    response: object,
) -> tuple[GroundShellContextSuggestion, ...]:
    raw = _field(response, "context_suggestions", ())
    if (
        not isinstance(raw, Sequence)
        or isinstance(raw, (str, bytes))
        or len(raw) > 4
    ):
        raise ValueError("Chat response has invalid Context suggestions.")
    result: list[GroundShellContextSuggestion] = []
    seen: set[str] = set()
    for candidate in raw:
        context_name = _command_text(
            _field(candidate, "context_name"),
            "Context suggestion name",
        )
        role = _required_text(
            _field(candidate, "role"),
            "Context suggestion role",
        )
        reason = _required_text(
            _field(candidate, "reason"),
            "Context suggestion reason",
        )
        if role not in _CONTEXT_SUGGESTION_ROLES or context_name in seen:
            raise ValueError(
                "Chat response has invalid Context suggestions."
            )
        seen.add(context_name)
        result.append(
            GroundShellContextSuggestion(
                context_name=context_name,
                role=role,
                reason=reason,
            )
        )
    if result and sum(item.role == "MAIN" for item in result) != 1:
        raise ValueError("Chat response has invalid Context suggestions.")
    return tuple(result)
def _freeze_new_context_suggestions(
    response: object,
) -> tuple[GroundShellNewContextSuggestion, ...]:
    raw = _field(response, "new_context_suggestions", ())
    if (
        not isinstance(raw, Sequence)
        or isinstance(raw, (str, bytes))
        or len(raw) > 1
    ):
        raise ValueError(
            "Chat response has invalid new Context suggestions."
        )
    result: list[GroundShellNewContextSuggestion] = []
    for candidate in raw:
        try:
            context_name = validate_portable_context_name(
                _command_text(
                    _field(candidate, "context_name"),
                    "new Context suggestion name",
                )
            )
        except ValueError as error:
            raise ValueError(
                "Chat response has invalid new Context suggestions."
            ) from error
        result.append(
            GroundShellNewContextSuggestion(
                context_name=context_name,
                reason=_required_text(
                    _field(candidate, "reason"),
                    "new Context suggestion reason",
                ),
            )
        )
    return tuple(result)

def _freeze_source_spans(value: object, *, label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) > 4
    ):
        raise ValueError(f"Chat response has invalid {label} spans.")
    spans = tuple(_required_text(span, f"{label} span") for span in value)
    if len(set(spans)) != len(spans):
        raise ValueError(f"Chat response has invalid {label} spans.")
    return spans


def _freeze_rule_drafts(
    response: object,
) -> tuple[GroundShellRuleDraft, ...]:
    raw = _field(response, "rule_drafts", ())
    if (
        not isinstance(raw, Sequence)
        or isinstance(raw, (str, bytes))
        or len(raw) > 4
    ):
        raise ValueError("Chat response has invalid Rule drafts.")
    result: list[GroundShellRuleDraft] = []
    for candidate in raw:
        origin = _required_text(
            _field(candidate, "origin"),
            "Rule draft origin",
        )
        if origin not in {"USER_EXACT", "AGENT_SUGGESTED"}:
            raise ValueError("Chat response has invalid Rule drafts.")
        spans = _freeze_source_spans(
            _field(candidate, "source_spans", ()),
            label="Rule draft source",
        )
        if (origin == "USER_EXACT") != bool(spans):
            raise ValueError("Chat response has invalid Rule drafts.")
        content = _required_text(
            _field(candidate, "content"),
            "Rule draft content",
        )
        if origin == "USER_EXACT" and not any(
            content in span for span in spans
        ):
            raise ValueError("Chat response has invalid Rule drafts.")
        rationale = _field(candidate, "rationale", "")
        if not isinstance(rationale, str):
            raise ValueError("Chat response has invalid Rule drafts.")
        result.append(
            GroundShellRuleDraft(
                content=content,
                rationale=rationale,
                origin=origin,
                source_spans=spans,
            )
        )
    return tuple(result)


def _freeze_memory_drafts(
    response: object,
    *,
    rule_draft_count: int,
) -> tuple[GroundShellMemoryDraft, ...]:
    raw = _field(response, "memory_drafts", ())
    if (
        not isinstance(raw, Sequence)
        or isinstance(raw, (str, bytes))
        or len(raw) > 3
    ):
        raise ValueError("Chat response has invalid Memory drafts.")
    result: list[GroundShellMemoryDraft] = []
    for candidate in raw:
        role = _required_text(
            _field(candidate, "case_role"),
            "Memory draft role",
        )
        disposition = _required_text(
            _field(candidate, "disposition"),
            "Memory draft disposition",
        )
        origin = _required_text(
            _field(candidate, "origin"),
            "Memory draft origin",
        )
        rule_index = _field(candidate, "rule_draft_index", 0)
        if (
            role not in {"FIT", "BOUNDARY", "CONTRAST"}
            or disposition not in {"INCLUDE", "EXCLUDE", "UNRESOLVED"}
            or origin not in {"USER_EXACT", "AGENT_SUGGESTED"}
            or (
                origin == "AGENT_SUGGESTED"
                and disposition != "UNRESOLVED"
            )
            or isinstance(rule_index, bool)
            or not isinstance(rule_index, int)
            or not 0 <= rule_index <= rule_draft_count
        ):
            raise ValueError("Chat response has invalid Memory drafts.")
        spans = _freeze_source_spans(
            _field(candidate, "source_spans", ()),
            label="Memory draft source",
        )
        if (origin == "USER_EXACT") != bool(spans):
            raise ValueError("Chat response has invalid Memory drafts.")
        expected = _field(candidate, "expected", "")
        rationale = _field(candidate, "rationale", "")
        if not isinstance(expected, str) or not isinstance(rationale, str):
            raise ValueError("Chat response has invalid Memory drafts.")
        if disposition == "INCLUDE" and not expected.strip():
            raise ValueError("Chat response has invalid Memory drafts.")
        content = _required_text(
            _field(candidate, "content"),
            "Memory draft content",
        )
        if origin == "USER_EXACT" and (
            not any(content in span for span in spans)
            or (
                expected
                and not any(expected in span for span in spans)
            )
        ):
            raise ValueError("Chat response has invalid Memory drafts.")
        result.append(
            GroundShellMemoryDraft(
                content=content,
                expected=expected,
                rationale=rationale,
                case_role=role,
                disposition=disposition,
                rule_draft_index=rule_index,
                origin=origin,
                source_spans=spans,
            )
        )
    return tuple(result)
