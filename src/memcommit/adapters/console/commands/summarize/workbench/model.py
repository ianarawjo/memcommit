"""Process-local setup values for the Summarize console workbench."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from memcommit.core.context_targeting.tui.picker import ContextMemoryRow
from memcommit.core.context_targeting.tui.reach import ContextReachViewMode
from memcommit.source_projection.presentation import SourceDisplayValue
from memcommit.application.operations.summarize.application import SummarizeResult


@dataclass(frozen=True)
class SummarizeTuiSetup:
    """Freeze the readable picker namespace before interactive execution."""

    names: tuple[str, ...]
    selected_context: str
    initial_range_mode: ContextReachViewMode = "BOTH"
    current_context: str | None = None
    annotations: tuple[tuple[str, SourceDisplayValue], ...] = ()
    memory_loader: Callable[[str], Sequence[ContextMemoryRow]] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if (
            not self.names
            or len(set(self.names)) != len(self.names)
            or any(not isinstance(name, str) or not name for name in self.names)
        ):
            raise ValueError("Summarize TUI requires a distinct readable catalog.")
        if self.selected_context not in self.names:
            raise ValueError("The selected Context is outside the readable catalog.")
        if self.initial_range_mode not in {"BOTH", "EXACT", "SUBTREE"}:
            raise ValueError("Summarize TUI initial range is invalid.")
        if self.current_context is not None and self.current_context not in self.names:
            raise ValueError("The current Context is outside the readable catalog.")
        if self.memory_loader is not None and not callable(self.memory_loader):
            raise ValueError("Summarize TUI Memory loader must be callable.")
        labels = dict(self.annotations)
        if len(labels) != len(self.annotations) or set(labels) - set(self.names):
            raise ValueError("Summarize TUI annotations are outside the catalog.")


@dataclass(frozen=True)
class SummarizeTuiOutcome:
    """One or both independently executed Summary views."""

    results: tuple[SummarizeResult, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.results) <= 2 or any(
            not isinstance(result, SummarizeResult) for result in self.results
        ):
            raise ValueError("Summarize TUI outcome requires one or two results.")
        if len({result.context_name for result in self.results}) != 1:
            raise ValueError("Summarize TUI result Contexts do not match.")
        scopes = {
            (result.include_descendants, result.follow_embeds)
            for result in self.results
        }
        if any(descendants != embeds for descendants, embeds in scopes):
            raise ValueError("Summarize TUI results require preset reach pairs.")
        if len(scopes) != len(self.results):
            raise ValueError("Summarize TUI result scopes must be distinct.")
        if len(self.results) == 2 and (
            self.results[0].include_descendants
            or not self.results[1].include_descendants
        ):
            raise ValueError(
                "Both Summary views must keep direct before recursive."
            )

    def result_for(self, *, include_descendants: bool) -> SummarizeResult | None:
        return next(
            (
                result
                for result in self.results
                if result.include_descendants is include_descendants
            ),
            None,
        )


@dataclass(frozen=True)
class SummarizeClipboardProjection:
    """One plain-text TUI copy without a durable clipboard stage."""

    text: str
    label: str

    def __post_init__(self) -> None:
        if not self.text or not self.label:
            raise ValueError("Summarize clipboard projection must be nonblank.")
