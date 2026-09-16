"""Read-only shape accepted by the session host for an effect preview.

The host consumes this structural interface; it neither constructs previews nor
owns their validation or artifact-to-effect conversion. Impact implements the
interface in its command package without a reverse command import from the host.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EffectReportDetail:
    """Operation-authored evidence disclosed beneath one exact effect."""

    entry_uid: str
    heading: str
    text: str


@dataclass(frozen=True)
class EffectReportPresentation:
    """A compact Viewer, optionally accompanied by an owning action."""

    instruction: str = ""
    apply_label: str = ""
    unchanged_label: str = "KEEP"
    unchanged_entry_uids: frozenset[str] = frozenset()
    entry_details: tuple[EffectReportDetail, ...] = ()

    def details_for(self, uid: str) -> tuple[EffectReportDetail, ...]:
        return tuple(detail for detail in self.entry_details if detail.entry_uid == uid)


class EffectPreviewEntry(Protocol):
    @property
    def marker(self) -> str: ...

    @property
    def label(self) -> str: ...

    @property
    def text(self) -> str: ...

    @property
    def reason(self) -> str: ...

    @property
    def uid(self) -> str: ...

    @property
    def rules(self) -> tuple[str, ...]: ...

    @property
    def location(self) -> str: ...

    @property
    def before(self) -> str | None: ...

    @property
    def after(self) -> str | None: ...


class EffectPreviewView(Protocol):
    @property
    def operation(self) -> str: ...

    @property
    def artifact_uid(self) -> str: ...

    @property
    def revision(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def summary(self) -> str: ...

    @property
    def detail(self) -> str: ...

    @property
    def entries(self) -> tuple[EffectPreviewEntry, ...]: ...

    @property
    def replaces_results(self) -> bool: ...


class EffectPreviewSource(Protocol):
    def view(self) -> EffectPreviewView: ...
