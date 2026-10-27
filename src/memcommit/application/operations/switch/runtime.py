"""ProfileStore composition for the current-Context Switch application."""

from __future__ import annotations


from dataclasses import dataclass

from memcommit.application.context_access.access import resolve_context_access
from memcommit.persistence.store import ProfileStore
from memcommit.application.operations.switch.application import (
    SwitchContextRequest,
    SwitchContextResult,
    SwitchContextTarget,
    switch_context,
)


@dataclass(frozen=True)
class SwitchSetupSnapshot:
    """Catalog and current state frozen before optional terminal selection."""

    expected_current: str | None
    local_context_names: tuple[str, ...]


def prepare_switch(
    store: ProfileStore,
    *,
    expected_current: str | None,
) -> SwitchSetupSnapshot:
    """Capture the current pointer once and freeze the picker namespace."""

    return SwitchSetupSnapshot(
        expected_current=expected_current,
        local_context_names=tuple(store.list_context_names()),
    )


class MemoryStoreSwitchContextPort:
    """Authorize and publish a current pointer through existing Store CAS APIs."""

    def __init__(self, store: ProfileStore):
        self._store = store

    def local_context_exists(self, context_name: str) -> bool:
        return self._store.context_exists(context_name)

    def select(
        self,
        *,
        expected_current: str | None,
        context_name: str,
    ) -> SwitchContextTarget:
        resolve_context_access(
            self._store,
            context_name,
            current_name=expected_current,
        )
        target = self._store.load(context_name)

        self._store.set_current_context_if(
            expected_current,
            context_name,
            expected_context_uid=target.uid,
        )
        return SwitchContextTarget(
            context_name=context_name,
        )


def execute_switch_context(
    request: SwitchContextRequest,
    *,
    store: ProfileStore,
) -> SwitchContextResult:
    """Run Switch against one explicit Store without terminal dependencies."""

    return switch_context(
        request,
        port=MemoryStoreSwitchContextPort(store),
    )
