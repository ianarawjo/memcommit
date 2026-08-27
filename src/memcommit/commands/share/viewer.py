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

from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.interfaces.tui.components.frame import (
    bind_focused_frame_style,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.application.exact_command_review import ExactCommandReview
from memcommit.interfaces.tui.components.exact_command_review import (
    format_exact_command,
)
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerController,
    SemanticViewerDocument,
    SemanticViewerSection,
    semantic_viewer_block_fragments,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.application.reviewing.session_navigation import SessionWorkbenchNavigation
from memcommit.application.operations.share.model import SharePreview


ShareViewerAction = Literal["send", "browse_endpoint", "close"]


@dataclass(frozen=True)
class ShareViewerReceipt:
    """One explicit outcome of the process-local Share viewer."""

    action: ShareViewerAction


def _compact_memory(content: str) -> str:
    return display_escape_text(content).replace("\n", " ↵ ")


def _memory_count_text(count: int) -> str:
    return f"{count} {'Memory' if count == 1 else 'Memories'}"


def share_context_text(preview: SharePreview) -> str:
    """Render the selected Source Context scope without its separate endpoint."""

    if preview.include_descendants:
        members = tuple(
            f"C{index} · {display_escape_text(context.source_context)} · "
            f"{_memory_count_text(len(context.memories))}"
            for index, context in enumerate(preview.contexts, start=1)
        )
        return "\n".join(
            (
                "ROOT · "
                + display_escape_text(preview.source_context)
                + f" · {len(preview.contexts)} CONTEXTS"
                + f" · {len(preview.memories)} MEMORIES",
                *members,
            )
        )
    return "\n".join(
        (
            "CONTEXT TO SEND",
            display_escape_text(preview.source_context),
            f"MEMORIES · {len(preview.memories)}",
        )
    )


def share_memories_text(preview: SharePreview) -> str:
    """Render every disclosed Memory with its durable Source identity."""

    rows = (
        (context.source_context, memory)
        for context in preview.contexts
        for memory in context.memories
    )
    return "\n".join(
        memory.uid
        + " · "
        + (
            display_escape_text(context_name) + " · "
            if preview.include_descendants
            else ""
        )
        + _compact_memory(memory.content)
        for context_name, memory in rows
    )


def share_exact_command_text(preview: SharePreview) -> str:
    """Render the explicit direct/recursive command represented by a preview."""

    range_flag = "--recursive" if preview.include_descendants else "--direct"
    return format_exact_command(
        ExactCommandReview(
            argv=(
                "mem",
                "share",
                preview.source_context,
                range_flag,
                "--to",
                preview.endpoint,
            ),
            effects=("Send only the frozen Share unit shown above.",),
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
    viewer_controller = SemanticViewerController(nav)
    bindings = KeyBindings()
    if nav.pane not in {"viewer", "responses", "items", "todo"}:
        nav.focus("viewer")
    nav.move_row(len(preview.memories), 0)

    context_sections = [
        SemanticViewerSection(
            uid="SHARE:CONTEXT",
            kind="CONTEXT",
            block=SemanticViewerBlock(
                (
                    (
                        "class:section",
                        (
                            "ROOT · "
                            + display_escape_text(preview.source_context)
                            + f" · {len(preview.contexts)} CONTEXTS"
                            + f" · {len(preview.memories)} MEMORIES\n"
                            if preview.include_descendants
                            else "CONTEXT TO SEND\n"
                        ),
                    ),
                    *(
                        ()
                        if preview.include_descendants
                        else (
                            (
                                "",
                                display_escape_text(preview.source_context) + "\n",
                            ),
                            ("", f"MEMORIES · {len(preview.memories)}\n\n"),
                        )
                    ),
                ),
                focus_indices=(0,),
            ),
        ),
    ]
    if preview.include_descendants:
        context_sections.extend(
            SemanticViewerSection(
                uid=f"SHARE:CONTEXT:{index}",
                kind="CONTEXT",
                block=SemanticViewerBlock(
                    (
                        (
                            "class:section",
                            f"C{index} · "
                            + display_escape_text(context.source_context)
                            + " · "
                            + _memory_count_text(len(context.memories))
                            + "\n",
                        ),
                    ),
                    focus_indices=(0,),
                ),
            )
            for index, context in enumerate(preview.contexts, start=1)
        )
    context_document = SemanticViewerDocument(tuple(context_sections))

    def render_context():
        return FormattedText(
            viewer_controller.render(
                context_document,
                viewer_focused=nav.pane == "viewer",
            )
        )

    def render_memories():
        fragments: list[tuple[str, str]] = []
        rows = tuple(
            (context.source_context, memory)
            for context in preview.contexts
            for memory in context.memories
        )
        for index, (context_name, memory) in enumerate(rows):
            focused = nav.pane == "items" and index == nav.row_index
            marker = "›" if focused else " "
            owner = (
                display_escape_text(context_name) + " · "
                if preview.include_descendants
                else ""
            )
            fragments.extend(
                semantic_viewer_block_fragments(
                    [
                        (
                            "class:memory-object",
                            f"{marker} {memory.uid} · {owner}"
                            f"{_compact_memory(memory.content)}",
                        )
                    ],
                    active=focused,
                )
            )
            if index < len(preview.memories) - 1:
                fragments.append(("", "\n"))
        return FormattedText(fragments)

    def render_endpoint():
        return semantic_viewer_block_fragments(
            [
                (
                    "class:section",
                    display_escape_text(preview.endpoint) + " · [ BROWSE ] · Enter",
                )
            ],
            active=nav.pane == "responses",
        )

    def render_apply():
        return semantic_viewer_block_fragments(
            [
                (
                    "class:report-neutral",
                    share_exact_command_text(preview) + "\n",
                ),
                ("class:section", "[ PRESS ENTER TO APPLY ]"),
            ],
            active=nav.pane == "todo",
        )

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        event.app.exit(result=ShareViewerReceipt(action="close"))

    header = Window(
        FormattedTextControl(
            (
                " MEM SHARE · RECURSIVE · NOT SENT"
                if preview.include_descendants
                else " MEM SHARE · NOT SENT"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    context_window = Window(
        FormattedTextControl(render_context, focusable=True, show_cursor=False),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    endpoint_window = Window(
        FormattedTextControl(render_endpoint, focusable=True, show_cursor=False),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    memories_window = Window(
        FormattedTextControl(render_memories, focusable=True, show_cursor=False),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    apply_window = Window(
        FormattedTextControl(render_apply, focusable=True, show_cursor=False),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def move_viewer(_event, delta: int) -> SurfaceMoveResult:
        before = viewer_controller.index(context_document)
        viewer_controller.move(context_document, delta)
        after = viewer_controller.index(context_document)
        return "MOVED" if after != before else "BOUNDARY"

    def enter_viewer(delta: int) -> None:
        if delta > 0:
            viewer_controller.home(context_document)
        else:
            viewer_controller.end(context_document)

    def move_memories(_event, delta: int) -> SurfaceMoveResult:
        before = nav.row_index
        nav.move_row(len(preview.memories), delta)
        return "MOVED" if nav.row_index != before else "BOUNDARY"

    def enter_memories(delta: int) -> None:
        nav.row_index = 0 if delta > 0 else max(0, len(preview.memories) - 1)

    def boundary(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def browse_endpoint(event) -> SurfaceActionResult:
        event.app.exit(result=ShareViewerReceipt(action="browse_endpoint"))
        return "HANDLED"

    def send(event) -> SurfaceActionResult:
        event.app.exit(result=ShareViewerReceipt(action="send"))
        return "HANDLED"

    def close(event) -> SurfaceActionResult:
        event.app.exit(result=ShareViewerReceipt(action="close"))
        return "HANDLED"

    surface_controller = SurfaceFocusController(
        (
            FocusSurface(
                "share-context",
                context_window,
                move_vertical=move_viewer,
                back=close,
                on_focus=lambda: nav.focus("viewer"),
                on_vertical_enter=enter_viewer,
            ),
            FocusSurface(
                "share-endpoint",
                endpoint_window,
                move_vertical=boundary,
                activate=browse_endpoint,
                back=close,
                on_focus=lambda: nav.focus("responses"),
            ),
            FocusSurface(
                "share-memories",
                memories_window,
                move_vertical=move_memories,
                back=close,
                on_focus=lambda: nav.focus("items"),
                on_vertical_enter=enter_memories,
            ),
            FocusSurface(
                "share-apply",
                apply_window,
                move_vertical=boundary,
                activate=send,
                back=close,
                on_focus=lambda: nav.focus("todo"),
            ),
        )
    )
    bind_surface_navigation(bindings, surface_controller, back=True)
    context_frame = Frame(
        context_window,
        title=("FROM · CONTEXTS" if preview.include_descendants else "FROM · CONTEXT"),
        height=Dimension(min=7, preferred=8, max=10),
    )
    endpoint_frame = Frame(
        endpoint_window,
        title="TO · SHARE ENDPOINT",
        height=Dimension.exact(3),
    )
    memories_frame = Frame(
        memories_window,
        title="MEMORIES",
        height=Dimension(min=5, preferred=12, weight=1),
    )
    apply_frame = Frame(
        apply_window,
        title="APPLY",
        height=Dimension.exact(4),
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                " FOCUS "
                + {
                    "viewer": (
                        "FROM · CONTEXTS"
                        if preview.include_descendants
                        else "FROM · CONTEXT"
                    ),
                    "responses": "TO · SHARE ENDPOINT",
                    "items": "MEMORIES",
                    "todo": "APPLY",
                }[nav.pane]
                + " · Tab/Shift-Tab move · "
                "↑↓ inspect · Enter browses TO or applies exact command · "
                "Esc/Backspace/Q close"
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
                    endpoint_frame,
                    memories_frame,
                    apply_frame,
                    footer,
                ]
            ),
            focused_element={
                "viewer": context_window,
                "responses": endpoint_window,
                "items": memories_window,
                "todo": apply_window,
            }[nav.pane],
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
        ("responses", endpoint_frame),
        ("items", memories_frame),
        ("todo", apply_frame),
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
    bindings = KeyBindings()

    @bind_case_insensitive_key(bindings, "q", eager=True)
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
    endpoint_window = Window(
        FormattedTextControl(
            lambda: semantic_viewer_block_fragments(
                [("class:section", "NO SELECTED SHARE ENDPOINT")],
                active=nav.pane == "responses",
            ),
            focusable=True,
            show_cursor=False,
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    memories_window = Window(
        FormattedTextControl(
            lambda: [("", "(none)")],
            focusable=True,
            show_cursor=False,
        )
    )
    apply_window = Window(
        FormattedTextControl(
            lambda: semantic_viewer_block_fragments(
                [("class:section", "[ APPLY UNAVAILABLE ]")],
                active=nav.pane == "todo",
            ),
            focusable=True,
            show_cursor=False,
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    def boundary(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def close(event) -> SurfaceActionResult:
        event.app.exit(result=ShareViewerReceipt(action="close"))
        return "HANDLED"

    surface_controller = SurfaceFocusController(
        (
            FocusSurface(
                "share-unavailable-context",
                context_window,
                move_vertical=boundary,
                back=close,
                on_focus=lambda: nav.focus("viewer"),
            ),
            FocusSurface(
                "share-unavailable-endpoint",
                endpoint_window,
                move_vertical=boundary,
                back=close,
                on_focus=lambda: nav.focus("responses"),
            ),
            FocusSurface(
                "share-unavailable-memories",
                memories_window,
                move_vertical=boundary,
                back=close,
                on_focus=lambda: nav.focus("items"),
            ),
            FocusSurface(
                "share-unavailable-apply",
                apply_window,
                move_vertical=boundary,
                back=close,
                on_focus=lambda: nav.focus("todo"),
            ),
        )
    )
    bind_surface_navigation(bindings, surface_controller, back=True)
    frames = (
        ("viewer", Frame(context_window, title="FROM · CONTEXT")),
        (
            "responses",
            Frame(
                endpoint_window,
                title="TO · SHARE ENDPOINT",
                height=Dimension.exact(3),
            ),
        ),
        ("items", Frame(memories_window, title="MEMORIES")),
        (
            "todo",
            Frame(
                apply_window,
                title="APPLY",
                height=Dimension.exact(3),
            ),
        ),
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                " FOCUS "
                + {
                    "viewer": "FROM · CONTEXT",
                    "responses": "TO · SHARE ENDPOINT",
                    "items": "MEMORIES",
                    "todo": "APPLY",
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
                        FormattedTextControl(" MEM SHARE · NOT SENT"),
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
