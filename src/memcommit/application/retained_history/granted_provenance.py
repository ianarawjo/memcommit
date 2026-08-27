"""Current-state provenance boundary for one READ-granted Memory."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.authority.access import ContextAccess
from memcommit.context import Context, Memory
from memcommit.application.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryHistoryReconstructionError,
    MemoryState,
)


@dataclass(frozen=True)
class GrantedMemoryTraceReport:
    """A visible Grant route without unauthorized authority history."""

    context_uid: str
    context_name: str
    selected_uid: str
    current: MemoryState
    grant_uid: str
    grant_revision: int
    authority_profile_uid: str
    grantee_profile_uid: str
    resource_uid: str
    resource_name: str
    permissions: tuple[str, ...]
    warning: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "granted_memory",
            "context": {"uid": self.context_uid, "name": self.context_name},
            "selected_uid": self.selected_uid,
            "current": self.current.to_dict(),
            "access_route": {
                "grant_uid": self.grant_uid,
                "grant_revision": self.grant_revision,
                "authority_profile_uid": self.authority_profile_uid,
                "grantee_profile_uid": self.grantee_profile_uid,
                "resource_uid": self.resource_uid,
                "resource_name": self.resource_name,
                "permissions": list(self.permissions),
            },
            "history": {"status": "HIDDEN", "reason": self.warning},
            "warnings": [self.warning],
        }


def build_granted_memory_trace(
    access: ContextAccess,
    selector: str,
    *,
    context: Context | None = None,
    display_name: str | None = None,
) -> GrantedMemoryTraceReport:
    """Freeze one current readable Memory and its exact active Grant route."""

    view = access.view
    if view is None:
        raise ValueError("Granted Memory Trace requires a granted Context access.")
    context = context or access.store.load_direct(access.context_name)
    matches = tuple(
        item
        for item in context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(selector)
    )
    exact = tuple(item for item in matches if item.uid == selector)
    if exact:
        matches = exact
    if not matches:
        raise MemoryHistoryReconstructionError(
            f"No current readable Memory with uid starting with {selector!r} "
            f"exists in granted Context {(display_name or access.display_name)!r}."
        )
    if len(matches) != 1:
        raise MemoryHistoryReconstructionError(
            f"Ambiguous prefix {selector!r} matches {len(matches)} granted "
            "Memories: " + ", ".join(memory.uid[:8] for memory in matches)
        )
    memory = matches[0]
    position = next(
        index
        for index, item in enumerate(context.iter_items())
        if isinstance(item, Memory) and item.uid == memory.uid
    )
    warning = (
        "Authority checkpoint and command-log history is outside this READ "
        "Grant; only the current readable Memory and active Grant route are shown."
    )
    grant = view.grant
    return GrantedMemoryTraceReport(
        context_uid=context.uid,
        context_name=display_name or access.display_name,
        selected_uid=memory.uid,
        current=MemoryState(
            uid=memory.uid,
            content=memory.content,
            position=position,
        ),
        grant_uid=grant.uid,
        grant_revision=grant.revision,
        authority_profile_uid=view.authority.uid,
        grantee_profile_uid=view.grantee.uid,
        resource_uid=grant.resource_uid,
        resource_name=grant.resource_name,
        permissions=grant.permissions,
        warning=warning,
    )


__all__ = ["GrantedMemoryTraceReport", "build_granted_memory_trace"]
