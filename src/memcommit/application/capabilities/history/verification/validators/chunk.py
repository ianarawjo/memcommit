"""Validate and replay mechanical Chunk boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.chunk.domain import chunk_content

from ..checkpoint import _checkpoint_fields
from ..frame import _Frame


def _checkpoint_chunk_options(args: dict) -> dict[str, object] | None:
    options: dict[str, object] = {}
    if "break_on" in args:
        break_on = args.get("break_on")
        if not isinstance(break_on, str) or not break_on:
            return None
        options["break_on"] = break_on
    for key in ("min_chars", "max_chars"):
        if key not in args:
            continue
        value = args.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        options[key] = value
    min_chars = options.get("min_chars")
    max_chars = options.get("max_chars")
    if (
        isinstance(min_chars, int)
        and isinstance(max_chars, int)
        and min_chars > max_chars
    ):
        return None
    return options


def _replay_checkpoint_chunk(
    content: str,
    method: str,
    args: dict,
) -> list[str]:
    """Replay every authored mechanical boundary recorded by Chunk."""

    return chunk_content(
        content,
        method,
        break_on=args.get("break_on"),
        min_chars=args.get("min_chars"),
        max_chars=args.get("max_chars"),
    )


@dataclass(frozen=True)
class ChunkEvidence:
    splits: tuple[tuple[str, tuple[str, ...]], ...]
    method: str
    recorded: bool


def verify_legacy_chunk(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
) -> ChunkEvidence | None:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    if command != "chunk":
        return None
    source_uid = args.get("uid")
    method = args.get("method")
    if (
        not isinstance(source_uid, str)
        or source_uid not in before.memories
        or removed != {source_uid}
        or not added
        or not isinstance(method, str)
    ):
        return None
    options = _checkpoint_chunk_options(args)
    if options is None:
        return None

    children = [after.memories[uid] for uid in after.order if uid in added]
    source_position = before.order.index(source_uid)
    child_positions = [child.position for child in children]
    if child_positions != list(range(source_position, source_position + len(children))):
        return None
    before_without_source = [uid for uid in before.order if uid != source_uid]
    after_without_children = [uid for uid in after.order if uid not in added]
    if before_without_source != after_without_children:
        return None
    try:
        expected_contents = _replay_checkpoint_chunk(
            before.memories[source_uid].content,
            method,
            args,
        )
    except ValueError:
        return None
    if expected_contents != [child.content for child in children]:
        return None

    return ChunkEvidence(
        ((source_uid, tuple(child.uid for child in children)),), method, False
    )


def verify_context_chunk(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
) -> ChunkEvidence | None:
    """Validate a Context-scoped chunk checkpoint without content guessing."""

    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    records = args.get("splits")
    method = args.get("method")
    if command != "chunk" or not isinstance(records, list) or not records:
        return None
    if not isinstance(method, str):
        return None
    options = _checkpoint_chunk_options(args)
    if options is None:
        return None

    parsed: list[tuple[str, tuple[str, ...]]] = []
    source_uids: set[str] = set()
    chunk_uids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"uid", "chunk_uids"}:
            return None
        source_uid = record.get("uid")
        children = record.get("chunk_uids")
        if (
            not isinstance(source_uid, str)
            or source_uid in source_uids
            or source_uid not in before.memories
            or not isinstance(children, list)
            or len(children) < 2
            or not all(isinstance(uid, str) for uid in children)
            or len(children) != len(set(children))
            or any(uid in chunk_uids for uid in children)
        ):
            return None
        child_uids = tuple(children)
        source_uids.add(source_uid)
        chunk_uids.update(child_uids)
        parsed.append((source_uid, child_uids))

    if removed != source_uids or added != chunk_uids:
        return None
    replacements = dict(parsed)
    expected_after_order: list[str] = []
    for uid in before.order:
        expected_after_order.extend(replacements.get(uid, (uid,)))
    if tuple(expected_after_order) != after.order:
        return None

    for source_uid, child_uids in parsed:
        try:
            expected_contents = _replay_checkpoint_chunk(
                before.memories[source_uid].content,
                method,
                args,
            )
        except ValueError:
            return None
        children = tuple(after.memories.get(uid) for uid in child_uids)
        if any(child is None for child in children) or expected_contents != [
            child.content for child in children if child is not None
        ]:
            return None
    # Context Chunk is one structural operation. Publish its relations only
    # after every split replays exactly; a valid prefix is not enough evidence.
    return ChunkEvidence(tuple(parsed), method, True)
