"""Read-only pane and approval rendering for the blank-Ground shell."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from memcommit.adapters.console.shared.command_progress import BUSY_FRAMES
from memcommit.adapters.console.shared.exact_command_review import (
    render_exact_command_blocks,
    render_exact_command_review,
)
from memcommit.adapters.console.shared.tui_primitives import anchored_fragments
from memcommit.adapters.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.components.table import (
    RenderedTuiTable,
    TuiTableColumn,
    TuiTableRow,
    render_tui_table,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name

from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundShellContextSuggestion,
    GroundShellMemoryDraft,
    GroundShellNewContextSuggestion,
    GroundShellProposal,
    GroundShellRuleDraft,
    _proposal_review,
)


_THINKING_SUFFIXES = BUSY_FRAMES
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
