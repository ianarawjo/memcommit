"""Shared read-only presentation for validated semantic-operation results.

The common shell owns only information hierarchy, terminal safety, and case
navigation.  The operation adapter remains responsible for every semantic
judgment, reference, persisted artifact, provider call, and mutation.
"""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.commands.tui_primitives import (
    TuiRegion,
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    bind_case_insensitive_key,
    bind_focused_frame_style,
    build_tui_frame,
    dispatch_tui_back,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.commands.tui_text_layout import single_line_terminal_text
from memcommit.commands.semantic_detail_renderer import (
    semantic_detail_block_fragments,
    semantic_detail_header_fragments,
    semantic_trace_fragments,
)
from memcommit.commands.semantic_viewer import (
    SemanticViewerController,
    semantic_viewer_block_fragments,
)
from memcommit.result_workbench import (
    ResultCase,
    ResultCaseDetail,
    ResultSection,
    ResultWorkbenchAdapter,
    ResultWorkbenchError,
    ResultWorkbenchView,
)
from memcommit.session_workbench_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchSection,
)


def _compact(value: str) -> str:
    """Keep one logical case row; the live Window owns visual wrapping."""

    return single_line_terminal_text(safe_terminal_text(value))


def _section_text(section: ResultSection) -> str:
    text = safe_terminal_text(section.text)
    if section.state == "PRESENT":
        return text
    marker = (
        "(none reported under this operation's bounded contract)"
        if section.state == "NONE_REPORTED"
        else "(not recorded by this result artifact)"
    )
    return f"{marker}\n{text}" if text else marker


def _case_row(
    case: ResultCase,
    *,
    index: int,
    active: bool,
    expanded: bool,
) -> list[tuple[str, str]]:
    marker = "▾" if expanded else ("›" if active else " ")
    return semantic_viewer_block_fragments(
        [
            (
                "class:case-title",
                (f" {marker} {index:>2}. [{case.role}] {_compact(case.title)}\n"),
            ),
            ("", f"       {_compact(case.summary)}\n"),
        ],
        active=active,
    )


def _case_detail_fragments(
    view: ResultWorkbenchView,
    detail: ResultCaseDetail,
    *,
    focused_uid: str | None = None,
) -> list[tuple[str, str]]:
    detail = view.validate_detail(detail)
    case = view.case(detail.case_uid)
    case_number = next(
        index
        for index, candidate in enumerate(view.cases, start=1)
        if candidate.uid == case.uid
    )
    fragments = semantic_viewer_block_fragments(
        semantic_detail_header_fragments(
            label=f"CASE DETAIL · {case_number}/{len(view.cases)} · {case.role}",
            title=case.title,
            why_heading="WHY SELECTED",
            why=case.why_selected,
        ),
        active=focused_uid == f"RESULT:CASE:{case.uid}:DETAIL",
        anchor="end",
    )
    # Detail blocks are operation-authored and deliberately retain their
    # supplied order.  The common layer must not reinterpret their semantics.
    for block_index, block in enumerate(detail.blocks):
        fragments.extend(
            semantic_viewer_block_fragments(
                semantic_detail_block_fragments(
                    heading=block.heading,
                    text=block.text,
                    refs=block.refs,
                ),
                active=(focused_uid == f"RESULT:CASE:{case.uid}:BLOCK:{block_index}"),
                anchor="end",
            )
        )
    fragments.extend(
        semantic_viewer_block_fragments(
            semantic_trace_fragments(
                evidence_refs=detail.evidence_refs,
                judgment_refs=detail.judgment_refs,
                outcome_refs=detail.outcome_refs,
                unresolved_refs=detail.unresolved_refs,
            ),
            active=focused_uid == f"RESULT:CASE:{case.uid}:TRACE",
            anchor="end",
        )
    )
    return fragments


