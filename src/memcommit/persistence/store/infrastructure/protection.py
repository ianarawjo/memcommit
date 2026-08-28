"""Coordinate Profile, Context, and Memory write protection."""

from __future__ import annotations
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Iterable, Iterator
from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.authority.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistry,
    WriteProtectionRegistryError,
    WriteProtectionState,
)


from ..context_memory.models import ConcurrentContextUpdateError
from ..context_memory.records import (
    canonical_context_record,
    context_record_digest,
    validate_context_name,
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


class _WriteProtectionStoreMixin:
    """Focused slice of the temporary Store assembly."""

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
