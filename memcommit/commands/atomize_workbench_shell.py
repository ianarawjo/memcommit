"""Interactive and snapshot views over one saved atomize workbench."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    DynamicContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import TextArea

from memcommit.atomize import AtomizeAnalysisSession
from memcommit.atomize_resolution_adapter import (
    AtomizeResolutionWorkbenchAdapter,
)
from memcommit.atomize_result_adapter import AtomizeResultWorkbenchAdapter
from memcommit.atomize_workbench import (
    ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT,
    AtomizeWorkbenchFinding,
    AtomizeWorkbenchSession,
    atomize_workbench_issue_projection,
    project_atomize_workbench_findings,
)
from memcommit.commands.review_shell import (
    RESPONSE_LABEL,
    ReviewCancelled,
)
from memcommit.commands.result_workbench_shell import (
    render_result_workbench_snapshot,
    result_workbench_fragments,
)
from memcommit.commands.tui_primitives import (
    safe_terminal_text,
)
from memcommit.resolution_workbench import (
    ResolutionNavigation,
    ResolutionWorkbenchAction,
)
from memcommit.result_workbench import (
    ResultCase,
    ResultCaseDetail,
    ResultWorkbenchView,
)

if TYPE_CHECKING:
    from memcommit.commands.resolution_workbench_shell import ResolutionDestination

_LIST_READING_PREVIEW_LIMIT = 2
_LIST_READING_LABEL_LIMIT = 160
_LIST_REASON_TEXT_LIMIT = 220
# prompt-toolkit follows only one cursor marker. This private NUL-delimited
# token cannot collide with rendered data because terminal sanitization
# replaces C0 controls before list fragments are assembled.
_LIST_CURSOR_TOKEN = "\x00atomize-list-cursor\x00"


@dataclass
class _AtomizeNavigation:
    """Ephemeral drill-down state; semantic answers remain in the session."""

    expanded_issue_uid: str | None = None
    reading_index: int = 0
    result_mode: bool = False
    result_case_index: int = 0
    result_detail: ResultCaseDetail | None = None

    def close(self) -> None:
        self.expanded_issue_uid = None
        self.reading_index = 0

    def close_result_detail(self) -> None:
        self.result_detail = None


def _assert_matches(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
) -> None:
    if not session.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_workbench_issue_projection(analysis),
    ):
        raise ValueError("The atomize workbench does not match its saved analysis.")


def _finding_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, AtomizeWorkbenchFinding]:
    return {
        finding.uid: finding for finding in project_atomize_workbench_findings(analysis)
    }


def _source_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, str]:
    return {item.memory_uid: item.content for item in analysis.items}


def _single_line(value: str, *, limit: int = 72) -> str:
    normalized = " ".join(safe_terminal_text(value).split())
    return (
        normalized
        if len(normalized) <= limit
        else normalized[: limit - 1].rstrip() + "…"
    )


def _issue_label(finding: AtomizeWorkbenchFinding) -> str:
    return {
        "AMBIGUITY": "AMBIGUITY",
        "CONFLICT": "CONFLICT",
        "ATOMIZE_SPLIT": "SUGGESTED SPLIT",
        "ATOMIZE_UNCERTAINTY": "ATOMIZE UNCERTAINTY",
    }[finding.kind]


def _reading_preview_lines(
    finding: AtomizeWorkbenchFinding,
) -> list[str]:
    """Expose saved readings as lossy list hints, never new semantics."""
    if not finding.readings:
        return []
    visible = finding.readings[:_LIST_READING_PREVIEW_LIMIT]
    lines = [
        (
            "      WHY · "
            f"{_compact_preview_text(finding.reason, _LIST_REASON_TEXT_LIMIT)}"
        )
    ]
    lines.extend(
        (
            f"      ↳ R{index} · "
            f"{_compact_preview_text(reading.label, _LIST_READING_LABEL_LIMIT)}"
        )
        for index, reading in enumerate(visible, start=1)
    )
    hidden_count = len(finding.readings) - len(visible)
    if hidden_count:
        lines.append(
            f"      ↳ +{hidden_count} more "
            f"{'reading' if hidden_count == 1 else 'readings'} "
            "(open detail)"
        )
    return lines


def _compact_preview_text(value: str, limit: int) -> str:
    """Keep both a preview's opening claim and trailing qualification."""
    normalized = " ".join(safe_terminal_text(value).split())
    if len(normalized) <= limit:
        return normalized
    marker = " … "
    available = limit - len(marker)
    head_limit = available * 11 // 20
    tail_limit = available - head_limit
    head = normalized[:head_limit].rstrip()
    tail = normalized[-tail_limit:].lstrip()
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    if " " in tail:
        tail = tail.split(" ", 1)[1]
    if not head or not tail:
        return _single_line(normalized, limit=limit)
    return f"{head}{marker}{tail}"


