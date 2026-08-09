"""Shared key grammar and boundary traversal for terminal surfaces.

The controller owns how keys are routed through visible controls.  Callers
still own what moving or activating one semantic surface actually means.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent


SurfaceMoveResult = Literal["MOVED", "BOUNDARY", "CONSUMED"]
SurfaceActionResult = Literal["HANDLED", "ENTER_CHILD", "IGNORED"]
SurfaceMoveHandler = Callable[[KeyPressEvent, int], SurfaceMoveResult]
SurfaceActionHandler = Callable[[KeyPressEvent], SurfaceActionResult]
SurfaceFocusHandler = Callable[[], None]
SurfaceEnterHandler = Callable[[int], None]
SurfaceProvider = Callable[[], Sequence["FocusSurface"]]


@dataclass(frozen=True)
class FocusSurface:
    """One visible keyboard surface in screen order.

    ``move_vertical`` reports only interaction mechanics.  For example, a
    Context tree returns ``MOVED`` while its cursor changes and ``BOUNDARY`` at
    its first or last row.  The controller then performs the cross-surface
    transition without learning anything about Context selection semantics.
    """

    uid: str
    control: object
    move_vertical: SurfaceMoveHandler | None = None
    activate: SurfaceActionHandler | None = None
    back: SurfaceActionHandler | None = None
    on_focus: SurfaceFocusHandler | None = None
    on_vertical_enter: SurfaceEnterHandler | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ValueError("Focus surfaces require a nonblank UID.")


class SurfaceFocusController:
    """Route common keys through a caller-supplied visible surface topology."""

    def __init__(
        self,
        surfaces: Sequence[FocusSurface] | SurfaceProvider,
    ) -> None:
        self._surface_provider: SurfaceProvider = (
            surfaces if callable(surfaces) else lambda: surfaces
        )
        self.surfaces()

    def surfaces(self) -> tuple[FocusSurface, ...]:
        """Resolve and validate the current visible screen order."""

        values = tuple(self._surface_provider())
        if not values:
            raise ValueError("Surface focus requires at least one visible surface.")
        if any(not isinstance(surface, FocusSurface) for surface in values):
            raise ValueError("Surface focus received an invalid surface.")
        if len({surface.uid for surface in values}) != len(values):
            raise ValueError("Visible focus surface UIDs must be distinct.")
        if len({id(surface.control) for surface in values}) != len(values):
            raise ValueError("Visible focus surface controls must be distinct.")
        return values

    def active(self, app) -> FocusSurface | None:
        """Return the surface containing prompt-toolkit's current focus."""

        return next(
            (
                surface
                for surface in self.surfaces()
                if app.layout.has_focus(surface.control)
            ),
            None,
        )

    def focus_relative(
        self,
        app,
        delta: int,
        *,
        wrap: bool,
        vertical_entry: bool = False,
    ) -> bool:
        """Focus an adjacent visible surface in declared screen order."""

        if delta not in {-1, 1}:
            raise ValueError("Surface focus direction must be -1 or 1.")
        surfaces = self.surfaces()
        index = next(
            (
                position
                for position, surface in enumerate(surfaces)
                if app.layout.has_focus(surface.control)
            ),
            -1,
        )
        if index < 0:
            return False
        candidate = index + delta
        if wrap:
            candidate %= len(surfaces)
        elif not 0 <= candidate < len(surfaces):
            return False
        target = surfaces[candidate]
        if target.on_focus is not None:
            target.on_focus()
        if vertical_entry and target.on_vertical_enter is not None:
            target.on_vertical_enter(delta)
        app.layout.focus(target.control)
        return True

    def move_vertical(self, event: KeyPressEvent, delta: int) -> bool:
        """Move inside the active surface, then cross its boundary if reported."""

        if delta not in {-1, 1}:
            raise ValueError("Surface movement direction must be -1 or 1.")
        active = self.active(event.app)
        if active is None or active.move_vertical is None:
            return False
        result = active.move_vertical(event, delta)
        if result not in {"MOVED", "BOUNDARY", "CONSUMED"}:
            raise ValueError("Surface move handler returned an invalid result.")
        if result == "BOUNDARY":
            return self.focus_relative(
                event.app,
                delta,
                wrap=False,
                vertical_entry=True,
            )
        return True

    def activate(self, event: KeyPressEvent) -> bool:
        """Dispatch Enter to the active surface's operation-owned handler."""

        return self._dispatch_action(event, "activate")

    def back(self, event: KeyPressEvent) -> bool:
        """Dispatch one-level back navigation without defining its semantics."""

        return self._dispatch_action(event, "back")

    def _dispatch_action(
        self,
        event: KeyPressEvent,
        action_name: Literal["activate", "back"],
    ) -> bool:
        active = self.active(event.app)
        if active is None:
            return False
        handler = getattr(active, action_name)
        if handler is None:
            return False
        result = handler(event)
        if result not in {"HANDLED", "ENTER_CHILD", "IGNORED"}:
            raise ValueError("Surface action handler returned an invalid result.")
        return result != "IGNORED"

    def active_supports(
        self,
        app,
        capability: Literal["move_vertical", "activate", "back"],
    ) -> bool:
        active = self.active(app)
        return active is not None and getattr(active, capability) is not None


def focus_in_order(
    app,
    controls: Sequence[object],
    delta: int,
    *,
    wrap: bool,
) -> bool:
    """Compatibility traversal for callers without Surface adapters."""

    return SurfaceFocusController(
        tuple(
            FocusSurface(f"surface-{index}", control)
            for index, control in enumerate(controls)
        )
    ).focus_relative(app, delta, wrap=wrap)


def bind_surface_navigation(
    bindings: KeyBindings,
    controller: SurfaceFocusController,
    *,
    tab: bool = True,
    vertical: bool = True,
    activate: bool = True,
    back: bool = False,
) -> None:
    """Bind the shared key grammar for capabilities declared by each surface."""

    has_active_surface = Condition(lambda: controller.active(get_app()) is not None)
    can_move = Condition(
        lambda: controller.active_supports(get_app(), "move_vertical")
    )
    can_activate = Condition(lambda: controller.active_supports(get_app(), "activate"))
    can_back = Condition(lambda: controller.active_supports(get_app(), "back"))

    if tab:

        @bindings.add("tab", filter=has_active_surface, eager=True)
        def _next_surface(event: KeyPressEvent) -> None:
            controller.focus_relative(event.app, 1, wrap=True)
            event.app.invalidate()

        @bindings.add("s-tab", filter=has_active_surface, eager=True)
        def _previous_surface(event: KeyPressEvent) -> None:
            controller.focus_relative(event.app, -1, wrap=True)
            event.app.invalidate()

    if vertical:

        @bindings.add("down", filter=can_move, eager=True)
        def _move_down(event: KeyPressEvent) -> None:
            controller.move_vertical(event, 1)
            event.app.invalidate()

        @bindings.add("up", filter=can_move, eager=True)
        def _move_up(event: KeyPressEvent) -> None:
            controller.move_vertical(event, -1)
            event.app.invalidate()

    if activate:

        @bindings.add("enter", filter=can_activate, eager=True)
        def _activate_surface(event: KeyPressEvent) -> None:
            controller.activate(event)
            event.app.invalidate()

    if back:

        @bindings.add("escape", filter=can_back, eager=True)
        @bindings.add("backspace", filter=can_back, eager=True)
        def _back_surface(event: KeyPressEvent) -> None:
            controller.back(event)
            event.app.invalidate()
