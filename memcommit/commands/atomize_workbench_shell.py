"""Interactive and snapshot views over one saved atomize workbench."""
from __future__ import annotations

import sys
from collections.abc import Callable

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
    safe_terminal_text,
)

_LIST_READING_PREVIEW_LIMIT = 2
_LIST_READING_LABEL_LIMIT = 160
_LIST_REASON_TEXT_LIMIT = 220


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
        raise ValueError(
            "The atomize workbench does not match its saved analysis."
        )


def _finding_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, AtomizeWorkbenchFinding]:
    return {
        finding.uid: finding
        for finding in project_atomize_workbench_findings(analysis)
    }


def _source_map(
    analysis: AtomizeAnalysisSession,
) -> dict[str, str]:
    return {
        item.memory_uid: item.content for item in analysis.items
    }


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
        "ATOMIZE_SPLIT": "ATOMIZE SPLIT",
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
) -> str:
    split_count = sum(
        item.classification == "COMPOSITE" for item in analysis.items
    )
    child_count = sum(
        len(item.children)
        for item in analysis.items
        if item.classification == "COMPOSITE"
    )
    overview = analysis.overview
    if overview is None:
        raise ValueError("The saved atomize analysis has no overview.")
    lines = [
        (
            f"MEM IMPACT · ATOMIZE · "
            f"{safe_terminal_text(analysis.context_name)}"
        ),
        (
            f"{analysis.memory_count} source Memories → "
            f"{analysis.projected_memory_count} projected"
        ),
        (
            f"{split_count} proposed "
            f"{'split' if split_count == 1 else 'splits'} → "
            f"{child_count} "
            f"{'child' if child_count == 1 else 'children'}"
        ),
        (
            f"Analysis [{analysis.uid[:8]}] · "
            f"ORDER: {session.sort_mode} · "
            f"{session.answered_count}/{len(findings)} answered"
        ),
        "",
        "WHAT MEM UNDERSTOOD",
        safe_terminal_text(
            overview.understood.text or "No content summary was returned."
        ),
        "",
        "WHAT CHANGED / REMAINS UNRESOLVED",
        safe_terminal_text(
            overview.changed.text or "No structural change was proposed."
        ),
        safe_terminal_text(
            overview.unresolved.text
            or "No unresolved local expression was reported."
        ),
    ]
    return "\n".join(lines)


def _list_text(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    sources: dict[str, str],
) -> str:
    current = session.current_issue()
    lines = [
        _overview_text(session, analysis, findings),
        "",
        "ISSUES",
    ]
    for index, descriptor in enumerate(
        session.ordered_issues(),
        start=1,
    ):
        finding = findings[descriptor.uid]
        response = session.responses.get(descriptor.uid)
        pointer = (
            "›"
            if current is not None and current.uid == descriptor.uid
            else " "
        )
        status = "✓" if response is not None and response.answered else "·"
        source = sources.get(finding.source_uids[0], "")
        lines.append(
            f"{pointer} {index:>2}. {status} {_issue_label(finding)} · "
            f"{finding.classification}  “{_single_line(source, limit=48)}”"
        )
        lines.extend(_reading_preview_lines(finding))
    if not findings:
        lines.append("  (no actionable atomize, ambiguity, or conflict issues)")
    return "\n".join(lines)


def _list_fragments(
    session: AtomizeWorkbenchSession,
    analysis: AtomizeAnalysisSession,
    findings: dict[str, AtomizeWorkbenchFinding],
    sources: dict[str, str],
):
    """Keep the selected issue visible when a long list scrolls."""
    fragments: list[tuple[str, str]] = []
    for line in _list_text(session, analysis, findings, sources).splitlines():
        if line.startswith("›"):
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(("", line + "\n"))
    return fragments


