"""Render persisted Ground-session snapshots and focused target views."""

from __future__ import annotations

from collections.abc import Iterable

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundError,
    GroundSession,
    accepted_ground_case_count,
    is_bound_ground_schema,
    resolve_ground_requirement,
    stale_ground_frames,
    target_requirement_status,
)
from memcommit.core.context import Context, Memory


def _count_items(session: GroundSession, kind: str) -> int:
    return sum(item.kind == kind for item in session.items)


def _display_ground_compatibility_token(value: str) -> str:
    """Translate persisted Case-era tokens only for user-facing output."""
    if value in {"DISTILLED_FROM_GOAL", "INDUCED_FROM_CASES"}:
        return "DISTILLED"
    for action in ("ACCEPT", "DEFER", "REJECT", "REFINE"):
        if value == f"{action} CASE":
            return f"{action} MEMORY"
    return value


def _frame_contexts_by_uid(
    contexts: Iterable[Context],
) -> dict[str, Context]:
    return {context.uid: context for context in contexts}


def _accepted_case_count(session: GroundSession, target_uid: str) -> int:
    return accepted_ground_case_count(session, target_uid)


def _render_unbound_snapshot(session: GroundSession) -> str:
    open_issues = sum(
        item.kind == "ISSUE" and item.status != "RESOLVED" for item in session.items
    )
    goal = session.goal or "(not yet stated)"
    scope = ", ".join(session.scope) if session.scope else "(unbound)"
    lines = [
        (f"GROUND · {safe_terminal_text(session.contract_name)} · {session.status}"),
        f"Revision: {session.revision}",
        "",
        "GOAL",
        f"  {safe_terminal_text(goal)}",
        "",
        f"SCOPE  {safe_terminal_text(scope)}",
        (
            f"RULES {_count_items(session, 'RULE')} · "
            f"MEMORIES {_count_items(session, 'CASE')} · "
            f"UNRESOLVED {open_issues} · "
            f"DECISIONS {_count_items(session, 'DECISION')}"
        ),
        "",
        "No grounding material has been recorded.",
        "The session is ready to bind a Task description and Context frames.",
    ]
    return "\n".join(lines)


def _render_contract_layers(
    session: GroundSession,
    frame_name_by_uid: dict[str, str],
) -> list[str]:
    rules = [item for item in session.items if item.kind == "RULE"]
    cases = [item for item in session.items if item.kind == "CASE"]
    decisions = [item for item in session.items if item.kind == "DECISION"]
    lines = ["2 · RULES · STATED / DISTILLED / REVISED"]
    if not rules:
        lines.append(
            "  (none yet; state directly or distill from Goal and Ground Memories)"
        )
    for item in rules:
        provenance = _display_ground_compatibility_token(item.rule_provenance)
        lines.append(
            f"  [{item.status} · {provenance}] "
            f"[{item.uid[:8]}] "
            f"{safe_terminal_text(item.content)}"
        )
        if item.rationale:
            lines.append(f"    why: {safe_terminal_text(item.rationale)}")
    lines.extend(["", "3 · MEMORIES · FIT / BOUNDARY / CONTRAST"])
    if not cases:
        lines.append("  (none yet; proposed Ground Memories do not count as golden)")
    for item in cases:
        targets = ", ".join(
            frame_name_by_uid.get(uid, uid[:8]) for uid in item.target_context_uids
        )
        related_rules = ", ".join(
            f"[{uid[:8]}]"
            for uid in item.related_uids
            if any(rule.uid == uid for rule in rules)
        )
        lines.extend(
            [
                (
                    f"  [{item.status} · {item.case_role} · "
                    f"{item.disposition}] "
                    f"[{item.uid[:8]}]"
                ),
                (
                    f"    proposition: {safe_terminal_text(item.proposition)}"
                    if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                    else f"    input: {safe_terminal_text(item.content)}"
                ),
                f"    rule: {related_rules or '(all active Rules)'}",
            ]
        )
        if item.source_refs:
            source = item.source_refs[0]
            lines.append(
                f"    source: [{source.memory_uid[:8]}] in "
                f"{safe_terminal_text(frame_name_by_uid.get(source.context_uid, source.context_uid[:8]))} "
                f"· sha256:{source.content_digest[:12]}"
            )
        else:
            lines.append("    source: (not recorded)")
        lines.extend(
            [
                (
                    f"    target: {safe_terminal_text(targets)}"
                    if targets
                    else "    target: (none)"
                ),
                (
                    f"    output: {safe_terminal_text(item.expected)}"
                    if item.expected
                    else "    output: (none)"
                ),
                f"    notes: {safe_terminal_text(item.rationale)}",
            ]
        )
    if decisions:
        lines.extend(
            [
                "",
                f"REVISION LOG · {len(decisions)} decisions",
            ]
        )
        for item in decisions[-5:]:
            decision = _display_ground_compatibility_token(item.content)
            lines.append(
                f"  [{item.iteration}] {safe_terminal_text(decision)} "
                f"— {safe_terminal_text(item.rationale)}"
            )
    return lines


