"""Terminal workbench adapter for one saved Context Meld."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output

from memcommit.interfaces.tui.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_tui_frame,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.meld import MeldSession
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.selection.tui import choice_marker


@dataclass(frozen=True)
class MeldShellAction:
    kind: str
    issue_uid: str | None = None
    choice_index: int | None = None
    comment: str = ""
    destination: str | None = None


def _line(value: str, limit: int = 100) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _route_line(session: MeldSession) -> str:
    """Render authority direction without making a baseline look like a peer."""
    if session.mode == "DIRECTIONAL":
        frame_by_role = {frame.role: frame for frame in session.frames}
        incoming = frame_by_role["INCOMING"]
        return (
            " INCOMING "
            f"{safe_terminal_text(incoming.context_name)} → "
            "BASELINE / TARGET "
            f"{safe_terminal_text(session.target.context_name)}\n"
        )
    return (
        f" {safe_terminal_text(session.frames[0].context_name)} + "
        f"{safe_terminal_text(session.frames[1].context_name)} → "
        f"{safe_terminal_text(session.target.context_name)}\n"
    )


def _proposal_marker(session: MeldSession, operation: str) -> str:
    if session.mode == "DIRECTIONAL" and operation == "EDIT":
        return "~"
    return "+"


def _proposal_label(
    session: MeldSession,
    *,
    operation: str,
    disposition: str,
) -> str:
    if session.mode == "DIRECTIONAL":
        return f"{operation} · {disposition}"
    return disposition


def _screen_text(
    session: MeldSession,
    *,
    selected_index: int,
    expanded: bool,
    choice_index: int | None,
):
    assessment = session.current_assessment
    fragments: list[tuple[str, str]] = [
        ("class:title", f" MEM MELD · {session.mode}\n"),
        ("", _route_line(session)),
        (
            "",
            (
                f" {session.state} · "
                f"{len(assessment.relations) if assessment else 0} relations · "
                f"{len(assessment.issues) if assessment else 0} issues · "
                f"{len(assessment.proposals) if assessment else 0} "
                f"{'changes' if session.mode == 'DIRECTIONAL' else 'results'}"
                "\n\n"
            ),
        ),
    ]
    if assessment is None:
        fragments.append(("", " Analysis pending.\n"))
        return fragments
    fragments.extend(
        [
            ("class:section", " WHAT MEM UNDERSTOOD\n"),
            ("", " " + safe_terminal_text(assessment.overview) + "\n\n"),
            ("class:section", " ISSUES\n"),
        ]
    )
    relation_by_uid = {relation.uid: relation for relation in assessment.relations}
    relation_number = {
        relation.uid: index
        for index, relation in enumerate(assessment.relations, start=1)
    }
    frame_by_uid = {frame.uid: frame for frame in session.frames}
    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in session.frames
        for memory in frame.memories
    }
    if not assessment.issues:
        fragments.append(("", "  (none)\n"))
    for index, issue in enumerate(assessment.issues):
        selected = index == selected_index
        if selected:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                "class:selected" if selected else "",
                (
                    f" {'▾' if selected and expanded else ('›' if selected else ' ')} "
                    f"{index + 1:>2}. [{issue.priority}] {_line(issue.title)}\n"
                ),
            )
        )
        fragments.append(("", f"       WHY · {_line(issue.why_it_matters)}\n"))
        if selected and expanded:
            fragments.append(
                (
                    "",
                    f"       QUESTION · {safe_terminal_text(issue.question)}\n",
                )
            )
            for option_index, option in enumerate(issue.options):
                chosen = option_index == choice_index
                fragments.append(
                    (
                        "class:choice" if chosen else "",
                        (
                            f"       {choice_marker(selected=chosen)} "
                            f"{option_index + 1}. "
                            f"{safe_terminal_text(option.label)}\n"
                        ),
                    )
                )
                fragments.append(("", f"          {safe_terminal_text(option.text)}\n"))
            fragments.append(("class:section", "       SOURCE MEMORIES\n"))
            seen_members: set[tuple[str, str]] = set()
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                for member in relation.members:
                    key = (member.frame_uid, member.memory_uid)
                    if key in seen_members:
                        continue
                    seen_members.add(key)
                    frame = frame_by_uid[member.frame_uid]
                    memory = memory_by_key[key]
                    role = f"[{frame.role}] " if session.mode == "DIRECTIONAL" else ""
                    fragments.append(
                        (
                            "",
                            (
                                "       - "
                                f"{role}"
                                f"{safe_terminal_text(frame.context_name)} "
                                f"#{memory.position + 1} "
                                f"[{memory.uid[:8]}] · "
                                f"{safe_terminal_text(memory.content)}\n"
                            ),
                        )
                    )
            fragments.append(("class:section", "       RELATED RELATIONS\n"))
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                fragments.append(
                    (
                        "",
                        (
                            f"       - R{relation_number[relation_uid]} "
                            f"{relation.kind} · "
                            f"{safe_terminal_text(relation.reason)}\n"
                        ),
                    )
                )
            affected = [
                proposal
                for proposal in assessment.proposals
                if set(proposal.relation_uids) & set(issue.relation_uids)
            ]
            fragments.append(("class:section", "       AFFECTED RESULTS\n"))
            if not affected:
                fragments.append(
                    (
                        "",
                        "       - unresolved; no target Memory proposed yet\n",
                    )
                )
            for proposal in affected:
                marker = _proposal_marker(session, proposal.operation)
                label = _proposal_label(
                    session,
                    operation=proposal.operation,
                    disposition=proposal.disposition,
                )
                fragments.append(
                    (
                        "",
                        (
                            f"       {marker} [{label}] "
                            f"{safe_terminal_text(proposal.content)}\n"
                        ),
                    )
                )
    proposal_heading = (
        " PROPOSED BASELINE CHANGES\n"
        if session.mode == "DIRECTIONAL"
        else " PROPOSED TARGET MEMORIES\n"
    )
    fragments.extend(
        [
            ("", "\n"),
            ("class:section", proposal_heading),
        ]
    )
    if not assessment.proposals:
        if session.mode == "DIRECTIONAL" and session.state == "READY_TO_APPLY":
            fragments.append(
                (
                    "",
                    (
                        "  (no baseline changes proposed; ready to accept "
                        "this no-change result)\n"
                    ),
                )
            )
        else:
            fragments.append(("", "  (none yet)\n"))
    for index, proposal in enumerate(assessment.proposals, start=1):
        marker = _proposal_marker(session, proposal.operation)
        label = _proposal_label(
            session,
            operation=proposal.operation,
            disposition=proposal.disposition,
        )
        fragments.append(
            (
                "",
                (f"  {marker} {index:>2}. [{label}] {_line(proposal.content, 120)}\n"),
            )
        )
    return fragments


def run_meld_shell(
    session: MeldSession,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> MeldShellAction | None:
    """Collect one semantic or terminal action; never call a provider."""
    if require_tty:
        require_interactive_terminal(
            "Interactive meld",
            snapshot_hint=(
                "Run the same 'mem meld' command outside a TTY "
                "to render its saved snapshot."
            ),
        )
    assessment = session.current_assessment
    if assessment is None:
        return None
    selected = {"index": 0}
    expanded = {"value": False}
    choice = {"index": None}
    global_comment = {"value": False}
    status = {"value": ""}
    bindings = KeyBindings()

    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="meld-message",
    )
    input_area = composer.text_area
    body_control = FormattedTextControl(
        lambda: _screen_text(
            session,
            selected_index=selected["index"],
            expanded=expanded["value"],
            choice_index=choice["index"],
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def move(delta: int) -> None:
        if not assessment.issues:
            return
        selected["index"] = max(
            0,
            min(selected["index"] + delta, len(assessment.issues) - 1),
        )
        expanded["value"] = False
        choice["index"] = None
        global_comment["value"] = False
        composer.frame.title = "MESSAGE"

    def submit(event) -> None:
        text = input_area.text.strip()
        if global_comment["value"]:
            if not text:
                status["value"] = "Enter a whole-set comment first."
                return
            event.app.exit(result=MeldShellAction(kind="COMMENT_ALL", comment=text))
            return
        if not assessment.issues:
            status["value"] = "There is no issue to comment on."
            return
        if not text and choice["index"] is None:
            status["value"] = "Choose a reading or enter a comment."
            return
        event.app.exit(
            result=MeldShellAction(
                kind="COMMENT_ISSUE",
                issue_uid=assessment.issues[selected["index"]].uid,
                choice_index=choice["index"],
                comment=text,
            )
        )

    @bindings.add("down", filter=~has_focus(input_area))
    def _down(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=~has_focus(input_area))
    def _up(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=~has_focus(input_area))
    def _expand(event) -> None:
        if assessment.issues:
            expanded["value"] = not expanded["value"]
        event.app.invalidate()

    for number in range(1, 6):

        def choose_reading(event, index=number - 1) -> None:
            if assessment.issues and index < len(
                assessment.issues[selected["index"]].options
            ):
                expanded["value"] = True
                choice["index"] = None if choice["index"] == index else index
            event.app.invalidate()

        bindings.add(str(number), filter=~has_focus(input_area))(choose_reading)

    @bindings.add("tab")
    def _focus_input(event) -> None:
        global_comment["value"] = False
        composer.frame.title = "MESSAGE"
        event.app.layout.focus(input_area)

    @bindings.add("g", filter=~has_focus(input_area))
    def _global_comment(event) -> None:
        global_comment["value"] = True
        composer.frame.title = "WHOLE-SET COMMENT"
        input_area.text = ""
        event.app.layout.focus(input_area)

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    @bindings.add("c-s", filter=has_focus(input_area), eager=True)
    def _submit_input(event) -> None:
        submit(event)

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    def _insert_newline(event) -> None:
        input_area.buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add("p", filter=~has_focus(input_area))
    def _preserve(event) -> None:
        event.app.exit(result=MeldShellAction(kind="PRESERVE_ALL"))

    @bindings.add("d", filter=~has_focus(input_area))
    def _defer(event) -> None:
        event.app.exit(result=MeldShellAction(kind="DEFER_ALL"))

    @bindings.add("a", filter=~has_focus(input_area))
    def _accept(event) -> None:
        if session.state != "READY_TO_APPLY":
            status["value"] = "Resolve REQUIRED issues before accepting."
            event.app.invalidate()
            return
        event.app.exit(result=MeldShellAction(kind="ACCEPT"))

    def _collapse_detail(event) -> bool:
        # Escape in the composer cancels Meld instead of submitting a draft.
        # Only the visible issue drill-down forms a back-navigation layer.
        if event.app.layout.has_focus(input_area) or not expanded["value"]:
            return False
        expanded["value"] = False
        return True

    def _close(event) -> None:
        event.app.exit(result=None)

    @bindings.add("escape", eager=True)
    def _back_or_close(event) -> None:
        dispatch_tui_back(event, _collapse_detail, close=_close)

    @bind_case_insensitive_key(
        bindings, "q", filter=~has_focus(input_area), eager=True
    )
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        _close(event)

    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status['value']}"
                if status["value"]
                else (
                    " ↑/↓ issue  Enter detail  Esc back/close  1-5 reading  "
                    "Tab/G comment  Enter send  Ctrl-J newline  "
                    "P preserve all  D defer  A accept  Q close "
                )
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(body),
        TuiRegion(composer.container),
        TuiRegion(footer),
    )
    application: Application[MeldShellAction | None] = Application(
        layout=Layout(root, focused_element=body_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
    )
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return None


# Keep the operation-specific renderer above as a compatibility snapshot while
# routing the live interaction through the shared resolution grammar.  The
# wrapper translates only the UID-bound action envelope; Meld still owns every
# semantic turn, provider call, saved assessment, and acceptance boundary.
_run_legacy_meld_shell = run_meld_shell


def _comparison_issue_resolution_badges(session: MeldSession) -> tuple[str, ...]:
    """Project durable Compare-issue outcomes without inventing a selection."""
    if session.comparison_seed is None or session.current_assessment is None:
        return ()
    assessment = session.current_assessment
    open_issue_uids = {issue.uid for issue in assessment.issues}
    proposals_by_relation = {
        relation_uid: tuple(
            proposal
            for proposal in assessment.proposals
            if relation_uid in proposal.relation_uids
        )
        for issue in session.comparison_seed.analysis.issues
        for relation_uid in issue.relation_uids
    }
    badges: list[str] = []
    for issue in session.comparison_seed.analysis.issues:
        if issue.uid in open_issue_uids:
            badges.append("")
            continue
        matched_label = ""
        for turn in reversed(session.user_turns):
            for option in issue.options:
                if option.text in turn.comment:
                    matched_label = f"CHOSEN · {option.label}"
                    break
            if matched_label:
                break
            marker = f"- {issue.title}: Other direction:"
            marked_line = next(
                (
                    line.partition(marker)[2].strip()
                    for line in turn.comment.splitlines()
                    if marker in line
                ),
                "",
            )
            direct_comment = marked_line or (
                turn.comment.strip()
                if issue.uid in turn.issue_uids
                and not turn.comment.startswith("Choose this reading:")
                else ""
            )
            if direct_comment:
                matched_label = f"OTHER DIRECTION · {_line(direct_comment, 72)}"
                break
        if matched_label:
            badges.append(matched_label)
            continue
        related = tuple(
            proposal
            for relation_uid in issue.relation_uids
            for proposal in proposals_by_relation.get(relation_uid, ())
        )
        dispositions = {proposal.disposition for proposal in related}
        if related and dispositions == {"PRESERVE"}:
            option_labels = " + ".join(option.label for option in issue.options)
            badges.append(f"KEPT BOTH · {option_labels}")
        elif "SYNTHESIZE" in dispositions:
            synthesized = tuple(
                proposal for proposal in related if proposal.disposition == "SYNTHESIZE"
            )
            detail = _line(synthesized[0].content, 72)
            if len(synthesized) > 1:
                detail += f" + {len(synthesized) - 1} more"
            badges.append(f"COMBINED · {detail}")
        elif "COALESCE" in dispositions:
            coalesced = next(
                proposal for proposal in related if proposal.disposition == "COALESCE"
            )
            badges.append(f"COALESCED · {_line(coalesced.content, 72)}")
        else:
            badges.append("RESOLVED")
    return tuple(badges)


def run_meld_shell(
    session: MeldSession,
    *,
    navigation: ResolutionNavigation | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    read_only: bool = False,
    review_only: bool = False,
    destination=None,
) -> MeldShellAction | None:
    """Collect one action through the shared dynamic resolution workbench."""
    from memcommit.commands.resolution_workbench_shell import (
        ResolutionGlobalStrategy,
        run_resolution_workbench_shell,
    )
    from memcommit.meld_resolution_adapter import (
        MeldResolutionWorkbenchAdapter,
    )
    from memcommit.impact_controller import ImpactController
    from memcommit.review_report_adapters import meld_review_report

    snapshot_hint = (
        "Run the same 'mem meld' command outside a TTY to render its saved snapshot."
    )
    if require_tty:
        require_interactive_terminal(
            "Interactive meld",
            snapshot_hint=snapshot_hint,
        )
    if session.current_assessment is None:
        return None
    adapter = MeldResolutionWorkbenchAdapter(session)
    review_view = None
    if review_only:
        review_view = meld_review_report(session).report().view
        if review_view is None:
            raise ValueError("Meld Review report has no interactive view.")
    compare_report: str | None = None
    if session.mode == "SYMMETRIC" and session.comparison_seed is not None:
        # The Compare analysis is already copied into the Meld seed. Re-render
        # that exact artifact instead of maintaining a second summary dialect.
        # Navigation hints are omitted because this target-bound Meld already
        # supplies the next interaction below the shared report.
        from memcommit.comparison_present import render_comparison

        compare_report = (
            render_comparison(
                session.comparison_seed.analysis,
                reused=True,
                durable=True,
            )
            .partition("\nThe complete source-linked relation ledger")[0]
            .rstrip()
        )
    report_badges = _comparison_issue_resolution_badges(session)
    report_conflicts_remaining = sum(not badge for badge in report_badges)
    global_strategies = (
        ResolutionGlobalStrategy(
            label="Preserve all HELPFUL compatible/scoped items separately",
            action_kind="SUBMIT_ALL",
            comment=(
                "Keep every remaining HELPFUL COMPATIBLE or SCOPED relation "
                "at the preservation-first default: copy each independently "
                "useful source Memory as its own target Memory. Apply this "
                "below the REQUIRED priority threshold without changing any "
                "still-required conflict decision."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Combine HELPFUL items only when one atomic result is lossless",
            action_kind="SUBMIT_ALL",
            comment=(
                "For remaining HELPFUL COMPATIBLE or SCOPED relations, combine "
                "members only when one independently revisable Memory retains "
                "every rate, condition, audience, modality, exception, and "
                "source-specific scope. Otherwise preserve the members "
                "separately. Apply the same rationale to later related issues, "
                "but do not resolve any REQUIRED conflict by this strategy."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Preserve every unresolved distinction",
            action_kind="SUBMIT_ALL",
            comment=(
                "Preserve every unresolved distinction without forcing a "
                "choice, while applying the explicitly reviewed responses."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Use the broadest applicable choice for unresolved conflicts",
            action_kind="SUBMIT_ALL",
            comment=(
                "For each remaining conflict, choose the option with the "
                "broadest justified applicability or coverage. Retain any "
                "qualification needed to avoid extending a claim beyond its "
                "source support, and preserve compatible distinct information."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Use the narrowest useful choice for unresolved conflicts",
            action_kind="SUBMIT_ALL",
            comment=(
                "For each remaining conflict, choose the narrowest, most "
                "specific, or most constrained option that remains useful. "
                "Preserve compatible distinct information outside the conflict."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Use the strongest-supported choice for unresolved conflicts",
            action_kind="SUBMIT_ALL",
            comment=(
                "Resolve each remaining conflict independently by choosing "
                "the option with the strongest support in the source Memories "
                "and current user guidance. Preserve compatible and "
                "non-conflicting distinct information from both sources."
            ),
        ),
    )
    active_view = adapter.view()
    impact_controller = (
        ImpactController.from_text(
            operation=active_view.operation,
            artifact_uid=active_view.artifact_uid,
            revision=active_view.revision,
            title="IMPACT · COMPARE",
            summary=(
                "This saved Compare analysis is the symmetric Meld impact. "
                "It remains read-only until the reviewed Meld is applied."
            ),
            detail=compare_report,
        )
        if compare_report is not None
        else ImpactController.from_resolution(
            adapter.view,
            title="IMPACT · DIRECTIONAL MELD",
            summary=(
                "These are the exact proposed baseline effects of this "
                "directional Meld, not an equal-authority Compare."
            ),
        )
    )
    action = run_resolution_workbench_shell(
        review_view if review_view is not None else adapter.view,
        navigation=navigation,
        app_input=app_input,
        app_output=app_output,
        require_tty=False,
        terminal_label="Interactive meld",
        snapshot_hint=snapshot_hint,
        split_viewer_items=True,
        global_strategies=global_strategies,
        split_report_text=compare_report,
        split_report_item_badges=report_badges,
        split_report_conflicts_remaining=report_conflicts_remaining,
        review_and_apply=not read_only and not review_only,
        read_only=read_only,
        impact_controller=None if review_only else impact_controller,
        destination=destination,
    )
    if action.kind == "CLOSE":
        return None
    if action.kind == "SUBMIT_ALL":
        return MeldShellAction(kind="COMMENT_ALL", comment=action.comment)
    if action.kind == "PRESERVE_ALL":
        return MeldShellAction(kind="PRESERVE_ALL")
    if action.kind == "DEFER":
        return MeldShellAction(kind="DEFER_ALL")
    if action.kind == "ACCEPT":
        return MeldShellAction(kind="ACCEPT")
    if action.kind == "CHANGE_DESTINATION":
        return MeldShellAction(
            kind="CHANGE_DESTINATION",
            destination=action.destination,
        )
    if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
        raise ValueError(f"Unsupported resolution action '{action.kind}' for Meld.")
    issue = adapter.view().item(action.item_uid)
    choice_index = (
        next(
            index
            for index, option in enumerate(issue.options)
            if option.uid == action.option_uid
        )
        if action.option_uid is not None
        else None
    )
    return MeldShellAction(
        kind="COMMENT_ISSUE",
        issue_uid=action.item_uid,
        choice_index=choice_index,
        comment=action.comment,
    )
