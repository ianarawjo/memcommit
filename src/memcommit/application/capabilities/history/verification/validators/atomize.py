"""Validate retained Atomize lineage and reviewed evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any
import uuid

from ..frame import _Frame, _frame_from_snapshot
from ..model import (
    MemoryHistoryChildEvidence,
    TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION,
    TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
    TRACE_METADATA_SCHEMA_VERSION,
)


def _atomize_save_as_source_frame(
    args: dict[str, Any],
    after: _Frame,
) -> _Frame | None:
    """Recover the non-published branch baseline retained for History only."""

    receipt = args.get("atomize_save_as")
    if not isinstance(receipt, dict) or receipt.get("version") != 1:
        return None
    raw_frame = receipt.get("source_frame")
    declared_digest = receipt.get("source_frame_digest")
    if not isinstance(raw_frame, list) or not isinstance(declared_digest, str):
        return None
    ordered: list[dict[str, object]] = []
    seen: set[str] = set()
    for position, item in enumerate(raw_frame):
        if (
            not isinstance(item, dict)
            or set(item) != {"uid", "content", "position"}
            or not isinstance(item.get("uid"), str)
            or not isinstance(item.get("content"), str)
            or item.get("position") != position
            or item["uid"] in seen
        ):
            return None
        seen.add(item["uid"])
        ordered.append(item)
    actual_digest = hashlib.sha256(
        json.dumps(
            [{"uid": item["uid"], "content": item["content"]} for item in ordered],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if actual_digest != declared_digest:
        return None
    return _frame_from_snapshot(
        {
            "uid": after.context_uid,
            "name": after.context_name,
            "memories": {
                item["uid"]: {
                    "type": "memory",
                    "uid": item["uid"],
                    "content": item["content"],
                }
                for item in ordered
            },
            "order": [item["uid"] for item in ordered],
        },
        label="Atomize Save As Source frame",
    )


def _history_change_matches_snapshot(
    *,
    kind: str,
    source_uids: list[str],
    result_uids: list[str],
    before: _Frame,
    after: _Frame,
) -> bool:
    """Validate the structural claim made by one explicit lineage record.

    Explicit metadata is stronger evidence than a snapshot diff, so mere UID
    presence is not enough.  Each relation must describe the transition its
    name promises; otherwise a corrupt checkpoint could suppress the ordinary
    diff events by falsely consuming their UIDs.
    """
    if len(source_uids) != len(set(source_uids)) or len(result_uids) != len(
        set(result_uids)
    ):
        return False

    source_set = set(source_uids)
    result_set = set(result_uids)
    if kind in {"KEEP", "PRESERVE"}:
        if (
            len(source_uids) != 1
            or result_uids != source_uids
            or source_uids[0] not in before.memories
            or source_uids[0] not in after.memories
        ):
            return False
        uid = source_uids[0]
        return before.memories[uid].content == after.memories[uid].content

    if kind == "SPLIT":
        return (
            len(source_uids) == 1
            and bool(result_uids)
            and source_set.isdisjoint(result_set)
            and source_set <= set(before.memories)
            and source_set.isdisjoint(after.memories)
            and result_set <= set(after.memories)
            and result_set.isdisjoint(before.memories)
        )

    if kind == "ABSORB":
        if (
            len(source_uids) < 2
            or len(result_uids) != 1
            or not source_set <= set(before.memories)
        ):
            return False
        result_uid = result_uids[0]
        if result_uid not in after.memories:
            return False

        if result_uid in source_set:
            # Dedup-style absorption normally retains one stable source UID.
            # Its wording remains intact; every other named source disappears.
            if (
                result_uid not in before.memories
                or before.memories[result_uid].content
                != after.memories[result_uid].content
            ):
                return False
            absorbed = source_set - {result_uid}
        else:
            # Integration may instead create one fresh result, in which case
            # every source disappears from the resulting snapshot.
            if result_uid in before.memories:
                return False
            absorbed = source_set
        return absorbed.isdisjoint(after.memories)

    return False


def _atomize_evidence(
    record: dict,
    *,
    schema_version: int,
    kind: str,
    source_uids: list[str],
    result_uids: list[str],
    before: _Frame,
    args: dict,
) -> tuple[tuple[MemoryHistoryChildEvidence, ...], dict[str, str] | None] | None:
    """Validate optional reviewed evidence without weakening lineage checks."""
    expected_record_keys = {
        "kind",
        "classification",
        "source_uids",
        "result_uids",
        "reason",
        "reason_codes",
        "child_evidence",
        "review_evidence",
    }
    if schema_version == TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION:
        expected_record_keys.add("result_contents")
    if set(record) != expected_record_keys:
        return None
    classification = record["classification"]
    expected_kind = {
        "ATOMIC": "KEEP",
        "COMPOSITE": "SPLIT",
        "UNCERTAIN": "PRESERVE",
        "NON_PROPOSITIONAL": "PRESERVE",
    }
    if schema_version not in {
        TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
        TRACE_METADATA_SCHEMA_VERSION,
        TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION,
    }:
        return None
    if (
        not isinstance(classification, str)
        or expected_kind.get(classification) != kind
        or len(source_uids) != 1
        or source_uids[0] not in before.memories
    ):
        return None

    raw_children = record["child_evidence"]
    if (
        not isinstance(raw_children, list)
        or (kind == "SPLIT" and len(raw_children) != len(result_uids))
        or (kind != "SPLIT" and raw_children)
    ):
        return None
    source_content = before.memories[source_uids[0]].content
    parsed_children: list[MemoryHistoryChildEvidence] = []
    for index, value in enumerate(raw_children):
        if not isinstance(value, dict) or set(value) != {
            "result_uid",
            "source_spans",
            "frame_spans",
        }:
            return None
        result_uid = value["result_uid"]
        source_spans = value["source_spans"]
        frame_spans = value["frame_spans"]
        if (
            result_uid != result_uids[index]
            or not isinstance(source_spans, list)
            or not source_spans
            or any(
                not isinstance(span, str) or not span or span not in source_content
                for span in source_spans
            )
            or len(set(source_spans)) != len(source_spans)
            or not isinstance(frame_spans, list)
            or any(not isinstance(span, str) or not span for span in frame_spans)
            or len(set(frame_spans)) != len(frame_spans)
        ):
            return None
        parsed_children.append(
            MemoryHistoryChildEvidence(
                result_uid=result_uid,
                source_spans=tuple(source_spans),
                frame_spans=tuple(frame_spans),
            )
        )

    raw_review = record["review_evidence"]
    if raw_review is None:
        if any(child.frame_spans for child in parsed_children):
            return None
        return tuple(parsed_children), None
    if not isinstance(raw_review, dict) or set(raw_review) != {
        "review_uid",
        "response_digest",
        "memory_uid",
        "review_item_uid",
        "source_analysis_uid",
        "uncertainty_reason",
        "text",
        "digest",
    }:
        return None
    review_uid = raw_review["review_uid"]
    response_digest = raw_review["response_digest"]
    memory_uid = raw_review["memory_uid"]
    review_item_uid = raw_review["review_item_uid"]
    source_analysis_uid = raw_review["source_analysis_uid"]
    uncertainty_reason = raw_review["uncertainty_reason"]
    text = raw_review["text"]
    digest = raw_review["digest"]
    if not all(
        isinstance(value, str)
        for value in (
            memory_uid,
            review_item_uid,
            source_analysis_uid,
            uncertainty_reason,
            text,
        )
    ):
        return None
    if schema_version == TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION:
        valid_review_item = review_item_uid == memory_uid
        expected_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    else:
        from memcommit.application.operations.semantic_updates.derive.atomize.domain import (
            atomize_declared_frame_digest,
        )

        valid_review_item = review_item_uid in {
            memory_uid,
            f"ambiguity:{memory_uid}",
            f"atomize:{memory_uid}",
        }
        expected_digest = atomize_declared_frame_digest(
            memory_uid=memory_uid,
            review_item_uid=review_item_uid,
            source_analysis_uid=source_analysis_uid,
            uncertainty_reason=uncertainty_reason,
            text=text,
        )
    if (
        not isinstance(review_uid, str)
        or not isinstance(response_digest, str)
        or memory_uid != source_uids[0]
        or not valid_review_item
        or not uncertainty_reason.strip()
        or not text.strip()
        or not isinstance(digest, str)
        or digest != expected_digest
        or len(response_digest) != 64
        or any(character not in "0123456789abcdef" for character in response_digest)
        or args.get("source_review_uid") != review_uid
        or args.get("source_review_digest") != response_digest
        or not isinstance(args.get("analysis_uid"), str)
        or args.get("analysis_uid") == source_analysis_uid
        or any(
            span not in text for child in parsed_children for span in child.frame_spans
        )
    ):
        return None
    try:
        uuid.UUID(review_uid)
        uuid.UUID(source_analysis_uid)
    except ValueError:
        return None
    return (
        tuple(parsed_children),
        {
            "review_uid": review_uid,
            "response_digest": response_digest,
            "source_analysis_uid": source_analysis_uid,
            "uncertainty_reason": uncertainty_reason,
            "text": text,
            "digest": digest,
        },
    )