def _screen_fragments(
    view: ResultWorkbenchView,
    *,
    selected_index: int,
    detail: ResultCaseDetail | None,
    focused_uid: str | None = None,
) -> list[tuple[str, str]]:
    metrics = "".join(
        (f" · {safe_terminal_text(metric.label)}={metric.value:,}")
        for metric in view.metrics
    )
    fragments: list[tuple[str, str]] = [
        (
            "class:title",
            (
                f" RESULT · {safe_terminal_text(view.operation)} · "
                f"{safe_terminal_text(view.title)}\n"
            ),
        ),
        (
            "class:metadata",
            f" STATUS · {safe_terminal_text(view.status)}{metrics}\n",
        ),
    ]
    for uid, heading, section in (
        ("RESULT:UNDERSTOOD", "WHAT MEM UNDERSTOOD", view.understood),
        ("RESULT:HAPPENED", "WHAT HAPPENED", view.happened),
        ("RESULT:UNRESOLVED", "WHAT REMAINS UNRESOLVED", view.unresolved),
    ):
        fragments.extend(
            semantic_viewer_block_fragments(
                [
                    ("class:section", f"\n {heading}\n"),
                    ("class:viewer-body", f" {_section_text(section)}\n"),
                ],
                active=focused_uid == uid,
                focus_indices=(0, 1),
            )
        )
    fragments.append(("class:section", "\n REPRESENTATIVE / BOUNDARY CASES\n"))
    if not view.cases:
        fragments.append(("", "  (no inspection cases recorded)\n"))
        return fragments
    expanded_uid = detail.case_uid if detail is not None else None
    for index, case in enumerate(view.cases):
        fragments.extend(
            _case_row(
                case,
                index=index + 1,
                active=(
                    focused_uid == f"RESULT:CASE:{case.uid}"
                    if focused_uid is not None
                    else index == selected_index
                ),
                expanded=case.uid == expanded_uid,
            )
        )
    if detail is not None:
        fragments.extend(_case_detail_fragments(view, detail, focused_uid=focused_uid))
    return fragments


def _fragments_text(fragments: list[tuple[str, str]]) -> str:
    return "".join(text for style, text in fragments if style != "[SetCursorPosition]")


def render_result_workbench_snapshot(
    view: ResultWorkbenchView,
    *,
    selected_case_uid: str | None = None,
    detail: ResultCaseDetail | None = None,
) -> str:
    """Render one deterministic result frame without ANSI control sequences.

    ``detail`` is accepted only when it belongs to the exact immutable
    artifact represented by ``view``.  This makes the pure snapshot renderer
    useful both for non-TTY CLI output and for focused integration tests.
    """
    snapshot = _fragments_text(
        result_workbench_fragments(
            view,
            selected_case_uid=selected_case_uid,
            detail=detail,
        )
    )
    return snapshot.rstrip() + "\n"


def result_workbench_fragments(
    view: ResultWorkbenchView,
    *,
    selected_case_uid: str | None = None,
    detail: ResultCaseDetail | None = None,
) -> list[tuple[str, str]]:
    """Return the validated common frame for embedding in another workbench.

    The cursor marker remains attached to the selected compact case, allowing
    an operation-owned shell to reuse the exact information hierarchy without
    copying its presentation or semantic validation rules.
    """
    if not isinstance(view, ResultWorkbenchView):
        raise ResultWorkbenchError("Invalid result workbench view.")
    if detail is not None:
        detail = view.validate_detail(detail)
        if selected_case_uid is not None and selected_case_uid != detail.case_uid:
            raise ResultWorkbenchError(
                "Expanded result detail does not match the selected case."
            )
        selected_case_uid = detail.case_uid
    if selected_case_uid is None:
        selected_index = 0
    else:
        selected_case = view.case(selected_case_uid)
        selected_index = view.cases.index(selected_case)
    return _screen_fragments(
        view,
        selected_index=selected_index,
        detail=detail,
    )


def _result_viewer_sections(
    view: ResultWorkbenchView,
    detail: ResultCaseDetail | None,
) -> tuple[WorkbenchSection, ...]:
    """Project result units into the service-wide focus grammar."""

    sections: list[WorkbenchSection] = [
        WorkbenchSection("RESULT:UNDERSTOOD", "OVERVIEW"),
        WorkbenchSection("RESULT:HAPPENED", "OVERVIEW"),
        WorkbenchSection("RESULT:UNRESOLVED", "OVERVIEW"),
    ]
    sections.extend(
        WorkbenchSection(f"RESULT:CASE:{case.uid}", "CASE", index)
        for index, case in enumerate(view.cases)
    )
    if detail is not None:
        sections.append(
            WorkbenchSection(
                f"RESULT:CASE:{detail.case_uid}:DETAIL",
                "CASE_DETAIL",
            )
        )
        sections.extend(
            WorkbenchSection(
                f"RESULT:CASE:{detail.case_uid}:BLOCK:{index}",
                "DETAIL_BLOCK",
            )
            for index, _block in enumerate(detail.blocks)
        )
        sections.append(
            WorkbenchSection(
                f"RESULT:CASE:{detail.case_uid}:TRACE",
                "TRACE",
            )
        )
    return tuple(sections)


