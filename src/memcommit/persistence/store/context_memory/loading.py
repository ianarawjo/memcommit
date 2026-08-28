"""Load Context and Memory records under stable read locks."""

from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Iterable, Iterator

from memcommit.core.context import Context, Memory

from ..infrastructure.atomic_io import _reject_duplicate_json_keys
from .models import ConcurrentContextUpdateError
from .records import (
    _rewrite_context_pointers,
    _validate_context_header,
    context_record_digest,
)


class _ContextLoadingMixin:
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
            from memcommit.application.capabilities.authority.access import load_granted_context_link

            return load_granted_context_link(
                link,
                active_store=self,
                loading=_loading | {name},
            )

        def granted_memory_loader(source):
            # A granted Memory Embed is content-free on disk and must pass the
            # same live Grant reauthorization boundary on every resolved load.
            from memcommit.application.capabilities.authority.access import (
                load_granted_memory_source,
            )

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
