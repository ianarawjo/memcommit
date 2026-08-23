"""
MemoryStore manages all persistence for mem contexts.
Single source of truth for reading/writing ~/.mem/.

Serialization is delegated to Context.to_dict() / Context.from_dict().
All disk I/O is explicit: callers must call store.save(ctx) to persist mutations.
"""

from __future__ import annotations

import copy
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import json
import os
import shutil
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Literal, Optional

from memcommit.context import AutoCheckpoint, Checkpoint, Context, Memory
from memcommit.context_naming import (
    RESERVED_CONTEXT_SEGMENTS,
    validate_portable_context_name,
)
from memcommit.context_lifecycle import (
    ContextLifecycleEvent,
    PREVIOUS_CHECKPOINT_NONE,
    PREVIOUS_CHECKPOINT_RECORDED,
    PREVIOUS_CHECKPOINT_UNREADABLE,
)
from memcommit.context_catalog import (
    ContextCatalogDiagnostic,
    ContextCatalogDiagnosticCode,
    ContextCatalogScan,
)
from memcommit.profile_config import resolve_active_store_dir
from memcommit.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)
from memcommit.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistry,
    WriteProtectionRegistryError,
    WriteProtectionState,
)

class _ActiveStorePath(os.PathLike[str]):
    """Compatibility path that defers active-Profile I/O until path use."""

    __slots__ = ("_parts",)
    __hash__ = None

    def __init__(self, *parts: str) -> None:
        self._parts = parts

    def _resolve(self) -> Path:
        return resolve_active_store_dir().joinpath(*self._parts)

    def __fspath__(self) -> str:
        return os.fspath(self._resolve())

    def __str__(self) -> str:
        return str(self._resolve())

    def __repr__(self) -> str:
        return f"_ActiveStorePath({self._resolve()!r})"

    def __truediv__(self, child: str | os.PathLike[str]) -> Path:
        return self._resolve() / child

    def __eq__(self, other: object) -> bool:
        try:
            return self._resolve() == Path(other)  # type: ignore[arg-type]
        except TypeError:
            return False

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)


# These names remain for command/test compatibility, but merely importing the
# module must not read HOME Profile state. New Store instances freeze the root
# once in __init__; direct legacy path use resolves only when it is actually used.
STORE_DIR = _ActiveStorePath()
CONTEXTS_DIR = _ActiveStorePath("contexts")
STATE_FILE = _ActiveStorePath("state.json")
QUERY_SOURCES_DIR = _ActiveStorePath("query-sources")
IMPACT_PLAN_FILE = _ActiveStorePath("impact-plan.json")
STAGED_UPDATE_FILE = _ActiveStorePath("staged-update.json")
REVIEW_SESSION_FILE = _ActiveStorePath("review-session.json")
ATOMIZE_ANALYSES_DIR = _ActiveStorePath("atomize-analyses")
ATOMIZE_WORKBENCHES_DIR = _ActiveStorePath("atomize-workbenches")
ATOMIZE_GROUNDING_SESSIONS_DIR = _ActiveStorePath("atomize-groundings")
ATOMIZE_GROUNDING_HISTORY_DIR = _ActiveStorePath("atomize-grounding-history")
GROUND_SESSIONS_DIR = _ActiveStorePath("ground-sessions")
MELD_SESSIONS_DIR = _ActiveStorePath("meld-sessions")
_NO_UPDATE_SESSION_EXPECTATION = object()
_NO_CURRENT_CONTEXT_EXPECTATION = object()


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build a JSON object while rejecting duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _write_json_atomic(path: Path, data: object) -> None:
    """Write owner-only JSON through a same-directory atomic replacement."""
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        ensure_private_directory(path.parent, parents=True)
        descriptor = open_private_exclusive(temporary)
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _fsync_directory(path: Path) -> None:
    """Persist a directory-entry change at a multi-file commit boundary."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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


def ground_session_record_digest(value: object) -> str:
    """Hash one complete validated Ground record canonically."""
    from memcommit.ground import GroundSession

    record = (
        value.to_dict()
        if isinstance(value, GroundSession)
        else GroundSession.from_dict(value).to_dict()
    )
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


class ConcurrentContextUpdateError(RuntimeError):
    """A Context changed after a caller captured its expected record."""


class ContextDeletionCommittedError(RuntimeError):
    """Deletion committed, but one or more post-commit cleanups failed."""

    def __init__(
        self,
        event: ContextLifecycleEvent,
        failures: tuple[tuple[str, Exception], ...],
    ) -> None:
        if not failures:
            raise ValueError("A committed deletion error requires a failure.")
        self.event = event.validated()
        self.failures = failures
        label, failure = failures[0]
        super().__init__(
            "Context deletion committed as lifecycle event "
            f"'{event.event_uid}', but {label} cleanup was incomplete: "
            f"{failure}"
        )


class ConcurrentGroundUpdateError(RuntimeError):
    """A named Ground changed after a caller captured its expected record."""


@dataclass(frozen=True)
class ContextBranchBinding:
    """One freshness-bound Source and its newly identified Branch Context."""

    source_name: str
    expected_source_uid: str
    expected_source_digest: str
    expected_history_digest: str
    target: Context


@dataclass(frozen=True)
class ContextRenameBinding:
    """One stable ordinary-Context identity in a namespace rename plan."""

    old_name: str
    new_name: str
    context_uid: str


@dataclass(frozen=True)
class ContextRenamePlan:
    """Read-only, freshness-bound preview for one Context namespace rename."""

    old_name: str
    new_name: str
    bindings: tuple[ContextRenameBinding, ...]
    changed_owner_names: tuple[str, ...]
    reference_count: int
    checkpoint_reference_count: int
    ground_frame_count: int
    translation_artifact_count: int
    meld_session_count: int
    current_before: str | None
    current_after: str | None
    graph_digest: str

    @property
    def descendant_count(self) -> int:
        return max(0, len(self.bindings) - 1)


@dataclass(frozen=True)
class ContextRenameResult:
    """Committed counts returned by :meth:`MemoryStore.rename_contexts`."""

    renamed_context_count: int
    changed_owner_count: int
    reference_count: int
    checkpoint_reference_count: int
    ground_frame_count: int
    translation_artifact_count: int
    meld_session_count: int
    current_context: str | None


@dataclass(frozen=True)
class _PreparedContextRename:
    """Validated pre/post images used only inside the store transaction."""

    plan: ContextRenamePlan
    records: dict[str, dict[str, object]]
    post_records: dict[str, dict[str, object]]
    checkpoints: dict[str, dict[str, dict[str, object]]]
    post_checkpoints: dict[str, dict[str, dict[str, object]]]
    state: dict[str, object]
    post_state: dict[str, object]
    ground_records: dict[str, dict[str, object]]
    post_ground_records: dict[str, dict[str, object]]
    translation_records: dict[str, dict[str, object]]
    post_translation_records: dict[str, dict[str, object]]
    meld_records: dict[str, dict[str, object]]
    post_meld_records: dict[str, dict[str, object]]


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


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    """Restore owner-only bytes through the JSON replace boundary."""
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        ensure_private_directory(path.parent, parents=True)
        descriptor = open_private_exclusive(temporary)
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _canonical_json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
            from memcommit.context_snapshot import ContextSnapshotRef

            snapshot = ContextSnapshotRef.from_dict(item)
            target_name = snapshot.target_context_name
            previous = selector_names.get(target_name)
            if previous == "query_context_ref":
                collisions.add(target_name)
            # Snapshot provenance is historical evidence, like a Memory
            # snapshot Source name, and is deliberately not rename-rewritten.
            selector_names[target_name] = "context_ref"
        elif kind in {"memory_ref", "memory_snapshot_ref"}:
            target = item.get("target_context")
            if not isinstance(target, dict):
                raise ValueError("Memory reference has no valid target Context.")
            target_uid = target.get("uid")
            target_name = target.get("name")
            if not isinstance(target_uid, str) or not isinstance(target_name, str):
                raise ValueError("Memory reference has an invalid target Context.")
            mapping = moved_names_by_uid.get(target_uid)
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
    """Migrate future-restorable typed pointers, including nested log frames."""
    rewritten = copy.deepcopy(value)
    changed = 0
    collisions: set[str] = set()

    snapshot = rewritten.get("snapshot")
    if isinstance(snapshot, dict):
        next_snapshot, count, found = _rewrite_context_pointers(
            snapshot,
            moved_names_by_uid=moved_names_by_uid,
            # Existing checkpoint owner labels remain historical evidence.
            # Revert already retargets the restored owner to the live Context.
            rewrite_owner_name=False,
            require_current_pointer_names=False,
        )
        rewritten["snapshot"] = next_snapshot
        changed += count
        collisions.update(found)

    args = rewritten.get("args")
    if isinstance(args, dict) and "log_snapshot" in args:
        log_snapshot = args["log_snapshot"]
        if not isinstance(log_snapshot, list):
            raise ValueError("Checkpoint log_snapshot must be a list.")
        next_entries: list[object] = []
        for entry in log_snapshot:
            if not isinstance(entry, dict):
                raise ValueError("Checkpoint log_snapshot entry must be an object.")
            next_entry, count, found = _rewrite_checkpoint_record(
                entry,
                moved_names_by_uid=moved_names_by_uid,
            )
            next_entries.append(next_entry)
            changed += count
            collisions.update(found)
        args["log_snapshot"] = next_entries

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
            from memcommit.context_snapshot import ContextSnapshotRef

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
        elif kind == "memory_snapshot_ref":
            target_context = item.get("target_context")
            if not isinstance(target_context, dict):
                raise ValueError("Memory snapshot has no valid Source Context.")
            if not isinstance(item.get("content"), str) or not isinstance(
                item.get("content_sha256"), str
            ):
                raise ValueError("Memory snapshot has invalid retained content.")
            if hashlib.sha256(
                item["content"].encode("utf-8")
            ).hexdigest() != item["content_sha256"]:
                raise ValueError("Memory snapshot content digest does not match.")
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
    rewritten = copy.deepcopy(value)
    for field in ("snapshot", "command_before"):
        frame = rewritten.get(field)
        if isinstance(frame, dict):
            rewritten[field] = _rewrite_branched_context_pointers(
                frame,
                targets_by_source_uid=targets_by_source_uid,
            )

    args = rewritten.get("args")
    if isinstance(args, dict) and "log_snapshot" in args:
        log_snapshot = args["log_snapshot"]
        if not isinstance(log_snapshot, list):
            raise ValueError("Checkpoint log_snapshot must be a list.")
        next_entries: list[dict[str, object]] = []
        for entry in log_snapshot:
            if not isinstance(entry, dict):
                raise ValueError("Checkpoint log_snapshot entry must be an object.")
            next_entries.append(
                _rewrite_branched_checkpoint_record(
                    entry,
                    targets_by_source_uid=targets_by_source_uid,
                )
            )
        args["log_snapshot"] = next_entries
    return rewritten


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


@dataclass(frozen=True)
class QuerySourceEntry:
    """One stable concealed record with an English canonical form."""

    uid: str
    key: str
    canonical_content: str
    translations: tuple[tuple[str, str], ...] = ()

    def content_for(
        self,
        language: str,
        *,
        canonical_language: str = "en",
        fallback_to_canonical: bool = False,
    ) -> str:
        """Select one language without changing this entry's stable identity."""
        if language == canonical_language:
            return self.canonical_content
        translated = dict(self.translations).get(language)
        if translated is not None:
            return translated
        if fallback_to_canonical:
            return self.canonical_content
        # Entry keys are concealed storage metadata.  A missing-language error
        # crosses the query-only boundary into the CLI, so it must not identify
        # which private record failed coverage.
        raise ValueError("Requested query-source translation is unavailable.")


@dataclass(frozen=True)
class QuerySource:
    """Research-only source text kept outside the normal Context namespace.

    ``content`` preserves the original one-string read contract. Construction
    and dataclass serialization are internal entry-oriented records in v2;
    callers obtain sources through ``MemoryStore`` rather than instantiating
    this type directly.
    """

    uid: str
    name: str
    entries: tuple[QuerySourceEntry, ...]
    selected_language: str = "en"
    canonical_language: str = "en"
    fallback_to_canonical: bool = False

    @property
    def contents(self) -> tuple[str, ...]:
        """Return selected entry texts in their persisted order."""
        return tuple(
            entry.content_for(
                self.selected_language,
                canonical_language=self.canonical_language,
                fallback_to_canonical=self.fallback_to_canonical,
            )
            for entry in self.entries
        )

    @property
    def content(self) -> str:
        """Return the provider-facing text used by legacy query callers."""
        return "\n\n".join(self.contents)


