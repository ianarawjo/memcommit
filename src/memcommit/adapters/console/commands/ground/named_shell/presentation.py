"""Read-only terminal projection for an existing named Ground."""

from __future__ import annotations


from memcommit.adapters.console.text import (
    safe_terminal_text,
)
from memcommit.application.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundItem,
    GroundSession,
    is_bound_ground_schema,
)
from memcommit.application.operations.fit.ground_report import FitJudgment
from memcommit.application.operations.fit.store import GroundFitReceipt
from memcommit.adapters.console.commands.fit.presentation import fit_mark
from memcommit.application.operations.fit.application import FitResult
from memcommit.application.operations.ground.turn_dialogue import (
    GroundTurnDraft,
)

from memcommit.adapters.console.commands.ground.named_shell.proposal import (
    _aliased_items,
    _display_ground_compatibility_token,
    _item_aliases_by_uid,
    _line,
)


def _case_card_value(value: str) -> str:
    """Fold stored multiline Case text into one visible card row."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return safe_terminal_text(normalized).replace("\n", " ↵ ").replace("\t", " ⇥ ")


def _ground_item_target_names(
    session: GroundSession,
    item: GroundItem,
) -> tuple[str, ...]:
    names = {
        frame.context_uid: frame.context_name
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    }
    return tuple(names[uid] for uid in item.target_context_uids if uid in names)


def _alias_range(
    items: tuple[tuple[str, GroundItem], ...],
) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return f" · ID {items[0][0]}"
    return f" · IDs {items[0][0]}–{items[-1][0]}"


def render_named_ground_top_panel(session: GroundSession) -> str:
    """Render a compact fixed Goal–Rules–Memories state panel."""
    state = "BOUND" if is_bound_ground_schema(session.schema_version) else "UNBOUND"
    rules = _aliased_items(session, "RULE")
    cases = _aliased_items(session, "CASE")
    rule_summary = (
        "(none yet)"
        if not rules
        else (f"{rules[-1][0]} [{rules[-1][1].status}] {_line(rules[-1][1].content)}")
    )
    case_summary = (
        "(none yet)"
        if not cases
        else (f"{cases[-1][0]} [{cases[-1][1].status}] {_line(cases[-1][1].content)}")
    )
    return "\n".join(
        [
            (
                f"MEM GROUND · {safe_terminal_text(session.contract_name)} · "
                f"WORKING · SAVED · {state} · REV {session.revision}"
            ),
            "GOAL",
            f"  {_line(session.goal or '(not yet stated)')}",
            (
                f"RULES {len(rules)} · "
                f"{sum(item.status == 'PROPOSED' for _, item in rules)} "
                f"proposed{_alias_range(rules)}"
            ),
            f"  {rule_summary}",
            (
                f"MEMORIES {len(cases)} · "
                f"{sum(item.status == 'PROPOSED' for _, item in cases)} "
                f"proposed{_alias_range(cases)}"
            ),
            f"  {case_summary}",
        ]
    )


def render_named_ground_header(session: GroundSession) -> str:
    """Render the one-line identity/status row above the five work areas."""
    state = "BOUND" if is_bound_ground_schema(session.schema_version) else "UNBOUND"
    return (
        f" MEM GROUND · {safe_terminal_text(session.contract_name)} · "
        f"WORKING · SAVED · {state} · REV {session.revision}"
    )


def _coherence_finding_applies(finding, alias: str) -> bool:
    if alias not in finding.subject_aliases:
        return False
    if finding.status == "FIT" or not finding.material_aliases:
        return True
    return alias in finding.material_aliases


def _coherence_subject_mark(
    receipt: GroundFitReceipt | None,
    subject_uid: str,
) -> str:
    if receipt is None or receipt.report.coherence is None:
        return "·"
    if not receipt.current:
        return "◷"
    coherence = receipt.report.coherence
    subject = next(
        (item for item in coherence.subjects if item.uid == subject_uid),
        None,
    )
    if subject is None:
        return "·"
    findings = tuple(
        item
        for item in coherence.findings
        if _coherence_finding_applies(item, subject.alias)
    )
    return "!" if any(item.status != "FIT" for item in findings) else "✓"


def _coherence_issue_lines(
    receipt: GroundFitReceipt | None,
    subject_uid: str,
) -> tuple[str, ...]:
    if receipt is None or not receipt.current or receipt.report.coherence is None:
        return ()
    coherence = receipt.report.coherence
    subject = next(
        (item for item in coherence.subjects if item.uid == subject_uid),
        None,
    )
    if subject is None:
        return ()
    return tuple(
        f"{item.axis} · {item.status} · {safe_terminal_text(item.reason)}"
        for item in coherence.findings
        if item.status != "FIT" and _coherence_finding_applies(item, subject.alias)
    )


def _coherence_context_mark(receipt: GroundFitReceipt | None) -> str:
    if receipt is None or receipt.report.coherence is None:
        return "·"
    if not receipt.current:
        return "◷"
    return (
        "!"
        if any(
            item.axis == "CONTEXT" and item.status != "FIT"
            for item in receipt.report.coherence.findings
        )
        else "✓"
    )


def render_named_ground_goal_pane(
    session: GroundSession,
    *,
    fit_receipt: GroundFitReceipt | None = None,
) -> str:
    """Render the complete Goal without truncation."""
    if fit_receipt is None:
        return safe_terminal_text(session.goal or "(not yet stated)")
    return "\n".join(
        [
            f"FIT · {_coherence_subject_mark(fit_receipt, session.uid)}",
            safe_terminal_text(session.goal or "(not yet stated)"),
            *_coherence_issue_lines(fit_receipt, session.uid),
        ]
    )


def render_named_ground_contexts_pane(
    session: GroundSession,
    *,
    context_hints: tuple[str, ...] = (),
    new_context_hint: str | None = None,
    fit_receipt: GroundFitReceipt | None = None,
) -> str:
    """Render saved frame metadata without reading live Context contents."""
    if not is_bound_ground_schema(session.schema_version) or not session.frames:
        if context_hints or new_context_hint:
            hint_lines = [
                *(
                    f"{'MAIN' if index == 0 else 'ADDITIONAL'} · "
                    f"{safe_terminal_text(name)} · SUGGESTED"
                    for index, name in enumerate(context_hints)
                )
            ]
            if new_context_hint:
                hint_lines.append(
                    "NEW CONTEXT · "
                    f"{safe_terminal_text(new_context_hint)} · "
                    "PLANNED · NOT CREATED"
                )
            return "\n".join(
                [
                    "CONTEXT PLAN",
                    *hint_lines,
                    "",
                    "Create any NEW Context and assign frame roles through",
                    "separately reviewed commands.",
                    "Context Memory content was not opened.",
                ]
            )
        return "\n".join(
            [
                "UNBOUND",
                "",
                "Name the raw evidence, working candidates,",
                "publication target, and placement targets.",
                "No current Context is inferred.",
            ]
        )
    role_labels = {
        "RAW_EVIDENCE": "RAW EVIDENCE",
        "WORKING_CANDIDATES": "WORKING CANDIDATES",
        "PUBLICATION_TARGET": "PUBLICATION TARGET",
        "PLACEMENT_TARGET": "PLACEMENT TARGET",
    }
    blocks: list[str] = (
        [f"FIT · {_coherence_context_mark(fit_receipt)}"]
        if fit_receipt is not None
        else []
    )
    for frame in session.frames:
        counts = f"{frame.direct_memory_count} direct Memories"
        if frame.direct_item_count != frame.direct_memory_count:
            counts += f" · {frame.direct_item_count} direct items"
        blocks.append(
            "\n".join(
                [
                    role_labels[frame.role],
                    f"{safe_terminal_text(frame.context_name)} · {counts}",
                ]
            )
        )
    blocks.append("Recorded binding; freshness is rechecked before mutation.")
    return "\n\n".join(blocks)


def render_named_ground_rules_pane(
    session: GroundSession,
    *,
    drafts: tuple[GroundTurnDraft, ...] = (),
    selected_draft_index: int = 0,
    drafts_stale: bool = False,
    selected_rule_index: int | None = None,
    placement_hint: str = "",
    fit_receipt: GroundFitReceipt | None = None,
) -> str:
    """Render saved Rules and the current unsaved classified draft queue."""
    rules = _aliased_items(session, "RULE")
    blocks: list[str] = []
    if rules:
        blocks.append("SAVED RULES")
        for index, (alias, item) in enumerate(rules):
            provenance = _display_ground_compatibility_token(
                item.rule_provenance or item.origin
            )
            marker = "› " if index == selected_rule_index else ""
            fit_suffix = (
                f" · FIT {_coherence_subject_mark(fit_receipt, item.uid)}"
                if fit_receipt is not None
                else ""
            )
            lines = [
                f"{marker}{alias} [{item.status}] · "
                f"{safe_terminal_text(provenance)}{fit_suffix}",
                safe_terminal_text(item.content),
            ]
            lines.extend(_coherence_issue_lines(fit_receipt, item.uid))
            if item.rationale:
                lines.extend(
                    [
                        "WHY",
                        safe_terminal_text(item.rationale),
                    ]
                )
            target_names = _ground_item_target_names(session, item)
            lines.append(
                "PLACEMENT · "
                + (", ".join(target_names) if target_names else "(legacy unspecified)")
            )
            blocks.append("\n".join(lines))
    else:
        blocks.append("SAVED RULES\n(none yet)")

    if drafts:
        draft_heading = f"DRAFTS · PENDING · {len(drafts)}"
        if drafts_stale:
            draft_heading += " · RECLASSIFY REQUIRED"
        blocks.append(
            "\n".join(
                [
                    draft_heading,
                    (
                        "Press R to reclassify against the saved Ground."
                        if drafts_stale
                        else (
                            "Select a READY Rule and press R to review "
                            "one exact proposal."
                        )
                    ),
                ]
            )
        )
        for index, draft in enumerate(drafts):
            marker = "›" if index == selected_draft_index else " "
            alias = f"d{index + 1}"
            displayed_kind = "MEMORY" if draft.kind == "CASE" else draft.kind
            displayed_status = "STALE" if drafts_stale else draft.status
            lines = [
                (
                    f"{marker} {alias} [{displayed_kind} · "
                    f"{displayed_status}] "
                    f"{safe_terminal_text(draft.content)}"
                )
            ]
            if index == selected_draft_index:
                lines.extend(
                    [
                        "WHY",
                        safe_terminal_text(draft.classification_reason),
                        "SOURCE",
                        " | ".join(
                            safe_terminal_text(span) for span in draft.source_spans
                        ),
                    ]
                )
                if placement_hint:
                    lines.extend(
                        [
                            "PLACEMENT · DIRECT SELECTION",
                            safe_terminal_text(placement_hint),
                        ]
                    )
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_named_ground_memories_pane(
    session: GroundSession,
    *,
    selected_memory_index: int | None = None,
    placement_hint: str = "",
    fit_receipt: GroundFitReceipt | None = None,
) -> str:
    """Render saved Ground Memories as one compact, non-wrapping list."""
    cases = _aliased_items(session, "CASE")
    if not cases:
        return "(none yet)"
    fit_by_example = _fit_judgments_by_example(fit_receipt)
    rows = ["  USE ID  FIT EXAMPLE"]
    for index, (alias, item) in enumerate(cases):
        marker = "›" if index == selected_memory_index else " "
        fit_label = _fit_label(item.uid, fit_receipt, fit_by_example)
        # USE is the durable participation decision; FIT is an independently
        # computed receipt projection. Keep the two axes adjacent and do not
        # ask readers to decode the legacy FIT/BOUNDARY/CONTRAST authoring
        # classification, which does not change executable Fit membership.
        use = _memory_use_checkbox(item.disposition)
        qualifiers = [item.status] if item.status != "PROPOSED" else []
        qualifier_label = (
            f"[{' · '.join(safe_terminal_text(value) for value in qualifiers)}] "
            if qualifiers
            else ""
        )
        prefix = f"{marker} {use} {alias:<3} {fit_label}  {qualifier_label}"
        # LIST is the scanning surface: one durable Ground Memory must consume
        # one physical terminal row. Enter opens the selected record's complete
        # vertical detail without duplicating the list as a wide table.
        if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
            value = _case_card_value(item.proposition)
        else:
            expected = (
                _case_card_value(item.expected) if item.expected else "(no output)"
            )
            value = f"{_case_card_value(item.content)} → {expected}"
        rows.append(f"{prefix}{value}")
    if placement_hint:
        rows.extend(
            (
                "",
                "PLACEMENT · DIRECT SELECTION",
                safe_terminal_text(placement_hint),
            )
        )
    return "\n".join(rows)


def _memory_use_checkbox(disposition: str) -> str:
    """Project persisted Fit participation without changing its authority."""
    return {
        "INCLUDE": "[x]",
        "EXCLUDE": "[ ]",
        "UNRESOLVED": "[?]",
    }.get(disposition, "[?]")


def render_named_ground_memory_detail(
    session: GroundSession,
    *,
    selected_memory_index: int,
    fit_receipt: GroundFitReceipt | None = None,
) -> str:
    """Render one selected Ground Memory as an inspectable vertical record."""
    cases = _aliased_items(session, "CASE")
    if not cases:
        return "(none yet)"
    selected_memory_index = max(
        0,
        min(selected_memory_index, len(cases) - 1),
    )
    alias, item = cases[selected_memory_index]
    aliases = _item_aliases_by_uid(session)
    fit_by_example = _fit_judgments_by_example(fit_receipt)
    linked_rules = [
        f"{aliases[uid]} · {linked.content}"
        for uid in item.related_uids
        for linked in session.items
        if linked.uid == uid and uid in aliases and aliases[uid].startswith("r")
    ]
    context_names = {frame.context_uid: frame.context_name for frame in session.frames}
    sources = [
        (
            f"{context_names.get(source.context_uid, source.context_uid[:8])}"
            f" · {source.memory_uid[:8]}"
        )
        for source in item.source_refs
    ]
    targets = [context_names.get(uid, uid[:8]) for uid in item.target_context_uids]
    lines = [
        f"MEMORY · {alias}",
        f"STATUS · {safe_terminal_text(item.status)}",
        (
            f"USE · {_memory_use_checkbox(item.disposition)} "
            f"{safe_terminal_text(item.disposition)}"
        ),
        f"FIT · {_fit_label(item.uid, fit_receipt, fit_by_example)}",
    ]
    if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION:
        lines.extend(("", "PROPOSITION", safe_terminal_text(item.proposition)))
    lines.extend(
        (
            "",
            "INPUT",
            safe_terminal_text(item.content) if item.content else "(none)",
            "",
            "EXPECTED",
            safe_terminal_text(item.expected) if item.expected else "(none)",
            "",
            "RULES",
            *(safe_terminal_text(value) for value in linked_rules or ["(none)"]),
            "",
            "SOURCES",
            *(safe_terminal_text(value) for value in sources or ["(none)"]),
            "",
            "TARGETS",
            *(safe_terminal_text(value) for value in targets or ["(none)"]),
            "",
            "NOTES",
            safe_terminal_text(item.rationale) if item.rationale else "(none)",
        )
    )
    judgment = fit_by_example.get(item.uid)
    if judgment is not None:
        lines.extend(
            (
                "",
                f"FIT JUDGMENT · {safe_terminal_text(judgment.status)}",
                safe_terminal_text(judgment.reason),
            )
        )
        if judgment.observed:
            lines.extend(("OBSERVED", safe_terminal_text(judgment.observed)))
    coherence_issues = _coherence_issue_lines(fit_receipt, item.uid)
    if coherence_issues:
        lines.extend(("", "GROUND FIT", *coherence_issues))
    return "\n".join(lines)


def render_named_ground_cases_pane(session: GroundSession) -> str:
    """Compatibility alias for the former user-facing Cases renderer."""
    return render_named_ground_memories_pane(session)


def _fit_judgments_by_example(
    receipt: GroundFitReceipt | None,
) -> dict[str, FitJudgment]:
    if receipt is None:
        return {}
    return {judgment.example_uid: judgment for judgment in receipt.report.judgments}


def _fit_label(
    example_uid: str,
    receipt: GroundFitReceipt | None,
    judgments: dict[str, FitJudgment],
) -> str:
    judgment = judgments.get(example_uid)
    if receipt is None or judgment is None:
        return "·"
    coherence_mark = _coherence_subject_mark(receipt, example_uid)
    if coherence_mark in {"!", "◷"}:
        return coherence_mark
    return fit_mark(
        FitResult(receipt.report, receipt.current),
        status=judgment.status,
    )


def _initial_question(session: GroundSession) -> str:
    if not is_bound_ground_schema(session.schema_version):
        return "\n".join(
            [
                "OPEN QUESTION · BINDING",
                "  Which explicit Task description, raw Context, derived",
                "  Context, and publication target should this Ground bind?",
                "",
                "No current Context is inferred. Placement or blocked targets",
                "can be supplied when they are part of the intended Ground.",
            ]
        )
    proposed = [
        item
        for item in session.items
        if item.kind in {"RULE", "CASE"} and item.status == "PROPOSED"
    ]
    if proposed:
        return "\n".join(
            [
                "OPEN QUESTION · REVIEW OR CONTINUE",
                "  Should the latest proposed Rule or Ground Memory be accepted,",
                "  refined, deferred, or rejected?",
            ]
        )
    return "\n".join(
        [
            "OPEN QUESTION · NEXT",
            "  Which one Ground layer should the next command change:",
            "  Goal, Rules, or Memories?",
        ]
    )