def run_result_workbench_shell(
    adapter: ResultWorkbenchAdapter,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ResultWorkbenchView:
    """Navigate one frozen result projection without changing operation state."""
    if require_tty:
        require_interactive_terminal(
            "Result workbench",
            snapshot_hint=(
                "Use the operation's snapshot option for non-interactive inspection."
            ),
        )
    # Freeze one validated operation projection for the entire UI session.
    # Detail lookups must match this digest; an adapter cannot quietly switch
    # artifacts while the person is inspecting a case.
    view = adapter.view()
    if not isinstance(view, ResultWorkbenchView):
        raise ResultWorkbenchError("Invalid result workbench view.")

    selected = {"index": 0}
    expanded = {"detail": None}
    status = {"value": ""}
    bindings = KeyBindings()
    navigation = SessionWorkbenchNavigation(pane="viewer")
    viewer_controller = SemanticViewerController(navigation)

    def viewer_sections() -> tuple[WorkbenchSection, ...]:
        return _result_viewer_sections(view, expanded["detail"])

    def focused_uid() -> str | None:
        section = viewer_controller.current(viewer_sections())
        return None if section is None else section.uid

    body_control = FormattedTextControl(
        lambda: _screen_fragments(
            view,
            selected_index=selected["index"],
            detail=expanded["detail"],
            focused_uid=focused_uid(),
        ),
        focusable=True,
        show_cursor=False,
    )
    body = Window(
        body_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def collapse() -> None:
        current = expanded["detail"]
        expanded["detail"] = None
        if current is not None:
            navigation.section_uid = f"RESULT:CASE:{current.case_uid}"
        status["value"] = ""

    def move(delta: int) -> None:
        section = viewer_controller.move(viewer_sections(), delta)
        if section is not None and section.kind == "CASE":
            selected["index"] = section.row_index or 0
        status["value"] = ""

    @bindings.add("down", filter=has_focus(body_control))
    def _down(event) -> None:
        move(1)
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(body_control))
    def _up(event) -> None:
        move(-1)
        event.app.invalidate()

    @bindings.add("pagedown", filter=has_focus(body_control))
    def _page_down(event) -> None:
        move(8)
        event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(body_control))
    def _page_up(event) -> None:
        move(-8)
        event.app.invalidate()

    @bindings.add("home", filter=has_focus(body_control))
    def _home(event) -> None:
        viewer_controller.home(viewer_sections())
        event.app.invalidate()

    @bindings.add("end", filter=has_focus(body_control))
    def _end(event) -> None:
        viewer_controller.end(viewer_sections())
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(body_control))
    def _expand(event) -> None:
        section = viewer_controller.current(viewer_sections())
        if section is None or section.kind != "CASE":
            status["value"] = "Move to a representative or boundary case first."
            event.app.invalidate()
            return
        selected["index"] = section.row_index or 0
        case = view.cases[selected["index"]]
        current = expanded["detail"]
        if current is not None and current.case_uid == case.uid:
            collapse()
            event.app.invalidate()
            return
        try:
            detail = adapter.case_detail(case.uid)
            expanded["detail"] = view.validate_detail(detail)
            status["value"] = ""
        except ResultWorkbenchError as error:
            expanded["detail"] = None
            status["value"] = f"Cannot open case: {error}"
        event.app.invalidate()

    def _collapse_detail(_event) -> bool:
        if expanded["detail"] is None:
            return False
        collapse()

        return True

    def close(event) -> None:
        event.app.exit(result=view)

    @bindings.add("escape", filter=has_focus(body_control), eager=True)
    @bindings.add("backspace", filter=has_focus(body_control), eager=True)
    def _back_or_close(event) -> None:
        dispatch_tui_back(event, _collapse_detail, close=close)

    @bind_case_insensitive_key(
        bindings, "q", filter=has_focus(body_control), eager=True
    )
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        close(event)

    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status['value']}"
                if status["value"]
                else (
                    " ↑/↓ section  Enter expand case  "
                    "Esc/Backspace back or close  Q quit · read-only "
                )
            )
        ),
        height=1,
        dont_extend_height=True,
    )
    viewer_frame = Frame(body, title="VIEWER")
    bind_focused_frame_style(viewer_frame, is_focused=lambda: True)
    application: Application[ResultWorkbenchView] = Application(
        layout=Layout(
            build_tui_frame(
                TuiRegion(viewer_frame),
                TuiRegion(footer),
            ),
            focused_element=body_control,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles(
            [
                MEMCOMMIT_TUI_STYLE,
                SEMANTIC_VIEWER_STYLE,
            ]
        ),
    )
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return view