def _overview_text(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    *,
    result_view: ResultWorkbenchView | None = None,
) -> str:
    view = result_view or AtomizeResultWorkbenchAdapter(analysis).view()
    result = render_result_workbench_snapshot(view).rstrip()
    return "\n".join(
        [
            result,
            "",
            (
                f"Analysis [{analysis.uid[:8]}] · "
                f"INPUT {analysis.context_name} → OUTPUT "
                f"{session.output_context_name or analysis.context_name} · "
                f"ORDER: {session.sort_mode} · "
                f"{session.answered_count}/{len(findings)} answered"
            ),
        ]
    )


def _list_text(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    sources: dict[str, str],
    *,
    expanded_issue_uid: str | None = None,
    reading_index: int = 0,
    cursor_token: str = "",
    result_view: ResultWorkbenchView | None = None,
) -> str:
    current = session.current_issue()
    lines = [
        _overview_text(
            session,
            analysis,
            findings,
            result_view=result_view,
        ),
        "",
        "ACTIONABLE ISSUES",
    ]
    for index, descriptor in enumerate(
        session.ordered_issues(),
        start=1,
    ):
        finding = findings[descriptor.uid]
        response = session.responses.get(descriptor.uid)
        is_current = current is not None and current.uid == descriptor.uid
        is_expanded = is_current and expanded_issue_uid == descriptor.uid
        pointer = "▾" if is_expanded else ("›" if is_current else " ")
        marker = (
            cursor_token
            if is_current and (not is_expanded or not finding.readings)
            else ""
        )
        status = "✓" if response is not None and response.answered else "·"
        source = sources.get(finding.source_uids[0], "")
        lines.append(
            f"{marker}{pointer} {index:>2}. {status} "
            f"{_issue_label(finding)} · "
            f"{finding.classification}  “{_single_line(source, limit=48)}”"
        )
        if is_expanded:
            lines.extend(
                f"      {line}" if line else ""
                for line in _detail_text(
                    session,
                    analysis,
                    findings,
                    sources,
                    reading_cursor_index=(reading_index if finding.readings else None),
                    reading_cursor_token=cursor_token,
                ).splitlines()
            )
        else:
            lines.extend(_reading_preview_lines(finding))
    if not findings:
        lines.append("  (no actionable atomize, ambiguity, or conflict issues)")
    return "\n".join(lines)


def _list_fragments(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    sources: dict[str, str],
    *,
    expanded_issue_uid: str | None = None,
    reading_index: int = 0,
    result_view: ResultWorkbenchView | None = None,
):
    """Keep the selected issue visible when a long list scrolls."""
    fragments: list[tuple[str, str]] = []
    for line in _list_text(
        session,
        analysis,
        findings,
        sources,
        expanded_issue_uid=expanded_issue_uid,
        reading_index=reading_index,
        cursor_token=_LIST_CURSOR_TOKEN,
        result_view=result_view,
    ).splitlines():
        if _LIST_CURSOR_TOKEN in line:
            line = line.replace(_LIST_CURSOR_TOKEN, "", 1)
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(("", line + "\n"))
    return fragments


def _reason_heading(finding: AtomizeWorkbenchFinding) -> str:
    if finding.kind == "ATOMIZE_SPLIT":
        return "WHY THIS MEMORY SPLIT"
    if finding.kind == "CONFLICT":
        return (
            "WHY THE CONFLICT DEPENDS ON SCOPE"
            if finding.classification.endswith("MAY")
            else "WHY THESE MEMORIES CONFLICT"
        )
    return "WHY THIS IS UNCLEAR"