def _query_source_language(value: object, *, field: str) -> str:
    """Validate one normalized, BCP-47-like language identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a normalized language identifier.")
    parts = value.split("-")
    if (
        not 2 <= len(parts[0]) <= 8
        or not parts[0].isascii()
        or not parts[0].isalpha()
        or parts[0] != parts[0].lower()
        or any(
            not 1 <= len(part) <= 8
            or not part.isascii()
            or not part.isalnum()
            or part != part.lower()
            for part in parts[1:]
        )
    ):
        raise ValueError(f"{field} must be a normalized language identifier.")
    return value


def _query_source_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text.")
    return value


def _query_source_entry_key(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 200
        or any(
            not character.isprintable()
            or unicodedata.category(character) in {"Cc", "Cf", "Cs"}
            for character in value
        )
    ):
        raise ValueError(
            "Query source entry key must be 1-200 visible characters "
            "without surrounding whitespace."
        )
    return value


def _query_source_entry_uid(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Query source entry uid must be a canonical UUID.")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Query source entry uid must be a canonical UUID.") from error
    canonical = str(parsed)
    if value != canonical:
        raise ValueError("Query source entry uid must be a canonical UUID.")
    return canonical


def _query_source_translations(
    value: object,
    *,
    canonical_language: str,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        raise ValueError("Query source entry translations must be an object.")
    translations: list[tuple[str, str]] = []
    for raw_language, raw_content in value.items():
        language = _query_source_language(
            raw_language,
            field="Query source translation language",
        )
        if language == canonical_language:
            raise ValueError(
                "Query source translations must not repeat the canonical "
                f"'{canonical_language}' content."
            )
        translations.append(
            (
                language,
                _query_source_text(
                    raw_content,
                    field=f"Query source '{language}' translation",
                ),
            )
        )
    return tuple(sorted(translations))


def _query_source_entry_from_record(
    value: object,
    *,
    canonical_language: str,
    allow_missing_uid: bool,
) -> QuerySourceEntry:
    if isinstance(value, QuerySourceEntry):
        value = {
            "uid": value.uid,
            "key": value.key,
            "canonical_content": value.canonical_content,
            "translations": dict(value.translations),
        }
    if not isinstance(value, dict):
        raise ValueError("Each query source entry must be an object.")
    allowed = {"uid", "key", "canonical_content", "translations"}
    required = {"key", "canonical_content"}
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise ValueError(
            "Query source entry fields must be key, canonical_content, "
            "optional uid, and optional translations."
        )
    raw_uid = value.get("uid")
    if raw_uid is None:
        if not allow_missing_uid:
            raise ValueError("Persisted query source entry has no uid.")
        entry_uid = str(uuid.uuid4())
    else:
        entry_uid = _query_source_entry_uid(raw_uid)
    translations = _query_source_translations(
        value.get("translations", {}),
        canonical_language=canonical_language,
    )
    return QuerySourceEntry(
        uid=entry_uid,
        key=_query_source_entry_key(value.get("key")),
        canonical_content=_query_source_text(
            value.get("canonical_content"),
            field="Query source canonical content",
        ),
        translations=translations,
    )


def _profile_write_guarded(method: Callable):
    """Hold the Profile policy generation across one non-Context write.

    Context mutations use the global command lock before checking Profile
    policy. Session and derived-artifact stores do not participate in command
    history, so they instead retain the registry's shared lock through their
    complete persistence boundary.
    """

    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.profile_write_guard():
            return method(self, *args, **kwargs)

    return guarded


class MemoryStore:
    def __init__(
        self,
        *,
        create: bool = True,
        root: Path | None = None,
    ):
        """
        Open the store.

        Normal commands create missing store infrastructure. Read-only
        inspection commands can pass create=False to guarantee that merely
        checking absent state does not create ~/.mem or state.json.  ``root``
        is an explicit, already-authorized store boundary used by profile
        grants; omitting it resolves and freezes the active Profile now.
        """
        # Explicit roots are already selected by the caller and must not touch
        # HOME Profile state. Profile-backed stores resolve exactly once here
        # so a later process-global Profile switch cannot retarget this object.
        self._store_dir = (
            Path(root).absolute() if root is not None else Path(STORE_DIR)
        )
        if create:
            ensure_private_directory(self.store_dir, parents=True)
            ensure_private_directory(self.contexts_dir, parents=True)
            if not self.state_file.exists():
                self._write_state({"current": None})

    @property
    def store_dir(self) -> Path:
        return self._store_dir

    @property
    def contexts_dir(self) -> Path:
        return self.store_dir / "contexts"

    @property
    def state_file(self) -> Path:
        return self.store_dir / "state.json"

    @property
    def query_sources_dir(self) -> Path:
        return self.store_dir / "query-sources"

    @property
    def impact_plan_file(self) -> Path:
        return self.store_dir / "impact-plan.json"

    @property
    def staged_update_file(self) -> Path:
        return self.store_dir / "staged-update.json"

    @property
    def review_session_file(self) -> Path:
        return self.store_dir / "review-session.json"

    @property
    def command_context_archives_dir(self) -> Path:
        """Private retained histories for undo of Context-creation commands."""
        return self.store_dir / "command-context-archives"

    @property
    def atomize_analyses_dir(self) -> Path:
        return self.store_dir / "atomize-analyses"

    @property
    def atomize_workbenches_dir(self) -> Path:
        return self.store_dir / "atomize-workbenches"

    @property
    def atomize_grounding_sessions_dir(self) -> Path:
        return self.store_dir / "atomize-groundings"

    @property
    def atomize_grounding_history_dir(self) -> Path:
        return self.store_dir / "atomize-grounding-history"

    @property
    def ground_sessions_dir(self) -> Path:
        return self.store_dir / "ground-sessions"

    @property
    def meld_sessions_dir(self) -> Path:
        return self.store_dir / "meld-sessions"

    @property
    def meld_resolution_branches_dir(self) -> Path:
        """Profile-local exact semantic outcomes for Meld follow-up turns."""
        return self.store_dir / "meld-resolution-branches"

    @property
    def meld_choice_branches_dir(self) -> Path:
        """Provider-free option selections staged for saved Meld sessions."""
        return self.store_dir / "meld-choice-branches"

    @property
    def write_protection_registry(self) -> WriteProtectionRegistry:
        """Return the persistent registry scoped to this exact Profile store."""
        return WriteProtectionRegistry(self.store_dir)

    def write_protection_state(self) -> WriteProtectionState:
        """Read the current Profile-scoped protection state."""
        return self.write_protection_registry.snapshot()

    @contextmanager
    def profile_write_guard(self) -> Iterator[WriteProtectionState]:
        """Keep Profile-level permission stable through one artifact write."""
        with self.write_protection_registry.profile_write_guard() as state:
            yield state

    def _assert_profile_write_allowed(self) -> WriteProtectionState:
        """Fail closed at a command boundary protected by its command lock."""
        state = self.write_protection_state()
        if state.profile_is_protected():
            raise WriteProtectionError(
                "Profile is locked against writes. Unlock that Profile first."
            )
        return state

    @staticmethod
    def _protected_context_message(name: str) -> str:
        return f"Context '{name}' is locked against changes. Unlock that Context first."

    @staticmethod
    def _protected_memory_message(name: str, memory_uid: str) -> str:
        return (
            f"Memory [{memory_uid[:8]}] in Context '{name}' is locked against "
            "changes. Unlock that Memory first."
        )

    def _assert_context_record_change_allowed(
        self,
        before: Context | dict[str, object],
        after: Context | dict[str, object],
        *,
        state: WriteProtectionState | None = None,
    ) -> None:
        """Reject a persisted record change that crosses a protection boundary.

        Callers already hold the affected Context write lock.  This order is
        intentional: lock/unlock takes that same Context lock before changing
        the registry, so a writer cannot validate one policy generation and
        publish after a concurrent protection change.
        """
        before_record = canonical_context_record(before)
        after_record = canonical_context_record(after)
        if before_record == after_record:
            return
        context_uid = str(before_record["uid"])
        context_name = str(before_record["name"])
        if str(after_record["uid"]) != context_uid:
            raise ValueError("A Context save cannot replace its stable identity.")
        protection = state if state is not None else self.write_protection_state()
        if protection.context_is_protected(context_uid):
            raise WriteProtectionError(self._protected_context_message(context_name))

        before_memories = before_record["memories"]
        after_memories = after_record["memories"]
        assert isinstance(before_memories, dict)
        assert isinstance(after_memories, dict)
        for memory_uid in sorted(protection.protected_memory_uids(context_uid)):
            before_memory = before_memories.get(memory_uid)
            if (
                not isinstance(before_memory, dict)
                or before_memory.get("type") != "memory"
                or before_memory.get("uid") != memory_uid
            ):
                raise WriteProtectionRegistryError(
                    f"Protected Memory [{memory_uid[:8]}] no longer identifies "
                    f"a direct Memory in Context '{context_name}'."
                )
            if after_memories.get(memory_uid) != before_memory:
                raise WriteProtectionError(
                    self._protected_memory_message(context_name, memory_uid)
                )

    def _assert_context_deletion_allowed(self, context: Context) -> None:
        """Deletion changes every protected direct record, regardless of CAS."""
        protection = self.write_protection_state()
        if protection.context_is_protected(context.uid):
            raise WriteProtectionError(self._protected_context_message(context.name))
        locked_memories = sorted(protection.protected_memory_uids(context.uid))
        if locked_memories:
            memory_uid = locked_memories[0]
            item = context.memories.get(memory_uid)
            if not isinstance(item, Memory):
                raise WriteProtectionRegistryError(
                    f"Protected Memory [{memory_uid[:8]}] no longer identifies "
                    f"a direct Memory in Context '{context.name}'."
                )
            raise WriteProtectionError(
                self._protected_memory_message(context.name, memory_uid)
            )

    def _revalidate_protection_target(
        self,
        name: str,
        *,
        expected_context_uid: str,
        expected_context_digest: str,
    ) -> Context:
        try:
            current = self.load_direct(name)
        except FileNotFoundError as error:
            raise ConcurrentContextUpdateError(
                f"Context '{name}' no longer exists."
            ) from error
        if (
            current.uid != expected_context_uid
            or context_record_digest(current) != expected_context_digest
        ):
            raise ConcurrentContextUpdateError(
                f"Context '{name}' changed before its lock state could be saved."
            )
        return current

    def set_context_write_protection(
        self,
        name: str,
        *,
        protected: bool,
        expected_context_uid: str,
        expected_context_digest: str,
    ) -> bool:
        """Lock or unlock one exact existing Context identity."""
        validate_context_name(name)
        with self._context_write_lock(name):
            current = self._revalidate_protection_target(
                name,
                expected_context_uid=expected_context_uid,
                expected_context_digest=expected_context_digest,
            )
            before, after = self.write_protection_registry.update(
                lambda state: state.with_context(
                    current.uid,
                    protected=protected,
                )
            )
            return before != after

    def set_context_namespace_write_protection(
        self,
        root_name: str,
        expected_contexts: Iterable[tuple[str, str, str]],
        *,
        protected: bool,
    ) -> tuple[int, int]:
        """Atomically change current members of one lexical Context subtree.

        ``--recursive`` has snapshot semantics like a recursive filesystem
        operation: it changes the root and descendants that exist in the
        reviewed catalog, while later descendants receive no implicit policy.
        The Profile lock is the persistent choice when future writes and new
        Contexts must also be blocked.
        """
        validate_context_name(root_name)
        expected = tuple(sorted(expected_contexts))
        if not expected or len({name for name, _, _ in expected}) != len(expected):
            raise ValueError("Invalid recursive Context protection target set.")
        prefix = root_name + "/"
        if any(
            name != root_name and not name.startswith(prefix) for name, _, _ in expected
        ):
            raise ValueError("Invalid recursive Context protection target set.")

        with self._context_graph_lock(exclusive=True):
            with self._context_write_locks(name for name, _, _ in expected):
                graph = self.load_direct_context_graph_strict()
                current = tuple(
                    sorted(
                        (
                            context.name,
                            context.uid,
                            context_record_digest(context),
                        )
                        for context in graph
                        if context.name == root_name or context.name.startswith(prefix)
                    )
                )
                if current != expected:
                    raise ConcurrentContextUpdateError(
                        f"Context namespace '{root_name}' changed before its "
                        "lock state could be saved."
                    )
                context_uids = tuple(uid for _, uid, _ in current)
                before, after = self.write_protection_registry.update(
                    lambda state: state.with_contexts(
                        context_uids,
                        protected=protected,
                    )
                )
                changed = len(
                    before.context_uids.symmetric_difference(after.context_uids)
                )
                return len(current), changed

    def set_profile_write_protection(self, *, protected: bool) -> bool:
        """Change the active Profile's upper write barrier.

        Context and Memory policies are intentionally retained. Unlocking the
        Profile therefore restores the narrower policy state instead of
        silently widening permissions.
        """
        with self._command_write_lock():
            before, after = self.write_protection_registry.update(
                lambda state: state.with_profile(protected=protected)
            )
            return before != after

    def set_memory_write_protection(
        self,
        name: str,
        memory_uid: str,
        *,
        protected: bool,
        expected_context_uid: str,
        expected_context_digest: str,
    ) -> bool:
        """Lock or unlock one direct Memory occurrence in one exact Context."""
        validate_context_name(name)
        with self._context_write_lock(name):
            current = self._revalidate_protection_target(
                name,
                expected_context_uid=expected_context_uid,
                expected_context_digest=expected_context_digest,
            )
            item = current.memories.get(memory_uid)
            if not isinstance(item, Memory):
                raise ValueError(
                    f"'{memory_uid}' is not a directly owned Memory in "
                    f"Context '{name}'."
                )
            before, after = self.write_protection_registry.update(
                lambda state: state.with_memory(
                    current.uid,
                    memory_uid,
                    protected=protected,
                )
            )
            return before != after

    @contextmanager
    def _context_graph_lock(self, *, exclusive: bool) -> Iterator[None]:
        """Coordinate graph-wide Context migrations with ordinary writers.

        Per-name locks cannot protect an inbound-reference scan: another
        process could add a new owner under a previously unseen name while a
        namespace migration is being prepared. Ordinary Context/state writers
        therefore take this lock shared, while rename holds it exclusively
        from its final scan through publication and rollback.
        """
        lock_path = self.store_dir / "context-graph.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Context graph lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
                )
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _context_write_lock(self, name: str) -> Iterator[None]:
        """Serialize cooperative Context saves across local mem processes."""
        _context_name_parts(name)
        lock_dir = self.store_dir / "context-write-locks"
        if lock_dir.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Context lock directory.")
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / (
            hashlib.sha256(name.encode("utf-8")).hexdigest() + ".lock"
        )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            # os.fdopen owns the descriptor once it succeeds. If it fails
            # before taking ownership, close the raw descriptor here.
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _context_write_locks(
        self,
        names: Iterable[str],
    ) -> Iterator[None]:
        """Hold several Context locks in one deterministic deadlock-free order."""
        ordered = sorted(set(names))
        with ExitStack() as stack:
            for name in ordered:
                stack.enter_context(self._context_write_lock(name))
            yield

    @contextmanager
    def _command_write_lock(self) -> Iterator[None]:
        """Serialize checkpoint-producing commands across Contexts.

        Per-Context locks prevent lost writes but cannot order two commands
        aimed at different Contexts. Undo/Redo reconstruct one global command
        stack, so future command commits share this short store-wide boundary.
        """
        lock_path = self.store_dir / "context-command-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link command lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _state_write_lock(self) -> Iterator[None]:
        """Serialize cooperative changes to the global current Context."""
        lock_path = self.store_dir / "state-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link state lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _update_session_write_lock(self) -> Iterator[None]:
        """Serialize promotion and application of the one active update."""
        lock_path = self.store_dir / "update-session-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link update lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _atomize_session_write_lock(
        self,
        context_uid: str,
    ) -> Iterator[None]:
        """Serialize one Context's analysis/workbench CAS lifecycle."""

        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid Atomize session Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid Atomize session Context uid.")
        lock_dir = self.store_dir / "atomize-session-write-locks"
        if lock_dir.is_symlink():
            raise ValueError("Refusing to use an Atomize session lock symlink.")
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / f"{canonical}.lock"
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _meld_resolution_branch_write_lock(self) -> Iterator[None]:
        """Serialize first-writer-wins publication for exact Meld branches."""
        lock_path = self.store_dir / "meld-resolution-branch-write.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Meld branch lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @contextmanager
    def _ground_session_write_lock(
        self,
        contract_name: str,
    ) -> Iterator[None]:
        """Serialize cooperative saves of one portable named Ground."""
        from memcommit.ground import validate_ground_contract_name

        canonical = validate_ground_contract_name(contract_name)
        if self.ground_sessions_dir.is_symlink():
            raise ValueError("Grounding session storage cannot be a symbolic link.")
        if self.ground_sessions_dir.exists() and not self.ground_sessions_dir.is_dir():
            raise ValueError("Grounding session storage is invalid.")
        self.ground_sessions_dir.mkdir(parents=True, exist_ok=True)
        # Keep coordination artifacts within the Ground storage boundary so
        # Ground-only work does not create unrelated top-level store state.
        lock_dir = self.ground_sessions_dir / ".locks"
        if lock_dir.is_symlink():
            raise ValueError("Refusing to use a symbolic-link Ground lock directory.")
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / (
            hashlib.sha256(canonical.encode("utf-8")).hexdigest() + ".lock"
        )
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    # --- Global state ---

    def _read_state(self) -> dict:
        with open(self.state_file) as f:
            return json.load(f)

    def _write_state(self, state: dict) -> None:
        # Context switching is the final phase of several multi-file
        # operations.  Replacing an fsynced sibling keeps an interrupted write
        # from leaving state.json truncated and making rollback impossible.
        _write_json_atomic(self.state_file, state)

    def current_context_name(self) -> Optional[str]:
        return self._read_state().get("current")

    def set_current(self, name: str) -> None:
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                if not self.context_exists(name):
                    raise FileNotFoundError(f"Context '{name}' not found.")
                with self._state_write_lock():
                    state = self._read_state()
                    state["current"] = name
                    self._write_state(state)

    def set_current_context_if(
        self,
        expected_current: str | None,
        name: str,
        *,
        expected_context_uid: str,
        expected_context_digest: str,
    ) -> None:
        """CAS-switch to one exact Context while blocking save/delete/recreate."""
        if (
            not isinstance(expected_context_digest, str)
            or len(expected_context_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_context_digest
            )
        ):
            raise ValueError("Expected Context digest is invalid.")
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                if not self.context_exists(name):
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' no longer exists."
                    )
                target = self.load_direct(name)
                if (
                    target.uid != expected_context_uid
                    or context_record_digest(target) != expected_context_digest
                ):
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' changed before it could be selected."
                    )
                with self._state_write_lock():
                    state = self._read_state()
                    if state.get("current") != expected_current:
                        raise ConcurrentContextUpdateError(
                            "The current Context changed before it could be switched."
                        )
                    state["current"] = name
                    self._write_state(state)

    def set_current_virtual_context_if(
        self,
        expected_current: str | None,
        name: str,
    ) -> None:
        """CAS-select one externally validated granted Context name.

        A granted view is a navigation pointer, not a locally materialized
        Context. Authorization and authority identity are therefore resolved
        again by each command that consumes the pointer. Only ``mem switch``
        may call this after validating a READ grant; query-only routes remain
        non-selectable.
        """

        _context_name_parts(name)
        if self.context_exists(name):
            raise ValueError(
                f"Context '{name}' is local and must use the ordinary switch path."
            )
        with self._state_write_lock():
            state = self._read_state()
            if state.get("current") != expected_current:
                raise ConcurrentContextUpdateError(
                    "The current Context changed before it could be switched."
                )
            state["current"] = name
            self._write_state(state)

    # --- Semantic update sessions ---

    @staticmethod
    def _load_update_session(path: Path):
        """Load and validate one cached semantic update session."""
        from memcommit.update import UpdateSession

        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Semantic update session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f, object_pairs_hook=_reject_duplicate_json_keys)
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("Semantic update session is invalid JSON.") from error
        try:
            return UpdateSession.from_dict(data)
        except ValueError as error:
            raise ValueError("Semantic update session is invalid.") from error

    @staticmethod
    def _save_update_session(path: Path, session) -> None:
        """Atomically persist one validated semantic update session."""
        from memcommit.update import UpdateSession

        if not isinstance(session, UpdateSession):
            raise TypeError("Expected an UpdateSession.")
        try:
            data = session.to_dict()
            restored = UpdateSession.from_dict(data)
        except ValueError as error:
            raise ValueError("Semantic update session is invalid.") from error
        if restored != session:
            raise ValueError("Semantic update session changed during validation.")
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Semantic update session storage is invalid.")
        _write_json_atomic(path, data)

    def load_impact_plan(self):
        """Return the cached impact plan, or None when no plan exists."""
        return self._load_update_session(self.impact_plan_file)

    @_profile_write_guarded
    def save_impact_plan(self, session) -> None:
        """Atomically cache a non-mutating impact plan."""
        self._save_update_session(self.impact_plan_file, session)

    def load_staged_update(self):
        """Return the active staged/applied update record, if one exists."""
        return self._load_update_session(self.staged_update_file)

    @_profile_write_guarded
    def save_staged_update(
        self,
        session,
        *,
        expected_current: object = _NO_UPDATE_SESSION_EXPECTATION,
    ) -> None:
        """Atomically save the active update, optionally using record CAS."""
        with self._update_session_write_lock():
            if expected_current is not _NO_UPDATE_SESSION_EXPECTATION:
                current = self._load_update_session(self.staged_update_file)
                if current != expected_current:
                    raise ConcurrentContextUpdateError(
                        "The active update record changed before it could be saved."
                    )
            self._save_update_session(self.staged_update_file, session)

    def apply_staged_update(self, session):
        """Apply one staged Update as one globally ordered command."""
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            return self._apply_staged_update_command_locked(session)

    def _apply_staged_update_command_locked(self, session):
        """Apply one exact staged plan to its local target Context graph.

        Every owner is preflighted before the first write. Cooperative Context
        locks remain held through the last checkpoint and the application
        receipt. If an ordinary write fails, already-written owners and their
        new checkpoints are rolled back before the error escapes.

        A process crash can still interrupt the sequence of per-Context atomic
        replacements. A durable transaction journal is intentionally deferred
        with remote publication; this prototype provides exception atomicity,
        not crash atomicity, across several Context files.
        """
        from memcommit.update import (
            UpdateApplicationReceipt,
            UpdateCheckpointReceipt,
            UpdateError,
            UpdateSession,
            applied_session_matches,
            collect_update_inputs,
            operation_digest,
            session_matches,
        )
        from memcommit.update_application import prepare_update_application
        from memcommit.context_targeting.loading import load_context_scope

        if not isinstance(session, UpdateSession) or session.status != "staged":
            raise ValueError("Expected one staged UpdateSession.")

        lock_names = {
            context.name
            for context in (
                *session.source_contexts,
                *session.target_contexts,
            )
        }
        lock_names.update(
            {
                session.source_name,
                session.target_name,
            }
        )
        # A source MemoryRef is readable evidence owned outside the embedded
        # source graph. Lock every cited owner too so its supporting text
        # cannot change between freshness validation and the final receipt.
        lock_names.update(
            source.context_name
            for operation in session.operations
            for source in operation.source_refs
        )

        with self._update_session_write_lock():
            current = self._load_update_session(self.staged_update_file)
            if current != session:
                raise ConcurrentContextUpdateError(
                    "The active staged update changed before application."
                )

            with self._context_write_locks(lock_names):
                source = load_context_scope(
                    self,
                    session.source_name,
                    include_descendants=session.source_include_descendants,
                )
                target = load_context_scope(
                    self,
                    session.target_name,
                    include_descendants=session.target_include_descendants,
                )
                if not session_matches(session, source, target):
                    raise ConcurrentContextUpdateError(
                        "The update source or local fork changed before application."
                    )

                result = prepare_update_application(session, target)
                base_by_identity = {
                    (context.uid, context.name): context
                    for context in session.target_contexts
                }
                original_records: dict[str, dict[str, object]] = {}
                expected_digests: dict[str, str] = {}
                for owner in result.affected_owners:
                    identity = (
                        owner.owner_context_uid,
                        owner.owner_context_name,
                    )
                    base = base_by_identity.get(identity)
                    if base is None:
                        raise UpdateError(
                            "Update owner is outside the recorded local fork."
                        )
                    direct = self.load_direct(owner.owner_context_name)
                    if (
                        direct.uid != owner.owner_context_uid
                        or context_record_digest(direct) != base.digest
                    ):
                        raise ConcurrentContextUpdateError(
                            f"Local fork Context '{owner.owner_context_name}' "
                            "changed before application."
                        )
                    if (
                        owner.post_image.uid != owner.owner_context_uid
                        or owner.post_image.name != owner.owner_context_name
                    ):
                        raise UpdateError(
                            "Update application changed an owner identity."
                        )
                    original_records[owner.owner_context_name] = direct.to_dict()
                    expected_digests[owner.owner_context_name] = base.digest

                created_checkpoints: list[tuple[str, str]] = []
                written_owner_names: list[str] = []
                try:
                    operation_hash = operation_digest(session.operations)
                    for owner in result.affected_owners:
                        owner_operations = [
                            operation
                            for operation in session.operations
                            if (operation.owner_context_uid == owner.owner_context_uid)
                        ]
                        checkpoint = self._save_locked(
                            owner.post_image,
                            AutoCheckpoint(
                                command="update",
                                args={
                                    "update_session_uid": session.uid,
                                    "operation_digest": operation_hash,
                                    "source_context_uid": session.source_uid,
                                    "source_context_name": session.source_name,
                                    "target_context_uid": session.target_uid,
                                    "target_context_name": session.target_name,
                                    "owner_context_uid": (owner.owner_context_uid),
                                    "operation_memory_uids": [
                                        operation.memory_uid
                                        for operation in owner_operations
                                    ],
                                    "command_contexts": [
                                        {
                                            "uid": affected.owner_context_uid,
                                            "name": affected.owner_context_name,
                                        }
                                        for affected in result.affected_owners
                                    ],
                                },
                                description=(
                                    "Applied semantic update "
                                    f"{session.uid[:8]} from "
                                    f"{session.source_name}."
                                ),
                            ),
                            expected_context_digest=expected_digests[
                                owner.owner_context_name
                            ],
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Update application created no checkpoint."
                            )
                        written_owner_names.append(owner.owner_context_name)
                        created_checkpoints.append(
                            (
                                owner.owner_context_name,
                                checkpoint.uid,
                            )
                        )

                    source_after = load_context_scope(
                        self,
                        session.source_name,
                        include_descendants=session.source_include_descendants,
                    )
                    target_after = load_context_scope(
                        self,
                        session.target_name,
                        include_descendants=session.target_include_descendants,
                    )
                    inputs_after = collect_update_inputs(
                        source_after,
                        target_after,
                    )
                    checkpoint_uid_by_name = dict(created_checkpoints)
                    receipt = UpdateApplicationReceipt(
                        applied_at=datetime.now().astimezone().isoformat(),
                        operation_digest=operation_hash,
                        target_digest=inputs_after.target_digest,
                        target_contexts=(inputs_after.target_context_fingerprints),
                        checkpoints=tuple(
                            UpdateCheckpointReceipt(
                                context_uid=owner.owner_context_uid,
                                context_name=owner.owner_context_name,
                                checkpoint_uid=checkpoint_uid_by_name[
                                    owner.owner_context_name
                                ],
                            )
                            for owner in result.affected_owners
                        ),
                    )
                    applied = session.with_application(receipt)
                    if not applied_session_matches(
                        applied,
                        source_after,
                        target_after,
                    ):
                        raise RuntimeError(
                            "Applied local fork does not match its receipt."
                        )
                    self._save_update_session(
                        self.staged_update_file,
                        applied,
                    )
                except Exception:
                    rollback_error: Exception | None = None
                    for name in written_owner_names:
                        try:
                            _write_json_atomic(
                                self._context_file(name),
                                original_records[name],
                            )
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
                    for name, checkpoint_uid in created_checkpoints:
                        try:
                            removed = False
                            for path in self._checkpoints_dir(name).glob(
                                f"*-{checkpoint_uid[:8]}.json"
                            ):
                                if path.is_symlink() or not path.is_file():
                                    continue
                                with open(path, encoding="utf-8") as file:
                                    value = json.load(
                                        file,
                                        object_pairs_hook=(_reject_duplicate_json_keys),
                                    )
                                if value.get("uid") == checkpoint_uid:
                                    path.unlink()
                                    removed = True
                                    break
                            if not removed:
                                raise RuntimeError(
                                    "Update checkpoint could not be found "
                                    "during rollback."
                                )
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
                    if rollback_error is not None:
                        raise RuntimeError(
                            "Update application failed and its local fork "
                            "could not be fully rolled back."
                        ) from rollback_error
                    raise

        return applied

    # --- Semantic review sessions ---

    @staticmethod
    def _load_review_session(path: Path):
        """Load and strictly validate the active semantic review."""
        from memcommit.review import ReviewError, ReviewSession

        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Semantic review session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("Semantic review session is invalid JSON.") from error
        try:
            return ReviewSession.from_dict(data)
        except (ReviewError, TypeError) as error:
            raise ValueError("Semantic review session is invalid.") from error

    def load_review_session(self):
        """Return the active semantic review, or None when none exists."""
        return self._load_review_session(self.review_session_file)

    @_profile_write_guarded
    def save_review_session(self, session) -> None:
        """Atomically save one validated semantic review session."""
        from memcommit.review import ReviewError, ReviewSession

        if not isinstance(session, ReviewSession):
            raise TypeError("Expected a ReviewSession.")
        if self.review_session_file.exists() and (
            not self.review_session_file.is_file()
            or self.review_session_file.is_symlink()
        ):
            raise ValueError("Semantic review session storage is invalid.")
        data = session.to_dict()
        # Validate the exact persisted shape before replacing a recoverable
        # review. In-memory dataclasses are mutable by the TUI controller.
        try:
            ReviewSession.from_dict(data)
        except (ReviewError, TypeError) as error:
            raise ValueError("Semantic review session is invalid.") from error
        _write_json_atomic(self.review_session_file, data)

    # --- Common-grounding sessions ---

    def _ground_session_path(self, contract_name: str) -> Path:
        """Resolve one portable contract ID without creating active state."""
        from memcommit.ground import validate_ground_contract_name

        canonical = validate_ground_contract_name(contract_name)
        if self.ground_sessions_dir.is_symlink():
            raise ValueError("Grounding session storage cannot be a symbolic link.")
        if self.ground_sessions_dir.exists() and not self.ground_sessions_dir.is_dir():
            raise ValueError("Grounding session storage is invalid.")
        return self.ground_sessions_dir / f"{canonical}.json"

    def load_ground_session(self, contract_name: str):
        """Return one named grounding session, or None when it does not exist."""
        from memcommit.ground import GroundError, GroundSession

        path = self._ground_session_path(contract_name)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Grounding session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = GroundSession.from_dict(data)
            if session.contract_name != contract_name:
                raise ValueError(
                    "Saved grounding contract does not match its storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            GroundError,
            ValueError,
        ) as error:
            raise ValueError("Saved grounding session is invalid.") from error

    def save_ground_session(
        self,
        session,
        *,
        replace: bool = False,
        expected_uid: str | None = None,
        expected_revision: int | None = None,
        expected_digest: str | None = None,
        verify_bound_frames: bool = False,
    ) -> None:
        """Persist one validated Ground, optionally using save-boundary CAS.

        The three expected-state fields are intentionally all-or-none.  A
        caller that presents them gets a compare-and-swap whose comparison
        and atomic file replacement occur under the same per-Ground process
        lock.  This closes the gap left by a UI-side freshness check followed
        by a separately launched CLI mutation.  Interactive mutations may
        additionally lock and verify every bound Context frame before taking
        the Ground lock; ordinary setup saves keep that stricter check off.
        """
        from memcommit.ground import GroundError, GroundSession

        if not isinstance(session, GroundSession):
            raise TypeError("Expected a GroundSession.")
        if not isinstance(verify_bound_frames, bool):
            raise ValueError("Ground frame verification flag is invalid.")
        # Fail before Ground lock storage is created when the Profile is
        # already read-only. The later shared guard is still authoritative
        # against a concurrent Profile lock.
        self._assert_profile_write_allowed()
        path = self._ground_session_path(session.contract_name)
        expected_values = (
            expected_uid,
            expected_revision,
            expected_digest,
        )
        if any(value is not None for value in expected_values) and any(
            value is None for value in expected_values
        ):
            raise ValueError(
                "Expected Ground uid, revision, and digest must be supplied together."
            )
        if expected_uid is not None:
            try:
                canonical_expected_uid = str(uuid.UUID(expected_uid))
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError("Expected Ground uid is invalid.") from error
            if canonical_expected_uid != expected_uid:
                raise ValueError("Expected Ground uid is invalid.")
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ValueError("Expected Ground revision is invalid.")
        if expected_digest is not None and (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(character not in "0123456789abcdef" for character in expected_digest)
        ):
            raise ValueError("Expected Ground digest is invalid.")
        data = session.to_dict()
        try:
            restored = GroundSession.from_dict(data)
        except GroundError as error:
            raise ValueError("Grounding session is invalid.") from error
        if restored.contract_name != session.contract_name:
            raise ValueError("Grounding session identity changed during save.")
        with ExitStack() as locks:
            if session.frames:
                # Bound Ground files are part of Context-rename freshness.
                # Enter the graph lock before any Context/Ground locks so a
                # newly created or revised binding cannot escape a concurrent
                # namespace scan. An unbound Ground has no Context locator and
                # retains its deliberate ability to exist without ~/.mem
                # Context state.
                locks.enter_context(self._context_graph_lock(exclusive=False))
            if verify_bound_frames:
                if not session.frames:
                    raise ValueError(
                        "Bound Ground frame verification requires a bound Ground."
                    )
                # Context locks always precede the Ground lock. Future
                # operations that need both must retain this order.
                locks.enter_context(
                    self._context_write_locks(
                        frame.context_name for frame in session.frames
                    )
                )
            locks.enter_context(self._ground_session_write_lock(session.contract_name))
            # Keep the existing graph -> Context -> artifact -> registry lock
            # order. Context lock/unlock also takes Context before registry.
            locks.enter_context(self.profile_write_guard())
            if self.ground_sessions_dir.exists() and (
                not self.ground_sessions_dir.is_dir()
                or self.ground_sessions_dir.is_symlink()
            ):
                raise ValueError("Grounding session storage is invalid.")
            self.ground_sessions_dir.mkdir(parents=True, exist_ok=True)
            if path.exists() and (not path.is_file() or path.is_symlink()):
                raise ValueError("Grounding session storage is invalid.")
            if verify_bound_frames:
                self._verify_ground_frames_locked(session)
            existing = (
                self.load_ground_session(session.contract_name)
                if expected_uid is not None or not replace
                else None
            )
            if expected_uid is not None:
                if existing is None:
                    raise ConcurrentGroundUpdateError(
                        "The named Ground no longer exists."
                    )
                if (
                    existing.uid != expected_uid
                    or existing.revision != expected_revision
                    or ground_session_record_digest(existing) != expected_digest
                ):
                    raise ConcurrentGroundUpdateError(
                        "The named Ground changed before it could be saved."
                    )
            elif existing is not None and not replace and existing.uid != session.uid:
                raise ValueError(
                    "A different grounding session already uses this contract name."
                )
            _write_json_atomic(path, data)

    def _verify_ground_frames_locked(self, session) -> None:
        """Require every bound frame to match while its Context lock is held."""
        from memcommit.ground import context_frame_digest

        for frame in session.frames:
            try:
                context = self.load_direct(frame.context_name)
            except FileNotFoundError as error:
                raise ConcurrentGroundUpdateError(
                    f"Bound Context '{frame.context_name}' no longer exists."
                ) from error
            direct_items = tuple(context.iter_items())
            if (
                context.uid != frame.context_uid
                or context_frame_digest(context) != frame.context_digest
                or sum(isinstance(item, Memory) for item in direct_items)
                != frame.direct_memory_count
                or len(direct_items) != frame.direct_item_count
            ):
                raise ConcurrentGroundUpdateError(
                    f"Bound Context '{frame.context_name}' changed before "
                    "the Ground could be saved."
                )

    # --- Context-to-Context meld sessions ---

    def _meld_choice_branches_path(self, session_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(session_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid Meld choice branch session uid.") from error
        if canonical != session_uid:
            raise ValueError("Invalid Meld choice branch session uid.")
        directory = self.meld_choice_branches_dir
        if directory.is_symlink():
            raise ValueError("Meld choice branch storage cannot be a symbolic link.")
        if directory.exists() and not directory.is_dir():
            raise ValueError("Meld choice branch storage is invalid.")
        return directory / f"{canonical}.json"

    def load_meld_choice_branches(self, session):
        """Restore sparse local choices for the exact current assessment."""
        from memcommit.meld import MeldSession
        from memcommit.meld_choice_branches import (
            MeldChoiceBranchError,
            MeldChoiceBranchSet,
        )

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        path = self._meld_choice_branches_path(session.uid)
        if not path.exists():
            return MeldChoiceBranchSet.empty(session)
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld choice branch storage is invalid.")
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file, object_pairs_hook=_reject_duplicate_json_keys)
            branches = MeldChoiceBranchSet.from_dict(data)
        except (json.JSONDecodeError, MeldChoiceBranchError, ValueError) as error:
            raise ValueError("Saved Meld choice branches are invalid.") from error
        if branches.session_uid != session.uid:
            raise ValueError(
                "Saved Meld choice branches do not match their storage key."
            )
        if branches.target_context_uid != session.target.context_uid:
            raise ValueError("Saved Meld choice branches target a different Context.")
        # A completed reconciliation changes the assessment. Its selections
        # are already retained in the durable user turn, so the old draft set
        # must not leak into a later revision.
        if not branches.matches(session):
            return MeldChoiceBranchSet.empty(session)
        try:
            return branches.validated_for(session)
        except MeldChoiceBranchError as error:
            raise ValueError("Saved Meld choice branches are invalid.") from error

    def save_meld_choice_branches(self, session, branches) -> None:
        """Persist only staged choices; no provider outcome is written here."""
        from memcommit.meld import MeldSession, meld_canonical_digest
        from memcommit.meld_choice_branches import (
            MeldChoiceBranchError,
            MeldChoiceBranchSet,
        )

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        if not isinstance(branches, MeldChoiceBranchSet):
            raise TypeError("Expected a MeldChoiceBranchSet.")
        try:
            restored = MeldChoiceBranchSet.from_dict(
                branches.to_dict()
            ).validated_for(session)
        except MeldChoiceBranchError as error:
            raise ValueError("Meld choice branches are invalid.") from error
        path = self._meld_choice_branches_path(session.uid)
        with self._context_write_lock(session.target.context_name):
            with self.profile_write_guard():
                saved_session = self.load_meld_session(session.target.context_uid)
                if saved_session is None or saved_session.uid != session.uid:
                    raise ConcurrentContextUpdateError(
                        "The Meld session changed before its choices could be saved."
                    )
                if meld_canonical_digest(saved_session.to_dict()) != (
                    meld_canonical_digest(session.to_dict())
                ):
                    raise ConcurrentContextUpdateError(
                        "The Meld assessment changed before its choices could be saved."
                    )
                directory = self.meld_choice_branches_dir
                if directory.exists() and (
                    not directory.is_dir() or directory.is_symlink()
                ):
                    raise ValueError("Meld choice branch storage is invalid.")
                directory.mkdir(parents=True, exist_ok=True)
                if path.exists() and (not path.is_file() or path.is_symlink()):
                    raise ValueError("Meld choice branch storage is invalid.")
                _write_json_atomic(path, restored.to_dict())

    def _meld_resolution_branch_path(self, key: str) -> Path:
        if (
            not isinstance(key, str)
            or len(key) != 64
            or any(character not in "0123456789abcdef" for character in key)
        ):
            raise ValueError("Invalid Meld resolution branch key.")
        directory = self.meld_resolution_branches_dir
        if directory.is_symlink():
            raise ValueError(
                "Meld resolution branch storage cannot be a symbolic link."
            )
        if directory.exists() and not directory.is_dir():
            raise ValueError("Meld resolution branch storage is invalid.")
        return directory / f"{key}.json"

    def load_meld_resolution_branch(self, key: str):
        """Return one exact validated follow-up branch, if it is saved."""
        from memcommit.meld_resolution_cache import (
            MeldResolutionBranch,
            MeldResolutionCacheError,
        )

        path = self._meld_resolution_branch_path(key)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld resolution branch storage is invalid.")
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            branch = MeldResolutionBranch.from_dict(data)
        except (
            json.JSONDecodeError,
            MeldResolutionCacheError,
            ValueError,
        ) as error:
            raise ValueError("Saved Meld resolution branch is invalid.") from error
        if branch.key != key:
            raise ValueError(
                "Saved Meld resolution branch does not match its storage key."
            )
        return branch

    def save_meld_resolution_branch(self, branch) -> None:
        """Publish one immutable exact branch without replacing a peer result."""
        from memcommit.meld_resolution_cache import (
            MeldResolutionBranch,
            MeldResolutionCacheError,
        )

        if not isinstance(branch, MeldResolutionBranch):
            raise TypeError("Expected a MeldResolutionBranch.")
        try:
            restored = MeldResolutionBranch.from_dict(branch.to_dict())
        except MeldResolutionCacheError as error:
            raise ValueError("Meld resolution branch is invalid.") from error
        path = self._meld_resolution_branch_path(restored.key)
        with self._meld_resolution_branch_write_lock():
            with self.profile_write_guard():
                directory = self.meld_resolution_branches_dir
                if directory.exists() and (
                    not directory.is_dir() or directory.is_symlink()
                ):
                    raise ValueError("Meld resolution branch storage is invalid.")
                directory.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    existing = self.load_meld_resolution_branch(restored.key)
                    assert existing is not None
                    if existing.to_dict() != restored.to_dict():
                        # One exact semantic request has one durable cached
                        # outcome. A concurrent stochastic result must not
                        # silently replace the branch another session reused.
                        raise ValueError(
                            "A different Meld resolution branch already uses "
                            "this exact request key."
                        )
                    return
                _write_json_atomic(path, restored.to_dict())

    def _meld_session_path(self, target_context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(target_context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid meld target Context uid.") from error
        if canonical != target_context_uid:
            raise ValueError("Invalid meld target Context uid.")
        if self.meld_sessions_dir.is_symlink():
            raise ValueError("Meld session storage cannot be a symbolic link.")
        if self.meld_sessions_dir.exists() and not self.meld_sessions_dir.is_dir():
            raise ValueError("Meld session storage is invalid.")
        return self.meld_sessions_dir / f"{canonical}.json"

    def load_meld_session(self, target_context_uid: str):
        """Return the saved meld for one target Context, if present."""
        from memcommit.meld import MeldError, MeldSession

        path = self._meld_session_path(target_context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = MeldSession.from_dict(data)
        except (
            json.JSONDecodeError,
            MeldError,
            ValueError,
        ) as error:
            raise ValueError("Saved meld session is invalid.") from error
        if session.target.context_uid != target_context_uid:
            raise ValueError(
                "Saved meld session does not match its target storage key."
            )
        return session

    def save_meld_session(
        self,
        session,
        *,
        expected_session_digest: str | None = None,
    ) -> None:
        """Persist one meld session with target-scoped optimistic concurrency."""
        from memcommit.meld import (
            MeldError,
            MeldSession,
            meld_canonical_digest,
        )

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        path = self._meld_session_path(session.target.context_uid)
        data = session.to_dict()
        try:
            restored = MeldSession.from_dict(data)
        except MeldError as error:
            raise ValueError("Meld session is invalid.") from error
        if restored.uid != session.uid:
            raise ValueError("Meld session identity changed during save.")

        # The Context lock coordinates the target artifact with its Context
        # transaction.  The session digest separately prevents two semantic
        # replies from silently replacing one another.
        with self._context_write_lock(session.target.context_name):
            with self.profile_write_guard():
                if self.meld_sessions_dir.exists() and (
                    not self.meld_sessions_dir.is_dir()
                    or self.meld_sessions_dir.is_symlink()
                ):
                    raise ValueError("Meld session storage is invalid.")
                self.meld_sessions_dir.mkdir(parents=True, exist_ok=True)
                if path.exists() and (not path.is_file() or path.is_symlink()):
                    raise ValueError("Meld session storage is invalid.")
                if path.exists():
                    with open(path, encoding="utf-8") as file:
                        current = json.load(
                            file,
                            object_pairs_hook=_reject_duplicate_json_keys,
                        )
                    current_digest = meld_canonical_digest(current)
                    if expected_session_digest is None:
                        raise ConcurrentContextUpdateError(
                            "A meld session already exists for this target."
                        )
                    if current_digest != expected_session_digest:
                        raise ConcurrentContextUpdateError(
                            "The meld session changed before it could be saved."
                        )
                elif expected_session_digest is not None:
                    raise ConcurrentContextUpdateError(
                        "The meld session no longer exists."
                    )
                _write_json_atomic(path, data)

    def create_meld_target_with_session(
        self,
        ctx: Context,
        session,
        auto_checkpoint: AutoCheckpoint,
    ) -> None:
        """Atomically publish a new empty symmetric target and its session.

        ``meld --to`` must not leave a selectable empty Context when session
        publication fails. Both records therefore share the command and target
        locks, and the exact new Context is rolled back before either lock is
        released if the session cannot be written.
        """
        from memcommit.meld import MeldError, MeldSession

        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        if session.mode != "SYMMETRIC":
            raise ValueError("A new Meld result requires a symmetric session.")
        if (
            session.target.context_uid != ctx.uid
            or session.target.context_name != ctx.name
            or context_record_digest(ctx) != session.target.context_digest
        ):
            raise ValueError("Meld session does not bind the new target exactly.")
        if tuple(ctx.iter_items()):
            raise ValueError("A new symmetric Meld target must be empty.")

        path = self._meld_session_path(ctx.uid)
        data = session.to_dict()
        try:
            restored = MeldSession.from_dict(data)
        except MeldError as error:
            raise ValueError("Meld session is invalid.") from error
        if restored.uid != session.uid:
            raise ValueError("Meld session identity changed during save.")

        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_lock(ctx.name):
                    with self.profile_write_guard():
                        if self.meld_sessions_dir.exists() and (
                            not self.meld_sessions_dir.is_dir()
                            or self.meld_sessions_dir.is_symlink()
                        ):
                            raise ValueError("Meld session storage is invalid.")
                        if path.exists() or path.is_symlink():
                            raise ConcurrentContextUpdateError(
                                "A meld session already exists for the new "
                                "target identity."
                            )
                        self._save_locked(
                            ctx,
                            auto_checkpoint,
                            expected_context_digest=None,
                            require_new=True,
                        )
                        try:
                            self.meld_sessions_dir.mkdir(parents=True, exist_ok=True)
                            _write_json_atomic(path, data)
                        except Exception as error:
                            try:
                                # No lifecycle deletion is recorded: the new
                                # result was never a successfully committed
                                # command outcome.
                                self._delete_locked(ctx.name)
                            except Exception as rollback_error:
                                raise RuntimeError(
                                    "Meld result creation failed and its exact "
                                    "new Context could not be rolled back."
                                ) from rollback_error
                            raise error
        ctx._store_digest = context_record_digest(ctx)

    @_profile_write_guarded
    def delete_meld_session(self, target_context_uid: str) -> None:
        """Remove one exact target-bound meld artifact."""
        path = self._meld_session_path(target_context_uid)
        if not path.exists():
            return
        if not path.is_file() or path.is_symlink():
            raise ValueError("Meld session storage is invalid.")
        path.unlink()

    # --- Saved semantic analyses ---

    def _atomize_analysis_path(self, context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize analysis Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize analysis Context uid.")
        if self.atomize_analyses_dir.is_symlink():
            raise ValueError("Atomize analysis storage cannot be a symbolic link.")
        if (
            self.atomize_analyses_dir.exists()
            and not self.atomize_analyses_dir.is_dir()
        ):
            raise ValueError("Atomize analysis storage is invalid.")
        return self.atomize_analyses_dir / f"{canonical}.json"

    def load_atomize_analysis(self, context_uid: str):
        """Return one Context's latest saved atomize preview, or None."""
        from memcommit.atomize import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )

        path = self._atomize_analysis_path(context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize analysis storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeAnalysisSession.from_dict(data)
            if session.context_uid != context_uid:
                raise ValueError(
                    "Saved atomize analysis Context identity does not match "
                    "its storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            ValueError,
            AtomizeImpactError,
        ) as error:
            raise ValueError("Saved atomize analysis is invalid.") from error

    @_profile_write_guarded
    def save_atomize_analysis(self, session) -> None:
        """Atomically persist a validated, non-applying atomize preview."""

        from memcommit.atomize import AtomizeAnalysisSession

        if not isinstance(session, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")

        with self._atomize_session_write_lock(session.context_uid):
            self._save_atomize_analysis_locked(session)

    def _save_atomize_analysis_locked(self, session) -> None:
        """Persist one analysis while its Context-scoped CAS lock is held."""

        from memcommit.atomize import (
            AtomizeAnalysisSession,
            AtomizeImpactError,
        )

        self._assert_profile_write_allowed()
        if not isinstance(session, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        path = self._atomize_analysis_path(session.context_uid)
        if self.atomize_analyses_dir.exists() and (
            not self.atomize_analyses_dir.is_dir()
            or self.atomize_analyses_dir.is_symlink()
        ):
            raise ValueError("Atomize analysis storage is invalid.")
        self.atomize_analyses_dir.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize analysis storage is invalid.")
        data = session.to_dict()
        try:
            AtomizeAnalysisSession.from_dict(data)
        except AtomizeImpactError as error:
            raise ValueError("Atomize analysis is invalid.") from error
        _write_json_atomic(path, data)

    @_profile_write_guarded
    def delete_atomize_analysis(self, context_uid: str) -> None:
        """Remove one derived analysis artifact during failed save-as cleanup."""
        with self._atomize_session_write_lock(context_uid):
            path = self._atomize_analysis_path(context_uid)
            if path.exists():
                if not path.is_file() or path.is_symlink():
                    raise ValueError("Atomize analysis storage is invalid.")
                path.unlink()

    # --- Context-bound atomize workbenches ---

    def _atomize_workbench_path(self, context_uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize workbench Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize workbench Context uid.")
        if self.atomize_workbenches_dir.is_symlink():
            raise ValueError("Atomize workbench storage cannot be a symbolic link.")
        if (
            self.atomize_workbenches_dir.exists()
            and not self.atomize_workbenches_dir.is_dir()
        ):
            raise ValueError("Atomize workbench storage is invalid.")
        return self.atomize_workbenches_dir / f"{canonical}.json"

    def load_atomize_workbench(self, analysis):
        """Load mutable state only against one exact saved analysis."""
        from memcommit.atomize import AtomizeAnalysisSession
        from memcommit.atomize_workbench import (
            AtomizeWorkbenchError,
            AtomizeWorkbenchSession,
            atomize_workbench_issue_projection,
        )

        if not isinstance(analysis, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        path = self._atomize_workbench_path(analysis.context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize workbench storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeWorkbenchSession.from_dict(
                data,
                issues=atomize_workbench_issue_projection(analysis),
            )
            if (
                session.analysis_uid != analysis.uid
                or session.context_uid != analysis.context_uid
            ):
                raise ValueError(
                    "Saved atomize workbench identity does not match its "
                    "analysis or storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            AtomizeWorkbenchError,
            ValueError,
        ) as error:
            raise ValueError("Saved atomize workbench is invalid.") from error

    @_profile_write_guarded
    def save_atomize_workbench(self, session) -> None:
        """Atomically persist one Context-bound mutable workbench."""
        from memcommit.atomize_workbench import AtomizeWorkbenchSession

        if not isinstance(session, AtomizeWorkbenchSession):
            raise TypeError("Expected an AtomizeWorkbenchSession.")
        with self._atomize_session_write_lock(session.context_uid):
            self._save_atomize_workbench_locked(session)

    def _save_atomize_workbench_locked(self, session) -> None:
        """Persist one workbench while its Context-scoped CAS lock is held."""
        from memcommit.atomize_workbench import (
            AtomizeWorkbenchError,
            AtomizeWorkbenchSession,
            atomize_workbench_issue_projection,
        )

        self._assert_profile_write_allowed()
        if not isinstance(session, AtomizeWorkbenchSession):
            raise TypeError("Expected an AtomizeWorkbenchSession.")
        path = self._atomize_workbench_path(session.context_uid)
        if self.atomize_workbenches_dir.exists() and (
            not self.atomize_workbenches_dir.is_dir()
            or self.atomize_workbenches_dir.is_symlink()
        ):
            raise ValueError("Atomize workbench storage is invalid.")
        self.atomize_workbenches_dir.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize workbench storage is invalid.")
        data = session.to_dict()
        try:
            AtomizeWorkbenchSession.from_dict(
                data,
                issues=session.issues,
            )
        except AtomizeWorkbenchError as error:
            raise ValueError("Atomize workbench is invalid.") from error
        analysis = self.load_atomize_analysis(session.context_uid)
        if analysis is None or not session.matches_analysis(
            analysis_uid=analysis.uid,
            context_uid=analysis.context_uid,
            context_name=analysis.context_name,
            context_digest=analysis.context_digest,
            issues=atomize_workbench_issue_projection(analysis),
        ):
            raise ValueError("Atomize workbench does not match the saved analysis.")
        _write_json_atomic(path, data)

    @_profile_write_guarded
    def delete_atomize_workbench(self, context_uid: str) -> None:
        """Remove derived UI state during failed save-as cleanup."""
        with self._atomize_session_write_lock(context_uid):
            path = self._atomize_workbench_path(context_uid)
            if path.exists():
                if not path.is_file() or path.is_symlink():
                    raise ValueError("Atomize workbench storage is invalid.")
                path.unlink()

    # --- Conversational atomize grounding sessions ---

    def _atomize_grounding_session_path(self, context_uid: str) -> Path:
        """Resolve one Context-bound dialogue without trusting path text."""
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize grounding Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize grounding Context uid.")
        if self.atomize_grounding_sessions_dir.is_symlink():
            raise ValueError("Atomize grounding storage cannot be a symbolic link.")
        if (
            self.atomize_grounding_sessions_dir.exists()
            and not self.atomize_grounding_sessions_dir.is_dir()
        ):
            raise ValueError("Atomize grounding storage is invalid.")
        return self.atomize_grounding_sessions_dir / f"{canonical}.json"

    def _atomize_grounding_history_dir(self, context_uid: str) -> Path:
        """Resolve one Context's immutable terminal-dialogue archive."""
        try:
            canonical = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize grounding Context uid.") from error
        if canonical != context_uid:
            raise ValueError("Invalid atomize grounding Context uid.")
        if self.atomize_grounding_history_dir.is_symlink():
            raise ValueError("Atomize grounding history cannot be a symbolic link.")
        if (
            self.atomize_grounding_history_dir.exists()
            and not self.atomize_grounding_history_dir.is_dir()
        ):
            raise ValueError("Atomize grounding history is invalid.")
        directory = self.atomize_grounding_history_dir / canonical
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError("Atomize grounding history is invalid.")
        return directory

    def _atomize_grounding_history_path(
        self,
        context_uid: str,
        session_uid: str,
    ) -> Path:
        try:
            canonical_session = str(uuid.UUID(session_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid atomize grounding session uid.") from error
        if canonical_session != session_uid:
            raise ValueError("Invalid atomize grounding session uid.")
        return (
            self._atomize_grounding_history_dir(context_uid)
            / f"{canonical_session}.json"
        )

    def load_atomize_grounding_session(self, context_uid: str):
        """Return one Context's latest atomize grounding dialogue, if any."""
        from memcommit.atomize_grounding import (
            AtomizeGroundingError,
            AtomizeGroundingSession,
        )

        path = self._atomize_grounding_session_path(context_uid)
        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Atomize grounding storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(
                    f,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            session = AtomizeGroundingSession.from_dict(data)
            if session.bindings.context_uid != context_uid:
                raise ValueError(
                    "Saved atomize grounding Context identity does not match "
                    "its storage key."
                )
            return session
        except (
            json.JSONDecodeError,
            AtomizeGroundingError,
            ValueError,
        ) as error:
            raise ValueError("Saved atomize grounding session is invalid.") from error

    @_profile_write_guarded
    def save_atomize_grounding_session(self, session) -> None:
        """Atomically persist one strict Context-bound grounding dialogue."""
        from memcommit.atomize_grounding import (
            AtomizeGroundingError,
            AtomizeGroundingSession,
        )

        if not isinstance(session, AtomizeGroundingSession):
            raise TypeError("Expected an AtomizeGroundingSession.")
        path = self._atomize_grounding_session_path(session.bindings.context_uid)
        if self.atomize_grounding_sessions_dir.exists() and (
            not self.atomize_grounding_sessions_dir.is_dir()
            or self.atomize_grounding_sessions_dir.is_symlink()
        ):
            raise ValueError("Atomize grounding storage is invalid.")
        self.atomize_grounding_sessions_dir.mkdir(parents=True, exist_ok=True)
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Atomize grounding storage is invalid.")
        data = session.to_dict()
        try:
            restored = AtomizeGroundingSession.from_dict(data)
        except AtomizeGroundingError as error:
            raise ValueError("Atomize grounding session is invalid.") from error
        if (
            restored.uid != session.uid
            or restored.bindings.context_uid != session.bindings.context_uid
        ):
            raise ValueError("Atomize grounding identity changed during save.")
        if session.state in {"APPLIED", "KEPT_REVIEW_ONLY"}:
            # Terminal conversations are evidence, not disposable UI state.
            # Archive them before replacing the latest slot so a subsequent
            # grounding round cannot silently erase reviewer comments.
            history_path = self._atomize_grounding_history_path(
                session.bindings.context_uid,
                session.uid,
            )
            history_dir = history_path.parent
            self.atomize_grounding_history_dir.mkdir(
                parents=True,
                exist_ok=True,
            )
            history_dir.mkdir(exist_ok=True)
            if history_path.exists() or history_path.is_symlink():
                if not history_path.is_file() or history_path.is_symlink():
                    raise ValueError("Atomize grounding history is invalid.")
                with open(history_path, encoding="utf-8") as f:
                    archived = json.load(
                        f,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                if archived != data:
                    raise ValueError("Atomize grounding history is immutable.")
            else:
                _write_json_atomic(history_path, data)
        _write_json_atomic(path, data)

    def load_atomize_grounding_history(
        self,
        context_uid: str,
    ) -> list:
        """Load immutable terminal dialogues for one exact Context."""
        from memcommit.atomize_grounding import (
            AtomizeGroundingError,
            AtomizeGroundingSession,
        )

        directory = self._atomize_grounding_history_dir(context_uid)
        if not directory.exists():
            return []
        sessions = []
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Atomize grounding history is invalid.")
            try:
                with open(path, encoding="utf-8") as f:
                    value = json.load(
                        f,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                session = AtomizeGroundingSession.from_dict(value)
            except (
                json.JSONDecodeError,
                AtomizeGroundingError,
                ValueError,
            ) as error:
                raise ValueError("Atomize grounding history is invalid.") from error
            if (
                session.bindings.context_uid != context_uid
                or session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}
                or path.stem != session.uid
            ):
                raise ValueError("Atomize grounding history is invalid.")
            sessions.append(session)
        return sessions

    # --- Context paths ---

    def _assert_context_storage_root(self) -> bool:
        """Return whether the ordinary root exists, rejecting unsafe aliases.

        A symlink at ``contexts/`` used to bypass the per-namespace symlink
        checks because every descendant resolved inside the aliased root.  All
        ordinary Context paths enter through this guard so a catalog read and a
        later load/write enforce the same storage boundary.
        """
        if self.contexts_dir.is_symlink():
            raise ValueError("Context storage root cannot be a symbolic link.")
        if not self.contexts_dir.exists():
            return False
        if not self.contexts_dir.is_dir():
            raise ValueError("Context storage root is not a directory.")
        return True

    def _catalog_diagnostic(
        self,
        code: ContextCatalogDiagnosticCode,
        path: Path,
        *,
        context_name: str | None,
        message: str,
    ) -> ContextCatalogDiagnostic:
        try:
            relative_path = path.relative_to(self.contexts_dir).as_posix()
        except ValueError:
            relative_path = str(path)
        return ContextCatalogDiagnostic(
            code=code,
            relative_path=relative_path or ".",
            context_name=context_name,
            message=message,
        )

    def _scan_context_record_paths(
        self,
    ) -> tuple[
        tuple[tuple[str, Path], ...],
        tuple[ContextCatalogDiagnostic, ...],
    ]:
        """Discover ordinary record paths without following namespace links."""
        if not self._assert_context_storage_root():
            return (), ()

        records: list[tuple[str, Path]] = []
        diagnostics: list[ContextCatalogDiagnostic] = []
        pending = [self.contexts_dir]
        while pending:
            directory = pending.pop()
            try:
                entries = tuple(
                    sorted(directory.iterdir(), key=lambda entry: entry.name)
                )
            except OSError as error:
                diagnostics.append(
                    self._catalog_diagnostic(
                        "UNREADABLE_ENTRY",
                        directory,
                        context_name=None,
                        message=f"Context namespace could not be read: {error}",
                    )
                )
                continue

            child_directories: list[Path] = []
            for entry in entries:
                # Checkpoint snapshots are history, not ordinary Contexts. Their
                # own readers retain the stricter checkpoint-specific boundary.
                if entry.name == "checkpoints":
                    continue
                try:
                    if entry.is_symlink():
                        diagnostics.append(
                            self._catalog_diagnostic(
                                "UNSAFE_ENTRY",
                                entry,
                                context_name=None,
                                message=(
                                    "Context storage contains a symbolic-link entry."
                                ),
                            )
                        )
                        continue
                    if entry.is_dir():
                        if entry.name == "context.json":
                            diagnostics.append(
                                self._catalog_diagnostic(
                                    "UNSAFE_ENTRY",
                                    entry,
                                    context_name=None,
                                    message=(
                                        "Context record path is not a regular file."
                                    ),
                                )
                            )
                        else:
                            child_directories.append(entry)
                        continue
                    if entry.name != "context.json":
                        if not entry.is_file():
                            diagnostics.append(
                                self._catalog_diagnostic(
                                    "UNSAFE_ENTRY",
                                    entry,
                                    context_name=None,
                                    message=(
                                        "Context storage contains a special entry."
                                    ),
                                )
                            )
                        continue
                    if not entry.is_file():
                        diagnostics.append(
                            self._catalog_diagnostic(
                                "UNSAFE_ENTRY",
                                entry,
                                context_name=None,
                                message=("Context record path is not a regular file."),
                            )
                        )
                        continue
                except OSError as error:
                    diagnostics.append(
                        self._catalog_diagnostic(
                            "UNREADABLE_ENTRY",
                            entry,
                            context_name=None,
                            message=f"Context storage entry is unreadable: {error}",
                        )
                    )
                    continue

                name = entry.parent.relative_to(self.contexts_dir).as_posix()
                try:
                    _context_name_parts(name)
                except ValueError as error:
                    diagnostics.append(
                        self._catalog_diagnostic(
                            "INVALID_LOCATOR",
                            entry,
                            context_name=name,
                            message=str(error),
                        )
                    )
                    continue
                records.append((name, entry))

            # Reverse the sorted children because ``pending`` is a LIFO stack.
            pending.extend(reversed(child_directories))

        return tuple(sorted(records)), tuple(diagnostics)

    def scan_context_catalog(self) -> ContextCatalogScan:
        """Return header-valid ordinary names and typed omission diagnostics."""
        records, diagnostics = self._scan_context_record_paths()
        names: list[str] = []
        found_diagnostics = list(diagnostics)
        for name, context_file in records:
            try:
                with open(context_file, encoding="utf-8") as file:
                    data = json.load(file)
            except OSError as error:
                found_diagnostics.append(
                    self._catalog_diagnostic(
                        "UNREADABLE_ENTRY",
                        context_file,
                        context_name=name,
                        message=f"Context record could not be read: {error}",
                    )
                )
                continue
            except (UnicodeError, json.JSONDecodeError) as error:
                found_diagnostics.append(
                    self._catalog_diagnostic(
                        "INVALID_JSON",
                        context_file,
                        context_name=name,
                        message=f"Context record is invalid JSON: {error}",
                    )
                )
                continue
            try:
                _validate_context_header(data, name)
            except ValueError as error:
                found_diagnostics.append(
                    self._catalog_diagnostic(
                        "INVALID_HEADER",
                        context_file,
                        context_name=name,
                        message=str(error),
                    )
                )
                continue
            names.append(name)
        return ContextCatalogScan(
            names=tuple(sorted(names)),
            diagnostics=tuple(found_diagnostics),
        )

    def _context_dir(self, name: str) -> Path:
        self._assert_context_storage_root()
        parts = _context_name_parts(name)
        path = self.contexts_dir.joinpath(*parts)
        candidate = self.contexts_dir
        for part in parts:
            candidate /= part
            if candidate.is_symlink():
                raise ValueError(
                    f"Invalid context name '{name}': symbolic links are not "
                    "allowed in context namespaces."
                )
            if candidate.exists() and not candidate.is_dir():
                raise ValueError(
                    f"Invalid context name '{name}': namespace component "
                    f"'{candidate.name}' is not a directory."
                )
        contexts_root = self.contexts_dir.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Invalid context name '{name}': path escapes the context store."
            )
        return path

    def _context_file(self, name: str) -> Path:
        return self._context_dir(name) / "context.json"

    def _checkpoints_dir(self, name: str) -> Path:
        path = self._context_dir(name) / "checkpoints"
        if path.is_symlink():
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' through a symbolic link."
            )
        contexts_root = self.contexts_dir.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' outside the "
                "context store."
            )
        return path

    def _context_lifecycle_events_dir(self) -> Path:
        """Return the active Profile's ledger path without creating it."""
        ledger_dir = self.store_dir / "ledger"
        events_dir = ledger_dir / "context-events"
        for path, label in (
            (ledger_dir, "Context lifecycle ledger"),
            (events_dir, "Context lifecycle event storage"),
        ):
            if path.is_symlink():
                raise ValueError(f"{label} cannot be a symbolic link.")
            if path.exists() and not path.is_dir():
                raise ValueError(f"{label} must be a directory.")
        return events_dir

    def _ensure_context_lifecycle_events_dir(self) -> Path:
        events_dir = self._context_lifecycle_events_dir()
        ledger_dir = events_dir.parent
        ledger_created = not ledger_dir.exists()
        ledger_dir.mkdir(exist_ok=True, mode=0o700)
        if ledger_created:
            _fsync_directory(self.store_dir)
        events_created = not events_dir.exists()
        events_dir.mkdir(exist_ok=True, mode=0o700)
        if events_created:
            _fsync_directory(ledger_dir)
        return events_dir

    @contextmanager
    def _context_lifecycle_ledger_lock(
        self,
        *,
        exclusive: bool,
    ) -> Iterator[None]:
        """Hide provisional event publication from concurrent ledger readers."""
        lock_path = self.store_dir / "context-lifecycle-ledger.lock"
        if lock_path.is_symlink():
            raise ValueError("Refusing to use a symbolic-link lifecycle lock.")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
                )
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    def _write_context_lifecycle_event(
        self,
        event: ContextLifecycleEvent,
    ) -> Path:
        """Publish one immutable Profile-ledger event before destructive work."""
        event.validated()
        _context_name_parts(event.last_context_name)
        events_dir = self._ensure_context_lifecycle_events_dir()
        path = events_dir / f"{event.event_uid}.json"
        if path.exists() or path.is_symlink():
            raise FileExistsError("Context lifecycle event already exists.")
        try:
            _write_json_atomic(path, event.to_dict())
            _fsync_directory(events_dir)
        except Exception:
            if path.exists() and not path.is_symlink():
                path.unlink()
                _fsync_directory(events_dir)
            raise
        return path

    @staticmethod
    def _remove_context_lifecycle_event(path: Path) -> None:
        """Roll back an event when deletion fails before its commit boundary."""
        if path.is_symlink() or not path.is_file():
            raise ValueError("Context lifecycle event rollback path is unsafe.")
        path.unlink()
        _fsync_directory(path.parent)

    def list_context_lifecycle_events(
        self,
        *,
        context_name: str | None = None,
        context_uid: str | None = None,
        recursive: bool = False,
    ) -> list[ContextLifecycleEvent]:
        """Read Profile-ledger events, optionally filtering one namespace."""
        if context_name is not None:
            _context_name_parts(context_name)
        if context_uid is not None and (
            not isinstance(context_uid, str) or not context_uid
        ):
            raise ValueError("Context lifecycle Context uid must be non-empty.")
        events_dir = self._context_lifecycle_events_dir()
        if not events_dir.exists():
            # An absent ledger has no publication to coordinate with. Returning
            # here also keeps read-only inspection from creating a lock file.
            return []
        with self._context_lifecycle_ledger_lock(exclusive=False):
            events_dir = self._context_lifecycle_events_dir()
            if not events_dir.exists():
                return []
            events: list[ContextLifecycleEvent] = []
            for path in events_dir.iterdir():
                if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                    raise ValueError("Context lifecycle event storage is invalid.")
                try:
                    with open(path, encoding="utf-8") as file:
                        data = json.load(
                            file,
                            object_pairs_hook=_reject_duplicate_json_keys,
                        )
                    event = ContextLifecycleEvent.from_dict(data)
                except (
                    OSError,
                    UnicodeError,
                    json.JSONDecodeError,
                    ValueError,
                ) as error:
                    raise ValueError(
                        f"Context lifecycle event '{path.name}' is invalid."
                    ) from error
                if path.name != f"{event.event_uid}.json":
                    raise ValueError(
                        "Context lifecycle event filename does not match its uid."
                    )
                _context_name_parts(event.last_context_name)
                if context_uid is not None and event.context_uid != context_uid:
                    continue
                if context_name is not None:
                    in_scope = event.last_context_name == context_name
                    if recursive:
                        in_scope = in_scope or event.last_context_name.startswith(
                            context_name + "/"
                        )
                    if not in_scope:
                        continue
                events.append(event)
            return sorted(
                events,
                key=lambda event: datetime.fromisoformat(event.timestamp),
                reverse=True,
            )

    def context_exists(self, name: str) -> bool:
        if not self._assert_context_storage_root():
            return False
        try:
            context_file = self._context_file(name)
        except (OSError, TypeError, ValueError):
            return False
        return context_file.is_file() and not context_file.is_symlink()

    def list_context_names(self) -> list[str]:
        return list(self.scan_context_catalog().names)

    def _assert_context_storage_available(self, name: str) -> None:
        """Allow a new root Context when only namespace directories predate it."""
        context_dir = self._context_dir(name)
        if not context_dir.exists():
            return
        invalid_entries = [
            entry.name
            for entry in context_dir.iterdir()
            if (
                entry.is_symlink()
                or not entry.is_dir()
                or entry.name.casefold() in RESERVED_CONTEXT_SEGMENTS
            )
        ]
        if invalid_entries:
            raise ValueError(
                f"Cannot create context '{name}': its storage directory already "
                "exists and is not empty; only child namespace directories may "
                "precede a root Context. Invalid entries: "
                + ", ".join(sorted(invalid_entries))
            )

    def _prune_empty_namespace_dirs(self, start: Path) -> None:
        """Remove empty namespace directories without removing self.contexts_dir."""
        candidate = start
        while candidate != self.contexts_dir:
            try:
                candidate.rmdir()
            except OSError:
                break
            candidate = candidate.parent

    # --- Load / Save ---

    def _load_direct_memory(
        self,
        context_name: str,
        expected_context_uid: str,
        memory_uid: str,
    ) -> Memory | None:
        """
        Resolve one directly owned Memory without recursively loading its Context.

        Reading the raw context file avoids MemoryRef chains and Context embed
        cycles. The Context uid check prevents a deleted/recreated context with
        the same name from silently becoming the new target.
        """
        if not self.context_exists(context_name):
            return None
        with open(self._context_file(context_name)) as f:
            data = json.load(f)
        try:
            data = _validate_context_header(data, context_name)
        except ValueError:
            return None
        if data.get("uid") != expected_context_uid:
            return None

        item = data.get("memories", {}).get(memory_uid)
        if (
            not isinstance(item, dict)
            or item.get("type") != "memory"
            or item.get("uid") != memory_uid
        ):
            return None
        return Memory.from_dict(item)

    def load(self, name: str, _loading: frozenset[str] = frozenset()) -> Context:
        """Load a context by name, resolving embedded context refs as live loads."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)

        def loader(ref_name: str) -> Context | None:
            if ref_name in _loading:
                return None  # break circular reference
            if not self.context_exists(ref_name):
                return None
            return self.load(ref_name, _loading | {name})

        def granted_loader(link):
            # Import lazily: authority access depends on MemoryStore, while the
            # Store needs only this runtime reauthorization callback.
            from memcommit.authority.access import load_granted_context_link

            return load_granted_context_link(
                link,
                active_store=self,
                loading=_loading | {name},
            )

        try:
            ctx = Context.from_dict(
                data,
                loader=loader,
                memory_loader=self._load_direct_memory,
                granted_loader=granted_loader,
            )
            # A loaded Context carries the exact logical version it was based
            # on. Every later ordinary save uses it for optimistic concurrency
            # so a stale writer cannot erase a completed operation.
            ctx._store_digest = context_record_digest(data)
            return ctx
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Context file for '{name}' has an invalid memory structure: {e}"
            ) from e

    def load_direct(self, name: str) -> Context:
        """
        Load one Context record without opening any referenced Context files.

        Read-only operations whose scope is explicitly limited to directly
        owned Memories must not resolve embedded Contexts or MemoryRef targets
        before filtering. QueryContextRefs remain opaque under both load paths.
        """
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)
        try:
            ctx = Context.from_dict(data)
            ctx._store_digest = context_record_digest(data)
            return ctx
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Context file for '{name}' has an invalid memory structure: {e}"
            ) from e

    def load_for_update(self, name: str) -> Context:
        """Load a Context without permitting unresolved direct Context refs.

        Normal ``load`` intentionally tolerates a missing embedded Context for
        read paths. A mutating command must be stricter: serializing that
        partially resolved object would silently erase the unresolved pointer.
        """
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)
        direct_context_refs = {
            uid: item.get("name")
            for uid, item in data["memories"].items()
            if isinstance(item, dict) and item.get("type") == "context_ref"
        }
        direct_granted_refs = {
            uid: item.get("name")
            for uid, item in data["memories"].items()
            if isinstance(item, dict) and item.get("type") == "granted_context_ref"
        }
        ctx = self.load(name)
        for uid, expected_name in direct_context_refs.items():
            item = ctx.memories.get(uid)
            if not isinstance(item, Context) or item.name != expected_name:
                raise ValueError(
                    f"Context '{name}' contains an unavailable embedded "
                    f"Context reference '{expected_name}'. Refusing to save "
                    "a partial load."
                )
        for uid, expected_name in direct_granted_refs.items():
            item = ctx.memories.get(uid)
            if (
                not isinstance(item, Context)
                or item.name != expected_name
                or item._granted_link is None
            ):
                raise ValueError(
                    f"Context '{name}' contains an unavailable granted "
                    f"Context reference '{expected_name}'. Refusing to save "
                    "a partial load."
                )
        return ctx

    def load_current(self) -> Context:
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load(name)

    def load_current_direct(self) -> Context:
        """Load the current Context through the non-resolving direct path."""
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load_direct(name)

    def assert_context_creatable(self, name: str) -> None:
        """Fail before expensive work when a new Context cannot use this name."""
        validate_portable_context_name(name)
        if self.context_exists(name):
            raise FileExistsError(f"Context '{name}' already exists.")
        self._assert_context_storage_available(name)

    def _read_direct_context_records_strict(
        self,
    ) -> dict[str, dict[str, object]]:
        """Read every ordinary direct record or reject an incomplete graph."""
        record_paths, diagnostics = self._scan_context_record_paths()
        if diagnostics:
            diagnostic = diagnostics[0]
            raise ValueError(
                "Context storage scan is incomplete at "
                f"'{diagnostic.relative_path}': {diagnostic.message}"
            )

        records: dict[str, dict[str, object]] = {}
        uid_owners: dict[str, str] = {}
        for name, context_file in record_paths:
            try:
                with open(context_file, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
                raise ValueError(f"Context '{name}' is invalid JSON.") from error
            record = _validate_context_header(raw, name)
            # Parse without loaders so strict graph discovery never opens an
            # embedded Context, MemoryRef target, or query-only source.
            try:
                Context.from_dict(record)
                _rewrite_context_pointers(
                    record,
                    moved_names_by_uid={},
                    rewrite_owner_name=False,
                    require_current_pointer_names=True,
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Context '{name}' has an invalid direct record: {error}"
                ) from error
            uid = record["uid"]
            previous = uid_owners.get(uid)
            if previous is not None:
                raise ValueError(
                    f"Ordinary Context uid is duplicated by '{previous}' and '{name}'."
                )
            uid_owners[uid] = name
            records[name] = record
        return records

    def load_direct_context_graph_strict(self) -> tuple[Context, ...]:
        """Load one complete direct ordinary graph without resolving pointers.

        Unlike :meth:`list_context_names`, this API is a completeness boundary
        for mutation preflights. Any malformed, unsafe, unreadable, or
        duplicate record fails the whole scan instead of becoming an omitted
        name.
        """
        contexts: list[Context] = []
        for name, record in self._read_direct_context_records_strict().items():
            try:
                context = Context.from_dict(record)
            except (KeyError, TypeError, ValueError) as error:
                # The private record reader already performs this validation;
                # retain a local guard so this public API never returns partial
                # results if the model's constructor changes later.
                raise ValueError(
                    f"Context '{name}' has an invalid direct record: {error}"
                ) from error
            context._store_digest = context_record_digest(record)
            contexts.append(context)
        return tuple(contexts)

    def _read_context_graph_for_rename(
        self,
    ) -> tuple[
        dict[str, dict[str, object]],
        dict[str, dict[str, dict[str, object]]],
    ]:
        """Read every ordinary record and restorable checkpoint fail-closed."""
        records = self._read_direct_context_records_strict()
        checkpoints: dict[str, dict[str, dict[str, object]]] = {}
        for name in records:
            checkpoint_dir = self._checkpoints_dir(name)
            entries: dict[str, dict[str, object]] = {}
            if checkpoint_dir.exists():
                if checkpoint_dir.is_symlink() or not checkpoint_dir.is_dir():
                    raise ValueError(
                        f"Checkpoints for '{name}' are not a safe directory."
                    )
                for checkpoint_file in sorted(checkpoint_dir.iterdir()):
                    if (
                        checkpoint_file.is_symlink()
                        or not checkpoint_file.is_file()
                        or checkpoint_file.suffix != ".json"
                    ):
                        raise ValueError(
                            f"Checkpoints for '{name}' contain an unsafe entry."
                        )
                    try:
                        with open(checkpoint_file, encoding="utf-8") as file:
                            raw_checkpoint = json.load(
                                file,
                                object_pairs_hook=_reject_duplicate_json_keys,
                            )
                    except (json.JSONDecodeError, ValueError) as error:
                        raise ValueError(
                            f"Checkpoint '{checkpoint_file.name}' for '{name}' "
                            "is invalid JSON."
                        ) from error
                    if (
                        not isinstance(raw_checkpoint, dict)
                        or not isinstance(raw_checkpoint.get("uid"), str)
                        or not isinstance(raw_checkpoint.get("timestamp"), str)
                        or not isinstance(raw_checkpoint.get("snapshot"), dict)
                    ):
                        raise ValueError(
                            f"Checkpoint '{checkpoint_file.name}' for '{name}' "
                            "is invalid."
                        )
                    try:
                        _rewrite_checkpoint_record(
                            raw_checkpoint,
                            moved_names_by_uid={},
                        )
                    except ValueError as error:
                        raise ValueError(
                            f"Checkpoint '{checkpoint_file.name}' for '{name}' "
                            f"is invalid: {error}"
                        ) from error
                    entries[checkpoint_file.name] = raw_checkpoint
            checkpoints[name] = entries

        if not records:
            # Keep the later source-not-found message stable; an empty store is
            # not itself corrupt.
            return records, checkpoints
        return records, checkpoints

    def _assert_rename_destination_available(
        self,
        old_name: str,
        new_name: str,
        *,
        records: dict[str, dict[str, object]],
    ) -> None:
        validate_context_name(old_name)
        validate_portable_context_name(new_name)
        if old_name == new_name:
            raise ValueError(
                f"source and destination Context namespaces are the same: '{old_name}'."
            )
        if old_name.startswith(new_name + "/") or new_name.startswith(old_name + "/"):
            raise ValueError(
                "source and destination Context namespaces overlap: "
                f"'{old_name}' → '{new_name}'."
            )

        source_dir = self._context_dir(old_name)
        destination_dir = self._context_dir(new_name)
        if destination_dir.exists() or destination_dir.is_symlink():
            raise FileExistsError(
                f"destination Context namespace '{new_name}' is already occupied."
            )
        try:
            if source_dir.resolve() == destination_dir.resolve(strict=False):
                raise ValueError(
                    "source and destination Context namespaces resolve to the "
                    "same filesystem location; case-only or normalization-only "
                    "renames are not supported."
                )
        except OSError as error:
            raise ValueError(
                "Context namespace paths cannot be resolved safely."
            ) from error

        mapped_names = {
            mapped
            for name in records
            if (mapped := _mapped_context_name(name, old_name, new_name)) is not None
        }
        occupied = mapped_names & (
            set(records)
            - {
                name
                for name in records
                if _mapped_context_name(name, old_name, new_name) is not None
            }
        )
        if occupied:
            raise FileExistsError(
                f"destination Context namespace '{new_name}' is already occupied."
            )

    @staticmethod
    def _context_graph_digest_for_rename(
        records: dict[str, dict[str, object]],
        checkpoints: dict[str, dict[str, dict[str, object]]],
        state: dict[str, object],
        *,
        ground_records: dict[str, dict[str, object]],
        translation_records: dict[str, dict[str, object]],
        meld_records: dict[str, dict[str, object]],
    ) -> str:
        return _canonical_json_digest(
            {
                "contexts": [
                    {
                        "name": name,
                        "record": records[name],
                        "checkpoints": [
                            {"file": filename, "record": record}
                            for filename, record in sorted(
                                checkpoints.get(name, {}).items()
                            )
                        ],
                    }
                    for name in sorted(records)
                ],
                "state": state,
                "grounds": [
                    {"file": name, "record": record}
                    for name, record in sorted(ground_records.items())
                ],
                "translations": [
                    {"file": name, "record": record}
                    for name, record in sorted(translation_records.items())
                ],
                "melds": [
                    {"file": name, "record": record}
                    for name, record in sorted(meld_records.items())
                ],
            }
        )

    def _ground_contract_names_for_rename(self) -> tuple[str, ...]:
        """Return every named Ground whose file must join rename freshness."""
        if not self.ground_sessions_dir.exists():
            if self.ground_sessions_dir.is_symlink():
                raise ValueError("Grounding session storage is invalid.")
            return ()
        if (
            not self.ground_sessions_dir.is_dir()
            or self.ground_sessions_dir.is_symlink()
        ):
            raise ValueError("Grounding session storage is invalid.")
        names: list[str] = []
        for path in sorted(self.ground_sessions_dir.iterdir()):
            if path.name == ".locks" and path.is_dir() and not path.is_symlink():
                continue
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Grounding session storage is invalid.")
            names.append(path.stem)
        return tuple(names)

    def _read_ground_records_for_rename(
        self,
        contract_names: Iterable[str],
    ) -> dict[str, dict[str, object]]:
        from memcommit.ground import GroundError, GroundSession

        records: dict[str, dict[str, object]] = {}
        for contract_name in contract_names:
            path = self._ground_session_path(contract_name)
            try:
                with open(path, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                session = GroundSession.from_dict(raw)
            except (
                json.JSONDecodeError,
                GroundError,
                OSError,
                ValueError,
            ) as error:
                raise ValueError(
                    f"Saved Ground '{contract_name}' is invalid."
                ) from error
            if session.contract_name != contract_name:
                raise ValueError(
                    f"Saved Ground '{contract_name}' does not match its file."
                )
            records[path.name] = raw
        return records

    @staticmethod
    def _read_translation_records_for_rename() -> dict[str, dict[str, object]]:
        from memcommit.translation_view import (
            TranslationCatalog,
            TranslationView,
            TranslationViewError,
        )
        from memcommit.translation_view_store import (
            translation_catalog_path,
            translation_view_path,
            translation_views_dir,
        )

        root = translation_views_dir()
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Translation view storage is invalid.")
            return {}
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Translation view storage is invalid.")
        records: dict[str, dict[str, object]] = {}
        for path in sorted(root.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Translation view storage is invalid.")
            try:
                with open(path, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                if not isinstance(raw, dict):
                    raise ValueError("Translation artifact must be an object.")
                if "revision" in raw:
                    artifact = TranslationCatalog.from_dict(raw)
                    expected_path = translation_catalog_path(
                        artifact.context_uid,
                        artifact.target_language,
                    )
                else:
                    artifact = TranslationView.from_dict(raw)
                    expected_path = translation_view_path(
                        artifact.context_uid,
                        artifact.target_language,
                        artifact.selected_memory_uid,
                    )
                if expected_path != path:
                    raise ValueError(
                        "Translation artifact does not match its storage key."
                    )
            except (
                json.JSONDecodeError,
                TranslationViewError,
                ValueError,
            ) as error:
                raise ValueError(
                    f"Saved translation artifact '{path.name}' is invalid."
                ) from error
            records[path.name] = raw
        return records

    def _read_meld_records_for_rename(self) -> dict[str, dict[str, object]]:
        """Load every target-keyed Meld artifact into rename freshness."""

        from memcommit.meld import MeldError, MeldSession

        root = self.meld_sessions_dir
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Meld session storage is invalid.")
            return {}
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Meld session storage is invalid.")
        records: dict[str, dict[str, object]] = {}
        for path in sorted(root.iterdir()):
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Meld session storage is invalid.")
            try:
                with open(path, encoding="utf-8") as file:
                    raw = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                session = MeldSession.from_dict(raw)
            except (json.JSONDecodeError, MeldError, OSError, ValueError) as error:
                raise ValueError(
                    f"Saved Meld session '{path.name}' is invalid."
                ) from error
            if path.stem != session.target.context_uid:
                raise ValueError(
                    f"Saved Meld session '{path.name}' does not match its file."
                )
            records[path.name] = raw
        return records

    def _prepare_context_rename_locked(
        self,
        old_name: str,
        new_name: str,
        *,
        ground_contract_names: Iterable[str],
    ) -> _PreparedContextRename:
        """Build validated pre/post images while graph and item locks are held."""
        records, checkpoints = self._read_context_graph_for_rename()
        if old_name not in records:
            raise FileNotFoundError(f"Context '{old_name}' not found.")
        self._assert_rename_destination_available(
            old_name,
            new_name,
            records=records,
        )

        bindings = tuple(
            ContextRenameBinding(
                old_name=name,
                new_name=_mapped_context_name(name, old_name, new_name) or name,
                context_uid=str(records[name]["uid"]),
            )
            for name in sorted(records)
            if _mapped_context_name(name, old_name, new_name) is not None
        )
        moved_names_by_uid = {
            binding.context_uid: (binding.old_name, binding.new_name)
            for binding in bindings
        }

        post_records: dict[str, dict[str, object]] = {}
        changed_owner_names: list[str] = []
        live_reference_count = 0
        for owner_name, record in records.items():
            pre_probe, _, pre_collisions = _rewrite_context_pointers(
                record,
                moved_names_by_uid={},
                rewrite_owner_name=False,
                require_current_pointer_names=True,
            )
            if pre_probe != record:
                raise ValueError(
                    f"Context '{owner_name}' changed during rename validation."
                )
            post, count, post_collisions = _rewrite_context_pointers(
                record,
                moved_names_by_uid=moved_names_by_uid,
                rewrite_owner_name=True,
                require_current_pointer_names=True,
            )
            introduced = set(post_collisions) - set(pre_collisions)
            if introduced:
                raise ValueError(
                    f"Renaming would give Context '{owner_name}' both an "
                    "ordinary and query-only child named "
                    + ", ".join(repr(name) for name in sorted(introduced))
                    + "."
                )
            post_name = (
                _mapped_context_name(owner_name, old_name, new_name) or owner_name
            )
            _validate_context_header(post, post_name)
            try:
                Context.from_dict(post)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Renamed Context '{post_name}' would be invalid."
                ) from error
            post_records[owner_name] = post
            live_reference_count += count
            if post != record:
                changed_owner_names.append(owner_name)

        post_checkpoints: dict[str, dict[str, dict[str, object]]] = {}
        checkpoint_reference_count = 0
        for owner_name, entries in checkpoints.items():
            next_entries: dict[str, dict[str, object]] = {}
            for filename, entry in entries.items():
                _, _, pre_collisions = _rewrite_checkpoint_record(
                    entry,
                    moved_names_by_uid={},
                )
                post, count, post_collisions = _rewrite_checkpoint_record(
                    entry,
                    moved_names_by_uid=moved_names_by_uid,
                )
                introduced = set(post_collisions) - set(pre_collisions)
                if introduced:
                    raise ValueError(
                        f"Renaming would make checkpoint '{filename}' in "
                        f"'{owner_name}' ambiguous with query-only child "
                        + ", ".join(repr(name) for name in sorted(introduced))
                        + "."
                    )
                next_entries[filename] = post
                checkpoint_reference_count += count
            post_checkpoints[owner_name] = next_entries

        if self.state_file.is_symlink() or not self.state_file.is_file():
            raise ValueError("Context state storage is invalid.")
        try:
            with open(self.state_file, encoding="utf-8") as file:
                raw_state = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("Context state storage is invalid JSON.") from error
        if not isinstance(raw_state, dict):
            raise ValueError("Context state storage must contain an object.")
        current_before = raw_state.get("current")
        if current_before is not None and not isinstance(current_before, str):
            raise ValueError("Current Context state is invalid.")
        current_after = current_before
        if isinstance(current_before, str):
            mapped_current = _mapped_context_name(
                current_before,
                old_name,
                new_name,
            )
            if mapped_current is not None:
                if current_before not in records:
                    raise ValueError(
                        "Current Context points inside the source namespace but "
                        "does not identify a stored Context."
                    )
                current_after = mapped_current
        post_state = copy.deepcopy(raw_state)
        post_state["current"] = current_after

        pre_digest_by_uid = {
            str(record["uid"]): context_record_digest(record)
            for record in records.values()
        }
        post_record_by_uid = {
            str(record["uid"]): record for record in post_records.values()
        }
        post_digest_by_uid = {
            uid: context_record_digest(record)
            for uid, record in post_record_by_uid.items()
        }
        post_name_by_uid = {
            str(record["uid"]): str(record["name"]) for record in post_records.values()
        }
        changed_uids = {str(records[name]["uid"]) for name in changed_owner_names}
        # Rename rewrites both moved Context headers and inbound Context/Memory
        # reference owners. Validate every changed owner against one frozen
        # policy snapshot while all graph Context locks are still held.
        protection = self.write_protection_state()
        for owner_name in changed_owner_names:
            self._assert_context_record_change_allowed(
                records[owner_name],
                post_records[owner_name],
                state=protection,
            )

        ground_records = self._read_ground_records_for_rename(ground_contract_names)
        post_ground_records: dict[str, dict[str, object]] = {}
        ground_frame_count = 0
        from memcommit.ground import GroundError, GroundSession

        for filename, record in ground_records.items():
            post = copy.deepcopy(record)
            frames = post.get("frames")
            if isinstance(frames, list):
                for frame in frames:
                    if not isinstance(frame, dict):
                        raise ValueError(
                            f"Saved Ground '{filename}' has an invalid frame."
                        )
                    context_uid = frame.get("context_uid")
                    if context_uid not in changed_uids:
                        continue
                    before_frame = copy.deepcopy(frame)
                    frame["context_name"] = post_name_by_uid[context_uid]
                    # Preserve prior staleness. Only a frame that matched the
                    # exact pre-rename record may follow the metadata-only
                    # digest change to the post-rename record.
                    if frame.get("context_digest") == pre_digest_by_uid[context_uid]:
                        frame["context_digest"] = post_digest_by_uid[context_uid]
                    if frame != before_frame:
                        ground_frame_count += 1
            try:
                GroundSession.from_dict(post)
            except GroundError as error:
                raise ValueError(
                    f"Saved Ground '{filename}' cannot follow this rename."
                ) from error
            post_ground_records[filename] = post

        translation_records = self._read_translation_records_for_rename()
        post_translation_records: dict[str, dict[str, object]] = {}
        translation_artifact_count = 0
        from memcommit.translation_view import (
            TranslationCatalog,
            TranslationView,
            TranslationViewError,
        )

        for filename, record in translation_records.items():
            post = copy.deepcopy(record)
            context_uid = post.get("context_uid")
            if isinstance(context_uid, str) and context_uid in changed_uids:
                before_artifact = copy.deepcopy(post)
                post["context_name"] = post_name_by_uid[context_uid]
                if (
                    "context_digest" in post
                    and post.get("context_digest") == pre_digest_by_uid[context_uid]
                ):
                    post["context_digest"] = post_digest_by_uid[context_uid]
                if post != before_artifact:
                    translation_artifact_count += 1
            try:
                if "revision" in post:
                    TranslationCatalog.from_dict(post)
                else:
                    TranslationView.from_dict(post)
            except TranslationViewError as error:
                raise ValueError(
                    f"Saved translation artifact '{filename}' cannot follow "
                    "this rename."
                ) from error
            post_translation_records[filename] = post

        meld_records = self._read_meld_records_for_rename()
        post_meld_records: dict[str, dict[str, object]] = {}
        meld_session_count = 0
        from memcommit.comparison import comparison_canonical_digest
        from memcommit.meld import MeldError, MeldSession

        def rewrite_meld_binding(binding: object) -> bool:
            if not isinstance(binding, dict):
                raise ValueError("Saved Meld session has an invalid Context binding.")
            context_uid = binding.get("context_uid")
            if not isinstance(context_uid, str) or context_uid not in changed_uids:
                return False
            binding["context_name"] = post_name_by_uid[context_uid]
            if binding.get("context_digest") == pre_digest_by_uid[context_uid]:
                binding["context_digest"] = post_digest_by_uid[context_uid]
            return True

        for filename, record in meld_records.items():
            post = copy.deepcopy(record)
            changed = rewrite_meld_binding(post.get("target"))
            frames = post.get("frames")
            if not isinstance(frames, list):
                raise ValueError(f"Saved Meld session '{filename}' has invalid frames.")
            for frame in frames:
                changed = rewrite_meld_binding(frame) or changed
            seed = post.get("comparison_seed")
            if isinstance(seed, dict):
                analysis = seed.get("analysis")
                analysis_frames = (
                    analysis.get("frames") if isinstance(analysis, dict) else None
                )
                if not isinstance(analysis_frames, list):
                    raise ValueError(
                        f"Saved Meld session '{filename}' has an invalid Compare seed."
                    )
                seed_changed = False
                for frame in analysis_frames:
                    seed_changed = rewrite_meld_binding(frame) or seed_changed
                if seed_changed:
                    seed["analysis_digest"] = comparison_canonical_digest(analysis)
                    changed = True
            if changed and post.get("state") == "APPLIED":
                raise ValueError(
                    "An applied Meld target or source cannot be renamed until "
                    "its application is undone."
                )
            try:
                MeldSession.from_dict(post)
            except MeldError as error:
                raise ValueError(
                    f"Saved Meld session '{filename}' cannot follow this rename."
                ) from error
            if changed:
                meld_session_count += 1
            post_meld_records[filename] = post

        graph_digest = self._context_graph_digest_for_rename(
            records,
            checkpoints,
            raw_state,
            ground_records=ground_records,
            translation_records=translation_records,
            meld_records=meld_records,
        )
        plan = ContextRenamePlan(
            old_name=old_name,
            new_name=new_name,
            bindings=bindings,
            changed_owner_names=tuple(sorted(changed_owner_names)),
            reference_count=live_reference_count,
            checkpoint_reference_count=checkpoint_reference_count,
            ground_frame_count=ground_frame_count,
            translation_artifact_count=translation_artifact_count,
            meld_session_count=meld_session_count,
            current_before=current_before,
            current_after=current_after,
            graph_digest=graph_digest,
        )
        return _PreparedContextRename(
            plan=plan,
            records=records,
            post_records=post_records,
            checkpoints=checkpoints,
            post_checkpoints=post_checkpoints,
            state=raw_state,
            post_state=post_state,
            ground_records=ground_records,
            post_ground_records=post_ground_records,
            translation_records=translation_records,
            post_translation_records=post_translation_records,
            meld_records=meld_records,
            post_meld_records=post_meld_records,
        )

    @staticmethod
    def _rename_lock_names(
        records: dict[str, dict[str, object]],
        old_name: str,
        new_name: str,
    ) -> tuple[str, ...]:
        names = set(records)
        names.update(
            mapped
            for name in records
            if (mapped := _mapped_context_name(name, old_name, new_name)) is not None
        )
        # Lock the exact requested destination even when the source scan is
        # corrupt or empty so a cooperative creator cannot claim it between
        # validation and the stable error/result.
        names.add(new_name)
        return tuple(sorted(names))

    def plan_context_rename(
        self,
        old_name: str,
        new_name: str,
    ) -> ContextRenamePlan:
        """Return one exact, read-only namespace migration preview."""
        # The Source may be a legacy name that exists precisely so this
        # migration can retire it. Only the new canonical locator must satisfy
        # the portable creation contract.
        validate_context_name(old_name)
        validate_portable_context_name(new_name)
        with self._context_graph_lock(exclusive=True):
            records, _ = self._read_context_graph_for_rename()
            lock_names = self._rename_lock_names(records, old_name, new_name)
            ground_names = self._ground_contract_names_for_rename()
            with self._context_write_locks(lock_names):
                with self._state_write_lock():
                    with ExitStack() as grounds:
                        for contract_name in ground_names:
                            grounds.enter_context(
                                self._ground_session_write_lock(contract_name)
                            )
                        return self._prepare_context_rename_locked(
                            old_name,
                            new_name,
                            ground_contract_names=ground_names,
                        ).plan

    def _commit_context_rename_locked(
        self,
        prepared: _PreparedContextRename,
    ) -> ContextRenameResult:
        """Publish prepared images with exception rollback under all locks.

        The current prototype guarantees exception atomicity across the graph.
        A durable crash-recovery journal remains a documented boundary, just
        as for the existing multi-Context update transaction.
        """
        plan = prepared.plan
        name_mapping = {binding.old_name: binding.new_name for binding in plan.bindings}
        source_dir = self._context_dir(plan.old_name)
        destination_dir = self._context_dir(plan.new_name)
        destination_parent = destination_dir.parent

        def live_name(owner_name: str) -> str:
            return name_mapping.get(owner_name, owner_name)

        restore_files: dict[Path, bytes] = {}
        changed_context_paths: list[tuple[Path, dict[str, object]]] = []
        changed_checkpoint_paths: list[tuple[Path, dict[str, object]]] = []
        changed_ground_paths: list[tuple[Path, dict[str, object]]] = []
        changed_translation_paths: list[tuple[Path, dict[str, object]]] = []
        changed_meld_paths: list[tuple[Path, dict[str, object]]] = []

        for owner_name in plan.changed_owner_names:
            before_path = self._context_file(owner_name)
            after_path = self._context_file(live_name(owner_name))
            restore_files[after_path] = before_path.read_bytes()
            changed_context_paths.append(
                (after_path, prepared.post_records[owner_name])
            )
        for owner_name, entries in prepared.checkpoints.items():
            for filename, before in entries.items():
                after = prepared.post_checkpoints[owner_name][filename]
                if after == before:
                    continue
                before_path = self._checkpoints_dir(owner_name) / filename
                after_path = self._checkpoints_dir(live_name(owner_name)) / filename
                restore_files[after_path] = before_path.read_bytes()
                changed_checkpoint_paths.append((after_path, after))
        for filename, before in prepared.ground_records.items():
            after = prepared.post_ground_records[filename]
            if after == before:
                continue
            path = self.ground_sessions_dir / filename
            restore_files[path] = path.read_bytes()
            changed_ground_paths.append((path, after))
        if prepared.translation_records:
            from memcommit.translation_view_store import translation_views_dir

            translation_root = translation_views_dir()
            for filename, before in prepared.translation_records.items():
                after = prepared.post_translation_records[filename]
                if after == before:
                    continue
                path = translation_root / filename
                restore_files[path] = path.read_bytes()
                changed_translation_paths.append((path, after))
        for filename, before in prepared.meld_records.items():
            after = prepared.post_meld_records[filename]
            if after == before:
                continue
            path = self.meld_sessions_dir / filename
            restore_files[path] = path.read_bytes()
            changed_meld_paths.append((path, after))
        if prepared.post_state != prepared.state:
            restore_files[self.state_file] = self.state_file.read_bytes()

        timestamp = datetime.now()
        checkpoint_paths: list[Path] = []
        checkpoint_writes: list[tuple[Path, dict[str, object]]] = []
        for owner_name in plan.changed_owner_names:
            owner_after = live_name(owner_name)
            checkpoint_uid = str(uuid.uuid4())
            description = (
                f"Renamed Context namespace '{plan.old_name}' to "
                f"'{plan.new_name}'; updated '{owner_name}'"
                + (
                    f" to '{owner_after}'."
                    if owner_name != owner_after
                    else " references."
                )
            )
            checkpoint = {
                "uid": checkpoint_uid,
                "message": description,
                "timestamp": timestamp.isoformat(),
                "snapshot": canonical_context_record(prepared.post_records[owner_name]),
                "command": "rename",
                "args": {
                    "old_name": plan.old_name,
                    "new_name": plan.new_name,
                    "context_uid": prepared.records[owner_name]["uid"],
                    "owner_before": owner_name,
                    "owner_after": owner_after,
                },
                "description": description,
                "auto": True,
            }
            checkpoint_dir = self._checkpoints_dir(owner_after)
            filename = (
                f"{timestamp.strftime('%Y%m%dT%H%M%S')}-rename-"
                f"{checkpoint_uid[:8]}.json"
            )
            path = checkpoint_dir / filename
            checkpoint_paths.append(path)
            checkpoint_writes.append((path, checkpoint))

        source_moved = False
        try:
            destination_parent.mkdir(parents=True, exist_ok=True)
            # Recheck immediately before publication. Cooperative Context
            # creators are excluded by the graph lock; this explicit check
            # also prevents Path.rename from replacing a pre-existing empty
            # destination directory on platforms that permit that behavior.
            if destination_dir.exists() or destination_dir.is_symlink():
                raise FileExistsError(
                    f"destination Context namespace '{plan.new_name}' is "
                    "already occupied."
                )
            source_dir.rename(destination_dir)
            source_moved = True

            for path, record in changed_context_paths:
                _write_json_atomic(path, record)
            for path, record in changed_checkpoint_paths:
                _write_json_atomic(path, record)
            for path, record in changed_ground_paths:
                _write_json_atomic(path, record)
            for path, record in changed_translation_paths:
                _write_json_atomic(path, record)
            for path, record in changed_meld_paths:
                _write_json_atomic(path, record)
            for path, record in checkpoint_writes:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() or path.is_symlink():
                    raise FileExistsError(
                        "Rename checkpoint destination unexpectedly exists."
                    )
                _write_json_atomic(path, record)
            if prepared.post_state != prepared.state:
                _write_json_atomic(self.state_file, prepared.post_state)

            for binding in plan.bindings:
                if self.context_exists(binding.old_name):
                    raise RuntimeError(
                        f"Old Context '{binding.old_name}' remains after rename."
                    )
                renamed = self.load_direct(binding.new_name)
                if renamed.uid != binding.context_uid:
                    raise RuntimeError(
                        f"Renamed Context '{binding.new_name}' changed identity."
                    )
            for owner_name in plan.changed_owner_names:
                expected = canonical_context_record(prepared.post_records[owner_name])
                actual = canonical_context_record(
                    self.load_direct(live_name(owner_name))
                )
                if actual != expected:
                    raise RuntimeError(
                        f"Renamed Context '{live_name(owner_name)}' failed "
                        "post-publication verification."
                    )
            if self._read_state() != prepared.post_state:
                raise RuntimeError(
                    "Current Context state failed post-rename verification."
                )
            for filename, expected in prepared.post_meld_records.items():
                path = self.meld_sessions_dir / filename
                with open(path, encoding="utf-8") as file:
                    actual = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
                if actual != expected:
                    raise RuntimeError(
                        f"Meld session '{filename}' failed post-rename verification."
                    )
        except Exception as error:
            rollback_error: Exception | None = None
            for path in checkpoint_paths:
                try:
                    if path.exists() and not path.is_symlink():
                        path.unlink()
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            for path, original in restore_files.items():
                try:
                    if path.exists() and not path.is_symlink():
                        _write_bytes_atomic(path, original)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            if source_moved:
                try:
                    if source_dir.exists() or source_dir.is_symlink():
                        raise RuntimeError(
                            "Source namespace reappeared during rollback."
                        )
                    destination_dir.rename(source_dir)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            self._prune_empty_namespace_dirs(destination_parent)
            if rollback_error is not None:
                raise RuntimeError(
                    "Context rename failed and could not be fully rolled back."
                ) from rollback_error
            raise error

        self._prune_empty_namespace_dirs(source_dir.parent)
        return ContextRenameResult(
            renamed_context_count=len(plan.bindings),
            changed_owner_count=len(plan.changed_owner_names),
            reference_count=plan.reference_count,
            checkpoint_reference_count=plan.checkpoint_reference_count,
            ground_frame_count=plan.ground_frame_count,
            translation_artifact_count=plan.translation_artifact_count,
            meld_session_count=plan.meld_session_count,
            current_context=plan.current_after,
        )

    def rename_contexts(
        self,
        plan: ContextRenamePlan,
    ) -> ContextRenameResult:
        """Apply one namespace rename outside concurrent command restores."""
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            return self._rename_contexts_command_locked(plan)

    def _rename_contexts_command_locked(
        self,
        plan: ContextRenamePlan,
    ) -> ContextRenameResult:
        """Apply exactly one previously reviewed Context namespace plan."""
        if not isinstance(plan, ContextRenamePlan):
            raise TypeError("Expected a ContextRenamePlan.")
        validate_context_name(plan.old_name)
        validate_portable_context_name(plan.new_name)
        with self._context_graph_lock(exclusive=True):
            records, _ = self._read_context_graph_for_rename()
            lock_names = self._rename_lock_names(
                records,
                plan.old_name,
                plan.new_name,
            )
            ground_names = self._ground_contract_names_for_rename()
            with self._context_write_locks(lock_names):
                with self._state_write_lock():
                    with ExitStack() as grounds:
                        for contract_name in ground_names:
                            grounds.enter_context(
                                self._ground_session_write_lock(contract_name)
                            )
                        prepared = self._prepare_context_rename_locked(
                            plan.old_name,
                            plan.new_name,
                            ground_contract_names=ground_names,
                        )
                        if prepared.plan != plan:
                            raise ConcurrentContextUpdateError(
                                "The Context graph changed after the rename was "
                                "reviewed; nothing was renamed."
                            )
                        return self._commit_context_rename_locked(prepared)

    def save(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
        *,
        expected_context_digest: str | None = None,
    ) -> Checkpoint | None:
        """Persist one Context inside the global command-order boundary."""
        with self._command_write_lock():
            return self._save_command_locked(
                ctx,
                auto_checkpoint,
                expected_context_digest=expected_context_digest,
            )

    def _save_command_locked(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
        *,
        expected_context_digest: str | None = None,
    ) -> Checkpoint | None:
        """Persist a Context, optionally only if its disk record is unchanged."""
        if expected_context_digest is None:
            expected_context_digest = getattr(ctx, "_store_digest", None)
        # A brand-new identity can add an inbound reference under a name that
        # did not exist during rename's graph scan. Coordinate that creation
        # with the graph lock; stale loaded writers already carry a digest and
        # are rejected by ordinary per-Context CAS after a rename.
        if expected_context_digest is None:
            with self._context_graph_lock(exclusive=False):
                with self._context_write_lock(ctx.name):
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=expected_context_digest,
                    )
        else:
            with self._context_write_lock(ctx.name):
                checkpoint = self._save_locked(
                    ctx,
                    auto_checkpoint,
                    expected_context_digest=expected_context_digest,
                )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def save_context_command_batch(
        self,
        entries: Iterable[tuple[Context, AutoCheckpoint, str]],
        *,
        source_bindings: Iterable[tuple[str, str, str]] = (),
        expected_context_catalog: Iterable[str] | None = None,
    ) -> tuple[Checkpoint, ...]:
        """Persist one existing multi-Context command with exception rollback.

        Each entry carries its own already-reviewed Context digest.  The
        complete name set remains locked from the first revalidation through
        the final write, so application adapters can publish a command unit
        without inventing a whole-graph digest.  This is exception-atomic;
        like the other multi-Context prototype paths, a durable crash journal
        is intentionally deferred.
        """

        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context command entry is required.")
        if any(
            not isinstance(context, Context)
            or not isinstance(checkpoint, AutoCheckpoint)
            or not isinstance(expected_digest, str)
            for context, checkpoint, expected_digest in records
        ):
            raise TypeError("Invalid Context command batch entry.")
        names = tuple(context.name for context, _, _ in records)
        if len(names) != len(set(names)):
            raise ValueError("Context command batch contains duplicate names.")
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _uid, _digest in bindings)
        if len(source_names) != len(set(source_names)):
            raise ValueError("Context command batch repeats a source binding.")
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(uid, str)
            or not uid
            or not isinstance(digest, str)
            or not digest
            for name, uid, digest in bindings
        ):
            raise TypeError("Invalid Context command source binding.")
        for name in names:
            validate_context_name(name)
        for name in source_names:
            validate_context_name(name)
        expected_catalog = (
            None
            if expected_context_catalog is None
            else tuple(expected_context_catalog)
        )
        if expected_catalog is not None and (
            len(expected_catalog) != len(set(expected_catalog))
            or any(not isinstance(name, str) or not name for name in expected_catalog)
        ):
            raise ValueError("Expected Context command catalog is invalid.")

        with self._command_write_lock():
            # A complete-scope operation may bind catalog membership as well
            # as Context bytes. Use the exclusive graph lock only for those
            # callers; ordinary batches retain the narrower shared lock.
            with self._context_graph_lock(exclusive=expected_catalog is not None):
                if (
                    expected_catalog is not None
                    and tuple(self.list_context_names()) != expected_catalog
                ):
                    raise ConcurrentContextUpdateError(
                        "The Context namespace changed after the command was reviewed."
                    )
                # Read-only members of a complete operation frame stay locked
                # through the writes as well. Otherwise a plan claiming all
                # matches could silently miss a newly changed sibling.
                with self._context_write_locks((*names, *source_names)):
                    if bindings:
                        self._assert_source_bindings_locked(
                            bindings,
                            result_label="Context command batch",
                        )
                    original_records: dict[str, dict[str, object]] = {}
                    for context, _, expected_digest in records:
                        try:
                            current = self.load_direct(context.name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' no longer exists."
                            ) from error
                        if (
                            current.uid != context.uid
                            or context_record_digest(current) != expected_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' changed before the "
                                "command could be saved."
                            )
                        # Validate the entire write set before the first
                        # publication. Rollback still protects unexpected I/O
                        # failures, while a locked later Context must fail the
                        # complete command without a provisional earlier save.
                        self._assert_context_record_change_allowed(
                            current,
                            context,
                        )
                        original_records[context.name] = current.to_dict()

                    created: list[tuple[str, Checkpoint]] = []
                    written: list[str] = []
                    try:
                        for context, auto_checkpoint, expected_digest in records:
                            checkpoint = self._save_locked(
                                context,
                                auto_checkpoint,
                                expected_context_digest=expected_digest,
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Context command batch created no checkpoint."
                                )
                            written.append(context.name)
                            created.append((context.name, checkpoint))
                    except Exception:
                        rollback_error: Exception | None = None
                        for name in written:
                            try:
                                _write_json_atomic(
                                    self._context_file(name),
                                    original_records[name],
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in created:
                            try:
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Context command batch failed and could not be "
                                "fully rolled back."
                            ) from rollback_error
                        raise

        for context, _, _ in records:
            context._store_digest = context_record_digest(context)
        return tuple(checkpoint for _, checkpoint in created)

    def save_meld_target(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpoint,
        *,
        expected_context_digest: str,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Save one Meld result as one globally ordered command."""
        with self._command_write_lock():
            return self._save_meld_target_command_locked(
                ctx,
                auto_checkpoint,
                expected_context_digest=expected_context_digest,
                source_bindings=source_bindings,
            )

    def _save_meld_target_command_locked(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpoint,
        *,
        expected_context_digest: str,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Save one meld target while its exact source snapshots stay locked.

        Ordinary Context CAS protects only the target. A meld result also
        depends on read-only source snapshots, so all participating Context
        locks must remain held from the final source recheck through the
        target checkpoint and write. In a directional meld the BASELINE frame
        is the target itself and is protected by target CAS rather than being
        repeated in ``source_bindings``.
        """
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _, _ in bindings)
        if len(source_names) != len(set(source_names)) or ctx.name in source_names:
            raise ValueError("Invalid meld source lock set.")
        with self._context_graph_lock(exclusive=False):
            with self._context_write_locks((*source_names, ctx.name)):
                self._assert_source_bindings_locked(
                    bindings,
                    result_label="meld target",
                )
                checkpoint = self._save_locked(
                    ctx,
                    auto_checkpoint,
                    expected_context_digest=expected_context_digest,
                )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def save_context_with_sources(
        self,
        ctx: Context,
        auto_checkpoint: AutoCheckpoint,
        *,
        expected_context_digest: str,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Save a target only while every source receipt is still exact.

        A target digest cannot detect a rename or replacement of a separate
        source that supplied a persisted locator.  Keep every source and the
        target locked from final validation through the target write so a
        successful command cannot reintroduce stale source names.
        """
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _, _ in bindings)
        if not bindings or len(source_names) != len(set(source_names)):
            raise ValueError("Invalid Context source lock set.")
        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks((*source_names, ctx.name)):
                    self._assert_source_bindings_locked(bindings)
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=expected_context_digest,
                    )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def _assert_source_bindings_locked(
        self,
        bindings: Iterable[tuple[str, str, str]],
        *,
        result_label: str = "result",
    ) -> None:
        """Validate exact source identities while their write locks are held."""
        if not result_label:
            raise ValueError("Context source result label cannot be empty.")
        for name, expected_uid, expected_digest in bindings:
            try:
                source = self.load_direct(name)
            except FileNotFoundError as error:
                raise ConcurrentContextUpdateError(
                    f"The source Context no longer exists: '{name}'."
                ) from error
            if (
                source.uid != expected_uid
                or context_record_digest(source) != expected_digest
            ):
                raise ConcurrentContextUpdateError(
                    f"The source Context changed before the {result_label} "
                    f"could be saved: '{name}'."
                )

    def create_context(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
    ) -> Checkpoint | None:
        """Create one new Context without overwriting a concurrent owner."""
        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_lock(ctx.name):
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=None,
                        require_new=True,
                    )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    @contextmanager
    def locked_context_snapshot(
        self,
        name: str,
        *,
        expected_uid: str,
        expected_digest: str,
    ) -> Iterator[Context]:
        """Hold one exact read snapshot across an authorized external publish.

        Cross-store delivery cannot rely on a UI-time freshness check. Keeping
        the source write lock held until the receiver commit completes makes a
        successful receipt describe the exact bytes that were transmitted.
        """

        with self._command_write_lock():
            with self._context_write_lock(name):
                current = self.load_direct(name)
                if (
                    current.uid != expected_uid
                    or context_record_digest(current) != expected_digest
                ):
                    raise ConcurrentContextUpdateError(
                        f"Context '{name}' changed before it could be published."
                    )
                yield current

    @contextmanager
    def locked_context_snapshots(
        self,
        bindings: Iterable[tuple[str, str, str]],
        *,
        source_root: str,
        include_descendants: bool,
    ) -> Iterator[tuple[Context, ...]]:
        """Hold one exact local Context scope across an external publish.

        Recursive disclosure binds namespace membership as well as record
        bytes.  The exclusive graph lock prevents a new lexical descendant
        from entering the reviewed bundle while its receiver copy is being
        created; direct disclosure retains the narrower shared graph lock.
        """

        records = tuple(bindings)
        names = tuple(name for name, _uid, _digest in records)
        if (
            not records
            or len(names) != len(set(names))
            or any(
                not isinstance(name, str)
                or not name
                or not isinstance(uid, str)
                or not uid
                or not isinstance(digest, str)
                or not digest
                for name, uid, digest in records
            )
            or type(include_descendants) is not bool
        ):
            raise ValueError("Invalid Context publication snapshot set.")

        with self._command_write_lock():
            with self._context_graph_lock(exclusive=include_descendants):
                if include_descendants:
                    from memcommit.context_targeting.model import ContextScope
                    from memcommit.context_targeting.resolution import (
                        expand_lexical_context_names,
                    )

                    live_names = expand_lexical_context_names(
                        ContextScope.create(
                            (source_root,),
                            include_descendants=True,
                        ),
                        self.list_context_names(),
                    )
                    if live_names != names:
                        raise ConcurrentContextUpdateError(
                            "The Source Context subtree changed before it could "
                            "be published."
                        )
                elif names != (source_root,):
                    raise ValueError(
                        "A direct Context publication must bind exactly its root."
                    )

                with self._context_write_locks(names):
                    frozen: list[Context] = []
                    for name, expected_uid, expected_digest in records:
                        try:
                            current = self.load_direct(name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Context '{name}' no longer exists."
                            ) from error
                        if (
                            current.uid != expected_uid
                            or context_record_digest(current) != expected_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Context '{name}' changed before it could be "
                                "published."
                            )
                        frozen.append(current)
                    yield tuple(frozen)


    def create_context_with_sources(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint] = None,
        *,
        source_bindings: Iterable[tuple[str, str, str]],
    ) -> Checkpoint | None:
        """Publish a new Context from exact source snapshots.

        The source recheck and require-new write share one lock set.  This is
        the creation counterpart of ``save_context_with_sources`` and prevents
        both stale locators and a concurrent owner from reaching the new path.
        """
        bindings = tuple(source_bindings)
        source_names = tuple(name for name, _, _ in bindings)
        if (
            not bindings
            or len(source_names) != len(set(source_names))
            or ctx.name in source_names
        ):
            raise ValueError("Invalid Context creation source lock set.")
        with self._command_write_lock():
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks((*source_names, ctx.name)):
                    self._assert_source_bindings_locked(bindings)
                    checkpoint = self._save_locked(
                        ctx,
                        auto_checkpoint,
                        expected_context_digest=None,
                        require_new=True,
                    )
        ctx._store_digest = context_record_digest(ctx)
        return checkpoint

    def create_branch_context(
        self,
        ctx: Context,
        *,
        source_name: str,
        expected_source_uid: str,
        expected_source_digest: str,
        expected_history_digest: str,
        expected_current: str | None,
    ) -> None:
        """Create, inherit history, and select one exact branch atomically."""
        self.create_branch_contexts(
            (
                ContextBranchBinding(
                    source_name=source_name,
                    expected_source_uid=expected_source_uid,
                    expected_source_digest=expected_source_digest,
                    expected_history_digest=expected_history_digest,
                    target=ctx,
                ),
            ),
            source_root=source_name,
            target_root=ctx.name,
            include_descendants=False,
            expected_current=expected_current,
        )

    def create_branch_contexts(
        self,
        bindings: Iterable[ContextBranchBinding],
        *,
        source_root: str,
        target_root: str,
        include_descendants: bool,
        expected_current: str | None,
    ) -> None:
        """Publish one exact or lexical-subtree Branch as a single command.

        The complete Source membership, every record and checkpoint history,
        every require-new destination, and current selection remain frozen
        from final validation through publication and exception rollback.
        """
        records = tuple(bindings)
        if not records:
            raise ValueError("A Branch requires at least one Context binding.")
        if type(include_descendants) is not bool:
            raise ValueError("Branch descendant scope must be a boolean.")
        _context_name_parts(source_root)
        validate_portable_context_name(target_root)
        if source_root == target_root:
            raise ValueError("A Branch must have a new Context root name.")

        source_names = tuple(binding.source_name for binding in records)
        target_names = tuple(binding.target.name for binding in records)
        for target_name in target_names:
            validate_portable_context_name(target_name)
        if (
            len(source_names) != len(set(source_names))
            or len(target_names) != len(set(target_names))
            or set(source_names) & set(target_names)
            or source_root not in source_names
            or target_root not in target_names
        ):
            raise ValueError("Invalid Branch Source or target binding set.")
        if not include_descendants and len(records) != 1:
            raise ValueError("An exact Branch must create exactly one Context.")

        expected_targets = {
            source_name: target_root + source_name[len(source_root) :]
            for source_name in source_names
            if source_name == source_root or source_name.startswith(source_root + "/")
        }
        if len(expected_targets) != len(records) or any(
            binding.target.name != expected_targets.get(binding.source_name)
            for binding in records
        ):
            raise ValueError("Branch targets must preserve Source subtree suffixes.")
        source_uids = {binding.expected_source_uid for binding in records}
        if len({binding.target.uid for binding in records}) != len(records) or any(
            binding.target.uid in source_uids for binding in records
        ):
            raise ValueError("Every Branch Context requires one new identity.")
        targets_by_source_uid = {
            binding.expected_source_uid: (
                binding.target.uid,
                binding.target.name,
            )
            for binding in records
        }
        operation_uid = str(uuid.uuid4())
        command_contexts = [
            {
                "uid": binding.target.uid,
                "name": binding.target.name,
            }
            for binding in records
        ]
        branch_tree = {
            "version": 1,
            "operation_uid": operation_uid,
            "source_root": source_root,
            "target_root": target_root,
            "include_descendants": include_descendants,
            "current_before": expected_current,
            "contexts": [
                {
                    "source_uid": binding.expected_source_uid,
                    "source_name": binding.source_name,
                    "target_uid": binding.target.uid,
                    "target_name": binding.target.name,
                }
                for binding in records
            ],
        }
        branch_description = (
            f"Branched subtree '{source_root}' to '{target_root}'."
            if include_descendants
            else f"Branched '{source_root}' to '{target_root}'."
        )

        source_receipts = tuple(
            (
                binding.source_name,
                binding.expected_source_uid,
                binding.expected_source_digest,
            )
            for binding in records
        )
        lock_names = (*source_names, *target_names)
        with self._command_write_lock():
            # Subtree membership is itself part of the reviewed request. An
            # exclusive graph lock prevents a new lexical descendant from
            # appearing after the final membership recheck.
            with self._context_graph_lock(exclusive=include_descendants):
                with self._context_write_locks(lock_names):
                    if include_descendants:
                        from memcommit.context_targeting.model import ContextScope
                        from memcommit.context_targeting.resolution import (
                            expand_lexical_context_names,
                        )

                        live_source_names = expand_lexical_context_names(
                            ContextScope.create(
                                (source_root,),
                                include_descendants=True,
                            ),
                            self.list_context_names(),
                        )
                        if live_source_names != source_names:
                            raise ConcurrentContextUpdateError(
                                "The Source Context subtree changed before the "
                                "Branch could be created."
                            )
                    self._assert_source_bindings_locked(
                        source_receipts,
                        result_label="branch",
                    )

                    checkpoint_files: dict[
                        str,
                        tuple[tuple[Path, dict[str, object] | None], ...],
                    ] = {}
                    for binding in records:
                        history = self.list_checkpoints(binding.source_name)
                        if (
                            checkpoint_history_digest(history)
                            != binding.expected_history_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Checkpoint history for '{binding.source_name}' "
                                "changed before the branch could be created."
                            )
                        source_checkpoints = self._checkpoints_dir(binding.source_name)
                        files: tuple[Path, ...] = ()
                        if source_checkpoints.exists():
                            if (
                                source_checkpoints.is_symlink()
                                or not source_checkpoints.is_dir()
                            ):
                                raise ValueError(
                                    f"Checkpoint history for "
                                    f"'{binding.source_name}' is unsafe."
                                )
                            files = tuple(sorted(source_checkpoints.iterdir()))
                            if any(
                                path.is_symlink()
                                or not path.is_file()
                                or path.suffix != ".json"
                                for path in files
                            ):
                                raise ValueError(
                                    f"Checkpoint history for "
                                    f"'{binding.source_name}' is unsafe."
                                )
                        prepared_files: list[tuple[Path, dict[str, object] | None]] = []
                        for path in files:
                            rewritten: dict[str, object] | None = None
                            if include_descendants:
                                try:
                                    with open(path, encoding="utf-8") as file:
                                        raw = json.load(
                                            file,
                                            object_pairs_hook=(
                                                _reject_duplicate_json_keys
                                            ),
                                        )
                                except (json.JSONDecodeError, ValueError) as error:
                                    raise ValueError(
                                        f"Checkpoint history for "
                                        f"'{binding.source_name}' is invalid."
                                    ) from error
                                if not isinstance(raw, dict):
                                    raise ValueError(
                                        f"Checkpoint history for "
                                        f"'{binding.source_name}' is invalid."
                                    )
                                rewritten = _rewrite_branched_checkpoint_record(
                                    raw,
                                    targets_by_source_uid=targets_by_source_uid,
                                )
                            prepared_files.append((path, rewritten))
                        checkpoint_files[binding.source_name] = tuple(prepared_files)

                    for target_name in target_names:
                        if self.context_exists(target_name):
                            self.load_direct(target_name)
                            raise FileExistsError(
                                f"Context '{target_name}' already exists."
                            )
                        self._assert_context_storage_available(target_name)

                    created: list[Context] = []
                    branch_error: Exception | None = None
                    with self._state_write_lock():
                        state = self._read_state()
                        if state.get("current") != expected_current:
                            raise ConcurrentContextUpdateError(
                                "The current Context changed before the branch "
                                "could be created."
                            )
                        try:
                            for binding in records:
                                target = binding.target
                                self._save_locked(
                                    target,
                                    None,
                                    expected_context_digest=None,
                                    require_new=True,
                                )
                                created.append(target)
                                target_checkpoints = self._checkpoints_dir(target.name)
                                for source_path, rewritten in checkpoint_files[
                                    binding.source_name
                                ]:
                                    destination = target_checkpoints / source_path.name
                                    if destination.exists() or destination.is_symlink():
                                        raise FileExistsError(
                                            f"Branch checkpoint destination for "
                                            f"'{target.name}' already exists."
                                        )
                                    if rewritten is None:
                                        _write_bytes_atomic(
                                            destination,
                                            source_path.read_bytes(),
                                        )
                                    else:
                                        _write_json_atomic(destination, rewritten)
                                checkpoint = self._save_locked(
                                    target,
                                    AutoCheckpoint(
                                        command="branch",
                                        args={
                                            "branch_tree": branch_tree,
                                            "command_contexts": command_contexts,
                                        },
                                        description=branch_description,
                                    ),
                                    expected_context_digest=context_record_digest(
                                        target
                                    ),
                                )
                                if checkpoint is None:
                                    raise RuntimeError(
                                        "Branch creation recorded no command "
                                        "checkpoint."
                                    )
                            state["current"] = target_root
                            self._write_state(state)
                        except Exception as error:
                            branch_error = error
                    if branch_error is not None:
                        rollback_error: Exception | None = None
                        for target in reversed(created):
                            try:
                                self._delete_locked(target.name)
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Branch creation failed and its new Context "
                                "hierarchy could not be fully rolled back."
                            ) from rollback_error
                        raise branch_error
        for binding in records:
            binding.target._store_digest = context_record_digest(binding.target)

    def create_missing_contexts(
        self,
        entries: Iterable[tuple[Context, Optional[AutoCheckpoint]]],
        *,
        make_current: str | None = None,
        require_all_new: bool = False,
        expected_current: str | None | object = _NO_CURRENT_CONTEXT_EXPECTATION,
    ) -> tuple[Context, ...]:
        """Create one namespace batch and optionally CAS-select its target."""
        with self._command_write_lock():
            return self._create_missing_contexts_command_locked(
                entries,
                make_current=make_current,
                require_all_new=require_all_new,
                expected_current=expected_current,
            )

    def _create_missing_contexts_command_locked(
        self,
        entries: Iterable[tuple[Context, Optional[AutoCheckpoint]]],
        *,
        make_current: str | None = None,
        require_all_new: bool = False,
        expected_current: str | None | object = _NO_CURRENT_CONTEXT_EXPECTATION,
    ) -> tuple[Context, ...]:
        """Create a validated batch and optionally select one batch Context.

        All names stay locked from preflight through rollback. This matters
        for namespace-parent creation: releasing an earlier parent lock before
        a later child fails could let another process modify that new parent,
        which a command-level rollback might then wrongly delete. Selection
        stays inside the same boundary so a new leaf cannot be deleted or
        replaced between its creation and the state write.

        ``require_all_new`` is used by exact creation and identity-preserving
        import: silently reusing one existing name would turn a reviewed
        all-new batch into a different operation. When supplied,
        ``expected_current`` prevents a long interactive creation flow from
        overwriting a later Context switch at the final state write.
        """
        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context is required.")
        if any(not isinstance(context, Context) for context, _ in records):
            raise TypeError("Expected Context records.")
        names = tuple(context.name for context, _ in records)
        for name in names:
            validate_portable_context_name(name)
        if len(names) != len(set(names)):
            raise ValueError("Context batch contains duplicate names.")
        if make_current is not None and make_current not in names:
            raise ValueError("Selected Context must be part of the creation batch.")

        with self._context_graph_lock(exclusive=False):
            with self._context_write_locks(names):
                existing: set[str] = set()
                for name in names:
                    if self.context_exists(name):
                        # A present file is not reusable until its stored identity
                        # and path-bound header have passed normal validation.
                        self.load_direct(name)
                        existing.add(name)
                    else:
                        self._assert_context_storage_available(name)

                if require_all_new and existing:
                    raise FileExistsError(
                        "Context destination already exists: "
                        + ", ".join(sorted(existing))
                    )

                created: list[Context] = []
                try:
                    for context, auto_checkpoint in records:
                        if context.name in existing:
                            continue
                        self._save_locked(
                            context,
                            auto_checkpoint,
                            expected_context_digest=None,
                            require_new=True,
                        )
                        context._store_digest = context_record_digest(context)
                        created.append(context)
                    if make_current is not None:
                        with self._state_write_lock():
                            state = self._read_state()
                            if (
                                expected_current is not _NO_CURRENT_CONTEXT_EXPECTATION
                                and state.get("current") != expected_current
                            ):
                                raise ConcurrentContextUpdateError(
                                    "The current Context changed before the new "
                                    "Context could be selected."
                                )
                            state["current"] = make_current
                            self._write_state(state)
                except Exception as error:
                    rollback_error: Exception | None = None
                    for context in reversed(created):
                        try:
                            self._delete_locked(context.name)
                        except Exception as candidate:
                            rollback_error = candidate
                            break
                    if rollback_error is not None:
                        raise RuntimeError(
                            "Context hierarchy creation failed and its newly "
                            "created Contexts could not be rolled back."
                        ) from rollback_error
                    raise error
        return tuple(created)

    def _save_locked(
        self,
        ctx: Context,
        auto_checkpoint: Optional[AutoCheckpoint],
        *,
        expected_context_digest: str | None,
        require_new: bool = False,
    ) -> Checkpoint | None:
        """Save while holding this Context's cooperative process lock."""
        self._assert_profile_write_allowed()
        ctx_dir = self._context_dir(ctx.name)
        context_file = self._context_file(ctx.name)
        if context_file.is_symlink():
            raise ValueError(
                f"Refusing to write context '{ctx.name}' through a symbolic link."
            )
        context_preexisting = self.context_exists(ctx.name)
        if not context_preexisting:
            # Existing non-portable records remain writable until an explicit
            # identity-preserving migration moves them. A newly published
            # identity must never reintroduce shell-dependent spelling.
            validate_portable_context_name(ctx.name)
        if require_new and context_preexisting:
            raise FileExistsError(f"Context '{ctx.name}' already exists.")
        current_record: dict[str, object] | None = None
        if context_preexisting:
            with open(context_file, encoding="utf-8") as file:
                loaded_record = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            current_record = _validate_context_header(
                loaded_record,
                ctx.name,
            )
        if expected_context_digest is not None:
            if len(expected_context_digest) != 64 or any(
                character not in "0123456789abcdef"
                for character in expected_context_digest
            ):
                raise ValueError("Expected Context digest is invalid.")
            if not context_preexisting:
                raise ConcurrentContextUpdateError(
                    f"Context '{ctx.name}' no longer exists."
                )
            assert current_record is not None
            if context_record_digest(current_record) != expected_context_digest:
                raise ConcurrentContextUpdateError(
                    f"Context '{ctx.name}' changed before it could be saved."
                )
        if current_record is not None:
            self._assert_context_record_change_allowed(current_record, ctx)
        if not context_preexisting:
            self._assert_context_storage_available(ctx.name)
        ctx_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir = self._checkpoints_dir(ctx.name)
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        created_checkpoint: Checkpoint | None = None
        try:
            if auto_checkpoint is not None:
                # _save_locked already owns the Context lock. Calling the
                # public locking wrapper here would deadlock on flock, while
                # writing without this shared lock would let checkpoint
                # history race reviewed revert/undo selections.
                created_checkpoint = self._checkpoint_locked(
                    ctx,
                    message=auto_checkpoint.description,
                    command=auto_checkpoint.command,
                    args=auto_checkpoint.args,
                    description=auto_checkpoint.description,
                    auto=True,
                    command_before=current_record,
                )
            _write_json_atomic(context_file, ctx.to_dict())
        except Exception as error:
            cleanup_error: Exception | None = None
            if created_checkpoint is not None:
                try:
                    matches = list(
                        checkpoints_dir.glob(f"*-{created_checkpoint.uid[:8]}.json")
                    )
                    for path in matches:
                        if path.is_symlink() or not path.is_file():
                            continue
                        with open(path) as f:
                            value = json.load(f)
                        if value.get("uid") == created_checkpoint.uid:
                            path.unlink()
                            break
                except Exception as candidate:
                    cleanup_error = candidate
            if not context_preexisting and not context_file.exists():
                try:
                    checkpoints_dir.rmdir()
                    self._prune_empty_namespace_dirs(ctx_dir)
                except OSError:
                    # A pre-existing child namespace or an unexpected artifact
                    # is never removed as part of rollback.
                    pass
            if cleanup_error is not None:
                raise RuntimeError(
                    "Context save failed and its automatic checkpoint could "
                    "not be rolled back."
                ) from cleanup_error
            raise error
        return created_checkpoint

    # --- Query-only research sources ---

    @staticmethod
    def _canonical_query_source_uid(source_uid: str) -> str:
        if not isinstance(source_uid, str):
            raise ValueError("Query source uid must be a canonical UUID.")
        try:
            parsed = uuid.UUID(source_uid)
        except (AttributeError, TypeError, ValueError) as e:
            raise ValueError("Query source uid must be a canonical UUID.") from e
        canonical = str(parsed)
        if source_uid != canonical:
            raise ValueError("Query source uid must be a canonical UUID.")
        return canonical

    def _query_source_dir(self, source_uid: str) -> Path:
        canonical = self._canonical_query_source_uid(source_uid)
        if self.query_sources_dir.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        source_dir = self.query_sources_dir / canonical
        if source_dir.is_symlink():
            raise ValueError("Query source directory cannot be a symbolic link.")
        root = self.query_sources_dir.resolve()
        resolved = source_dir.resolve(strict=False)
        if root not in resolved.parents:
            raise ValueError("Query source path escapes query source storage.")
        return source_dir

    def _query_source_file(self, source_uid: str) -> Path:
        source_file = self._query_source_dir(source_uid) / "source.json"
        if source_file.is_symlink():
            raise ValueError("Query source file cannot be a symbolic link.")
        return source_file

    def create_query_source(self, name: str, content: str) -> QuerySource:
        """
        Store a concealed research source outside normal Context storage.

        This is UI-level concealment for a study prototype, not a security
        boundary. The local user can still read files under ~/.mem.
        """
        return self.create_bilingual_query_source(
            name,
            entries=(
                {
                    "key": "content",
                    "canonical_content": content,
                },
            ),
        )

    @_profile_write_guarded
    def create_bilingual_query_source(
        self,
        name: str,
        entries: Iterable[QuerySourceEntry | dict[str, object]],
    ) -> QuerySource:
        """Store stable English entries and optional concealed translations.

        The method name reflects the study-fixture use case, while the record
        format accepts more than one non-English language. Entry ``uid`` values
        are generated when omitted and may be supplied as canonical UUIDs by a
        deterministic fixture builder.
        """
        validate_portable_context_name(name)
        canonical_language = "en"
        try:
            raw_entries = tuple(entries)
        except TypeError as error:
            raise ValueError("Query source entries must be iterable.") from error
        if not raw_entries:
            raise ValueError("Query source must contain at least one entry.")
        source_entries = tuple(
            _query_source_entry_from_record(
                entry,
                canonical_language=canonical_language,
                allow_missing_uid=True,
            )
            for entry in raw_entries
        )
        entry_uids = [entry.uid for entry in source_entries]
        entry_keys = [entry.key for entry in source_entries]
        if len(entry_uids) != len(set(entry_uids)):
            raise ValueError("Query source entry uids must be unique.")
        if len(entry_keys) != len(set(entry_keys)):
            raise ValueError("Query source entry keys must be unique.")
        if self.query_sources_dir.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        self.query_sources_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.query_sources_dir, 0o700)

        source = QuerySource(
            uid=str(uuid.uuid4()),
            name=name,
            entries=source_entries,
        )
        source_dir = self._query_source_dir(source.uid)
        source_file = self._query_source_file(source.uid)
        source_dir.mkdir(mode=0o700)
        os.chmod(source_dir, 0o700)
        try:
            with open(source_file, "x", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": 2,
                        "uid": source.uid,
                        "name": source.name,
                        "canonical_language": canonical_language,
                        "entries": [
                            {
                                "uid": entry.uid,
                                "key": entry.key,
                                "canonical_content": entry.canonical_content,
                                "translations": dict(entry.translations),
                            }
                            for entry in source.entries
                        ],
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
                f.flush()
                os.fsync(f.fileno())
            os.chmod(source_file, 0o600)
        except Exception:
            if source_file.exists() and not source_file.is_symlink():
                source_file.unlink()
            source_dir.rmdir()
            raise
        return source

    def load_query_source(
        self,
        source_uid: str,
        *,
        expected_name: str,
        language: str = "en",
        fallback_to_canonical: bool = False,
    ) -> QuerySource:
        """Load one concealed source, selecting entry text in ``language``.

        A requested translation must cover every entry. Callers that
        deliberately accept a mixed-language result may opt into canonical
        English fallback explicitly.
        """
        canonical_source_uid = self._canonical_query_source_uid(source_uid)
        _context_name_parts(expected_name)
        selected_language = _query_source_language(
            language,
            field="Query source language",
        )
        if not isinstance(fallback_to_canonical, bool):
            raise ValueError("Query source fallback_to_canonical must be a boolean.")
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        with open(source_file, encoding="utf-8") as f:
            data = json.load(f, object_pairs_hook=_reject_duplicate_json_keys)
        if not isinstance(data, dict):
            raise ValueError("Query source identity or structure is invalid.")
        schema_version = data.get("schema_version")
        if schema_version == 1 and type(schema_version) is int:
            if set(data) != {"schema_version", "uid", "name", "content"}:
                raise ValueError("Query source identity or structure is invalid.")
            content = _query_source_text(
                data.get("content"),
                field="Query source content",
            )
            legacy_entry_uid = str(
                uuid.uuid5(
                    uuid.UUID(canonical_source_uid),
                    "legacy-query-source-content",
                )
            )
            canonical_language = "en"
            entries = (
                QuerySourceEntry(
                    uid=legacy_entry_uid,
                    key="legacy-content",
                    canonical_content=content,
                ),
            )
        elif schema_version == 2 and type(schema_version) is int:
            if set(data) != {
                "schema_version",
                "uid",
                "name",
                "canonical_language",
                "entries",
            }:
                raise ValueError("Query source identity or structure is invalid.")
            canonical_language = _query_source_language(
                data.get("canonical_language"),
                field="Query source canonical language",
            )
            if canonical_language != "en":
                raise ValueError(
                    "Query source canonical language must be English ('en')."
                )
            raw_entries = data.get("entries")
            if not isinstance(raw_entries, list) or not raw_entries:
                raise ValueError(
                    "Query source must contain at least one persisted entry."
                )
            entries = tuple(
                _query_source_entry_from_record(
                    entry,
                    canonical_language=canonical_language,
                    allow_missing_uid=False,
                )
                for entry in raw_entries
            )
            entry_uids = [entry.uid for entry in entries]
            entry_keys = [entry.key for entry in entries]
            if len(entry_uids) != len(set(entry_uids)):
                raise ValueError("Query source entry uids must be unique.")
            if len(entry_keys) != len(set(entry_keys)):
                raise ValueError("Query source entry keys must be unique.")
        else:
            raise ValueError("Query source identity or structure is invalid.")
        if data.get("uid") != canonical_source_uid or data.get("name") != expected_name:
            raise ValueError("Query source identity or structure is invalid.")

        # Resolve the full source now so an absent translation fails before a
        # partially usable QuerySource can reach the provider.
        for entry in entries:
            entry.content_for(
                selected_language,
                canonical_language=canonical_language,
                fallback_to_canonical=fallback_to_canonical,
            )
        return QuerySource(
            uid=data["uid"],
            name=data["name"],
            entries=entries,
            selected_language=selected_language,
            canonical_language=canonical_language,
            fallback_to_canonical=fallback_to_canonical,
        )

    @_profile_write_guarded
    def delete_query_source(self, source_uid: str) -> None:
        """Delete one exact hidden source, used to roll back failed setup."""
        source_dir = self._query_source_dir(source_uid)
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        source_file.unlink()
        source_dir.rmdir()

    def _context_deletion_event_locked(
        self,
        name: str,
        *,
        current: Context | None = None,
    ) -> ContextLifecycleEvent:
        """Freeze deletion metadata while the exact Context lock is held."""
        context = current if current is not None else self.load_direct(name)
        if context.name != name:
            raise ValueError("Context deletion metadata names the wrong Context.")
        try:
            checkpoints = self.list_checkpoints(name)
        except (KeyError, OSError, TypeError, ValueError):
            # Deletion removes the complete history directory regardless. A
            # malformed non-checkpoint artifact must not retarget or prevent
            # an exact-identity deletion; it only means the optional lifecycle
            # ledger cannot name a trustworthy previous checkpoint.
            checkpoints = []
            previous_status = PREVIOUS_CHECKPOINT_UNREADABLE
        else:
            previous_status = (
                PREVIOUS_CHECKPOINT_RECORDED
                if checkpoints
                else PREVIOUS_CHECKPOINT_NONE
            )
        if checkpoints:
            previous = checkpoints[0]
            previous_uid = previous.get("uid")
            if not isinstance(previous_uid, str) or not previous_uid:
                raise ValueError(
                    "Latest Context checkpoint has no valid uid for deletion."
                )
            previous_digest = _canonical_json_digest(previous)
        else:
            previous_uid = None
            previous_digest = None
        return ContextLifecycleEvent.deleted(
            context_uid=context.uid,
            last_context_name=context.name,
            last_context_digest=context_record_digest(context),
            previous_checkpoint_status=previous_status,
            previous_checkpoint_uid=previous_uid,
            previous_checkpoint_digest=previous_digest,
        )

    def delete(self, name: str) -> ContextLifecycleEvent:
        """Delete one Context and retain metadata in its Profile ledger."""
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                with self.profile_write_guard():
                    event = self._context_deletion_event_locked(name)
                    recorded = self._delete_locked(name, lifecycle_event=event)
                    assert recorded is event
                    return event

    def delete_context_if(
        self,
        name: str,
        *,
        expected_context_uid: str,
        expected_context_digest: str,
    ) -> ContextLifecycleEvent:
        """Delete only the exact Context identity that was previously reviewed."""
        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(name):
                with self.profile_write_guard():
                    try:
                        current = self.load_direct(name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Context '{name}' no longer exists."
                        ) from error
                    if (
                        current.uid != expected_context_uid
                        or context_record_digest(current) != expected_context_digest
                    ):
                        raise ConcurrentContextUpdateError(
                            f"Context '{name}' changed after deletion was reviewed."
                        )
                    event = self._context_deletion_event_locked(
                        name,
                        current=current,
                    )
                    recorded = self._delete_locked(name, lifecycle_event=event)
                    assert recorded is event
                    return event

    def _delete_locked(
        self,
        name: str,
        *,
        lifecycle_event: ContextLifecycleEvent | None = None,
    ) -> ContextLifecycleEvent | None:
        """Delete one Context; internal creation rollback passes no event."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        current_context = self.load_direct(name)
        context_uid = current_context.uid
        if lifecycle_event is not None:
            self._assert_context_deletion_allowed(current_context)
        if lifecycle_event is not None and (
            lifecycle_event.context_uid != context_uid
            or lifecycle_event.last_context_name != name
            or lifecycle_event.last_context_digest
            != context_record_digest(current_context)
        ):
            raise ConcurrentContextUpdateError(
                "Context changed before its deletion event could be committed."
            )
        # Validate the derived-artifact path before deleting the primary
        # Context so a malformed analysis store cannot turn cleanup into a
        # surprising partial operation.
        try:
            canonical_context_uid = str(uuid.UUID(context_uid))
        except (AttributeError, TypeError, ValueError):
            canonical_context_uid = None
        from memcommit.comparison_store import (
            comparison_paths_for_context,
            delete_comparison_paths,
        )
        from memcommit.translation_view_store import (
            delete_translation_view_paths,
            translation_view_paths_for_context,
        )
        from memcommit.rationale_cache import (
            delete_rationale_inference_paths,
            rationale_inference_paths_for_context,
        )

        # Compare artifacts snapshot both sources and derived explanations.
        # Their privacy lifetime therefore ends when either bound source is
        # deleted, regardless of which side was the display reference.
        comparison_paths = (
            comparison_paths_for_context(context_uid)
            if canonical_context_uid == context_uid
            else ()
        )
        translation_view_paths = (
            translation_view_paths_for_context(context_uid)
            if canonical_context_uid == context_uid
            else ()
        )
        rationale_inference_paths = (
            rationale_inference_paths_for_context(context_uid)
            if canonical_context_uid == context_uid
            else ()
        )
        analysis_path = (
            self._atomize_analysis_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        workbench_path = (
            self._atomize_workbench_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        grounding_path = (
            self._atomize_grounding_session_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        grounding_history_dir = (
            self._atomize_grounding_history_dir(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        meld_path = (
            self._meld_session_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        for artifact, label in (
            (analysis_path, "Atomize analysis"),
            (workbench_path, "Atomize workbench"),
            (grounding_path, "Atomize grounding"),
            (meld_path, "Meld session"),
        ):
            if (
                artifact is not None
                and (artifact.exists() or artifact.is_symlink())
                and (not artifact.is_file() or artifact.is_symlink())
            ):
                raise ValueError(f"{label} storage is invalid.")
        if (
            grounding_history_dir is not None
            and grounding_history_dir.exists()
            and any(
                child.is_symlink() or not child.is_file() or child.suffix != ".json"
                for child in grounding_history_dir.iterdir()
            )
        ):
            raise ValueError("Atomize grounding history is invalid.")
        review_session = self.load_review_session()
        delete_review_session = (
            review_session is not None
            and review_session.context_uid == context_uid
            and review_session.context_name == name
        )
        ctx_dir = self._context_dir(name)
        context_file = self._context_file(name)
        checkpoints_dir = self._checkpoints_dir(name)
        if checkpoints_dir.exists() and not checkpoints_dir.is_dir():
            raise ValueError(
                f"Cannot delete context '{name}': its checkpoints path is not "
                "a directory."
            )

        # Move exact Context artifacts aside before deletion. Renames within a
        # directory are atomic, and descendants are never part of these paths.
        # If staging fails, restore the Context file before surfacing the error.
        token = uuid.uuid4().hex
        staged_context = ctx_dir / f".context.json.delete-{token}"
        staged_checkpoints = ctx_dir / f".checkpoints.delete-{token}"
        context_file.rename(staged_context)
        checkpoints_staged = False
        try:
            if checkpoints_dir.exists():
                checkpoints_dir.rename(staged_checkpoints)
                checkpoints_staged = True
            _fsync_directory(ctx_dir)
        except OSError:
            if checkpoints_staged:
                staged_checkpoints.rename(checkpoints_dir)
            staged_context.rename(context_file)
            _fsync_directory(ctx_dir)
            raise

        ledger_guard = ExitStack()
        try:
            if lifecycle_event is not None:
                ledger_guard.enter_context(
                    self._context_lifecycle_ledger_lock(exclusive=True)
                )
        except Exception:
            if checkpoints_staged:
                staged_checkpoints.rename(checkpoints_dir)
            staged_context.rename(context_file)
            _fsync_directory(ctx_dir)
            raise

        lifecycle_event_path: Path | None = None
        # A final event is provisional until the primary unlink succeeds.
        # Readers share this lock, so they can never observe an event that a
        # normal pre-commit rollback subsequently removes.
        with ledger_guard:
            try:
                if lifecycle_event is not None:
                    lifecycle_event_path = self._write_context_lifecycle_event(
                        lifecycle_event
                    )
            except Exception:
                if checkpoints_staged:
                    staged_checkpoints.rename(checkpoints_dir)
                staged_context.rename(context_file)
                _fsync_directory(ctx_dir)
                raise

            try:
                staged_context.unlink()
            except OSError as error:
                rollback_error: Exception | None = None
                if lifecycle_event_path is not None:
                    try:
                        self._remove_context_lifecycle_event(lifecycle_event_path)
                    except Exception as candidate:
                        rollback_error = candidate
                try:
                    if checkpoints_staged:
                        staged_checkpoints.rename(checkpoints_dir)
                    staged_context.rename(context_file)
                    _fsync_directory(ctx_dir)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
                if rollback_error is not None:
                    raise RuntimeError(
                        "Context deletion failed before commit and its staged "
                        "Context or lifecycle event could not be restored."
                    ) from rollback_error
                raise error

        cleanup_failures: list[tuple[str, Exception]] = []

        def attempt_cleanup(label: str, action: Callable[[], None]) -> None:
            try:
                action()
            except Exception as error:
                # Primary deletion is already committed. Continue independent
                # privacy cleanup so one sidecar failure cannot retain all
                # remaining Context-owned content.
                cleanup_failures.append((label, error))

        attempt_cleanup(
            "Context directory durability",
            lambda: _fsync_directory(ctx_dir),
        )
        if checkpoints_staged:

            def remove_checkpoint_history() -> None:
                shutil.rmtree(staged_checkpoints)
                _fsync_directory(ctx_dir)

            attempt_cleanup("checkpoint history", remove_checkpoint_history)
        if analysis_path is not None and analysis_path.exists():
            attempt_cleanup("Atomize analysis", analysis_path.unlink)
        if workbench_path is not None and workbench_path.exists():
            # Workbench responses may contain free-form user context. They are
            # scoped to the deleted Context and must not survive it.
            attempt_cleanup("Atomize workbench", workbench_path.unlink)
        if grounding_path is not None and grounding_path.exists():
            # Grounding turns retain the reviewer's words verbatim. Keeping
            # them after their exact Context is gone would be both misleading
            # state and an avoidable privacy leak.
            attempt_cleanup("Atomize grounding", grounding_path.unlink)
        if meld_path is not None and meld_path.exists():
            # Meld dialogue may retain both source text and verbatim user
            # comments. Its privacy and validity lifetime is the target.
            attempt_cleanup("Meld session", meld_path.unlink)
        attempt_cleanup(
            "Compare analyses",
            lambda: delete_comparison_paths(comparison_paths),
        )
        # Translation views retain provider-derived copies of source content.
        # Their privacy and validity lifetime therefore ends with the source.
        attempt_cleanup(
            "translation views",
            lambda: delete_translation_view_paths(translation_view_paths),
        )
        # A contextual explanation is derived from the deleted direct frame,
        # so its cache shares that Context's privacy lifetime.
        attempt_cleanup(
            "rationale inference cache",
            lambda: delete_rationale_inference_paths(rationale_inference_paths),
        )
        if grounding_history_dir is not None and grounding_history_dir.exists():
            # Terminal dialogues contain the same verbatim local evidence as
            # the latest slot and share the deleted Context's privacy lifetime.
            def remove_grounding_history() -> None:
                shutil.rmtree(grounding_history_dir)
                _fsync_directory(grounding_history_dir.parent)
                try:
                    self.atomize_grounding_history_dir.rmdir()
                except OSError:
                    pass

            attempt_cleanup("Atomize grounding history", remove_grounding_history)
        if delete_review_session and self.review_session_file.exists():
            # Review answers may contain user-supplied local context. Once
            # their exact Context is deleted, retaining that global artifact
            # would be both misleading state and an avoidable privacy leak.
            attempt_cleanup("review session", self.review_session_file.unlink)

        def clear_current_pointer() -> None:
            with self._state_write_lock():
                state = self._read_state()
                if state.get("current") == name:
                    state["current"] = None
                    self._write_state(state)

        attempt_cleanup("current pointer", clear_current_pointer)
        self._prune_empty_namespace_dirs(ctx_dir)
        if cleanup_failures:
            if lifecycle_event is not None:
                raise ContextDeletionCommittedError(
                    lifecycle_event,
                    tuple(cleanup_failures),
                ) from cleanup_failures[0][1]
            raise cleanup_failures[0][1]
        return lifecycle_event

    # --- Checkpoints ---

    # Storage design note:
    # Checkpoints intentionally embed a complete serialization of the Context's
    # direct state.  At the current research-prototype scale, this keeps
    # persistence, recovery, and migration simpler than an object store; nested
    # Contexts and MemoryRefs are already serialized as pointers rather than
    # recursively copied.  If Contexts or histories grow substantially, retain
    # the same logical snapshot semantics while moving Memory contents to
    # content-addressed blobs and having checkpoints point to ordered tree
    # manifests.  A pure delta/event chain is not required by the current model.
    def checkpoint(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
    ) -> Checkpoint:
        """Save a persisted Context snapshot under its cooperative write lock."""
        with self._command_write_lock():
            with self._context_write_lock(ctx.name):
                if not self.context_exists(ctx.name):
                    raise FileNotFoundError(
                        f"Context '{ctx.name}' must be saved before checkpointing."
                    )
                current = self.load_direct(ctx.name)
                expected_digest = getattr(ctx, "_store_digest", None)
                current_digest = context_record_digest(current)
                if current.uid != ctx.uid or (
                    expected_digest is not None and current_digest != expected_digest
                ):
                    # A checkpoint is part of the same serial history as saves and
                    # reverts. Never append a stale caller's snapshot after a
                    # concurrent state change.
                    raise ConcurrentContextUpdateError(
                        f"Context '{ctx.name}' changed before it could be checkpointed."
                    )
                if context_record_digest(ctx) != current_digest:
                    raise ValueError(
                        f"Context '{ctx.name}' has unsaved changes; save it "
                        "before checkpointing."
                    )
                return self._checkpoint_locked(
                    ctx,
                    message=message,
                    command=command,
                    args=args,
                    description=description,
                    auto=auto,
                )

    def checkpoint_context_batch(
        self,
        entries: Iterable[tuple[Context, str]],
        *,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        expected_context_catalog: Iterable[str] | None = None,
    ) -> tuple[Checkpoint, ...]:
        """Append one exception-atomic checkpoint set to existing Contexts.

        Context bytes are unchanged. Every member is locked and revalidated
        before the first history append, and a failed later append removes the
        provisional checkpoints already written by this call. A durable crash
        journal remains outside this prototype boundary.
        """

        records = tuple(entries)
        if not records:
            raise ValueError("At least one Context checkpoint entry is required.")
        if any(
            not isinstance(context, Context)
            or not isinstance(expected_digest, str)
            or not expected_digest
            for context, expected_digest in records
        ):
            raise TypeError("Invalid Context checkpoint batch entry.")
        names = tuple(context.name for context, _expected_digest in records)
        if len(names) != len(set(names)):
            raise ValueError("Context checkpoint batch contains duplicate names.")
        for name in names:
            validate_context_name(name)
        expected_catalog = (
            None
            if expected_context_catalog is None
            else tuple(expected_context_catalog)
        )
        if expected_catalog is not None and (
            len(expected_catalog) != len(set(expected_catalog))
            or any(not isinstance(name, str) or not name for name in expected_catalog)
        ):
            raise ValueError("Expected Context checkpoint catalog is invalid.")

        with self._command_write_lock():
            with self._context_graph_lock(exclusive=expected_catalog is not None):
                if (
                    expected_catalog is not None
                    and tuple(self.list_context_names()) != expected_catalog
                ):
                    raise ConcurrentContextUpdateError(
                        "The Context namespace changed after the checkpoint "
                        "scope was selected."
                    )
                with self._context_write_locks(names):
                    self._assert_profile_write_allowed()
                    for context, expected_digest in records:
                        try:
                            current = self.load_direct(context.name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' no longer exists."
                            ) from error
                        current_digest = context_record_digest(current)
                        if (
                            current.uid != context.uid
                            or current_digest != expected_digest
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Context '{context.name}' changed before it "
                                "could be checkpointed."
                            )
                        if context_record_digest(context) != current_digest:
                            raise ValueError(
                                f"Context '{context.name}' has unsaved changes; "
                                "save it before checkpointing."
                            )

                    created: list[tuple[str, Checkpoint]] = []
                    try:
                        for context, _expected_digest in records:
                            checkpoint = self._checkpoint_locked(
                                context,
                                message=message,
                                command=command,
                                args=args,
                                description=description,
                                auto=auto,
                            )
                            created.append((context.name, checkpoint))
                    except Exception:
                        rollback_error: Exception | None = None
                        for name, checkpoint in created:
                            try:
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Context checkpoint batch failed and could not "
                                "be fully rolled back."
                            ) from rollback_error
                        raise
        return tuple(checkpoint for _name, checkpoint in created)

    def _checkpoint_locked(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        command_before: dict[str, object] | None = None,
    ) -> Checkpoint:
        """Write one checkpoint while the caller holds the Context lock."""
        self._assert_profile_write_allowed()
        cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command=command,
            args=args,
            description=description,
            auto=auto,
        )
        ts = cp.timestamp.strftime("%Y%m%dT%H%M%S")
        slug = (
            message[:24].replace(" ", "-").replace("/", "-")
            if message
            else (command or "checkpoint")
        )
        cp_dir = self._checkpoints_dir(ctx.name)
        cp_dir.mkdir(parents=True, exist_ok=True)
        cp_file = cp_dir / f"{ts}-{slug}-{cp.uid[:8]}.json"
        if cp_file.is_symlink():
            raise ValueError(
                f"Refusing to write checkpoint for '{ctx.name}' through a "
                "symbolic link."
            )
        checkpoint_record = {
            "uid": cp.uid,
            "message": cp.message,
            "timestamp": cp.timestamp.isoformat(),
            "snapshot": cp.snapshot,
            "command": cp.command,
            "args": cp.args,
            "description": cp.description,
            "auto": cp.auto,
        }
        if command_before is not None:
            checkpoint_record["command_before"] = command_before
        _write_json_atomic(cp_file, checkpoint_record)
        return cp

    def list_checkpoints(self, name: str) -> list[dict]:
        """Return checkpoints for a context, sorted newest-first."""
        cp_dir = self._checkpoints_dir(name)
        if not cp_dir.exists():
            return []
        entries = []
        for path in sorted(cp_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            with open(path) as f:
                entries.append(json.load(f))
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)

    def _command_context_archive_path(self, checkpoint_uid: str) -> Path:
        """Resolve one exact creation-command archive without accepting paths."""
        try:
            canonical = str(uuid.UUID(checkpoint_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Command archive checkpoint uid is invalid.") from error
        if canonical != checkpoint_uid:
            raise ValueError("Command archive checkpoint uid is invalid.")
        root = self.command_context_archives_dir
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ValueError("Command Context archive storage is invalid.")
        return root / checkpoint_uid

    def _load_command_context_archive(
        self,
        checkpoint_uid: str,
    ) -> tuple[Path, dict[str, object], Context, list[dict[str, object]]]:
        """Load one absent Context and its retained checkpoint history."""
        archive = self._command_context_archive_path(checkpoint_uid)
        if archive.is_symlink() or not archive.is_dir():
            raise FileNotFoundError("Command Context archive is unavailable.")
        manifest_path = archive / "manifest.json"
        context_path = archive / "context.json"
        checkpoints_path = archive / "checkpoints"
        for path, label in (
            (manifest_path, "manifest"),
            (context_path, "Context record"),
        ):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Command Context archive {label} is invalid.")
        if checkpoints_path.is_symlink() or not checkpoints_path.is_dir():
            raise ValueError("Command Context archive checkpoints are invalid.")
        with open(manifest_path, encoding="utf-8") as file:
            manifest = json.load(
                file,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        sever_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
            "session_uid",
            "application",
            "reviewing_session_digest",
        }
        lifecycle_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
        }
        atomize_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
            "analysis_uid",
            "source_context_uid",
            "source_context_name",
            "source_workbench",
            "reviewing_workbench_digest",
            "terminal_workbench_digest",
            "current_before",
        }
        if (
            not isinstance(manifest, dict)
            or manifest.get("version") != 1
            or manifest.get("checkpoint_uid") != checkpoint_uid
        ):
            raise ValueError("Command Context archive manifest is invalid.")
        command = manifest.get("command")
        unit_uid = manifest.get("unit_uid")
        if command == "sever":
            if (
                set(manifest) != sever_manifest_fields
                or unit_uid != f"checkpoint:{checkpoint_uid}"
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "merge":
            if (
                set(manifest) != lifecycle_manifest_fields
                or not isinstance(unit_uid, str)
                or not unit_uid.startswith("merge:")
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "branch":
            if (
                set(manifest) != lifecycle_manifest_fields
                or not isinstance(unit_uid, str)
                or not unit_uid.startswith("branch:")
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "atomize":
            if (
                set(manifest) != atomize_manifest_fields
                or unit_uid != f"checkpoint:{checkpoint_uid}"
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        else:
            raise ValueError("Command Context archive manifest is invalid.")
        context_name = manifest.get("context_name")
        context_uid = manifest.get("context_uid")
        if (
            not isinstance(context_name, str)
            or not context_name
            or not isinstance(context_uid, str)
            or not context_uid
        ):
            raise ValueError("Command Context archive manifest is invalid.")
        if command == "sever":
            session_uid = manifest.get("session_uid")
            reviewing_digest = manifest.get("reviewing_session_digest")
            if (
                not isinstance(session_uid, str)
                or not session_uid
                or not isinstance(reviewing_digest, str)
                or len(reviewing_digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in reviewing_digest
                )
                or not isinstance(manifest.get("application"), dict)
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "atomize":
            source_context_uid = manifest.get("source_context_uid")
            source_context_name = manifest.get("source_context_name")
            analysis_uid = manifest.get("analysis_uid")
            current_before = manifest.get("current_before")
            if (
                not isinstance(source_context_uid, str)
                or not source_context_uid
                or not isinstance(source_context_name, str)
                or not source_context_name
                or not isinstance(analysis_uid, str)
                or not analysis_uid
                or (current_before is not None and not isinstance(current_before, str))
            ):
                raise ValueError("Command Context archive manifest is invalid.")
            _context_name_parts(source_context_name)
            source_workbench = manifest.get("source_workbench")
            reviewing_digest = manifest.get("reviewing_workbench_digest")
            terminal_digest = manifest.get("terminal_workbench_digest")
            if source_workbench is None:
                if reviewing_digest is not None or terminal_digest is not None:
                    raise ValueError(
                        "Command Context archive manifest is invalid."
                    )
            elif (
                not isinstance(source_workbench, dict)
                or not isinstance(reviewing_digest, str)
                or len(reviewing_digest) != 64
                or not isinstance(terminal_digest, str)
                or len(terminal_digest) != 64
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        _context_name_parts(context_name)
        with open(context_path, encoding="utf-8") as file:
            context_record = json.load(
                file,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        context = Context.from_dict(
            _validate_context_header(context_record, context_name)
        )
        if context.uid != context_uid:
            raise ValueError("Command Context archive identity is invalid.")
        entries: list[dict[str, object]] = []
        for path in checkpoints_path.iterdir():
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Command Context archive checkpoints are invalid.")
            with open(path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if not isinstance(value, dict):
                raise ValueError("Command Context archive checkpoint is invalid.")
            entries.append(value)
        if not any(entry.get("uid") == checkpoint_uid for entry in entries):
            raise ValueError("Command Context archive lost its source checkpoint.")
        return (
            archive,
            manifest,
            context,
            sorted(entries, key=lambda item: str(item.get("timestamp")), reverse=True),
        )

    def list_command_context_archives(
        self,
    ) -> tuple[tuple[Context, list[dict[str, object]]], ...]:
        """Return validated absent Context histories used by command Undo/Redo."""
        root = self.command_context_archives_dir
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Command Context archive storage is invalid.")
            return ()
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Command Context archive storage is invalid.")
        result: list[tuple[Context, list[dict[str, object]]]] = []
        for path in root.iterdir():
            if path.is_symlink() or not path.is_dir():
                raise ValueError("Command Context archive storage is invalid.")
            _archive, _manifest, context, entries = self._load_command_context_archive(
                path.name
            )
            result.append((context, entries))
        return tuple(sorted(result, key=lambda item: item[0].name))

    @staticmethod
    def _context_for_restoration(
        snapshot: dict[str, object],
        *,
        context_uid: str,
        context_name: str,
        expected_context_digest: str,
    ) -> Context:
        """Build one exact direct restore target under its current owner.

        Revert may select an inherited checkpoint whose serialized owner is a
        branch source, while Undo/Redo carries already-normalized command
        images. Both paths must preserve the live Context identity and attach
        the same compare-and-set digest before publishing through
        ``_save_locked``.
        """

        restored = Context.from_dict(
            {
                **snapshot,
                "uid": context_uid,
                "name": context_name,
            }
        )
        restored._store_digest = expected_context_digest
        return restored

    def restore_recent_context_command(
        self,
        direction: str,
        *,
        expected_unit_uid: str | None = None,
    ):
        """Undo or redo one globally ordered checkpoint-producing command.

        The command stack is reconstructed while the store-wide command lock
        is held, then every affected Context is freshness-checked and restored
        under one deterministic multi-lock boundary. This supplies exception
        atomicity for multi-Context Update commands; as elsewhere in this
        prototype, a machine crash can still interrupt several file replaces.
        """
        from memcommit.command_history import (
            CommandHistoryError,
            CommandRestoreResult,
            build_command_stacks,
            command_restore_metadata,
        )

        if direction not in {"undo", "redo"}:
            raise ValueError("Command restoration direction must be undo or redo.")
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            stacks = build_command_stacks(self)
            candidates = stacks.undo if direction == "undo" else stacks.redo
            if not candidates:
                raise CommandHistoryError(
                    f"There is no recorded Context command to {direction}."
                )
            unit = candidates[-1]
            if expected_unit_uid is not None and unit.uid != expected_unit_uid:
                # Granted recovery names one exact authority command from the
                # participant-side receipt. Never substitute a newer, unrelated
                # authority mutation merely because it is currently on top.
                raise CommandHistoryError(
                    "The recorded granted update is not the next Context "
                    f"command to {direction}."
                )
            if any(
                change.before is None or change.after is None for change in unit.changes
            ):
                return self._restore_context_creation_command_locked(
                    unit,
                    direction,
                )
            names = tuple(change.context_name for change in unit.changes)
            receipt_uid = str(uuid.uuid4())
            restore_metadata = command_restore_metadata(
                receipt_uid=receipt_uid,
                direction=direction,
                unit=unit,
            )
            original_records: dict[str, dict[str, object]] = {}
            created_checkpoints: list[tuple[str, Checkpoint]] = []
            written_names: list[str] = []
            artifact_restore: (
                tuple[Path, dict[str, object], dict[str, object]] | None
            ) = None
            artifact_written = False
            with self._context_graph_lock(exclusive=False):
                with self._context_write_locks(names):
                    for change in unit.changes:
                        try:
                            current = self.load_direct(change.context_name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' "
                                "no longer exists."
                            ) from error
                        expected = (
                            change.after if direction == "undo" else change.before
                        )
                        if current.uid != change.context_uid or context_record_digest(
                            current
                        ) != context_record_digest(expected):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' changed "
                                f"after the command selected for {direction}."
                            )
                        original_records[change.context_name] = current.to_dict()

                    artifact_restore = self._prepare_applied_artifact_restore(
                        unit,
                        direction,
                    )

                    try:
                        for change in unit.changes:
                            target_record = (
                                change.before if direction == "undo" else change.after
                            )
                            expected_digest = context_record_digest(
                                original_records[change.context_name]
                            )
                            restored = self._context_for_restoration(
                                target_record,
                                context_uid=change.context_uid,
                                context_name=change.context_name,
                                expected_context_digest=expected_digest,
                            )
                            checkpoint = self._save_locked(
                                restored,
                                AutoCheckpoint(
                                    command=direction,
                                    args={
                                        "command_restore": restore_metadata,
                                    },
                                    description=(
                                        f"{direction.title()} command "
                                        f"'mem {unit.command}' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=expected_digest,
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Command restoration created no checkpoint."
                                )
                            written_names.append(change.context_name)
                            created_checkpoints.append(
                                (change.context_name, checkpoint)
                            )
                        if artifact_restore is not None:
                            session_path, _session_before, session_after = (
                                artifact_restore
                            )
                            self._write_applied_artifact_restore(
                                session_path,
                                expected=_session_before,
                                value=session_after,
                            )
                            artifact_written = True
                    except Exception:
                        rollback_error: Exception | None = None
                        if artifact_written and artifact_restore is not None:
                            try:
                                session_path, session_before, _session_after = (
                                    artifact_restore
                                )
                                self._write_applied_artifact_restore(
                                    session_path,
                                    expected=_session_after,
                                    value=session_before,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name in written_names:
                            try:
                                _write_json_atomic(
                                    self._context_file(name),
                                    original_records[name],
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in created_checkpoints:
                            try:
                                removed = False
                                for path in self._checkpoints_dir(name).glob(
                                    f"*-{checkpoint.uid[:8]}.json"
                                ):
                                    if path.is_symlink() or not path.is_file():
                                        continue
                                    with open(path, encoding="utf-8") as file:
                                        value = json.load(
                                            file,
                                            object_pairs_hook=(
                                                _reject_duplicate_json_keys
                                            ),
                                        )
                                    if value.get("uid") == checkpoint.uid:
                                        path.unlink()
                                        removed = True
                                        break
                                if not removed:
                                    raise RuntimeError(
                                        "Restoration checkpoint could not be "
                                        "found during rollback."
                                    )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Command restoration failed and its Contexts "
                                "could not be fully rolled back."
                            ) from rollback_error
                        raise
            return CommandRestoreResult(
                unit=unit,
                direction=direction,
                receipt_uid=receipt_uid,
                checkpoints=tuple(checkpoint for _, checkpoint in created_checkpoints),
            )

    def _remove_checkpoint_uid_locked(self, name: str, checkpoint_uid: str) -> None:
        """Remove one exact provisional checkpoint while its Context is locked."""
        for path in self._checkpoints_dir(name).glob(f"*-{checkpoint_uid[:8]}.json"):
            if path.is_symlink() or not path.is_file():
                continue
            with open(path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if value.get("uid") == checkpoint_uid:
                path.unlink()
                return
        raise RuntimeError("Provisional restoration checkpoint is unavailable.")

    def _restore_context_creation_command_locked(self, unit, direction: str):
        """Restore one command unit that includes created Context lifecycles."""

        if unit.command == "branch":
            return self._restore_branch_context_creation_command_locked(
                unit,
                direction,
            )
        if unit.command == "merge":
            return self._restore_merge_context_creation_command_locked(
                unit,
                direction,
            )
        if unit.command == "sever":
            return self._restore_sever_context_creation_command_locked(
                unit,
                direction,
            )
        if unit.command == "atomize":
            return self._restore_atomize_context_creation_command_locked(
                unit,
                direction,
            )
        raise ValueError(
            f"Command '{unit.command}' has no Context-creation restoration."
        )

    def _restore_branch_context_creation_command_locked(
        self,
        unit,
        direction: Literal["undo", "redo"],
    ):
        """Undo or redo one exact Branch or complete lexical subtree.

        Undo moves the created Context records and their inherited histories
        into private command archives. Redo restores those exact identities;
        it must not synthesize a fresh Branch from a Source that may have
        changed since the original command.
        """

        from memcommit.command_history import (
            CommandHistoryError,
            CommandRestoreResult,
            branch_tree_receipt,
            command_restore_metadata,
        )

        if (
            unit.command != "branch"
            or not unit.changes
            or any(
                change.before is not None or change.after is None
                for change in unit.changes
            )
            or not unit.checkpoint_args
        ):
            raise ValueError(
                "Branch lifecycle restoration requires one complete creation unit."
            )
        try:
            receipts = tuple(
                branch_tree_receipt(args) for args in unit.checkpoint_args
            )
        except CommandHistoryError as error:
            raise ValueError(str(error)) from error
        receipt = receipts[0]
        if (
            any(candidate != receipt for candidate in receipts[1:])
            or unit.uid != f"branch:{receipt.operation_uid}"
            or {
                (change.context_uid, change.context_name)
                for change in unit.changes
            }
            != {
                (item.target_uid, item.target_name)
                for item in receipt.contexts
            }
        ):
            raise ValueError("Branch lifecycle receipts are inconsistent.")

        names = tuple(change.context_name for change in unit.changes)
        name_set = set(names)
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        checkpoints: list[Checkpoint] = []

        def move_record_and_history(
            source_context: Path,
            source_checkpoints: Path,
            target_context: Path,
            target_checkpoints: Path,
        ) -> None:
            """Move one lifecycle pair without leaving a half-moved Context."""

            source_context.rename(target_context)
            try:
                source_checkpoints.rename(target_checkpoints)
            except Exception as error:
                try:
                    target_context.rename(source_context)
                except Exception as rollback_error:
                    raise RuntimeError(
                        "A Branch Context record moved without its history and "
                        "could not be restored."
                    ) from rollback_error
                raise error

        with self._context_graph_lock(exclusive=True):
            with self._context_write_locks(names):
                if direction == "undo":
                    current_by_name: dict[str, Context] = {}
                    for change in unit.changes:
                        try:
                            current = self.load_direct(change.context_name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' "
                                "no longer exists."
                            ) from error
                        assert change.after is not None
                        if (
                            current.uid != change.context_uid
                            or context_record_digest(current)
                            != context_record_digest(change.after)
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' changed "
                                "after the Branch selected for undo."
                            )
                        self._assert_context_deletion_allowed(current)
                        current_by_name[change.context_name] = current

                    archives = {
                        change.context_name: self._command_context_archive_path(
                            change.checkpoint_uid
                        )
                        for change in unit.changes
                    }
                    root = self.command_context_archives_dir
                    if any(
                        archive.exists() or archive.is_symlink()
                        for archive in archives.values()
                    ):
                        raise ConcurrentContextUpdateError(
                            "A Branch command archive already exists."
                        )

                    saved: list[tuple[str, Checkpoint]] = []
                    moved: list[tuple[Any, Path, Path, Path]] = []
                    created_archives: list[Path] = []
                    undo_original_state: dict[str, object] | None = None
                    state_changed = False
                    try:
                        root.mkdir(parents=True, exist_ok=True, mode=0o700)
                        if root.is_symlink() or not root.is_dir():
                            raise ValueError(
                                "Command Context archive storage is invalid."
                            )
                        for change in unit.changes:
                            current = current_by_name[change.context_name]
                            checkpoint = self._save_locked(
                                current,
                                AutoCheckpoint(
                                    command="undo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Undo command 'mem branch' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(
                                    current
                                ),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Branch restoration created no Undo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            saved.append((change.context_name, checkpoint))
                            archive = archives[change.context_name]
                            archive.mkdir(mode=0o700)
                            created_archives.append(archive)
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(
                                change.context_name
                            )
                            archived_context = archive / "context.json"
                            archived_checkpoints = archive / "checkpoints"
                            move_record_and_history(
                                context_file,
                                checkpoints_dir,
                                archived_context,
                                archived_checkpoints,
                            )
                            moved.append(
                                (
                                    change,
                                    archive,
                                    archived_context,
                                    archived_checkpoints,
                                )
                            )
                            _write_json_atomic(
                                archive / "manifest.json",
                                {
                                    "version": 1,
                                    "command": "branch",
                                    "unit_uid": unit.uid,
                                    "context_uid": change.context_uid,
                                    "context_name": change.context_name,
                                    "checkpoint_uid": change.checkpoint_uid,
                                },
                            )
                        with self._state_write_lock():
                            state = self._read_state()
                            undo_original_state = dict(state)
                            if state.get("current") in name_set:
                                state["current"] = receipt.current_before
                                self._write_state(state)
                                state_changed = True
                    except Exception:
                        undo_rollback_error: Exception | None = None
                        if state_changed and undo_original_state is not None:
                            try:
                                with self._state_write_lock():
                                    self._write_state(undo_original_state)
                            except Exception as candidate:
                                undo_rollback_error = (
                                    undo_rollback_error or candidate
                                )
                        moved_names = {
                            change.context_name for change, *_rest in moved
                        }
                        for (
                            change,
                            archive,
                            archived_context,
                            archived_checkpoints,
                        ) in reversed(moved):
                            try:
                                move_record_and_history(
                                    archived_context,
                                    archived_checkpoints,
                                    self._context_file(change.context_name),
                                    self._checkpoints_dir(change.context_name),
                                )
                                checkpoint = next(
                                    candidate
                                    for name, candidate in saved
                                    if name == change.context_name
                                )
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                                manifest = archive / "manifest.json"
                                if manifest.exists() and not manifest.is_symlink():
                                    manifest.unlink()
                                archive.rmdir()
                            except Exception as candidate:
                                undo_rollback_error = (
                                    undo_rollback_error or candidate
                                )
                        for archive_path in reversed(created_archives):
                            if (
                                not archive_path.exists()
                                or archive_path.is_symlink()
                            ):
                                continue
                            try:
                                archive_path.rmdir()
                            except OSError:
                                # A nonempty archive belongs to a failed
                                # rollback already reported above.
                                pass
                        for name, checkpoint in reversed(saved):
                            if name in moved_names:
                                continue
                            try:
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                undo_rollback_error = (
                                    undo_rollback_error or candidate
                                )
                        try:
                            root.rmdir()
                        except OSError:
                            pass
                        if undo_rollback_error is not None:
                            raise RuntimeError(
                                "Branch Undo failed and its Context tree could "
                                "not be fully rolled back."
                            ) from undo_rollback_error
                        raise
                else:
                    archived: dict[
                        str,
                        tuple[Path, dict[str, object], Context],
                    ] = {}
                    for change in unit.changes:
                        if self.context_exists(change.context_name):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' already "
                                "exists."
                            )
                        archive_path, archive_manifest, archived_record, _entries = (
                            self._load_command_context_archive(
                                change.checkpoint_uid
                            )
                        )
                        assert change.after is not None
                        if (
                            archive_manifest.get("command") != "branch"
                            or archive_manifest.get("unit_uid") != unit.uid
                            or archived_record.uid != change.context_uid
                            or archived_record.name != change.context_name
                            or context_record_digest(archived_record)
                            != context_record_digest(change.after)
                        ):
                            raise ConcurrentContextUpdateError(
                                "The archived Branch result changed before Redo."
                            )
                        self._assert_context_storage_available(change.context_name)
                        archived[change.context_name] = (
                            archive_path,
                            archive_manifest,
                            archived_record,
                        )

                    activated: list[tuple[Any, Path, Path, Path]] = []
                    redone: list[
                        tuple[Any, Path, Path, Path, Checkpoint]
                    ] = []
                    redo_original_state: dict[str, object] | None = None
                    state_changed = False
                    try:
                        for change in unit.changes:
                            archive, _manifest, context = archived[
                                change.context_name
                            ]
                            self._context_dir(change.context_name).mkdir(
                                parents=True,
                                exist_ok=True,
                            )
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(
                                change.context_name
                            )
                            archived_context = archive / "context.json"
                            archived_checkpoints = archive / "checkpoints"
                            move_record_and_history(
                                archived_context,
                                archived_checkpoints,
                                context_file,
                                checkpoints_dir,
                            )
                            activated.append(
                                (
                                    change,
                                    archive,
                                    archived_context,
                                    archived_checkpoints,
                                )
                            )
                            checkpoint = self._save_locked(
                                context,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Redo command 'mem branch' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(
                                    context
                                ),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Branch restoration created no Redo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            redone.append(
                                (
                                    change,
                                    archive,
                                    archived_context,
                                    archived_checkpoints,
                                    checkpoint,
                                )
                            )
                        with self._state_write_lock():
                            state = self._read_state()
                            redo_original_state = dict(state)
                            if state.get("current") == receipt.current_before:
                                state["current"] = receipt.target_root
                                self._write_state(state)
                                state_changed = True
                    except Exception:
                        redo_rollback_error: Exception | None = None
                        if state_changed and redo_original_state is not None:
                            try:
                                with self._state_write_lock():
                                    self._write_state(redo_original_state)
                            except Exception as candidate:
                                redo_rollback_error = (
                                    redo_rollback_error or candidate
                                )
                        redone_names = {
                            change.context_name for change, *_rest in redone
                        }
                        for (
                            change,
                            _archive,
                            archived_context,
                            archived_checkpoints,
                            checkpoint,
                        ) in reversed(redone):
                            try:
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                                move_record_and_history(
                                    self._context_file(change.context_name),
                                    self._checkpoints_dir(change.context_name),
                                    archived_context,
                                    archived_checkpoints,
                                )
                            except Exception as candidate:
                                redo_rollback_error = (
                                    redo_rollback_error or candidate
                                )
                        for (
                            change,
                            _archive,
                            archived_context,
                            archived_checkpoints,
                        ) in reversed(activated):
                            if change.context_name in redone_names:
                                continue
                            try:
                                move_record_and_history(
                                    self._context_file(change.context_name),
                                    self._checkpoints_dir(change.context_name),
                                    archived_context,
                                    archived_checkpoints,
                                )
                            except Exception as candidate:
                                redo_rollback_error = (
                                    redo_rollback_error or candidate
                                )
                        if redo_rollback_error is not None:
                            raise RuntimeError(
                                "Branch Redo failed and its Context tree could "
                                "not be fully rolled back."
                            ) from redo_rollback_error
                        raise
                    for change, archive, *_rest in redone:
                        manifest = archive / "manifest.json"
                        manifest.unlink()
                        archive.rmdir()
                    try:
                        self.command_context_archives_dir.rmdir()
                    except OSError:
                        pass

        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=tuple(checkpoints),
        )

    def _restore_merge_context_creation_command_locked(self, unit, direction: str):
        """Atomically restore a Merge across updated and created Contexts.

        Created descendants move into the same private, validated lifecycle
        archive used by command history. Updated Contexts are restored in
        place. Every member receives the same restoration receipt, so neither
        a partial tree nor an incomplete redo can enter the global stack.
        """
        from memcommit.command_history import (
            CommandRestoreResult,
            command_restore_metadata,
        )

        if (
            unit.command != "merge"
            or not unit.changes
            or any(change.after is None for change in unit.changes)
            or not any(change.before is None for change in unit.changes)
        ):
            raise ValueError(
                "Merge lifecycle restoration requires one complete mixed command unit."
            )
        names = tuple(change.context_name for change in unit.changes)
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        created_changes = tuple(
            change for change in unit.changes if change.before is None
        )
        updated_changes = tuple(
            change for change in unit.changes if change.before is not None
        )
        checkpoints: list[Checkpoint] = []

        with self._context_graph_lock(exclusive=True):
            with self._context_write_locks(names):
                if direction == "undo":
                    current_by_name: dict[str, Context] = {}
                    original_bytes: dict[str, bytes] = {}
                    for change in unit.changes:
                        try:
                            current = self.load_direct(change.context_name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' "
                                "no longer exists."
                            ) from error
                        assert change.after is not None
                        if (
                            current.uid != change.context_uid
                            or context_record_digest(current)
                            != context_record_digest(change.after)
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' changed "
                                "after the Merge selected for undo."
                            )
                        if change.before is None:
                            self._assert_context_deletion_allowed(current)
                        current_by_name[change.context_name] = current
                        original_bytes[change.context_name] = self._context_file(
                            change.context_name
                        ).read_bytes()

                    updated_written: list[tuple[str, Checkpoint]] = []
                    created_saved: list[tuple[str, Checkpoint]] = []
                    moved: list[tuple[object, object, object, object]] = []
                    try:
                        for change in updated_changes:
                            assert change.before is not None
                            current = current_by_name[change.context_name]
                            expected_digest = context_record_digest(current)
                            restored = self._context_for_restoration(
                                change.before,
                                context_uid=change.context_uid,
                                context_name=change.context_name,
                                expected_context_digest=expected_digest,
                            )
                            checkpoint = self._save_locked(
                                restored,
                                AutoCheckpoint(
                                    command="undo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Undo command 'mem merge' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=expected_digest,
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Undo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            updated_written.append((change.context_name, checkpoint))

                        for change in created_changes:
                            current = current_by_name[change.context_name]
                            checkpoint = self._save_locked(
                                current,
                                AutoCheckpoint(
                                    command="undo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Undo command 'mem merge' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(current),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Undo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            created_saved.append((change.context_name, checkpoint))
                            archive = self._command_context_archive_path(
                                change.checkpoint_uid
                            )
                            root = archive.parent
                            root.mkdir(parents=True, exist_ok=True, mode=0o700)
                            if root.is_symlink() or not root.is_dir():
                                raise ValueError(
                                    "Command Context archive storage is invalid."
                                )
                            if archive.exists() or archive.is_symlink():
                                raise ConcurrentContextUpdateError(
                                    "A Merge command archive already exists."
                                )
                            archive.mkdir(mode=0o700)
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(
                                change.context_name
                            )
                            archived_context = archive / "context.json"
                            archived_checkpoints = archive / "checkpoints"
                            context_file.rename(archived_context)
                            checkpoints_dir.rename(archived_checkpoints)
                            moved.append(
                                (
                                    change,
                                    archive,
                                    archived_context,
                                    archived_checkpoints,
                                )
                            )
                            _write_json_atomic(
                                archive / "manifest.json",
                                {
                                    "version": 1,
                                    "command": "merge",
                                    "unit_uid": unit.uid,
                                    "context_uid": change.context_uid,
                                    "context_name": change.context_name,
                                    "checkpoint_uid": change.checkpoint_uid,
                                },
                            )
                    except Exception:
                        rollback_error: Exception | None = None
                        moved_names = {
                            change.context_name for change, *_rest in moved
                        }
                        for change, archive, archived_context, archived_checkpoints in reversed(
                            moved
                        ):
                            try:
                                archived_checkpoints.rename(
                                    self._checkpoints_dir(change.context_name)
                                )
                                archived_context.rename(
                                    self._context_file(change.context_name)
                                )
                                checkpoint = next(
                                    checkpoint
                                    for name, checkpoint in created_saved
                                    if name == change.context_name
                                )
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                                manifest = archive / "manifest.json"
                                if manifest.exists() and not manifest.is_symlink():
                                    manifest.unlink()
                                archive.rmdir()
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in reversed(created_saved):
                            if name in moved_names:
                                continue
                            try:
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in reversed(updated_written):
                            try:
                                _write_bytes_atomic(
                                    self._context_file(name),
                                    original_bytes[name],
                                )
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Merge Undo failed and its Context tree could not "
                                "be fully rolled back."
                            ) from rollback_error
                        raise
                else:
                    current_by_name: dict[str, Context] = {}
                    original_bytes: dict[str, bytes] = {}
                    archives: dict[str, tuple[object, object, Context]] = {}
                    for change in updated_changes:
                        assert change.before is not None
                        try:
                            current = self.load_direct(change.context_name)
                        except FileNotFoundError as error:
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' "
                                "no longer exists."
                            ) from error
                        if (
                            current.uid != change.context_uid
                            or context_record_digest(current)
                            != context_record_digest(change.before)
                        ):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' changed "
                                "after the Merge selected for redo."
                            )
                        current_by_name[change.context_name] = current
                        original_bytes[change.context_name] = self._context_file(
                            change.context_name
                        ).read_bytes()
                    for change in created_changes:
                        if self.context_exists(change.context_name):
                            raise ConcurrentContextUpdateError(
                                f"Affected Context '{change.context_name}' already exists."
                            )
                        archive, manifest, archived, _entries = (
                            self._load_command_context_archive(change.checkpoint_uid)
                        )
                        assert change.after is not None
                        if (
                            manifest.get("command") != "merge"
                            or manifest.get("unit_uid") != unit.uid
                            or archived.uid != change.context_uid
                            or archived.name != change.context_name
                            or context_record_digest(archived)
                            != context_record_digest(change.after)
                        ):
                            raise ConcurrentContextUpdateError(
                                "The archived Merge result changed before Redo."
                            )
                        archives[change.context_name] = (
                            archive,
                            manifest,
                            archived,
                        )

                    updated_written: list[tuple[str, Checkpoint]] = []
                    activated: list[tuple[object, object, object, object]] = []
                    moved: list[tuple[object, object, object, object, Checkpoint]] = []
                    try:
                        for change in updated_changes:
                            assert change.after is not None
                            current = current_by_name[change.context_name]
                            expected_digest = context_record_digest(current)
                            restored = self._context_for_restoration(
                                change.after,
                                context_uid=change.context_uid,
                                context_name=change.context_name,
                                expected_context_digest=expected_digest,
                            )
                            checkpoint = self._save_locked(
                                restored,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Redo command 'mem merge' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=expected_digest,
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Redo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            updated_written.append((change.context_name, checkpoint))

                        for change in created_changes:
                            archive, _manifest, archived = archives[
                                change.context_name
                            ]
                            self._assert_context_storage_available(change.context_name)
                            self._context_dir(change.context_name).mkdir(
                                parents=True,
                                exist_ok=True,
                            )
                            context_file = self._context_file(change.context_name)
                            checkpoints_dir = self._checkpoints_dir(
                                change.context_name
                            )
                            archived_context = archive / "context.json"
                            archived_checkpoints = archive / "checkpoints"
                            archived_context.rename(context_file)
                            archived_checkpoints.rename(checkpoints_dir)
                            activated.append(
                                (
                                    change,
                                    archive,
                                    archived_context,
                                    archived_checkpoints,
                                )
                            )
                            checkpoint = self._save_locked(
                                archived,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Redo command 'mem merge' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(archived),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Merge restoration created no Redo checkpoint."
                                )
                            checkpoints.append(checkpoint)
                            moved.append(
                                (
                                    change,
                                    archive,
                                    archived_context,
                                    archived_checkpoints,
                                    checkpoint,
                                )
                            )
                    except Exception:
                        rollback_error: Exception | None = None
                        moved_names = {
                            change.context_name for change, *_rest in moved
                        }
                        for change, archive, archived_context, archived_checkpoints, checkpoint in reversed(
                            moved
                        ):
                            try:
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                                self._checkpoints_dir(change.context_name).rename(
                                    archived_checkpoints
                                )
                                self._context_file(change.context_name).rename(
                                    archived_context
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for change, archive, archived_context, archived_checkpoints in reversed(
                            activated
                        ):
                            if change.context_name in moved_names:
                                continue
                            try:
                                self._checkpoints_dir(change.context_name).rename(
                                    archived_checkpoints
                                )
                                self._context_file(change.context_name).rename(
                                    archived_context
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for name, checkpoint in reversed(updated_written):
                            try:
                                _write_bytes_atomic(
                                    self._context_file(name),
                                    original_bytes[name],
                                )
                                self._remove_checkpoint_uid_locked(
                                    name,
                                    checkpoint.uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Merge Redo failed and its Context tree could not "
                                "be fully rolled back."
                            ) from rollback_error
                        raise
                    for change, archive, *_rest in moved:
                        manifest = archive / "manifest.json"
                        manifest.unlink()
                        archive.rmdir()
                    try:
                        self.command_context_archives_dir.rmdir()
                    except OSError:
                        pass

        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=tuple(checkpoints),
        )

    def _restore_atomize_context_creation_command_locked(self, unit, direction: str):
        """Undo/Redo one final Atomize Save As output and its Source receipt."""

        from memcommit.atomize import AtomizeAnalysisSession
        from memcommit.atomize_workbench import atomize_workbench_record_digest
        from memcommit.command_history import (
            CommandRestoreResult,
            command_restore_metadata,
        )

        if (
            unit.command != "atomize"
            or len(unit.changes) != 1
            or unit.changes[0].before is not None
            or unit.changes[0].after is None
        ):
            raise ValueError(
                "Only an exact Atomize Save As creation can use lifecycle "
                "restoration."
            )
        change = unit.changes[0]
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        checkpoint: Checkpoint | None = None

        def load_creation_receipt(
            entries: Iterable[dict[str, object]],
        ) -> tuple[dict[str, object], dict[str, object]]:
            source_checkpoint = next(
                (
                    entry
                    for entry in entries
                    if entry.get("uid") == change.checkpoint_uid
                ),
                None,
            )
            args = (
                source_checkpoint.get("args")
                if isinstance(source_checkpoint, dict)
                else None
            )
            creation = args.get("context_creation") if isinstance(args, dict) else None
            save_as = args.get("atomize_save_as") if isinstance(args, dict) else None
            if (
                creation
                != {
                    "version": 1,
                    "context_uid": change.context_uid,
                    "context_name": change.context_name,
                }
                or not isinstance(save_as, dict)
                or set(save_as)
                != {
                    "version",
                    "source_context",
                    "source_frame",
                    "source_frame_digest",
                    "source_analysis_uid",
                    "source_workbench",
                    "current_before",
                }
                or save_as.get("version") != 1
            ):
                raise ValueError(
                    "Atomize checkpoint has no valid Save As creation receipt."
                )
            return args, save_as

        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(change.context_name):
                if direction == "undo":
                    try:
                        current = self.load_direct(change.context_name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' no "
                            "longer exists."
                        ) from error
                    if current.uid != change.context_uid or context_record_digest(
                        current
                    ) != context_record_digest(change.after):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' changed "
                            "after the Atomize Save As selected for undo."
                        )
                    self._assert_context_deletion_allowed(current)
                    entries = self.list_checkpoints(change.context_name)
                    args, save_as = load_creation_receipt(entries)
                    source_record = save_as.get("source_context")
                    if (
                        not isinstance(source_record, dict)
                        or set(source_record) != {"uid", "name", "digest"}
                    ):
                        raise ValueError(
                            "Atomize Save As Source receipt is invalid."
                        )
                    source_uid = source_record.get("uid")
                    source_name = source_record.get("name")
                    analysis_uid = save_as.get("source_analysis_uid")
                    current_before = save_as.get("current_before")
                    if (
                        not isinstance(source_uid, str)
                        or not isinstance(source_name, str)
                        or not isinstance(analysis_uid, str)
                        or (
                            current_before is not None
                            and not isinstance(current_before, str)
                        )
                    ):
                        raise ValueError(
                            "Atomize Save As Source receipt is invalid."
                        )
                    with ExitStack() as session_locks:
                        for context_uid in sorted({source_uid, change.context_uid}):
                            session_locks.enter_context(
                                self._atomize_session_write_lock(context_uid)
                            )
                        source_analysis = self.load_atomize_analysis(source_uid)
                        output_analysis = self.load_atomize_analysis(
                            change.context_uid
                        )
                        if (
                            source_analysis is None
                            or output_analysis is None
                            or source_analysis.uid != analysis_uid
                            or output_analysis.uid != analysis_uid
                            or output_analysis.context_uid != change.context_uid
                            or output_analysis.context_name != change.context_name
                            or args.get("analysis_uid") != analysis_uid
                        ):
                            raise ValueError(
                                "Atomize analyses do not match the restored "
                                "Save As command."
                            )
                        source_workbench_record = save_as.get("source_workbench")
                        terminal = self.load_atomize_workbench(source_analysis)
                        reviewing = None
                        reviewing_digest = None
                        terminal_digest = None
                        if source_workbench_record is None:
                            if terminal is not None:
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Undo."
                                )
                        else:
                            if (
                                not isinstance(source_workbench_record, dict)
                                or set(source_workbench_record)
                                != {"uid", "output_context_name", "record_digest"}
                                or terminal is None
                                or terminal.uid
                                != source_workbench_record.get("uid")
                            ):
                                raise ValueError(
                                    "Atomize Source workbench receipt is invalid."
                                )
                            terminal_digest = atomize_workbench_record_digest(terminal)
                            reviewing = copy.deepcopy(terminal)
                            reviewing.clear_application(
                                output_context_name=change.context_name,
                                checkpoint_uid=change.checkpoint_uid,
                                restore_output_context_name=(
                                    source_workbench_record.get(
                                        "output_context_name"
                                    )
                                ),
                            )
                            reviewing_digest = atomize_workbench_record_digest(
                                reviewing
                            )
                            if reviewing_digest != source_workbench_record.get(
                                "record_digest"
                            ):
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Undo."
                                )

                        checkpoint = self._save_locked(
                            current,
                            AutoCheckpoint(
                                command="undo",
                                args={"command_restore": restore_metadata},
                                description=(
                                    "Undo command 'mem atomize' "
                                    f"[{receipt_uid[:8]}]"
                                ),
                            ),
                            expected_context_digest=context_record_digest(current),
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Atomize restoration created no Undo checkpoint."
                            )
                        archive = self._command_context_archive_path(
                            change.checkpoint_uid
                        )
                        root = archive.parent
                        root.mkdir(parents=True, exist_ok=True, mode=0o700)
                        if root.is_symlink() or not root.is_dir():
                            raise ValueError(
                                "Command Context archive storage is invalid."
                            )
                        if archive.exists() or archive.is_symlink():
                            raise ConcurrentContextUpdateError(
                                "An Atomize command archive already exists."
                            )
                        archive.mkdir(mode=0o700)
                        context_file = self._context_file(change.context_name)
                        checkpoints_dir = self._checkpoints_dir(change.context_name)
                        analysis_path = self._atomize_analysis_path(
                            change.context_uid
                        )
                        archived_context = archive / "context.json"
                        archived_checkpoints = archive / "checkpoints"
                        archived_analysis = archive / "atomize-analysis.json"
                        moved = False
                        workbench_saved = False
                        original_state: dict[str, object] | None = None
                        state_changed = False
                        try:
                            context_file.rename(archived_context)
                            checkpoints_dir.rename(archived_checkpoints)
                            analysis_path.rename(archived_analysis)
                            moved = True
                            _write_json_atomic(
                                archive / "manifest.json",
                                {
                                    "version": 1,
                                    "command": "atomize",
                                    "unit_uid": unit.uid,
                                    "context_uid": change.context_uid,
                                    "context_name": change.context_name,
                                    "checkpoint_uid": change.checkpoint_uid,
                                    "analysis_uid": analysis_uid,
                                    "source_context_uid": source_uid,
                                    "source_context_name": source_name,
                                    "source_workbench": source_workbench_record,
                                    "reviewing_workbench_digest": reviewing_digest,
                                    "terminal_workbench_digest": terminal_digest,
                                    "current_before": current_before,
                                },
                            )
                            if reviewing is not None:
                                self._save_atomize_workbench_locked(reviewing)
                                workbench_saved = True
                            with self._state_write_lock():
                                state = self._read_state()
                                original_state = dict(state)
                                if state.get("current") == change.context_name:
                                    state["current"] = current_before
                                    self._write_state(state)
                                    state_changed = True
                        except Exception:
                            if state_changed and original_state is not None:
                                with self._state_write_lock():
                                    self._write_state(original_state)
                            if workbench_saved and terminal is not None:
                                self._save_atomize_workbench_locked(terminal)
                            if moved:
                                archived_analysis.rename(analysis_path)
                                archived_checkpoints.rename(checkpoints_dir)
                                archived_context.rename(context_file)
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                            manifest_path = archive / "manifest.json"
                            if (
                                manifest_path.exists()
                                and not manifest_path.is_symlink()
                            ):
                                manifest_path.unlink()
                            try:
                                archive.rmdir()
                                root.rmdir()
                            except OSError:
                                pass
                            raise
                else:
                    if self.context_exists(change.context_name):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' already "
                            "exists."
                        )
                    archive, manifest, archived_context, entries = (
                        self._load_command_context_archive(change.checkpoint_uid)
                    )
                    _args, save_as = load_creation_receipt(entries)
                    if (
                        manifest.get("command") != "atomize"
                        or manifest.get("unit_uid") != unit.uid
                        or archived_context.uid != change.context_uid
                        or archived_context.name != change.context_name
                        or context_record_digest(archived_context)
                        != context_record_digest(change.after)
                    ):
                        raise ConcurrentContextUpdateError(
                            "The archived Atomize result changed before Redo."
                        )
                    source_uid = manifest.get("source_context_uid")
                    analysis_uid = manifest.get("analysis_uid")
                    assert isinstance(source_uid, str)
                    assert isinstance(analysis_uid, str)
                    with ExitStack() as session_locks:
                        for context_uid in sorted({source_uid, change.context_uid}):
                            session_locks.enter_context(
                                self._atomize_session_write_lock(context_uid)
                            )
                        source_analysis = self.load_atomize_analysis(source_uid)
                        if (
                            source_analysis is None
                            or source_analysis.uid != analysis_uid
                        ):
                            raise ConcurrentContextUpdateError(
                                "The Source Atomize analysis changed before Redo."
                            )
                        source_workbench_record = manifest.get("source_workbench")
                        reviewing = self.load_atomize_workbench(source_analysis)
                        terminal = None
                        if source_workbench_record is None:
                            if reviewing is not None:
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Redo."
                                )
                        else:
                            if (
                                reviewing is None
                                or atomize_workbench_record_digest(reviewing)
                                != manifest.get("reviewing_workbench_digest")
                            ):
                                raise ConcurrentContextUpdateError(
                                    "The Source Atomize workbench changed before Redo."
                                )
                            terminal = copy.deepcopy(reviewing)
                            terminal.output_context_name = change.context_name
                            terminal.record_application(
                                output_context_name=change.context_name,
                                checkpoint_uid=change.checkpoint_uid,
                            )
                            if atomize_workbench_record_digest(
                                terminal
                            ) != manifest.get("terminal_workbench_digest"):
                                raise ConcurrentContextUpdateError(
                                    "The terminal Atomize workbench changed "
                                    "before Redo."
                                )
                        archived_analysis = archive / "atomize-analysis.json"
                        if (
                            archived_analysis.is_symlink()
                            or not archived_analysis.is_file()
                        ):
                            raise ValueError(
                                "Archived Atomize analysis is invalid."
                            )
                        with open(archived_analysis, encoding="utf-8") as file:
                            output_analysis = AtomizeAnalysisSession.from_dict(
                                json.load(
                                    file,
                                    object_pairs_hook=_reject_duplicate_json_keys,
                                )
                            )
                        if (
                            output_analysis.uid != analysis_uid
                            or output_analysis.context_uid != change.context_uid
                            or output_analysis.context_name != change.context_name
                        ):
                            raise ValueError(
                                "Archived Atomize analysis identity is invalid."
                            )
                        self._assert_context_storage_available(change.context_name)
                        context_dir = self._context_dir(change.context_name)
                        context_dir.mkdir(parents=True, exist_ok=True)
                        context_file = self._context_file(change.context_name)
                        checkpoints_dir = self._checkpoints_dir(change.context_name)
                        analysis_path = self._atomize_analysis_path(
                            change.context_uid
                        )
                        archived_context_file = archive / "context.json"
                        archived_checkpoints = archive / "checkpoints"
                        moved = False
                        workbench_saved = False
                        original_state: dict[str, object] | None = None
                        state_changed = False
                        try:
                            archived_context_file.rename(context_file)
                            archived_checkpoints.rename(checkpoints_dir)
                            archived_analysis.rename(analysis_path)
                            moved = True
                            checkpoint = self._save_locked(
                                archived_context,
                                AutoCheckpoint(
                                    command="redo",
                                    args={"command_restore": restore_metadata},
                                    description=(
                                        "Redo command 'mem atomize' "
                                        f"[{receipt_uid[:8]}]"
                                    ),
                                ),
                                expected_context_digest=context_record_digest(
                                    archived_context
                                ),
                            )
                            if checkpoint is None:
                                raise RuntimeError(
                                    "Atomize restoration created no Redo checkpoint."
                                )
                            if terminal is not None:
                                self._save_atomize_workbench_locked(terminal)
                                workbench_saved = True
                            with self._state_write_lock():
                                state = self._read_state()
                                original_state = dict(state)
                                if state.get("current") == manifest.get(
                                    "current_before"
                                ):
                                    state["current"] = change.context_name
                                    self._write_state(state)
                                    state_changed = True
                        except Exception:
                            if state_changed and original_state is not None:
                                with self._state_write_lock():
                                    self._write_state(original_state)
                            if workbench_saved and reviewing is not None:
                                self._save_atomize_workbench_locked(reviewing)
                            if moved:
                                if checkpoint is not None:
                                    self._remove_checkpoint_uid_locked(
                                        change.context_name,
                                        checkpoint.uid,
                                    )
                                analysis_path.rename(archived_analysis)
                                checkpoints_dir.rename(archived_checkpoints)
                                context_file.rename(archived_context_file)
                            raise
                    manifest_path = archive / "manifest.json"
                    manifest_path.unlink()
                    archive.rmdir()
                    try:
                        archive.parent.rmdir()
                    except OSError:
                        pass
        assert checkpoint is not None
        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=(checkpoint,),
        )

    def _restore_sever_context_creation_command_locked(self, unit, direction: str):
        """Undo/Redo one Sever output creation and its saved review.

        Undo moves the complete Context record and checkpoint directory into a
        private command archive instead of destroying them. Redo can therefore
        restore the same identity and history, including every restoration
        receipt, without copying Memory text into lifecycle metadata.
        """
        from memcommit.command_history import (
            CommandRestoreResult,
            command_restore_metadata,
        )
        from memcommit.sever import SeverApplication, sever_record_digest
        from memcommit.sever_store import SeverSessionStore

        if (
            unit.command != "sever"
            or len(unit.changes) != 1
            or unit.changes[0].before is not None
            or unit.changes[0].after is None
        ):
            raise ValueError(
                "Only an exact Sever Context creation can use lifecycle restoration."
            )
        change = unit.changes[0]
        receipt_uid = str(uuid.uuid4())
        restore_metadata = command_restore_metadata(
            receipt_uid=receipt_uid,
            direction=direction,
            unit=unit,
        )
        sessions = SeverSessionStore(self)
        checkpoint: Checkpoint | None = None

        with self._context_graph_lock(exclusive=False):
            with self._context_write_lock(change.context_name):
                if direction == "undo":
                    try:
                        current = self.load_direct(change.context_name)
                    except FileNotFoundError as error:
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' no longer exists."
                        ) from error
                    if current.uid != change.context_uid or context_record_digest(
                        current
                    ) != context_record_digest(change.after):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' changed "
                            "after the command selected for undo."
                        )
                    self._assert_context_deletion_allowed(current)
                    source_checkpoint = next(
                        (
                            entry
                            for entry in self.list_checkpoints(change.context_name)
                            if entry.get("uid") == change.checkpoint_uid
                        ),
                        None,
                    )
                    args = (
                        source_checkpoint.get("args")
                        if isinstance(source_checkpoint, dict)
                        else None
                    )
                    sever_receipt = (
                        args.get("sever") if isinstance(args, dict) else None
                    )
                    session_uid = (
                        sever_receipt.get("session_uid")
                        if isinstance(sever_receipt, dict)
                        else None
                    )
                    if not isinstance(session_uid, str) or not session_uid:
                        raise ValueError(
                            "Sever checkpoint has no valid session receipt."
                        )
                    session = sessions.load(session_uid)
                    application = session.application
                    if (
                        session.state != "APPLIED"
                        or application is None
                        or session.output_name != change.context_name
                        or application.output_context_uid != change.context_uid
                        or application.checkpoint_uid != change.checkpoint_uid
                        or tuple(current.memories) != application.result_memory_uids
                    ):
                        raise ValueError(
                            "Sever session does not match the restored command."
                        )
                    reviewing = session.clear_application(
                        output_context_uid=change.context_uid,
                        checkpoint_uid=change.checkpoint_uid,
                    )
                    session_before_digest = sever_record_digest(session)
                    reviewing_digest = sever_record_digest(reviewing)
                    checkpoint = self._save_locked(
                        current,
                        AutoCheckpoint(
                            command="undo",
                            args={"command_restore": restore_metadata},
                            description=(
                                "Undo command 'mem sever' " f"[{receipt_uid[:8]}]"
                            ),
                        ),
                        expected_context_digest=context_record_digest(current),
                    )
                    if checkpoint is None:
                        raise RuntimeError(
                            "Sever restoration created no Undo checkpoint."
                        )
                    archive = self._command_context_archive_path(change.checkpoint_uid)
                    root = archive.parent
                    root.mkdir(parents=True, exist_ok=True, mode=0o700)
                    if root.is_symlink() or not root.is_dir():
                        raise ValueError("Command Context archive storage is invalid.")
                    if archive.exists() or archive.is_symlink():
                        raise ConcurrentContextUpdateError(
                            "A Sever command archive already exists."
                        )
                    archive.mkdir(mode=0o700)
                    context_file = self._context_file(change.context_name)
                    checkpoints_dir = self._checkpoints_dir(change.context_name)
                    archived_context = archive / "context.json"
                    archived_checkpoints = archive / "checkpoints"
                    moved = False
                    session_saved = False
                    try:
                        context_file.rename(archived_context)
                        checkpoints_dir.rename(archived_checkpoints)
                        moved = True
                        _write_json_atomic(
                            archive / "manifest.json",
                            {
                                "version": 1,
                                "command": "sever",
                                "unit_uid": unit.uid,
                                "context_uid": change.context_uid,
                                "context_name": change.context_name,
                                "checkpoint_uid": change.checkpoint_uid,
                                "session_uid": session.uid,
                                "application": application.to_dict(),
                                "reviewing_session_digest": reviewing_digest,
                            },
                        )
                        sessions.save(
                            reviewing,
                            expected_digest=session_before_digest,
                        )
                        session_saved = True
                        with self._state_write_lock():
                            state = self._read_state()
                            if state.get("current") == change.context_name:
                                state["current"] = None
                                self._write_state(state)
                    except Exception:
                        if session_saved:
                            sessions.save(
                                session,
                                expected_digest=reviewing_digest,
                            )
                        if moved:
                            archived_checkpoints.rename(checkpoints_dir)
                            archived_context.rename(context_file)
                            self._remove_checkpoint_uid_locked(
                                change.context_name,
                                checkpoint.uid,
                            )
                        manifest_path = archive / "manifest.json"
                        if manifest_path.exists() and not manifest_path.is_symlink():
                            manifest_path.unlink()
                        try:
                            archive.rmdir()
                            root.rmdir()
                        except OSError:
                            pass
                        raise
                else:
                    if self.context_exists(change.context_name):
                        raise ConcurrentContextUpdateError(
                            f"Affected Context '{change.context_name}' already exists."
                        )
                    archive, manifest, archived_context, _entries = (
                        self._load_command_context_archive(change.checkpoint_uid)
                    )
                    if (
                        archived_context.uid != change.context_uid
                        or archived_context.name != change.context_name
                        or context_record_digest(archived_context)
                        != context_record_digest(change.after)
                    ):
                        raise ConcurrentContextUpdateError(
                            "The archived Sever result changed before Redo."
                        )
                    session_uid = manifest["session_uid"]
                    assert isinstance(session_uid, str)
                    session = sessions.load(session_uid)
                    if (
                        sever_record_digest(session)
                        != manifest["reviewing_session_digest"]
                    ):
                        raise ConcurrentContextUpdateError(
                            "The Sever session changed before Redo."
                        )
                    application = SeverApplication.from_dict(manifest["application"])
                    applied = session.with_application(application)
                    session_before_digest = sever_record_digest(session)
                    self._assert_context_storage_available(change.context_name)
                    context_dir = self._context_dir(change.context_name)
                    context_dir.mkdir(parents=True, exist_ok=True)
                    context_file = self._context_file(change.context_name)
                    checkpoints_dir = self._checkpoints_dir(change.context_name)
                    archived_context_file = archive / "context.json"
                    archived_checkpoints = archive / "checkpoints"
                    moved = False
                    try:
                        archived_context_file.rename(context_file)
                        archived_checkpoints.rename(checkpoints_dir)
                        moved = True
                        checkpoint = self._save_locked(
                            archived_context,
                            AutoCheckpoint(
                                command="redo",
                                args={"command_restore": restore_metadata},
                                description=(
                                    "Redo command 'mem sever' " f"[{receipt_uid[:8]}]"
                                ),
                            ),
                            expected_context_digest=context_record_digest(
                                archived_context
                            ),
                        )
                        if checkpoint is None:
                            raise RuntimeError(
                                "Sever restoration created no Redo checkpoint."
                            )
                        sessions.save(
                            applied,
                            expected_digest=session_before_digest,
                        )
                    except Exception:
                        if moved:
                            if checkpoint is not None:
                                self._remove_checkpoint_uid_locked(
                                    change.context_name,
                                    checkpoint.uid,
                                )
                            checkpoints_dir.rename(archived_checkpoints)
                            context_file.rename(archived_context_file)
                        raise
                    manifest_path = archive / "manifest.json"
                    manifest_path.unlink()
                    archive.rmdir()
                    try:
                        archive.parent.rmdir()
                    except OSError:
                        pass
        assert checkpoint is not None
        return CommandRestoreResult(
            unit=unit,
            direction=direction,
            receipt_uid=receipt_uid,
            checkpoints=(checkpoint,),
        )

    def _prepare_applied_artifact_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare a saved semantic artifact coupled to one Context command."""
        if unit.command == "meld":
            return self._prepare_meld_command_restore(unit, direction)
        if unit.command == "sever":
            return self._prepare_sever_command_restore(unit, direction)
        if unit.command == "atomize-grounding":
            return self._prepare_atomize_grounding_command_restore(unit, direction)
        if unit.command == "update":
            return self._prepare_update_command_restore(unit, direction)
        return None

    def _prepare_sever_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the Sever-session half of one self-save restoration."""

        if unit.command != "sever" or len(unit.changes) != 1:
            return None
        change = unit.changes[0]
        if change.before is None or change.after is None:
            # Other-save creation uses the dedicated lifecycle restoration.
            return None
        checkpoint = next(
            (
                entry
                for entry in self.list_checkpoints(change.context_name)
                if entry.get("uid") == change.checkpoint_uid
            ),
            None,
        )
        args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
        record = args.get("sever") if isinstance(args, dict) else None
        session_uid = record.get("session_uid") if isinstance(record, dict) else None
        if (
            not isinstance(session_uid, str)
            or record.get("save_mode") != "SELF_SAVE"
            or record.get("source") != change.context_name
            or record.get("output") != change.context_name
        ):
            raise ValueError("Self-save Sever checkpoint has no valid session receipt.")
        from memcommit.sever import SeverApplication
        from memcommit.sever_store import SeverSessionStore

        sessions = SeverSessionStore(self)
        session = sessions.load(session_uid)
        result_uids = tuple(source.uid for _candidate, source, _content in session.results())
        application = SeverApplication(
            output_context_uid=change.context_uid,
            checkpoint_uid=change.checkpoint_uid,
            result_memory_uids=result_uids,
        )
        if (
            session.save_mode != "SELF_SAVE"
            or session.output_name != change.context_name
            or session.source.root_uid != change.context_uid
        ):
            raise ValueError("Self-save Sever session does not match its command.")
        if direction == "undo":
            if session.state != "APPLIED" or session.application != application:
                raise ConcurrentContextUpdateError(
                    "The self-save Sever session changed before Undo."
                )
            restored = session.clear_application(
                output_context_uid=application.output_context_uid,
                checkpoint_uid=application.checkpoint_uid,
            )
        else:
            if session.state != "REVIEWING" or session.application is not None:
                raise ConcurrentContextUpdateError(
                    "The self-save Sever session changed before Redo."
                )
            restored = session.with_application(application)
        return sessions._path(session.uid), session.to_dict(), restored.to_dict()

    def _write_applied_artifact_restore(
        self,
        path: Path,
        *,
        expected: dict[str, object],
        value: dict[str, object],
    ) -> None:
        """CAS-write one companion artifact inside command restoration."""
        if path == self.staged_update_file:
            with self._update_session_write_lock():
                current = self._load_update_session(path)
                if current is None or current.to_dict() != expected:
                    raise ConcurrentContextUpdateError(
                        "The active Update receipt changed during restoration."
                    )
                from memcommit.update import UpdateSession

                self._save_update_session(path, UpdateSession.from_dict(value))
            return
        from memcommit.sever_store import SeverSessionStore

        sever_sessions = SeverSessionStore(self)
        if path.parent == sever_sessions.directory:
            uid = path.stem
            if path != sever_sessions._path(uid):
                raise ConcurrentContextUpdateError(
                    "The Sever session restore path is invalid."
                )
            with self.profile_write_guard():
                with sever_sessions._write_lock(uid):
                    if not path.is_file() or path.is_symlink():
                        raise ConcurrentContextUpdateError(
                            "The applied Sever session changed during restoration."
                        )
                    with open(path, encoding="utf-8") as file:
                        current = json.load(
                            file,
                            object_pairs_hook=_reject_duplicate_json_keys,
                        )
                    if current != expected:
                        raise ConcurrentContextUpdateError(
                            "The applied Sever session changed during restoration."
                        )
                    _write_json_atomic(path, value)
            return
        with self.profile_write_guard():
            if not path.is_file() or path.is_symlink():
                raise ConcurrentContextUpdateError(
                    "The applied operation artifact changed during restoration."
                )
            with open(path, encoding="utf-8") as file:
                current = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if current != expected:
                raise ConcurrentContextUpdateError(
                    "The applied operation artifact changed during restoration."
                )
            _write_json_atomic(path, value)

    def _prepare_meld_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the Meld-session half of one Context command restoration."""
        if unit.command != "meld":
            return None
        if not unit.changes:
            raise ValueError("A Meld command has no target Context changes.")
        records: list[dict[str, object]] = []
        for change in unit.changes:
            checkpoint = next(
                (
                    entry
                    for entry in self.list_checkpoints(change.context_name)
                    if entry.get("uid") == change.checkpoint_uid
                ),
                None,
            )
            args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
            record = args.get("meld") if isinstance(args, dict) else None
            if not isinstance(record, dict):
                raise ValueError("Meld checkpoint has no valid session receipt.")
            records.append(record)
        session_uids = {record.get("session_uid") for record in records}
        change_set_digests = {record.get("change_set_digest") for record in records}
        raw_results = records[0].get("results")
        if (
            len(session_uids) != 1
            or len(change_set_digests) != 1
            or not all(isinstance(item, str) and item for item in session_uids)
            or not all(isinstance(item, str) and item for item in change_set_digests)
            or not isinstance(raw_results, list)
            or any(record.get("results") != raw_results for record in records[1:])
        ):
            raise ValueError("Meld checkpoint session receipts are inconsistent.")
        session_uid = next(iter(session_uids))
        change_set_digest = next(iter(change_set_digests))
        result_uids = tuple(
            result.get("memory_uid")
            for result in raw_results
            if isinstance(result, dict) and isinstance(result.get("memory_uid"), str)
        )
        if len(result_uids) != len(raw_results):
            raise ValueError("Meld checkpoint result identities are invalid.")
        target = records[0].get("target_baseline")
        if not isinstance(target, dict):
            raise ValueError("Meld checkpoint target binding is invalid.")
        target_uid = target.get("context_uid")
        target_name = target.get("context_name")
        if not isinstance(target_uid, str) or not isinstance(target_name, str):
            raise ValueError("Meld checkpoint target binding is invalid.")
        session = self.load_meld_session(target_uid)
        if (
            session is None
            or session.uid != session_uid
            or session.target.context_uid != target_uid
            or session.target.context_name != target_name
        ):
            raise ValueError("Meld session does not match the restored command.")
        from memcommit.meld import (
            MELD_OWNER_AWARE_SCHEMA_VERSION,
            MeldCheckpointReceipt,
        )

        checkpoint_by_identity = {
            (change.context_uid, change.context_name): change.checkpoint_uid
            for change in unit.changes
        }
        baseline = session.frames[1]
        owner_order = (
            tuple((context.uid, context.name) for context in baseline.contexts)
            if baseline.contexts is not None
            else ((target_uid, target_name),)
        )
        receipts = tuple(
            MeldCheckpointReceipt(
                context_uid=context_uid,
                context_name=context_name,
                checkpoint_uid=checkpoint_by_identity[(context_uid, context_name)],
            )
            for context_uid, context_name in owner_order
            if (context_uid, context_name) in checkpoint_by_identity
        )
        if len(receipts) != len(unit.changes):
            raise ValueError("Meld checkpoint owners are outside the target scope.")
        primary_checkpoint_uid = receipts[0].checkpoint_uid
        application_receipts = (
            receipts
            if session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
            else ()
        )
        before = session.to_dict()
        if direction == "undo":
            session.clear_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=primary_checkpoint_uid,
                checkpoints=application_receipts,
            )
        elif session.state == "READY_TO_APPLY" and session.application is None:
            session.record_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=primary_checkpoint_uid,
                result_memory_uids=result_uids,
                checkpoints=application_receipts,
            )
        elif not (
            session.state == "APPLIED"
            and session.application is not None
            and session.application.change_set_digest == change_set_digest
            and session.application.checkpoint_uid == primary_checkpoint_uid
            and session.application.result_memory_uids == result_uids
            and (
                not session.application.checkpoints
                or session.application.checkpoints == receipts
            )
        ):
            raise ValueError("Meld session cannot be restored to applied state.")
        return self._meld_session_path(target_uid), before, session.to_dict()

    def _prepare_atomize_grounding_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]]:
        """Prepare the atomize-grounding session half of Undo or Redo."""
        if len(unit.changes) != 1:
            raise ValueError(
                "An atomize-grounding command must restore exactly one Context."
            )
        change = unit.changes[0]
        checkpoint = next(
            (
                entry
                for entry in self.list_checkpoints(change.context_name)
                if entry.get("uid") == change.checkpoint_uid
            ),
            None,
        )
        args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
        record = args.get("grounding") if isinstance(args, dict) else None
        if not isinstance(record, dict):
            raise ValueError("Atomize grounding checkpoint has no valid receipt.")
        session_uid = record.get("session_uid")
        change_set_digest = record.get("change_set_digest")
        raw_change_set = record.get("change_set")
        if (
            not isinstance(session_uid, str)
            or not session_uid
            or not isinstance(change_set_digest, str)
            or not change_set_digest
            or not isinstance(raw_change_set, dict)
        ):
            raise ValueError("Atomize grounding checkpoint receipt is invalid.")
        raw_proposals = raw_change_set.get("proposals")
        proposal_uids = (
            tuple(
                proposal.get("uid")
                for proposal in raw_proposals
                if isinstance(proposal, dict) and isinstance(proposal.get("uid"), str)
            )
            if isinstance(raw_proposals, list)
            else ()
        )
        if not isinstance(raw_proposals, list) or len(proposal_uids) != len(
            raw_proposals
        ):
            raise ValueError("Atomize grounding proposal identities are invalid.")
        session = self.load_atomize_grounding_session(change.context_uid)
        if (
            session is None
            or session.uid != session_uid
            or session.bindings.context_uid != change.context_uid
            or session.bindings.context_name != change.context_name
        ):
            raise ValueError(
                "Atomize grounding session does not match the restored command."
            )
        before = session.to_dict()
        if direction == "undo":
            session.clear_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=change.checkpoint_uid,
            )
        elif session.state == "READY_TO_APPLY" and session.application is None:
            session.record_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=change.checkpoint_uid,
            )
        elif not (
            session.state == "APPLIED"
            and session.application is not None
            and session.application.change_set_digest == change_set_digest
            and session.application.checkpoint_uid == change.checkpoint_uid
            and session.application.proposal_uids == proposal_uids
        ):
            raise ValueError(
                "Atomize grounding session cannot be restored to applied state."
            )
        return (
            self._atomize_grounding_session_path(change.context_uid),
            before,
            session.to_dict(),
        )

    def _prepare_update_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the active local Update receipt coupled to its checkpoints."""
        from memcommit.update import operation_digest

        session = self.load_staged_update()
        if session is None:
            # Granted-target Contexts live in the authority Profile; their
            # participant receipt is coordinated by restore_granted_update.
            return None
        digest = operation_digest(session.operations)
        expected_unit_uid = f"update:{session.uid}:{digest}"
        if unit.uid != expected_unit_uid:
            return None
        if session.application is None:
            raise ValueError("Update command has no application receipt.")
        receipt_by_context = {
            (receipt.context_uid, receipt.context_name): receipt.checkpoint_uid
            for receipt in session.application.checkpoints
        }
        command_by_context = {
            (change.context_uid, change.context_name): change.checkpoint_uid
            for change in unit.changes
        }
        if (
            session.application.operation_digest != digest
            or receipt_by_context != command_by_context
        ):
            raise ValueError("Update application receipt does not match this command.")
        before = session.to_dict()
        if direction == "undo":
            session = session.with_restored_application(applied=False)
        elif session.status == "undone":
            session = session.with_restored_application(applied=True)
        elif session.status != "applied":
            raise ValueError("Update session cannot be restored to applied state.")
        return self.staged_update_file, before, session.to_dict()

    def revert(
        self,
        ctx_name: str,
        uid_prefix: str,
        keep_history: bool = False,
        *,
        expected_context_uid: str | None = None,
        expected_context_digest: str | None = None,
        expected_history_digest: str | None = None,
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert one Context while holding its cooperative write lock."""
        with self._command_write_lock():
            self._assert_profile_write_allowed()
            with self._context_write_lock(ctx_name):
                return self._revert_locked(
                    ctx_name,
                    uid_prefix,
                    keep_history=keep_history,
                    expected_context_uid=expected_context_uid,
                    expected_context_digest=expected_context_digest,
                    expected_history_digest=expected_history_digest,
                )

    def _revert_locked(
        self,
        ctx_name: str,
        uid_prefix: str,
        *,
        keep_history: bool,
        expected_context_uid: str | None,
        expected_context_digest: str | None,
        expected_history_digest: str | None,
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert context to a checkpoint. Returns (pre_revert_cp, target_cp).

        By default, checkpoints newer than the target are removed and the
        pre-revert snapshot is appended as the new head. If the target is itself
        a pre-revert checkpoint carrying a log_snapshot, the full original log
        is rebuilt from that snapshot instead of just truncating.

        Pass keep_history=True to leave all checkpoint files untouched.
        """
        entries = self.list_checkpoints(ctx_name)  # captured before any mutations
        # Preconditions and the recovery snapshot concern the directly owned
        # Context record. Do not resolve MemoryRef targets or embedded
        # Contexts merely to decide whether a reviewed frame is still fresh.
        ctx = self.load_direct(ctx_name)
        if expected_context_uid is not None and ctx.uid != expected_context_uid:
            raise ConcurrentContextUpdateError(
                "Context identity changed before the reviewed revert."
            )
        if (
            expected_context_digest is not None
            and context_record_digest(ctx) != expected_context_digest
        ):
            raise ConcurrentContextUpdateError(
                "Context content changed before the reviewed revert."
            )
        if (
            expected_history_digest is not None
            and checkpoint_history_digest(entries) != expected_history_digest
        ):
            raise ConcurrentContextUpdateError(
                "Checkpoint history changed before the reviewed revert."
            )
        matches = [e for e in entries if e["uid"].startswith(uid_prefix)]
        if not matches:
            raise KeyError(f"No checkpoint with uid prefix '{uid_prefix}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous prefix '{uid_prefix}' matches {len(matches)} checkpoints."
            )

        target_data = matches[0]
        target_ts = target_data["timestamp"]
        cp_dir = self._checkpoints_dir(ctx_name)
        checkpoint_paths = tuple(sorted(cp_dir.glob("*.json")))
        if any(path.is_symlink() or not path.is_file() for path in checkpoint_paths):
            raise ValueError(f"Checkpoint history for '{ctx_name}' is unsafe.")
        original_checkpoint_bytes = {
            path.name: path.read_bytes() for path in checkpoint_paths
        }
        physical_records: dict[str, dict[str, object]] = {}
        for path in checkpoint_paths:
            try:
                with open(path, encoding="utf-8") as file:
                    record = json.load(
                        file,
                        object_pairs_hook=_reject_duplicate_json_keys,
                    )
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(
                    f"Checkpoint history for '{ctx_name}' is invalid."
                ) from error
            if not isinstance(record, dict):
                raise ValueError(f"Checkpoint history for '{ctx_name}' is invalid.")
            physical_records[path.name] = record

        # Strip nested log snapshots so the recovery frame remains bounded.
        thin_entries: list[dict] = []
        for entry in entries:
            args = entry.get("args") or {}
            if "log_snapshot" in args:
                entry = {
                    **entry,
                    "args": {
                        key: value
                        for key, value in args.items()
                        if key != "log_snapshot"
                    },
                }
            thin_entries.append(entry)

        message = f"Pre-revert to [{target_data['uid'][:8]}] — revert here to undo"
        pre_cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command="revert",
            args={
                "target_uid": target_data["uid"],
                "log_snapshot": thin_entries,
            },
            description=message,
            auto=True,
        )
        pre_slug = message[:24].replace(" ", "-").replace("/", "-")
        pre_name = (
            f"{pre_cp.timestamp.strftime('%Y%m%dT%H%M%S')}-"
            f"{pre_slug}-{pre_cp.uid[:8]}.json"
        )
        pre_record: dict[str, object] = {
            "uid": pre_cp.uid,
            "message": pre_cp.message,
            "timestamp": pre_cp.timestamp.isoformat(),
            "snapshot": pre_cp.snapshot,
            "command": pre_cp.command,
            "args": pre_cp.args,
            "description": pre_cp.description,
            "auto": pre_cp.auto,
        }

        desired_records: dict[str, dict[str, object]]
        if keep_history:
            desired_records = dict(physical_records)
        else:
            log_snapshot = (target_data.get("args") or {}).get("log_snapshot")
            if log_snapshot is not None:
                if not isinstance(log_snapshot, list):
                    raise ValueError("Checkpoint log snapshot is invalid.")
                desired_records = {}
                for entry in sorted(
                    log_snapshot,
                    key=lambda value: value["timestamp"],
                ):
                    if not isinstance(entry, dict):
                        raise ValueError("Checkpoint log snapshot is invalid.")
                    timestamp = datetime.fromisoformat(entry["timestamp"])
                    uid = entry.get("uid")
                    if not isinstance(uid, str) or not uid:
                        raise ValueError("Checkpoint log snapshot is invalid.")
                    filename = f"{timestamp.strftime('%Y%m%dT%H%M%S')}-{uid[:8]}.json"
                    if filename in desired_records:
                        raise ValueError(
                            "Checkpoint log snapshot contains duplicate entries."
                        )
                    desired_records[filename] = entry
            else:
                desired_records = {
                    filename: record
                    for filename, record in physical_records.items()
                    if record["timestamp"] <= target_ts
                }
        if pre_name in desired_records:
            raise ValueError("Recovery checkpoint filename collided with history.")
        desired_records[pre_name] = pre_record

        # A branch inherits checkpoint files whose snapshots still carry the
        # source Context identity. Restore their contents into the Context the
        # caller requested instead of writing back to the source Context. A
        # non-resolving parse preserves unavailable context_ref pointers.
        restored = self._context_for_restoration(
            target_data["snapshot"],
            context_uid=ctx.uid,
            context_name=ctx.name,
            expected_context_digest=context_record_digest(ctx),
        )

        context_path = self._context_file(ctx_name)
        original_context_bytes = context_path.read_bytes()
        written_names: set[str] = set()
        try:
            # Prepare every replacement with the normal atomic writer before
            # removing obsolete history. The command lock keeps other history
            # operations outside this exception-rollback boundary.
            for filename, record in desired_records.items():
                destination = cp_dir / filename
                if destination.is_symlink():
                    raise ValueError(
                        f"Refusing to restore checkpoint for '{ctx_name}' "
                        "through a symbolic link."
                    )
                _write_json_atomic(destination, record)
                written_names.add(filename)
            for filename in original_checkpoint_bytes:
                if filename not in desired_records:
                    (cp_dir / filename).unlink()
            self._save_locked(
                restored,
                None,
                expected_context_digest=ctx._store_digest,
            )
        except Exception as error:
            rollback_error: Exception | None = None
            for filename in written_names:
                if filename in original_checkpoint_bytes:
                    continue
                try:
                    path = cp_dir / filename
                    if path.exists() and not path.is_symlink():
                        path.unlink()
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            for filename, content in original_checkpoint_bytes.items():
                try:
                    _write_bytes_atomic(cp_dir / filename, content)
                except Exception as candidate:
                    rollback_error = rollback_error or candidate
            try:
                _write_bytes_atomic(context_path, original_context_bytes)
            except Exception as candidate:
                rollback_error = rollback_error or candidate
            if rollback_error is not None:
                raise RuntimeError(
                    "Revert failed and its original Context/history could not "
                    "be fully restored."
                ) from rollback_error
            raise error
        restored._store_digest = context_record_digest(restored)

        target_cp = Checkpoint(
            uid=target_data["uid"],
            message=target_data.get("message", ""),
            timestamp=datetime.fromisoformat(target_data["timestamp"]),
            snapshot=target_data["snapshot"],
            command=target_data.get("command"),
            args=target_data.get("args"),
            description=target_data.get("description"),
            auto=target_data.get("auto", False),
        )
        return pre_cp, target_cp
