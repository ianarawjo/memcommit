"""Shared read-only Help handoff for long-lived terminal sessions."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.filters import FilterOrBool
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import Output

try:  # Typer 0.27+ vendors Click but does not re-export this helper.
    from typer._click.globals import get_current_context
except ImportError:  # pragma: no cover - compatibility with older Typer
    from click import get_current_context

from memcommit.adapters.interfaces.tui.operations.help.inventory import (
    CommandEntry,
    command_entries,
    run_help_selector,
)
from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.persistence.command_ledger.study_actions import record_study_action


HelpActionObserver = Callable[[str, str | None], None]
HelpClosedHandler = Callable[[Application], None]
HelpUnavailableHandler = Callable[[Application], None]


def current_help_entries() -> tuple[CommandEntry, ...]:
    """Freeze the root command inventory for one process-local TUI session."""

    current = get_current_context(silent=True)
    if current is None:
        return ()
    while current.parent is not None:
        current = current.parent
    return tuple(command_entries(current))


class SessionHelpController:
    """Temporarily hand one active TUI to the shared Help inventory.

    The parent Application keeps its layout, focus, buffers, and operation
    state. Help receives only the frozen public command inventory and owns
    terminal input until H, Q, or Escape returns to that exact parent.
    """

    def __init__(
        self,
        *,
        entries: Sequence[CommandEntry] | None = None,
        app_input: Input | None = None,
        app_output: Output | None = None,
        title: str = "mem help · session guide",
        return_label: str = "session",
        status_supplier: Callable[[], str] | None = None,
        study_surface: str | None = None,
        on_action: HelpActionObserver | None = None,
        on_closed: HelpClosedHandler | None = None,
        on_unavailable: HelpUnavailableHandler | None = None,
    ) -> None:
        self.entries = tuple(
            current_help_entries() if entries is None else entries
        )
        self.app_input = app_input
        self.app_output = app_output
        self.title = title
        self.return_label = return_label
        self.status_supplier = status_supplier
        self.study_surface = study_surface
        self.on_action = on_action
        self.on_closed = on_closed
        self.on_unavailable = on_unavailable
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def _emit(self, action: str, command_name: str | None = None) -> None:
        if self.study_surface is not None:
            detail = f"HELP {action}"
            if command_name is not None:
                detail += f" {command_name}"
            record_study_action(
                "TUI_ACTION",
                surface=self.study_surface,
                action=detail,
            )
        if self.on_action is not None:
            self.on_action(action, command_name)

    def open(self, application: Application) -> bool:
        """Schedule one exclusive Help handoff; return whether it was opened."""

        if self._open:
            return False
        if not self.entries:
            if self.on_unavailable is not None:
                self.on_unavailable(application)
            application.invalidate()
            return False

        # Reserve the handoff before scheduling it. Pipe-driven tests and fast
        # repeated keys must not start two nested Applications concurrently.
        self._open = True

        async def explore_help() -> None:
            try:
                await run_in_terminal(
                    lambda: run_help_selector(
                        list(self.entries),
                        app_input=self.app_input,
                        app_output=self.app_output,
                        require_tty=False,
                        mode="EXPLORE",
                        status_supplier=self.status_supplier,
                        on_explore_action=self._emit,
                        on_ready=lambda: self._emit("OPEN"),
                        explore_title=self.title,
                        explore_return_label=self.return_label,
                    ),
                    # The nested Help Application owns its own event loop and
                    # must not block animation or a provider turn in the parent.
                    in_executor=True,
                )
            finally:
                self._open = False
                self._emit("CLOSE")
                # Restore the parent even if Help rendering itself fails. The
                # task may still report that error, but it must not leave the
                # session permanently marked open or without a repaint.
                if self.on_closed is not None:
                    self.on_closed(application)
                else:
                    application.invalidate()

        try:
            application.create_background_task(explore_help())
        except Exception:
            self._open = False
            raise
        return True

    def bind(
        self,
        bindings: KeyBindings,
        *,
        filter: FilterOrBool = True,
        eager: FilterOrBool = True,
        additional_keys: Sequence[str] = (),
    ) -> None:
        """Bind H/h plus any nonalphabetic aliases to this Help handoff."""

        @bind_case_insensitive_key(
            bindings,
            "h",
            filter=filter,
            eager=eager,
        )
        def open_help(event) -> None:
            self.open(event.app)

        for key in additional_keys:
            bindings.add(key, filter=filter, eager=eager)(open_help)


def bind_session_help(
    bindings: KeyBindings,
    *,
    filter: FilterOrBool = True,
    entries: Sequence[CommandEntry] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    study_surface: str | None = None,
) -> SessionHelpController:
    """Construct and bind the ordinary session Help controller."""

    controller = SessionHelpController(
        entries=entries,
        app_input=app_input,
        app_output=app_output,
        study_surface=study_surface,
    )
    controller.bind(bindings, filter=filter)
    return controller
