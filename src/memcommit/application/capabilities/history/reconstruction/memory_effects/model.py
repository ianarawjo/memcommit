"""Direct changes and independently verified lineage from one command."""

from dataclasses import dataclass, field

from ...model.memory_event import MemoryHistoryEvent, MemoryHistoryRelation


@dataclass
class EffectDerivation:
    events: list[MemoryHistoryEvent] = field(default_factory=list)
    relations: list[MemoryHistoryRelation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
