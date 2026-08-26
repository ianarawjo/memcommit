"""Compact, read-only terminal browser for quality-finder reports."""

from __future__ import annotations

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
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.workbenches.findings.document import (
    quality_finding_compact_fragments,
    quality_find_report_header_text,
)
from memcommit.reviewing.quality.report import (
    QualityFindBrowserReceipt,
    QualityFindReportView,
    QualityFindingReportItem,
)

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
    bindings = KeyBindings()

    def current_item() -> QualityFindingReportItem | None:
        return view.items[cursor["index"]] if view.items else None

    def render_header() -> list[tuple[str, str]]:
        return [
            (
                "class:report-label",
                f" {quality_find_report_header_text(view)}\n",
            ),
        ]

    def render_body() -> list[tuple[str, str]]:
        if not view.items:
            return [
                (
                    "class:report-neutral",
                    f" {safe_terminal_text(view.empty_message)}",
                )
            ]
        fragments: list[tuple[str, str]] = []
        for index, item in enumerate(view.items):
            focused = index == cursor["index"]
            if focused:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    "class:memcommit.table.selected" if focused else "",
                    "› " if focused else "  ",
                )
            )
            fragments.extend(
                quality_finding_compact_fragments(
                    item,
                    focused=focused,
                    show_context=view.source_count > 1,
                )
            )
        return fragments

    def render_footer() -> str:
        handoff = (
            ""
            if view.handoff_label is None
            else f" · Enter {safe_terminal_text(view.handoff_label)}"
        )
        return f" ↑/↓ finding{handoff} · Esc close · READ-ONLY"

    header = Window(
        FormattedTextControl(render_header),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    body_control = FormattedTextControl(render_body, focusable=True, show_cursor=False)
    body = Window(
        body_control,
        # Every finding is complete in this one scrollable list. The cursor
        # anchor keeps long wrapped paragraphs reachable without a detail mode.
        height=Dimension(min=4, preferred=24, max=38),
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

    @bindings.add("down")
    def _down(event) -> None:
        move_finding(1)
        event.app.invalidate()

    @bindings.add("up")
    def _up(event) -> None:
        move_finding(-1)
        event.app.invalidate()

    @bindings.add("home")
    def _home(event) -> None:
        if view.items:
            cursor["index"] = 0
        event.app.invalidate()

    @bindings.add("end")
    def _end(event) -> None:
        if view.items:
            cursor["index"] = len(view.items) - 1
        event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=QualityFindBrowserReceipt("CLOSE"))

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    def _back(event) -> None:
        close(event)

    @bindings.add("c-c", eager=True)
    @bind_case_insensitive_key(bindings, "q", eager=True)
    def _close(event) -> None:
        close(event)

    if view.handoff_label is not None:

        @bindings.add("enter", eager=True)
        def _handoff(event) -> None:
            item = current_item()
            if item is not None:
                event.app.exit(
                    result=QualityFindBrowserReceipt(
                        "HANDOFF",
                        item.uid,
                    )
                )

    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return QualityFindBrowserReceipt("CLOSE")


__all__ = ["run_quality_find_browser"]
