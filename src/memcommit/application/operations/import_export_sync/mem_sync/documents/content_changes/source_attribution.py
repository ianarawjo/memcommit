"""Validate renderer ownership before reversing external bytes into Memories."""

from collections import defaultdict

from memcommit.application.operations.import_export_sync.mem_sync.model import (
    SyncConflictError,
)
from memcommit.models.memory import Memory


def validate_source_ranges(context, baseline_file, ranges, *, path):
    memories = {
        item.uid: item for item in context.iter_memories() if isinstance(item, Memory)
    }

    def conflict(message):
        raise SyncConflictError(path, message)

    if len(memories) > 2000:
        conflict("Too many Memories for bounded automatic matching.")
    spans_by_uid = defaultdict(list)
    previous_end = 0
    for span in ranges:
        source = span.source
        if (
            type(span.start) is not int
            or type(span.end) is not int
            or not previous_end <= span.start < span.end <= len(baseline_file)
            or source.context_uid != context.uid
            or source.context_name != context.name
            or source.memory_uid not in memories
        ):
            conflict("Baseline emission ownership is invalid.")
        memory_bytes = memories[source.memory_uid].content.encode("utf-8")
        if (
            type(source.start) is not int
            or type(source.end) is not int
            or not 0 <= source.start < source.end <= len(memory_bytes)
            or memory_bytes[source.start : source.end]
            != baseline_file[span.start : span.end]
        ):
            conflict("Baseline source bytes do not match their Memory.")
        previous_end = span.end
        spans_by_uid[source.memory_uid].append(span)
    if set(spans_by_uid) != set(memories):
        conflict("A Memory has no reversible emitted content.")
    return memories, spans_by_uid
