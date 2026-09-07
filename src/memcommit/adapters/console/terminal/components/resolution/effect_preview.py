"""Read-only shape accepted by the session host for an effect preview.

The host consumes this structural interface; it neither constructs previews nor
owns their validation or artifact-to-effect conversion. Impact implements the
interface in its command package without a reverse command import from the host.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EffectReportPresentation:
    """Operation-authored copy for a Viewer and one exact Apply control."""

    instruction: str
    apply_label: str
    unchanged_label: str
    unchanged_entry_uids: frozenset[str] = frozenset()


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
