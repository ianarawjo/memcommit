"""Shared terminal Surface focus and key-routing contracts."""

from types import SimpleNamespace

import pytest

from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceFocusController,
    focus_in_order,
)


class _Layout:
    def __init__(self, focused: object) -> None:
        self.focused = focused

    def has_focus(self, control: object) -> bool:
        return self.focused is control

    def focus(self, control: object) -> None:
        self.focused = control


class _App:
    def __init__(self, focused: object) -> None:
        self.layout = _Layout(focused)
        self.invalidations = 0

    def invalidate(self) -> None:
        self.invalidations += 1


def test_vertical_move_stays_inside_then_crosses_the_surface_boundary():
    first = object()
    second = object()
    at_boundary = {"value": False}
    entries: list[int] = []

    def move_first(_event, _delta):
        if at_boundary["value"]:
            return "BOUNDARY"
        at_boundary["value"] = True
        return "MOVED"

    controller = SurfaceFocusController(
        (
            FocusSurface("first", first, move_vertical=move_first),
            FocusSurface(
                "second",
                second,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                on_vertical_enter=entries.append,
            ),
        )
    )
    app = _App(first)
    event = SimpleNamespace(app=app)

    assert controller.move_vertical(event, 1) is True
    assert app.layout.focused is first
    assert controller.move_vertical(event, 1) is True
    assert app.layout.focused is second
    assert entries == [1]


def test_vertical_boundary_does_not_wrap_the_screen():
    only = object()
    controller = SurfaceFocusController(
        (FocusSurface("only", only, move_vertical=lambda _event, _delta: "BOUNDARY"),)
    )
    app = _App(only)

    assert controller.move_vertical(SimpleNamespace(app=app), 1) is False
    assert app.layout.focused is only


def test_tab_traversal_wraps_without_resetting_surface_entry_state():
    first = object()
    second = object()
    entries: list[int] = []
    focused: list[str] = []
    controller = SurfaceFocusController(
        (
            FocusSurface(
                "first",
                first,
                on_focus=lambda: focused.append("first"),
                on_vertical_enter=entries.append,
            ),
            FocusSurface(
                "second",
                second,
                on_focus=lambda: focused.append("second"),
                on_vertical_enter=entries.append,
            ),
        )
    )
    app = _App(first)

    assert controller.focus_relative(app, 1, wrap=True) is True
    assert app.layout.focused is second
    assert controller.focus_relative(app, 1, wrap=True) is True
    assert app.layout.focused is first
    assert entries == []
    assert focused == ["second", "first"]


def test_enter_dispatches_to_the_active_surface_only():
    first = object()
    second = object()
    calls: list[str] = []
    controller = SurfaceFocusController(
        (
            FocusSurface(
                "first",
                first,
                activate=lambda _event: calls.append("first") or "HANDLED",
            ),
            FocusSurface(
                "second",
                second,
                activate=lambda _event: calls.append("second") or "ENTER_CHILD",
            ),
        )
    )
    app = _App(second)

    assert controller.activate(SimpleNamespace(app=app)) is True
    assert calls == ["second"]


def test_surface_controller_rejects_duplicate_visible_controls():
    shared = object()

    with pytest.raises(ValueError, match="controls must be distinct"):
        SurfaceFocusController(
            (
                FocusSurface("first", shared),
                FocusSurface("second", shared),
            )
        )


def test_dynamic_surface_provider_may_rebuild_surface_records_each_time():
    first = object()
    second = object()
    entries: list[int] = []

    def surfaces():
        return (
            FocusSurface("first", first),
            FocusSurface(
                "second",
                second,
                on_vertical_enter=lambda delta: entries.append(delta),
            ),
        )

    controller = SurfaceFocusController(surfaces)
    app = _App(first)

    assert controller.focus_relative(
        app,
        1,
        wrap=False,
        vertical_entry=True,
    ) is True
    assert app.layout.focused is second
    assert entries == [1]


def test_legacy_focus_in_order_uses_the_same_wrapping_contract():
    first = object()
    second = object()
    app = _App(second)

    assert focus_in_order(app, (first, second), 1, wrap=True) is True
    assert app.layout.focused is first
