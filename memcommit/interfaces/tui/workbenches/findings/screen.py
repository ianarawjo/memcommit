"""Compact, read-only terminal browser for quality-finder reports."""

from __future__ import annotations

import sys

from prompt_toolkit.application import Application
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, FormattedTextControl, Layout, Window
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.components.frame import TuiRegion, build_tui_frame
from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key
from memcommit.interfaces.tui.core.text_layout import elide_terminal_text
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerController,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.quality_find_report import (
    QualityFindBrowserReceipt,
    QualityFindReportView,
    QualityFindingReportItem,
)
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation


def _plain(value: str) -> str:
    return safe_terminal_text(value).strip()


def _item_document(item: QualityFindingReportItem) -> SemanticViewerDocument:
    sections: list[SemanticViewerSection] = [
        SemanticViewerSection(
            f"FINDING:{item.uid}:IDENTITY",
            "IDENTITY",
            SemanticViewerBlock(
                (
                    (
                        "class:report-label",
                        f" {safe_terminal_text(item.kind)} · "
                        f"{safe_terminal_text(item.classification)}\n",
                    ),
                    ("class:memory-object", f" {safe_terminal_text(item.title)}\n"),
                )
            ),
        )
    ]
    for source in item.sources:
        sections.append(
            SemanticViewerSection(
                f"FINDING:{item.uid}:SOURCE:{source.memory_uid}",
                "SOURCE",
                SemanticViewerBlock(
                    (
                        (
                            "class:report-label",
                            f" {safe_terminal_text(source.label)} · "
                            f"{safe_terminal_text(source.context_name)} · "
                            f"[{safe_terminal_text(source.memory_uid[:8])}]\n",
                        ),
                        (
                            "class:memory-object",
                            f" {safe_terminal_text(source.content)}\n",
                        ),
                    )
                ),
            )
        )
    sections.append(
        SemanticViewerSection(
            f"FINDING:{item.uid}:REASON",
            "REASON",
            SemanticViewerBlock(
                (
                    (
                        "class:report-label",
                        f" {safe_terminal_text(item.reason_heading)}\n",
                    ),
                    ("class:viewer-body", f" {safe_terminal_text(item.reason)}\n"),
                )
            ),
        )
    )
    if item.follow_up:
        sections.append(
            SemanticViewerSection(
                f"FINDING:{item.uid}:FOLLOW_UP",
                "FOLLOW_UP",
                SemanticViewerBlock(
                    (
                        ("class:report-label", " FOLLOW-UP QUESTION\n"),
                        (
                            "class:viewer-body",
                            f" {safe_terminal_text(item.follow_up)}\n",
                        ),
                    )
                ),
            )
        )
    if item.readings:
        fragments: list[tuple[str, str]] = [
            ("class:report-label", " POSSIBLE READINGS\n")
        ]
        for reading in item.readings:
            fragments.extend(
                [
                    (
                        "class:report-neutral",
                        f" - {safe_terminal_text(reading.label)} · ",
                    ),
                    ("class:viewer-body", safe_terminal_text(reading.text) + "\n"),
                ]
            )
        sections.append(
            SemanticViewerSection(
                f"FINDING:{item.uid}:READINGS",
                "READINGS",
                SemanticViewerBlock(tuple(fragments)),
            )
        )
    return SemanticViewerDocument(tuple(sections))