def _reason_heading(finding: AtomizeWorkbenchFinding) -> str:
    if finding.kind == "ATOMIZE_SPLIT":
        return "WHY THIS SPLIT"
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
            "SOURCE"
            if len(finding.source_uids) == 1
            else f"SOURCE {source_number}"
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
            pointer = "›" if selected == index - 1 else " "
            lines.append(
                f"{pointer} {index}. [{safe_terminal_text(reading.role)}] "
                f"{safe_terminal_text(reading.label)}"
            )
            if reading.label != reading.text:
                lines.append(f"   {safe_terminal_text(reading.text)}")
    if finding.children:
        lines.extend(["", "PROPOSED CHILDREN"])
        for index, child in enumerate(finding.children, start=1):
            lines.append(
                f"{index}. {safe_terminal_text(child.content)}"
            )
            evidence = [*child.source_spans, *child.frame_spans]
            if evidence:
                lines.append(
                    "   EVIDENCE: "
                    + " | ".join(
                        safe_terminal_text(span) for span in evidence
                    )
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
    current = session.current_issue()
    response_text = ""
    if current is not None:
        response = session.responses.get(current.uid)
        if response is not None:
            response_text = safe_terminal_text(response.text)
    lines = [
        _list_text(session, analysis, findings, sources),
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
    if require_tty and (
        not sys.stdin.isatty() or not sys.stdout.isatty()
    ):
        raise ValueError(
            "Atomize workbench requires an interactive terminal. "
            "Use a snapshot-capable entry point in a remote session."
        )
    findings = _finding_map(analysis)
    sources = _source_map(analysis)
    bindings = KeyBindings()
    status_message = {"value": ""}

    list_control = FormattedTextControl(
        text=lambda: _list_fragments(
            session,
            analysis,
            findings,
            sources,
        ),
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
    split_body = VSplit(
        [list_window, Window(width=1, char="│"), detail_panel]
    )
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
    body = DynamicContainer(
        lambda: split_body if session.layout == "SPLIT" else stacked_body
    )
    header = Window(
        FormattedTextControl(
            lambda: (
                f" mem impact atomize · "
                f"{safe_terminal_text(analysis.context_name)} · "
                f"analysis={analysis.uid[:8]} "
                f"sort={session.sort_mode} layout={session.layout} "
                f"answered={session.answered_count}/{len(findings)}"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status_message['value']}"
                if status_message["value"]
                else (
                    " ←/→ issue  ↑/↓ reading  1-5 choose  Enter input  "
                    "Esc review  F2/Ctrl-S save+next  S sort  L layout  Q quit "
                )
            )
        ),
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
        session.move(delta)
        load_response()
        save(session)

    def move_choice(delta: int) -> None:
        issue = session.current_issue()
        if issue is None or not issue.choice_uids:
            return
        selected = session.selected_choice_index(issue)
        next_index = 0 if selected is None else selected + delta
        next_index = max(0, min(next_index, len(issue.choice_uids) - 1))
        session.select_choice(next_index)
        save(session)

    @bindings.add("right", filter=has_focus(list_control))
    def _next_issue(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(list_control))
    def _previous_issue(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(list_control))
    def _next_reading(event) -> None:
        move_choice(1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(list_control))
    def _previous_reading(event) -> None:
        move_choice(-1)
        event.app.invalidate()

    for number in range(1, 6):

        @bindings.add(str(number), filter=has_focus(list_control))
        def _choose_number(event, number=number) -> None:
            issue = session.current_issue()
            if issue is not None and number <= len(issue.choice_uids):
                session.select_choice(number - 1)
                save(session)
                event.app.invalidate()

    @bindings.add("0", filter=has_focus(list_control))
    def _clear_choice(event) -> None:
        session.select_choice(None)
        save(session)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(list_control))
    @bindings.add("tab", filter=has_focus(list_control))
    def _focus_response(event) -> None:
        event.app.layout.focus(response_area)

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
            session.move(1)
            load_response()
            save(session)
        event.app.invalidate()

    @bindings.add("s", filter=has_focus(list_control))
    def _toggle_sort(event) -> None:
        if capture_response():
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
