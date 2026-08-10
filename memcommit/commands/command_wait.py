"""Interactive, operation-neutral waiting for one blocking command stage.

The semantic operation remains one frozen blocking unit. In a TTY it runs in
an executor so the foreground terminal can offer the shared read-only Help
inventory; outside a TTY the existing stable one-line progress contract is
preserved.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import sys
import threading
import time
from typing import Protocol, TypeVar

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame

try:  # Typer 0.27+ vendors Click; older supported releases do not.
    from typer import _click as click
except ImportError:  # pragma: no cover - compatibility with older Typer
    import click

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
    bind_case_insensitive_key,
    display_escape_text,
)
from memcommit.study_action_log import record_study_action


T = TypeVar("T")


class CommandWaitProgress(Protocol):
    """The real stage boundary exposed to one frozen blocking operation."""

    def update(self, stage: str, *, step: int) -> None: ...


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

    current = click.get_current_context(silent=True)
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
) -> T:
    """Run blocking work while a TTY may browse the shared Help inventory.

    The Help session is deliberately read-only. It can inspect command names,
    descriptions, and audited forms, but cannot prefill or execute another
    command while the operation owns a frozen semantic turn.
    """

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
                + " · Q RETURN"
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
                    "  H / ?  EXPLORE MEM HELP  ",
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

    body_control = FormattedTextControl(
        wait_fragments,
        focusable=True,
        show_cursor=False,
    )

    async def explore_help() -> None:
        if help_open["value"] or not frozen_help_entries:
            return
        help_open["value"] = True
        emit_help_action("OPEN")
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

    @bind_case_insensitive_key(bindings, "h", eager=True)
    @bindings.add("?", eager=True)
    def _open_help(event) -> None:
        if not frozen_help_entries:
            status_message["value"] = "Help inventory is unavailable here."
            event.app.invalidate()
            return
        event.app.create_background_task(explore_help())

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
            lambda: [
                (
                    "class:title",
                    f" MEM {display_escape_text(operation.upper())} · WORKING",
                )
            ]
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    body = Frame(Window(body_control), title="BACKGROUND WORK")
    footer = Window(
        FormattedTextControl(
            lambda: (
                " H / ? Help · Q request close"
                if frozen_help_entries
                else " Q request close"
            )
        ),
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
        style=MEMCOMMIT_TUI_STYLE,
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
