"""Validate source-occurrence evidence retained by historical Add records."""

from __future__ import annotations

import hashlib
from typing import Any

from ..frame import _Frame
from ..model import MemoryHistoryEvidence, SourceOccurrence


def _source_occurrences(
    *,
    args: dict[str, Any],
    after: _Frame,
    added_uids: set[str],
) -> dict[str, tuple[SourceOccurrence, MemoryHistoryEvidence]]:
    if not added_uids:
        return {}
    added = [uid for uid in after.order if uid in added_uids]
    source = args.get("source")
    if not isinstance(source, dict):
        return {}
    mode = args.get("mode")
    mode = mode if isinstance(mode, str) and mode else "single"
    declared_uids = args.get("memory_uids")
    raw_text = source.get("raw_text")
    declared_hash = source.get("sha256")
    source_integrity = (
        isinstance(raw_text, str)
        and isinstance(declared_hash, str)
        and hashlib.sha256(raw_text.encode("utf-8")).hexdigest() == declared_hash
    )
    explicit = (
        isinstance(declared_uids, list)
        and all(isinstance(uid, str) for uid in declared_uids)
        and len(declared_uids) == len(set(declared_uids))
        and declared_uids == added
        and source_integrity
    )
    ordered = list(declared_uids) if explicit else added

    raw_records: list[tuple[int, str]] = []
    if source_integrity:
        raw_records = [
            (line_number, raw_line)
            for line_number, raw_line in enumerate(raw_text.splitlines(), 1)
            if raw_line.strip()
        ]
    contents = args.get("contents")
    normalized_contents = contents if isinstance(contents, list) else None
    total_value = args.get("count")
    total = (
        total_value
        if isinstance(total_value, int) and total_value > 0
        else len(ordered)
    )

    result: dict[str, tuple[SourceOccurrence, MemoryHistoryEvidence]] = {}
    for index, uid in enumerate(ordered):
        if uid not in after.memories:
            continue
        line_number: int | None = None
        raw_line: str | None = None
        exact_raw_source = False
        if len(raw_records) == len(ordered):
            candidate_line_number, candidate_raw_line = raw_records[index]
            if candidate_raw_line.strip() == after.memories[uid].content:
                line_number = candidate_line_number
                raw_line = candidate_raw_line
                exact_raw_source = explicit
        elif (
            normalized_contents is not None
            and len(normalized_contents) == len(ordered)
            and normalized_contents[index] == after.memories[uid].content
        ):
            raw_line = normalized_contents[index]

        result[uid] = (
            SourceOccurrence(
                mode=mode,
                ordinal=index + 1,
                total=total,
                line_number=line_number,
                raw_line=raw_line,
                exact_raw_source=exact_raw_source,
            ),
            "RECORDED" if explicit else "RECONSTRUCTED",
        )
    return result
