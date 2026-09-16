"""Validate legacy and derived-Context translation receipts against snapshots."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from memcommit.application.operations.translate.runtime import (
    TRANSLATION_TARGET_CHAR_LIMIT,
)
from memcommit.persistence.store import context_record_digest

from ..checkpoint import _checkpoint_fields
from ..frame import _Frame


@dataclass(frozen=True)
class TranslationEvidence:
    schema_version: int
    operation_uid: str
    target_language: str
    pairs: tuple[tuple[str, str], ...]


def verify_translation(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
    changed: set[str],
) -> tuple[TranslationEvidence | None, list[str]]:
    """Validate legacy sibling copies or derived-Context replacements."""
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    if command != "translate":
        return None, []

    def valid_digest(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    operation_uid = args.get("operation_uid")
    target_language = args.get("target_language")
    source_context = args.get("source_context")
    destination_context = args.get("destination_context")
    scope = args.get("scope")
    response_digest = args.get("provider_response_sha256")
    records = args.get("translations")
    schema_version = args.get("schema_version")
    required_keys = {
        "schema_version",
        "operation_uid",
        "target_language",
        "source_context",
        "scope",
        "provider_response_sha256",
        "translations",
    }
    if schema_version == 2:
        required_keys.add("destination_context")
    valid = (
        set(args) == required_keys
        and schema_version in {1, 2}
        and isinstance(operation_uid, str)
        and isinstance(target_language, str)
        and bool(target_language.strip())
        # History validation must accept the same semantic target that the
        # translation boundary accepted.  A second, shorter limit here would
        # make a valid checkpoint look unrecorded merely because its audience
        # or terminology guidance was descriptive.
        and len(target_language) <= TRANSLATION_TARGET_CHAR_LIMIT
        and all(character.isprintable() for character in target_language)
        and isinstance(source_context, dict)
        and set(source_context) == {"uid", "name", "digest"}
        and isinstance(source_context.get("uid"), str)
        and bool(source_context.get("uid"))
        and isinstance(source_context.get("name"), str)
        and bool(source_context.get("name"))
        and valid_digest(source_context.get("digest"))
        and isinstance(scope, dict)
        and valid_digest(response_digest)
        and isinstance(records, list)
        and bool(records)
        and not changed
    )
    if valid and schema_version == 1:
        valid = (
            source_context.get("uid") == before.context_uid
            and source_context.get("name") == before.context_name
            and source_context.get("digest") == before.record_digest
            and not removed
        )
    elif valid and schema_version == 2:
        normalized_source_record = {
            **before.record,
            "uid": source_context.get("uid"),
            "name": source_context.get("name"),
        }
        valid = (
            isinstance(destination_context, dict)
            and set(destination_context) == {"uid", "name", "baseline_digest"}
            and destination_context.get("uid") == before.context_uid
            and destination_context.get("name") == before.context_name
            and valid_digest(destination_context.get("baseline_digest"))
            and destination_context.get("baseline_digest") == before.record_digest
            and source_context.get("uid") != before.context_uid
            and source_context.get("name") != before.context_name
            and source_context.get("digest")
            == context_record_digest(normalized_source_record)
        )
    try:
        uuid.UUID(operation_uid if isinstance(operation_uid, str) else "")
    except ValueError:
        valid = False

    parsed: list[tuple[str, str]] = []
    if valid:
        for record in records:
            if not isinstance(record, dict) or set(record) != {
                "source_uid",
                "result_uid",
                "source_sha256",
                "result_sha256",
            }:
                valid = False
                break
            source_uid = record.get("source_uid")
            result_uid = record.get("result_uid")
            source_digest = record.get("source_sha256")
            result_digest = record.get("result_sha256")
            common_invalid = (
                not isinstance(source_uid, str)
                or not isinstance(result_uid, str)
                or source_uid == result_uid
                or source_uid not in before.memories
                or result_uid in before.memories
                or result_uid not in after.memories
                or not valid_digest(source_digest)
                or not valid_digest(result_digest)
                or before.memories[source_uid].content_digest != source_digest
                or after.memories[result_uid].content_digest != result_digest
            )
            version_invalid = (
                (
                    source_uid not in after.memories
                    or before.memories[source_uid].content
                    != after.memories[source_uid].content
                )
                if schema_version == 1
                else source_uid in after.memories
            )
            if common_invalid or version_invalid:
                valid = False
                break
            parsed.append((source_uid, result_uid))

    source_uids = [source_uid for source_uid, _ in parsed]
    result_uids = [result_uid for _, result_uid in parsed]
    if valid and (
        len(source_uids) != len(set(source_uids))
        or len(result_uids) != len(set(result_uids))
        or set(source_uids) & set(result_uids)
    ):
        valid = False
    if valid and schema_version == 1:
        after_memories = after.record.get("memories")
        after_order = after.record.get("order")
        before_order = before.record.get("order")
        after_without_results = (
            {
                **after.record,
                "memories": {
                    uid: item
                    for uid, item in after_memories.items()
                    if uid not in set(result_uids)
                },
                "order": [uid for uid in after_order if uid not in set(result_uids)],
            }
            if (
                isinstance(after_memories, dict)
                and isinstance(after_order, list)
                and isinstance(before_order, list)
            )
            else None
        )
        valid = (
            set(result_uids) == added
            and after_without_results == before.record
            and [uid for uid in after.order if uid not in set(result_uids)]
            == list(before.order)
            and all(
                after.order.index(result_uid) == after.order.index(source_uid) + 1
                for source_uid, result_uid in parsed
            )
        )
    elif valid and schema_version == 2:
        before_memories = before.record.get("memories")
        before_order = before.record.get("order")
        after_memories = after.record.get("memories")
        source_to_result = dict(parsed)
        expected_memories = (
            {
                source_to_result.get(uid, uid): (
                    after_memories[source_to_result[uid]]
                    if uid in source_to_result
                    else item
                )
                for uid, item in before_memories.items()
            }
            if (
                isinstance(before_memories, dict)
                and isinstance(before_order, list)
                and isinstance(after_memories, dict)
            )
            else None
        )
        expected_after = (
            {
                **before.record,
                "memories": expected_memories,
                "order": [source_to_result.get(uid, uid) for uid in before_order],
            }
            if expected_memories is not None
            else None
        )
        valid = (
            set(source_uids) == removed
            and set(result_uids) == added
            and expected_after == after.record
        )
    if valid and scope == {"kind": "all"} and source_uids == list(before.order):
        pass
    elif (
        valid
        and isinstance(scope, dict)
        and set(scope) == {"kind", "memory_uid"}
        and scope.get("kind") == "memory"
        and len(source_uids) == 1
        and scope.get("memory_uid") == source_uids[0]
    ):
        pass
    else:
        valid = False

    if not valid:
        return (
            None,
            [
                f"Checkpoint [{checkpoint_uid[:8]}] has invalid translation "
                "lineage metadata; snapshot differences were used instead."
            ],
        )

    return TranslationEvidence(
        schema_version=schema_version,
        operation_uid=operation_uid,
        target_language=target_language,
        pairs=tuple(parsed),
    ), []
