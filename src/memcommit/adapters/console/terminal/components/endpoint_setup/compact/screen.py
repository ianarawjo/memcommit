"""Compose endpoint editors, command synchronization, and screen navigation."""

from __future__ import annotations

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    Float,
    FloatContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.name_draft import (
    infer_context_parent,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.command_binding import (
    DraftValidator,
    EndpointCommandBinding,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.memory_focus import (
    MemoryProjectionLoader,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupDraft,
    EndpointSetupSpec,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import build_focused_frame
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
    focused_control_style,
)

from .endpoint_editor import EndpointEditor
from .command_sync import EndpointCommandSync


class _CompactEndpointScreen:
    """Own screen-wide focus and transient panes; editors own endpoint values."""

    def __init__(
        self,
        spec: EndpointSetupSpec,
        *,
        memory_loader: MemoryProjectionLoader | None,
        validate_draft: DraftValidator | None,
        command_editor: EndpointCommandBinding | None,
        app_input: Input | None,
        app_output: Output | None,
    ) -> None:
        self.spec = spec
        self.status = ""
        self.memory_detail: str | None = None
        self.catalog_detail: str | None = None
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
        self.command_sync = EndpointCommandSync(
            spec,
            self.editors,
            self.mode_state,
            binding=command_editor,
            validate_draft=validate_draft,
            on_applied=self.clear_details,
        )
        self.command_control = self.command_sync.control
        self.mode_control = FormattedTextControl(
            self.render_mode, focusable=True, show_cursor=False
        )
        self.action_control = FormattedTextControl(
            self.render_action, focusable=True, show_cursor=False
        )
        root = self.build_layout()
        self.bindings = KeyBindings()
        self.surfaces = SurfaceFocusController(self.visible_surfaces)
        bind_surface_navigation(self.bindings, self.surfaces)
        self.bind_keys()
        self.app: Application[EndpointSetupDraft | None] = Application(
            layout=Layout(
                root,
                focused_element=self.initial_control(),
            ),
            key_bindings=self.bindings,
            full_screen=False,
            erase_when_done=True,
            input=app_input,
            output=app_output,
            mouse_support=False,
            style=merge_styles([MEMCOMMIT_TUI_STYLE]),
            before_render=(lambda _app: self.command_control.sync_if_review_changed())
            if self.command_control is not None
            else None,
        )

    def input_changed(self, role_uid: str) -> None:
        if self.memory_detail == role_uid:
            self.memory_detail = None

    def clear_details(self) -> None:
        self.memory_detail = None
        self.catalog_detail = None
        self.status = ""

    def focused_control_role(self, attribute: str) -> str | None:
        return next(
            (
                uid
                for uid, editor in self.editors.items()
                if (control := getattr(editor, attribute)) is not None
                and get_app().layout.has_focus(control)
            ),
            None,
        )

    def selected_mode_uid(self) -> str:
        return self.mode_state.selected_uid

    def refresh_new_name_suggestions(self) -> None:
        """Refresh only untouched operation-owned new-name drafts."""

        values = {
            uid: editor.input.text.strip() for uid, editor in self.editors.items()
        }
        for role in self.spec.roles:
            if role.new_name_suggester is None:
                continue
            candidate = role.new_name_suggester(values)
            draft = self.editors[role.uid].new_name_draft
            parent = (
                infer_context_parent(
                    candidate,
                    role.names,
                    fallback=role.selected_name,
                )
                if role.new_parent_locator
                else None
            )
            inherited = draft.inherit_suggestion(
                candidate,
                parent_name=parent,
            )
            if self.editors[role.uid].input.text != inherited:
                self.editors[role.uid].set_role_text(inherited)

    def render_mode(self) -> StyleAndTextTuples:
        return render_horizontal_choice(
            self.mode_state,
            title="MODE",
            focused=get_app().layout.has_focus(self.mode_control),
            inline_boxed=True,
        )

    def render_action(self) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(self.action_control)
        return [
            (
                focused_control_style(focused=focused, selected=focused),
                f"{('›' if focused else ' ')} [ {safe_terminal_text(self.spec.action_label)} ]",
            )
        ]

    def render_memory_detail(self) -> StyleAndTextTuples:
        role_uid = self.memory_detail
        if role_uid is None:
            return []
        context_name = self.editors[role_uid].selected_memory_context()
        fragments: StyleAndTextTuples = [
            (
                "class:report-neutral",
                ("  " if self.editors[role_uid].role.memory_required else "  MEMORY · ")
                + safe_terminal_text(
                    self.spec.role_label(self.selected_mode_uid(), role_uid)
                )
                + f" · {display_escape_text(context_name)}\n",
            )
        ]
        fragments.extend(
            self.editors[role_uid].memory_focus.render(
                focused=True, include_descendants=False
            )
        )
        return fragments

    def move_mode(self, _event, delta: int) -> SurfaceMoveResult:
        changed = self.mode_state.move(delta)
        for editor in self.editors.values():
            if (
                editor.memory_focus is not None
                and not editor.role_allows_memory_focus()
            ):
                editor.memory_focus.clear()
        self.clear_details()
        return "MOVED" if changed else "BOUNDARY"

    def choose_mode(self, _event) -> SurfaceActionResult:
        self.status = ""
        return "HANDLED"

    def move_source_type_choice(self, role_uid: str, delta: int) -> SurfaceMoveResult:
        editor = self.editors[role_uid]
        state = editor.source_type
        changed = state.move(delta)
        if changed:
            editor.memory_focus.required = state.selected_uid == "STORED_MEMORY"
            self.memory_detail = None
            self.catalog_detail = None
            self.status = ""
        return "MOVED" if changed else "BOUNDARY"

    def move_source_type_row(
        self, event, role_uid: str, delta: int
    ) -> SurfaceMoveResult:
        if delta > 0:
            event.app.layout.focus(self.editors[role_uid].role_primary_input())
            return "CONSUMED"
        if self.show_mode:
            event.app.layout.focus(self.mode_control)
            return "CONSUMED"
        return "BOUNDARY"

    def choose_source_type(self, _event, _role_uid: str) -> SurfaceActionResult:
        self.status = ""
        return "HANDLED"

    def adjacent_role_uid(self, role_uid: str, delta: int) -> str | None:
        """Return the primary field on the adjacent persistent form row."""

        active_role_uids = self.spec.active_role_uids(self.selected_mode_uid())
        index = active_role_uids.index(role_uid)
        candidate = index + delta
        return (
            active_role_uids[candidate]
            if 0 <= candidate < len(active_role_uids)
            else None
        )

    def move_role_row(self, event, role_uid: str, delta: int) -> SurfaceMoveResult:
        """Move vertically by form row, not across controls drawn on one row.

        Left/Right own non-editor peers and Tab keeps the exhaustive fallback.
        Mapping Up/Down to that same sequence made a visually vertical form
        move sideways and left the on-demand Memory list as an arrow-key trap.
        """
        editor = self.editors[role_uid]

        self.memory_detail = None
        self.status = ""
        adjacent = self.adjacent_role_uid(role_uid, delta)
        if adjacent is not None:
            event.app.layout.focus(self.editors[adjacent].role_primary_input())
            return "CONSUMED"
        if delta < 0 and editor.source_type_visible():
            event.app.layout.focus(editor.source_type_control)
        elif delta < 0 and self.show_mode:
            event.app.layout.focus(self.mode_control)
        elif delta > 0:
            if self.command_control is not None:
                self.command_control.sync_if_review_changed()
            event.app.layout.focus(
                self.command_control.active_control
                if self.command_control is not None
                else self.action_control
            )
        else:
            return "BOUNDARY"
        return "CONSUMED"

    def move_role(self, event, role_uid: str, delta: int) -> SurfaceMoveResult:
        buffer = self.editors[role_uid].role_primary_input().buffer
        if buffer.complete_state is None:
            return self.move_role_row(event, role_uid, delta)
        if delta > 0:
            buffer.complete_next()
        else:
            buffer.complete_previous()
        return "CONSUMED"

    def choose_role(self, event, role_uid: str) -> SurfaceActionResult:
        editor = self.editors[role_uid]
        buffer = editor.role_primary_input().buffer
        if editor.effective_source_type() == "INLINE_MEMORY":
            if not buffer.text.strip():
                self.status = f"{self.spec.role_label(self.selected_mode_uid(), role_uid)} needs inline Memory text."
                return "HANDLED"
            self.status = ""
            self.surfaces.focus_relative(event.app, 1, wrap=False)
            return "HANDLED"
        if (
            buffer.complete_state is not None
            and buffer.complete_state.current_completion is not None
        ):
            buffer.apply_completion(buffer.complete_state.current_completion)
            self.status = ""
            return "HANDLED"
        try:
            if editor.role.memory_required:
                editor.synchronize_required_memory_input()
            else:
                editor.resolve_role()
        except (OSError, TypeError, ValueError) as error:
            self.status = str(error)
        else:
            self.status = ""
            try:
                self.refresh_new_name_suggestions()
            except (TypeError, ValueError) as error:
                self.status = str(error)
                return "HANDLED"
            self.surfaces.focus_relative(event.app, 1, wrap=False)
            if editor.browse_control is not None:
                # Enter confirms direct input and advances to the next semantic
                # control; Tab remains the explicit path into adjacent Browse.
                self.surfaces.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def open_catalog(self, event, role_uid: str) -> bool:
        editor = self.editors[role_uid]
        selector = editor.selector
        if selector is None:
            self.status = f"{self.spec.role_label(self.selected_mode_uid(), role_uid)} has no eligible existing Context; type one new exact name."
            return False
        buffer = editor.input.buffer
        if buffer.complete_state is not None:
            buffer.cancel_completion()
        role = editor.role
        candidate = (
            editor.new_name_draft.parent_name
            if role.new_parent_locator
            else editor.selected_memory_context()
        )
        selected = (
            candidate if candidate in selector.selectable else selector.view.names[0]
        )
        selector.select_name(selected)
        self.memory_detail = None
        self.catalog_detail = role_uid
        self.status = ""
        event.app.layout.focus(selector.control)
        return True

    def move_catalog(self, _event, role_uid: str, delta: int) -> SurfaceMoveResult:
        selector = self.editors[role_uid].selector
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def close_catalog(self, event, *, choose: bool) -> SurfaceActionResult:
        role_uid = self.catalog_detail
        if role_uid is None:
            return "IGNORED"
        if choose:
            selector = self.editors[role_uid].selector
            selector.choose_cursor()
            selected_name = selector.tree.selected_name
            role = self.editors[role_uid].role
            if role.new_parent_locator:
                draft = self.editors[role_uid].new_name_draft
                candidate = draft.choose_parent(selected_name)
                self.editors[role_uid].set_role_text(candidate)
                self.status = (
                    "Parent selected; edited exact name preserved."
                    if draft.edited
                    else ""
                )
            else:
                if role.memory_required:
                    self.editors[role_uid].required_memory_owner = selected_name
                self.editors[role_uid].set_role_text(selected_name)
                self.refresh_new_name_suggestions()
        self.catalog_detail = None
        if not self.editors[role_uid].role.new_parent_locator:
            self.status = ""
        event.app.layout.focus(self.editors[role_uid].browse_control)
        return "HANDLED"

    def choose_catalog(self, event, _role_uid: str) -> SurfaceActionResult:
        return self.close_catalog(event, choose=True)

    def choose_browse(self, event, role_uid: str) -> SurfaceActionResult:
        self.open_catalog(event, role_uid)
        return "HANDLED"

    def prepare_browse(self, role_uid: str) -> None:
        self.memory_detail = None
        buffer = self.editors[role_uid].input.buffer
        if buffer.complete_state is not None:
            buffer.cancel_completion()

    def close_memory_detail(self) -> None:
        self.memory_detail = None

    def move_role_peer(self, event, role_uid: str, control: object, delta: int) -> bool:
        """Move spatially between non-editor controls on one endpoint row.

        Exact-name inputs hand off here only after their own caret reaches the
        right edge. Mode and transient Context trees retain their horizontal
        semantics.
        """
        editor = self.editors[role_uid]

        controls = editor.role_peer_controls()
        index = controls.index(control)
        candidate = index + delta
        if not 0 <= candidate < len(controls):
            self.status = (
                "No more controls on this row · use Up/Down for endpoint rows."
            )
            return False
        self.memory_detail = None
        self.status = ""
        target = controls[candidate]
        if target is editor.browse_control:
            self.prepare_browse(role_uid)
        event.app.layout.focus(target)
        return True

    def move_reach(self, event, role_uid: str, delta: int) -> SurfaceMoveResult:
        return self.move_role_row(event, role_uid, delta)

    def set_reach(self, role_uid: str, *, include_descendants: bool) -> None:
        editor = self.editors[role_uid]
        editor.reach.move(1 if include_descendants else -1)
        if editor.reach is not None and editor.reach.include_descendants:
            cleared = editor.memory_focus
            if cleared is not None and cleared.clear():
                self.status = f"{self.spec.role_label(self.selected_mode_uid(), role_uid)} Memory focus cleared for descendants."
            else:
                self.status = ""
            if self.memory_detail == role_uid:
                self.memory_detail = None
        else:
            self.status = ""

    def choose_reach(self, _event, role_uid: str) -> SurfaceActionResult:
        self.set_reach(
            role_uid,
            include_descendants=not self.editors[role_uid].reach.include_descendants,
        )
        return "HANDLED"

    def open_memory(self, role_uid: str) -> bool:
        editor = self.editors[role_uid]
        if editor.reach is not None and editor.reach.include_descendants:
            editor.memory_focus.clear()
            self.status = "Focused Memory requires THIS CONTEXT ONLY."
            return False
        try:
            if editor.role.memory_required:
                context_name, _selected_memory = self.editors[
                    role_uid
                ].synchronize_required_memory_input()
                create = False
            else:
                context_name, create = editor.resolve_role()
            if create:
                raise ValueError("A new Context cannot select an existing Memory.")
            editor.memory_focus.prepare_context(context_name)
            editor.memory_focus.state()
        except (OSError, TypeError, ValueError) as error:
            self.status = str(error)
            return False
        self.memory_detail = role_uid
        self.status = ""
        return True

    def move_memory(self, event, role_uid: str, delta: int) -> SurfaceMoveResult:
        if self.memory_detail != role_uid:
            return self.move_role_row(event, role_uid, delta)
        changed = self.editors[role_uid].memory_focus.move(delta)
        self.status = ""
        if changed:
            return "CONSUMED"
        # Once the transient list reaches an edge, the same arrow closes it
        # and continues along the compact form's vertical row topology.
        self.memory_detail = None
        return self.move_role_row(event, role_uid, delta)

    def choose_memory(self, _event, role_uid: str) -> SurfaceActionResult:
        editor = self.editors[role_uid]
        if self.memory_detail != role_uid:
            self.open_memory(role_uid)
            return "HANDLED"
        if editor.role.memory_preview_only:
            self.status = "Memory rows are read-only evidence; the whole Context remains selected."
            return "HANDLED"
        selected = editor.memory_focus.choose()
        if editor.role.memory_required:
            if selected is None:
                raise RuntimeError("A required Memory chooser returned no Memory.")
            owner = editor.required_memory_owner
            editor.set_role_text(f"{owner}:{selected}")
            editor.memory_focus.select_exact(owner, selected)
        self.memory_detail = None
        self.status = (
            f"{self.spec.role_label(self.selected_mode_uid(), role_uid)} uses Memory {selected[:8]}."
            if selected is not None
            else f"{self.spec.role_label(self.selected_mode_uid(), role_uid)} uses the whole Context."
        )
        return "HANDLED"

    def finish(self, event) -> SurfaceActionResult:
        try:
            if self.command_control is not None and (
                not self.command_control.validate_current(event.app)
            ):
                self.status = self.command_control.draft.error
                return "HANDLED"
            draft = self.command_sync.checked_draft()
        except (OSError, TypeError, ValueError) as error:
            self.status = str(error)
            return "HANDLED"
        event.app.exit(result=draft)
        return "HANDLED"

    def move_action(self, event, delta: int) -> SurfaceMoveResult:
        if delta > 0:
            return "BOUNDARY"
        active_role_uids = self.spec.active_role_uids(self.selected_mode_uid())
        event.app.layout.focus(self.editors[active_role_uids[-1]].role_primary_input())
        self.status = ""
        return "CONSUMED"

    def visible_surfaces(self) -> tuple[FocusSurface, ...]:
        catalog_role_uid = self.catalog_detail
        if catalog_role_uid is not None:
            selector = self.editors[catalog_role_uid].selector
            return (
                FocusSurface(
                    f"CATALOG:{catalog_role_uid}",
                    selector.control,
                    move_vertical=lambda event,
                    delta,
                    uid=catalog_role_uid: self.move_catalog(event, uid, delta),
                    activate=lambda event, uid=catalog_role_uid: self.choose_catalog(
                        event, uid
                    ),
                ),
            )
        values: list[FocusSurface] = []
        if self.show_mode:
            values.append(
                FocusSurface(
                    "MODE",
                    self.mode_control,
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                    activate=self.choose_mode,
                    on_focus=self.close_memory_detail,
                )
            )
        for role_uid in self.spec.active_role_uids(self.selected_mode_uid()):
            if self.editors[role_uid].source_type_visible():
                values.append(
                    FocusSurface(
                        f"SOURCE_TYPE:{role_uid}",
                        self.editors[role_uid].source_type_control,
                        move_vertical=lambda event,
                        delta,
                        uid=role_uid: self.move_source_type_row(event, uid, delta),
                        activate=lambda event, uid=role_uid: self.choose_source_type(
                            event, uid
                        ),
                        on_focus=self.close_memory_detail,
                    )
                )
            values.append(
                FocusSurface(
                    f"ROLE:{role_uid}",
                    self.editors[role_uid].role_primary_input(),
                    move_vertical=lambda event, delta, uid=role_uid: self.move_role(
                        event, uid, delta
                    ),
                    activate=lambda event, uid=role_uid: self.choose_role(event, uid),
                    on_focus=self.close_memory_detail,
                )
            )
            if (
                self.editors[role_uid].browse_control is not None
                and self.editors[role_uid].role_uses_context_name()
            ):
                values.append(
                    FocusSurface(
                        f"BROWSE:{role_uid}",
                        self.editors[role_uid].browse_control,
                        move_vertical=lambda event,
                        delta,
                        uid=role_uid: self.move_role_row(event, uid, delta),
                        activate=lambda event, uid=role_uid: self.choose_browse(
                            event, uid
                        ),
                        on_focus=lambda uid=role_uid: self.prepare_browse(uid),
                    )
                )
            if (
                self.editors[role_uid].reach_control is not None
                and self.editors[role_uid].role_allows_descendants()
                and self.editors[role_uid].role_uses_context_range()
            ):
                values.append(
                    FocusSurface(
                        f"RANGE:{role_uid}",
                        self.editors[role_uid].reach_control,
                        move_vertical=lambda event,
                        delta,
                        uid=role_uid: self.move_reach(event, uid, delta),
                        activate=lambda event, uid=role_uid: self.choose_reach(
                            event, uid
                        ),
                        on_focus=self.close_memory_detail,
                    )
                )
            if (
                self.editors[role_uid].memory_control is not None
                and self.editors[role_uid].role_allows_memory_focus()
                and (
                    self.editors[role_uid].source_type is None
                    or self.editors[role_uid].role_uses_stored_memory()
                )
            ):
                values.append(
                    FocusSurface(
                        f"MEMORY:{role_uid}",
                        self.editors[role_uid].memory_control,
                        move_vertical=lambda event,
                        delta,
                        uid=role_uid: self.move_memory(event, uid, delta),
                        activate=lambda event, uid=role_uid: self.choose_memory(
                            event, uid
                        ),
                    )
                )
        values.append(
            FocusSurface(
                "COMMAND" if self.command_control is not None else "CONTINUE",
                self.command_control.active_control
                if self.command_control is not None
                else self.action_control,
                move_vertical=self.move_action,
                activate=self.finish,
                on_focus=self.command_control.sync_if_review_changed
                if self.command_control is not None
                else self.close_memory_detail,
            )
        )
        return tuple(values)

    def _mode_left(self, event) -> None:
        self.move_mode(event, -1)
        event.app.invalidate()

    def _mode_right(self, event) -> None:
        self.move_mode(event, 1)
        event.app.invalidate()

    def _source_type_left(self, event) -> None:
        role_uid = self.focused_control_role("source_type_control")
        if role_uid is not None:
            self.move_source_type_choice(role_uid, -1)
        event.app.invalidate()

    def _source_type_right(self, event) -> None:
        role_uid = self.focused_control_role("source_type_control")
        if role_uid is not None:
            self.move_source_type_choice(role_uid, 1)
        event.app.invalidate()

    def focused_reach_role(self) -> str | None:
        return self.focused_control_role("reach_control")

    def _previous_reach_peer(self, event) -> None:
        role_uid = self.focused_reach_role()
        if role_uid is not None:
            self.move_role_peer(
                event, role_uid, self.editors[role_uid].reach_control, -1
            )
        event.app.invalidate()

    def _next_reach_peer(self, event) -> None:
        role_uid = self.focused_reach_role()
        if role_uid is not None:
            self.move_role_peer(
                event, role_uid, self.editors[role_uid].reach_control, 1
            )
        event.app.invalidate()

    def _toggle_reach(self, event) -> None:
        role_uid = self.focused_reach_role()
        if role_uid is not None:
            self.choose_reach(event, role_uid)
        event.app.invalidate()

    def _next_input_position_or_peer(self, event) -> None:
        """Keep editing inside the field, then cross its visible right edge.

        The exact Context name must retain ordinary caret semantics, but a
        Right press that cannot move the caret should not become a dead key on
        a row whose Browse/range/Memory controls are visibly to its right.
        """

        buffer = event.current_buffer
        if buffer.cursor_position < len(buffer.text):
            buffer.cursor_position += 1
        else:
            role_uid = self.focused_control_role("input") or self.focused_control_role(
                "inline_input"
            )
            if role_uid is not None:
                self.move_role_peer(
                    event, role_uid, self.editors[role_uid].role_primary_input(), 1
                )
        event.app.invalidate()

    def _previous_browse_peer(self, event) -> None:
        role_uid = self.focused_control_role("browse_control")
        if role_uid is not None:
            self.move_role_peer(
                event, role_uid, self.editors[role_uid].browse_control, -1
            )
        event.app.invalidate()

    def _next_browse_peer(self, event) -> None:
        role_uid = self.focused_control_role("browse_control")
        if role_uid is not None:
            self.move_role_peer(
                event, role_uid, self.editors[role_uid].browse_control, 1
            )
        event.app.invalidate()

    def _previous_memory_peer(self, event) -> None:
        role_uid = self.focused_control_role("memory_control")
        if role_uid is None:
            return
        if self.memory_detail == role_uid:
            self.memory_detail = None
            self.status = ""
        else:
            self.move_role_peer(
                event, role_uid, self.editors[role_uid].memory_control, -1
            )
        event.app.invalidate()

    def _next_memory_peer(self, event) -> None:
        role_uid = self.focused_control_role("memory_control")
        if role_uid is None:
            return
        if self.memory_detail == role_uid:
            self.status = "Memory choices use Up/Down · Left closes details."
        else:
            self.move_role_peer(
                event, role_uid, self.editors[role_uid].memory_control, 1
            )
        event.app.invalidate()

    def focused_input_has_completions(self) -> bool:
        return any(
            get_app().layout.has_focus(editor.input)
            and editor.input.buffer.complete_state is not None
            for editor in self.editors.values()
        )

    def _escape(self, event) -> None:
        if self.catalog_detail is not None:
            self.close_catalog(event, choose=False)
        elif self.memory_detail is not None:
            self.memory_detail = None
            self.status = ""
        elif self.input_focus():
            buffer = event.current_buffer
            if buffer.complete_state is not None:
                buffer.cancel_completion()
            else:
                event.app.exit(result=None)
        else:
            event.app.exit(result=None)
        event.app.invalidate()

    def _close(self, event) -> None:
        event.app.exit(result=None)

    def render_footer(self) -> str:
        if self.status:
            return " " + safe_terminal_text(self.status)
        if self.catalog_detail is not None:
            return (
                " ↑/↓ parent · Enter reparent exact name · Esc close all"
                if self.editors[self.catalog_detail].role.new_parent_locator
                else " ↑/↓ Context · Enter use exact name · Esc close all"
            )
        if get_app().layout.has_focus(self.mode_control):
            return " ←/→ mode · ↓ first endpoint row · Tab next control · Esc cancel"
        if self.source_type_focus():
            return " ←/→ Source type · ↓ Source input · Tab next control · Esc cancel"
        if self.input_focus():
            inline_role_uid = self.focused_control_role("inline_input")
            if inline_role_uid is not None:
                return (
                    " Type exact inline Memory · ←/→ caret · ↑/↓ endpoint row · "
                    "Enter confirm · Tab next control · Esc cancel"
                )
            has_matches = self.focused_input_has_completions()
            movement = "↑/↓ matches" if has_matches else "↑/↓ endpoint row"
            return (
                f" Type exact Context · ←/→ caret · → at end next control · "
                f"{movement} · Enter confirm · Tab next control · Esc cancel"
            )
        if self.browse_focus():
            role_uid = self.focused_control_role("browse_control")
            browse_action = (
                "Enter browse parent Contexts"
                if role_uid is not None
                and self.editors[role_uid].role.new_parent_locator
                else "Enter browse all allowed Contexts"
            )
            return (
                " ↑/↓ endpoint row · ←/→ row control · "
                f"{browse_action} · "
                "Tab next control · Esc cancel"
            )
        if self.reach_focus():
            return (
                " ↑/↓ endpoint row · ←/→ row control · "
                "Space or Enter toggle descendants · Tab next control · Esc cancel"
            )
        if self.memory_control_focus():
            role_uid = self.focused_control_role("memory_control")
            preview_only = (
                role_uid is not None and self.editors[role_uid].role.memory_preview_only
            )
            if self.memory_detail is not None:
                return (
                    " ↑/↓ Memory evidence (edge continues by row) · "
                    "Enter keeps whole Context · "
                    "←/Esc close details"
                    if preview_only
                    else " ↑/↓ Memory (edge continues by row) · Enter choose · "
                    "←/Esc close details"
                )
            return (
                " ↑/↓ endpoint row · ←/→ row control · "
                + (
                    "Enter open read-only Memory evidence · "
                    if preview_only
                    else "Enter open Memory choices · "
                )
                + "Tab next control · Esc cancel"
            )
        if self.command_control is not None and self.command_control.is_focused():
            if not self.command_control.valid:
                return " Fix the red command before running · Tab first control · Esc cancel"
            if self.spec.command_ready_hint is not None:
                return f" {safe_terminal_text(self.spec.command_ready_hint.capitalize())} · ↑ previous · Esc cancel"
            return f" Enter run exact {safe_terminal_text(self.spec.command_verb)} command · ↑ previous · Esc cancel"
        if get_app().layout.has_focus(self.action_control):
            return f" Enter {safe_terminal_text(self.spec.action_label)} · ↑ previous · Esc cancel"
        return " Tab next · Esc cancel"

    def initial_control(self) -> object:
        if self.show_mode:
            return self.mode_control
        first_uid = self.spec.active_role_uids(self.selected_mode_uid())[0]
        first = self.editors[first_uid]
        return (
            first.source_type_control
            if first.source_type_visible()
            else first.role_primary_input()
        )

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

        command_frame = self.build_command_frame()

        catalog_detail_containers = self.build_catalog_details()

        memory_detail_container = self.build_memory_detail()

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
                command_frame if command_frame is not None else action_line,
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

        footer_control.text = self.render_footer
        return root

    def role_label_width(self) -> int:
        typed_source_roles = tuple(
            role for role in self.spec.roles if role.allow_inline_memory
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

    def build_command_frame(self) -> Frame | None:
        command_frame = (
            build_focused_frame(
                self.command_control.body,
                title=lambda: "PROPOSED COMMAND"
                + (
                    f" · {safe_terminal_text(self.spec.command_ready_hint)}"
                    if self.spec.command_ready_hint is not None
                    else ""
                )
                if self.command_control.frame_title == "COMMAND · RUNNABLE"
                else "PROPOSED COMMAND · INVALID",
                is_focused=self.command_control.is_focused,
                height=Dimension.exact(4),
            )
            if self.command_control is not None
            else None
        )

        if command_frame is not None:
            command_frame.container.style = self.command_control.frame_style
        return command_frame

    def build_catalog_details(self) -> list[ConditionalContainer]:
        catalog_detail_containers = []

        for role_uid, editor in self.editors.items():
            selector = editor.selector
            if selector is None:
                continue
            catalog_detail_containers.append(
                ConditionalContainer(
                    HSplit(
                        [
                            Window(
                                FormattedTextControl(
                                    lambda uid=role_uid: (
                                        "  PARENT CONTEXTS · "
                                        if self.editors[uid].role.new_parent_locator
                                        else "  CONTEXTS · "
                                    )
                                    + safe_terminal_text(
                                        self.spec.role_label(
                                            self.selected_mode_uid(), uid
                                        )
                                    )
                                    + (
                                        " · LOCAL LOCATIONS"
                                        if self.editors[uid].role.new_parent_locator
                                        else " · ALL ALLOWED"
                                    )
                                ),
                                height=Dimension.exact(1),
                                dont_extend_height=True,
                            ),
                            Window(
                                selector.control,
                                wrap_lines=False,
                                right_margins=[ScrollbarMargin(display_arrows=True)],
                                height=Dimension.exact(
                                    min(8, len(selector.view.names))
                                ),
                                dont_extend_height=True,
                            ),
                        ]
                    ),
                    filter=Condition(lambda uid=role_uid: self.catalog_detail == uid),
                )
            )
        return catalog_detail_containers

    def build_memory_detail(self) -> ConditionalContainer:
        memory_detail_control = FormattedTextControl(
            self.render_memory_detail, focusable=False, show_cursor=False
        )

        memory_detail_container = ConditionalContainer(
            Window(
                memory_detail_control,
                wrap_lines=True,
                right_margins=[ScrollbarMargin(display_arrows=True)],
                height=Dimension(min=3, preferred=7, max=9),
            ),
            filter=Condition(lambda: self.memory_detail is not None),
        )
        return memory_detail_container

    def bind_keys(self) -> None:
        self.source_type_focus = Condition(
            lambda: self.focused_control_role("source_type_control") is not None
        )
        self.reach_focus = Condition(
            lambda: self.focused_control_role("reach_control") is not None
        )
        self.input_focus = Condition(
            lambda: self.focused_control_role("input") is not None
            or self.focused_control_role("inline_input") is not None
        )
        self.writable_input_focus = Condition(
            lambda: self.input_focus()
            or (self.command_control is not None and self.command_control.is_focused())
        )
        self.browse_focus = Condition(
            lambda: self.focused_control_role("browse_control") is not None
        )
        self.memory_control_focus = Condition(
            lambda: self.focused_control_role("memory_control") is not None
        )

        self.bindings.add("left", filter=has_focus(self.mode_control), eager=True)(
            self._mode_left
        )
        self.bindings.add("right", filter=has_focus(self.mode_control), eager=True)(
            self._mode_right
        )
        self.bindings.add("left", filter=self.source_type_focus, eager=True)(
            self._source_type_left
        )
        self.bindings.add("right", filter=self.source_type_focus, eager=True)(
            self._source_type_right
        )
        self.bindings.add("left", filter=self.reach_focus, eager=True)(
            self._previous_reach_peer
        )
        self.bindings.add("right", filter=self.reach_focus, eager=True)(
            self._next_reach_peer
        )
        self.bindings.add(" ", filter=self.reach_focus, eager=True)(self._toggle_reach)
        self.bindings.add("right", filter=self.input_focus, eager=True)(
            self._next_input_position_or_peer
        )
        self.bindings.add("left", filter=self.browse_focus, eager=True)(
            self._previous_browse_peer
        )
        self.bindings.add("right", filter=self.browse_focus, eager=True)(
            self._next_browse_peer
        )
        self.bindings.add("left", filter=self.memory_control_focus, eager=True)(
            self._previous_memory_peer
        )
        self.bindings.add("right", filter=self.memory_control_focus, eager=True)(
            self._next_memory_peer
        )
        self.bindings.add("escape", eager=True)(self._escape)
        self.bindings.add("c-c", eager=True)(self._close)
        bind_case_insensitive_key(
            self.bindings, "q", filter=~self.writable_input_focus, eager=True
        )(self._close)


def run_compact_endpoint_setup(
    spec: EndpointSetupSpec,
    *,
    memory_loader: MemoryProjectionLoader | None,
    validate_draft: DraftValidator | None = None,
    command_editor: EndpointCommandBinding | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> EndpointSetupDraft | None:
    """Collect the same typed draft through a compact, input-first form."""

    if spec.screen_layout != "COMPACT_FORM":
        raise ValueError("Compact Endpoint Setup requires COMPACT_FORM layout.")
    if require_tty:
        require_interactive_terminal(
            spec.title,
            snapshot_hint="Pass explicit Context operands outside a terminal.",
        )
    memory_roles = tuple(role for role in spec.roles if role.allow_memory_focus)
    if memory_roles and memory_loader is None:
        raise ValueError("Endpoint Memory focus requires a projection loader.")

    return _CompactEndpointScreen(
        spec,
        memory_loader=memory_loader,
        validate_draft=validate_draft,
        command_editor=command_editor,
        app_input=app_input,
        app_output=app_output,
    ).app.run()
