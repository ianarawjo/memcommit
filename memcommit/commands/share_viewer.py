"""Minimal Context-and-Memories viewer for one outbound Share unit."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    bind_focused_frame_style,
    display_escape_text,
)
from memcommit.commands.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
    semantic_viewer_block_fragments,
)
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation
from memcommit.share import SharePreview


ShareViewerAction = Literal["send", "close"]


@dataclass(frozen=True)
class ShareViewerReceipt:
    """The only two outcomes of the process-local Share viewer."""

    action: ShareViewerAction


def _compact_memory(content: str) -> str:
    return display_escape_text(content).replace("\n", " ↵ ")


def share_context_text(preview: SharePreview) -> str:
    """Render the selected Context and destination without workflow jargon."""

    return "\n".join(
        (
            "CONTEXT TO SEND",
            display_escape_text(preview.source_context),
            f"MEMORIES · {len(preview.memories)}",
            "",
            "TO · " + display_escape_text(preview.endpoint),
        )
    )


def run_share_viewer(
    preview: SharePreview,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    navigation: SessionWorkbenchNavigation | None = None,
) -> ShareViewerReceipt:
    """Inspect one frozen Context and explicitly choose Send or close."""

    if not isinstance(preview, SharePreview):
        raise TypeError("Expected a SharePreview.")
    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Share requires a terminal.")

    nav = navigation or SessionWorkbenchNavigation(pane="viewer")
    selected = {"memory": 0}
    windows: dict[str, Window] = {}
    bindings = KeyBindings()

    context_document = SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid="SHARE:CONTEXT",
                kind="CONTEXT",
                block=SemanticViewerBlock(
                    (
                        ("class:section", "CONTEXT TO SEND\n"),
                        ("", display_escape_text(preview.source_context) + "\n"),
                        ("", f"MEMORIES · {len(preview.memories)}\n\n"),
                    ),
                    focus_indices=(0,),
                ),
            ),
            SemanticViewerSection(
                uid="SHARE:DESTINATION",
                kind="DESTINATION",
                block=SemanticViewerBlock(
                    (
                        (
                            "class:section",
                            "TO · " + display_escape_text(preview.endpoint),
                        ),
                    ),
                    focus_indices=(0,),
                ),
            ),
        )
    )

    def render_context():
        section_index = nav.section_index(context_document.navigation_sections)
        return FormattedText(
            context_document.render(
                focused_uid=context_document.navigation_sections[section_index].uid,
                viewer_focused=nav.pane == "viewer",
            )
        )

    def render_memories():
        fragments: list[tuple[str, str]] = []
        for index, memory in enumerate(preview.memories):
            focused = nav.pane == "items" and index == selected["memory"]
            marker = "›" if focused else " "
            fragments.extend(
                semantic_viewer_block_fragments(
                    [
                        (
                            "class:memory-object",
                            f"{marker} M{index + 1} · {_compact_memory(memory.content)}",
                        )
                    ],
                    active=focused,
                )
            )
            if index < len(preview.memories) - 1:
                fragments.append(("", "\n"))
        return FormattedText(fragments)

    def render_send():
        return semantic_viewer_block_fragments(
            [("class:section", "SEND CONTEXT · Enter")],
            active=nav.pane == "todo",
        )

    def focus_current(event) -> None:
        event.app.layout.focus(windows[nav.pane])
        event.app.invalidate()

    @bindings.add("tab")
    def _next(event) -> None:
        nav.cycle_panes(("viewer", "items", "todo"), 1)
        focus_current(event)

    @bindings.add("s-tab")
    def _previous(event) -> None:
        nav.cycle_panes(("viewer", "items", "todo"), -1)
        focus_current(event)

    @bindings.add("down")
    def _down(event) -> None:
        if nav.pane == "viewer":
            nav.move_section(context_document.navigation_sections, 1)
        elif nav.pane == "items":
            selected["memory"] = min(
                selected["memory"] + 1,
                len(preview.memories) - 1,
            )
        event.app.invalidate()

    @bindings.add("up")
    def _up(event) -> None:
        if nav.pane == "viewer":
            nav.move_section(context_document.navigation_sections, -1)
        elif nav.pane == "items":
            selected["memory"] = max(0, selected["memory"] - 1)
        event.app.invalidate()

    @bindings.add("enter")
    def _enter(event) -> None:
        if nav.pane == "todo":
            event.app.exit(result=ShareViewerReceipt(action="send"))

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    @bindings.add("q", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(result=ShareViewerReceipt(action="close"))

    header = Window(
        FormattedTextControl(
            " MEM SHARE · NOT SENT"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    context_window = Window(
        FormattedTextControl(render_context, focusable=True, show_cursor=False),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    memories_window = Window(
        FormattedTextControl(render_memories, focusable=True, show_cursor=False),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    send_window = Window(
        FormattedTextControl(render_send, focusable=True, show_cursor=False),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    windows.update(
        viewer=context_window,
        items=memories_window,
        todo=send_window,
    )
    context_frame = Frame(
        context_window,
        title="CONTEXT",
        height=Dimension(min=7, preferred=8, max=10),
    )
    memories_frame = Frame(
        memories_window,
        title="MEMORIES",
        height=Dimension(min=5, preferred=12, weight=1),
    )
    send_frame = Frame(
        send_window,
        title="ACTION",
        height=Dimension.exact(3),
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                " FOCUS "
                + {
                    "viewer": "CONTEXT",
                    "items": "MEMORIES",
                    "todo": "ACTION",
                }[nav.pane]
                + " · Tab/Shift-Tab move · "
                "↑↓ inspect · Enter sends in ACTION · Esc/Backspace/Q close"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[ShareViewerReceipt] = Application(
        layout=Layout(
            HSplit(
                [
                    header,
                    context_frame,
                    memories_frame,
                    send_frame,
                    footer,
                ]
            ),
            focused_element=context_window,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    for pane, frame in (
        ("viewer", context_frame),
        ("items", memories_frame),
        ("todo", send_frame),
    ):
        bind_focused_frame_style(
            frame,
            is_focused=lambda pane=pane: nav.pane == pane,
        )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return ShareViewerReceipt(action="close")


def run_share_unavailable_viewer(
    reason: str,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ShareViewerReceipt:
    """Open the bare Share surface even when no sendable plan exists."""

    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Share requires a terminal.")
    safe_reason = display_escape_text(reason)
    nav = SessionWorkbenchNavigation(pane="viewer")
    windows: dict[str, Window] = {}
    bindings = KeyBindings()

    def focus_current(event) -> None:
        event.app.layout.focus(windows[nav.pane])
        event.app.invalidate()

    @bindings.add("tab")
    def _next(event) -> None:
        nav.cycle_panes(("viewer", "items", "todo"), 1)
        focus_current(event)

    @bindings.add("s-tab")
    def _previous(event) -> None:
        nav.cycle_panes(("viewer", "items", "todo"), -1)
        focus_current(event)

    @bindings.add("escape", eager=True)
    @bindings.add("backspace", eager=True)
    @bindings.add("q", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(result=ShareViewerReceipt(action="close"))

    context_window = Window(
        FormattedTextControl(
            lambda: semantic_viewer_block_fragments(
                [
                    ("class:section", "NO SENDABLE CONTEXT\n"),
                    ("", safe_reason),
                ],
                active=nav.pane == "viewer",
            ),
            focusable=True,
            show_cursor=False,
        ),
        wrap_lines=True,
    )
    memories_window = Window(
        FormattedTextControl(
            lambda: [("", "(none)")],
            focusable=True,
            show_cursor=False,
        )
    )
    action_window = Window(
        FormattedTextControl(
            lambda: semantic_viewer_block_fragments(
                [("class:section", "SEND UNAVAILABLE")],
                active=nav.pane == "todo",
            ),
            focusable=True,
            show_cursor=False,
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    windows.update(
        viewer=context_window,
        items=memories_window,
        todo=action_window,
    )
    frames = (
        ("viewer", Frame(context_window, title="CONTEXT")),
        ("items", Frame(memories_window, title="MEMORIES")),
        (
            "todo",
            Frame(
                action_window,
                title="ACTION",
                height=Dimension.exact(3),
            ),
        ),
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                " FOCUS "
                + {
                    "viewer": "CONTEXT",
                    "items": "MEMORIES",
                    "todo": "ACTION",
                }[nav.pane]
                + " · Tab/Shift-Tab move · Esc/Backspace/Q close"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[ShareViewerReceipt] = Application(
        layout=Layout(
            HSplit(
                [
                    Window(
                        FormattedTextControl(
                            " MEM SHARE · NOT SENT"
                        ),
                        height=Dimension.exact(1),
                        dont_extend_height=True,
                    ),
                    *(frame for _pane, frame in frames),
                    footer,
                ]
            ),
            focused_element=context_window,
        ),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    for pane, frame in frames:
        bind_focused_frame_style(
            frame,
            is_focused=lambda pane=pane: nav.pane == pane,
        )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return ShareViewerReceipt(action="close")