def _detail_text(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    sources: dict[str, str],
    *,
    reading_cursor_index: int | None = None,
    reading_cursor_token: str = "",
) -> str:
    descriptor = session.current_issue()
    if descriptor is None:
        return (
            "NO ACTIONABLE ISSUES\n\n"
            "The overview and complete atomize analysis remain saved."
        )
    finding = findings[descriptor.uid]
    ordered = session.ordered_issues()
    number = next(
        index
        for index, candidate in enumerate(ordered, start=1)
        if candidate.uid == descriptor.uid
    )
    lines = [
        f"{_issue_label(finding)} {number}/{len(findings)}",
        "",
    ]
    for source_number, source_uid in enumerate(
        finding.source_uids,
        start=1,
    ):
        source_label = (
            "SOURCE" if len(finding.source_uids) == 1 else f"SOURCE {source_number}"
        )
        lines.extend(
            [
                f"{source_label} [{safe_terminal_text(source_uid[:8])}]",
                safe_terminal_text(
                    sources.get(source_uid, "[source Memory unavailable]")
                ),
                "",
            ]
        )
    lines.extend(
        [
            "CLASSIFICATION",
            safe_terminal_text(finding.classification),
            "",
            _reason_heading(finding),
            safe_terminal_text(finding.reason),
        ]
    )
    if finding.question:
        lines.extend(
            [
                "",
                "CLARIFICATION PROMPT",
                safe_terminal_text(finding.question),
            ]
        )
    if finding.readings:
        selected = session.selected_choice_index(descriptor)
        lines.extend(["", "READING OPTIONS"])
        for index, reading in enumerate(finding.readings, start=1):
            if reading_cursor_index is None:
                pointer = "›" if selected == index - 1 else " "
                marker = ""
            else:
                pointer = "›" if reading_cursor_index == index - 1 else " "
                marker = "● " if selected == index - 1 else "○ "
            cursor_marker = (
                reading_cursor_token if reading_cursor_index == index - 1 else ""
            )
            lines.append(
                f"{cursor_marker}{pointer} {marker}{index}. "
                f"[{safe_terminal_text(reading.role)}] "
                f"{safe_terminal_text(reading.label)}"
            )
            if reading.label != reading.text:
                lines.append(f"   {safe_terminal_text(reading.text)}")
    if finding.children:
        lines.extend(["", "PROPOSED CHILDREN"])
        for index, child in enumerate(finding.children, start=1):
            lines.append(f"{index}. {safe_terminal_text(child.content)}")
            evidence = [*child.source_spans, *child.frame_spans]
            if evidence:
                lines.append(
                    "   EVIDENCE: "
                    + " | ".join(safe_terminal_text(span) for span in evidence)
                )
    return "\n".join(lines).rstrip()


def render_atomize_workbench_snapshot(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    *,
    show_all: bool = False,
) -> str:
    """Render the same durable state without ANSI or a live terminal."""
    _assert_matches(session, analysis)
    findings = _finding_map(analysis)
    sources = _source_map(analysis)
    result_view = AtomizeResultWorkbenchAdapter(analysis).view()
    current = session.current_issue()
    response_text = ""
    if current is not None:
        response = session.responses.get(current.uid)
        if response is not None:
            response_text = safe_terminal_text(response.text)
    lines = [
        _list_text(
            session,
            analysis,
            findings,
            sources,
            result_view=result_view,
        ),
        "",
        _detail_text(session, analysis, findings, sources),
        "",
        RESPONSE_LABEL,
        f"> {response_text}",
    ]
    if show_all:
        lines.extend(["", "ALL ATOMIZE RESULTS"])
        for item in analysis.items:
            lines.append(
                f"{item.position + 1:>3}. {item.classification} "
                f"[{item.memory_uid[:8]}] "
                f"{_single_line(item.content)}"
            )
    lines.extend(
        [
            "",
            (
                "SOURCE means canonical Context order; Memory creation "
                "timestamps are not recorded."
            ),
            "No Memory changes have been applied. No checkpoint was created.",
        ]
    )
    return "\n".join(lines)


