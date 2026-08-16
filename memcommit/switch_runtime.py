"""MemoryStore composition for the current-Context Switch application."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.authority.access import (
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.context_targeting.catalog import (
    GrantedContextNavigation,
    freeze_granted_context_navigation,
)
from memcommit.profiles import authority_grant_snapshot_lock
from memcommit.store import MemoryStore
from memcommit.switch_application import (
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
    granted_navigation: GrantedContextNavigation


def prepare_switch(
    store: MemoryStore,
    *,
    expected_current: str | None,
) -> SwitchSetupSnapshot:
    """Capture the current pointer once and freeze the picker namespace."""

    return SwitchSetupSnapshot(
        expected_current=expected_current,
        local_context_names=tuple(store.list_context_names()),
        granted_navigation=freeze_granted_context_navigation(store),
    )


class MemoryStoreSwitchContextPort:
    """Authorize and publish a current pointer through existing Store CAS APIs."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def local_context_exists(self, context_name: str) -> bool:
        return self._store.context_exists(context_name)

    def select(
        self,
        *,
        expected_current: str | None,
        context_name: str,
    ) -> SwitchContextTarget:
        access = resolve_context_access(
            self._store,
            context_name,
            current_name=expected_current,
            required_permission="READ",
        )
        target = (
            GrantedReadStore(access).load_direct(access.display_name)
            if access.is_granted
            else self._store.load(context_name)
        )

        # A granted current pointer is reauthorized under the registry lock;
        # a local pointer binds both the target record and command-start state.
        if access.is_granted:
            with authority_grant_snapshot_lock() as registry:
                resolve_context_access(
                    self._store,
                    context_name,
                    current_name=expected_current,
                    required_permission="READ",
                    registry=registry,
                )
                self._store.set_current_virtual_context_if(
                    expected_current,
                    context_name,
                )
        else:
            self._store.set_current_context_if(
                expected_current,
                context_name,
                expected_context_uid=target.uid,
                expected_context_digest=target._store_digest or "",
            )
        return SwitchContextTarget(
            context_name=context_name,
            granted=access.is_granted,
        )


def execute_switch_context(
    request: SwitchContextRequest,
    *,
    store: MemoryStore,
) -> SwitchContextResult:
    """Run Switch against one explicit Store without terminal dependencies."""

    return switch_context(
        request,
        port=MemoryStoreSwitchContextPort(store),
    )
