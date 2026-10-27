"""Map bounded, unambiguous document edits to existing Memory identities."""

from collections import Counter
from difflib import SequenceMatcher

from memcommit.application.operations.import_export_sync.common.formats import (
    markdown,
)
from memcommit.application.operations.import_export_sync.mem_sync.model import (
    InboundContextChange,
    SyncConflictError,
    SyncMemoryEffect,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)

from .source_attribution import validate_source_ranges


def import_document_changes(context, baseline_file, external_bytes, ranges, *, path):
    """Return a proposal only; exact shared re-rendering is required by the caller.

    Whole unchanged Memories anchor the alignment. Only one old Memory may own
    a changed gap; positional pairing across multiple owners is never evidence
    of identity. Unique exact whole-Memory moves are independently recognizable.
    """

    def conflict(message):
        raise SyncConflictError(path, message)

    if len(external_bytes) > 2_000_000 or len(baseline_file) > 2_000_000:
        conflict("Document exceeds the bounded automatic matching limit.")
    try:
        external_text = external_bytes.decode("utf-8")
    except UnicodeError:
        conflict("External changes require UTF-8 text.")
    state = context.corresponding_document_metadata or CorrespondingDocumentMetadata(
        path, "md"
    )
    if state.role != "document":
        conflict("Inbound Sync requires an ordinary Markdown document.")
    external_blocks = markdown.parse_markdown(
        external_text, path=path, state=state
    ).blocks
    if len(external_blocks) > 2000:
        conflict("Too many blocks for bounded automatic matching.")

    memories, spans_by_uid = validate_source_ranges(
        context, baseline_file, ranges, path=path
    )

    old_uids = list(memories)
    footprints = {
        uid: baseline_file[spans[0].start : spans[-1].end]
        for uid, spans in spans_by_uid.items()
    }
    footprint_counts = Counter(footprints.values())
    blocks = list(external_blocks)
    if len(memories) * len(blocks) > 100_000:
        conflict("Document exceeds the bounded identity candidate budget.")
    # Candidates start at real parser boundaries, and must finish at a complete
    # block (apart from its whitespace suffix). A substring match is insufficient.
    candidates = {}
    for uid, raw in footprints.items():
        matches = []
        for first, block in enumerate(blocks):
            start = block.start_byte
            if not external_bytes.startswith(raw, start):
                continue
            end = start + len(raw)
            last = next(
                (
                    index
                    for index in range(first, len(blocks))
                    if blocks[index].end_byte >= end
                ),
                None,
            )
            if (
                last is not None
                and not external_bytes[end : blocks[last].end_byte].strip()
            ):
                matches.append((first, last + 1, start, end))
        candidates[uid] = matches
    anchors = {
        uid: matches[0]
        for uid, matches in candidates.items()
        if len(matches) == 1 and footprint_counts[footprints[uid]] == 1
    }
    occupied = set()
    for first, last, _, _ in anchors.values():
        if occupied.intersection(range(first, last)):
            conflict("Unchanged Memory ranges overlap.")
        occupied.update(range(first, last))

    ordered_anchors = sorted(anchors, key=lambda uid: anchors[uid][0])
    original_anchors = [uid for uid in old_uids if uid in anchors]
    if ordered_anchors != original_anchors:
        if len(anchors) != len(old_uids) or len(occupied) != len(blocks):
            conflict("Combining a reorder with unmatched changes is ambiguous.")

    proposed = Context.from_dict(context.to_dict())
    effects = []
    result_uids = []

    def append_unchanged_gap(gap_uids, first, last):
        cursor = first
        for uid in gap_uids:
            matching = [
                match
                for match in candidates[uid]
                if match[0] == cursor and match[1] <= last
            ]
            if len(matching) != 1:
                return False
            cursor = matching[0][1]
        return cursor == last

    def apply_gap(gap_uids, first, last):
        new_blocks = blocks[first:last]
        if append_unchanged_gap(gap_uids, first, last):
            result_uids.extend(gap_uids)
            return
        if not new_blocks:
            for uid in gap_uids:
                proposed.remove(uid)
                effects.append(SyncMemoryEffect(context.name, uid, "REMOVE"))
            return

        def replace_with_new_memories():
            for uid in gap_uids:
                proposed.remove(uid)
                effects.append(SyncMemoryEffect(context.name, uid, "REMOVE"))
            for block in new_blocks:
                memory = proposed.add(Memory.create(block.text))
                result_uids.append(memory.uid)
                effects.append(SyncMemoryEffect(context.name, memory.uid, "ADD"))

        if not gap_uids:
            replace_with_new_memories()
            return
        if len(gap_uids) != 1:
            if len(new_blocks) == 1:
                # A merged Memory has a new identity, not an arbitrarily chosen owner.
                replace_with_new_memories()
                return
            conflict(
                "Changed interval crosses several Memory owners; resolve explicitly."
            )
        uid = gap_uids[0]
        original_blocks = markdown.parse_markdown(
            footprints[uid].decode("utf-8"), path=path, state=state
        ).blocks
        if len(original_blocks) != len(new_blocks):
            # Splitting must not give the old identity to an arbitrary fragment.
            replace_with_new_memories()
            return
        replacement = external_bytes[new_blocks[0].start_byte : new_blocks[-1].end_byte]
        old_rendered = footprints[uid]
        if last < len(blocks) and not old_rendered.endswith(b"\n"):
            replacement = replacement.rstrip(b"\r\n")
        source_bytes = memories[uid].content.encode("utf-8")
        patches = []
        common_prefix = 0
        while (
            common_prefix < min(len(old_rendered), len(replacement))
            and old_rendered[common_prefix] == replacement[common_prefix]
        ):
            common_prefix += 1
        old_limit, new_limit = len(old_rendered), len(replacement)
        while (
            old_limit > common_prefix
            and new_limit > common_prefix
            and old_rendered[old_limit - 1] == replacement[new_limit - 1]
        ):
            old_limit -= 1
            new_limit -= 1
        if (old_limit - common_prefix) * (new_limit - common_prefix) > 4_000_000:
            conflict("Changed Memory exceeds the bounded alignment budget.")
        for tag, old_start, old_end, new_start, new_end in SequenceMatcher(
            None,
            old_rendered[common_prefix:old_limit],
            replacement[common_prefix:new_limit],
            autojunk=False,
        ).get_opcodes():
            if tag == "equal":
                continue
            old_start += common_prefix
            old_end += common_prefix
            new_start += common_prefix
            new_end += common_prefix
            absolute_start = spans_by_uid[uid][0].start + old_start
            absolute_end = spans_by_uid[uid][0].start + old_end
            owners = [
                span
                for span in spans_by_uid[uid]
                if span.start <= absolute_start <= absolute_end <= span.end
            ]
            if len(owners) != 1:
                conflict("Changed formatting has no reversible Memory source range.")
            owner = owners[0]
            patches.append(
                (
                    owner.source.start + absolute_start - owner.start,
                    owner.source.start + absolute_end - owner.start,
                    replacement[new_start:new_end],
                )
            )
        for start, end, inserted in reversed(patches):
            source_bytes = source_bytes[:start] + inserted + source_bytes[end:]
        try:
            content = source_bytes.decode("utf-8")
        except UnicodeError:
            conflict("Changed byte ranges do not form complete UTF-8 text.")
        proposed.replace_memory(Memory(uid, content))
        result_uids.append(uid)
        effects.append(SyncMemoryEffect(context.name, uid, "EDIT"))

    if ordered_anchors != original_anchors:
        result_uids = ordered_anchors
    else:
        old_cursor = new_cursor = 0
        for uid in ordered_anchors:
            old_index = old_uids.index(uid)
            first, last, _, _ = anchors[uid]
            apply_gap(old_uids[old_cursor:old_index], new_cursor, first)
            result_uids.append(uid)
            old_cursor, new_cursor = old_index + 1, last
        apply_gap(old_uids[old_cursor:], new_cursor, len(blocks))

    retained = [uid for uid in old_uids if uid in result_uids]
    # The closed Memory-only frame has no opaque slots to preserve around this order.
    proposed.order = result_uids
    if retained != [uid for uid in result_uids if uid in memories]:
        effects.append(SyncMemoryEffect(context.name, None, "REORDER"))
    return InboundContextChange(
        context.to_dict(), proposed.to_dict(), (path,), tuple(effects)
    )
