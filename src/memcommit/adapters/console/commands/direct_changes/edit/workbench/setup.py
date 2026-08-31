"""Compose Edit's console workbench with UPDATE-aware Context access."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.authority.context_access import context_access_display_facts
from memcommit.application.capabilities.authority.granted_context_navigation import (
    freeze_granted_context_navigation,
)
from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.adapters.console.terminal.components.context_picker import context_memory_rows
from memcommit.application.operations.direct_changes.edit.application import FrozenEditPlan, prepare_edit
from memcommit.application.operations.direct_changes.edit.runtime import MemoryStoreEditPort
from memcommit.adapters.console.commands.direct_changes.edit.workbench.model import EditTuiSetup
from memcommit.adapters.console.commands.direct_changes.edit.workbench.screen import run_edit_tui


def build_edit_tui_setup(
    port: MemoryStoreEditPort,
    *,
    requested_context: str | None = None,
) -> EditTuiSetup:
    local_names = tuple(port.store.list_context_names())
    granted = freeze_granted_context_navigation(port.store)
    names = set(local_names) | set(granted.names)
    selectable = set(local_names)
    annotations = {
        name: value
        for name, value in granted.annotations.items()
        if name not in local_names
    }
    for name in granted.names:
        if name in local_names:
            continue
        try:
            access = port.access(name)
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            continue
        selectable.add(access.display_name)
        annotations[access.display_name] = context_access_display_facts(access)

    if requested_context is not None:
        access = port.access(requested_context)
        selected = access.display_name
        names.add(selected)
        selectable.add(selected)
        if access.is_granted:
            annotations[selected] = context_access_display_facts(access)
    elif port.current_context_name in selectable:
        selected = port.current_context_name
    elif selectable:
        selected = sorted(selectable, key=str.casefold)[0]
    else:
        raise ValueError("Interactive Edit requires an UPDATE-authorized Context.")

    assert selected is not None
    return EditTuiSetup(
        names=tuple(sorted(names, key=str.casefold)),
        selectable_names=frozenset(selectable),
        selected_context=selected,
        current_context=port.current_context_name,
        annotations=tuple(
            (name, annotations[name])
            for name in sorted(annotations, key=str.casefold)
            if name in names
        ),
    )


def choose_edit_setup(
    port: MemoryStoreEditPort,
    *,
    requested_context: str | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenEditPlan | None:
    def load_context(name: str):
        return port.inspect_context(name)

    def load_content(target: DirectMemoryTarget) -> str:
        item = ops.resolve_direct_memory(
            load_context(target.context_name),
            target.memory_uid,
        )
        return item.content

    return run_edit_tui(
        build_edit_tui_setup(port, requested_context=requested_context),
        memory_loader=lambda name: context_memory_rows(load_context(name)),
        content_loader=load_content,
        prepare=lambda request: prepare_edit(request, port=port),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = ["build_edit_tui_setup", "choose_edit_setup"]
