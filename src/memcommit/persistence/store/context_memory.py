"""Persist the current Context and Memory graph and its lifecycle."""

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

from memcommit.application.retained_history.checkpoint_frames import map_restorable_checkpoint_frames
from memcommit.context import AutoCheckpoint, Checkpoint, Context, Memory, MemoryRef
from memcommit.core.context_targeting.naming import (
    RESERVED_CONTEXT_SEGMENTS,
    validate_portable_context_name,
)
from memcommit.core.context_targeting.navigation import (
    ContextNavigationDirection,
    apply_context_navigation,
    context_navigation_target,
    record_current_context_transition,
    rewrite_context_navigation_names,
)
from memcommit.application.retained_history.context_lifecycle import (
    ContextLifecycleEvent,
    PREVIOUS_CHECKPOINT_NONE,
    PREVIOUS_CHECKPOINT_RECORDED,
    PREVIOUS_CHECKPOINT_UNREADABLE,
)
from memcommit.core.context_targeting.context_catalog import (
    ContextCatalogDiagnostic,
    ContextCatalogDiagnosticCode,
    ContextCatalogScan,
)
from memcommit.application.operations.profile.config import resolve_active_store_dir
from memcommit.application.authority.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)
from memcommit.application.authority.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistry,
    WriteProtectionRegistryError,
    WriteProtectionState,
)
from memcommit.application.retained_history.memory_lineage import (
    MemoryLineageEdge,
    checkpoint_memory_lineage_edges,
    memory_content_sha256,
    memory_lineage_record,
    remap_restoration_snapshot,
)

from .operation_state import (
    ConcurrentContextUpdateError,
    ContextBranchBinding,
    ContextBranchMemoryBinding,
    ContextDeletionCommittedError,
    ContextRenameBinding,
    ContextRenamePlan,
    ContextRenameResult,
    QuerySource,
    QuerySourceEntry,
    _NO_CURRENT_CONTEXT_EXPECTATION,
    _PreparedContextRename,
    _canonical_json_digest,
    _context_name_parts,
    _fsync_directory,
    _mapped_context_name,
    _profile_write_guarded,
    _query_source_entry_from_record,
    _query_source_language,
    _query_source_text,
    _reject_duplicate_json_keys,
    _rewrite_branched_checkpoint_record,
    _rewrite_checkpoint_record,
    _rewrite_context_pointers,
    _validate_context_header,
    _write_bytes_atomic,
    _write_json_atomic,
    canonical_context_record,
    checkpoint_history_digest,
    context_record_digest,
    validate_context_name,
)