def run_atomize_workbench_shell(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    *,
    save: Callable[[AtomizeWorkbenchSession], None],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> AtomizeWorkbenchSession:
    """Run the shared list/detail/response interaction over atomize issues."""
    _assert_matches(session, analysis)
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError(
            "Atomize workbench requires an interactive terminal. "
            "Use a snapshot-capable entry point in a remote session."
        )
    findings = _finding_map(analysis)
    sources = _source_map(analysis)
    result_adapter = AtomizeResultWorkbenchAdapter(analysis)
    result_view = result_adapter.view()
    bindings = KeyBindings()
    status_message = {"value": ""}
    navigation = _AtomizeNavigation()

    def selected_result_case() -> ResultCase | None:
        if not result_view.cases:
            return None
        navigation.result_case_index = max(
            0,
            min(
                navigation.result_case_index,
                len(result_view.cases) - 1,
            ),
        )
        return result_view.cases[navigation.result_case_index]

    def current_result_fragments():
        selected_case = selected_result_case()
        return result_workbench_fragments(
            result_view,
            selected_case_uid=(
                selected_case.uid if selected_case is not None else None
            ),
            detail=navigation.result_detail,
        )

    list_control = FormattedTextControl(
        text=lambda: _list_fragments(
            session,
            analysis,
            findings,
            sources,
            expanded_issue_uid=navigation.expanded_issue_uid,
            reading_index=navigation.reading_index,
            result_view=result_view,
        ),
        focusable=True,
        show_cursor=False,
    )
    result_control = FormattedTextControl(
        text=current_result_fragments,
        focusable=True,
        show_cursor=False,
    )
    detail_control = FormattedTextControl(
        text=lambda: _detail_text(
            session,
            analysis,
            findings,
            sources,
        ),
        focusable=False,
        show_cursor=False,
    )
    response_area = TextArea(
        text="",
        multiline=True,
        wrap_lines=True,
        scrollbar=True,
        height=Dimension(min=3, max=5),
        prompt="> ",
    )
    list_window = Window(
        list_control,
        width=Dimension(min=42, preferred=56),
        wrap_lines=True,
    )
    detail_panel = HSplit(
        [
            Window(detail_control, wrap_lines=True),
            Window(height=1, char="─"),
            Window(
                FormattedTextControl(RESPONSE_LABEL),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            response_area,
        ]
    )
    split_body = VSplit([list_window, Window(width=1, char="│"), detail_panel])
    stacked_body = HSplit(
        [
            Window(
                list_control,
                height=Dimension(min=12, preferred=18),
                wrap_lines=True,
            ),
            Window(height=1, char="─"),
            detail_panel,
        ]
    )
    issue_body = DynamicContainer(
        lambda: split_body if session.layout == "SPLIT" else stacked_body
    )
    result_body = Window(
        result_control,
        wrap_lines=True,
    )
    body = DynamicContainer(
        lambda: result_body if navigation.result_mode else issue_body
    )
    header = Window(
        FormattedTextControl(
            lambda: (
                f" mem impact atomize · "
                f"INPUT {safe_terminal_text(analysis.context_name)} → "
                f"OUTPUT {safe_terminal_text(session.output_context_name or analysis.context_name)} · "
                f"analysis={analysis.uid[:8]} "
                f"view={'RESULT' if navigation.result_mode else 'ISSUES'} "
                f"sort={session.sort_mode} layout={session.layout} "
                f"answered={session.answered_count}/{len(findings)}"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def footer_text() -> str:
        if status_message["value"]:
            return f" {status_message['value']}"
        if navigation.result_mode:
            if navigation.result_detail is None:
                return (
                    " ↑/↓ case  Enter expand  Esc/V issues  "
                    "Q save+quit · result view is read-only "
                )
            return (
                " Esc/Backspace collapse  V issues  "
                "Q save+quit · result view is read-only "
            )
        expanded_uid = navigation.expanded_issue_uid
        if expanded_uid is None:
            navigation_help = " ↑/↓ issue  Enter open  Tab input  V result  "
        elif findings[expanded_uid].readings:
            navigation_help = (
                " ↑/↓ reading  Enter choose/clear  Esc/Backspace up  Tab input  "
            )
        else:
            navigation_help = " Enter close  Esc/Backspace up  Tab input  "
        return navigation_help + "F2/Ctrl-S save+next  S sort  L layout  Q quit "

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def load_response() -> None:
        issue = session.current_issue()
        response_area.text = (
            session.response_for(issue.uid).text if issue is not None else ""
        )
        response_area.buffer.cursor_position = len(response_area.text)

    def capture_response() -> bool:
        issue = session.current_issue()
        if issue is None:
            return True
        if len(response_area.text) > ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT:
            status_message["value"] = (
                "Response is too long to save "
                f"({len(response_area.text):,}/"
                f"{ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT:,} characters)."
            )
            return False
        session.response_for(issue.uid).text = response_area.text
        status_message["value"] = ""
        return True

    def persist() -> bool:
        if not capture_response():
            return False
        save(session)
        return True

    def move(delta: int) -> None:
        if not capture_response():
            return
        navigation.close()
        session.move(delta)
        load_response()
        save(session)

    def current_expanded_issue():
        issue = session.current_issue()
        if issue is None or navigation.expanded_issue_uid != issue.uid:
            return None
        return issue

    def move_reading(delta: int) -> None:
        issue = current_expanded_issue()
        if issue is None or not issue.choice_uids:
            return
        navigation.reading_index = max(
            0,
            min(
                navigation.reading_index + delta,
                len(issue.choice_uids) - 1,
            ),
        )

    def open_or_choose() -> None:
        issue = session.current_issue()
        if issue is None:
            return
        if navigation.expanded_issue_uid != issue.uid:
            navigation.expanded_issue_uid = issue.uid
            selected = session.selected_choice_index(issue)
            navigation.reading_index = 0 if selected is None else selected
            return
        if issue.choice_uids:
            selected = session.selected_choice_index(issue)
            session.select_choice(
                None
                if selected == navigation.reading_index
                else navigation.reading_index
            )
            save(session)
        navigation.close()

    def show_result(event) -> None:
        if not capture_response():
            event.app.invalidate()
            return
        navigation.close()
        navigation.result_mode = True
        navigation.close_result_detail()
        event.app.layout.focus(result_control)
        event.app.invalidate()

    def show_issues(event) -> None:
        navigation.result_mode = False
        navigation.close_result_detail()
        event.app.layout.focus(list_control)
        event.app.invalidate()

    def move_result_case(delta: int) -> None:
        if not result_view.cases:
            return
        navigation.result_case_index = max(
            0,
            min(
                navigation.result_case_index + delta,
                len(result_view.cases) - 1,
            ),
        )
        navigation.close_result_detail()

    @bindings.add("v", filter=has_focus(list_control))
    def _show_result(event) -> None:
        show_result(event)

    @bindings.add("v", filter=has_focus(result_control))
    def _show_issues(event) -> None:
        show_issues(event)

    @bindings.add("down", filter=has_focus(result_control))
    def _next_result_case(event) -> None:
        move_result_case(1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(result_control))
    def _previous_result_case(event) -> None:
        move_result_case(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(result_control))
    def _toggle_result_detail(event) -> None:
        selected_case = selected_result_case()
        if selected_case is None:
            status_message["value"] = "No inspection case is available."
            event.app.invalidate()
            return
        if (
            navigation.result_detail is not None
            and navigation.result_detail.case_uid == selected_case.uid
        ):
            navigation.close_result_detail()
        else:
            navigation.result_detail = result_adapter.case_detail(selected_case.uid)
        status_message["value"] = ""
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(result_control))
    @bindings.add("backspace", filter=has_focus(result_control))
    def _collapse_result_or_return(event) -> None:
        if navigation.result_detail is not None:
            navigation.close_result_detail()
            event.app.invalidate()
        else:
            show_issues(event)

    # Keep horizontal issue movement as a compatibility alias for remote
    # controllers; vertical arrows follow whichever list level is visible.
    @bindings.add("right", filter=has_focus(list_control))
    def _next_issue(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(list_control))
    def _previous_issue(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(list_control))
    def _next_issue_vertical(event) -> None:
        if current_expanded_issue() is None:
            move(1)
        else:
            move_reading(1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(list_control))
    def _previous_issue_vertical(event) -> None:
        if current_expanded_issue() is None:
            move(-1)
        else:
            move_reading(-1)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(list_control))
    def _open_or_choose(event) -> None:
        open_or_choose()
        event.app.invalidate()

    @bindings.add("tab", filter=has_focus(list_control))
    def _focus_response(event) -> None:
        event.app.layout.focus(response_area)

    @bindings.add("escape", filter=has_focus(list_control))
    @bindings.add("backspace", filter=has_focus(list_control))
    def _close_expanded(event) -> None:
        navigation.close()
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(response_area))
    @bindings.add("tab", filter=has_focus(response_area))
    def _focus_review(event) -> None:
        if persist():
            event.app.layout.focus(list_control)
        event.app.invalidate()

    @bindings.add("f2", eager=True)
    @bindings.add("c-s", eager=True)
    def _save_and_next(event) -> None:
        if persist():
            event.app.layout.focus(list_control)
            navigation.close()
            session.move(1)
            load_response()
            save(session)
        event.app.invalidate()

    @bindings.add("s", filter=has_focus(list_control))
    def _toggle_sort(event) -> None:
        if capture_response():
            navigation.close()
            session.toggle_sort()
            load_response()
            save(session)
        event.app.invalidate()

    @bindings.add("l", filter=has_focus(list_control))
    def _toggle_layout(event) -> None:
        session.toggle_layout()
        save(session)
        event.app.invalidate()

    @bindings.add("q", filter=has_focus(list_control), eager=True)
    @bindings.add("q", filter=has_focus(result_control), eager=True)
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        if persist():
            event.app.exit(result=session)
        else:
            event.app.invalidate()

    app: Application[AtomizeWorkbenchSession] = Application(
        layout=Layout(
            HSplit([header, body, footer]),
            focused_element=list_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
    )
    load_response()
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt) as error:
        if not persist():
            raise ValueError(status_message["value"]) from error
        raise ReviewCancelled from error


# Preserve the operation-specific snapshot helpers above, but use the common
# list/detail/comment grammar for live review.  Atomize continues to own its
# immutable issue digest, durable cursor and responses, explicit reanalysis,
# and later Context application.
_run_legacy_atomize_workbench_shell = run_atomize_workbench_shell


def run_atomize_workbench_shell(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    *,
    save: Callable[[AtomizeWorkbenchSession], None],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    workflow_actions: bool = False,
    application_complete: bool = False,
    destination: ResolutionDestination | None = None,
) -> AtomizeWorkbenchSession | ResolutionWorkbenchAction:
    """Review Atomize findings through the shared resolution workbench."""
    from memcommit.commands.resolution_workbench_shell import (
        ResolutionGlobalStrategy,
        run_resolution_workbench_shell,
    )

    _assert_matches(session, analysis)
    navigation = ResolutionNavigation(
        selected_item_uid=session.cursor_uid,
    )

    def view():
        projected = AtomizeResolutionWorkbenchAdapter(analysis, session).view()
        if workflow_actions:
            return projected
        # Review-only and terminal sessions may still edit saved comments, but
        # they must not leak the adapter's Apply or whole-set materialization
        # capabilities through keyboard shortcuts in the common shell.
        return replace(
            projected,
            status="APPLIED" if application_complete else projected.status,
            capabilities=frozenset({"SUBMIT_ITEM"}),
            accept_enabled=False,
            accept_mode="CHANGES",
            unresolved_at_apply_count=0,
        )

    def load_draft(issue_uid: str) -> tuple[str | None, str]:
        response = session.responses.get(issue_uid)
        if response is None:
            return None, ""
        return response.selected_choice_uid, response.text

    saved_in_round = {"value": False}

    def save_draft(
        issue_uid: str,
        option_uid: str | None,
        comment: str,
    ) -> None:
        if len(comment) > ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT:
            raise ValueError(
                "Response is too long to save "
                f"({len(comment):,}/"
                f"{ATOMIZE_WORKBENCH_RESPONSE_CHAR_LIMIT:,} characters)."
            )
        response = session.response_for(issue_uid)
        response.selected_choice_uid = option_uid
        response.text = comment
        session.cursor_uid = issue_uid
        save(session)
        saved_in_round["value"] = True

    def toggle_sort() -> None:
        session.toggle_sort()
        save(session)
        saved_in_round["value"] = True

    first_round = True
    while True:
        saved_in_round["value"] = False
        action = run_resolution_workbench_shell(
            view,
            navigation=navigation,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty and first_round,
            terminal_label="Interactive atomize workbench",
            snapshot_hint=(
                "Run 'mem impact atomize' outside a TTY to render the saved snapshot."
            ),
            draft_loader=load_draft,
            draft_saver=save_draft,
            save_draft_on_close=True,
            toggle_sort=toggle_sort,
            split_viewer_items=True,
            review_and_apply=workflow_actions,
            destination=destination,
            global_strategies=(
                ResolutionGlobalStrategy(
                    label="Keep unanswered optional findings as analyzed",
                    action_kind="SUBMIT_ALL",
                    comment=(
                        "Keep unanswered optional findings as analyzed while "
                        "incorporating every saved Atomize response into the "
                        "revised proposal."
                    ),
                ),
            )
            if workflow_actions
            else (),
        )
        first_round = False
        session.cursor_uid = navigation.selected_item_uid
        if action.kind == "CLOSE":
            if not saved_in_round["value"]:
                save(session)
            return session
        if workflow_actions and action.kind in {
            "SUBMIT_ALL",
            "INCORPORATE_AND_APPLY",
            "ACCEPT",
            "CHANGE_DESTINATION",
        }:
            return action
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise ValueError(
                f"Unsupported resolution action '{action.kind}' for Atomize."
            )
        save_draft(
            action.item_uid,
            action.option_uid,
            action.comment,
        )
        session.move(1)
        navigation.selected_item_uid = session.cursor_uid
        navigation.close_detail()
