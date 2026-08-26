"""Interactive, fail-closed shell for starting one Ground from a blank page.

The dialogue provider may explain or propose, but it cannot supply a shell
command.  This module freezes the Ground name and Goal, renders their argv
locally, and calls the supplied ``apply`` adapter only after one explicit
approval.
"""

from __future__ import annotations

import asyncio
import threading
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from typing import Literal, Protocol

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    DynamicContainer,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame

from memcommit.commands.command_progress import (
    BUSY_FRAMES,
    BUSY_INTERVAL_SECONDS,
)
from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    format_exact_command,
    render_exact_command_blocks,
    render_exact_command_review,
)
from memcommit.commands.session_help import bind_session_help
from memcommit.context_targeting.tui.picker import choose_context
from memcommit.interfaces.tui.components.in_frame_input import (
    InFrameInputManager,
    InFrameInputSection,
    INLINE_AGENT_COMMENT_TITLE,
    build_inline_direct_edit_input,
    classify_inline_edit_submission,
)
from memcommit.interfaces.tui.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.interfaces.tui.components.exact_command_review import (
    bind_exact_command_approval,
)
from memcommit.commands.tui_primitives import anchored_fragments
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.interfaces.tui.components.scrollable_pane import (
    build_scrollable_text_pane,
    equal_pane_height,
    scroll_wrapped_page,
)
from memcommit.interfaces.console.terminal import (
    require_interactive_terminal,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.interfaces.tui.components.table import (
    RenderedTuiTable,
    SelectedTableCellProcessor,
    TuiTableColumn,
    TuiTableRow,
    clamp_table_position,
    render_tui_table,
)
from memcommit.operations.ground.model import (
    GroundError,
    validate_ground_contract_name,
    validate_ground_goal,
)
from memcommit.context_targeting.naming import validate_portable_context_name


INITIAL_QUESTION = (
    "What are you trying to understand, decide, or make together?"
)
GROUND_GOAL_FRAME_HEIGHT = Dimension(min=3, preferred=5, max=5)
# CONTEXTS is the first-turn orientation and selection surface. Its preferred
# outer height leaves five body rows, while the shared three-row minimum lets
# prompt-toolkit compress it to one body row on a conventional 24-row terminal.
GROUND_CONTEXTS_FRAME_HEIGHT = Dimension(min=3, preferred=7, max=10)
GROUND_LOCATION_FRAME_HEIGHT = Dimension.exact(3)
# Compatibility aliases remain patchable by focused shell tests while Ground
# shares the same liveness vocabulary and cadence as blocking commands.
_THINKING_SUFFIXES = BUSY_FRAMES
_THINKING_INTERVAL_SECONDS = BUSY_INTERVAL_SECONDS
_GroundPane = Literal[
    "LOCATION",
    "GOAL",
    "CONTEXTS",
    "RULES",
    "MEMORIES",
    "CHAT",
]
_GroundPaneActivityPhase = Literal[
    "IDLE",
    "THINKING",
    "PROPOSED",
    "NEEDS_CLARIFICATION",
    "FAILED",
]
_CONTEXT_SUGGESTION_ROLES = {
    "MAIN",
    "ALTERNATIVE",
}
_CONTEXT_ROLE_LABELS = {
    "MAIN": "MAIN?",
    "ALTERNATIVE": "ALTERNATIVE",
}
_BLANK_MEMORY_TABLE_COLUMNS = (
    TuiTableColumn("id", "ID", 6),
    TuiTableColumn("from", "FROM", 12),
    TuiTableColumn("check", "CHECK", 16),
    TuiTableColumn("input", "INPUT", 24),
    TuiTableColumn("expected", "EXPECTED", 24),
    TuiTableColumn("role", "ROLE", 12),
    TuiTableColumn("decision", "DECISION", 14),
    TuiTableColumn("rule", "RULE", 8),
)


@dataclass
class _GroundPaneActivity:
    """One target-owned semantic turn projected inside its originating pane."""

    phase: _GroundPaneActivityPhase = "IDLE"
    request: str = ""
    detail: str = ""


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
class _GroundShellContextRow:
    """One semantic cursor row in the process-local Context planner."""

    kind: Literal[
        "EXISTING",
        "NEW_SUGGESTION",
        "DIRECT_PICK",
        "ADD_NEW",
        "CONTINUE_EMPTY",
    ]
    context_name: str = ""
    existing: GroundShellContextSuggestion | None = None


async def _interpret_from_daemon_thread(
    interpret: GroundInterpreter,
    text: str,
) -> object:
    """Await blocking inference without making TUI shutdown join its worker."""
    loop = asyncio.get_running_loop()
    completed: asyncio.Future[object] = loop.create_future()

    def deliver(*, result: object = None, error: Exception | None = None) -> None:
        if completed.done():
            return
        if error is not None:
            completed.set_exception(error)
        else:
            completed.set_result(result)

    def worker() -> None:
        try:
            result = interpret(text)
        except Exception as error:
            callback = partial(deliver, error=error)
        else:
            callback = partial(deliver, result=result)
        try:
            loop.call_soon_threadsafe(callback)
        except RuntimeError:
            # Escape may close the event loop before a non-cancellable
            # provider process returns. Its late result has no UI authority.
            return

    threading.Thread(
        target=worker,
        name="mem-ground-dialogue",
        daemon=True,
    ).start()
    return await completed


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


def render_ground_top_panel(
    proposal: GroundShellProposal | None = None,
    *,
    working_goal: str = "",
    current_context_name: str | None = None,
    context_catalog_count: int = 0,
    context_discovery_complete: bool = False,
    context_discovery_in_progress: bool = False,
    thinking_suffix: str = "…",
) -> str:
    """Render the compact unsaved Goal–Contexts–Rules–Memories state."""
    goal = (
        proposal.goal
        if proposal is not None
        else working_goal or "(not yet stated)"
    )
    context_lines = render_ground_contexts_pane(
        proposal.context_suggestions if proposal is not None else (),
        new_context_suggestions=(
            proposal.new_context_suggestions
            if proposal is not None
            else ()
        ),
        current_context_name=current_context_name,
        catalog_count=context_catalog_count,
        discovery_complete=(
            context_discovery_complete or proposal is not None
        ),
        discovery_in_progress=context_discovery_in_progress,
        thinking_suffix=thinking_suffix,
    ).splitlines()
    return "\n".join(
        [
            "MEM GROUND · DRAFT",
            "GOAL",
            f"  {safe_terminal_text(goal)}",
            "CONTEXTS",
            *(f"  {line}" for line in context_lines),
            "RULES",
            *(
                f"  {line}"
                for line in render_ground_rules_pane(
                    proposal.rule_drafts if proposal is not None else ()
                ).splitlines()
            ),
            "MEMORIES",
            *(
                f"  {line}"
                for line in render_ground_memories_pane(
                    proposal.memory_drafts if proposal is not None else ()
                ).splitlines()
            ),
        ]
    )


def render_ground_goal_pane(
    proposal: GroundShellProposal | None = None,
    *,
    working_goal: str = "",
) -> str:
    """Render the complete blank-Ground Goal state for its own viewport."""
    if proposal is None:
        return safe_terminal_text(working_goal or "(not yet stated)")

    lines = [
        "PROPOSED",
        safe_terminal_text(proposal.goal),
    ]
    if working_goal and working_goal != proposal.goal:
        lines.extend(
            [
                "",
                "STARTING REQUEST",
                safe_terminal_text(working_goal),
            ]
        )
    return "\n".join(lines)


def render_ground_contexts_pane(
    suggestions: Sequence[GroundShellContextSuggestion] = (),
    *,
    new_context_suggestions: Sequence[
        GroundShellNewContextSuggestion
    ] = (),
    current_context_name: str | None = None,
    catalog_count: int = 0,
    discovery_complete: bool = False,
    discovery_in_progress: bool = False,
    thinking_suffix: str = "…",
    candidate_cursor_name: str | None = None,
    candidate_cursor_kind: str | None = None,
    selected_context_names: Sequence[str] = (),
    local_new_context_name: str = "",
    selection_finished: bool = False,
    direct_context_names: Sequence[str] = (),
) -> str:
    """Render name-only Context choices without implying a binding."""

    def one_line(value: str) -> str:
        return safe_terminal_text(value).replace("\r", " ").replace("\n", " ")

    current_name = (
        one_line(current_context_name)
        if current_context_name
        else "(none)"
    )
    main = next(
        (item for item in suggestions if item.role == "MAIN"),
        None,
    )
    alternatives = tuple(
        item for item in suggestions if item.role == "ALTERNATIVE"
    )
    current_match = next(
        (
            item
            for item in suggestions
            if item.context_name == current_context_name
        ),
        None,
    )

    suggestion_by_name = {
        item.context_name: item
        for item in suggestions
    }
    selectable_names = set(suggestion_by_name) | set(direct_context_names)
    selected_names = tuple(
        name
        for name in dict.fromkeys(selected_context_names)
        if name in selectable_names
    )
    selected_set = set(selected_names)

    def candidate_prefix(item: GroundShellContextSuggestion) -> str:
        if (
            candidate_cursor_name is None
            or selection_finished
            or candidate_cursor_kind not in {None, "EXISTING"}
        ):
            return ""
        return "› " if item.context_name == candidate_cursor_name else "  "

    def planning_prefix(kind: str, context_name: str = "") -> str:
        if selection_finished or candidate_cursor_kind != kind:
            return ""
        if kind == "NEW_SUGGESTION":
            return "› " if candidate_cursor_name == context_name else "  "
        return "› "

    def candidate_label(item: GroundShellContextSuggestion) -> str:
        if item.context_name in selected_set:
            return (
                "MAIN"
                if selected_names and item.context_name == selected_names[0]
                else "ADDITIONAL"
            )
        return _CONTEXT_ROLE_LABELS[item.role]

    def selection_marker(item: GroundShellContextSuggestion) -> str:
        return (
            " · SELECTED"
            if item.context_name in selected_set
            else ""
        )

    def candidate_line(
        item: GroundShellContextSuggestion,
        *,
        current: bool = False,
    ) -> str:
        checkbox = (
            ""
            if selection_finished
            else "[x] "
            if item.context_name in selected_set
            else "[ ] "
        )
        current_marker = "CURRENT · " if current else ""
        return (
            f"{candidate_prefix(item)}{checkbox}{current_marker}"
            f"{candidate_label(item)} · "
            f"{one_line(item.context_name)}{selection_marker(item)} — "
            f"{one_line(item.reason)}"
        )

    if selection_finished:
        lines = (
            [f"SELECTED CONTEXTS · {len(selected_names)}"]
            if selected_names
            else [
                "CONTEXT PLAN · "
                + ("NEW ONLY" if local_new_context_name else "NONE")
            ]
        )
        for name in selected_names:
            item = suggestion_by_name.get(name)
            if item is not None:
                lines.append(
                    candidate_line(
                        item,
                        current=name == current_context_name,
                    )
                )
            else:
                lines.append(
                    f"DIRECT · {one_line(name)} · SELECTED"
                )
        if local_new_context_name:
            lines.append(
                "NEW CONTEXT · "
                f"{one_line(local_new_context_name)} · "
                "PLANNED · NOT CREATED"
            )
        lines.append(
            "These Contexts will be reviewed with the Ground draft."
        )
        return "\n".join(lines)

    lines = ["CONTEXT SUGGESTIONS"]
    if current_context_name is None:
        lines.append("CURRENT · (none)")
    elif current_match is not None:
        lines.append(candidate_line(current_match, current=True))
    else:
        lines.append(f"CURRENT · {current_name}")

    if discovery_in_progress:
        subject = (
            f"ranking {catalog_count} Context locator names; CURRENT stays local"
            if catalog_count
            else "no ordinary Context locator names to rank; CURRENT stays local"
        )
        suffix = (
            thinking_suffix
            if thinking_suffix in _THINKING_SUFFIXES
            else "…"
        )
        lines.append(f"THINKING{suffix} · {subject}")
    elif main is not None:
        if main.context_name != current_context_name:
            lines.append(candidate_line(main))
        for alternative in alternatives:
            if alternative.context_name == current_context_name:
                continue
            lines.append(candidate_line(alternative))
    elif discovery_complete:
        lines.append("MAIN? · (none found from Context names)")
    elif catalog_count:
        lines.append(
            f"READY · {catalog_count} ordinary Context locator names"
        )
    else:
        lines.append("READY · no ordinary Context locator names found")

    if not selection_finished:
        for candidate in new_context_suggestions:
            lines.append(
                planning_prefix(
                    "NEW_SUGGESTION",
                    candidate.context_name,
                )
                + "NEW? · "
                f"{one_line(candidate.context_name)} · NOT CREATED — "
                f"{one_line(candidate.reason)}"
            )
        if local_new_context_name:
            lines.append(
                "NEW CONTEXT · "
                f"{one_line(local_new_context_name)} · "
                "PLANNED · NOT CREATED"
            )
        if direct_context_names:
            lines.append(
                planning_prefix("DIRECT_PICK")
                + "DIRECT SELECT · P opens the ordinary Context tree"
            )
        if discovery_complete:
            lines.append(
                planning_prefix("ADD_NEW")
                + "ADD NEW CONTEXT · N to enter an exact Context name"
            )
            if not suggestions:
                lines.append(
                    planning_prefix("CONTINUE_EMPTY")
                    + "CONTINUE WITHOUT CONTEXT PLAN · Review Ground only"
                )

    lines.append("Suggestions use Context names only; Memory content was not opened.")
    return "\n".join(lines)


def render_ground_location_pane(
    ground_name: str | None,
    *,
    source: Literal["UNSET", "SUGGESTED", "SELECTED", "RESUMED"] = "UNSET",
) -> str:
    """Render the session-owned Context Save Location above Goal."""

    if ground_name is None:
        return "NOT SET · Enter/L to choose with the Context tree"
    name = validate_portable_context_name(ground_name)
    label = {
        "UNSET": "NOT SET",
        "SUGGESTED": "SUGGESTED · REVIEW REQUIRED",
        "SELECTED": "SELECTED",
        "RESUMED": "RESUMED",
    }[source]
    return (
        f"{safe_terminal_text(name)} · {label} · NOT CREATED\n"
        "Enter/L to change; final exact approval saves this Ground here."
    )


def render_ground_workspace_pane(ground_name: str | None) -> str:
    """Render one already chosen, still-uncreated physical workspace root."""

    if ground_name is None:
        return "\n".join(
            (
                "SAVE LOCATION · NOT SET",
                "Choose Location above Goal before exact save approval.",
                "No physical Context, manifest, or checkpoint exists.",
            )
        )
    name = validate_portable_context_name(ground_name)
    return "\n".join(
        (
            f"SAVE LOCATION · {safe_terminal_text(name)} · NOT CREATED",
            "PHYSICAL CONTEXTS AFTER APPROVAL",
            f"  {safe_terminal_text(name)}/goals",
            f"  {safe_terminal_text(name)}/rules",
            f"  {safe_terminal_text(name)}/examples",
            f"  {safe_terminal_text(name)}/contexts",
            f"  {safe_terminal_text(name)}/relations",
            "Existing Contexts are not recommended or selected here.",
        )
    )


def _preview_card_value(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return (
        safe_terminal_text(normalized)
        .replace("\n", " ↵ ")
        .replace("\t", " ⇥ ")
    )


def _rule_draft_origin_label(origin: str) -> str:
    return (
        "[Provided] [Source-matched]"
        if origin == "USER_EXACT"
        else "[Suggested] [Unverified]"
    )


def _memory_draft_origin_label(origin: str) -> str:
    return (
        "[Provided] [Source-matched]"
        if origin == "USER_EXACT"
        else "[Suggested] [Unverified]"
    )


def render_ground_rules_pane(
    drafts: Sequence[GroundShellRuleDraft] = (),
) -> str:
    """Render process-local first-turn Rule hypotheses."""
    if drafts:
        return "\n".join(
            (
                f"r{index} {_rule_draft_origin_label(draft.origin)} "
                f"{_preview_card_value(draft.content)}"
            )
            for index, draft in enumerate(drafts, start=1)
        )
    return "\n".join(
        [
            "(none yet)",
            "",
            "Rule drafts may appear as the Ground takes shape.",
        ]
    )


def render_ground_memories_pane(
    drafts: Sequence[GroundShellMemoryDraft] = (),
    *,
    view: Literal["LIST", "TABLE"] = "LIST",
    selected_memory_index: int = 0,
    selected_memory_column: int = 0,
) -> str:
    """Render process-local Memory previews in list or table form."""
    if view == "TABLE":
        return _render_ground_memory_table(
            drafts,
            selected_memory_index=selected_memory_index,
            selected_memory_column=selected_memory_column,
        ).text
    if view != "LIST":
        raise ValueError("Memory view must be LIST or TABLE.")
    if drafts:
        lines: list[str] = []
        for index, draft in enumerate(drafts, start=1):
            relation = (
                f" · r{draft.rule_draft_index}"
                if draft.rule_draft_index
                else ""
            )
            lines.append(
                f"c{index} {_memory_draft_origin_label(draft.origin)} "
                f"{_preview_card_value(draft.content)} | "
                + (
                    _preview_card_value(draft.expected)
                    if draft.expected
                    else "(no output)"
                )
                + f" · {draft.case_role} / {draft.disposition}{relation}"
            )
        return "\n".join(lines)
    return "\n".join(
        [
            "(none yet)",
            "",
            "Memory drafts may appear as the Ground takes shape.",
        ]
    )


def _render_ground_memory_table(
    drafts: Sequence[GroundShellMemoryDraft],
    *,
    selected_memory_index: int,
    selected_memory_column: int,
) -> RenderedTuiTable:
    rows = tuple(
        TuiTableRow(
            row_id=f"c{index}",
            cells=(
                f"c{index}",
                "Provided" if draft.origin == "USER_EXACT" else "Suggested",
                (
                    "Source-matched"
                    if draft.origin == "USER_EXACT"
                    else "Unverified"
                ),
                draft.content,
                draft.expected or "(no output)",
                draft.case_role,
                draft.disposition,
                (
                    f"r{draft.rule_draft_index}"
                    if draft.rule_draft_index
                    else "—"
                ),
            ),
        )
        for index, draft in enumerate(drafts, start=1)
    )
    return render_tui_table(
        columns=_BLANK_MEMORY_TABLE_COLUMNS,
        rows=rows,
        selected_row=selected_memory_index,
        selected_column=selected_memory_column,
        noun="MEMORIES",
    )


def render_ground_cases_pane(
    drafts: Sequence[GroundShellMemoryDraft] = (),
) -> str:
    """Compatibility alias for the former user-facing Cases renderer."""
    return render_ground_memories_pane(drafts)


def render_proposal_review(proposal: GroundShellProposal) -> str:
    """Render the exact proposal and its complete first-slice effect boundary."""
    return render_exact_command_review(_proposal_review(proposal))


def _proposal_review(
    proposal: GroundShellProposal,
    *,
    has_local_new_context: bool = False,
) -> ExactCommandReview:
    if has_local_new_context:
        new_context_effect = "New Context plan: reviewed with this Ground"
    elif proposal.new_context_suggestions:
        new_context_effect = (
            "New Context suggestion: not selected"
        )
    else:
        new_context_effect = "New Context plan: none"
    return ExactCommandReview(
        argv=proposal_argv(proposal),
        effects=(
            f"Ground: CREATE {proposal.ground_name}",
            "Goal: SET",
            "Rules and Ground Memories: none in this draft",
            new_context_effect,
            "Other Contexts will not be edited by this command",
        ),
    )


def _render_proposal_command_block(
    proposal: GroundShellProposal,
) -> str:
    return render_exact_command_blocks(_proposal_review(proposal))[0]


def _render_proposal_effects_block(
    proposal: GroundShellProposal,
    *,
    has_local_new_context: bool = False,
) -> str:
    return render_exact_command_blocks(
        _proposal_review(
            proposal,
            has_local_new_context=has_local_new_context,
        )
    )[1]


def _anchored_conversation_fragments(
    blocks: Sequence[str],
    *,
    anchor_index: int | None,
    anchor_at_end: bool = False,
) -> list[tuple[str, str]]:
    """Render dialogue blocks with the active content as the scroll anchor.

    ``FormattedTextControl`` uses ``[SetCursorPosition]`` as its viewport
    anchor. Approval anchors the end of the exact command so its wrapped text
    remains visible when it fits, rather than anchoring the end of a
    potentially long transcript and hiding the command before Enter applies.
    """
    return anchored_fragments(
        blocks,
        anchor_index=anchor_index,
        anchor_at_end=anchor_at_end,
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


def _agent_block(*, understanding: str, question: str) -> str:
    return "\n".join(
        [
            "AGENT UNDERSTANDING",
            f"  {safe_terminal_text(understanding)}",
            "",
            "AGENT QUESTION",
            f"  {safe_terminal_text(question)}",
        ]
    )


def run_ground_shell(
    *,
    interpret: GroundInterpreter,
    apply: GroundApplier,
    ground_name: str | None = None,
    initial_request: str = "",
    initial_proposal: GroundShellProposal | None = None,
    initial_submitted_turns: Sequence[str] = (),
    current_context_name: str | None = None,
    context_catalog_count: int = 0,
    context_catalog_names: Sequence[str] = (),
    validate_new_context: Callable[[str], str] = validate_portable_context_name,
    choose_save_location: Callable[[str | None], str | None] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    background_interpretation: bool = True,
) -> GroundShellResult:
    """Run the blank-Ground dialogue until one command is applied or cancelled."""
    if require_tty:
        require_interactive_terminal(
            "Interactive Ground",
            snapshot_hint=(
                "Run 'mem ground' in a terminal or use a snapshot mode."
            ),
        )

    fixed_ground_name = (
        validate_portable_context_name(ground_name)
        if ground_name is not None
        else None
    )
    planned_ground_name: dict[str, str | None] = {
        "value": fixed_ground_name
    }
    location_source: dict[
        str,
        Literal["UNSET", "SUGGESTED", "SELECTED", "RESUMED"],
    ] = {
        "value": (
            "RESUMED"
            if initial_proposal is not None
            else "SELECTED"
            if fixed_ground_name is not None
            else "UNSET"
        )
    }
    if initial_proposal is not None and initial_request.strip():
        raise ValueError(
            "A resumed Ground proposal cannot start another initial request."
        )
    if initial_proposal is not None and fixed_ground_name is None:
        raise ValueError("A resumed Ground proposal requires its Save Location.")
    frozen_initial_proposal = (
        _freeze_proposal(
            initial_proposal,
            expected_ground_name=fixed_ground_name,
        )
        if initial_proposal is not None
        else None
    )
    frozen_initial_turns = tuple(initial_submitted_turns)
    if any(
        not isinstance(turn, str) or not turn.strip()
        for turn in frozen_initial_turns
    ):
        raise ValueError("Resumed Ground turns must be nonblank text.")
    if frozen_initial_proposal is None and frozen_initial_turns:
        raise ValueError("Resumed Ground turns require a saved proposal.")
    if fixed_ground_name is not None and (
        context_catalog_count or tuple(context_catalog_names)
    ):
        raise ValueError(
            "A fixed Ground Save Location cannot use Context recommendations."
        )

    working_goal = (
        frozen_initial_proposal.goal
        if frozen_initial_proposal is not None
        else initial_request.strip()
    )
    editable_goal = {"value": working_goal}
    required_direct_goal: dict[str, str | None] = {"value": None}
    inline_goal_open = {"value": False}
    inline_goal_original = {"value": ""}
    inline_context_open = {"value": False}
    inline_context_original = {"value": ""}
    panel_comment_target: dict[
        str,
        _GroundPane | None,
    ] = {"value": None}
    panel_comment_focus = {"value": ""}
    pending_inline_goal: dict[
        str, tuple[str, str, str] | None
    ] = {"value": None}
    suspended_message = {"value": ""}
    mode = {
        "value": (
            "APPROVAL"
            if frozen_initial_proposal is not None
            else "INTERPRETING"
            if working_goal
            else "INPUT"
        )
    }
    review_view = {"value": "COMMAND"}
    pending: dict[str, GroundShellProposal | None] = {
        "value": frozen_initial_proposal
    }
    suspended_context_proposal: dict[
        str, GroundShellProposal | None
    ] = {"value": None}
    context_suggestions: dict[
        str, tuple[GroundShellContextSuggestion, ...]
    ] = {"value": ()}
    new_context_suggestions: dict[
        str, tuple[GroundShellNewContextSuggestion, ...]
    ] = {"value": ()}
    rule_drafts: dict[str, tuple[GroundShellRuleDraft, ...]] = {
        "value": (
            frozen_initial_proposal.rule_drafts
            if frozen_initial_proposal is not None
            else ()
        )
    }
    memory_drafts: dict[str, tuple[GroundShellMemoryDraft, ...]] = {
        "value": (
            frozen_initial_proposal.memory_drafts
            if frozen_initial_proposal is not None
            else ()
        )
    }
    memory_view: dict[str, Literal["LIST", "TABLE"]] = {"value": "LIST"}
    selected_memory_index = {"value": 0}
    selected_memory_column = {"value": 0}
    memory_table_render: dict[str, RenderedTuiTable | None] = {
        "value": None
    }
    context_candidate_index = {"value": 0}
    selected_context_names: dict[str, tuple[str, ...]] = {"value": ()}
    local_new_context_name = {"value": ""}
    context_selection_finished = {"value": False}
    context_discovery_complete = {
        "value": frozen_initial_proposal is not None
    }
    # Liveness begins only when ``begin_interpretation`` records the owning
    # pane. Rendering it earlier would briefly revive the legacy assumption
    # that every initial Goal turn belongs to Context discovery.
    context_discovery_in_progress = {"value": False}
    thinking_phase = {"value": 0}
    interpretation_generation = {"value": 0}
    active_turn_target: dict[str, _GroundPane] = {
        "value": "GOAL" if frozen_initial_proposal is not None else "CHAT"
    }
    pane_activities: dict[_GroundPane, _GroundPaneActivity] = {
        pane: _GroundPaneActivity()
        for pane in (
            "LOCATION",
            "GOAL",
            "CONTEXTS",
            "RULES",
            "MEMORIES",
            "CHAT",
        )
    }
    if frozen_initial_proposal is not None:
        pane_activities["GOAL"] = _GroundPaneActivity(
            phase="PROPOSED",
            request=(frozen_initial_turns[-1] if frozen_initial_turns else ""),
        )
    shell_closed = {"value": False}
    error_message = {"value": ""}
    status_message = {
        "value": (
            "Draft resumed · NOT CREATED · review and approve the exact command."
            if frozen_initial_proposal is not None
            else ""
        )
    }
    last_submission = {
        "value": (
            frozen_initial_turns[-1]
            if frozen_initial_turns
            else working_goal
        )
    }
    last_submission_target: dict[str, _GroundPane] = {
        "value": "GOAL" if working_goal else "CHAT"
    }
    last_submission_display = {"value": working_goal}
    # A badge means that this process received a new result for a pane after
    # the person's last explicit visit. It deliberately does not mean that a
    # Ground layer is complete or agreed: Ground has no implicit completion
    # criterion, and focus chosen by the program must not dismiss a result.
    pane_notifications = {
        "LOCATION": False,
        "GOAL": False,
        "CONTEXTS": False,
        "RULES": False,
        "MEMORIES": False,
        "CHAT": False,
    }

    def mark_pane_updates(*layers: str) -> None:
        for layer in layers:
            pane_notifications[layer] = True

    def acknowledge_pane(layer: str) -> None:
        pane_notifications[layer] = False

    submitted_turns: list[str] = list(frozen_initial_turns)
    conversation: list[str] = (
        [
            "\n".join(
                [
                    "RESUMED DRAFT · NOT CREATED",
                    "  The saved proposal is ready for exact command review.",
                    "  No Context, manifest, or checkpoint exists yet.",
                ]
            )
        ]
        if frozen_initial_proposal is not None
        else
        [
            "\n".join(
                [
                    "YOU · STARTING REQUEST",
                    f"  {safe_terminal_text(working_goal)}",
                    "",
                    "AGENT · CONTEXT DISCOVERY",
                    (
                        f"  Checking {context_catalog_count} ordinary Context "
                        "locator names."
                        if context_catalog_count
                        else "  No ordinary Context locator names were found."
                    ),
                    "  No Context Memory content will be opened.",
                ]
            )
        ]
        if working_goal
        else [
            "\n".join(
                [
                    "OPEN QUESTION · GOAL",
                    f"  {INITIAL_QUESTION}",
                    "",
                    "Start in your own words; a rough outcome, case, or",
                    "uncertainty is enough.",
                ]
            )
        ]
    )

    bindings = KeyBindings()
    # Goal is an orientation statement, not a document surface. Three body
    # rows are enough for the 40-word authoring contract; longer legacy or
    # provisional text remains inspectable through this pane's scrollbar.
    # Rules, Memories, and Chat absorb the remaining reading space after
    # the compact Goal and bounded Contexts panel. Their independent
    # scrollbars still bound content growth, while leaving max unset avoids a
    # dead band below ACTION on taller terminals.
    pane_height = equal_pane_height(
        minimum=3,
        preferred=4,
    )
    message_height = Dimension(min=3, preferred=4, max=5)
    embedded_field_height = Dimension(min=1, preferred=2, max=3)
    conversation_pane_height = Dimension(min=5, preferred=7)
    direct_edit_pane_height = Dimension(min=7, preferred=9)
    approval_action_height = Dimension.exact(4)
    compact_action_height = Dimension.exact(3)

    def current_thinking_suffix() -> str:
        return _THINKING_SUFFIXES[thinking_phase["value"]]

    def pane_turn_label(target: _GroundPane) -> str:
        return {
            "LOCATION": "SAVE LOCATION",
            "GOAL": "GOAL REVISION REQUEST",
            "CONTEXTS": "WORKSPACE REVISION REQUEST",
            "RULES": "RULE REVISION REQUEST",
            "MEMORIES": "MEMORY REVISION REQUEST",
            "CHAT": "MESSAGE",
        }[target]

    def pane_thinking_verb(target: _GroundPane) -> str:
        return {
            "LOCATION": "CHOOSING",
            "GOAL": "REVISING",
            "CONTEXTS": "RECONSIDERING",
            "RULES": "REVISING",
            "MEMORIES": "REVISING",
            "CHAT": "RESPONDING",
        }[target]

    def pane_activity_text(target: _GroundPane, base: str) -> str:
        """Keep a focused semantic turn in the pane that originated it."""

        activity = pane_activities[target]
        if activity.phase == "IDLE" or target == "CHAT":
            return base
        if activity.phase == "THINKING":
            heading = f"{pane_turn_label(target)} · SUBMITTED"
        elif activity.phase == "PROPOSED":
            heading = f"PROPOSED {target} REVISION"
        elif activity.phase == "NEEDS_CLARIFICATION":
            heading = f"{target} REVISION · NEEDS CLARIFICATION"
        else:
            heading = f"{target} REVISION · FAILED · NOTHING APPLIED"
        lines = [heading]
        if activity.phase == "PROPOSED":
            # A compact Goal viewport must show the revised semantic value
            # before its provenance. Otherwise the request fills all visible
            # rows and makes a successful revision look unchanged.
            visible_result = (
                base.removeprefix("PROPOSED\n")
                if target == "GOAL"
                else base
            )
            lines.append(visible_result)
            if activity.request:
                lines.extend(
                    [
                        "",
                        "REQUEST",
                        safe_terminal_text(activity.request),
                    ]
                )
            return "\n".join(lines)
        if activity.detail:
            lines.extend([safe_terminal_text(activity.detail), ""])
        if activity.request:
            lines.extend(
                [
                    "REQUEST",
                    safe_terminal_text(activity.request),
                    "",
                ]
            )
        lines.append(base)
        return "\n".join(lines)

    def ordered_context_rows() -> tuple[_GroundShellContextRow, ...]:
        if fixed_ground_name is not None:
            return ()
        suggestions = context_suggestions["value"]
        current = tuple(
            item
            for item in suggestions
            if item.context_name == current_context_name
        )
        main = tuple(
            item
            for item in suggestions
            if item.role == "MAIN"
            and item.context_name != current_context_name
        )
        alternatives = tuple(
            item
            for item in suggestions
            if item.role == "ALTERNATIVE"
            and item.context_name != current_context_name
        )
        # This order mirrors the rendered rows. A current candidate remains
        # one selectable row rather than appearing twice and making Down move
        # the cursor upward on screen.
        rows = [
            _GroundShellContextRow(
                kind="EXISTING",
                context_name=item.context_name,
                existing=item,
            )
            for item in (*current, *main, *alternatives)
        ]
        rows.extend(
            _GroundShellContextRow(
                kind="NEW_SUGGESTION",
                context_name=item.context_name,
            )
            for item in new_context_suggestions["value"]
        )
        if context_discovery_complete["value"]:
            if context_catalog_names:
                rows.append(_GroundShellContextRow(kind="DIRECT_PICK"))
            rows.append(_GroundShellContextRow(kind="ADD_NEW"))
            if not suggestions:
                rows.append(
                    _GroundShellContextRow(kind="CONTINUE_EMPTY")
                )
        return tuple(rows)

    def reset_context_candidate_cursor() -> None:
        candidates = ordered_context_rows()
        context_candidate_index["value"] = next(
            (
                index
                for index, item in enumerate(candidates)
                if (
                    item.kind == "EXISTING"
                    and item.existing is not None
                    and item.existing.role == "MAIN"
                )
            ),
            0,
        )

    def context_cursor_row() -> _GroundShellContextRow | None:
        candidates = ordered_context_rows()
        if not candidates:
            return None
        context_candidate_index["value"] = min(
            context_candidate_index["value"],
            len(candidates) - 1,
        )
        return candidates[context_candidate_index["value"]]

    def candidate_cursor_name() -> str | None:
        row = context_cursor_row()
        return row.context_name if row is not None else None

    location_pane = build_scrollable_text_pane(
        "LOCATION",
        render_ground_location_pane(
            planned_ground_name["value"],
            source=location_source["value"],
        ),
        buffer_name="ground-new-location",
        height=GROUND_LOCATION_FRAME_HEIGHT,
        notification=lambda: pane_notifications["LOCATION"],
    )
    goal_pane = build_scrollable_text_pane(
        "GOAL",
        pane_activity_text(
            "GOAL",
            render_ground_goal_pane(
                frozen_initial_proposal,
                working_goal=editable_goal["value"],
            ),
        ),
        buffer_name="ground-new-goal",
        height=GROUND_GOAL_FRAME_HEIGHT,
        notification=lambda: pane_notifications["GOAL"],
    )
    contexts_pane = build_scrollable_text_pane(
        "CONTEXTS",
        (
            render_ground_contexts_pane(
                current_context_name=current_context_name,
                catalog_count=context_catalog_count,
                discovery_in_progress=context_discovery_in_progress["value"],
                thinking_suffix=current_thinking_suffix(),
            )
            if context_catalog_count
            else render_ground_workspace_pane(planned_ground_name["value"])
        ),
        buffer_name="ground-new-contexts",
        height=GROUND_CONTEXTS_FRAME_HEIGHT,
        notification=lambda: pane_notifications["CONTEXTS"],
    )
    rules_pane = build_scrollable_text_pane(
        "RULES",
        render_ground_rules_pane(rule_drafts["value"]),
        buffer_name="ground-new-rules",
        height=pane_height,
        notification=lambda: pane_notifications["RULES"],
    )
    cases_pane = build_scrollable_text_pane(
        "MEMORIES",
        render_ground_memories_pane(memory_drafts["value"]),
        buffer_name="ground-new-cases",
        height=pane_height,
        notification=lambda: pane_notifications["MEMORIES"],
    )
    # LIST preserves wrapped cards. TABLE uses logical rows and lets the
    # selected-cell cursor drive horizontal scrolling like a spreadsheet.
    cases_pane.text_area.window.wrap_lines = Condition(
        lambda: memory_view["value"] == "LIST"
    )
    cases_pane.text_area.control.input_processors.append(
        SelectedTableCellProcessor(
            lambda: (
                memory_table_render["value"].selected_span
                if memory_view["value"] == "TABLE"
                and memory_table_render["value"] is not None
                else None
            )
        )
    )

    def conversation_text() -> str:
        blocks = list(conversation)
        proposal = pending["value"]
        if proposal is not None:
            if review_view["value"] == "EFFECTS":
                blocks.append(
                    _render_proposal_effects_block(
                        proposal,
                        has_local_new_context=bool(
                            local_new_context_name["value"]
                        ),
                    )
                )
            else:
                blocks.append(
                    _render_proposal_command_block(proposal),
                )
        if (
            error_message["value"]
            and active_turn_target["value"] == "CHAT"
        ):
            blocks.append(
                "INTERPRETATION FAILED · NOTHING APPLIED\n"
                f"  {safe_terminal_text(error_message['value'])}"
            )
        return "\n\n".join(blocks)

    dialogue_pane = build_scrollable_text_pane(
        "CHAT",
        conversation_text(),
        buffer_name="ground-new-dialogue",
        height=pane_height,
        notification=lambda: pane_notifications["CHAT"],
    )
    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="ground-new-message",
        height=message_height,
    )
    input_area = composer.text_area
    direct_editor = build_inline_direct_edit_input(
        buffer_name="ground-new-direct-edit",
    )
    direct_edit_area = direct_editor.text_area

    header = Window(
        FormattedTextControl(" MEM GROUND · DRAFT"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    approval_panel = Frame(
        Window(
            FormattedTextControl(
                "CHAT: ←/↑ cmd · →/↓ fx\n"
                "Enter apply · A also · E/B/Q"
            ),
            wrap_lines=True,
        ),
        title="ACTION",
        height=approval_action_height,
    )
    error_panel = Frame(
        Window(
            FormattedTextControl(
                "R retry · E refine · B/Q"
            ),
            wrap_lines=True,
        ),
        title="ACTION",
        height=compact_action_height,
    )
    apply_error_panel = Frame(
        Window(
            FormattedTextControl(
                "E refine · B/Q"
            ),
            wrap_lines=True,
        ),
        title="ACTION",
        height=compact_action_height,
    )
    empty_action_panel = Window(height=Dimension.exact(0))
    action_panel = DynamicContainer(
        lambda: (
            approval_panel
            if mode["value"] == "APPROVAL"
            else apply_error_panel
            if mode["value"] == "APPLY_ERROR"
            else error_panel
            if mode["value"] == "ERROR"
            else empty_action_panel
        )
    )

    def footer_text() -> str:
        active_mode = mode["value"]
        if panel_comment_target["value"] is not None:
            target = panel_comment_target["value"]
            return (
                f" Enter · send {pane_turn_label(target).lower()}    "
                "Ctrl-J · newline    "
                "Esc · collapse"
            )
        if inline_context_open["value"]:
            if application.layout.has_focus(direct_edit_area):
                return (
                    " Enter · use exact one-line name    "
                    "Tab · comment    Esc · collapse"
                )
            return (
                " Enter · send comment    Ctrl-J · newline    "
                "Tab · exact name    Esc · collapse"
            )
        if inline_goal_open["value"]:
            return (
                " Enter · review edit/comment    Ctrl-J · newline    "
                "Tab/Shift-Tab · field    Esc · collapse"
            )
        contexts_focused = application.layout.has_focus(
            contexts_pane.text_area
        )
        memories_focused = application.layout.has_focus(
            cases_pane.text_area
        )
        location_focused = application.layout.has_focus(
            location_pane.text_area
        )
        input_focused = application.layout.has_focus(input_area)
        if (
            location_focused
            and active_mode in {"INPUT", "APPROVAL"}
        ):
            return (
                " LOCATION: Enter/L · choose or change    "
                "Tab/Shift-Tab · move    B · Grounds    Q · quit"
            )
        if (
            context_selection_finished["value"]
            and contexts_focused
            and active_mode in {"INPUT", "APPROVAL"}
        ):
            return (
                " CONTEXTS: Enter talk here    F edit selection    "
                "B · Grounds    Q · quit"
            )
        if status_message["value"]:
            return f" {status_message['value']}"
        if memories_focused and memory_drafts["value"]:
            tail = (
                "Enter · exact approval"
                if active_mode == "APPROVAL"
                else "Enter · talk here"
            )
            if memory_view["value"] == "TABLE":
                return (
                    " MEMORIES · TABLE: ↑/↓ row · ←/→ column · "
                    f"V · list    {tail}    B · Grounds    Q · quit"
                )
            return (
                " MEMORIES · LIST: ↑/↓ scroll · V · table    "
                f"{tail}    B · Grounds    Q · quit"
            )
        if active_mode == "INTERPRETING":
            return (
                f" Waiting in {active_turn_target['value']}    "
                "B · Grounds    Q · quit"
            )
        if (
            active_mode in {"INPUT", "CONTEXT_SELECTION"}
            and contexts_focused
            and not context_selection_finished["value"]
            and bool(ordered_context_rows())
        ):
            return (
                " CONTEXTS: ↑/↓ move · Space select · F finish · "
                "P direct tree · N exact name · B Grounds · Q quit"
            )
        if active_mode in {"INPUT", "CONTEXT_SELECTION"}:
            if input_focused:
                return (
                    " Enter · send    Ctrl-J · newline    "
                    "Tab · panes (B Grounds · Q quit)"
                )
            if (
                active_mode == "INPUT"
                and application.layout.has_focus(goal_pane.text_area)
            ):
                return (
                    " Enter · talk here    E · edit Goal    L · location    "
                    "B · Grounds    Q · quit"
                )
            return (
                " Enter · talk here    C · same action    L · location    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "APPROVAL":
            row = context_cursor_row()
            if (
                contexts_focused
                and not context_selection_finished["value"]
                and row is not None
                and row.kind == "ADD_NEW"
            ):
                return (
                    " CONTEXTS: N · plan a new Context name    "
                    "Enter approve · B Grounds · Q quit"
                )
            return (
                " No command runs without Enter · exact approval    "
                "L · location    B · Grounds    Q · quit"
            )
        if active_mode == "APPLY_ERROR":
            return " The exact command will not be applied again"
        return " The failed interpretation cannot change Ground state"

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    normal_root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(location_pane.container),
        TuiRegion(goal_pane.container),
        TuiRegion(contexts_pane.container),
        TuiRegion(rules_pane.container),
        TuiRegion(cases_pane.container),
        TuiRegion(dialogue_pane.container),
        TuiRegion(action_panel),
        TuiRegion(footer),
    )
    # The same Message buffer is embedded in whichever semantic pane owns the
    # current exchange. This preserves one continuous conversational surface
    # without introducing a detached sixth panel or duplicating input state.
    input_manager = InFrameInputManager(
        goal_pane,
        contexts_pane,
        rules_pane,
        cases_pane,
        dialogue_pane,
    )

    def pane_for_layer(layer: _GroundPane):
        return {
            "LOCATION": location_pane,
            "GOAL": goal_pane,
            "CONTEXTS": contexts_pane,
            "RULES": rules_pane,
            "MEMORIES": cases_pane,
            "CHAT": dialogue_pane,
        }.get(layer, dialogue_pane)

    def sync_pane_titles() -> None:
        base_titles: dict[_GroundPane, str] = {
            "LOCATION": "LOCATION",
            "GOAL": "GOAL",
            "CONTEXTS": "CONTEXTS",
            "RULES": "RULES",
            "MEMORIES": "MEMORIES",
            "CHAT": "CHAT",
        }
        for target, title in base_titles.items():
            activity = pane_activities[target]
            pane_for_layer(target).frame.title = (
                f"{title} · THINKING{current_thinking_suffix()} · "
                f"{pane_thinking_verb(target)}"
                if activity.phase == "THINKING"
                else title
            )

    def sync_input_host() -> None:
        input_manager.clear()
        if inline_goal_open["value"]:
            input_manager.show(
                goal_pane,
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    direct_edit_area,
                    height=embedded_field_height,
                ),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    input_area,
                    height=embedded_field_height,
                ),
                height=direct_edit_pane_height,
            )
            return
        if inline_context_open["value"]:
            input_manager.show(
                contexts_pane,
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    direct_edit_area,
                    height=embedded_field_height,
                ),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    input_area,
                    height=embedded_field_height,
                ),
                height=direct_edit_pane_height,
            )
            return
        if panel_comment_target["value"] is not None:
            target = panel_comment_target["value"]
            input_manager.show(
                pane_for_layer(target),
                InFrameInputSection(
                    pane_turn_label(target),
                    input_area,
                    height=embedded_field_height,
                ),
                height=conversation_pane_height,
            )
            return
        if mode["value"] in {"INPUT", "CONTEXT_SELECTION"}:
            input_manager.show(
                dialogue_pane,
                InFrameInputSection(
                    "MESSAGE",
                    input_area,
                    height=embedded_field_height,
                ),
                height=conversation_pane_height,
            )

    sync_input_host()
    application: Application[GroundShellResult] = Application(
        layout=Layout(
            normal_root,
            # Ground is Goal-first. The general Message composer remains one
            # explicit Tab stop, but opening the workbench must not visually
            # or semantically make Chat the primary entry surface.
            focused_element=goal_pane.text_area,
        ),
        key_bindings=bindings,
        full_screen=True,
        # Make the reading contract explicit instead of relying on
        # prompt-toolkit deriving page navigation from full_screen mode.
        enable_page_navigation_bindings=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=MEMCOMMIT_TUI_STYLE,
    )
    # Ground does not bind Alt-prefixed actions, so a short escape-sequence
    # timeout improves the dedicated cancel key without creating ambiguity.
    application.ttimeoutlen = 0.05

    for pane in (
        location_pane,
        goal_pane,
        contexts_pane,
        rules_pane,
        cases_pane,
        dialogue_pane,
    ):
        bind_focused_frame_style(
            pane.frame,
            is_focused=lambda pane=pane: application.layout.has_focus(
                pane.frame
            ),
        )

    def sync_contexts_pane(*, align_candidate: bool = False) -> None:
        if (
            not context_catalog_count
            and not context_suggestions["value"]
            and not new_context_suggestions["value"]
        ):
            contexts_pane.set_text(
                pane_activity_text(
                    "CONTEXTS",
                    render_ground_workspace_pane(
                        planned_ground_name["value"]
                    ),
                ),
                anchor="preserve",
            )
            return
        cursor_row = context_cursor_row()
        cursor_name = (
            cursor_row.context_name if cursor_row is not None else None
        )
        rendered = render_ground_contexts_pane(
            context_suggestions["value"],
            new_context_suggestions=new_context_suggestions["value"],
            current_context_name=current_context_name,
            catalog_count=context_catalog_count,
            discovery_complete=context_discovery_complete["value"],
            # The active pane's title owns the liveness cue. Keeping the old
            # Context-body spinner as well would duplicate THINKING and make a
            # Goal-owned turn look like Context discovery.
            discovery_in_progress=False,
            thinking_suffix=current_thinking_suffix(),
            candidate_cursor_name=cursor_name,
            candidate_cursor_kind=(
                cursor_row.kind if cursor_row is not None else None
            ),
            selected_context_names=selected_context_names["value"],
            local_new_context_name=local_new_context_name["value"],
            selection_finished=context_selection_finished["value"],
            direct_context_names=context_catalog_names,
        )
        projected = pane_activity_text("CONTEXTS", rendered)
        contexts_pane.set_text(projected, anchor="preserve")
        if align_candidate and cursor_name is not None:
            marker = projected.find("› ")
            if marker >= 0:
                # The TextArea stays read-only; moving its cursor only asks
                # prompt-toolkit to keep the highlighted logical row visible.
                contexts_pane.text_area.buffer.cursor_position = marker

    def sync_memories_pane(*, align_selection: bool = False) -> None:
        row, column = clamp_table_position(
            row_count=len(memory_drafts["value"]),
            column_count=len(_BLANK_MEMORY_TABLE_COLUMNS),
            row=selected_memory_index["value"],
            column=selected_memory_column["value"],
        )
        selected_memory_index["value"] = row
        selected_memory_column["value"] = column
        if memory_view["value"] == "TABLE":
            rendered = _render_ground_memory_table(
                memory_drafts["value"],
                selected_memory_index=row,
                selected_memory_column=column,
            )
            memory_table_render["value"] = rendered
            projected = pane_activity_text("MEMORIES", rendered.text)
            cases_pane.set_text(
                projected,
                anchor="preserve",
            )
            if align_selection and rendered.selected_span is not None:
                cases_pane.text_area.buffer.cursor_position = (
                    len(projected) - len(rendered.text) + rendered.cursor_position
                )
            return
        memory_table_render["value"] = None
        rendered_text = render_ground_memories_pane(memory_drafts["value"])
        projected = pane_activity_text("MEMORIES", rendered_text)
        cases_pane.set_text(
            projected,
            anchor="preserve",
        )
        if align_selection and memory_drafts["value"]:
            marker = projected.find(f"c{row + 1} ")
            if marker >= 0:
                cases_pane.text_area.buffer.cursor_position = marker

    def sync_panes(*, dialogue_anchor: str = "end") -> None:
        sync_pane_titles()
        location_pane.set_text(
            render_ground_location_pane(
                planned_ground_name["value"],
                source=location_source["value"],
            ),
            anchor="preserve",
        )
        goal_pane.set_text(
            pane_activity_text(
                "GOAL",
                render_ground_goal_pane(
                    pending["value"],
                    working_goal=editable_goal["value"],
                ),
            ),
            anchor="preserve",
        )
        sync_contexts_pane()
        rules_pane.set_text(
            pane_activity_text(
                "RULES",
                render_ground_rules_pane(rule_drafts["value"]),
            ),
            anchor="preserve",
        )
        sync_memories_pane(
            align_selection=memory_view["value"] == "TABLE"
        )
        dialogue_pane.set_text(
            conversation_text(),
            anchor=dialogue_anchor,
        )

    def focus_conversation() -> None:
        application.layout.focus(dialogue_pane.text_area)

    def focus_contexts() -> None:
        application.layout.focus(contexts_pane.text_area)

    def focus_turn_target(target: _GroundPane) -> None:
        application.layout.focus(pane_for_layer(target).text_area)
        acknowledge_pane(target)

    def focus_input(*, restore: bool) -> None:
        mode["value"] = "INPUT"
        pending["value"] = None
        suspended_context_proposal["value"] = None
        review_view["value"] = "COMMAND"
        error_message["value"] = ""
        status_message["value"] = ""
        if restore:
            input_area.text = last_submission["value"]
            input_area.buffer.cursor_position = len(input_area.text)
        else:
            input_area.text = ""
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        application.layout.focus(input_area)
        application.invalidate()

    def dialogue_payload() -> str:
        return (
            submitted_turns[0]
            if len(submitted_turns) == 1
            else "\n\n".join(
                f"USER TURN {index}\n{turn}"
                for index, turn in enumerate(
                    submitted_turns,
                    start=1,
                )
            )
        )

    def finish_interpretation(
        response: object,
        *,
        append_user: bool,
        initial: bool,
        turn_target: _GroundPane,
    ) -> None:
        kind = _response_kind(response)
        understanding = _required_text(
            _field(response, "understanding"),
            "understanding",
        )
        question = _required_text(
            _field(response, "question"),
            "question",
        )
        frozen_contexts = _freeze_context_suggestions(response)
        frozen_new_contexts = _freeze_new_context_suggestions(response)
        if planned_ground_name["value"] is not None and (
            frozen_contexts or frozen_new_contexts
        ):
            raise ValueError(
                "Chat response added Context recommendations after the exact "
                "Ground Save Location was fixed."
            )
        frozen_rule_drafts = _freeze_rule_drafts(response)
        frozen_memory_drafts = _freeze_memory_drafts(
            response,
            rule_draft_count=len(frozen_rule_drafts),
        )
        if bool(frozen_contexts) != bool(context_catalog_count):
            raise ValueError(
                "Chat response has invalid Context suggestions."
            )
        context_suggestions["value"] = frozen_contexts
        new_context_suggestions["value"] = frozen_new_contexts
        rule_drafts["value"] = frozen_rule_drafts
        memory_drafts["value"] = frozen_memory_drafts
        # A focused turn belongs to its originating pane. Other panes receive
        # badges only when the response actually changed their semantic data;
        # the same request is never duplicated into Chat as presentation.
        mark_pane_updates(turn_target)
        if fixed_ground_name is None:
            mark_pane_updates("CONTEXTS")
        if frozen_rule_drafts:
            mark_pane_updates("RULES")
        if frozen_memory_drafts:
            mark_pane_updates("MEMORIES")
        if kind != "ASK":
            mark_pane_updates("GOAL")
        selected_memory_index["value"] = 0
        selected_memory_column["value"] = 0
        reset_context_candidate_cursor()
        selected_context_names["value"] = ()
        context_selection_finished["value"] = False
        context_discovery_in_progress["value"] = False
        context_discovery_complete["value"] = True
        activity = pane_activities[turn_target]
        activity.phase = (
            "NEEDS_CLARIFICATION" if kind == "ASK" else "PROPOSED"
        )
        activity.detail = question if kind == "ASK" else ""
        if turn_target == "CHAT" and (append_user or initial):
            conversation.append(
                _agent_block(
                    understanding=understanding,
                    question=question,
                )
            )
        elif turn_target == "CHAT":
            conversation.append(
                "\n".join(
                    [
                        "AGENT RETRY",
                        f"  {safe_terminal_text(understanding)}",
                        "",
                        "AGENT QUESTION",
                        f"  {safe_terminal_text(question)}",
                    ]
                )
            )
        error_message["value"] = ""
        status_message["value"] = ""
        if kind == "ASK":
            focus_input(restore=False)
            if frozen_contexts or frozen_new_contexts:
                sync_contexts_pane(align_candidate=True)
                focus_contexts()
                application.invalidate()
            elif turn_target != "CHAT":
                status_message["value"] = (
                    f"{turn_target.title()} revision needs clarification · "
                    "Enter to continue in this pane."
                )
                sync_panes(dialogue_anchor="preserve")
                focus_turn_target(turn_target)
                application.invalidate()
            return
        frozen = _freeze_proposal(
            response,
            expected_ground_name=planned_ground_name["value"],
        )
        if planned_ground_name["value"] is None:
            # The provider may suggest a portable initial location, but the
            # persistent LOCATION pane keeps it visibly unapproved and lets
            # the person replace it through the shared Context tree.
            planned_ground_name["value"] = frozen.ground_name
            location_source["value"] = "SUGGESTED"
            mark_pane_updates("LOCATION", "CONTEXTS")
        else:
            # A person-owned local location plan outranks later provider
            # naming. The exact command is always rebuilt from this value.
            frozen = replace(
                frozen,
                ground_name=planned_ground_name["value"],
            )
        exact_goal = required_direct_goal["value"]
        if exact_goal is not None and frozen.goal != exact_goal:
            raise ValueError(
                "The provider rewrote the directly edited Goal; no command "
                "was prepared."
            )
        if exact_goal is None:
            pending_inline_goal["value"] = None
        editable_goal["value"] = frozen.goal
        pending["value"] = frozen
        review_view["value"] = "COMMAND"
        mode["value"] = (
            "CONTEXT_SELECTION"
            if frozen_contexts or frozen_new_contexts
            else "APPROVAL"
        )
        input_area.text = ""
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        if frozen_contexts or frozen_new_contexts:
            sync_contexts_pane(align_candidate=True)
            focus_contexts()
        elif turn_target != "CHAT":
            status_message["value"] = (
                f"{turn_target.title()} revision proposed · inspect this pane; "
                "Tab to CHAT for the exact command review."
            )
            focus_turn_target(turn_target)
        else:
            focus_conversation()
        application.invalidate()

    def fail_interpretation(error: Exception, *, turn_target: _GroundPane) -> None:
        pending["value"] = None
        suspended_context_proposal["value"] = None
        context_suggestions["value"] = ()
        new_context_suggestions["value"] = ()
        rule_drafts["value"] = ()
        memory_drafts["value"] = ()
        selected_memory_index["value"] = 0
        selected_memory_column["value"] = 0
        memory_table_render["value"] = None
        context_candidate_index["value"] = 0
        selected_context_names["value"] = ()
        local_new_context_name["value"] = ""
        context_selection_finished["value"] = False
        context_discovery_in_progress["value"] = False
        context_discovery_complete["value"] = False
        error_message["value"] = (
            f"{type(error).__name__}: {error}"
        )
        activity = pane_activities[turn_target]
        activity.phase = "FAILED"
        activity.detail = error_message["value"]
        status_message["value"] = ""
        mark_pane_updates(turn_target)
        if fixed_ground_name is None:
            mark_pane_updates("CONTEXTS")
        mode["value"] = "ERROR"
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        focus_turn_target(turn_target)
        application.invalidate()

    async def interpret_in_background(
        text: str,
        *,
        append_user: bool,
        initial: bool,
        turn_target: _GroundPane,
    ) -> None:
        try:
            response = await _interpret_from_daemon_thread(
                interpret,
                text,
            )
            if shell_closed["value"]:
                return
            finish_interpretation(
                response,
                append_user=append_user,
                initial=initial,
                turn_target=turn_target,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not shell_closed["value"]:
                fail_interpretation(error, turn_target=turn_target)

    async def animate_thinking(generation: int) -> None:
        """Animate the title of the pane that owns the active semantic turn."""
        while (
            not shell_closed["value"]
            and context_discovery_in_progress["value"]
            and interpretation_generation["value"] == generation
        ):
            await asyncio.sleep(_THINKING_INTERVAL_SECONDS)
            if (
                shell_closed["value"]
                or not context_discovery_in_progress["value"]
                or interpretation_generation["value"] != generation
            ):
                return
            thinking_phase["value"] = (
                thinking_phase["value"] + 1
            ) % len(_THINKING_SUFFIXES)
            # Title-only liveness preserves every pane's independent viewport
            # and keeps the cue above, rather than below, the owned request.
            sync_pane_titles()
            application.invalidate()

    def begin_interpretation(
        text: str,
        *,
        append_user: bool,
        initial: bool = False,
        preserve_local_new_context: bool = False,
        turn_target: _GroundPane = "CHAT",
        turn_display: str | None = None,
    ) -> None:
        if append_user:
            submitted_turns.append(text)
            if turn_target == "CHAT":
                conversation.append(
                    f"YOU\n  {safe_terminal_text(turn_display or text)}"
                )
        active_turn_target["value"] = turn_target
        activity = pane_activities[turn_target]
        activity.phase = "THINKING"
        activity.request = (turn_display or text).strip()
        activity.detail = ""
        payload = dialogue_payload()
        pending["value"] = None
        suspended_context_proposal["value"] = None
        context_suggestions["value"] = ()
        new_context_suggestions["value"] = ()
        rule_drafts["value"] = ()
        memory_drafts["value"] = ()
        selected_memory_index["value"] = 0
        selected_memory_column["value"] = 0
        memory_table_render["value"] = None
        context_candidate_index["value"] = 0
        selected_context_names["value"] = ()
        if not preserve_local_new_context:
            local_new_context_name["value"] = ""
        context_selection_finished["value"] = False
        context_discovery_complete["value"] = False
        context_discovery_in_progress["value"] = True
        thinking_phase["value"] = 0
        interpretation_generation["value"] += 1
        generation = interpretation_generation["value"]
        error_message["value"] = ""
        status_message["value"] = ""
        mode["value"] = "INTERPRETING"
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        focus_turn_target(turn_target)
        application.invalidate()
        if background_interpretation:
            application.create_background_task(
                animate_thinking(generation)
            )
            application.create_background_task(
                interpret_in_background(
                    payload,
                    append_user=append_user,
                    initial=initial,
                    turn_target=turn_target,
                )
            )
            return
        try:
            finish_interpretation(
                interpret(payload),
                append_user=append_user,
                initial=initial,
                turn_target=turn_target,
            )
        except Exception as error:
            fail_interpretation(error, turn_target=turn_target)

    def collapse_inline_goal(
        event: object | None = None,
        *,
        focus_goal: bool = True,
    ) -> bool:
        if not inline_goal_open["value"]:
            return False
        inline_goal_open["value"] = False
        inline_goal_original["value"] = ""
        direct_edit_area.text = ""
        composer.frame.title = "MESSAGE"
        input_area.text = suspended_message["value"]
        suspended_message["value"] = ""
        sync_input_host()
        if focus_goal:
            application.layout.focus(goal_pane.text_area)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def collapse_inline_context(
        event: object | None = None,
        *,
        focus_contexts_after: bool = True,
    ) -> bool:
        if not inline_context_open["value"]:
            return False
        inline_context_open["value"] = False
        inline_context_original["value"] = ""
        direct_edit_area.text = ""
        composer.frame.title = "MESSAGE"
        input_area.text = suspended_message["value"]
        suspended_message["value"] = ""
        sync_input_host()
        if focus_contexts_after:
            focus_contexts()
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def panel_comment_owner_area():
        return {
            "GOAL": goal_pane.text_area,
            "CONTEXTS": contexts_pane.text_area,
            "RULES": rules_pane.text_area,
            "MEMORIES": cases_pane.text_area,
            "CHAT": dialogue_pane.text_area,
        }.get(panel_comment_target["value"], dialogue_pane.text_area)

    def collapse_panel_comment(
        event: object | None = None,
        *,
        focus_owner: bool = True,
    ) -> bool:
        if panel_comment_target["value"] is None:
            return False
        owner = panel_comment_owner_area()
        panel_comment_target["value"] = None
        panel_comment_focus["value"] = ""
        composer.frame.title = "MESSAGE"
        input_area.text = suspended_message["value"]
        suspended_message["value"] = ""
        sync_input_host()
        if focus_owner:
            application.layout.focus(owner)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def open_panel_comment(
        *,
        target: _GroundPane,
        focus: str,
    ) -> None:
        if mode["value"] not in {"INPUT", "CONTEXT_SELECTION"}:
            return
        acknowledge_pane(target)
        if target == "CHAT":
            # Chat already contains the ordinary Message field. Entering it
            # changes focus only and adds no synthetic FOCUS marker.
            application.layout.focus(input_area)
            application.invalidate()
            return
        suspended_message["value"] = input_area.text
        input_area.text = ""
        panel_comment_target["value"] = target
        panel_comment_focus["value"] = focus
        composer.frame.title = pane_turn_label(target)
        status_message["value"] = ""
        sync_input_host()
        application.layout.focus(input_area)
        application.invalidate()

    def finish_panel_comment() -> None:
        target = panel_comment_target["value"]
        if target is None:
            return
        comment = input_area.text.strip()
        if not comment:
            status_message["value"] = "Enter a nonblank agent comment first."
            application.invalidate()
            return
        focus = panel_comment_focus["value"] or target
        # Only the panel label and raw comment cross the blank-Ground boundary.
        # Provider-authored preview text is deliberately excluded so it cannot
        # be mistaken for USER_EXACT evidence on this follow-up turn.
        payload = "\n".join(
            [
                f"FOCUS · {focus}",
                INLINE_AGENT_COMMENT_TITLE,
                comment,
            ]
        )
        suspended_message["value"] = ""
        collapse_panel_comment(focus_owner=False)
        last_submission["value"] = payload
        last_submission_target["value"] = target
        last_submission_display["value"] = comment
        begin_interpretation(
            payload,
            append_user=True,
            turn_target=target,
            turn_display=comment,
        )

    def restore_suspended_context_approval(
        event: object | None = None,
    ) -> bool:
        proposal = suspended_context_proposal["value"]
        if (
            proposal is None
            or inline_context_open["value"]
            or mode["value"] != "CONTEXT_SELECTION"
        ):
            return False
        pending["value"] = proposal
        suspended_context_proposal["value"] = None
        mode["value"] = "APPROVAL"
        sync_input_host()
        status_message["value"] = (
            "Local Context edit cancelled; exact Ground approval restored."
        )
        sync_panes(dialogue_anchor="end")
        focus_contexts()
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    def complete_context_plan(*, allow_empty: bool = False) -> bool:
        selected = selected_context_names["value"]
        new_name = local_new_context_name["value"]
        if not selected and not new_name and not allow_empty:
            status_message["value"] = (
                "Select an existing Context with Space or enter a new "
                "Context name first."
            )
            application.invalidate()
            return False
        context_selection_finished["value"] = True
        sync_contexts_pane()
        parts = []
        if selected:
            parts.append(f"{len(selected)} existing")
        if new_name:
            parts.append("1 new local name")
        summary = " + ".join(parts) or "No Context plan"
        suspended = suspended_context_proposal["value"]
        if suspended is not None:
            pending["value"] = suspended
            suspended_context_proposal["value"] = None
            mode["value"] = "APPROVAL"
            sync_input_host()
            status_message["value"] = (
                f"{summary}. The Ground command is ready for a fresh Enter."
            )
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            application.invalidate()
            return True
        if mode["value"] == "CONTEXT_SELECTION" and pending["value"] is not None:
            # Context planning never expands the frozen creation command. A
            # future Context init and frame bind remain separate approvals.
            mode["value"] = "APPROVAL"
            sync_input_host()
            status_message["value"] = (
                f"{summary}. "
                "Enter approves only the Ground name and Goal."
            )
            focus_conversation()
        else:
            status_message["value"] = (
                f"{summary}. Continue in Message."
            )
            application.layout.focus(input_area)
        application.invalidate()
        return True

    def open_inline_context(*, prefill: str) -> None:
        if mode["value"] not in {"INPUT", "CONTEXT_SELECTION"}:
            return
        acknowledge_pane("CONTEXTS")
        inline_context_original["value"] = prefill
        suspended_message["value"] = input_area.text
        input_area.text = ""
        direct_edit_area.text = prefill
        direct_edit_area.buffer.cursor_position = len(prefill)
        composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        inline_context_open["value"] = True
        status_message["value"] = ""
        sync_input_host()
        application.layout.focus(direct_edit_area)
        application.invalidate()

    def finish_inline_context() -> None:
        original = inline_context_original["value"]
        edited = direct_edit_area.text
        comment = input_area.text.strip()
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        if submission_kind == "NOOP" and original:
            # Opening NEW? with N and submitting it unchanged is an explicit
            # acceptance
            # of that proposed exact name, even though no byte changed.
            submission_kind = "DIRECT"
        if submission_kind == "NOOP":
            collapse_inline_context(focus_contexts_after=True)
            status_message["value"] = (
                "No Context name or agent comment was submitted."
            )
            application.invalidate()
            return
        if submission_kind in {"DIRECT", "BOTH"}:
            try:
                exact_name = validate_new_context(edited)
            except (OSError, ValueError) as error:
                status_message["value"] = safe_terminal_text(str(error))
                application.invalidate()
                return
            if not isinstance(exact_name, str) or not exact_name:
                status_message["value"] = (
                    "The new Context validator returned no exact name."
                )
                application.invalidate()
                return
            local_new_context_name["value"] = exact_name
            conversation.append(
                "\n".join(
                    [
                        "YOU · NEW CONTEXT NAME (DIRECTLY)",
                        f"  {safe_terminal_text(exact_name)}",
                        "  PLANNED CONTEXT · NOT CREATED",
                    ]
                )
            )
        else:
            exact_name = ""

        suspended_message["value"] = ""
        collapse_inline_context(focus_contexts_after=False)
        if comment:
            # The agent receives the comment, never the catalog suggestion or
            # exact local name. Those remain process-local orientation and do
            # not become hidden provider evidence on a follow-up turn.
            blocks = [
                "FOCUS · NEW CONTEXT PLANNING",
                INLINE_AGENT_COMMENT_TITLE,
                comment,
            ]
            payload = "\n".join(blocks)
            last_submission["value"] = payload
            last_submission_target["value"] = "CONTEXTS"
            last_submission_display["value"] = comment
            begin_interpretation(
                payload,
                append_user=True,
                preserve_local_new_context=bool(exact_name),
                turn_target="CONTEXTS",
                turn_display=comment,
            )
            return
        sync_panes(dialogue_anchor="end")
        complete_context_plan()

    def open_inline_goal() -> None:
        if mode["value"] != "INPUT":
            return
        acknowledge_pane("GOAL")
        original = editable_goal["value"]
        inline_goal_original["value"] = original
        suspended_message["value"] = input_area.text
        input_area.text = ""
        direct_edit_area.text = original
        direct_edit_area.buffer.cursor_position = len(original)
        composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        inline_goal_open["value"] = True
        status_message["value"] = ""
        sync_input_host()
        application.layout.focus(direct_edit_area)
        application.invalidate()

    def finish_inline_goal() -> None:
        original = inline_goal_original["value"]
        edited = direct_edit_area.text
        comment = input_area.text.strip()
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        if submission_kind == "NOOP":
            collapse_inline_goal(focus_goal=True)
            status_message["value"] = "No edit or agent comment was submitted."
            application.invalidate()
            return
        if submission_kind in {"DIRECT", "BOTH"}:
            try:
                exact_goal = validate_ground_goal(
                    edited,
                    label="directly edited Ground goal",
                )
            except GroundError as error:
                status_message["value"] = safe_terminal_text(str(error))
                application.invalidate()
                return
            editable_goal["value"] = exact_goal
            required_direct_goal["value"] = exact_goal
            pending_inline_goal["value"] = (
                original,
                exact_goal,
                comment,
            )
            blocks = [
                "FOCUS · GOAL",
                "EDIT (DIRECTLY) · PRESERVE EXACTLY",
                exact_goal,
            ]
            if comment:
                blocks.extend(
                    [
                        "",
                        INLINE_AGENT_COMMENT_TITLE,
                        comment,
                    ]
                )
            payload = "\n".join(blocks)
            turn_display = (
                f"DIRECT GOAL\n{exact_goal}\n\n{comment}"
                if comment
                else f"DIRECT GOAL\n{exact_goal}"
            )
        else:
            pending_inline_goal["value"] = None
            blocks = ["FOCUS · GOAL"]
            if editable_goal["value"]:
                blocks.extend(
                    [
                        "CURRENT GOAL · DRAFT",
                        editable_goal["value"],
                    ]
                )
            blocks.extend([INLINE_AGENT_COMMENT_TITLE, comment])
            payload = "\n".join(blocks)
            turn_display = comment
        suspended_message["value"] = ""
        collapse_inline_goal(focus_goal=False)
        last_submission["value"] = payload
        last_submission_target["value"] = "GOAL"
        last_submission_display["value"] = turn_display
        begin_interpretation(
            payload,
            append_user=True,
            turn_target="GOAL",
            turn_display=turn_display,
        )

    input_mode = Condition(lambda: mode["value"] == "INPUT")
    context_selection_mode = Condition(
        lambda: mode["value"] == "CONTEXT_SELECTION"
    )
    inline_goal_mode = Condition(
        lambda: mode["value"] == "INPUT" and inline_goal_open["value"]
    )
    inline_context_mode = Condition(
        lambda: mode["value"] in {"INPUT", "CONTEXT_SELECTION"}
        and inline_context_open["value"]
    )
    inline_edit_mode = inline_goal_mode | inline_context_mode
    panel_comment_mode = Condition(
        lambda: mode["value"] in {"INPUT", "CONTEXT_SELECTION"}
        and panel_comment_target["value"] is not None
    )
    normal_input_mode = input_mode & ~inline_edit_mode & ~panel_comment_mode
    navigation_mode = (
        normal_input_mode | context_selection_mode
    ) & ~inline_edit_mode & ~panel_comment_mode
    approval_mode = Condition(lambda: mode["value"] == "APPROVAL")
    approval_dialogue_focus = approval_mode & has_focus(
        dialogue_pane.text_area
    )
    error_mode = Condition(lambda: mode["value"] == "ERROR")
    action_mode = Condition(
        lambda: mode["value"] in {"APPROVAL", "ERROR", "APPLY_ERROR"}
    )
    read_panes = (
        location_pane.text_area,
        goal_pane.text_area,
        contexts_pane.text_area,
        rules_pane.text_area,
        cases_pane.text_area,
        dialogue_pane.text_area,
    )
    read_pane_focus = (
        has_focus(location_pane.text_area)
        | has_focus(goal_pane.text_area)
        | has_focus(contexts_pane.text_area)
        | has_focus(rules_pane.text_area)
        | has_focus(cases_pane.text_area)
        | has_focus(dialogue_pane.text_area)
    )
    memory_pane_focus = (
        has_focus(cases_pane.text_area)
        & ~inline_edit_mode
        & Condition(lambda: bool(memory_drafts["value"]))
    )
    memory_table_focus = memory_pane_focus & Condition(
        lambda: memory_view["value"] == "TABLE"
    )
    inline_field_focus = inline_edit_mode & (
        has_focus(direct_edit_area) | has_focus(input_area)
    )
    # Preserve visual top-to-bottom order. Starting at Goal makes Shift-Tab
    # reach Location immediately, while ordinary Tab proceeds through the
    # semantic workbench and eventually wraps through Message and Location.
    focus_order = (*read_panes, input_area)
    focus_layers = {
        id(input_area): "CHAT",
        id(location_pane.text_area): "LOCATION",
        id(goal_pane.text_area): "GOAL",
        id(contexts_pane.text_area): "CONTEXTS",
        id(rules_pane.text_area): "RULES",
        id(cases_pane.text_area): "MEMORIES",
        id(dialogue_pane.text_area): "CHAT",
    }

    def acknowledge_focused_read_pane() -> None:
        for pane in read_panes:
            if application.layout.has_focus(pane):
                acknowledge_pane(focus_layers[id(pane)])
                return
    context_candidate_focus = (
        navigation_mode
        & has_focus(contexts_pane.text_area)
        & Condition(lambda: bool(ordered_context_rows()))
        & Condition(lambda: not context_selection_finished["value"])
    )
    finished_context_focus = (
        (input_mode | approval_mode)
        & has_focus(contexts_pane.text_area)
        & Condition(
            lambda: bool(ordered_context_rows())
            or bool(local_new_context_name["value"])
        )
        & Condition(lambda: context_selection_finished["value"])
    )
    approval_context_add_focus = (
        approval_mode
        & has_focus(contexts_pane.text_area)
        & Condition(lambda: not context_selection_finished["value"])
        & Condition(
            lambda: (
                context_cursor_row() is not None
                and context_cursor_row().kind == "ADD_NEW"
            )
        )
    )
    location_focus = has_focus(location_pane.text_area)
    location_edit_available = (
        (input_mode | approval_mode)
        & read_pane_focus
        & ~inline_edit_mode
        & ~panel_comment_mode
    )

    def choose_or_change_save_location(event) -> None:
        """Expand the focused compact Location into the shared tree editor."""

        acknowledge_pane("LOCATION")
        if choose_save_location is None:
            status_message["value"] = (
                "Save Location editing is unavailable in this adapter."
            )
            event.app.invalidate()
            return

        async def choose() -> None:
            result = await run_in_terminal(
                lambda: choose_save_location(planned_ground_name["value"]),
                in_executor=True,
            )
            if result is None:
                status_message["value"] = "Save Location change cancelled."
                application.invalidate()
                return
            exact_name = validate_portable_context_name(result)
            planned_ground_name["value"] = exact_name
            location_source["value"] = "SELECTED"
            if pending["value"] is not None:
                pending["value"] = replace(
                    pending["value"],
                    ground_name=exact_name,
                )
            if suspended_context_proposal["value"] is not None:
                suspended_context_proposal["value"] = replace(
                    suspended_context_proposal["value"],
                    ground_name=exact_name,
                )
            mark_pane_updates("LOCATION", "CONTEXTS", "CHAT")
            status_message["value"] = (
                f"Save Location selected · {safe_terminal_text(exact_name)} "
                "· NOT CREATED."
            )
            sync_panes(dialogue_anchor="end")
            application.invalidate()

        event.app.create_background_task(choose())

    @bindings.add("l", filter=location_edit_available, eager=True)
    @bindings.add("L", filter=location_edit_available, eager=True)
    def _choose_or_change_save_location(event) -> None:
        choose_or_change_save_location(event)

    @bindings.add(
        "enter",
        filter=location_edit_available & location_focus,
        eager=True,
    )
    def _expand_focused_save_location(event) -> None:
        choose_or_change_save_location(event)

    def cycle_focus(step: int) -> None:
        current_index = next(
            (
                index
                for index, element in enumerate(focus_order)
                if application.layout.has_focus(element)
            ),
            0,
        )
        target = focus_order[(current_index + step) % len(focus_order)]
        application.layout.focus(target)
        acknowledge_pane(focus_layers[id(target)])
        application.invalidate()

    def cycle_read_focus(step: int) -> None:
        current_index = next(
            (
                index
                for index, element in enumerate(read_panes)
                if application.layout.has_focus(element)
            ),
            len(read_panes) - 1,
        )
        target = read_panes[(current_index + step) % len(read_panes)]
        application.layout.focus(target)
        acknowledge_pane(focus_layers[id(target)])
        application.invalidate()

    @bindings.add("tab", filter=navigation_mode, eager=True)
    def _focus_next(_event) -> None:
        cycle_focus(1)

    @bindings.add(Keys.BackTab, filter=navigation_mode, eager=True)
    def _focus_previous(_event) -> None:
        cycle_focus(-1)

    @bindings.add("tab", filter=inline_edit_mode, eager=True)
    @bindings.add(Keys.BackTab, filter=inline_edit_mode, eager=True)
    def _cycle_inline_edit_fields(event) -> None:
        target = (
            input_area
            if event.app.layout.has_focus(direct_edit_area)
            else direct_edit_area
        )
        event.app.layout.focus(target)
        event.app.invalidate()

    @bindings.add(
        "tab",
        filter=~navigation_mode & ~inline_edit_mode & ~panel_comment_mode,
        eager=True,
    )
    def _focus_next_modal_pane(_event) -> None:
        # The composer is replaced by ACTION in modal states, but browsing a
        # read-only pane cannot edit or implicitly approve the frozen command.
        cycle_read_focus(1)

    @bindings.add(
        Keys.BackTab,
        filter=~navigation_mode & ~inline_edit_mode & ~panel_comment_mode,
        eager=True,
    )
    def _focus_previous_modal_pane(_event) -> None:
        cycle_read_focus(-1)

    @bindings.add(Keys.PageDown, filter=read_pane_focus, eager=True)
    def _page_down(event) -> None:
        acknowledge_focused_read_pane()
        scroll_wrapped_page(event, direction=1)

    @bindings.add(Keys.PageUp, filter=read_pane_focus, eager=True)
    def _page_up(event) -> None:
        acknowledge_focused_read_pane()
        scroll_wrapped_page(event, direction=-1)

    def focused_comment_target() -> tuple[str, str] | None:
        if application.layout.has_focus(goal_pane.text_area):
            return "GOAL", "GOAL"
        if application.layout.has_focus(contexts_pane.text_area):
            return "CONTEXTS", "CONTEXTS"
        if application.layout.has_focus(rules_pane.text_area):
            return "RULES", "RULES"
        if application.layout.has_focus(cases_pane.text_area):
            return "MEMORIES", "MEMORIES"
        if application.layout.has_focus(dialogue_pane.text_area):
            return "CHAT", "CHAT"
        return None

    @bindings.add(
        "c",
        filter=navigation_mode & read_pane_focus,
        eager=True,
    )
    def _open_focused_comment(_event) -> None:
        selected = focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        open_panel_comment(target=target, focus=focus)

    def toggle_memory_view() -> None:
        if not memory_drafts["value"]:
            return
        acknowledge_pane("MEMORIES")
        if memory_view["value"] == "LIST":
            selected_memory_index["value"] = (
                cases_pane.text_area.buffer.document.cursor_position_row
            )
            memory_view["value"] = "TABLE"
        else:
            memory_view["value"] = "LIST"
        sync_memories_pane(align_selection=True)
        application.invalidate()

    def move_memory_table_cell(*, row_step: int = 0, column_step: int = 0) -> None:
        acknowledge_pane("MEMORIES")
        row, column = clamp_table_position(
            row_count=len(memory_drafts["value"]),
            column_count=len(_BLANK_MEMORY_TABLE_COLUMNS),
            row=selected_memory_index["value"] + row_step,
            column=selected_memory_column["value"] + column_step,
        )
        selected_memory_index["value"] = row
        selected_memory_column["value"] = column
        sync_memories_pane(align_selection=True)
        application.invalidate()

    @bindings.add("v", filter=memory_pane_focus, eager=True)
    def _toggle_memory_view(_event) -> None:
        toggle_memory_view()

    @bindings.add("down", filter=memory_table_focus, eager=True)
    def _next_memory_table_row(_event) -> None:
        move_memory_table_cell(row_step=1)

    @bindings.add("up", filter=memory_table_focus, eager=True)
    def _previous_memory_table_row(_event) -> None:
        move_memory_table_cell(row_step=-1)

    @bindings.add("right", filter=memory_table_focus, eager=True)
    def _next_memory_table_column(_event) -> None:
        move_memory_table_cell(column_step=1)

    @bindings.add("left", filter=memory_table_focus, eager=True)
    def _previous_memory_table_column(_event) -> None:
        move_memory_table_cell(column_step=-1)

    def move_context_candidate(step: int) -> None:
        candidates = ordered_context_rows()
        if not candidates:
            return
        acknowledge_pane("CONTEXTS")
        context_candidate_index["value"] = max(
            0,
            min(
                context_candidate_index["value"] + step,
                len(candidates) - 1,
            ),
        )
        sync_contexts_pane(align_candidate=True)
        application.invalidate()

    @bindings.add("down", filter=context_candidate_focus, eager=True)
    def _next_context_candidate(_event) -> None:
        move_context_candidate(1)

    @bindings.add("up", filter=context_candidate_focus, eager=True)
    def _previous_context_candidate(_event) -> None:
        move_context_candidate(-1)

    @bindings.add(" ", filter=context_candidate_focus, eager=True)
    def _toggle_context_candidate(event) -> None:
        acknowledge_pane("CONTEXTS")
        row = context_cursor_row()
        if row is None:
            return
        if row.kind != "EXISTING":
            status_message["value"] = (
                "Press F to continue without a Context plan."
                if row.kind == "CONTINUE_EMPTY"
                else (
                    "Press P to open the direct ordinary Context tree."
                    if row.kind == "DIRECT_PICK"
                else (
                    "Press N to edit this new Context name; Space "
                    "selects existing Contexts only."
                )
                )
            )
            event.app.invalidate()
            return
        selected_name = row.context_name
        selected = list(selected_context_names["value"])
        if selected_name in selected:
            selected.remove(selected_name)
        else:
            # Selection order is meaningful only inside this view: the first
            # checked name is the local Main and later names are additional
            # hints. Actual frame roles still require a separate binding.
            selected.append(selected_name)
        selected_context_names["value"] = tuple(selected)
        sync_contexts_pane(align_candidate=True)
        status_message["value"] = (
            f"{len(selected)} Context(s) selected for this draft."
        )
        event.app.invalidate()

    @bindings.add("p", filter=context_candidate_focus, eager=True)
    @bindings.add("P", filter=context_candidate_focus, eager=True)
    def _direct_context_picker(event) -> None:
        if not context_catalog_names:
            status_message["value"] = "No ordinary Context names are available."
            event.app.invalidate()
            return

        async def choose() -> None:
            selected = selected_context_names["value"]
            result = await run_in_terminal(
                lambda: choose_context(
                    tuple(context_catalog_names),
                    current=(
                        selected[-1]
                        if selected and selected[-1] in context_catalog_names
                        else current_context_name
                    ),
                    app_input=app_input,
                    app_output=app_output,
                    require_tty=require_tty,
                ),
                # The nested picker owns a synchronous prompt-toolkit
                # Application. Run it off the outer Ground event loop so its
                # internal asyncio.run() remains valid.
                in_executor=True,
            )
            if result is None:
                status_message["value"] = "Direct Context selection cancelled."
            else:
                names = list(selected_context_names["value"])
                if result not in names:
                    names.append(result)
                selected_context_names["value"] = tuple(names)
                status_message["value"] = (
                    f"{len(names)} Context(s) selected for this draft."
                )
                sync_contexts_pane(align_candidate=True)
            application.invalidate()

        event.app.create_background_task(choose())

    @bindings.add("n", filter=context_candidate_focus, eager=True)
    def _edit_context_name_plan(event) -> None:
        row = context_cursor_row()
        if row is None:
            return
        if row.kind == "NEW_SUGGESTION":
            open_inline_context(prefill=row.context_name)
            return
        if row.kind == "ADD_NEW":
            open_inline_context(prefill=local_new_context_name["value"])
            return
        status_message["value"] = (
            "N edits NEW? or ADD NEW CONTEXT; Space selects existing "
            "Contexts."
        )
        event.app.invalidate()

    @bindings.add("f", filter=context_candidate_focus, eager=True)
    def _finish_context_selection(_event) -> None:
        acknowledge_pane("CONTEXTS")
        row = context_cursor_row()
        if row is not None and row.kind == "CONTINUE_EMPTY":
            local_new_context_name["value"] = ""
            complete_context_plan(allow_empty=True)
            return
        complete_context_plan()

    @bindings.add(
        "f",
        filter=finished_context_focus,
        eager=True,
    )
    def _reopen_context_selection(event) -> None:
        # Reopening changes only process-local checkmarks. The frozen Ground
        # creation argv remains pending and cannot run until a later Enter.
        context_selection_finished["value"] = False
        mode["value"] = "CONTEXT_SELECTION"
        sync_input_host()
        status_message["value"] = (
            "Context plan reopened · Space selects existing · F finishes · "
            "N edits a new name."
        )
        sync_contexts_pane(align_candidate=True)
        focus_contexts()
        event.app.invalidate()

    @bindings.add(
        "n",
        filter=approval_context_add_focus,
        eager=True,
    )
    def _open_add_context_from_approval(event) -> None:
        proposal = pending["value"]
        if proposal is None:
            return
        # N explicitly leaves the exact-approval layer before opening an
        # editor. The unchanged receipt is restored only after the local name
        # passes validation, so no pane editor coexists with approval mode.
        suspended_context_proposal["value"] = proposal
        pending["value"] = None
        mode["value"] = "CONTEXT_SELECTION"
        review_view["value"] = "COMMAND"
        status_message["value"] = (
            "Ground approval suspended while editing a local Context name."
        )
        sync_panes(dialogue_anchor="end")
        open_inline_context(prefill=local_new_context_name["value"])
        event.app.invalidate()

    @bindings.add(
        "enter",
        filter=(
            navigation_mode
            & read_pane_focus
            & ~has_focus(location_pane.text_area)
        ),
        eager=True,
    )
    def _talk_in_focused_pane(_event) -> None:
        selected = focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        open_panel_comment(target=target, focus=focus)

    @bindings.add(
        "e",
        filter=normal_input_mode & has_focus(goal_pane.text_area),
        eager=True,
    )
    def _open_goal_editor(_event) -> None:
        open_inline_goal()

    @bindings.add("enter", filter=inline_field_focus, eager=True)
    def _submit_inline_edit(_event) -> None:
        if inline_context_open["value"]:
            finish_inline_context()
        else:
            finish_inline_goal()

    @bindings.add(
        "enter",
        filter=panel_comment_mode & has_focus(input_area),
        eager=True,
    )
    def _submit_panel_comment(_event) -> None:
        finish_panel_comment()

    @bindings.add(
        "enter",
        filter=(
            has_focus(input_area)
            & ~inline_edit_mode
            & ~panel_comment_mode
        ),
        eager=True,
    )
    def _submit(event) -> None:
        text = input_area.text.strip()
        if not text:
            status_message["value"] = "Enter a nonblank description first."
            event.app.invalidate()
            return
        status_message["value"] = ""
        acknowledge_pane("CHAT")
        last_submission["value"] = text
        last_submission_target["value"] = "CHAT"
        last_submission_display["value"] = text
        input_area.text = ""
        begin_interpretation(
            text,
            append_user=True,
            turn_target="CHAT",
            turn_display=text,
        )

    @bindings.add(
        "c-j",
        filter=(
            (has_focus(input_area) & ~inline_edit_mode)
            | (inline_goal_mode & inline_field_focus)
            | (inline_context_mode & has_focus(input_area))
        ),
        eager=True,
    )
    def _insert_newline(event) -> None:
        event.app.current_buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add(
        "c-j",
        filter=inline_context_mode & has_focus(direct_edit_area),
        eager=True,
    )
    def _reject_newline_in_context_name(event) -> None:
        status_message["value"] = (
            "Context names are one line; press Tab to add a multiline comment."
        )
        event.app.invalidate()

    @bind_exact_command_approval(
        bindings,
        filter=approval_dialogue_focus,
        legacy_a_filter=approval_mode,
        eager=True,
    )
    def _approve(event) -> None:
        if mode["value"] != "APPROVAL" or pending["value"] is None:
            return
        # Freeze the reference before calling out.  Repeated keypresses cannot
        # approve another command because a successful call exits this app.
        proposal = pending["value"]
        mode["value"] = "APPLYING"
        event.app.invalidate()
        try:
            actual_output = apply(proposal)
        except Exception as error:
            conversation.append(
                "\n".join(
                    [
                        "APPLY FAILED",
                        f"  {safe_terminal_text(type(error).__name__)}: "
                        f"{safe_terminal_text(str(error))}",
                        "",
                        "The same approval will not be retried automatically.",
                    ]
                )
            )
            error_message["value"] = ""
            mark_pane_updates("CHAT")
            mode["value"] = "APPLY_ERROR"
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            event.app.invalidate()
            return
        event.app.exit(
            result=GroundShellResult(
                status="APPLIED",
                proposal=proposal,
                actual_output=str(actual_output),
                submitted_turns=tuple(submitted_turns),
                selected_context_names=selected_context_names["value"],
                new_context_name_hint=(
                    local_new_context_name["value"] or None
                ),
            )
        )

    @bindings.add("up", filter=approval_dialogue_focus, eager=True)
    @bindings.add("left", filter=approval_dialogue_focus, eager=True)
    def _show_command(event) -> None:
        if mode["value"] != "APPROVAL":
            return
        acknowledge_pane("CHAT")
        review_view["value"] = "COMMAND"
        sync_panes(dialogue_anchor="end")
        event.app.invalidate()

    @bindings.add("down", filter=approval_dialogue_focus, eager=True)
    @bindings.add("right", filter=approval_dialogue_focus, eager=True)
    def _show_effects(event) -> None:
        if mode["value"] != "APPROVAL":
            return
        acknowledge_pane("CHAT")
        review_view["value"] = "EFFECTS"
        sync_panes(dialogue_anchor="end")
        event.app.invalidate()

    @bindings.add("e", filter=action_mode, eager=True)
    def _refine(event) -> None:
        if mode["value"] not in {
            "CONTEXT_SELECTION",
            "APPROVAL",
            "ERROR",
            "APPLY_ERROR",
        }:
            return
        previous_mode = mode["value"]
        inline_draft = pending_inline_goal["value"]
        if pending["value"] is not None:
            # Refinement explicitly discards the frozen creation receipt, but
            # retains its reviewed Goal as the next editable unsaved draft.
            editable_goal["value"] = pending["value"].goal
        conversation.append(
            "REFINEMENT\n  Previous proposal or interpretation returned "
            "for revision."
        )
        if inline_draft is not None and previous_mode in {
            "CONTEXT_SELECTION",
            "APPROVAL",
            "ERROR",
        }:
            original, edited, comment = inline_draft
            focus_input(restore=False)
            open_inline_goal()
            # Reopen the same authority-bearing fields.  Treating the
            # host-framed exact edit as an ordinary Message would silently
            # downgrade it into provider-authored wording on resubmission.
            inline_goal_original["value"] = original
            direct_edit_area.text = edited
            direct_edit_area.buffer.cursor_position = len(edited)
            input_area.text = comment
            input_area.buffer.cursor_position = len(comment)
            event.app.invalidate()
            return
        if inline_draft is not None and previous_mode == "APPLY_ERROR":
            # The external command may have reached its mutation boundary
            # even though the shell did not receive confirmation.  Never
            # recreate the same direct proposal from an uncertain result.
            pending_inline_goal["value"] = None
            required_direct_goal["value"] = None
            focus_input(restore=False)
            status_message["value"] = (
                "The direct Goal edit was discarded after an unconfirmed "
                "apply; reopen Goal before proposing it again."
            )
            event.app.invalidate()
            return
        focus_input(restore=True)

    @bindings.add("r", filter=error_mode, eager=True)
    def _retry(event) -> None:
        if mode["value"] != "ERROR":
            return
        error_message["value"] = ""
        begin_interpretation(
            last_submission["value"],
            append_user=False,
            turn_target=last_submission_target["value"],
            turn_display=last_submission_display["value"],
        )

    def cancel(event) -> None:
        # Executor-backed provider work may finish after Escape. The closed
        # flag makes its result observationally inert: no proposal, apply, or
        # state mutation can occur after this shell has left the screen.
        shell_closed["value"] = True
        event.app.exit(
            result=GroundShellResult(
                status="CANCELLED",
                proposal=(
                    pending["value"]
                    or suspended_context_proposal["value"]
                ),
                submitted_turns=tuple(submitted_turns),
                selected_context_names=selected_context_names["value"],
                new_context_name_hint=(
                    local_new_context_name["value"] or None
                ),
            )
        )

    @bindings.add("b", filter=read_pane_focus, eager=True)
    def _back_to_picker(event) -> None:
        # Returning to the launcher never applies the pending creation
        # receipt. It does carry the exact validated proposal so the caller
        # can publish a separately typed NOT CREATED resume receipt first.
        shell_closed["value"] = True
        event.app.exit(
            result=GroundShellResult(
                status="BACK_TO_PICKER",
                proposal=(
                    pending["value"]
                    or suspended_context_proposal["value"]
                ),
                submitted_turns=tuple(submitted_turns),
                selected_context_names=selected_context_names["value"],
                new_context_name_hint=(
                    local_new_context_name["value"] or None
                ),
            )
        )

    @bind_case_insensitive_key(bindings, "q", filter=read_pane_focus, eager=True)
    def _quit_ground(event) -> None:
        cancel(event)

    bind_session_help(
        bindings,
        filter=read_pane_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="ground",
    )

    @bindings.add("escape", eager=True)
    def _cancel_on_escape(event) -> None:
        dispatch_tui_back(
            event,
            collapse_panel_comment,
            collapse_inline_context,
            collapse_inline_goal,
            restore_suspended_context_approval,
            close=cancel,
        )

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _cancel_anywhere(event) -> None:
        cancel(event)

    def start_initial_turn() -> None:
        # The positional request is already USER TURN 1. Scheduling provider
        # work only after the event loop starts makes target-owned THINKING
        # visible, while keeping Escape responsive during the read-only call.
        begin_interpretation(
            working_goal,
            append_user=False,
            initial=True,
            turn_target="GOAL",
            turn_display=working_goal,
        )

    try:
        if initial_request.strip():
            submitted_turns.append(working_goal)
            if background_interpretation:
                return application.run(pre_run=start_initial_turn)
            start_initial_turn()
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return GroundShellResult(
            status="CANCELLED",
            proposal=(
                pending["value"] or suspended_context_proposal["value"]
            ),
            submitted_turns=tuple(submitted_turns),
            selected_context_names=selected_context_names["value"],
            new_context_name_hint=(local_new_context_name["value"] or None),
        )
    finally:
        shell_closed["value"] = True