class ContextMemoryStoreMixin:
    """Temporary Store slice for current Context and Memory persistence."""

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
            from memcommit.application.authority.access import load_granted_context_link

            return load_granted_context_link(
                link,
                active_store=self,
                loading=_loading | {name},
            )

        def granted_memory_loader(source):
            # A granted Memory Embed is content-free on disk and must pass the
            # same live Grant reauthorization boundary on every resolved load.
            from memcommit.application.authority.access import load_granted_memory_source

            return load_granted_memory_source(source, active_store=self)

        try:
            ctx = Context.from_dict(
                data,
                loader=loader,
                memory_loader=self._load_direct_memory,
                granted_memory_loader=(
                    granted_memory_loader if self._resolve_granted_links else None
                ),
                granted_loader=(
                    granted_loader if self._resolve_granted_links else None
                ),
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

    def load_without_attached_reads(self, name: str) -> Context:
        """Load recursive persisted edges without process-local READ projections.

        A plain MemoryStore never synthesizes attachment projections, but this
        explicit capability lets provider-facing adapters require the same
        fail-closed interface from both ordinary and unified readable stores.
        """

        return self.load(name)

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
        from memcommit.application.operations.ground.model import GroundError, GroundSession

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
        from memcommit.application.operations.translate.view import (
            TranslationCatalog,
            TranslationView,
            TranslationViewError,
        )
        from memcommit.application.operations.translate.view_store import (
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

        from memcommit.application.operations.meld.model import MeldError, MeldSession

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
        rewrite_context_navigation_names(
            post_state,
            lambda candidate: (
                _mapped_context_name(candidate, old_name, new_name) or candidate
            ),
        )

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
        from memcommit.application.operations.ground.model import GroundError, GroundSession

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
        from memcommit.application.operations.translate.view import (
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
        from memcommit.application.operations.compare.ledger.model import comparison_canonical_digest
        from memcommit.application.operations.meld.model import MeldError, MeldSession

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
            from memcommit.application.operations.translate.view_store import translation_views_dir

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
                    from memcommit.core.context_targeting.model import ContextScope
                    from memcommit.core.context_targeting.resolution import (
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
        source = self.load_direct(source_name)
        source_memories = tuple(
            item for item in source.iter_items() if isinstance(item, Memory)
        )
        target_memories = tuple(
            item for item in ctx.iter_items() if isinstance(item, Memory)
        )
        if len(source_memories) != len(target_memories) or any(
            source_item.content != target_item.content
            for source_item, target_item in zip(
                source_memories,
                target_memories,
                strict=True,
            )
        ):
            raise ValueError("Branch target Memories do not match the Source frame.")
        self.create_branch_contexts(
            (
                ContextBranchBinding(
                    source_name=source_name,
                    expected_source_uid=expected_source_uid,
                    expected_source_digest=expected_source_digest,
                    expected_history_digest=expected_history_digest,
                    target=ctx,
                    memories=tuple(
                        ContextBranchMemoryBinding(
                            source_uid=source_item.uid,
                            target_uid=target_item.uid,
                            source_content_sha256=memory_content_sha256(
                                source_item.content
                            ),
                            target_content_sha256=memory_content_sha256(
                                target_item.content
                            ),
                        )
                        for source_item, target_item in zip(
                            source_memories,
                            target_memories,
                            strict=True,
                        )
                    ),
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

        for binding in records:
            source_memory_uids = tuple(item.source_uid for item in binding.memories)
            target_memory_uids = tuple(item.target_uid for item in binding.memories)
            target_memories = {
                item.uid: item
                for item in binding.target.iter_items()
                if isinstance(item, Memory)
            }
            if (
                len(source_memory_uids) != len(set(source_memory_uids))
                or len(target_memory_uids) != len(set(target_memory_uids))
                or set(source_memory_uids) & set(target_memory_uids)
                or set(target_memory_uids) != set(target_memories)
            ):
                raise ValueError("Branch Memory occurrence mapping is invalid.")
            for item in binding.memories:
                target_memory = target_memories.get(item.target_uid)
                if (
                    not isinstance(target_memory, Memory)
                    or memory_content_sha256(target_memory.content)
                    != item.target_content_sha256
                    or item.source_content_sha256 != item.target_content_sha256
                ):
                    raise ValueError(
                        "Branch Memory occurrence mapping does not match its target."
                    )

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
        branch_memory_lineage = memory_lineage_record(
            operation_uid,
            (
                MemoryLineageEdge(
                    source_context_uid=binding.expected_source_uid,
                    source_memory_uid=memory.source_uid,
                    target_context_uid=binding.target.uid,
                    target_memory_uid=memory.target_uid,
                    source_content_sha256=memory.source_content_sha256,
                    target_content_sha256=memory.target_content_sha256,
                )
                for binding in records
                for memory in binding.memories
            ),
        )
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
                        from memcommit.core.context_targeting.model import ContextScope
                        from memcommit.core.context_targeting.resolution import (
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
                    for binding in records:
                        live_source = self.load_direct(binding.source_name)
                        live_memories = {
                            item.uid: item
                            for item in live_source.iter_items()
                            if isinstance(item, Memory)
                        }
                        if set(live_memories) != {
                            item.source_uid for item in binding.memories
                        }:
                            raise ConcurrentContextUpdateError(
                                "The Branch Source Memory membership changed before "
                                "publication."
                            )
                        for item in binding.memories:
                            source_memory = live_memories[item.source_uid]
                            if (
                                memory_content_sha256(source_memory.content)
                                != item.source_content_sha256
                            ):
                                raise ConcurrentContextUpdateError(
                                    "A Branch Source Memory changed before publication."
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
                                            "memory_lineage": branch_memory_lineage,
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
                            record_current_context_transition(state, target_root)
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
                            record_current_context_transition(state, make_current)
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
        from memcommit.application.operations.compare.ledger.store import (
            comparison_paths_for_context,
            delete_comparison_paths,
        )
        from memcommit.application.operations.translate.view_store import (
            delete_translation_view_paths,
            translation_view_paths_for_context,
        )
        from memcommit.application.operations.rationale.cache import (
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
        atomize_session_history_dir = (
            self.atomize_session_history_dir / context_uid
            if canonical_context_uid == context_uid
            else None
        )
        meld_path = (
            self._meld_session_path(context_uid)
            if canonical_context_uid == context_uid
            else None
        )
        meld_session_history_dir = (
            self.meld_session_history_dir / context_uid
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
        retained_reviews = self.list_review_sessions()
        delete_review_session = (
            review_session is not None
            and review_session.context_uid == context_uid
            and review_session.context_name == name
        )
        review_history_paths = tuple(
            self._review_session_history_path(session.uid)
            for session in retained_reviews
            if session.uid != getattr(review_session, "uid", None)
            and session.context_uid == context_uid
            and session.context_name == name
        )
        review_source_paths = tuple(
            self._review_session_source_path(session.uid)
            for session in retained_reviews
            if session.context_uid == context_uid and session.context_name == name
        )
        if atomize_session_history_dir is not None and (
            atomize_session_history_dir.exists()
            or atomize_session_history_dir.is_symlink()
        ):
            # Strict loading rejects malformed entries before the primary
            # Context deletion can commit.
            self.list_atomize_session_history()
        meld_history_paths = tuple(
            path
            for session, path in self.list_meld_session_history()
            if any(frame.context_uid == context_uid for frame in session.frames)
            or session.target.context_uid == context_uid
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
        if (
            atomize_session_history_dir is not None
            and atomize_session_history_dir.exists()
        ):
            def remove_atomize_session_history() -> None:
                shutil.rmtree(atomize_session_history_dir)
                _fsync_directory(atomize_session_history_dir.parent)
                try:
                    self.atomize_session_history_dir.rmdir()
                except OSError:
                    pass

            attempt_cleanup("Atomize session history", remove_atomize_session_history)
        for retained_meld_path in meld_history_paths:
            attempt_cleanup("Meld session history", retained_meld_path.unlink)
        if (
            meld_session_history_dir is not None
            and meld_session_history_dir.exists()
        ):
            def remove_empty_meld_history_directory() -> None:
                try:
                    meld_session_history_dir.rmdir()
                except OSError:
                    return
                _fsync_directory(meld_session_history_dir.parent)
                try:
                    self.meld_session_history_dir.rmdir()
                except OSError:
                    pass

            attempt_cleanup(
                "Meld session history directory",
                remove_empty_meld_history_directory,
            )
        if delete_review_session and self.review_session_file.exists():
            # Review answers may contain user-supplied local context. Once
            # their exact Context is deleted, retaining that global artifact
            # would be both misleading state and an avoidable privacy leak.
            attempt_cleanup("review session", self.review_session_file.unlink)
        for retained_review_path in review_history_paths:
            if retained_review_path.exists():
                attempt_cleanup("review session history", retained_review_path.unlink)
        for review_source_path in review_source_paths:
            if review_source_path.exists():
                attempt_cleanup("review source snapshot", review_source_path.unlink)

        def clear_current_pointer() -> None:
            with self._state_write_lock():
                state = self._read_state()
                if state.get("current") == name:
                    record_current_context_transition(state, None)
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

