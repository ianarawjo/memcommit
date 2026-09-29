"""Validate current candidate Meld effects against retained Target snapshots."""

from typing import Any
from ..frame import _Frame


def _meld_change_evidence(
    *, args: dict[str, Any], before: _Frame, after: _Frame
) -> tuple[dict[str, dict[str, Any]], str | None]:
    record = args.get("meld")
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != 1
        or record.get("contract") != "AUDIT_RESOLVE_UPDATE"
    ):
        return {}, "has an unsupported Meld receipt contract"
    target = record.get("target_baseline")
    if (
        not isinstance(target, dict)
        or target.get("context_uid") != before.context_uid
        or target.get("context_name") != before.context_name
        or (before.context_uid, before.context_name)
        != (after.context_uid, after.context_name)
    ):
        return {}, "has a mismatched Meld Target"
    effects, results = record.get("effects"), record.get("results")
    if (
        not isinstance(effects, list)
        or not isinstance(results, list)
        or results != [{"memory_uid": uid} for uid in after.order]
    ):
        return {}, "has invalid Meld result evidence"
    expected = {uid: memory.content for uid, memory in before.memories.items()}
    by_uid = {}
    for effect in effects:
        if not isinstance(effect, dict) or set(effect) != {
            "kind",
            "memory_uid",
            "old_content",
            "new_content",
        }:
            return {}, "has invalid Meld effects"
        uid, kind = effect["memory_uid"], effect["kind"]
        if not isinstance(uid, str) or uid in by_uid:
            return {}, "has duplicate Meld effects"
        old, new = effect["old_content"], effect["new_content"]
        if (
            kind == "ADD"
            and uid not in expected
            and old == ""
            and isinstance(new, str)
            and new
        ):
            expected[uid] = new
        elif (
            kind == "EDIT"
            and uid in expected
            and old == expected[uid]
            and isinstance(new, str)
            and new
            and old != new
        ):
            expected[uid] = new
        elif (
            kind == "REMOVE" and uid in expected and old == expected[uid] and new == ""
        ):
            del expected[uid]
        else:
            return {}, "has a Meld effect outside its Target snapshot"
        by_uid[uid] = {
            "operation_uid": record.get("operation_uid"),
            "change_set_digest": record.get("change_set_digest"),
            "mode": record.get("mode"),
            "operation": kind,
            "reason": "Verified Audit–Resolve–Update candidate",
            "declared_frame": "",
        }
    if expected != {uid: memory.content for uid, memory in after.memories.items()}:
        return {}, "has incomplete Meld Target effects"
    return by_uid, None


def meld_creation_preimage(entry: dict, after: _Frame) -> _Frame | None:
    """Prove an empty predecessor only for an exact newly created Result."""
    from ..frame import _empty_frame

    args = entry.get("args")
    if (
        entry.get("command") != "meld"
        or entry.get("auto") is not True
        or not isinstance(args, dict)
    ):
        return None
    record = args.get("meld")
    if not isinstance(record, dict) or record.get("target_created") is not True:
        return None
    if args.get("context_creation") != {
        "version": 1,
        "context_uid": after.context_uid,
        "context_name": after.context_name,
    }:
        return None
    before = _empty_frame(after.context_uid, after.context_name)
    _, error = _meld_change_evidence(args=args, before=before, after=after)
    return before if error is None else None
