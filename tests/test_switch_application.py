"""Typed application and adapter boundaries for current-Context switching."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from memcommit.adapters.interfaces.tui.operations.switch import (
    SwitchTuiSetup,
    run_switch_tui,
)
from memcommit.application.operations.switch.application import (
    SwitchContextError,
    SwitchContextRequest,
    SwitchContextTarget,
    switch_context,
)


ROOT = Path(__file__).parents[1]


@dataclass
class FakeSwitchPort:
    local_names: frozenset[str]
    selected: list[tuple[str | None, str]] = field(default_factory=list)
    navigated: list[tuple[str | None, str]] = field(default_factory=list)
    returned_name: str | None = None

    def local_context_exists(self, context_name: str) -> bool:
        return context_name in self.local_names

    def select(
        self,
        *,
        expected_current: str | None,
        context_name: str,
    ) -> SwitchContextTarget:
        self.selected.append((expected_current, context_name))
        return SwitchContextTarget(
            context_name=self.returned_name or context_name,
            granted=False,
        )

    def navigate(
        self,
        *,
        expected_current: str | None,
        direction: str,
    ) -> SwitchContextTarget:
        self.navigated.append((expected_current, direction))
        return SwitchContextTarget(
            context_name=self.returned_name or "previous",
            granted=False,
        )


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text())
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def test_application_resolves_relative_selector_against_one_frozen_current() -> None:
    port = FakeSwitchPort(
        frozenset({"task/from", "task/to"}),
    )

    result = switch_context(
        SwitchContextRequest(
            selector="../to",
            expected_current="task/from",
        ),
        port=port,
    )

    assert port.selected == [("task/from", "task/to")]
    assert result.previous_context_name == "task/from"
    assert result.context_name == "task/to"
    assert result.changed is True


def test_application_keeps_bare_name_global() -> None:
    port = FakeSwitchPort(frozenset({"organization/wiki", "facilities"}))

    result = switch_context(
        SwitchContextRequest(
            selector="facilities",
            expected_current="organization/wiki",
        ),
        port=port,
    )

    assert result.context_name == "facilities"
    assert port.selected == [("organization/wiki", "facilities")]


def test_application_routes_previous_navigation_without_locator_resolution() -> None:
    port = FakeSwitchPort(
        frozenset({"previous", "current"}),
        returned_name="previous",
    )

    result = switch_context(
        SwitchContextRequest(
            selector=None,
            expected_current="current",
            direction="PREVIOUS",
        ),
        port=port,
    )

    assert port.selected == []
    assert port.navigated == [("current", "PREVIOUS")]
    assert result.previous_context_name == "current"
    assert result.context_name == "previous"
    assert result.changed is True


@pytest.mark.parametrize(
    "selector,direction",
    ((None, None), ("alpha", "NEXT")),
)
def test_application_requires_exactly_one_selector_or_direction(
    selector,
    direction,
) -> None:
    with pytest.raises(SwitchContextError, match="exactly one"):
        SwitchContextRequest(
            selector=selector,
            expected_current="current",
            direction=direction,
        )


def test_application_rejects_relative_selector_without_current_before_port() -> None:
    port = FakeSwitchPort(frozenset())

    with pytest.raises(SwitchContextError, match="no current context"):
        switch_context(
            SwitchContextRequest(selector="./child", expected_current=None),
            port=port,
        )

    assert port.selected == []


def test_application_rejects_missing_exact_lexical_parent_before_select() -> None:
    port = FakeSwitchPort(frozenset({"organization/wiki"}))

    with pytest.raises(
        SwitchContextError,
        match="namespace parent context 'organization' does not exist",
    ):
        switch_context(
            SwitchContextRequest(
                selector="..",
                expected_current="organization/wiki",
            ),
            port=port,
        )

    assert port.selected == []


def test_application_rejects_port_identity_outside_requested_target() -> None:
    port = FakeSwitchPort(
        frozenset({"alpha", "beta"}),
        returned_name="beta",
    )

    with pytest.raises(SwitchContextError, match="outside the requested target"):
        switch_context(
            SwitchContextRequest(selector="alpha", expected_current="beta"),
            port=port,
        )


def test_tui_adapter_returns_request_without_selecting_state() -> None:
    observed: dict[str, object] = {}

    def choose(names, **options):
        observed["names"] = names
        observed.update(options)
        return "alpha"

    request = run_switch_tui(
        SwitchTuiSetup(
            expected_current="beta",
            local_context_names=("alpha", "beta"),
            memory_loader=lambda _name: (),
        ),
        chooser=choose,
    )

    assert request == SwitchContextRequest(
        selector="alpha",
        expected_current="beta",
    )
    assert observed["names"] == ["alpha", "beta"]
    assert observed["accept_label"] == "switch"


def test_switch_application_and_runtime_do_not_import_terminal_adapters() -> None:
    forbidden = ("typer", "prompt_toolkit", "memcommit.adapters.console.commands")
    for relative in (
        "src/memcommit/application/operations/switch/application.py",
        "src/memcommit/application/operations/switch/runtime.py",
    ):
        imports = _imports(ROOT / relative)
        assert not any(
            module == prefix or module.startswith(prefix + ".")
            for module in imports
            for prefix in forbidden
        )


def test_context_picker_compatibility_module_is_behavior_free() -> None:
    path = ROOT / "src" / "memcommit" / "commands" / "shared" / "context_picker.py"
    tree = ast.parse(path.read_text())
    assert not any(
        isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        for node in tree.body
    )
    production_importers = [
        source
        for source in (ROOT / "src" / "memcommit").rglob("*.py")
        if source != path
        and source.name != "_legacy_command_alias_map.py"
        and "memcommit.adapters.console.commands.shared.context_picker" in source.read_text()
    ]
    assert production_importers == []


def test_switch_tui_operation_does_not_import_command_adapters() -> None:
    operation = ROOT / "src" / "memcommit" / "adapters" / "interfaces" / "tui" / "operations" / "switch"
    offenders = [
        source
        for source in operation.rglob("*.py")
        if any(
            module == "memcommit.adapters.console.commands" or module.startswith("memcommit.adapters.console.commands.")
            for module in _imports(source)
        )
    ]
    assert offenders == []
