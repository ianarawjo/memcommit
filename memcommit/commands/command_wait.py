"""Interactive, operation-neutral waiting for one blocking command stage.

The semantic operation remains one frozen blocking unit. In a TTY it runs in
an executor so the foreground terminal can offer the shared read-only Help
inventory; outside a TTY the existing stable one-line progress contract is
preserved.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import sys
import threading
import time
from typing import Protocol, TypeVar

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.containers import DynamicContainer
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

try:  # Typer 0.27+ vendors Click but does not re-export this helper.
    from typer._click.globals import get_current_context
except ImportError:  # pragma: no cover - compatibility with older Typer
    from click import get_current_context

from memcommit.commands.background_turn import BackgroundExecutorTurn
from memcommit.commands.command_progress import (
    BUSY_INTERVAL_SECONDS,
    CommandProgress,
    render_progress_line,
)
from memcommit.commands.help_inventory import (
    CommandEntry,
    command_entries,
    run_help_selector,
)
from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    bind_case_insensitive_key,
    build_scrollable_formatted_text_pane,
    display_escape_text,
    move_wrapped_read_cursor,
    scroll_wrapped_page,
)
from memcommit.study_action_log import record_study_action


T = TypeVar("T")


class CommandWaitProgress(Protocol):
    """The real stage boundary exposed to one frozen blocking operation."""

    def update(self, stage: str, *, step: int) -> None: ...


@dataclass(frozen=True)
class CommandWaitView:
    """Frozen operation-owned screen restored when Help is hidden.

    The waiting shell owns only read-only display and navigation. Callers own
    the semantic text so a pending result is never presented as an already
    available report.
    """

    title: str
    text: str | StyleAndTextTuples


def build_report_loading_view(
    operation: str,
    *,
    sections: Sequence[str],
) -> CommandWaitView:
    """Build an honest report-shaped skeleton without invented content."""

    if not operation.strip() or not sections or any(
        not section.strip() for section in sections
    ):
        raise ValueError("A loading report requires an operation and sections.")
    widths = (58, 44, 66, 36)
    fragments: StyleAndTextTuples = [
        ("class:loading-label", f"MEM {operation.upper()} · REPORT BUILDING\n"),
        ("class:loading-status", "CONTENT PENDING · THIS IS NOT A RESULT\n\n"),
    ]
    for section_index, section in enumerate(sections):
        fragments.append(("class:viewer-section", section.upper() + "\n"))
        row_count = 3 if section_index == 0 else 2
        for row_index in range(row_count):
            width = widths[(section_index + row_index) % len(widths)]
            fragments.append(
                (
                    "class:loading-placeholder",
                    "  ╶" + ("━" * width) + "╴\n",
                )
            )
        if section_index < len(sections) - 1:
            fragments.append(("", "\n"))
    fragments.extend(
        [
            ("", "\n"),
            (
                "class:report-neutral",
                "The completed report will replace this shape after analysis.\n",
            ),
            (
                "class:report-neutral",
                "C shows the exact frozen inputs; H opens Help.",
            ),
        ]
    )
    return CommandWaitView(
        title=f"{operation.upper()} REPORT · BUILDING",
        text=fragments,
    )


class _InteractiveProgress:
    def __init__(
        self,
        operation: str,
        stage: str,
        *,
        step: int,
        total: int,
        started_at: float,
    ) -> None:
        self.operation = operation
        self._stage = stage
        self._step = step
        self.total = total
        self.started_at = started_at
        self._finished_at: float | None = None
        self._lock = threading.Lock()
        self._application: Application[None] | None = None
        render_progress_line(
            operation,
            stage,
            step=step,
            total=total,
            elapsed_seconds=0,
            frame_index=0,
        )

    def bind(self, application: Application[None]) -> None:
        self._application = application

    def update(self, stage: str, *, step: int) -> None:
        render_progress_line(
            self.operation,
            stage,
            step=step,
            total=self.total,
            elapsed_seconds=0,
            frame_index=0,
        )
        with self._lock:
            self._stage = stage
            self._step = step
        application = self._application
        if application is not None:
            application.invalidate()

    def mark_ready(self) -> None:
        """Freeze elapsed work time before optional continued Help browsing."""

        with self._lock:
            if self._finished_at is None:
                self._finished_at = time.monotonic()

    def render(self, *, frame_index: int) -> str:
        with self._lock:
            stage = self._stage
            step = self._step
            finished_at = self._finished_at
        return render_progress_line(
            self.operation,
            stage,
            step=step,
            total=self.total,
            elapsed_seconds=(
                finished_at if finished_at is not None else time.monotonic()
            )
            - self.started_at,
            frame_index=frame_index,
        )


def _current_help_entries() -> tuple[CommandEntry, ...]:
    """Freeze the root command inventory before background work begins."""

    current = get_current_context(silent=True)
    if current is None:
        return ()
    while current.parent is not None:
        current = current.parent
    return tuple(command_entries(current))


def _study_help_action(action: str, command_name: str | None) -> None:
    detail = f"HELP {action}"
    if command_name is not None:
        detail += f" {command_name}"
    record_study_action(
        "TUI_ACTION",
        surface="command-wait",
        action=detail,
    )


def run_command_wait(
    operation: str,
    stage: str,
    *,
    total: int,
    work: Callable[[CommandWaitProgress], T],
    step: int = 1,
    help_entries: Sequence[CommandEntry] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    interactive: bool | None = None,
    interval: float = BUSY_INTERVAL_SECONDS,
    on_help_action: Callable[[str, str | None], None] | None = None,
    return_view: CommandWaitView | None = None,
    context_view: CommandWaitView | None = None,
) -> T:
    """Run blocking work while a TTY may browse the shared Help inventory.

    The Help session is deliberately read-only. It can inspect command names,
    descriptions, and audited forms, but cannot prefill or execute another
    command while the operation owns a frozen semantic turn.
    """

    if context_view is not None and return_view is None:
        raise ValueError("A confirmed-input view requires a primary return view.")

    enabled = (
        sys.stdin.isatty() and sys.stdout.isatty()
        if interactive is None
        else interactive
    )
    if not enabled:
        with CommandProgress(
            operation,
            stage,
            total=total,
            step=step,
            interval=interval,
        ) as progress:
            return work(progress)

    frozen_help_entries = tuple(
        _current_help_entries() if help_entries is None else help_entries
    )
    started_at = time.monotonic()
    progress = _InteractiveProgress(
        operation,
        stage,
        step=step,
        total=total,
        started_at=started_at,
    )
    background: BackgroundExecutorTurn[T] = BackgroundExecutorTurn(
        interval_seconds=interval
    )
    bindings = KeyBindings()
    result: dict[str, T] = {}
    error: dict[str, Exception] = {}
    help_open = {"value": False}
    ready = {"value": False}
    close_requested = {"value": False}
    status_message = {"value": ""}
    context_open = {"value": False}
    application_ref: dict[str, Application[None]] = {}

    def emit_help_action(action: str, command_name: str | None = None) -> None:
        _study_help_action(action, command_name)
        if on_help_action is not None:
            on_help_action(action, command_name)

    def help_status() -> str:
        if ready["value"]:
            return (
                f"MEM {operation.upper()} · "
                + ("ERROR READY" if error else "RESULT READY")
                + " · H / Q RETURN"
            )
        return progress.render(frame_index=background.frame)

    def wait_fragments() -> list[tuple[str, str]]:
        line = progress.render(frame_index=background.frame)
        fragments: list[tuple[str, str]] = [
            ("[SetCursorPosition]", ""),
            ("class:title", f"\n  {line}\n\n"),
            (
                "",
                "  This operation continues while the shared Help inventory "
                "is open.\n\n",
            ),
        ]
        if frozen_help_entries:
            fragments.append(
                (
                    "class:selected",
                    "  H / ?  REOPEN MEM HELP  ",
                )
            )
            fragments.append(("", "\n"))
        else:
            fragments.append(("", "  Help inventory unavailable.\n"))
        if status_message["value"]:
            fragments.append(
                (
                    "class:warning",
                    "\n  " + display_escape_text(status_message["value"]),
                )
            )
        return fragments

    return_pane = (
        build_scrollable_formatted_text_pane(
            return_view.title,
            return_view.text,
            height=Dimension(min=4, weight=1),
        )
        if return_view is not None
        else None
    )
    context_pane = (
        build_scrollable_formatted_text_pane(
            context_view.title,
            context_view.text,
            height=Dimension(min=4, weight=1),
        )
        if context_view is not None
        else None
    )
    body_control = (
        return_pane.text_area
        if return_pane is not None
        else FormattedTextControl(
            wait_fragments,
            focusable=True,
            show_cursor=False,
        )
    )

    async def explore_help() -> None:
        try:
            await run_in_terminal(
                lambda: run_help_selector(
                    list(frozen_help_entries),
                    app_input=app_input,
                    app_output=app_output,
                    require_tty=False,
                    mode="EXPLORE",
                    status_supplier=help_status,
                    on_explore_action=emit_help_action,
                    # OPEN means the nested application owns input, not merely
                    # that its handoff task was scheduled. Pipe input and a
                    # fast participant can otherwise race the transition.
                    on_ready=lambda: emit_help_action("OPEN"),
                ),
                # The nested Help Application owns its own event loop. Keep it
                # in this process but outside the waiting Application's loop.
                in_executor=True,
            )
        finally:
            help_open["value"] = False
            emit_help_action("CLOSE")
        application = application_ref["application"]
        if ready["value"]:
            application.exit()
        else:
            application.invalidate()

    def open_help(application: Application[None]) -> bool:
        if help_open["value"] or not frozen_help_entries:
            return False
        # Reserve the visible Help state before scheduling either it or the
        # worker. A very fast worker must still see Help as open and leave its
        # completed result waiting for the participant's explicit H/Q return.
        help_open["value"] = True
        try:
            application.create_background_task(explore_help())
        except Exception:
            help_open["value"] = False
            raise
        return True

    @bind_case_insensitive_key(bindings, "h", eager=True)
    @bindings.add("?", eager=True)
    def _open_help(event) -> None:
        if not frozen_help_entries:
            status_message["value"] = "Help inventory is unavailable here."
            event.app.invalidate()
            return
        open_help(event.app)

    if context_pane is not None and return_pane is not None:

        @bind_case_insensitive_key(bindings, "c", eager=True)
        def _toggle_context(event) -> None:
            context_open["value"] = not context_open["value"]
            target = context_pane if context_open["value"] else return_pane
            event.app.layout.focus(target.text_area)
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action=(
                    "CONFIRMED INPUTS OPEN"
                    if context_open["value"]
                    else "CONFIRMED INPUTS CLOSE"
                ),
            )
            event.app.invalidate()

    if return_pane is not None:

        def record_return_view_action(action: str) -> None:
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action=f"RETURN VIEW {action}",
            )

        @bindings.add("up")
        def _scroll_return_view_up(event) -> None:
            move_wrapped_read_cursor(event, direction=-1)
            record_return_view_action("UP")

        @bindings.add("down")
        def _scroll_return_view_down(event) -> None:
            move_wrapped_read_cursor(event, direction=1)
            record_return_view_action("DOWN")

        @bindings.add("pageup")
        def _page_return_view_up(event) -> None:
            scroll_wrapped_page(event, direction=-1)
            record_return_view_action("PAGE UP")

        @bindings.add("pagedown")
        def _page_return_view_down(event) -> None:
            scroll_wrapped_page(event, direction=1)
            record_return_view_action("PAGE DOWN")

        @bindings.add("home")
        def _return_view_home(event) -> None:
            event.current_buffer.cursor_position = 0
            record_return_view_action("HOME")

        @bindings.add("end")
        def _return_view_end(event) -> None:
            event.current_buffer.cursor_position = len(event.current_buffer.text)
            record_return_view_action("END")

    def request_close(event) -> None:
        if background.request_close():
            close_requested["value"] = True
            status_message["value"] = (
                "Close requested; waiting for the current frozen work to finish."
            )
            record_study_action(
                "TUI_ACTION",
                surface="command-wait",
                action="CLOSE REQUESTED",
            )
            event.app.invalidate()
            return
        close_requested["value"] = True
        event.app.exit()

    @bind_case_insensitive_key(bindings, "q", eager=True)
    @bindings.add("c-c", eager=True)
    def _close(event) -> None:
        request_close(event)

    header = Window(
        FormattedTextControl(
            lambda: [("class:title", " " + help_status())]
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    if return_pane is not None:
        body = DynamicContainer(
            lambda: (
                context_pane.container
                if context_open["value"] and context_pane is not None
                else return_pane.container
            )
        )
    else:
        body = Frame(Window(body_control), title="BACKGROUND WORK")

    def footer_text() -> str:
        if status_message["value"]:
            return " " + display_escape_text(status_message["value"])
        if return_pane is not None:
            help_hint = "H / ? Help · " if frozen_help_entries else ""
            context_hint = "C inputs/report · " if context_pane is not None else ""
            return (
                f" {context_hint}{help_hint}↑/↓ scroll · "
                "PgUp/PgDn page · Home/End · "
                "Q request close · read-only"
            )
        return (
            " H / ? Help · Q request close"
            if frozen_help_entries
            else " Q request close"
        )

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    application: Application[None] = Application(
        layout=Layout(HSplit([header, body, footer]), focused_element=body_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )
    application_ref["application"] = application
    progress.bind(application)

    def on_success(value: T) -> None:
        result["value"] = value
        progress.mark_ready()
        ready["value"] = True
        emit_help_action("RESULT_READY")

    def on_error(value: Exception) -> None:
        error["value"] = value
        progress.mark_ready()
        ready["value"] = True
        emit_help_action("ERROR_READY")

    def on_idle() -> None:
        if help_open["value"]:
            application.invalidate()
        else:
            application.exit()

    def on_close() -> None:
        close_requested["value"] = True
        application.exit()

    def start_work() -> None:
        # The report (or prior report) remains the stable default surface.
        # Help is an explicit exploration layer and never delays a fast result.
        background.start(
            application,
            work=lambda: work(progress),
            on_success=on_success,
            on_error=on_error,
            on_idle=on_idle,
            on_close=on_close,
        )

    try:
        application.run(pre_run=start_work)
    except (EOFError, KeyboardInterrupt):
        close_requested["value"] = True
    if close_requested["value"]:
        raise KeyboardInterrupt()
    if error:
        raise error["value"]
    return result["value"]
