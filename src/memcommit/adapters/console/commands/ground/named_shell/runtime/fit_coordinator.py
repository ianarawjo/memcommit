"""Background Fit coordination for the named Ground workbench."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import Application

from memcommit.adapters.console.commands.fit.presentation import fit_fraction, fit_mark
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.fit.application import FitResult
from memcommit.application.operations.fit.ground_report import FitReport
from memcommit.application.operations.fit.store import GroundFitReceipt
from memcommit.application.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundSession,
    is_bound_ground_schema,
)

from memcommit.adapters.console.commands.ground.named_shell.proposal import (
    NamedGroundFitLookup,
    NamedGroundFitRunner,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.state import (
    NamedGroundShellState,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.workbench_view import (
    NamedGroundWorkbenchView,
)


class NamedGroundFitCoordinator:
    """Serialize Fit work and publish only complete receipt-boundary results."""

    def __init__(
        self,
        state: NamedGroundShellState,
        *,
        run_fit: NamedGroundFitRunner | None,
        lookup_fit: NamedGroundFitLookup | None,
    ) -> None:
        self.state = state
        self.run_fit = run_fit
        self.lookup_fit = lookup_fit
        self.view: NamedGroundWorkbenchView | None = None
        self.refresh_current: Callable[..., bool] | None = None

    def attach(
        self,
        view: NamedGroundWorkbenchView,
        *,
        refresh_current: Callable[..., bool],
    ) -> None:
        self.view = view
        self.refresh_current = refresh_current

    def require_view(self) -> NamedGroundWorkbenchView:
        if self.view is None:
            raise RuntimeError("Named Ground Fit coordinator is not attached.")
        return self.view

    @staticmethod
    def auto_fit_is_executable(active: GroundSession) -> bool:
        """Avoid a provider turn until the saved Ground has both Fit sides."""

        if not is_bound_ground_schema(active.schema_version):
            return False
        has_rule = any(
            item.kind == "RULE" and item.status in {"PROPOSED", "ACCEPTED"}
            for item in active.items
        )
        has_example = any(
            item.kind == "CASE"
            and item.status in {"PROPOSED", "ACCEPTED"}
            and item.disposition == "INCLUDE"
            and (
                bool(item.proposition.strip())
                if active.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                else bool(item.expected.strip())
            )
            for item in active.items
        )
        return has_rule and has_example

    def fit_receipt_needs_refresh(self) -> bool:
        receipt = self.state.fit_receipt
        if receipt is None or not receipt.current:
            return True
        # A legacy Rule–Example-only receipt is readable, but it is not the
        # complete Context/vertical/peer detection promised by AUTO-FIT.
        return receipt.report.coherence is None

    def schedule_auto_fit(self, app: Application) -> None:
        state = self.state
        if (
            not state.auto_fit_enabled
            or not self.auto_fit_is_executable(state.current)
            or not self.fit_receipt_needs_refresh()
        ):
            state.auto_fit_pending = False
            return
        if state.fit_turn.busy:
            # A reviewed mutation may land while an earlier frozen Fit is in
            # flight. Finish that receipt boundary, then fit the latest saved
            # revision once; never publish a partial older result.
            state.auto_fit_pending = True
            return
        state.auto_fit_pending = False
        self.start(app, automatic=True)

    def start(self, app: Application, *, automatic: bool) -> None:
        state = self.state
        view = self.require_view()
        if self.run_fit is None:
            state.status_message = "Fit is unavailable in this Ground adapter."
            app.invalidate()
            return
        if self.refresh_current is None:
            raise RuntimeError("Named Ground Fit refresh callback is not attached.")

        try:
            self.refresh_current(announce=True)
        except Exception as error:
            state.status_message = (
                "FIT FAILED · NOTHING APPLIED · "
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
            app.invalidate()
            return

        frozen_session = state.current

        def on_success(report: FitReport) -> None:
            if not isinstance(report, FitReport):
                raise ValueError("Ground Fit runner returned an invalid report.")
            if self.lookup_fit is None:
                state.fit_receipt = GroundFitReceipt(report=report, current=True)
            else:
                state.fit_receipt = self.lookup_fit(state.current)
            receipt = state.fit_receipt
            result = FitResult(
                report,
                current=receipt.current if receipt is not None else True,
            )
            state.status_message = f"{fit_mark(result)} {fit_fraction(result)}"
            state.mark_pane_updates("GOAL", "CONTEXTS", "RULES", "MEMORIES")
            view.sync_panes()

        def on_error(error: Exception) -> None:
            state.status_message = (
                "FIT FAILED · NOTHING APPLIED · "
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )

        def on_idle() -> None:
            if state.auto_fit_pending:
                state.auto_fit_pending = False
                self.schedule_auto_fit(view.require_application())
                return
            if not automatic:
                view.require_application().layout.focus(view.cases_pane.text_area)

        def on_close() -> None:
            view.require_application().exit(
                result=state.result(state.deferred_exit_status)
            )

        state.status_message = (
            "AUTO-FIT" if automatic else "FIT"
        ) + " RUNNING · Ground and Contexts unchanged"
        view.sync_memories_pane(align_selection=True)
        started = state.fit_turn.start(
            app,
            work=lambda: self.run_fit(frozen_session),
            on_success=on_success,
            on_error=on_error,
            on_idle=on_idle,
            on_close=on_close,
        )
        if not started:
            state.status_message = (
                "FIT ALREADY RUNNING · wait for the current receipt boundary"
            )
        app.invalidate()
