"""Process-local selection of already loaded owner/Memory pairs."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_targeting.model import ContextSelectionMode


class DirectMemorySelectionState:
    """Keep one or many loaded selections independent from the hover cursor."""

    def __init__(
        self,
        selected: tuple[Context, Memory] | None = None,
        *,
        mode: ContextSelectionMode = "SINGLE",
        selected_targets: Sequence[tuple[Context, Memory]] = (),
    ) -> None:
        if mode not in {"SINGLE", "MULTIPLE"}:
            raise ValueError("Direct Memory selection mode must be SINGLE or MULTIPLE.")
        if selected is not None and selected_targets:
            raise ValueError("Use selected or selected_targets, not both.")
        self.mode = mode
        self._selected: dict[tuple[str, str], tuple[Context, Memory]] = {}
        self.replace((selected,) if selected is not None else selected_targets)

    @property
    def multiple(self) -> bool:
        return self.mode == "MULTIPLE"

    @property
    def selected(self) -> tuple[Context, Memory] | None:
        if self.multiple:
            raise ValueError("Multiple direct Memory selection has no single target.")
        return next(iter(self._selected.values()), None)

    @property
    def selected_targets(self) -> tuple[tuple[Context, Memory], ...]:
        return tuple(self._selected.values())

    def choose(self, target: tuple[Context, Memory]) -> bool:
        context, memory = target
        key = context.uid, memory.uid
        if self.multiple:
            if key in self._selected:
                del self._selected[key]
            else:
                self._selected[key] = target
            return True
        changed = tuple(self._selected) != (key,)
        self._selected = {key: target}
        return changed

    def replace(self, targets: Sequence[tuple[Context, Memory]]) -> bool:
        values = {
            (context.uid, memory.uid): (context, memory) for context, memory in targets
        }
        if not self.multiple and len(values) > 1:
            raise ValueError(
                "Single direct Memory selection accepts at most one target."
            )
        changed = tuple(values) != tuple(self._selected)
        self._selected = values
        return changed

    def clear(self) -> bool:
        changed = bool(self._selected)
        self._selected.clear()
        return changed

    def clear_unless_context(self, context_name: str) -> bool:
        if self.multiple:
            return False
        selected = self.selected
        if selected is None or selected[0].name == context_name:
            return False
        return self.clear()
