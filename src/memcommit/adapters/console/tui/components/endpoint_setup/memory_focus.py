"""Role-local direct-Memory focus mechanics for Endpoint Setup."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from memcommit.adapters.console.tui.components.endpoint_setup.model import (
    EndpointSetupMemory,
)
from memcommit.adapters.console.tui.core.theme import focused_control_style
from memcommit.adapters.console.selection import FlatSelectionState, SelectionOption
from memcommit.adapters.console.selection.tui import render_vertical_choice_rows


MemoryProjectionLoader = Callable[
    [str, str], Sequence[EndpointSetupMemory]
]

_WHOLE_CONTEXT_UID = "ENDPOINT_SETUP_WHOLE_CONTEXT"
_MEMORY_OPTION_PREFIX = "ENDPOINT_SETUP_MEMORY:"


def _memory_option_uid(memory_uid: str) -> str:
    return _MEMORY_OPTION_PREFIX + memory_uid


@dataclass
class EndpointMemoryFocusController:
    """Keep one Memory choice valid for one currently selected exact Context."""

    role_uid: str
    selected_context: Callable[[], str]
    loader: MemoryProjectionLoader
    selected_memory_uid: str | None = None
    cache: dict[str, tuple[EndpointSetupMemory, ...]] = field(default_factory=dict)
    cursor_uid: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.role_uid, str)
            or not self.role_uid
            or not callable(self.selected_context)
            or not callable(self.loader)
        ):
            raise ValueError("Endpoint Memory focus requires one typed role loader.")
        self.cursor_uid = (
            _memory_option_uid(self.selected_memory_uid)
            if self.selected_memory_uid is not None
            else _WHOLE_CONTEXT_UID
        )
        if self.selected_memory_uid is not None:
            initial = self.prepare_context(self.selected_context())
            if all(
                memory.uid != self.selected_memory_uid
                for memory in initial
            ):
                raise ValueError(
                    "Endpoint role initial Memory is outside its selected Context."
                )

    def prepare_context(
        self,
        context_name: str,
    ) -> tuple[EndpointSetupMemory, ...]:
        """Load one authorized exact Context without broad catalog disclosure."""

        cached = self.cache.get(context_name)
        if cached is not None:
            return cached
        loaded = tuple(self.loader(self.role_uid, context_name))
        if any(
            not isinstance(memory, EndpointSetupMemory)
            or memory.context_name != context_name
            for memory in loaded
        ):
            raise ValueError(
                "Endpoint Memory loader returned a projection for another Context."
            )
        uids = tuple(memory.uid for memory in loaded)
        if len(uids) != len(set(uids)):
            raise ValueError("Endpoint Memory loader returned duplicate UIDs.")
        self.cache[context_name] = loaded
        return loaded

    def state(self) -> FlatSelectionState:
        memories = self.prepare_context(self.selected_context())
        options = (
            SelectionOption(
                _WHOLE_CONTEXT_UID,
                "WHOLE CONTEXT",
                "Use every direct Memory in this exact Context.",
            ),
            *(
                SelectionOption(
                    _memory_option_uid(memory.uid),
                    f"MEMORY · {memory.uid[:8]}",
                    memory.preview,
                )
                for memory in memories
            ),
        )
        available = {option.uid for option in options}
        if self.cursor_uid not in available:
            self.cursor_uid = _WHOLE_CONTEXT_UID
        selected_uid = (
            _memory_option_uid(self.selected_memory_uid)
            if self.selected_memory_uid is not None
            else _WHOLE_CONTEXT_UID
        )
        if selected_uid not in available:
            # This is a fail-safe for a caller changing the selected Context
            # without using the screen's explicit Context-choice transition.
            self.clear()
            selected_uid = _WHOLE_CONTEXT_UID
        return FlatSelectionState(
            options=options,
            cursor_uid=self.cursor_uid,
            selected_uid=selected_uid,
            allow_empty=False,
        )

    def clear(self) -> bool:
        """Drop item identity when its exact owning range is no longer shown."""

        changed = self.selected_memory_uid is not None
        self.selected_memory_uid = None
        self.cursor_uid = _WHOLE_CONTEXT_UID
        return changed

    def move(self, delta: int) -> bool:
        state = self.state()
        changed = state.move(delta)
        self.cursor_uid = state.cursor_uid
        return changed

    def enter(self, delta: int) -> None:
        state = self.state()
        self.cursor_uid = state.options[0 if delta > 0 else -1].uid

    def choose(self) -> str | None:
        self.selected_memory_uid = (
            None
            if self.cursor_uid == _WHOLE_CONTEXT_UID
            else self.cursor_uid.removeprefix(_MEMORY_OPTION_PREFIX)
        )
        return self.selected_memory_uid

    def render(
        self,
        *,
        focused: bool,
        include_descendants: bool,
    ) -> list[tuple[str, str]]:
        if include_descendants:
            fragments: list[tuple[str, str]] = []
            if focused:
                fragments.append(("[SetCursorPosition]", ""))
            fragments.append(
                (
                    focused_control_style(focused=focused, selected=True),
                    "✓ WHOLE SUBTREE\n",
                )
            )
            fragments.append(
                (
                    "class:report-neutral",
                    "  Focused Memory requires THIS CONTEXT ONLY.",
                )
            )
            return fragments
        return render_vertical_choice_rows(
            self.state(),
            focused=focused,
            content_width=84,
            numbered=False,
        )
