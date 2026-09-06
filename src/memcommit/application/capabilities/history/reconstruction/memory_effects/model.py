"""Results from one evidence projection, including the differences it explains."""

from dataclasses import dataclass, field

from ...model.memory_event import MemoryHistoryEvent


@dataclass
class EffectDerivation:
    events: list[MemoryHistoryEvent] = field(default_factory=list)
    consumed_before: set[str] = field(default_factory=set)
    consumed_after: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
