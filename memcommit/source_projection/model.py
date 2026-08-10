"""Operation-neutral facts behind one displayed Context or item source."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceAccess(str, Enum):
    """How the active Profile is authorized to use the source."""

    OWNED = "OWNED"
    READ_GRANT = "READ_GRANT"
    QUERY_GRANT = "QUERY_GRANT"


class SourceReach(str, Enum):
    """How an occurrence was reached from the person's selected root."""

    DIRECT = "DIRECT"
    DESCENDANT = "DESCENDANT"
    VIA_EMBED = "VIA_EMBED"


class SourceForm(str, Enum):
    """The durable or virtual shape represented by the displayed row."""

    CONTEXT = "CONTEXT"
    MEMORY = "MEMORY"
    MEMORY_REF = "MEMORY_REF"
    QUERY_VIEW = "QUERY_VIEW"


class SourceState(str, Enum):
    """Display-relevant availability state independent of authority."""

    READ_ONLY = "READ_ONLY"
    UNAVAILABLE = "UNAVAILABLE"
    DANGLING = "DANGLING"
    CYCLE = "CYCLE"
    NOT_INCLUDED = "NOT_INCLUDED"


@dataclass(frozen=True)
class SourceDisplayFacts:
    """Typed source facts rendered by every CLI and TUI surface.

    Access, reach, and form are independent axes.  For example, a MemoryRef
    can be reached through an embedded Context whose source is READ-granted;
    collapsing those facts into one operation-authored label loses material
    provenance and makes wording changes capable of changing behavior.
    """

    access: SourceAccess = SourceAccess.OWNED
    reach: SourceReach = SourceReach.DIRECT
    form: SourceForm = SourceForm.CONTEXT
    states: tuple[SourceState, ...] = ()
    permissions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.access, SourceAccess):
            raise TypeError("Source access must be a SourceAccess value.")
        if not isinstance(self.reach, SourceReach):
            raise TypeError("Source reach must be a SourceReach value.")
        if not isinstance(self.form, SourceForm):
            raise TypeError("Source form must be a SourceForm value.")
        if len(set(self.states)) != len(self.states):
            raise ValueError("Source display states must be distinct.")
        if any(not isinstance(value, SourceState) for value in self.states):
            raise TypeError("Source display states must be SourceState values.")
        if any(
            not isinstance(permission, str)
            or not permission.strip()
            or any(character in permission for character in "\r\n")
            for permission in self.permissions
        ):
            raise ValueError("Source permissions must be nonblank one-line text.")
        if len(set(self.permissions)) != len(self.permissions):
            raise ValueError("Source permissions must be distinct.")
        if self.access is SourceAccess.OWNED and self.permissions:
            raise ValueError("Owned sources do not carry Grant permissions.")


def context_access_facts(
    *,
    granted: bool,
    permission: str = "READ",
    permissions: tuple[str, ...] = (),
    reach: SourceReach = SourceReach.DIRECT,
    form: SourceForm = SourceForm.CONTEXT,
    states: tuple[SourceState, ...] = (),
) -> SourceDisplayFacts:
    """Adapt a ContextAccess-like decision without importing command code."""

    if not isinstance(permission, str) or not permission.strip():
        raise ValueError("Context access permission must be nonblank text.")
    normalized = permission.strip().upper()
    if granted:
        access = (
            SourceAccess.QUERY_GRANT
            if normalized == "QUERY"
            else SourceAccess.READ_GRANT
        )
    else:
        access = SourceAccess.OWNED
        permissions = ()
    return SourceDisplayFacts(
        access=access,
        reach=reach,
        form=form,
        states=states,
        permissions=permissions,
    )
