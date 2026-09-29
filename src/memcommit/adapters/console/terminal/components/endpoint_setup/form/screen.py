"""Compose typed endpoint editors and one validated setup action."""

from __future__ import annotations

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.layout import (
    Dimension,
    Float,
    FloatContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.components.endpoint_setup.memory_focus import (
    MemoryProjectionLoader,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.spec import (
    EndpointSetupSpec,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.values import (
    DraftValidator,
    EndpointSetupDraft,
)
from memcommit.adapters.console.terminal.components.focus.controller import (
    SurfaceActionResult,
    SurfaceMoveResult,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)

from memcommit.adapters.console.terminal.components.action import build_action_control

from .context_browser import ContextBrowser
from .endpoint_editor import EndpointEditor
from .form_navigation import FormNavigation
from .memory_picker import MemoryPicker


class _EndpointSetupForm:
    """Compose endpoint editors and panels into one process-local setup form."""

    def __init__(
        self,
        spec: EndpointSetupSpec,
        *,
        memory_loader: MemoryProjectionLoader | None,
        validate_draft: DraftValidator | None,
        app_input: Input | None,
        app_output: Output | None,
    ) -> None:
        self.spec = spec
        self.status = ""
        self.show_mode = len(spec.modes) > 1
        self.mode_state = HorizontalChoiceState(
            tuple(
                HorizontalChoiceOption(mode.uid, mode.label, mode.description)
                for mode in spec.modes
            ),
            selected_uid=spec.initial_mode_uid,
        )
        self.editors = {
            role.uid: EndpointEditor(
                spec,
                role,
                selected_mode_uid=self.selected_mode_uid,
                memory_loader=memory_loader,
                on_input_changed=self.input_changed,
            )
            for role in spec.roles
        }
        self.validate_draft = validate_draft
        self.mode_control = FormattedTextControl(
            self.render_mode, focusable=True, show_cursor=False
        )
        self.action_control = build_action_control(spec.action_label)
        self.memory_picker = MemoryPicker(self.editors, set_status=self.set_status)
        self.browser = ContextBrowser(
            self.editors,
            set_status=self.set_status,
            before_open=self.memory_picker.reset,
            on_context_selected=self.refresh_new_name_suggestions,
        )
        root = self.build_layout()
        self.navigation = FormNavigation(
            spec,
            self.editors,
            mode_state=self.mode_state,
            mode_control=self.mode_control,
            action_control=self.action_control,
            browser=self.browser,
            memory_picker=self.memory_picker,
            move_mode=self.move_mode,
            refresh_new_name_suggestions=self.refresh_new_name_suggestions,
            finish=self.finish,
            get_status=lambda: self.status,
            set_status=self.set_status,
        )
        self.app: Application[EndpointSetupDraft | None] = Application(
            layout=Layout(
                root,
                focused_element=self.navigation.initial_control(),
            ),
            key_bindings=self.navigation.bindings,
            full_screen=False,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            mouse_support=False,
            style=merge_styles([MEMCOMMIT_TUI_STYLE]),
        )

    def set_status(self, value: str) -> None:
        self.status = value

    def input_changed(self, role_uid: str) -> None:
        self.memory_picker.reset_for(role_uid)

    def clear_details(self) -> None:
        self.memory_picker.reset()
        self.browser.reset()
        self.status = ""

    def selected_mode_uid(self) -> str:
        return self.mode_state.selected_uid

    def refresh_new_name_suggestions(self) -> None:
        """Refresh only untouched operation-owned new-name drafts."""

        values = {
            uid: editor.input.text.strip() for uid, editor in self.editors.items()
        }
        for editor in self.editors.values():
            editor.refresh_name_suggestion(values)

    def render_mode(self) -> StyleAndTextTuples:
        return render_horizontal_choice(
            self.mode_state,
            title=self.spec.mode_label,
            focused=get_app().layout.has_focus(self.mode_control),
            inline_boxed=True,
        )

    def move_mode(self, _event, delta: int) -> SurfaceMoveResult:
        changed = self.mode_state.move(delta)
        for editor in self.editors.values():
            editor.reconcile_mode()
        self.clear_details()
        return "MOVED" if changed else "BOUNDARY"

    def finish(self, event) -> SurfaceActionResult:
        try:
            mode_uid = self.mode_state.selected_uid
            draft = EndpointSetupDraft(
                mode_uid,
                tuple(
                    self.editors[uid].collect_value()
                    for uid in self.spec.active_role_uids(mode_uid)
                ),
            )
            message = (
                self.validate_draft(draft) if self.validate_draft is not None else None
            )
            if message:
                raise ValueError(message)
        except (OSError, TypeError, ValueError) as error:
            self.status = str(error)
            return "HANDLED"
        event.app.exit(result=draft)
        return "HANDLED"

    def build_layout(self) -> FloatContainer:
        mode_line = Window(
            self.mode_control,
            height=Dimension.exact(1),
            dont_extend_height=True,
            wrap_lines=False,
        )

        label_width = self.role_label_width()

        role_rows = [
            row
            for editor in self.editors.values()
            for row in editor.build_rows(label_width)
        ]
        action_line = Window(
            self.action_control,
            height=Dimension.exact(1),
            dont_extend_height=True,
            wrap_lines=False,
        )

        catalog_detail_containers = self.browser.build_details()

        memory_detail_container = self.memory_picker.build_detail()

        header = Window(
            FormattedTextControl(
                f" {safe_terminal_text(self.spec.title)} · {safe_terminal_text(self.spec.subtitle)}"
            ),
            height=Dimension.exact(1),
            dont_extend_height=True,
        )

        footer_control = FormattedTextControl()

        footer = Window(
            footer_control,
            height=Dimension.exact(1),
            dont_extend_height=True,
        )

        body = HSplit(
            [
                header,
                *([mode_line] if self.show_mode else []),
                *role_rows,
                action_line,
                *catalog_detail_containers,
                memory_detail_container,
                footer,
            ]
        )

        root = FloatContainer(
            content=body,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(
                        max_height=8,
                        scroll_offset=1,
                        display_arrows=True,
                    ),
                )
            ],
        )

        footer_control.text = lambda: self.navigation.render_footer()
        return root

    def role_label_width(self) -> int:
        typed_source_roles = tuple(
            role for role in self.spec.roles if role.memory.allow_inline
        )
        label_width = max(
            7,
            max(
                (
                    max(
                        (
                            len(f"{role.uid} · SOURCE · {suffix}")
                            for suffix in ("CONTEXT", "MEMORY OWNER", "INLINE MEMORY")
                        )
                    )
                    + 3
                    for role in typed_source_roles
                ),
                default=0,
            ),
            max(
                (
                    len(self.spec.role_label(mode.uid, role.uid)) + 3
                    for mode in self.spec.modes
                    for role in self.spec.roles
                    if role.uid in self.spec.active_role_uids(mode.uid)
                )
            ),
        )
        return label_width


def run_endpoint_setup_form(
    spec: EndpointSetupSpec,
    *,
    memory_loader: MemoryProjectionLoader | None,
    validate_draft: DraftValidator | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> EndpointSetupDraft | None:
    """Collect the same typed draft through an input-first form."""

    if spec.screen_layout != "FORM":
        raise ValueError("Endpoint Setup Form requires FORM layout.")
    if require_tty:
        require_interactive_terminal(
            spec.title,
            snapshot_hint="Pass explicit Context operands outside a terminal.",
        )
    memory_roles = tuple(role for role in spec.roles if role.memory.enabled)
    if memory_roles and memory_loader is None:
        raise ValueError("Endpoint Memory focus requires a projection loader.")

    return _EndpointSetupForm(
        spec,
        memory_loader=memory_loader,
        validate_draft=validate_draft,
        app_input=app_input,
        app_output=app_output,
    ).app.run()
