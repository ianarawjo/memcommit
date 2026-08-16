"""Persistent Goal–Rules–Memories TUI for one already named Ground."""
from __future__ import annotations

from dataclasses import dataclass, replace
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

from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    render_exact_command_blocks,
)
from memcommit.commands.context_picker import choose_context
from memcommit.commands.ground_shell import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
)
from memcommit.commands.session_help import bind_session_help
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
from memcommit.interfaces.tui.components.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.interfaces.tui.components.exact_command_review import (
    bind_exact_command_approval,
)
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
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.ground import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundItem,
    GroundSession,
    is_bound_ground_schema,
)
from memcommit.fit import FitJudgment, FitReport
from memcommit.fit_application import FitResult
from memcommit.fit_store import GroundFitReceipt
from memcommit.interfaces.fit import fit_fraction, fit_mark
from memcommit.ground_turn_dialogue import (
    GroundTurnDraft,
    GroundTurnDraftBatch,
)


class NamedGroundInterpreter(Protocol):
    def __call__(
        self,
        session: GroundSession,
        dialogue_text: str,
        draft_source_text: str,
    ) -> object:
        """Return an ASK object or one frozen command proposal."""


@dataclass(frozen=True)
class GroundCommandProposal:
    """One operation-specific action reduced to a frozen local argv."""

    kind: str
    understanding: str
    question: str
    review: ExactCommandReview
    expected_ground_uid: str
    expected_revision: int
    expected_state_digest: str
    expected_context_versions: tuple[str, ...] = ()
    application_payload: object | None = None


class NamedGroundApplier(Protocol):
    def __call__(
        self,
        session: GroundSession,
        proposal: GroundCommandProposal,
    ) -> tuple[GroundSession, str]:
        """Apply exactly one approved command and reload the Ground."""


class NamedGroundReloader(Protocol):
    def __call__(self, contract_name: str) -> GroundSession:
        """Reload one required named Ground from durable storage."""


class NamedGroundFitRunner(Protocol):
    def __call__(self, session: GroundSession) -> FitReport:
        """Run Fit through the application service, never by shelling out."""


class NamedGroundFitLookup(Protocol):
    def __call__(self, session: GroundSession) -> GroundFitReceipt | None:
        """Return the latest immutable Fit receipt for this Ground identity."""


class NamedGroundFitResolutionPreparer(Protocol):
    def __call__(
        self,
        session: GroundSession,
        receipt: GroundFitReceipt,
        *,
        example_uid: str,
        action: str,
        content: str = "",
        rationale: str = "",
        rule_uid: str = "",
        use: str = "",
    ) -> GroundCommandProposal:
        """Freeze one Fit-bound Resolve plan as one exact reviewed action."""


@dataclass(frozen=True)
class _FitResolutionOption:
    """One visible response path for a selected non-FIT Example."""

    action: str
    label: str
    rule_uid: str = ""


@dataclass(frozen=True)
class _FitResolutionMenu:
    """Process-local picker bound to one immutable Fit judgment."""

    receipt_uid: str
    example_uid: str
    example_alias: str
    judgment: FitJudgment
    options: tuple[_FitResolutionOption, ...]
    selected_index: int = 0


@dataclass(frozen=True)
class _FitResolutionEdit:
    """Inline edit provenance retained until exact command review."""

    action: str
    example_uid: str
    rule_uid: str
    rationale: str


class NamedGroundDraftPreparer(Protocol):
    def __call__(
        self,
        session: GroundSession,
        draft: GroundTurnDraft,
    ) -> GroundCommandProposal:
        """Reduce one selected READY Rule draft to a frozen command."""


class NamedGroundProposalRetargeter(Protocol):
    def __call__(
        self,
        session: GroundSession,
        proposal: GroundCommandProposal,
        target_name: str,
    ) -> GroundCommandProposal:
        """Replace one proposal's placement with an exact local selection."""


class NamedGroundDirectEditPreparer(Protocol):
    def __call__(
        self,
        session: GroundSession,
        target: Literal["GOAL", "RULE", "MEMORY"],
        selector: str,
        edited: str,
        comment: str,
    ) -> GroundCommandProposal:
        """Freeze one exact pane-local replacement as one reviewed command."""


class NamedGroundUseTogglePreparer(Protocol):
    def __call__(
        self,
        session: GroundSession,
        selector: str,
    ) -> GroundCommandProposal:
        """Freeze one selected Example's next USE value as a reviewed command."""


@dataclass(frozen=True)
class NamedGroundShellResult:
    status: Literal["CLOSED", "BACK_TO_PICKER"]
    session: GroundSession
    applied_argvs: tuple[tuple[str, ...], ...] = ()
    submitted_turns: tuple[str, ...] = ()


