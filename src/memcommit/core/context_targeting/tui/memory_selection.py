"""Process-local retained selection for exact direct Memory targets."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.core.context_targeting.model import ContextSelectionMode, DirectMemoryTarget


class DirectMemorySelectionState:
    """Keep one or many exact selections independent from the hover cursor.

    MULTIPLE mode intentionally permits an empty staged set.  The composing
    operation owns minimum-cardinality validation when it constructs an exact
    request, matching the shared Context-selection contract.
    """

    def __init__(
        self,
        selected: DirectMemoryTarget | None = None,
        *,
        mode: ContextSelectionMode = "SINGLE",
        selected_targets: Sequence[DirectMemoryTarget] = (),
    ) -> None:
        if mode not in {"SINGLE", "MULTIPLE"}:
            raise ValueError("Direct Memory selection mode must be SINGLE or MULTIPLE.")
        values = list(dict.fromkeys(selected_targets))
        if selected is not None:
            if values:
                raise ValueError(
                    "Use selected or selected_targets, not both, for direct Memory selection."
                )
            values = [selected]
        if any(not isinstance(target, DirectMemoryTarget) for target in values):
            raise TypeError("Direct Memory selection requires typed targets.")
        if mode == "SINGLE" and len(values) > 1:
            raise ValueError("Single direct Memory selection accepts at most one target.")
        self.mode = mode
        self._selected_order = values

    @property
    def multiple(self) -> bool:
        return self.mode == "MULTIPLE"

    @property
    def selected(self) -> DirectMemoryTarget | None:
        """Return the sole selection used by existing single-cardinality callers."""

        if self.multiple:
            raise ValueError("Multiple direct Memory selection has no single target.")
        return self._selected_order[0] if self._selected_order else None

    @property
    def selected_targets(self) -> tuple[DirectMemoryTarget, ...]:
        return tuple(self._selected_order)

    @property
    def selected_set(self) -> frozenset[DirectMemoryTarget]:
        return frozenset(self._selected_order)

    def choose(self, target: DirectMemoryTarget) -> bool:
        if not isinstance(target, DirectMemoryTarget):
            raise TypeError("Direct Memory selection requires a typed target.")
        if self.multiple:
            if target in self._selected_order:
                self._selected_order.remove(target)
            else:
                self._selected_order.append(target)
            return True
        changed = self._selected_order != [target]
        self._selected_order = [target]
        return changed

    def replace(self, targets: Sequence[DirectMemoryTarget]) -> bool:
        values = list(dict.fromkeys(targets))
        if any(not isinstance(target, DirectMemoryTarget) for target in values):
            raise TypeError("Direct Memory selection requires typed targets.")
        if not self.multiple and len(values) > 1:
            raise ValueError("Single direct Memory selection accepts at most one target.")
        changed = values != self._selected_order
        self._selected_order = values
        return changed

    def clear(self) -> bool:
        if not self._selected_order:
            return False
        self._selected_order = []
        return True

    def clear_unless_context(self, context_name: str) -> bool:
        if self.multiple:
            return False
        selected = self.selected
        if selected is None or selected.context_name == context_name:
            return False
        return self.clear()