def run_quality_find_browser(
    view: QualityFindReportView,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> QualityFindBrowserReceipt:
    """Inspect a frozen report and optionally leave for another operation."""

    if require_tty:
        require_interactive_terminal(
            f"Interactive {view.operation.title()}",
            snapshot_hint="Run the same finder without --select for plain output.",
        )
    if not isinstance(view, QualityFindReportView):
        raise TypeError("Quality Find browser requires a typed report view.")

    cursor = {"index": 0}
    detail = {"open": False}
    navigation = SessionWorkbenchNavigation(pane="viewer")
    viewer = SemanticViewerController(navigation)
    bindings = KeyBindings()

    def current_item() -> QualityFindingReportItem | None:
        return view.items[cursor["index"]] if view.items else None

    def current_document() -> SemanticViewerDocument | None:
        item = current_item()
        return None if item is None else _item_document(item)

    def render_header() -> list[tuple[str, str]]:
        position = (
            "NO FINDINGS"
            if not view.items
            else f"{cursor['index'] + 1}/{len(view.items)}"
        )
        mode = "DETAIL" if detail["open"] else "FINDINGS"
        return [
            (
                "class:report-label",
                f" {safe_terminal_text(view.operation)} · {mode} · {position}\n",
            ),
            (
                "class:report-neutral",
                f" {view.source_count} CONTEXT(S) · "
                f"{view.memory_count} SOURCE MEMORIES · "
                f"{safe_terminal_text(view.route)}\n",
            ),
        ]

    def render_list() -> list[tuple[str, str]]:
        if not view.items:
            return [("class:report-neutral", f" {safe_terminal_text(view.empty_message)}")]
        fragments: list[tuple[str, str]] = []
        for index, item in enumerate(view.items):
            focused = index == cursor["index"]
            if focused:
                fragments.append(("[SetCursorPosition]", ""))
            pointer = "›" if focused else " "
            line = (
                f"{pointer} {index + 1:>2}  {safe_terminal_text(item.classification)}"
                f" · {safe_terminal_text(item.title)}"
            )
            fragments.append(
                (
                    "class:memcommit.table.selected" if focused else "",
                    elide_terminal_text(line, 156) + "\n",
                )
            )
        return fragments

    def render_body() -> list[tuple[str, str]]:
        if not detail["open"]:
            return render_list()
        document = current_document()
        if document is None:
            return [("class:report-neutral", f" {safe_terminal_text(view.empty_message)}")]
        return viewer.render(document, viewer_focused=True)

    def render_footer() -> str:
        handoff = (
            ""
            if view.handoff_key is None
            else f" · {view.handoff_key.upper()} {safe_terminal_text(view.handoff_label or '')}"
        )
        if detail["open"]:
            return (
                " ↑/↓ section · PgUp/PgDn page · ←/→ finding · "
                f"Esc/Backspace list{handoff} · Q close · read-only"
            )
        return (
            " ↑/↓ finding · Enter inspect · Home/End · "
            f"Esc/Backspace/Q close{handoff} · read-only"
        )

    header = Window(
        FormattedTextControl(render_header),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    body_control = FormattedTextControl(render_body, focusable=True, show_cursor=False)
    body = Window(
        body_control,
        # Keep the browser inline while allowing one ordinary finding detail
        # (sources, reason, question, readings) to remain visible as a unit.
        height=Dimension(min=4, preferred=12, max=20),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(body),
        TuiRegion(footer),
    )
    application: Application[QualityFindBrowserReceipt] = Application(
        layout=Layout(root, focused_element=body_control),
        key_bindings=bindings,
        full_screen=False,
        erase_when_done=False,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def move_finding(delta: int) -> None:
        if not view.items:
            return
        cursor["index"] = max(0, min(cursor["index"] + delta, len(view.items) - 1))
        navigation.section_uid = None

    @bindings.add("down")
    def _down(event) -> None:
        document = current_document()
        if detail["open"] and document is not None:
            viewer.move(document, 1)
        else:
            move_finding(1)
        event.app.invalidate()

    @bindings.add("up")
    def _up(event) -> None:
        document = current_document()
        if detail["open"] and document is not None:
            viewer.move(document, -1)
        else:
            move_finding(-1)
        event.app.invalidate()

    @bindings.add("left")
    def _left(event) -> None:
        if detail["open"]:
            move_finding(-1)
            event.app.invalidate()

    @bindings.add("right")
    def _right(event) -> None:
        if detail["open"]:
            move_finding(1)
            event.app.invalidate()

    @bindings.add("pageup")
    def _page_up(event) -> None:
        document = current_document()
        if detail["open"] and document is not None:
            viewer.move(document, -8)
            event.app.invalidate()

    @bindings.add("pagedown")
    def _page_down(event) -> None:
        document = current_document()
        if detail["open"] and document is not None:
            viewer.move(document, 8)
            event.app.invalidate()

    @bindings.add("home")
    def _home(event) -> None:
        document = current_document()
        if detail["open"] and document is not None:
            viewer.home(document)
        elif view.items:
            cursor["index"] = 0
        event.app.invalidate()

    @bindings.add("end")
    def _end(event) -> None:
        document = current_document()
        if detail["open"] and document is not None:
            viewer.end(document)
        elif view.items:
            cursor["index"] = len(view.items) - 1
        event.app.invalidate()

    @bindings.add("enter")
    def _inspect(event) -> None:
        if current_item() is not None:
            detail["open"] = True
            navigation.section_uid = None
            event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=QualityFindBrowserReceipt("CLOSE"))

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        if detail["open"]:
            detail["open"] = False
            navigation.section_uid = None
            event.app.invalidate()
            return
        close(event)

    @bindings.add("c-c", eager=True)
    @bind_case_insensitive_key(bindings, "q", eager=True)
    def _close(event) -> None:
        close(event)

    if view.handoff_key is not None:

        @bind_case_insensitive_key(bindings, view.handoff_key, eager=True)
        def _handoff(event) -> None:
            item = current_item()
            event.app.exit(
                result=QualityFindBrowserReceipt(
                    "HANDOFF",
                    None if item is None else item.uid,
                )
            )

    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return QualityFindBrowserReceipt("CLOSE")


__all__ = ["run_quality_find_browser"]