def _line(value: str, limit: int = 110) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _case_card_value(value: str) -> str:
    """Fold stored multiline Case text into one visible card row."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return (
        safe_terminal_text(normalized)
        .replace("\n", " ↵ ")
        .replace("\t", " ⇥ ")
    )


def _aliased_items(
    session: GroundSession,
    kind: str,
) -> tuple[tuple[str, GroundItem], ...]:
    prefix = "r" if kind == "RULE" else "c"
    return tuple(
        (f"{prefix}{number}", item)
        for number, item in enumerate(
            (item for item in session.items if item.kind == kind),
            start=1,
        )
    )


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


def _display_ground_compatibility_token(value: str) -> str:
    """Translate persisted Case-era tokens only at the presentation boundary."""
    if value in {"DISTILLED_FROM_GOAL", "INDUCED_FROM_CASES"}:
        return "DISTILLED"
    return value


def render_named_ground_top_panel(session: GroundSession) -> str:
    """Render a compact fixed Goal–Rules–Memories state panel."""
    state = (
        "BOUND"
        if is_bound_ground_schema(session.schema_version)
        else "UNBOUND"
    )
    rules = _aliased_items(session, "RULE")
    cases = _aliased_items(session, "CASE")
    rule_summary = (
        "(none yet)"
        if not rules
        else (
            f"{rules[-1][0]} [{rules[-1][1].status}] "
            f"{_line(rules[-1][1].content)}"
        )
    )
    case_summary = (
        "(none yet)"
        if not cases
        else (
            f"{cases[-1][0]} [{cases[-1][1].status}] "
            f"{_line(cases[-1][1].content)}"
        )
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
    state = (
        "BOUND"
        if is_bound_ground_schema(session.schema_version)
        else "UNBOUND"
    )
    return (
        f" MEM GROUND · {safe_terminal_text(session.contract_name)} · "
        f"WORKING · SAVED · {state} · REV {session.revision}"
    )


def render_named_ground_goal_pane(session: GroundSession) -> str:
    """Render the complete Goal without truncation."""
    return safe_terminal_text(session.goal or "(not yet stated)")


def render_named_ground_contexts_pane(
    session: GroundSession,
    *,
    context_hints: tuple[str, ...] = (),
    new_context_hint: str | None = None,
) -> str:
    """Render saved frame metadata without reading live Context contents."""
    if not is_bound_ground_schema(session.schema_version) or not session.frames:
        if context_hints or new_context_hint:
            hint_lines = [
                *(
                    f"{'MAIN' if index == 0 else 'ADDITIONAL'} · "
                    f"{safe_terminal_text(name)} · NOT BOUND"
                    for index, name in enumerate(context_hints)
                )
            ]
            if new_context_hint:
                hint_lines.append(
                    "NEW CONTEXT · "
                    f"{safe_terminal_text(new_context_hint)} · "
                    "LOCAL ONLY · NOT CREATED"
                )
            return "\n".join(
                [
                    "UNBOUND · LOCAL CONTEXT PLAN",
                    *hint_lines,
                    "",
                    "Create any NEW Context and assign frame roles through",
                    "separately reviewed commands.",
                    "No Context content was loaded or inferred.",
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
    blocks: list[str] = []
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
    blocks.append(
        "Recorded binding; freshness is rechecked before mutation."
    )
    return "\n\n".join(blocks)


def render_named_ground_rules_pane(
    session: GroundSession,
    *,
    drafts: tuple[GroundTurnDraft, ...] = (),
    selected_draft_index: int = 0,
    drafts_stale: bool = False,
    selected_rule_index: int | None = None,
    placement_hint: str = "",
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
            lines = [
                f"{marker}{alias} [{item.status}] · "
                f"{safe_terminal_text(provenance)}",
                safe_terminal_text(item.content),
            ]
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
        draft_heading = f"DRAFTS · NOT SAVED · {len(drafts)}"
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
            displayed_kind = (
                "MEMORY" if draft.kind == "CASE" else draft.kind
            )
            displayed_status = (
                "STALE" if drafts_stale else draft.status
            )
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
                            safe_terminal_text(span)
                            for span in draft.source_spans
                        ),
                    ]
                )
                if placement_hint:
                    lines.extend(
                        ["PLACEMENT · DIRECT SELECTION", safe_terminal_text(placement_hint)]
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
                _case_card_value(item.expected)
                if item.expected
                else "(no output)"
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
        if linked.uid == uid
        and uid in aliases
        and aliases[uid].startswith("r")
    ]
    context_names = {
        frame.context_uid: frame.context_name for frame in session.frames
    }
    sources = [
        (
            f"{context_names.get(source.context_uid, source.context_uid[:8])}"
            f" · {source.memory_uid[:8]}"
        )
        for source in item.source_refs
    ]
    targets = [
        context_names.get(uid, uid[:8]) for uid in item.target_context_uids
    ]
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
    return "\n".join(lines)


def render_named_ground_cases_pane(session: GroundSession) -> str:
    """Compatibility alias for the former user-facing Cases renderer."""
    return render_named_ground_memories_pane(session)


def _fit_judgments_by_example(
    receipt: GroundFitReceipt | None,
) -> dict[str, FitJudgment]:
    if receipt is None:
        return {}
    return {
        judgment.example_uid: judgment
        for judgment in receipt.report.judgments
    }


def _fit_label(
    example_uid: str,
    receipt: GroundFitReceipt | None,
    judgments: dict[str, FitJudgment],
) -> str:
    judgment = judgments.get(example_uid)
    if receipt is None or judgment is None:
        return "·"
    return fit_mark(
        FitResult(receipt.report, receipt.current),
        status=judgment.status,
    )


def _option_values(argv: tuple[str, ...], option: str) -> tuple[str, ...]:
    return tuple(
        argv[index + 1]
        for index, value in enumerate(argv[:-1])
        if value == option
    )


def _option_value(argv: tuple[str, ...], option: str) -> str:
    values = _option_values(argv, option)
    return values[0] if values else ""


def _item_aliases_by_uid(session: GroundSession) -> dict[str, str]:
    return {
        item.uid: alias
        for kind in ("RULE", "CASE")
        for alias, item in _aliased_items(session, kind)
    }


def _review_item_effects(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, ...]:
    argv = proposal.review.argv
    selector = _option_value(argv, "--decide")
    action = _option_value(argv, "--action").upper()
    target = next(
        (item for item in session.items if item.uid == selector),
        None,
    )
    if target is None or target.kind not in {"RULE", "CASE"}:
        return ()
    alias = _item_aliases_by_uid(session).get(target.uid, target.uid[:8])
    item_name = (
        "Ground Memory" if target.kind == "CASE" else target.kind.title()
    )
    statement = (
        target.proposition
        if (
            target.kind == "CASE"
            and session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
        )
        else target.content
    )
    details = [
        (
            f"Selected item: {alias} · {item_name} · {target.status} · "
            f"{_line(statement)}"
        )
    ]
    if action == "REFINE":
        replacement = _option_value(argv, "--response")
        if target.kind == "RULE":
            details.extend(
                [
                    (
                        f"REFINE: replace {alias} Rule content with "
                        f"'{_line(replacement)}'"
                    ),
                    (
                        f"{alias} remains PROPOSED; provenance becomes "
                        "JOINTLY_REVISED"
                    ),
                ]
            )
        else:
            field_name = (
                "proposition"
                if session.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                else "expected output"
            )
            details.extend(
                [
                    (
                        f"REFINE: replace {alias} {field_name} with "
                        f"'{_line(replacement)}'"
                    ),
                    (
                        f"{alias} remains PROPOSED; its source, linked Rule, "
                        "role, disposition, and targets remain unchanged"
                    ),
                ]
            )
    elif action in {"ACCEPT", "DEFER", "REJECT"}:
        status = {
            "ACCEPT": "ACCEPTED",
            "DEFER": "DEFERRED",
            "REJECT": "REJECTED",
        }[action]
        unchanged_field = (
            "proposition"
            if (
                target.kind == "CASE"
                and session.schema_version
                == GROUND_PROPOSITION_SCHEMA_VERSION
            )
            else "content"
        )
        details.append(
            f"{action}: mark {alias} {status}; its {unchanged_field} "
            "remains unchanged"
        )
    details.append("One review Decision record: ADD")
    return tuple(details)


def _proposal_item_effects(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, ...]:
    argv = proposal.review.argv
    if proposal.kind == "BIND":
        placements = _option_values(argv, "--placement-target")
        details = [
            f"Task binding: '{_line(_option_value(argv, '--description'))}'",
            (
                "Frames: raw="
                f"{_option_value(argv, '--raw-context')} · derived="
                f"{_option_value(argv, '--derived-context')}"
            ),
            (
                "Publication target: "
                f"{_option_value(argv, '--publication-target')}"
            ),
        ]
        if placements:
            details.append("Placement targets: " + ", ".join(placements))
        return tuple(details)
    if proposal.kind == "REVISE_GOAL":
        return (
            (
                "Replacement Goal: "
                f"'{_line(_option_value(argv, '--revise-goal'))}'"
            ),
            (
                "Reason: "
                f"{_line(_option_value(argv, '--change-reason'))}"
            ),
        )
    if proposal.kind == "PROPOSE_RULE":
        alias = f"r{len(_aliased_items(session, 'RULE')) + 1}"
        return (
            (
                f"New {alias} · PROPOSED Rule: "
                f"{_line(_option_value(argv, '--propose-rule'))}"
            ),
            (
                "Provenance: "
                f"{_display_ground_compatibility_token(_option_value(argv, '--rule-provenance'))}"
            ),
            f"Rationale: {_line(_option_value(argv, '--rationale'))}",
        )
    if proposal.kind == "PROPOSE_CASE":
        aliases = _item_aliases_by_uid(session)
        native = bool(_option_value(argv, "--propose-example"))
        rule_uid = _option_value(
            argv,
            "--example-rule" if native else "--fit-rule",
        )
        rule = next(
            (item for item in session.items if item.uid == rule_uid),
            None,
        )
        rule_alias = aliases.get(rule_uid, rule_uid[:8])
        alias = f"c{len(_aliased_items(session, 'CASE')) + 1}"
        details = [
            (
                f"New {alias} · PROPOSED "
                f"{_option_value(argv, '--case-role')}/"
                f"{_option_value(argv, '--disposition')} Ground Memory"
            ),
            (
                f"Linked Rule: {rule_alias}"
                + (f" · {_line(rule.content)}" if rule is not None else "")
            ),
            (
                "Targets: "
                + ", ".join(
                    _option_values(
                        argv,
                        "--example-target" if native else "--propose-target",
                    )
                )
            ),
            (
                "Expected output: "
                + (
                    _line(_option_value(argv, "--expected"))
                    or "(none for this disposition)"
                )
            ),
            (
                "Source: exact Context Memory selected from the bound "
                "candidate Context"
            ),
        ]
        if native:
            details.insert(
                1,
                "Proposition: "
                + _line(_option_value(argv, "--propose-example")),
            )
            exact_input = _option_value(argv, "--example-input")
            exact_expected = _option_value(argv, "--example-expected")
            details[4] = (
                "Exact projection: "
                + (
                    f"{_line(exact_input)} → {_line(exact_expected)}"
                    if exact_input and exact_expected
                    else "(none)"
                )
            )
        return tuple(details)
    if proposal.kind == "SET_EXAMPLE_USE":
        selector = _option_value(argv, "--set-example-use")
        use = _option_value(argv, "--use")
        aliases = _item_aliases_by_uid(session)
        item = next(
            (candidate for candidate in session.items if candidate.uid == selector),
            None,
        )
        alias = aliases.get(selector, selector[:8])
        before = item.disposition if item is not None else "UNKNOWN"
        return (
            f"Selected Memory: {alias}",
            f"USE: {before} -> {use}",
            "Future Fit and Ground Distill runs freeze this new participation set.",
        )
    if proposal.kind == "REVIEW_ITEM":
        return _review_item_effects(session, proposal)
    return ()


def render_named_ground_proposal_blocks(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, str]:
    """Render one Ground proposal with operation-aware approval context."""
    details = _proposal_item_effects(session, proposal)
    base_effects = proposal.review.effects
    if proposal.kind == "REVIEW_ITEM":
        base_effects = tuple(
            effect
            for effect in base_effects
            if not effect.startswith("Selected Rule/Ground Memory:")
            and not effect.startswith("One review Decision:")
        )
    informed_review = ExactCommandReview(
        argv=proposal.review.argv,
        effects=(*details, *base_effects),
    )
    return render_exact_command_blocks(informed_review)


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


def _response_kind(response: object) -> str:
    raw = getattr(response, "kind", None)
    if not isinstance(raw, str):
        raise ValueError("Ground turn has no ASK or action kind.")
    return raw


def _response_text(response: object, field_name: str) -> str:
    value = getattr(response, field_name, None)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Ground turn has no {field_name}.")
    return value.strip()


def run_named_ground_shell(
    session: GroundSession,
    *,
    interpret: NamedGroundInterpreter,
    apply: NamedGroundApplier,
    prepare_rule_draft: NamedGroundDraftPreparer | None = None,
    prepare_direct_edit: NamedGroundDirectEditPreparer | None = None,
    prepare_use_toggle: NamedGroundUseTogglePreparer | None = None,
    retarget_proposal: NamedGroundProposalRetargeter | None = None,
    reload_session: NamedGroundReloader | None = None,
    run_fit: NamedGroundFitRunner | None = None,
    lookup_fit: NamedGroundFitLookup | None = None,
    prepare_fit_resolution: NamedGroundFitResolutionPreparer | None = None,
    initial_receipt: str = "",
    context_hints: tuple[str, ...] = (),
    new_context_hint: str | None = None,
    placement_catalog_names: tuple[str, ...] = (),
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> NamedGroundShellResult:
    """Run repeated one-command Ground turns until the person closes the TUI."""
    if require_tty:
        require_interactive_terminal(
            "Interactive Ground",
            snapshot_hint=(
                f"Use 'mem ground {session.contract_name} --snapshot' "
                "outside a terminal."
            ),
        )

    current = {"value": session}
    fit_receipt: dict[str, GroundFitReceipt | None] = {
        "value": lookup_fit(session) if lookup_fit is not None else None
    }
    pending: dict[str, GroundCommandProposal | None] = {"value": None}
    draft_queue: dict[str, tuple[GroundTurnDraft, ...]] = {"value": ()}
    draft_index = {"value": 0}
    draft_queue_stale = {"value": False}
    draft_source_submission = {"value": ""}
    pending_draft_index: dict[str, int | None] = {"value": None}
    mode = {"value": "INPUT"}
    review_view = {"value": "COMMAND"}
    error_message = {"value": ""}
    status_message = {"value": ""}
    fit_turn: BackgroundExecutorTurn[FitReport] = BackgroundExecutorTurn()
    deferred_exit_status: dict[
        str, Literal["CLOSED", "BACK_TO_PICKER"]
    ] = {"value": "CLOSED"}
    last_submission = {"value": ""}
    inline_target: dict[
        str, Literal["GOAL", "RULE", "MEMORY"] | None
    ] = {"value": None}
    inline_selector = {"value": ""}
    inline_original = {"value": ""}
    inline_direct_locked = {"value": False}
    panel_comment_target: dict[
        str,
        Literal["GOAL", "CONTEXTS", "RULES", "MEMORIES", "CHAT"] | None,
    ] = {"value": None}
    panel_comment_focus = {"value": ""}
    pending_inline_edit: dict[
        str,
        tuple[
            Literal["GOAL", "RULE", "MEMORY"],
            str,
            str,
            str,
            str,
        ]
        | None,
    ] = {"value": None}
    suspended_message = {"value": ""}
    selected_rule_index = {"value": 0}
    selected_memory_index = {"value": 0}
    memory_detail_open = {"value": False}
    fit_resolution_menu: dict[str, _FitResolutionMenu | None] = {
        "value": None
    }
    fit_resolution_edit: dict[str, _FitResolutionEdit | None] = {
        "value": None
    }
    pending_fit_resolution_edit: dict[
        str, _FitResolutionEdit | None
    ] = {"value": None}
    bound_target_names = tuple(
        frame.context_name
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    )
    initial_placement_options = bound_target_names or tuple(placement_catalog_names)
    default_placement = next(
        (
            frame.context_name
            for frame in session.frames
            if frame.role == "PUBLICATION_TARGET"
        ),
        context_hints[0]
        if context_hints and context_hints[0] in initial_placement_options
        else initial_placement_options[0]
        if initial_placement_options
        else "",
    )
    placement_choice = {
        "CONTEXTS": default_placement,
        "RULES": default_placement,
        "MEMORIES": default_placement,
    }
    placement_overridden = {
        "CONTEXTS": False,
        "RULES": False,
        "MEMORIES": False,
    }

    def current_placement_options() -> tuple[str, ...]:
        bound = tuple(
            frame.context_name
            for frame in current["value"].frames
            if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
        )
        return bound or tuple(placement_catalog_names)
    # Notification dots track unseen process-local results, not completion or
    # agreement. A provider-selected focus does not count as the person's
    # explicit visit, and this state never enters the saved Ground or command
    # receipt.
    pane_notifications = {
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

    cycle_dialogue: list[str] = []
    all_submitted_turns: list[str] = []
    applied_argvs: list[tuple[str, ...]] = []
    conversation = [_initial_question(session)]
    if initial_receipt:
        conversation.insert(
            0,
            "APPLIED\n  " + safe_terminal_text(initial_receipt),
        )

    bindings = KeyBindings()
    # Goal stays compact because new/revised Goals are limited to 40 words.
    # The scrollbar preserves access to older records that predate that limit.
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

    def rendered_contexts(active: GroundSession) -> str:
        base = render_named_ground_contexts_pane(
            active,
            context_hints=context_hints,
            new_context_hint=new_context_hint,
        )
        if not placement_choice["CONTEXTS"]:
            return base
        return (
            base
            + "\n\nPLACEMENT TARGET · DIRECT SELECTION\n"
            + safe_terminal_text(placement_choice["CONTEXTS"])
            + " · P to choose from the Context tree"
        )
    goal_pane = build_scrollable_text_pane(
        "GOAL",
        render_named_ground_goal_pane(session),
        buffer_name="ground-named-goal",
        height=GROUND_GOAL_FRAME_HEIGHT,
        notification=lambda: pane_notifications["GOAL"],
    )
    contexts_pane = build_scrollable_text_pane(
        "CONTEXTS",
        rendered_contexts(session),
        buffer_name="ground-named-contexts",
        height=GROUND_CONTEXTS_FRAME_HEIGHT,
        notification=lambda: pane_notifications["CONTEXTS"],
    )
    rules_pane = build_scrollable_text_pane(
        "RULES",
        render_named_ground_rules_pane(
            session,
            selected_rule_index=0,
            placement_hint=placement_choice["RULES"],
        ),
        buffer_name="ground-named-rules",
        height=pane_height,
        notification=lambda: pane_notifications["RULES"],
    )
    cases_pane = build_scrollable_text_pane(
        "MEMORIES",
        render_named_ground_memories_pane(
            session,
            selected_memory_index=0,
            placement_hint=placement_choice["MEMORIES"],
            fit_receipt=fit_receipt["value"],
        ),
        buffer_name="ground-named-cases",
        height=pane_height,
        notification=lambda: pane_notifications["MEMORIES"],
    )
    # Saved Memories remain one physical row in List. Their Enter detail may
    # wrap naturally because it is a reading surface rather than a scanner.
    cases_pane.text_area.window.wrap_lines = Condition(
        lambda: memory_detail_open["value"]
    )

    def render_fit_resolution_menu() -> str:
        menu = fit_resolution_menu["value"]
        if menu is None:
            return ""
        lines = [
            (
                f"RESOLVE FIT ISSUE · {safe_terminal_text(menu.example_alias)} "
                f"· {safe_terminal_text(menu.judgment.status)}"
            ),
            f"  {safe_terminal_text(menu.judgment.reason)}",
        ]
        if menu.judgment.observed:
            lines.append(
                "  OBSERVED · "
                + safe_terminal_text(menu.judgment.observed)
            )
        lines.extend(
            (
                "",
                "CHOOSE ONE RESPONSE · NOTHING APPLIED",
            )
        )
        for index, option in enumerate(menu.options):
            marker = "›" if index == menu.selected_index else " "
            lines.append(f"{marker} {safe_terminal_text(option.label)}")
        lines.extend(
            (
                "",
                "Edits open the existing inline editor, then freeze one exact ",
                "Ground command. DEFER is process-local and changes nothing.",
            )
        )
        return "\n".join(lines)

    def conversation_text() -> str:
        blocks = list(conversation)
        resolution_menu = render_fit_resolution_menu()
        if resolution_menu:
            blocks.append(resolution_menu)
        proposal = pending["value"]
        if proposal is not None:
            command_block, effects_block = render_named_ground_proposal_blocks(
                current["value"],
                proposal,
            )
            blocks.append(
                effects_block
                if review_view["value"] == "EFFECTS"
                else command_block
            )
        if error_message["value"]:
            blocks.append(
                "TURN FAILED · NOTHING NEW APPLIED\n"
                f"  {safe_terminal_text(error_message['value'])}"
            )
        return "\n\n".join(blocks)

    dialogue_pane = build_scrollable_text_pane(
        "CHAT",
        conversation_text(),
        buffer_name="ground-named-dialogue",
        height=pane_height,
        notification=lambda: pane_notifications["CHAT"],
    )
    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="ground-named-message",
        height=message_height,
    )
    input_area = composer.text_area
    direct_editor = build_inline_direct_edit_input(
        buffer_name="ground-named-direct-edit",
    )
    direct_edit_area = direct_editor.text_area
    direct_edit_area.buffer.read_only = Condition(
        lambda: inline_direct_locked["value"]
    )
    header = Window(
        FormattedTextControl(
            lambda: render_named_ground_header(current["value"])
        ),
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
    fit_resolution_panel = Frame(
        Window(
            FormattedTextControl(
                "↑/↓ choose · Enter continue · Esc cancel"
            ),
            wrap_lines=True,
        ),
        title="FIT RESOLVE",
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
            else fit_resolution_panel
            if mode["value"] == "FIT_RESOLVE"
            else empty_action_panel
        )
    )
    def footer_text() -> str:
        if panel_comment_target["value"] is not None:
            return (
                " Enter · send focused comment    Ctrl-J · newline    "
                "Esc · collapse"
            )
        if inline_target["value"] is not None:
            if inline_direct_locked["value"]:
                return (
                    " Unbound saved Goal · comment only    "
                    "bind before direct edit    Esc · collapse"
                )
            return (
                " Enter · review edit/comment    Ctrl-J · newline    "
                "Tab/Shift-Tab · field    Esc · collapse"
            )
        if fit_turn.busy:
            activity = "." * ((fit_turn.frame % 3) + 1)
            close_state = (
                "CLOSE REQUESTED · waiting for receipt boundary"
                if fit_turn.close_requested
                else "Esc/Q closes after the receipt boundary"
            )
            return (
                f" FIT RUNNING{activity} · Ground and Contexts unchanged · "
                + close_state
            )
        if status_message["value"]:
            return f" {status_message['value']}"
        active_mode = mode["value"]
        if active_mode == "FIT_RESOLVE":
            return (
                " FIT RESOLVE: ↑/↓ · response    Enter · continue    "
                "Esc · cancel · nothing applied"
            )
        if (
            active_mode in {"INPUT", "APPROVAL"}
            and application.layout.has_focus(cases_pane.text_area)
            and _aliased_items(current["value"], "CASE")
        ):
            tail = (
                "E · edit selected"
                if active_mode == "INPUT"
                else "A · exact approval"
            )
            if memory_detail_open["value"]:
                return (
                    " MEMORY DETAIL: Esc/Backspace · list    "
                    f"Space · toggle USE    F · run Fit    X · resolve issue    "
                    "P · placement    "
                    f"C · comment    {tail}    "
                    "B · Grounds    Q · quit"
                )
            return (
                " MEMORIES: ↑/↓ Example · Space · toggle USE    "
                "Enter · details    F · run Fit    X · resolve issue    "
                f"P · placement    C · comment    {tail}    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "INPUT" and application.layout.has_focus(
            rules_pane.text_area
        ):
            if draft_queue["value"]:
                if draft_queue_stale["value"]:
                    return (
                        " Enter · talk here    R · reclassify drafts    "
                        "B · Grounds    Q · quit"
                    )
                return (
                    " ↑/↓ · draft    Enter · talk here    "
                    "P · placement    R · review READY Rule    B · Grounds    Q · quit"
                )
            return (
                " ↑/↓ · saved Rule    Enter · talk here    "
                "P · placement    E · edit selected    B · Grounds    Q · quit"
            )
        if active_mode == "INPUT" and application.layout.has_focus(
            goal_pane.text_area
        ):
            return (
                " Enter · talk here    E · edit Goal    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "INPUT":
            if application.layout.has_focus(contexts_pane.text_area):
                return (
                    " P · placement Context tree    Enter · talk here    "
                    "B · Grounds    Q · quit"
                )
            if application.layout.has_focus(input_area):
                return (
                    " Enter · send    Ctrl-J · newline    "
                    "Tab · panes (B Grounds · Q quit)"
                )
            return (
                " Enter · talk in this pane    C · same action    "
                "B · Grounds    Q · quit"
            )
        if active_mode == "APPROVAL":
            return (
                " One approval applies one exact command · "
                "B returns to Grounds · Q quits without approval"
            )
        if active_mode == "APPLY_ERROR":
            return " An unconfirmed command is never retried automatically"
        return " No Ground state changed from the failed turn"

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    normal_root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(goal_pane.container),
        TuiRegion(contexts_pane.container),
        TuiRegion(rules_pane.container),
        TuiRegion(cases_pane.container),
        TuiRegion(dialogue_pane.container),
        TuiRegion(action_panel),
        TuiRegion(footer),
    )
    # One writable buffer moves into the semantic pane that owns the current
    # exchange. Keeping a single outer Frame makes the interaction read as a
    # conversation *within* Goal, Contexts, Rules, Memories, or Chat rather
    # than as a detached sixth workbench component.
    input_manager = InFrameInputManager(
        goal_pane,
        contexts_pane,
        rules_pane,
        cases_pane,
        dialogue_pane,
    )

    def pane_for_layer(
        layer: str,
    ):
        return {
            "GOAL": goal_pane,
            "CONTEXTS": contexts_pane,
            "RULE": rules_pane,
            "RULES": rules_pane,
            "MEMORY": cases_pane,
            "MEMORIES": cases_pane,
            "CHAT": dialogue_pane,
        }.get(layer, dialogue_pane)

    def sync_input_host() -> None:
        input_manager.clear()
        if inline_target["value"] is not None:
            sections = [
                InFrameInputSection(
                    "EDIT (DIRECTLY)",
                    direct_edit_area,
                    height=embedded_field_height,
                    allow_read_only=inline_direct_locked["value"],
                )
            ]
            sections.append(
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    input_area,
                    height=embedded_field_height,
                )
            )
            input_manager.show(
                pane_for_layer(inline_target["value"]),
                *sections,
                height=direct_edit_pane_height,
            )
            return
        if panel_comment_target["value"] is not None:
            input_manager.show(
                pane_for_layer(panel_comment_target["value"]),
                InFrameInputSection(
                    INLINE_AGENT_COMMENT_TITLE,
                    input_area,
                    height=embedded_field_height,
                ),
                height=conversation_pane_height,
            )
            return
        if mode["value"] == "INPUT":
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
    application: Application[NamedGroundShellResult] = Application(
        layout=Layout(
            normal_root,
            focused_element=(
                input_area
                if input_manager.active_pane is not None
                else dialogue_pane.text_area
            ),
        ),
        key_bindings=bindings,
        full_screen=True,
        # Every focused read-only component is a real viewport. Keep page
        # navigation explicit so a prompt-toolkit default change cannot turn
        # Tab into focus-without-scroll.
        enable_page_navigation_bindings=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=MEMCOMMIT_TUI_STYLE,
    )
    # Ground has no Alt-prefixed actions. A short timeout lets a literal
    # Escape collapse the pane editor before the next navigation key arrives.
    application.ttimeoutlen = 0.05

    for pane in (
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

    def sync_rules_pane(
        *,
        align_draft: bool = False,
        align_saved: bool = False,
    ) -> None:
        rendered = render_named_ground_rules_pane(
            current["value"],
            drafts=draft_queue["value"],
            selected_draft_index=draft_index["value"],
            drafts_stale=draft_queue_stale["value"],
            selected_rule_index=(
                None
                if draft_queue["value"]
                else selected_rule_index["value"]
            ),
            placement_hint=placement_choice["RULES"],
        )
        rules_pane.set_text(rendered, anchor="preserve")
        if align_draft and draft_queue["value"]:
            marker = rendered.find(f"› d{draft_index['value'] + 1} ")
            if marker >= 0:
                # Cursor motion is only a viewport anchor; drafts remain
                # immutable until one exact proposal receives approval.
                rules_pane.text_area.buffer.cursor_position = marker
        elif align_saved and not draft_queue["value"]:
            marker = rendered.find(
                f"› r{selected_rule_index['value'] + 1} "
            )
            if marker >= 0:
                rules_pane.text_area.buffer.cursor_position = marker

    def sync_memories_pane(*, align_selection: bool = False) -> None:
        cases = _aliased_items(current["value"], "CASE")
        row = max(
            0,
            min(selected_memory_index["value"], max(0, len(cases) - 1)),
        )
        selected_memory_index["value"] = row
        if not cases:
            memory_detail_open["value"] = False
        if memory_detail_open["value"]:
            rendered_text = render_named_ground_memory_detail(
                current["value"],
                selected_memory_index=row,
                fit_receipt=fit_receipt["value"],
            )
            if placement_choice["MEMORIES"]:
                rendered_text += (
                    "\n\nPLACEMENT TARGET · DIRECT SELECTION\n"
                    + safe_terminal_text(placement_choice["MEMORIES"])
                )
            cases_pane.set_text(rendered_text, anchor="preserve")
            if align_selection:
                cases_pane.text_area.buffer.cursor_position = 0
            return
        rendered_text = render_named_ground_memories_pane(
            current["value"],
            selected_memory_index=row,
            placement_hint=placement_choice["MEMORIES"],
            fit_receipt=fit_receipt["value"],
        )
        cases_pane.set_text(rendered_text, anchor="preserve")
        if align_selection and cases:
            marker = rendered_text.find("› ")
            if marker >= 0:
                cases_pane.text_area.buffer.cursor_position = marker

    def sync_panes(*, dialogue_anchor: str = "end") -> None:
        active = current["value"]
        goal_pane.set_text(
            render_named_ground_goal_pane(active),
            anchor="preserve",
        )
        contexts_pane.set_text(
            rendered_contexts(active),
            anchor="preserve",
        )
        sync_rules_pane()
        sync_memories_pane()
        dialogue_pane.set_text(
            conversation_text(),
            anchor=dialogue_anchor,
        )

    def focus_conversation() -> None:
        application.layout.focus(dialogue_pane.text_area)

    def focus_input(*, restore: bool) -> None:
        mode["value"] = "INPUT"
        pending["value"] = None
        pending_inline_edit["value"] = None
        pending_fit_resolution_edit["value"] = None
        fit_resolution_menu["value"] = None
        fit_resolution_edit["value"] = None
        pending_draft_index["value"] = None
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

    def dialogue_text() -> str:
        return "\n\n".join(cycle_dialogue)

    def changed_pane_layers(
        previous: GroundSession,
        refreshed: GroundSession,
    ) -> tuple[str, ...]:
        """Identify saved layers that visibly changed after a reload/apply."""
        changed: list[str] = []
        if previous.goal != refreshed.goal:
            changed.append("GOAL")
        if (
            previous.schema_version,
            previous.frames,
        ) != (
            refreshed.schema_version,
            refreshed.frames,
        ):
            changed.append("CONTEXTS")
        for kind, layer in (("RULE", "RULES"), ("CASE", "MEMORIES")):
            before = tuple(item for item in previous.items if item.kind == kind)
            after = tuple(item for item in refreshed.items if item.kind == kind)
            if before != after:
                changed.append(layer)
        return tuple(changed)

    def refresh_current(*, announce: bool) -> bool:
        if reload_session is None:
            return False
        previous = current["value"]
        refreshed = reload_session(previous.contract_name)
        if not isinstance(refreshed, GroundSession):
            raise ValueError("Named Ground reload returned invalid state.")
        if refreshed.contract_name != previous.contract_name:
            raise ValueError("Named Ground reload changed its storage key.")
        if refreshed == previous:
            return False
        mark_pane_updates(*changed_pane_layers(previous, refreshed))
        current["value"] = refreshed
        if lookup_fit is not None:
            fit_receipt["value"] = lookup_fit(refreshed)
        selected_rule_index["value"] = min(
            selected_rule_index["value"],
            max(0, len(_aliased_items(refreshed, "RULE")) - 1),
        )
        selected_memory_index["value"] = min(
            selected_memory_index["value"],
            max(0, len(_aliased_items(refreshed, "CASE")) - 1),
        )
        cycle_dialogue.clear()
        fit_resolution_menu["value"] = None
        fit_resolution_edit["value"] = None
        pending_fit_resolution_edit["value"] = None
        draft_queue["value"] = ()
        draft_index["value"] = 0
        draft_queue_stale["value"] = False
        draft_source_submission["value"] = ""
        pending_draft_index["value"] = None
        if announce:
            mark_pane_updates("CHAT")
            conversation.append(
                "\n".join(
                    [
                        "GROUND REFRESHED",
                        "  Another saved change was found before this turn.",
                        (
                            "  The five workbench panes and semantic turn now use "
                            "the "
                            "latest Ground."
                        ),
                    ]
                )
            )
        sync_panes(dialogue_anchor="end")
        application.invalidate()
        return True

    def interpret_current(
        *,
        append_user: bool,
        text: str,
        focus: str = "",
    ) -> None:
        # Provider work and exact review are read-only presentation states;
        # no writable field remains mounted while either is active.
        input_manager.clear()
        try:
            refresh_current(announce=True)
            if append_user or not cycle_dialogue:
                user_turn_number = (
                    sum(
                        block.startswith("USER TURN ")
                        for block in cycle_dialogue
                    )
                    + 1
                )
                focus_line = f"\nFOCUS · {focus}" if focus else ""
                cycle_dialogue.append(
                    f"USER TURN {user_turn_number}{focus_line}\n{text}"
                )
            if append_user:
                all_submitted_turns.append(text)
                conversation.append(
                    (
                        f"YOU · COMMENT FOR {safe_terminal_text(focus)}\n"
                        if focus
                        else "YOU\n"
                    )
                    + f"  {safe_terminal_text(text)}"
                )
                if draft_queue["value"]:
                    # A correction or retraction can invalidate an earlier
                    # READY judgment before the provider answers. Only a
                    # successful replacement DRAFTS batch may clear this.
                    draft_queue_stale["value"] = True
            response = interpret(
                current["value"],
                dialogue_text(),
                text,
            )
            kind = _response_kind(response)
            understanding = _response_text(response, "understanding")
            question = _response_text(response, "question")
            agent_turn_number = (
                sum(
                    block.startswith("AGENT TURN ")
                    for block in cycle_dialogue
                )
                + 1
            )
            cycle_dialogue.append(
                "\n".join(
                    [
                        f"AGENT TURN {agent_turn_number}",
                        f"UNDERSTANDING\n{understanding}",
                        f"QUESTION\n{question}",
                    ]
                )
            )
            conversation.append(
                "\n".join(
                    [
                        (
                            "AGENT UNDERSTANDING"
                            if append_user
                            else "AGENT RETRY"
                        ),
                        f"  {safe_terminal_text(understanding)}",
                        "",
                        "AGENT QUESTION",
                        f"  {safe_terminal_text(question)}",
                    ]
                )
            )
            mark_pane_updates("CHAT")
            error_message["value"] = ""
            status_message["value"] = ""
            if kind == "ASK":
                focus_input(restore=False)
                return
            if isinstance(response, GroundTurnDraftBatch):
                draft_queue["value"] = response.drafts
                if response.drafts:
                    mark_pane_updates("RULES")
                draft_queue_stale["value"] = False
                draft_source_submission["value"] = response.raw_source
                draft_index["value"] = next(
                    (
                        index
                        for index, draft in enumerate(response.drafts)
                        if draft.kind == "RULE"
                        and draft.status == "READY"
                    ),
                    0,
                )
                pending["value"] = None
                pending_draft_index["value"] = None
                review_view["value"] = "COMMAND"
                mode["value"] = "INPUT"
                input_area.text = ""
                sync_input_host()
                status_message["value"] = (
                    f"{len(response.drafts)} unsaved draft(s) classified. "
                    "Review them in Rules."
                )
                conversation.append(
                    "\n".join(
                        [
                            "DRAFTS · NOT SAVED",
                            (
                                f"  {len(response.drafts)} independent "
                                "unit(s) classified from this turn."
                            ),
                            (
                                "  No Rule, Ground Memory, Context Memory, or "
                                "checkpoint changed."
                            ),
                        ]
                    )
                )
                sync_panes(dialogue_anchor="end")
                sync_rules_pane(align_draft=True)
                application.layout.focus(rules_pane.text_area)
                application.invalidate()
                return
            if not isinstance(response, GroundCommandProposal):
                raise ValueError(
                    "Ground action was not reduced to an exact command."
                )
            layer = {
                "BIND": "CONTEXTS",
                "PROPOSE_RULE": "RULES",
                "PROPOSE_CASE": "MEMORIES",
            }.get(response.kind)
            if (
                layer is not None
                and placement_overridden[layer]
                and retarget_proposal is not None
            ):
                response = retarget_proposal(
                    current["value"],
                    response,
                    placement_choice[layer],
                )
            pending["value"] = response
            pending_inline_edit["value"] = None
            review_view["value"] = "COMMAND"
            mode["value"] = "APPROVAL"
            input_area.text = ""
            sync_input_host()
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            application.invalidate()
        except Exception as error:
            pending["value"] = None
            error_message["value"] = f"{type(error).__name__}: {error}"
            status_message["value"] = ""
            mark_pane_updates("CHAT")
            mode["value"] = "ERROR"
            sync_input_host()
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            application.invalidate()

    def inline_owner_area():
        return {
            "GOAL": goal_pane.text_area,
            "RULE": rules_pane.text_area,
            "MEMORY": cases_pane.text_area,
        }.get(inline_target["value"], goal_pane.text_area)

    def collapse_inline_editor(
        event: object | None = None,
        *,
        focus_owner: bool = True,
    ) -> bool:
        if inline_target["value"] is None:
            return False
        owner = inline_owner_area()
        inline_target["value"] = None
        inline_selector["value"] = ""
        inline_original["value"] = ""
        inline_direct_locked["value"] = False
        fit_resolution_edit["value"] = None
        direct_edit_area.text = ""
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
        target: Literal["GOAL", "CONTEXTS", "RULES", "MEMORIES", "CHAT"],
        focus: str,
    ) -> None:
        if mode["value"] != "INPUT":
            return
        acknowledge_pane(target)
        if target == "CHAT":
            # Chat owns the ordinary whole-Ground Message composer already;
            # entering it only transfers focus and does not manufacture a
            # pane-scoped FOCUS marker.
            application.layout.focus(input_area)
            application.invalidate()
            return
        suspended_message["value"] = input_area.text
        input_area.text = ""
        panel_comment_target["value"] = target
        panel_comment_focus["value"] = focus
        composer.frame.title = INLINE_AGENT_COMMENT_TITLE
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
        suspended_message["value"] = ""
        collapse_panel_comment(focus_owner=False)
        last_submission["value"] = comment
        interpret_current(
            append_user=True,
            text=comment,
            focus=focus,
        )

    def open_inline_editor(
        *,
        target: Literal["GOAL", "RULE", "MEMORY"],
        selector: str,
        original: str,
    ) -> None:
        if mode["value"] != "INPUT":
            return
        acknowledge_pane(
            {"GOAL": "GOAL", "RULE": "RULES", "MEMORY": "MEMORIES"}[
                target
            ]
        )
        suspended_message["value"] = input_area.text
        input_area.text = ""
        inline_target["value"] = target
        inline_selector["value"] = selector
        inline_original["value"] = original
        inline_direct_locked["value"] = (
            not is_bound_ground_schema(current["value"].schema_version)
        )
        direct_edit_area.text = original
        direct_edit_area.buffer.cursor_position = len(original)
        composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        status_message["value"] = ""
        sync_input_host()
        application.layout.focus(
            input_area
            if inline_direct_locked["value"]
            else direct_edit_area
        )
        application.invalidate()

    def selected_saved_item(
        kind: Literal["RULE", "CASE"],
        index: int,
    ) -> tuple[str, GroundItem] | None:
        items = _aliased_items(current["value"], kind)
        if not items:
            return None
        return items[min(max(index, 0), len(items) - 1)]

    def finish_inline_submission() -> None:
        target = inline_target["value"]
        if target is None:
            return
        selector = inline_selector["value"]
        original = inline_original["value"]
        edited = direct_edit_area.text
        comment = input_area.text.strip()
        resolution_edit = fit_resolution_edit["value"]
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        focus_label = target if not selector else f"{target} {selector}"
        if submission_kind == "NOOP":
            collapse_inline_editor(focus_owner=True)
            status_message["value"] = "No edit or agent comment was submitted."
            application.invalidate()
            return
        if refresh_current(announce=True):
            collapse_inline_editor(focus_owner=False)
            input_area.text = comment
            status_message["value"] = (
                "The saved Ground changed. Reopen the pane before editing; "
                "your comment remains in Message."
            )
            application.layout.focus(input_area)
            application.invalidate()
            return
        if submission_kind == "COMMENT":
            # Restore the ordinary composer boundary before inference. The
            # focus marker is visible provider context; it is not a durable
            # selector or hidden provider session state.
            suspended_message["value"] = ""
            collapse_inline_editor(focus_owner=False)
            last_submission["value"] = comment
            interpret_current(
                append_user=True,
                text=comment,
                focus=focus_label,
            )
            return
        if resolution_edit is None and prepare_direct_edit is None:
            status_message["value"] = (
                "This shell cannot prepare a direct Ground edit."
            )
            application.invalidate()
            return
        if resolution_edit is not None and prepare_fit_resolution is None:
            status_message["value"] = (
                "This shell cannot prepare a Fit-bound Ground edit."
            )
            application.invalidate()
            return
        try:
            if resolution_edit is not None:
                receipt = fit_receipt["value"]
                if receipt is None or not receipt.current:
                    raise ValueError(
                        "The selected Fit receipt is missing or stale. Run Fit again."
                    )
                proposal = prepare_fit_resolution(
                    current["value"],
                    receipt,
                    example_uid=resolution_edit.example_uid,
                    action=resolution_edit.action,
                    content=edited,
                    rationale=comment or resolution_edit.rationale,
                    rule_uid=resolution_edit.rule_uid,
                )
            else:
                assert prepare_direct_edit is not None
                proposal = prepare_direct_edit(
                    current["value"],
                    target,
                    selector,
                    edited,
                    comment,
                )
        except Exception as error:
            status_message["value"] = (
                f"{type(error).__name__}: "
                f"{safe_terminal_text(str(error))}"
            )
            application.invalidate()
            return

        turn_lines = [
            f"DIRECT EDIT · {focus_label}",
            safe_terminal_text(edited),
        ]
        if comment:
            turn_lines.extend(
                [
                    "",
                    INLINE_AGENT_COMMENT_TITLE,
                    safe_terminal_text(comment),
                ]
            )
        submitted_text = "\n".join(turn_lines)
        all_submitted_turns.append(submitted_text)
        last_submission["value"] = comment or edited
        if draft_queue["value"]:
            # A direct correction is a new user turn even though no provider
            # rewrites it. Earlier READY semantic classifications no longer
            # retain authority if this exact proposal is refined or declined.
            draft_queue_stale["value"] = True
        conversation.append("YOU · " + submitted_text)
        conversation.append(
            "DIRECT WORDING FROZEN\n"
            "  The edited text was not rewritten by the provider.\n"
            "  It remains NOT SAVED until the exact command receives Enter."
        )
        suspended_message["value"] = ""
        pending_inline_edit["value"] = (
            target,
            selector,
            original,
            edited,
            comment,
        )
        pending_fit_resolution_edit["value"] = resolution_edit
        collapse_inline_editor(focus_owner=False)
        pending["value"] = proposal
        review_view["value"] = "COMMAND"
        mode["value"] = "APPROVAL"
        status_message["value"] = ""
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        focus_conversation()
        application.invalidate()

    input_mode = Condition(lambda: mode["value"] == "INPUT")
    inline_editor_mode = Condition(
        lambda: mode["value"] == "INPUT"
        and inline_target["value"] is not None
    )
    panel_comment_mode = Condition(
        lambda: mode["value"] == "INPUT"
        and panel_comment_target["value"] is not None
    )
    normal_input_mode = input_mode & ~inline_editor_mode & ~panel_comment_mode
    approval_mode = Condition(lambda: mode["value"] == "APPROVAL")
    fit_resolution_mode = Condition(
        lambda: mode["value"] == "FIT_RESOLVE"
    )
    approval_dialogue_focus = approval_mode & has_focus(
        dialogue_pane.text_area
    )
    error_mode = Condition(lambda: mode["value"] == "ERROR")
    action_mode = Condition(
        lambda: mode["value"] in {"APPROVAL", "ERROR", "APPLY_ERROR"}
    )
    read_panes = (
        goal_pane.text_area,
        contexts_pane.text_area,
        rules_pane.text_area,
        cases_pane.text_area,
        dialogue_pane.text_area,
    )
    read_pane_focus = (
        has_focus(goal_pane.text_area)
        | has_focus(contexts_pane.text_area)
        | has_focus(rules_pane.text_area)
        | has_focus(cases_pane.text_area)
        | has_focus(dialogue_pane.text_area)
    )
    memory_pane_focus = (
        has_focus(cases_pane.text_area)
        & ~inline_editor_mode
        & Condition(
            lambda: bool(_aliased_items(current["value"], "CASE"))
        )
    )
    memory_detail_focus = memory_pane_focus & Condition(
        lambda: memory_detail_open["value"]
    )
    rule_draft_focus = (
        input_mode
        & has_focus(rules_pane.text_area)
        & Condition(lambda: bool(draft_queue["value"]))
    )
    stale_rule_draft_focus = (
        rule_draft_focus
        & Condition(lambda: draft_queue_stale["value"])
    )
    saved_rule_focus = (
        normal_input_mode
        & has_focus(rules_pane.text_area)
        & Condition(lambda: not draft_queue["value"])
    )
    saved_memory_focus = (
        normal_input_mode
        & has_focus(cases_pane.text_area)
    )
    saved_memory_list_focus = saved_memory_focus & Condition(
        lambda: not memory_detail_open["value"]
    )
    inline_field_focus = inline_editor_mode & (
        has_focus(direct_edit_area) | has_focus(input_area)
    )
    focus_order = (input_area, *read_panes)
    focus_layers = {
        id(input_area): "CHAT",
        id(goal_pane.text_area): "GOAL",
        id(contexts_pane.text_area): "CONTEXTS",
        id(rules_pane.text_area): "RULES",
        id(cases_pane.text_area): "MEMORIES",
        id(dialogue_pane.text_area): "CHAT",
    }

    def focused_placement_layer() -> str | None:
        if application.layout.has_focus(contexts_pane.text_area):
            return "CONTEXTS"
        if application.layout.has_focus(rules_pane.text_area):
            return "RULES"
        if application.layout.has_focus(cases_pane.text_area):
            return "MEMORIES"
        return None

    placement_pane_focus = normal_input_mode & Condition(
        lambda: focused_placement_layer() is not None
    )

    @bindings.add("p", filter=placement_pane_focus, eager=True)
    @bindings.add("P", filter=placement_pane_focus, eager=True)
    def _choose_placement_target(event) -> None:
        layer = focused_placement_layer()
        if layer is None:
            return
        options = current_placement_options()
        if not options:
            status_message["value"] = (
                "No ordinary Context names are available for placement."
            )
            event.app.invalidate()
            return

        async def choose() -> None:
            result = await run_in_terminal(
                lambda: choose_context(
                    options,
                    current=(
                        placement_choice[layer]
                        if placement_choice[layer] in options
                        else options[0]
                    ),
                    app_input=app_input,
                    app_output=app_output,
                    require_tty=require_tty,
                )
            )
            if result is None:
                status_message["value"] = "Placement selection cancelled."
            else:
                placement_choice[layer] = result
                placement_overridden[layer] = True
                status_message["value"] = (
                    f"{layer} placement · {safe_terminal_text(result)} · "
                    "LOCAL UNTIL EXACT COMMAND APPROVAL"
                )
                sync_panes(dialogue_anchor="end")
            application.invalidate()

        event.app.create_background_task(choose())

    def acknowledge_focused_read_pane() -> None:
        for pane in read_panes:
            if application.layout.has_focus(pane):
                acknowledge_pane(focus_layers[id(pane)])
                return

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

    @bindings.add("tab", filter=normal_input_mode, eager=True)
    def _focus_next(_event) -> None:
        cycle_focus(1)

    @bindings.add(Keys.BackTab, filter=normal_input_mode, eager=True)
    def _focus_previous(_event) -> None:
        cycle_focus(-1)

    @bindings.add("tab", filter=inline_editor_mode, eager=True)
    @bindings.add(Keys.BackTab, filter=inline_editor_mode, eager=True)
    def _cycle_inline_fields(event) -> None:
        target = (
            input_area
            if event.app.layout.has_focus(direct_edit_area)
            else direct_edit_area
        )
        event.app.layout.focus(target)
        event.app.invalidate()

    @bindings.add("tab", filter=~input_mode, eager=True)
    def _focus_next_modal_pane(_event) -> None:
        cycle_read_focus(1)

    @bindings.add(Keys.BackTab, filter=~input_mode, eager=True)
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
            if not draft_queue["value"]:
                selected = selected_saved_item(
                    "RULE",
                    selected_rule_index["value"],
                )
                if selected is not None:
                    return "RULES", f"RULE {selected[0]}"
            # Draft text is provider-authored and is not resent as user
            # evidence; a draft-queue comment therefore anchors the pane only.
            return "RULES", "RULES"
        if application.layout.has_focus(cases_pane.text_area):
            selected = selected_saved_item(
                "CASE",
                selected_memory_index["value"],
            )
            if selected is not None:
                return "MEMORIES", f"MEMORY {selected[0]}"
            return "MEMORIES", "MEMORIES"
        if application.layout.has_focus(dialogue_pane.text_area):
            return "CHAT", "CHAT"
        return None

    @bindings.add(
        "c",
        filter=normal_input_mode & read_pane_focus,
        eager=True,
    )
    def _open_focused_comment(_event) -> None:
        selected = focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        open_panel_comment(target=target, focus=focus)

    def open_memory_detail() -> None:
        if not _aliased_items(current["value"], "CASE"):
            return
        acknowledge_pane("MEMORIES")
        memory_detail_open["value"] = True
        sync_memories_pane(align_selection=True)
        application.invalidate()

    def collapse_memory_detail(_event) -> bool:
        if not memory_detail_open["value"]:
            return False
        memory_detail_open["value"] = False
        sync_memories_pane(align_selection=True)
        return True

    @bindings.add("enter", filter=saved_memory_list_focus, eager=True)
    def _open_memory_detail(_event) -> None:
        open_memory_detail()

    @bindings.add(" ", filter=saved_memory_focus, eager=True)
    def _toggle_memory_use(event) -> None:
        selected = selected_saved_item(
            "CASE",
            selected_memory_index["value"],
        )
        if selected is None:
            return
        if prepare_use_toggle is None:
            status_message["value"] = (
                "This Ground adapter cannot change Example USE."
            )
            event.app.invalidate()
            return
        try:
            refresh_current(announce=True)
            selected = selected_saved_item(
                "CASE",
                selected_memory_index["value"],
            )
            if selected is None:
                raise ValueError("The selected Ground Memory no longer exists.")
            alias, item = selected
            proposal = prepare_use_toggle(current["value"], alias)
        except Exception as error:
            status_message["value"] = (
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
            event.app.invalidate()
            return
        conversation.append(
            "USE TOGGLE · "
            f"{safe_terminal_text(alias)}\n"
            f"  {_memory_use_checkbox(item.disposition)} "
            f"{safe_terminal_text(item.disposition)} remains saved until "
            "the exact command is approved."
        )
        pending["value"] = proposal
        pending_inline_edit["value"] = None
        review_view["value"] = "COMMAND"
        mode["value"] = "APPROVAL"
        status_message["value"] = ""
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        focus_conversation()
        event.app.invalidate()

    @bindings.add(
        "f",
        filter=normal_input_mode & memory_pane_focus,
        eager=True,
    )
    def _run_fit_from_cases(event) -> None:
        if run_fit is None:
            status_message["value"] = "Fit is unavailable in this Ground adapter."
            event.app.invalidate()
            return

        try:
            refresh_current(announce=True)
        except Exception as error:
            status_message["value"] = (
                "FIT FAILED · NOTHING APPLIED · "
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
            event.app.invalidate()
            return

        frozen_session = current["value"]

        def on_success(report: FitReport) -> None:
            if not isinstance(report, FitReport):
                raise ValueError("Ground Fit runner returned an invalid report.")
            if lookup_fit is None:
                fit_receipt["value"] = GroundFitReceipt(
                    report=report,
                    current=True,
                )
            else:
                fit_receipt["value"] = lookup_fit(current["value"])
            receipt = fit_receipt["value"]
            result = FitResult(
                report,
                current=receipt.current if receipt is not None else True,
            )
            status_message["value"] = (
                f"{fit_mark(result)} {fit_fraction(result)}"
            )
            mark_pane_updates("MEMORIES")
            sync_memories_pane(align_selection=True)

        def on_error(error: Exception) -> None:
            status_message["value"] = (
                "FIT FAILED · NOTHING APPLIED · "
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )

        def on_idle() -> None:
            application.layout.focus(cases_pane.text_area)

        def on_close() -> None:
            application.exit(
                result=NamedGroundShellResult(
                    status=deferred_exit_status["value"],
                    session=current["value"],
                    applied_argvs=tuple(applied_argvs),
                    submitted_turns=tuple(all_submitted_turns),
                )
            )

        status_message["value"] = "FIT RUNNING · Ground and Contexts unchanged"
        sync_memories_pane(align_selection=True)
        started = fit_turn.start(
            event.app,
            work=lambda: run_fit(frozen_session),
            on_success=on_success,
            on_error=on_error,
            on_idle=on_idle,
            on_close=on_close,
        )
        if not started:
            status_message["value"] = (
                "FIT ALREADY RUNNING · wait for the current receipt boundary"
            )
        event.app.invalidate()

    def selected_fit_issue() -> tuple[
        GroundFitReceipt, str, GroundItem, FitJudgment
    ]:
        receipt = fit_receipt["value"]
        if receipt is None:
            raise ValueError("Run Fit before resolving an Example.")
        if not receipt.current:
            raise ValueError("The Fit receipt is stale. Run Fit again.")
        selected = selected_saved_item(
            "CASE",
            selected_memory_index["value"],
        )
        if selected is None:
            raise ValueError("No saved Example is selected.")
        alias, item = selected
        judgments = tuple(
            judgment
            for judgment in receipt.report.judgments
            if judgment.example_uid == item.uid
        )
        if len(judgments) != 1:
            raise ValueError(
                "The current Fit receipt does not contain this Example."
            )
        judgment = judgments[0]
        if judgment.status == "FIT":
            raise ValueError(
                "The selected Example already fits the current Rules."
            )
        return receipt, alias, item, judgment

    @bindings.add(
        "x",
        filter=normal_input_mode & memory_pane_focus,
        eager=True,
    )
    @bindings.add(
        "X",
        filter=normal_input_mode & memory_pane_focus,
        eager=True,
    )
    def _open_fit_resolution(event) -> None:
        if prepare_fit_resolution is None:
            status_message["value"] = (
                "Fit Resolve is unavailable in this Ground adapter."
            )
            event.app.invalidate()
            return
        try:
            refresh_current(announce=True)
            receipt, alias, item, judgment = selected_fit_issue()
            rule_aliases = _item_aliases_by_uid(current["value"])
            rules_by_uid = {
                candidate.uid: candidate
                for candidate in current["value"].items
                if candidate.kind == "RULE"
            }
            rule_options = tuple(
                _FitResolutionOption(
                    action="REFINE_RULE",
                    rule_uid=rule_uid,
                    label=(
                        "REFINE RULE · "
                        f"{rule_aliases.get(rule_uid, rule_uid[:8])} · "
                        f"{_line(rules_by_uid[rule_uid].content)}"
                    ),
                )
                for rule_uid in judgment.rule_uids
                if rule_uid in rules_by_uid
            )
            next_use = (
                "EXCLUDE" if item.disposition == "INCLUDE" else "INCLUDE"
            )
            options = (
                _FitResolutionOption("REVISE_GOAL", "REVISE GOAL"),
                *rule_options,
                _FitResolutionOption(
                    "REFINE_EXAMPLE",
                    f"REFINE EXAMPLE · {alias}",
                ),
                _FitResolutionOption(
                    "SET_EXAMPLE_USE",
                    f"SET USE · {next_use}",
                ),
                _FitResolutionOption(
                    "DEFER",
                    "DEFER · KEEP EXPLICITLY UNRESOLVED",
                ),
            )
            fit_resolution_menu["value"] = _FitResolutionMenu(
                receipt_uid=receipt.report.uid,
                example_uid=item.uid,
                example_alias=alias,
                judgment=judgment,
                options=options,
            )
            mode["value"] = "FIT_RESOLVE"
            status_message["value"] = ""
            sync_input_host()
            sync_panes(dialogue_anchor="end")
            focus_conversation()
        except Exception as error:
            status_message["value"] = (
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
        event.app.invalidate()

    def move_fit_resolution(step: int) -> None:
        menu = fit_resolution_menu["value"]
        if menu is None:
            return
        selected_index = max(
            0,
            min(menu.selected_index + step, len(menu.options) - 1),
        )
        fit_resolution_menu["value"] = replace(
            menu,
            selected_index=selected_index,
        )
        sync_panes(dialogue_anchor="end")
        application.invalidate()

    def collapse_fit_resolution(event: object | None = None) -> bool:
        if fit_resolution_menu["value"] is None:
            return False
        fit_resolution_menu["value"] = None
        mode["value"] = "INPUT"
        status_message["value"] = "Fit Resolve cancelled · nothing applied"
        sync_input_host()
        sync_panes(dialogue_anchor="end")
        application.layout.focus(cases_pane.text_area)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            application.invalidate()
        return True

    @bindings.add("down", filter=fit_resolution_mode, eager=True)
    @bindings.add("right", filter=fit_resolution_mode, eager=True)
    def _next_fit_resolution(_event) -> None:
        move_fit_resolution(1)

    @bindings.add("up", filter=fit_resolution_mode, eager=True)
    @bindings.add("left", filter=fit_resolution_mode, eager=True)
    def _previous_fit_resolution(_event) -> None:
        move_fit_resolution(-1)

    @bindings.add("enter", filter=fit_resolution_mode, eager=True)
    def _choose_fit_resolution(event) -> None:
        menu = fit_resolution_menu["value"]
        if menu is None:
            return
        option = menu.options[menu.selected_index]
        receipt = fit_receipt["value"]
        if (
            receipt is None
            or not receipt.current
            or receipt.report.uid != menu.receipt_uid
        ):
            fit_resolution_menu["value"] = None
            mode["value"] = "INPUT"
            status_message["value"] = (
                "The Fit receipt changed. Run Fit and choose again."
            )
            sync_input_host()
            sync_panes(dialogue_anchor="end")
            application.layout.focus(cases_pane.text_area)
            event.app.invalidate()
            return
        if option.action == "DEFER":
            conversation.append(
                "\n".join(
                    (
                        "FIT ISSUE DEFERRED · NOTHING APPLIED",
                        (
                            f"  {safe_terminal_text(menu.example_alias)} · "
                            f"{safe_terminal_text(menu.judgment.status)}"
                        ),
                        f"  RECEIPT · {safe_terminal_text(menu.receipt_uid)}",
                        "  The Fit receipt and Ground remain unchanged.",
                        "  This acknowledgement is process-local, not durable.",
                    )
                )
            )
            fit_resolution_menu["value"] = None
            mode["value"] = "INPUT"
            status_message["value"] = "DEFERRED · NOTHING APPLIED"
            sync_input_host()
            sync_panes(dialogue_anchor="end")
            application.layout.focus(cases_pane.text_area)
            event.app.invalidate()
            return
        selected = selected_saved_item(
            "CASE",
            selected_memory_index["value"],
        )
        if selected is None or selected[1].uid != menu.example_uid:
            status_message["value"] = (
                "The selected Example changed. Open Resolve again."
            )
            fit_resolution_menu["value"] = None
            mode["value"] = "INPUT"
            sync_input_host()
            sync_panes(dialogue_anchor="end")
            application.layout.focus(cases_pane.text_area)
            event.app.invalidate()
            return
        alias, item = selected
        if option.action == "SET_EXAMPLE_USE":
            next_use = (
                "EXCLUDE" if item.disposition == "INCLUDE" else "INCLUDE"
            )
            try:
                proposal = prepare_fit_resolution(
                    current["value"],
                    receipt,
                    example_uid=menu.example_uid,
                    action=option.action,
                    rationale=menu.judgment.reason,
                    use=next_use,
                )
            except Exception as error:
                status_message["value"] = (
                    f"{type(error).__name__}: "
                    f"{safe_terminal_text(str(error))}"
                )
                event.app.invalidate()
                return
            conversation.append(
                "FIT RESOLVE · EXACT ACTION FROZEN\n"
                f"  {safe_terminal_text(alias)} · SET USE {next_use}\n"
                "  Nothing changes until Enter approves the displayed command."
            )
            fit_resolution_menu["value"] = None
            pending["value"] = proposal
            pending_inline_edit["value"] = None
            pending_fit_resolution_edit["value"] = None
            review_view["value"] = "COMMAND"
            mode["value"] = "APPROVAL"
            sync_input_host()
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            event.app.invalidate()
            return

        fit_resolution_edit["value"] = _FitResolutionEdit(
            action=option.action,
            example_uid=menu.example_uid,
            rule_uid=option.rule_uid,
            rationale=menu.judgment.reason,
        )
        fit_resolution_menu["value"] = None
        mode["value"] = "INPUT"
        if option.action == "REVISE_GOAL":
            open_inline_editor(
                target="GOAL",
                selector="",
                original=current["value"].goal,
            )
        elif option.action == "REFINE_RULE":
            rule = next(
                candidate
                for candidate in current["value"].items
                if candidate.uid == option.rule_uid
            )
            open_inline_editor(
                target="RULE",
                selector=_item_aliases_by_uid(current["value"])[rule.uid],
                original=rule.content,
            )
        else:
            open_inline_editor(
                target="MEMORY",
                selector=alias,
                original=(
                    item.proposition
                    if current["value"].schema_version
                    == GROUND_PROPOSITION_SCHEMA_VERSION
                    else item.expected
                ),
            )
        # The menu is a transient Chat projection. Repaint after mounting the
        # existing pane-local editor so the old choices cannot look active
        # while replacement text is being authored.
        sync_panes(dialogue_anchor="end")
        event.app.invalidate()

    def move_saved_item(
        *,
        kind: Literal["RULE", "CASE"],
        step: int,
    ) -> None:
        items = _aliased_items(current["value"], kind)
        if not items:
            return
        acknowledge_pane("RULES" if kind == "RULE" else "MEMORIES")
        state = (
            selected_rule_index
            if kind == "RULE"
            else selected_memory_index
        )
        state["value"] = max(
            0,
            min(state["value"] + step, len(items) - 1),
        )
        if kind == "RULE":
            sync_rules_pane(align_saved=True)
        else:
            sync_memories_pane(align_selection=True)
        application.invalidate()

    @bindings.add("down", filter=saved_rule_focus, eager=True)
    def _next_saved_rule(_event) -> None:
        move_saved_item(kind="RULE", step=1)

    @bindings.add("up", filter=saved_rule_focus, eager=True)
    def _previous_saved_rule(_event) -> None:
        move_saved_item(kind="RULE", step=-1)

    @bindings.add("down", filter=saved_memory_list_focus, eager=True)
    def _next_saved_memory(_event) -> None:
        move_saved_item(kind="CASE", step=1)

    @bindings.add("up", filter=saved_memory_list_focus, eager=True)
    def _previous_saved_memory(_event) -> None:
        move_saved_item(kind="CASE", step=-1)

    def move_rule_draft(step: int) -> None:
        drafts = draft_queue["value"]
        if not drafts:
            return
        acknowledge_pane("RULES")
        draft_index["value"] = max(
            0,
            min(draft_index["value"] + step, len(drafts) - 1),
        )
        status_message["value"] = ""
        sync_rules_pane(align_draft=True)
        application.invalidate()

    @bindings.add("down", filter=rule_draft_focus, eager=True)
    def _next_rule_draft(_event) -> None:
        move_rule_draft(1)

    @bindings.add("up", filter=rule_draft_focus, eager=True)
    def _previous_rule_draft(_event) -> None:
        move_rule_draft(-1)

    @bindings.add(
        "r",
        filter=rule_draft_focus & ~stale_rule_draft_focus,
        eager=True,
    )
    def _review_rule_draft(event) -> None:
        drafts = draft_queue["value"]
        if not drafts:
            return
        acknowledge_pane("RULES")
        if draft_queue_stale["value"]:
            status_message["value"] = (
                "The saved Ground changed. Press R to reclassify every "
                "remaining draft before command review."
            )
            event.app.invalidate()
            return
        selected_index = draft_index["value"]
        draft = drafts[selected_index]
        if draft.kind != "RULE" or draft.status != "READY":
            status_message["value"] = (
                f"d{selected_index + 1} is {draft.kind} · {draft.status}; "
                "add clarification in Message or choose a READY Rule."
            )
            event.app.layout.focus(input_area)
            event.app.invalidate()
            return
        if prepare_rule_draft is None:
            status_message["value"] = (
                "This shell has no Rule-draft command preparer."
            )
            event.app.invalidate()
            return
        try:
            if refresh_current(announce=True):
                status_message["value"] = (
                    "The saved Ground changed; submit the comment again so "
                    "its drafts can be reclassified."
                )
                sync_panes(dialogue_anchor="end")
                event.app.layout.focus(input_area)
                event.app.invalidate()
                return
            proposal = prepare_rule_draft(current["value"], draft)
            if placement_overridden["RULES"] and retarget_proposal is not None:
                proposal = retarget_proposal(
                    current["value"],
                    proposal,
                    placement_choice["RULES"],
                )
        except Exception as error:
            status_message["value"] = (
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
            event.app.layout.focus(input_area)
            event.app.invalidate()
            return
        pending["value"] = proposal
        pending_draft_index["value"] = selected_index
        review_view["value"] = "COMMAND"
        mode["value"] = "APPROVAL"
        # READY-draft review reaches approval without passing through the
        # ordinary provider-turn branch. Detach the shared composer here too:
        # an exact command receipt must never coexist with writable input.
        sync_input_host()
        status_message["value"] = ""
        conversation.append(
            "\n".join(
                [
                    f"DRAFT SELECTED · d{selected_index + 1}",
                    (
                        "  One READY Rule was reduced to the exact command "
                        "shown below."
                    ),
                    "  It is still NOT SAVED until Enter approves it.",
                ]
            )
        )
        sync_panes(dialogue_anchor="end")
        focus_conversation()
        event.app.invalidate()

    @bindings.add("r", filter=stale_rule_draft_focus, eager=True)
    def _reclassify_rule_drafts(event) -> None:
        if not draft_source_submission["value"]:
            status_message["value"] = (
                "The original submitted comment is no longer available."
            )
            event.app.invalidate()
            return
        status_message["value"] = "Reclassifying drafts against saved Ground…"
        last_submission["value"] = draft_source_submission["value"]
        interpret_current(
            append_user=False,
            text=draft_source_submission["value"],
        )

    @bindings.add(
        "e",
        filter=normal_input_mode & has_focus(goal_pane.text_area),
        eager=True,
    )
    def _edit_goal(_event) -> None:
        open_inline_editor(
            target="GOAL",
            selector="",
            original=current["value"].goal,
        )

    @bindings.add("e", filter=saved_rule_focus, eager=True)
    def _edit_saved_rule(event) -> None:
        selected = selected_saved_item(
            "RULE",
            selected_rule_index["value"],
        )
        if selected is None:
            status_message["value"] = (
                "No saved Rule is available; describe a new one in Message."
            )
            event.app.invalidate()
            return
        alias, item = selected
        open_inline_editor(
            target="RULE",
            selector=alias,
            original=item.content,
        )

    @bindings.add("e", filter=saved_memory_focus, eager=True)
    def _edit_saved_memory(event) -> None:
        selected = selected_saved_item(
            "CASE",
            selected_memory_index["value"],
        )
        if selected is None:
            status_message["value"] = (
                "No saved Ground Memory is available; describe one in "
                "Message."
            )
            event.app.invalidate()
            return
        alias, item = selected
        open_inline_editor(
            target="MEMORY",
            selector=alias,
            # Version 3 makes the proposition authoritative. Legacy version 2
            # keeps its exact source immutable and refines expected output.
            original=(
                item.proposition
                if current["value"].schema_version
                == GROUND_PROPOSITION_SCHEMA_VERSION
                else item.expected
            ),
        )

    @bindings.add(
        "enter",
        filter=(
            normal_input_mode
            & read_pane_focus
            & ~has_focus(cases_pane.text_area)
        ),
        eager=True,
    )
    def _talk_in_focused_pane(_event) -> None:
        selected = focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        open_panel_comment(target=target, focus=focus)

    @bindings.add("enter", filter=inline_field_focus, eager=True)
    def _submit_inline(_event) -> None:
        finish_inline_submission()

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
            & ~inline_editor_mode
            & ~panel_comment_mode
        ),
        eager=True,
    )
    def _submit(event) -> None:
        text = input_area.text.strip()
        if not text:
            status_message["value"] = "Enter a nonblank Ground turn first."
            event.app.invalidate()
            return
        acknowledge_pane("CHAT")
        last_submission["value"] = text
        input_area.text = ""
        interpret_current(append_user=True, text=text)

    @bindings.add(
        "c-j",
        filter=(
            (has_focus(input_area) & ~inline_editor_mode)
            | inline_field_focus
        ),
        eager=True,
    )
    def _insert_newline(event) -> None:
        event.app.current_buffer.insert_text("\n")
        event.app.invalidate()

    @bind_exact_command_approval(
        bindings,
        filter=approval_dialogue_focus,
        legacy_a_filter=approval_mode,
        eager=True,
    )
    def _approve(event) -> None:
        proposal = pending["value"]
        if mode["value"] != "APPROVAL" or proposal is None:
            return
        mode["value"] = "APPLYING"
        event.app.invalidate()
        previous = current["value"]
        try:
            updated, actual_output = apply(previous, proposal)
        except Exception as error:
            refresh_note = (
                "The saved Ground could not be reloaded; close and resume "
                "before proposing another command."
            )
            try:
                if refresh_current(announce=False):
                    refresh_note = (
                        "The five workbench panes were refreshed from the latest "
                        "saved "
                        "Ground before further input."
                    )
                else:
                    refresh_note = (
                        "The five workbench panes already match the latest saved "
                        "Ground."
                    )
            except Exception as refresh_error:
                refresh_note += (
                    " Reload error: "
                    f"{safe_terminal_text(type(refresh_error).__name__)}: "
                    f"{safe_terminal_text(str(refresh_error))}"
                )
            conversation.append(
                "\n".join(
                    [
                        "APPLY NOT CONFIRMED",
                        f"  {safe_terminal_text(type(error).__name__)}: "
                        f"{safe_terminal_text(str(error))}",
                        "",
                        "The same approval will not be retried automatically.",
                        refresh_note,
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
        current["value"] = updated
        if lookup_fit is not None:
            # A USE change (and any other Ground revision) invalidates the
            # semantic input digest. Retain the receipt as history, but reload
            # its current/stale projection before repainting FIT.
            fit_receipt["value"] = lookup_fit(updated)
        placement_options = current_placement_options()
        placement_default = next(
            (
                frame.context_name
                for frame in updated.frames
                if frame.role == "PUBLICATION_TARGET"
            ),
            placement_options[0] if placement_options else "",
        )
        for placement_layer in placement_choice:
            if placement_choice[placement_layer] not in placement_options:
                placement_choice[placement_layer] = placement_default
                placement_overridden[placement_layer] = False
        mark_pane_updates(
            *changed_pane_layers(previous, updated),
            "CHAT",
        )
        applied_argvs.append(proposal.review.argv)
        applied_draft_index = pending_draft_index["value"]
        if (
            applied_draft_index is not None
            and 0 <= applied_draft_index < len(draft_queue["value"])
        ):
            remaining = list(draft_queue["value"])
            del remaining[applied_draft_index]
            draft_queue["value"] = tuple(remaining)
            draft_index["value"] = min(
                applied_draft_index,
                max(0, len(remaining) - 1),
            )
        pending_draft_index["value"] = None
        conversation.append(
            "\n".join(
                [
                    f"APPLIED · {safe_terminal_text(proposal.kind)}",
                    f"  {safe_terminal_text(actual_output)}",
                    "",
                    (
                        "The Goal, Contexts, Rules, Memories, and Chat "
                        "panes "
                        "now reflect the saved Ground."
                    ),
                ]
            )
        )
        conversation.append(_initial_question(updated))
        cycle_dialogue.clear()
        if draft_queue["value"]:
            # Any Ground mutation can change semantic duplicate/conflict
            # judgments. Keep the visible text, but never retain READY
            # authority across revisions.
            draft_queue_stale["value"] = True
        else:
            draft_queue_stale["value"] = False
            draft_source_submission["value"] = ""
            last_submission["value"] = ""
        applied_kind = proposal.kind
        focus_input(restore=False)
        if applied_kind == "SET_EXAMPLE_USE":
            status_message["value"] = (
                "Example USE updated · future Fit and Distill inputs changed"
            )
            sync_memories_pane(align_selection=True)
            application.layout.focus(cases_pane.text_area)
            application.invalidate()
        elif applied_kind.startswith("RESOLVE_"):
            status_message["value"] = (
                "RESOLVED · one Ground revision applied · prior Fit is stale"
            )
            sync_memories_pane(align_selection=True)
            application.layout.focus(cases_pane.text_area)
            application.invalidate()
        if draft_queue["value"]:
            status_message["value"] = (
                "Ground changed; remaining drafts are NOT SAVED and require "
                "R reclassification."
            )
            sync_rules_pane(align_draft=True)
            application.layout.focus(rules_pane.text_area)
            event.app.invalidate()

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
        if mode["value"] not in {"APPROVAL", "ERROR", "APPLY_ERROR"}:
            return
        previous_mode = mode["value"]
        inline_draft = pending_inline_edit["value"]
        fit_resolution_draft = pending_fit_resolution_edit["value"]
        conversation.append(
            "REFINEMENT\n  The pending action returned for revision."
        )
        if inline_draft is not None and previous_mode == "APPROVAL":
            target, selector, original, edited, comment = inline_draft
            focus_input(restore=False)
            open_inline_editor(
                target=target,
                selector=selector,
                original=original,
            )
            fit_resolution_edit["value"] = fit_resolution_draft
            direct_edit_area.text = edited
            direct_edit_area.buffer.cursor_position = len(edited)
            input_area.text = comment
            input_area.buffer.cursor_position = len(comment)
            event.app.invalidate()
            return
        if inline_draft is not None and previous_mode == "APPLY_ERROR":
            focus_input(restore=False)
            status_message["value"] = (
                "The direct edit was discarded after an unconfirmed apply; "
                "reopen the current pane before proposing it again."
            )
            event.app.invalidate()
            return
        focus_input(restore=True)

    @bindings.add("r", filter=error_mode, eager=True)
    def _retry(event) -> None:
        if mode["value"] != "ERROR":
            return
        mode["value"] = "INTERPRETING"
        error_message["value"] = ""
        interpret_current(append_user=False, text=last_submission["value"])

    def exit_view(
        event,
        *,
        status: Literal["CLOSED", "BACK_TO_PICKER"],
    ) -> None:
        deferred_exit_status["value"] = status
        if fit_turn.request_close():
            status_message["value"] = (
                "FIT RUNNING · close requested after the receipt boundary"
            )
            event.app.invalidate()
            return
        event.app.exit(
            result=NamedGroundShellResult(
                status=status,
                session=current["value"],
                applied_argvs=tuple(applied_argvs),
                submitted_turns=tuple(all_submitted_turns),
            )
        )

    @bindings.add("b", filter=read_pane_focus, eager=True)
    def _back_to_picker(event) -> None:
        # Returning to the picker is navigation only. A pending exact command
        # is discarded and can never be interpreted as approval.
        exit_view(event, status="BACK_TO_PICKER")

    @bind_case_insensitive_key(bindings, "q", filter=read_pane_focus, eager=True)
    def _quit_ground(event) -> None:
        exit_view(event, status="CLOSED")

    bind_session_help(
        bindings,
        filter=read_pane_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="ground-named",
    )

    @bindings.add("escape", eager=True)
    def _close_on_escape(event) -> None:
        dispatch_tui_back(
            event,
            collapse_fit_resolution,
            collapse_memory_detail,
            collapse_panel_comment,
            collapse_inline_editor,
            close=lambda current_event: exit_view(
                current_event,
                status="CLOSED",
            ),
        )

    @bindings.add("backspace", filter=memory_detail_focus, eager=True)
    def _back_from_memory_detail(event) -> None:
        collapse_memory_detail(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _close_anywhere(event) -> None:
        exit_view(event, status="CLOSED")

    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return NamedGroundShellResult(
            status="CLOSED",
            session=current["value"],
            applied_argvs=tuple(applied_argvs),
            submitted_turns=tuple(all_submitted_turns),
        )