def render_ground_snapshot(
    session: GroundSession,
    contexts: Iterable[Context] | None = None,
) -> str:
    """Render a stable, control-character-safe grounding frame."""
    if not is_bound_ground_schema(session.schema_version):
        lines = _render_unbound_snapshot(session).splitlines()
        lines.extend(["", "METHOD READINGS"])
        for reference in session.references:
            lines.extend(
                [
                    (
                        f"  [{reference.reading_status} · agent-suggested] "
                        f"{safe_terminal_text(reference.title)}"
                    ),
                    f"    {safe_terminal_text(reference.url)}",
                ]
            )
        lines.extend(
            [
                "",
                "No Context or Context Memory changes have been applied.",
                "No checkpoint has been created.",
            ]
        )
        return "\n".join(lines)

    contexts_loaded = contexts is not None
    current_contexts = tuple(contexts or ())
    current_by_uid = _frame_contexts_by_uid(current_contexts)
    stale_names = (
        set(stale_ground_frames(session, current_contexts))
        if contexts_loaded
        else set()
    )
    frame_by_uid = {frame.context_uid: frame for frame in session.frames}
    frame_name_by_uid = {
        frame.context_uid: frame.context_name for frame in session.frames
    }
    raw = next(frame for frame in session.frames if frame.role == "RAW_EVIDENCE")
    derived = next(
        frame for frame in session.frames if frame.role == "WORKING_CANDIDATES"
    )
    target_frames = [
        frame
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    ]
    freshness = (
        "FRESH"
        if contexts_loaded and not stale_names
        else ("STALE" if contexts_loaded else "BOUND")
    )
    lines = [
        (
            f"GROUND · {safe_terminal_text(session.contract_name)} · "
            f"{session.status} · {freshness}"
        ),
        f"Revision: {session.revision}",
        "",
        "SOURCE BRIEF · FIXED INPUT",
        f"  {safe_terminal_text(session.brief.content)}",
        "",
        "1 · GOAL",
        f"  {safe_terminal_text(session.goal or '(not yet stated)')}",
        "",
        "  TARGET REQUIREMENTS",
        (
            "    The Goal and requirements may be revised when Ground "
            "Memories expose a bad boundary."
        ),
    ]
    for requirement in session.requirements:
        frame = frame_by_uid[requirement.target_context_uid]
        status = target_requirement_status(session, requirement)
        accepted = _accepted_case_count(session, frame.context_uid)
        lines.append(
            f"    [{status:<7}] {safe_terminal_text(frame.context_name)} "
            f"· {frame.direct_memory_count} direct Memories "
            f"· {accepted}/{requirement.minimum_accepted_cases} accepted "
            f"[{requirement.uid[:8]}]"
        )
        lines.append(
            "               "
            + safe_terminal_text(requirement.description or "(not specified)")
        )
        if requirement.blocked_reason:
            lines.append(
                "               BLOCKED: "
                + safe_terminal_text(requirement.blocked_reason)
            )

    lines.extend(["", *_render_contract_layers(session, frame_name_by_uid)])
    lines.extend(
        [
            "",
            "WORKBENCH",
            (
                f"  {raw.direct_memory_count} RAW → "
                f"{derived.direct_memory_count} CANDIDATES → "
                f"{len(target_frames)} TARGETS"
            ),
        ]
    )
    display_role = {
        "RAW_EVIDENCE": "RAW",
        "WORKING_CANDIDATES": "DERIVED",
    }
    for frame in (raw, derived):
        marker = (
            "STALE"
            if frame.context_name in stale_names
            else ("FRESH" if contexts_loaded else "BOUND")
        )
        lines.append(
            f"  [{marker}] {display_role[frame.role]:<7} "
            f"{safe_terminal_text(frame.context_name)} "
            f"· {frame.direct_memory_count} Memories"
        )
    lines.append(
        "  TARGETS "
        f"{len(target_frames)} · DIRECT MEMORIES "
        f"{sum(frame.direct_memory_count for frame in target_frames)}"
    )

    candidate_context = current_by_uid.get(derived.context_uid)
    candidate_memories = (
        [item for item in candidate_context.iter_items() if isinstance(item, Memory)]
        if candidate_context is not None
        else []
    )
    lines.extend(["", "SELECTED CANDIDATE"])
    if derived.direct_memory_count == 0:
        lines.append("  (none; 0/0)")
    elif candidate_memories and session.cursor_position < len(candidate_memories):
        memory = candidate_memories[session.cursor_position]
        lines.extend(
            [
                (
                    f"  {session.cursor_position + 1}/"
                    f"{len(candidate_memories)} [{memory.uid[:8]}]"
                ),
                f"  {safe_terminal_text(memory.content)}",
            ]
        )
    else:
        lines.append(
            f"  {session.cursor_position + 1}/"
            f"{derived.direct_memory_count} (content not loaded)"
        )

    if stale_names:
        lines.extend(
            [
                "",
                "STALE FRAMES",
                *[f"  {safe_terminal_text(name)}" for name in sorted(stale_names)],
                "  Ground changes and Ground Memory decisions are blocked.",
            ]
        )

    lines.extend(["", "METHOD READINGS"])
    for reference in session.references:
        lines.append(
            f"  [{reference.reading_status} · agent-suggested] "
            f"{safe_terminal_text(reference.title)}"
        )
    lines.extend(
        [
            "",
            "Grounding changed only this named Ground.",
            "No Context or Context Memory changes have been applied.",
            "No checkpoint has been created.",
        ]
    )
    return "\n".join(lines)


