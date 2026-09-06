"""Declare endpoint form rows, keyboard traversal, and the matching key hints."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl

from memcommit.adapters.console.terminal.components.command_editor import (
    CommandEditorControl,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupSpec,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceState,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from .context_browser import ContextBrowser
from .endpoint_editor import EndpointEditor
from .memory_picker import MemoryPicker


class FormNavigation:
    """Adapt form rows to the common focus controller without owning their values."""

    def __init__(
        self,
        spec: EndpointSetupSpec,
        editors: Mapping[str, EndpointEditor],
        *,
        mode_state: HorizontalChoiceState,
        mode_control: FormattedTextControl,
        command_control: CommandEditorControl | None,
        action_control: FormattedTextControl,
        browser: ContextBrowser,
        memory_picker: MemoryPicker,
        move_mode: Callable[[object, int], SurfaceMoveResult],
        refresh_new_name_suggestions: Callable[[], None],
        finish: Callable[[object], SurfaceActionResult],
        get_status: Callable[[], str],
        set_status: Callable[[str], None],
    ) -> None:
        self.spec = spec
        self.editors = editors
        self.show_mode = len(spec.modes) > 1
        self.mode_state = mode_state
        self.mode_control = mode_control
        self.command_control = command_control
        self.action_control = action_control
        self.browser = browser
        self.memory_picker = memory_picker
        self.move_mode = move_mode
        self.refresh_new_name_suggestions = refresh_new_name_suggestions
        self.finish = finish
        self._get_status = get_status
        self._set_status = set_status
        self.bindings = KeyBindings()
        self.surfaces = SurfaceFocusController(self.visible_surfaces)
        bind_surface_navigation(self.bindings, self.surfaces)
        self.bind_keys()

    @property
    def status(self) -> str:
        return self._get_status()

    @status.setter
    def status(self, value: str) -> None:
        self._set_status(value)

    def choose_mode(self, _event) -> SurfaceActionResult:
        self.status = ""
        return "HANDLED"

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

    def move_source_type_choice(self, role_uid: str, delta: int) -> SurfaceMoveResult:
        editor = self.editors[role_uid]
        changed = editor.move_source_type(delta)
        if changed:
            self.memory_picker.reset()
            self.browser.reset()
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

        active_role_uids = self.spec.active_role_uids(self.mode_state.selected_uid)
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

        self.memory_picker.reset()
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
        inline = editor.effective_source_type() == "INLINE_MEMORY"
        if (
            not inline
            and buffer.complete_state is not None
            and buffer.complete_state.current_completion is not None
        ):
            buffer.apply_completion(buffer.complete_state.current_completion)
            self.status = ""
            return "HANDLED"
        try:
            editor.confirm_input()
        except (OSError, TypeError, ValueError) as error:
            self.status = str(error)
        else:
            self.status = ""
            if not inline:
                try:
                    self.refresh_new_name_suggestions()
                except (TypeError, ValueError) as error:
                    self.status = str(error)
                    return "HANDLED"
            self.surfaces.focus_relative(event.app, 1, wrap=False)
            if not inline and editor.browse_control is not None:
                # Enter confirms direct input and advances to the next semantic
                # control; Tab remains the explicit path into adjacent Browse.
                self.surfaces.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

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
        self.memory_picker.reset()
        self.status = ""
        target = controls[candidate]
        if target is editor.browse_control:
            self.browser.prepare(role_uid)
        event.app.layout.focus(target)
        return True

    def set_reach(self, role_uid: str, *, include_descendants: bool) -> None:
        editor = self.editors[role_uid]
        cleared = editor.set_descendants(include_descendants)
        self.status = (
            f"{editor.label()} Memory focus cleared for descendants." if cleared else ""
        )
        if include_descendants:
            self.memory_picker.reset_for(role_uid)

    def choose_reach(self, _event, role_uid: str) -> SurfaceActionResult:
        self.set_reach(
            role_uid,
            include_descendants=not self.editors[role_uid].reach.include_descendants,
        )
        return "HANDLED"

    def move_memory(self, event, role_uid: str, delta: int) -> SurfaceMoveResult:
        if self.memory_picker.active_role_uid != role_uid:
            return self.move_role_row(event, role_uid, delta)
        changed = self.memory_picker.move(delta)
        self.status = ""
        if changed:
            return "CONSUMED"
        # Once the transient list reaches an edge, the same arrow closes it
        # and continues along the endpoint form's vertical row topology.
        self.memory_picker.reset()
        return self.move_role_row(event, role_uid, delta)

    def move_action(self, event, delta: int) -> SurfaceMoveResult:
        if delta > 0:
            return "BOUNDARY"
        active_role_uids = self.spec.active_role_uids(self.mode_state.selected_uid)
        event.app.layout.focus(self.editors[active_role_uids[-1]].role_primary_input())
        self.status = ""
        return "CONSUMED"

    def visible_surfaces(self) -> tuple[FocusSurface, ...]:
        if self.browser.is_open:
            return (self.browser.surface(),)
        values: list[FocusSurface] = []
        if self.show_mode:
            values.append(
                FocusSurface(
                    "MODE",
                    self.mode_control,
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                    activate=self.choose_mode,
                    on_focus=self.memory_picker.reset,
                )
            )
        for role_uid in self.spec.active_role_uids(self.mode_state.selected_uid):
            editor = self.editors[role_uid]
            if editor.source_type_visible():
                values.append(
                    FocusSurface(
                        f"SOURCE_TYPE:{role_uid}",
                        editor.source_type_control,
                        move_vertical=lambda event,
                        delta,
                        uid=role_uid: self.move_source_type_row(event, uid, delta),
                        activate=lambda event, uid=role_uid: self.choose_source_type(
                            event, uid
                        ),
                        on_focus=self.memory_picker.reset,
                    )
                )
            # Use the same visible peer set for Tab and spatial row movement.
            peers = editor.role_peer_controls()
            actions = (
                (
                    "ROLE",
                    editor.role_primary_input(),
                    self.move_role,
                    self.choose_role,
                    self.memory_picker.reset,
                ),
                (
                    "BROWSE",
                    editor.browse_control,
                    self.move_role_row,
                    self.browser.activate,
                    partial(self.browser.prepare, role_uid),
                ),
                (
                    "RANGE",
                    editor.reach_control,
                    self.move_role_row,
                    self.choose_reach,
                    self.memory_picker.reset,
                ),
                (
                    "MEMORY",
                    editor.memory_control,
                    self.move_memory,
                    self.memory_picker.activate,
                    None,
                ),
            )
            for name, control, move, activate, on_focus in actions:
                if control in peers:
                    values.append(
                        FocusSurface(
                            f"{name}:{role_uid}",
                            control,
                            move_vertical=lambda event,
                            delta,
                            uid=role_uid,
                            handler=move: handler(event, uid, delta),
                            activate=lambda event,
                            uid=role_uid,
                            handler=activate: handler(event, uid),
                            on_focus=on_focus,
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
                else self.memory_picker.reset,
            )
        )
        return tuple(values)

    def _move_mode(self, event, *, delta: int) -> None:
        self.move_mode(event, delta)
        event.app.invalidate()

    def _move_source_type(self, event, *, delta: int) -> None:
        role_uid = self.focused_control_role("source_type_control")
        if role_uid is not None:
            self.move_source_type_choice(role_uid, delta)
        event.app.invalidate()

    def _move_peer(self, event, *, attribute: str, delta: int) -> None:
        role_uid = self.focused_control_role(attribute)
        if role_uid is None:
            return
        if (
            attribute == "memory_control"
            and self.memory_picker.active_role_uid == role_uid
        ):
            if delta < 0:
                self.memory_picker.dismiss(event)
            else:
                self.status = "Memory choices use Up/Down · Left closes details."
        else:
            self.move_role_peer(
                event, role_uid, getattr(self.editors[role_uid], attribute), delta
            )
        event.app.invalidate()

    def _toggle_reach(self, event) -> None:
        role_uid = self.focused_control_role("reach_control")
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

    def focused_input_has_completions(self) -> bool:
        return any(
            get_app().layout.has_focus(editor.input)
            and editor.input.buffer.complete_state is not None
            for editor in self.editors.values()
        )

    def _cancel_completion(self, event) -> bool:
        if self.input_focus() and event.current_buffer.complete_state is not None:
            event.current_buffer.cancel_completion()
            return True
        return False

    def _escape(self, event) -> None:
        dispatch_tui_back(
            event,
            self.browser.dismiss,
            self.memory_picker.dismiss,
            self._cancel_completion,
            close=self._close,
        )
        event.app.invalidate()

    def _close(self, event) -> None:
        event.app.exit(result=None)

    def render_footer(self) -> str:
        if self.status:
            return " " + safe_terminal_text(self.status)
        if self.browser.active_role_uid is not None:
            return (
                " ↑/↓ parent · Enter reparent exact name · Esc close all"
                if self.editors[self.browser.active_role_uid].role.new_parent_locator
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
            if self.memory_picker.active_role_uid is not None:
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
        first_uid = self.spec.active_role_uids(self.mode_state.selected_uid)[0]
        first = self.editors[first_uid]
        return (
            first.source_type_control
            if first.source_type_visible()
            else first.role_primary_input()
        )

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

        for key, delta in (("left", -1), ("right", 1)):
            self.bindings.add(key, filter=has_focus(self.mode_control), eager=True)(
                partial(self._move_mode, delta=delta)
            )
            self.bindings.add(key, filter=self.source_type_focus, eager=True)(
                partial(self._move_source_type, delta=delta)
            )
            for attribute, condition in (
                ("reach_control", self.reach_focus),
                ("browse_control", self.browse_focus),
                ("memory_control", self.memory_control_focus),
            ):
                self.bindings.add(key, filter=condition, eager=True)(
                    partial(self._move_peer, attribute=attribute, delta=delta)
                )
        self.bindings.add(" ", filter=self.reach_focus, eager=True)(self._toggle_reach)
        self.bindings.add("right", filter=self.input_focus, eager=True)(
            self._next_input_position_or_peer
        )
        self.bindings.add("escape", eager=True)(self._escape)
        self.bindings.add("c-c", eager=True)(self._close)
        bind_case_insensitive_key(
            self.bindings, "q", filter=~self.writable_input_focus, eager=True
        )(self._close)
