"""Revert approval screen composed over operation-neutral History controls."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.commands.revert.review import (
    REVERT_COMMAND_FORM,
    RevertSelectionReceipt,
    append_revert_review,
    parse_revert_command_argv,
    revert_exact_command_review,
)
from memcommit.adapters.console.terminal.components.command_editor import (
    CommandDraft,
    CommandEditorControl,
)
from memcommit.adapters.console.terminal.components.command_editor.model import (
    CommandReview,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.history.controls import (
    HistoryControls,
    validate_history_screen,
)
from memcommit.adapters.console.terminal.components.history.model import (
    HISTORY_BACK,
    HistoryBackNavigation,
    HistoryDetailContent,
    HistoryDetailRenderer,
    HistoryPickerItem,
)
from memcommit.adapters.console.terminal.components.history.rendering import (
    render_history_detail,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
)


class RevertWorkbench:
    """Own staged identity, retention policy, and their editable-command coupling."""

    def __init__(
        self,
        entries: Sequence[HistoryPickerItem],
        *,
        context_name: str,
        keep_history: bool = True,
        staged_checkpoint_uid: str | None = None,
        revert_review_factory: Callable[[str, bool], CommandReview] | None = None,
        initial_details_open: bool | None = None,
        detail_renderer: HistoryDetailRenderer | None = None,
        empty_message: str | None = None,
        empty_detail: str | None = None,
        back_navigation: bool = False,
        workbench_navigation: SessionWorkbenchNavigation | None = None,
    ) -> None:
        if not isinstance(keep_history, bool):
            raise ValueError("History preservation state must be boolean.")
        if revert_review_factory is not None and not callable(revert_review_factory):
            raise ValueError("A custom Revert review must be callable.")
        if detail_renderer is not None and not callable(detail_renderer):
            raise ValueError("History detail renderer must be callable.")
        self.context_name = context_name
        self.checkpoint_uid = staged_checkpoint_uid
        self.review_factory = revert_review_factory
        self.detail_renderer = detail_renderer or render_history_detail
        self.back_navigation = back_navigation
        self.policy = HorizontalChoiceState(
            (
                HorizontalChoiceOption(
                    "DISCARD_NEWER",
                    "DISCARD NEWER",
                    "Remove newer active checkpoint files after restoration; "
                    "the recovery checkpoint retains supported recovery metadata.",
                ),
                HorizontalChoiceOption(
                    "KEEP_ALL",
                    "KEEP ALL",
                    "Preserve every currently visible checkpoint after restoration.",
                ),
            ),
            selected_uid="KEEP_ALL" if keep_history else "DISCARD_NEWER",
        )
        self.history = HistoryControls(
            entries,
            initial_details_open=initial_details_open,
            detail_renderer=self.render_detail,
            empty_message=empty_message,
            empty_detail=empty_detail,
            navigation=workbench_navigation,
            initial_uid=staged_checkpoint_uid,
            checked_uid=lambda: self.checkpoint_uid,
        )
        self.bindings = KeyBindings()
        self.command_control: CommandEditorControl | None = None
        extra_frames: tuple[Frame, ...] = ()
        surfaces = list(
            self.history.surfaces(
                activate_items=self.stage_checkpoint,
                back_items=self.back_items,
            )
        )
        # Empty history is a reading screen; it has no approval or writable field.
        if self.history.options:
            extra_frames, extra_surfaces = self.build_approval()
            surfaces.extend(extra_surfaces)
        self.frames = (*self.history.frames, *extra_frames)
        self.focus = SurfaceFocusController(surfaces)
        bind_surface_navigation(self.bindings, self.focus, back=True)
        self.history.bind_viewer_keys(self.bindings)

        @bind_case_insensitive_key(self.bindings, "q", eager=True)
        @self.bindings.add("c-c", eager=True)
        def cancel(event) -> None:
            event.app.exit(result=None)

    def review(self) -> CommandReview:
        if self.checkpoint_uid is None:
            raise ValueError("Select a checkpoint before reviewing Revert.")
        keep = self.policy.selected_uid == "KEEP_ALL"
        if self.review_factory is not None:
            return self.review_factory(self.checkpoint_uid, keep)
        return revert_exact_command_review(
            context_name=self.context_name,
            checkpoint_uid=self.checkpoint_uid,
            keep_history=keep,
        )

    def render_detail(self, entry: HistoryPickerItem) -> HistoryDetailContent:
        rendered = self.detail_renderer(entry)
        if entry.uid == self.checkpoint_uid:
            return append_revert_review(rendered, self.review())
        return rendered

    def apply_command_argv(self, argv: tuple[str, ...]) -> None:
        uid, keep = parse_revert_command_argv(
            argv,
            context_name=self.context_name,
            entries=self.history.options,
        )
        self.checkpoint_uid = uid
        self.history.preview_uid(uid)
        self.policy.choose("KEEP_ALL" if keep else "DISCARD_NEWER")
        self.history.sync_detail(anchor="start")

    def stage_checkpoint(self, event) -> SurfaceActionResult:
        entry = self.history.current_item
        if entry is None or self.command_control is None:
            return "HANDLED"
        self.checkpoint_uid = entry.uid
        self.command_control.sync_from_review(event.app)
        self.history.sync_detail(anchor="start")
        # Row activation completes staging, so the next Enter is exact approval.
        event.app.layout.focus(self.command_control.active_control)
        return "HANDLED"

    def back_items(self, event) -> SurfaceActionResult:
        event.app.exit(result=HISTORY_BACK if self.back_navigation else None)
        return "HANDLED"

    def activate_policy(self, event) -> SurfaceActionResult:
        assert self.command_control is not None
        self.command_control.sync_from_review(event.app)
        self.history.sync_detail(anchor="start")
        self.focus.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def back_policy(self, event) -> SurfaceActionResult:
        self.focus.focus_relative(event.app, -1, wrap=False)
        return "HANDLED"

    def approve(self, event) -> SurfaceActionResult:
        assert self.command_control is not None
        if (
            not self.command_control.validate_current(event.app)
            or self.checkpoint_uid is None
        ):
            return "HANDLED"
        event.app.exit(
            result=RevertSelectionReceipt(
                context_name=self.context_name,
                checkpoint_uid=self.checkpoint_uid,
                keep_history=self.policy.selected_uid == "KEEP_ALL",
            )
        )
        return "HANDLED"

    def build_approval(
        self,
    ) -> tuple[tuple[Frame, Frame], tuple[FocusSurface, FocusSurface]]:
        self.command_control = CommandEditorControl.create(
            CommandDraft(
                review=self.review,
                apply_argv=self.apply_command_argv,
                form=REVERT_COMMAND_FORM,
            ),
            action_label="PRESS ENTER TO APPLY THE REVIEWED REVERT",
            incomplete_action="FIX THE RED COMMAND BEFORE APPLY",
            input_name="revert-proposed-command",
        )
        command = self.command_control
        self.policy_control = FormattedTextControl(
            lambda: render_horizontal_choice(
                self.policy,
                title="NEWER CHECKPOINTS",
                focused=get_app().layout.has_focus(self.policy_control),
                show_description=False,
                inline_boxed=True,
            ),
            focusable=True,
            show_cursor=False,
        )
        policy_frame = Frame(
            Window(self.policy_control, height=1, dont_extend_height=True),
            title="HISTORY",
        )
        bind_focused_frame_style(
            policy_frame,
            is_focused=lambda: get_app().layout.has_focus(self.policy_control),
        )
        command_frame = build_focused_frame(
            command.body,
            title=lambda: "PROPOSED COMMAND"
            if command.valid
            else "PROPOSED COMMAND · INVALID",
            is_focused=command.is_focused,
            height=Dimension.exact(4),
        )
        # Validity is an exact-command safety signal independent of keyboard focus.
        command_frame.container.style = command.frame_style

        def move_policy(event, delta: int) -> None:
            self.policy.move(delta)
            command.sync_from_review(event.app)
            event.app.invalidate()

        @self.bindings.add("left", filter=has_focus(self.policy_control), eager=True)
        def policy_left(event) -> None:
            move_policy(event, -1)

        @self.bindings.add("right", filter=has_focus(self.policy_control), eager=True)
        def policy_right(event) -> None:
            move_policy(event, 1)

        @self.bindings.add(
            "escape", filter=has_focus(command.active_control), eager=True
        )
        def command_back(event) -> None:
            event.app.layout.focus(self.policy_control)
            event.app.invalidate()

        return (policy_frame, command_frame), (
            FocusSurface(
                "history-policy",
                self.policy_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=self.activate_policy,
                back=self.back_policy,
            ),
            FocusSurface(
                "proposed-command", command.active_control, activate=self.approve
            ),
        )

    def footer(self) -> str:
        if not self.history.options:
            close = (
                "Esc/Backspace back  q close"
                if self.back_navigation
                else "Esc/Backspace/q close"
            )
            return f" {close}  ·  0/0"
        viewer = self.history.viewer_footer()
        if viewer is not None:
            return viewer
        layout = get_app().layout
        if layout.has_focus(self.policy_control):
            return (
                " FOCUS HISTORY · ←/→ select  Enter review command  "
                f"Esc/Backspace items  Tab switch  q cancel  ·  {self.history.position}"
            )
        assert self.command_control is not None
        if layout.has_focus(self.command_control.active_control):
            return (
                " FOCUS PROPOSED COMMAND · Enter apply reviewed Revert  "
                f"Esc history  Tab switch  q cancel  ·  {self.history.position}"
            )
        close = (
            "Esc/Backspace back  q cancel"
            if self.back_navigation
            else "Esc/Backspace/q cancel"
        )
        return (
            " FOCUS ITEMS · ↑/↓ move  Enter stage UID and review command  "
            f"Tab switch  {close}  ·  {self.history.position}"
        )


def choose_revert_history(
    entries: Sequence[HistoryPickerItem],
    *,
    context_name: str,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    initial_details_open: bool | None = None,
    detail_renderer: HistoryDetailRenderer | None = None,
    empty_message: str | None = None,
    empty_detail: str | None = None,
    back_navigation: bool = False,
    title: str | None = None,
    workbench_navigation: SessionWorkbenchNavigation | None = None,
    keep_history: bool = True,
    staged_checkpoint_uid: str | None = None,
    revert_review_factory: Callable[[str, bool], CommandReview] | None = None,
) -> RevertSelectionReceipt | HistoryBackNavigation | None:
    """Return a reviewed local selection without performing the restoration."""

    validate_history_screen(context_name, title=title, require_tty=require_tty)
    workbench = RevertWorkbench(
        entries,
        context_name=context_name,
        initial_details_open=initial_details_open,
        detail_renderer=detail_renderer,
        empty_message=empty_message,
        empty_detail=empty_detail,
        back_navigation=back_navigation,
        workbench_navigation=workbench_navigation,
        keep_history=keep_history,
        staged_checkpoint_uid=staged_checkpoint_uid,
        revert_review_factory=revert_review_factory,
    )
    header = Window(
        FormattedTextControl(
            f" {display_escape_text(title or 'REVERT')} · {display_escape_text(context_name)}"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(workbench.footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    app: Application[RevertSelectionReceipt | HistoryBackNavigation | None] = (
        Application(
            layout=Layout(
                build_tui_frame(
                    *(TuiRegion(frame) for frame in (header, *workbench.frames, footer))
                ),
                focused_element=(
                    workbench.command_control.active_control
                    if staged_checkpoint_uid is not None
                    and workbench.command_control is not None
                    else workbench.history.list_control
                ),
            ),
            key_bindings=workbench.bindings,
            full_screen=True,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        )
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None
