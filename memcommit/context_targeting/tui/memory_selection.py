"""Process-local retained selection for one exact direct Memory target."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.context_targeting.model import DirectMemoryTarget


@dataclass
class DirectMemorySelectionState:
    """Keep semantic selection independent from a Memory-row hover cursor."""

    selected: DirectMemoryTarget | None = None

    def choose(self, target: DirectMemoryTarget) -> bool:
        if not isinstance(target, DirectMemoryTarget):
            raise TypeError("Direct Memory selection requires a typed target.")
        changed = self.selected != target
        self.selected = target
        return changed

    def clear(self) -> bool:
        if self.selected is None:
            return False
        self.selected = None
        return True

    def clear_unless_context(self, context_name: str) -> bool:
        if self.selected is None or self.selected.context_name == context_name:
            return False
        return self.clear()
