"""Validate, rewrite, and digest persisted Context records."""

from __future__ import annotations
import copy
import hashlib
import json
from memcommit.application.retained_history.checkpoint_frames import (
    map_restorable_checkpoint_frames,
)
from memcommit.core.context import Context, MemoryRef
from memcommit.core.context_targeting.naming import (
    RESERVED_CONTEXT_SEGMENTS,
)


def canonical_context_record(
    value: Context | dict[str, object],
) -> dict[str, object]:
    """Return the canonical logical direct record used for persistence CAS."""
    if isinstance(value, Context):
        return value.to_dict()
    # Non-resolving deserialization preserves every pointer while normalizing
    # supported legacy omissions such as a missing explicit order list.
    return Context.from_dict(value).to_dict()


def context_record_digest(value: Context | dict[str, object]) -> str:
    """Hash one complete logical direct Context record canonically."""
    record = canonical_context_record(value)
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def checkpoint_history_digest(entries: list[dict]) -> str:
    """Hash one newest-first physical checkpoint frame canonically."""
    try:
        encoded = json.dumps(
            entries,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("Checkpoint history contains invalid data.") from error
    return hashlib.sha256(encoded).hexdigest()


def _context_name_parts(name: str) -> tuple[str, ...]:
    """Validate a Context name and return its POSIX namespace segments."""
    if not isinstance(name, str) or not name:
        raise ValueError("Context name must be a non-empty relative path.")
    if "\\" in name:
        raise ValueError(
            f"Invalid context name '{name}': use '/' as the namespace separator."
        )
    if ":" in name:
        raise ValueError(
            f"Invalid context name '{name}': ':' is not allowed in context names."
        )

    parts = tuple(name.split("/"))
    if any(part == "" for part in parts):
        raise ValueError(
            f"Invalid context name '{name}': leading, trailing, or repeated '/' "
            "is not allowed."
        )
    if any(part in {".", ".."} for part in parts):
        raise ValueError(
            f"Invalid context name '{name}': '.' and '..' segments are not allowed."
        )
    reserved = [part for part in parts if part.casefold() in RESERVED_CONTEXT_SEGMENTS]
    if reserved:
        raise ValueError(
            f"Invalid context name '{name}': '{reserved[0]}' is reserved for "
            "Context storage."
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError(
            f"Invalid context name '{name}': control characters are not allowed."
        )
    return parts


def validate_context_name(name: str) -> str:
    """Return one valid canonical Context name without touching storage.

    Context identity is a slash-delimited namespace, so this deliberately
    shares the storage layer's lexical validation instead of the flatter
    naming rules used by Ground sessions.  Availability and filesystem safety
    remain separate checks performed by ``assert_context_creatable``.
    """
    _context_name_parts(name)
    return name


def _mapped_context_name(name: str, old_root: str, new_root: str) -> str | None:
    """Return the slash-boundary prefix mapping, or ``None`` when unrelated."""
    if name == old_root:
        return new_root
    prefix = old_root + "/"
    if name.startswith(prefix):
        return new_root + name[len(old_root) :]
    return None


def _rewrite_context_pointers(
    record: dict[str, object],
    *,
    moved_names_by_uid: dict[str, tuple[str, str]],
    rewrite_owner_name: bool,
    require_current_pointer_names: bool,
) -> tuple[dict[str, object], int, tuple[str, ...]]:
    """Rewrite typed ordinary pointers by UID without touching prose/query refs.

    ``require_current_pointer_names`` is true for live records. Historical
    snapshots can legitimately retain a different name for a deleted/recreated
    identity, so only an exact old-name match is migrated there.
    """
    rewritten = copy.deepcopy(record)
    owner_uid = rewritten.get("uid")
    if rewrite_owner_name and isinstance(owner_uid, str):
        owner_mapping = moved_names_by_uid.get(owner_uid)
        if owner_mapping is not None:
            rewritten["name"] = owner_mapping[1]

    memories = rewritten.get("memories")
    if not isinstance(memories, dict):
        raise ValueError("Context record has no valid memories object.")

    changed = 0
    selector_names: dict[str, str] = {}
    collisions: set[str] = set()
    for item_uid, item in memories.items():
        if not isinstance(item_uid, str) or not isinstance(item, dict):
            raise ValueError("Context record contains an invalid direct item.")
        if item.get("uid") != item_uid:
            raise ValueError(
                "Context record contains a direct item whose uid does not "
                "match its dictionary key."
            )
        kind = item.get("type")
        if kind == "context_ref":
            target_uid = item.get("uid")
            target_name = item.get("name")
            if not isinstance(target_name, str):
                raise ValueError("Context reference has no valid target name.")
            mapping = (
                moved_names_by_uid.get(target_uid)
                if isinstance(target_uid, str)
                else None
            )
            if mapping is not None:
                old_name, new_name = mapping
                if target_name == old_name:
                    item["name"] = new_name
                    target_name = new_name
                    changed += 1
                elif require_current_pointer_names:
                    raise ValueError(
                        "Context reference identity and stored target name "
                        f"disagree for uid '{target_uid}'."
                    )
            previous = selector_names.get(target_name)
            if previous == "query_context_ref":
                collisions.add(target_name)
            selector_names[target_name] = "context_ref"
        elif kind == "granted_context_ref":
            target_name = item.get("name")
            if not isinstance(target_name, str):
                raise ValueError("Granted Context reference has no valid public name.")
            # A granted public locator belongs to the authority binding. Local
            # namespace rename must never reinterpret or rewrite it.
            previous = selector_names.get(target_name)
            if previous == "query_context_ref":
                collisions.add(target_name)
            selector_names[target_name] = "context_ref"
        elif kind == "context_snapshot_ref":
            from memcommit.application.retained_history.context_snapshot import (
                ContextSnapshotRef,
            )

            snapshot = ContextSnapshotRef.from_dict(item)
            target_name = snapshot.target_context_name
            previous = selector_names.get(target_name)
            if previous == "query_context_ref":
                collisions.add(target_name)
            # Snapshot provenance is historical evidence, like a Memory
            # snapshot Source name, and is deliberately not rename-rewritten.
            selector_names[target_name] = "context_ref"
        elif kind == "granted_memory_ref":
            # A granted public locator is part of the external authority
            # binding. Local namespace rename must preserve it byte-for-byte.
            reference = MemoryRef.from_dict(item)
            if not reference.is_granted or not reference.is_live:
                raise ValueError("Granted Memory reference binding is invalid.")
        elif kind in {"memory_ref", "memory_snapshot_ref"}:
            target = item.get("target_context")
            if not isinstance(target, dict):
                raise ValueError("Memory reference has no valid target Context.")
            target_uid = target.get("uid")
            target_name = target.get("name")
            if not isinstance(target_uid, str) or not isinstance(target_name, str):
                raise ValueError("Memory reference has an invalid target Context.")
            # A retained granted snapshot keeps the public Source alias as
            # historical provenance; it is not a local namespace pointer.
            reference = MemoryRef.from_dict(item)
            mapping = (
                None if reference.is_granted else moved_names_by_uid.get(target_uid)
            )
            if mapping is not None:
                old_name, new_name = mapping
                if target_name == old_name:
                    target["name"] = new_name
                    changed += 1
                elif require_current_pointer_names:
                    raise ValueError(
                        "Memory reference identity and stored target name "
                        f"disagree for uid '{target_uid}'."
                    )
            if kind == "memory_snapshot_ref":
                content = item.get("content")
                digest = item.get("content_sha256")
                if not isinstance(content, str) or not isinstance(digest, str):
                    raise ValueError("Memory snapshot has invalid retained content.")
                if hashlib.sha256(content.encode("utf-8")).hexdigest() != digest:
                    raise ValueError("Memory snapshot content digest does not match.")
        elif kind == "query_context_ref":
            query_name = item.get("name")
            if not isinstance(query_name, str):
                raise ValueError("Query-only Context reference has no valid name.")
            previous = selector_names.get(query_name)
            if previous == "context_ref":
                collisions.add(query_name)
            selector_names[query_name] = "query_context_ref"
        elif kind == "memory":
            if not isinstance(item.get("content"), str):
                raise ValueError("Memory content must be a string.")
        else:
            raise ValueError(f"Unsupported direct Context item type: {kind!r}.")

    return rewritten, changed, tuple(sorted(collisions))


def _rewrite_checkpoint_record(
    value: dict[str, object],
    *,
    moved_names_by_uid: dict[str, tuple[str, str]],
) -> tuple[dict[str, object], int, tuple[str, ...]]:
    """Migrate typed pointers in every future-restorable checkpoint frame."""
    changed = 0
    collisions: set[str] = set()

    def rewrite_frame(frame: dict[str, object]) -> dict[str, object]:
        nonlocal changed
        next_frame, count, found = _rewrite_context_pointers(
            frame,
            moved_names_by_uid=moved_names_by_uid,
            # Existing checkpoint owner labels remain historical evidence.
            # Revert already retargets the restored owner to the live Context.
            rewrite_owner_name=False,
            require_current_pointer_names=False,
        )
        changed += count
        collisions.update(found)
        return next_frame

    rewritten = map_restorable_checkpoint_frames(value, rewrite_frame)
    return rewritten, changed, tuple(sorted(collisions))


def _rewrite_branched_context_pointers(
    value: dict[str, object],
    *,
    targets_by_source_uid: dict[str, tuple[str, str]],
) -> dict[str, object]:
    """Retarget one historical snapshot to new subtree Context identities.

    Unlike namespace rename, Branch creates new UIDs. A Context reference's
    uid is also its direct-item key, so the key and explicit order entry must
    move together. UID is authoritative for historical snapshots whose old
    locator may predate a source-side rename.
    """
    rewritten = copy.deepcopy(value)
    memories = rewritten.get("memories")
    if not isinstance(memories, dict):
        raise ValueError("Context snapshot has no valid memories object.")

    next_memories: dict[str, object] = {}
    item_uid_mapping: dict[str, str] = {}
    ordinary_names: set[str] = set()
    query_names: set[str] = set()
    for item_uid, item in memories.items():
        if not isinstance(item_uid, str) or not isinstance(item, dict):
            raise ValueError("Context snapshot contains an invalid direct item.")
        if item.get("uid") != item_uid:
            raise ValueError(
                "Context snapshot contains a direct item whose uid does not "
                "match its dictionary key."
            )
        next_uid = item_uid
        kind = item.get("type")
        if kind == "context_ref":
            source_uid = item.get("uid")
            target = (
                targets_by_source_uid.get(source_uid)
                if isinstance(source_uid, str)
                else None
            )
            if target is not None:
                next_uid, next_name = target
                item["uid"] = next_uid
                item["name"] = next_name
            name = item.get("name")
            if not isinstance(name, str):
                raise ValueError("Context reference has no valid target name.")
            ordinary_names.add(name)
        elif kind == "granted_context_ref":
            name = item.get("name")
            if not isinstance(name, str):
                raise ValueError("Granted Context reference has no valid public name.")
            # Branch copies the revocable link as-is. Its authority identity is
            # external to the local subtree UID remapping.
            ordinary_names.add(name)
        elif kind == "context_snapshot_ref":
            from memcommit.application.retained_history.context_snapshot import (
                ContextSnapshotRef,
            )

            snapshot = ContextSnapshotRef.from_dict(item)
            ordinary_names.add(snapshot.target_context_name)
        elif kind == "memory_ref":
            target_context = item.get("target_context")
            if not isinstance(target_context, dict):
                raise ValueError("Memory reference has no valid target Context.")
            source_uid = target_context.get("uid")
            target = (
                targets_by_source_uid.get(source_uid)
                if isinstance(source_uid, str)
                else None
            )
            if target is not None:
                target_context["uid"], target_context["name"] = target
        elif kind == "granted_memory_ref":
            reference = MemoryRef.from_dict(item)
            if not reference.is_granted or not reference.is_live:
                raise ValueError("Granted Memory reference binding is invalid.")
            # Branch copies the external live binding unchanged. It must not
            # be retargeted to a new local subtree identity.
        elif kind == "memory_snapshot_ref":
            target_context = item.get("target_context")
            if not isinstance(target_context, dict):
                raise ValueError("Memory snapshot has no valid Source Context.")
            if not isinstance(item.get("content"), str) or not isinstance(
                item.get("content_sha256"), str
            ):
                raise ValueError("Memory snapshot has invalid retained content.")
            if (
                hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
                != item["content_sha256"]
            ):
                raise ValueError("Memory snapshot content digest does not match.")
            # Parsing also validates optional retained Grant provenance. It is
            # historical evidence and is deliberately not subtree-retargeted.
            MemoryRef.from_dict(item)
        elif kind == "query_context_ref":
            name = item.get("name")
            if not isinstance(name, str):
                raise ValueError("Query-only Context reference has no valid name.")
            query_names.add(name)
        elif kind == "memory":
            if not isinstance(item.get("content"), str):
                raise ValueError("Memory content must be a string.")
        else:
            raise ValueError(f"Unsupported direct Context item type: {kind!r}.")
        if next_uid in next_memories:
            raise ValueError("Subtree Branch checkpoint item identities collide.")
        next_memories[next_uid] = item
        item_uid_mapping[item_uid] = next_uid

    collisions = ordinary_names & query_names
    if collisions:
        raise ValueError(
            "Subtree Branch checkpoint would contain ordinary and query-only "
            "Context pointers with the same name: "
            + ", ".join(repr(name) for name in sorted(collisions))
        )
    rewritten["memories"] = next_memories
    order = rewritten.get("order")
    if order is not None:
        if not isinstance(order, list) or any(
            not isinstance(item_uid, str) for item_uid in order
        ):
            raise ValueError("Context snapshot has an invalid direct-item order.")
        rewritten["order"] = [
            item_uid_mapping.get(item_uid, item_uid) for item_uid in order
        ]
    return rewritten


def _rewrite_branched_checkpoint_record(
    value: dict[str, object],
    *,
    targets_by_source_uid: dict[str, tuple[str, str]],
) -> dict[str, object]:
    """Retarget every future-restorable Context frame in a copied history."""
    return map_restorable_checkpoint_frames(
        value,
        lambda frame: _rewrite_branched_context_pointers(
            frame,
            targets_by_source_uid=targets_by_source_uid,
        ),
    )


def _validate_context_header(data: object, expected_name: str) -> dict:
    """Validate the minimum Context JSON structure needed for safe loading."""
    if not isinstance(data, dict):
        raise ValueError(
            f"Context file for '{expected_name}' must contain a JSON object."
        )
    if data.get("name") != expected_name:
        raise ValueError(
            f"Context file for '{expected_name}' declares a different name "
            f"('{data.get('name')}')."
        )
    if not isinstance(data.get("uid"), str) or not data["uid"]:
        raise ValueError(f"Context file for '{expected_name}' has no valid uid.")
    if not isinstance(data.get("memories"), dict):
        raise ValueError(
            f"Context file for '{expected_name}' has no valid memories object."
        )
    return data
