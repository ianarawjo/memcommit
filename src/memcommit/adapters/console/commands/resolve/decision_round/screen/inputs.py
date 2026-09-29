"""Screen-facing input contracts and display settings, without Resolve models."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from memcommit.application.capabilities.resolution.workbench import (
    ResolutionOption,
    ResolutionWorkbenchAction,
)


class CompactIntentInput(Protocol):
    """An optional editor with paired read/submit behavior and preview generation."""

    def response_text(self, item_uid: str, /) -> str: ...

    def submit_intent(self, item_uid: str, value: str, /) -> None: ...

    def validate_intent(self, value: str, /) -> None: ...

    def response_option_uid(self, item_uid: str, /) -> str | None: ...

    @property
    def prepare_response(self) -> Callable[[str, str], Awaitable[None]] | None: ...


class CompactDecisionInput(Protocol):
    """The caller owns decisions; the shell only reads and forwards interaction."""

    @property
    def choice_previews(self) -> Mapping[str, tuple[tuple[str, str], ...]] | None: ...

    @property
    def bulk_options(self) -> tuple[ResolutionOption, ...]: ...

    @property
    def intent(self) -> CompactIntentInput | None: ...

    def selected_option(self, item_uid: str, /) -> str | None: ...

    def select_choice(self, item_uid: str, option_uid: str, /) -> None: ...

    def select_for_all(self, choice_uid: str, /) -> None: ...

    def confirm(self, item_uid: str | None, /) -> ResolutionWorkbenchAction | None: ...


@dataclass(frozen=True)
class CompactScreenPresentation:
    continue_label: str
    response_title: str = "DIRECTION OR NOTE · OPTIONAL"
    activation_hint: str = "select/apply"
    show_item_navigation: bool = False
    require_all_decisions: bool = True