def _focused_target(
    session: GroundSession,
    selector: str,
):
    requirement = resolve_ground_requirement(session, selector)
    frame_by_uid = {
        frame.context_uid: frame
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    }
    frame = frame_by_uid.get(requirement.target_context_uid)
    if frame is None:
        raise GroundError("Focused Ground target is missing or ambiguous.")
    return requirement, frame


def _current_direct_memory_count(context: Context | None) -> int | None:
    if context is None:
        return None
    return sum(isinstance(item, Memory) for item in context.iter_items())


def render_ground_focus(
    session: GroundSession,
    target_selector: str,
    contexts: Iterable[Context],
) -> str:
    """Render one compact, read-only Goal–Rules–Memories target frame."""
    if not is_bound_ground_schema(session.schema_version):
        raise GroundError("Bind the named Ground before focusing one of its targets.")
    current_contexts = tuple(contexts)
    current_by_uid = _frame_contexts_by_uid(current_contexts)
    stale_names = set(stale_ground_frames(session, current_contexts))
    requirement, target = _focused_target(session, target_selector)
    raw = next(frame for frame in session.frames if frame.role == "RAW_EVIDENCE")
    candidates = next(
        frame for frame in session.frames if frame.role == "WORKING_CANDIDATES"
    )
    freshness = "STALE" if stale_names else "FRESH"
    target_status = target_requirement_status(session, requirement)
    accepted = _accepted_case_count(session, target.context_uid)
    rules = [item for item in session.items if item.kind == "RULE"]
    cases = [item for item in session.items if item.kind == "CASE"]
    accepted_items = sum(
        item.kind in {"RULE", "CASE"} and item.status == "ACCEPTED"
        for item in session.items
    )

    def material_line(label: str, frame) -> str:
        current_count = _current_direct_memory_count(
            current_by_uid.get(frame.context_uid)
        )
        if frame.context_name not in stale_names:
            count = frame.direct_memory_count
            suffix = f"{count} Memories"
        elif current_count is None:
            suffix = f"{frame.direct_memory_count} bound Memories · current missing"
        else:
            suffix = (
                f"{frame.direct_memory_count} bound · {current_count} current Memories"
            )
        return f"  {label:<12}{safe_terminal_text(frame.context_name)} · {suffix}"

    lines = [
        (
            f"MEM GROUND · {safe_terminal_text(session.contract_name)} · "
            f"{session.status} · {freshness}"
        ),
        f"Revision: {session.revision}",
        f"FOCUS · {safe_terminal_text(target.context_name)}",
        "",
        "GOAL",
        f"  {safe_terminal_text(session.goal or '(not yet stated)')}",
        "",
        "BOUND MATERIAL",
        material_line("RAW", raw),
        material_line("CANDIDATES", candidates),
        material_line("TARGET", target),
        "",
        "MEM UNDERSTANDS",
        (f"  [{target_status}] {safe_terminal_text(requirement.description)}"),
    ]
    if requirement.blocked_reason:
        lines.extend(
            [
                (
                    "  The saved Ground records this missing material: "
                    f"{safe_terminal_text(requirement.blocked_reason)}"
                ),
                (
                    "  Bound evidence may support a target slice, but it "
                    "does not by itself remove this recorded gap."
                ),
            ]
        )
    else:
        lines.append(
            f"  Accepted support: {accepted}/"
            f"{requirement.minimum_accepted_cases} Ground Memories."
        )

    if stale_names:
        lines.extend(
            [
                "",
                "OPEN QUESTION · REQUIRED",
                (
                    "  The bound material changed. Create a fresh named "
                    "Ground or explicitly replace and rebind this one "
                    "before changing Goal, Rules, or Memories."
                ),
                "",
                "STALE BOUND MATERIAL",
                *[f"  {safe_terminal_text(name)}" for name in sorted(stale_names)],
            ]
        )
    elif requirement.blocked_reason:
        lines.extend(
            [
                "",
                "OPEN QUESTION · REQUIRED",
                (
                    "  How should the current evidence and the missing "
                    "target material divide this Ground?"
                ),
                "",
                "    1  SUPPORTED SLICE",
                (
                    "       Ground only Memories supported by the bound "
                    "evidence and keep the missing material explicit."
                ),
                "",
                "    2  FULL TARGET",
                (
                    "       Keep the full target as the scope boundary and "
                    "remain blocked until evidence is supplied."
                ),
                "",
                "  > 3  BOTH",
                (
                    "       Ground the supported Memories first, then record "
                    "the missing target requirements separately."
                ),
                "",
                "WHY THIS MATTERS",
                (
                    "  The answer changes the agreed scope and may "
                    "require one Goal or target-requirement command."
                ),
            ]
        )
    else:
        lines.extend(
            [
                "",
                "OPEN QUESTION · NEXT",
                "  Which one Ground layer should the next command change?",
                "",
                "    1  GOAL",
                "    2  RULES",
                "    3  MEMORIES",
            ]
        )

    lines.extend(
        [
            "",
            "REFINE, COMMENT, OR ENTER A DIFFERENT READING",
            "",
            "> ________________________________________________________________",
            "",
            "GROUND STATE",
            (
                f"  RULES {len(rules)} "
                f"({sum(item.status == 'PROPOSED' for item in rules)} "
                f"proposed) · "
                f"MEMORIES {len(cases)} "
                f"({sum(item.status == 'PROPOSED' for item in cases)} "
                f"proposed) · "
                f"ACCEPTED {accepted_items}"
            ),
            "",
            "NEXT",
            ("  The agent may propose one exact mem command from your reply."),
            ("  That command requires its own approval before the agent runs it."),
            "",
            "No Context or Context Memory changes have been applied.",
            "No checkpoint has been created.",
        ]
    )
    return "\n".join(lines)
