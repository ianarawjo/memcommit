"""Meld checkpoint construction, recovery, authority checks, and mutation."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from contextlib import ExitStack

from memcommit.application.capabilities.authority.access import (
    ContextAccess,
    revalidate_granted_context_binding,
)
from memcommit.application.operations.meld.application import (
    MeldApplicationError,
    MeldApplyPort,
    MeldApplyReceipt,
    MeldApplyRequest,
    MeldApplyResult,
    run_meld_apply,
)
from memcommit.application.operations.meld.model import (
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MeldCheckpointReceipt,
    MeldSession,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.application.operations.update.granted_application import (
    _remove_checkpoint,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
)

from .source_bindings import (
    assert_meld_non_target_source_bindings,
    assert_unapplied_meld_target,
    load_bound_meld_contexts,
    target_save_source_bindings,
    walk_meld_target_contexts,
)


def meld_checkpoint_record(
    session: MeldSession,
    change_set,
    *,
    owner: tuple[str, str] | None = None,
) -> dict[str, object]:
    """Build the existing complete, source-linked Meld checkpoint payload."""

    owner_aware = (
        session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
    )
    record: dict[str, object] = {
        "schema_version": 3
        if owner_aware
        else 2
        if session.mode == "DIRECTIONAL"
        else 1,
        "session_uid": session.uid,
        "turn_uid": change_set.turn_uid,
        "mode": session.mode,
        "change_set_digest": change_set.digest,
        "change_set": change_set.to_dict(),
        "sources": [
            {
                "frame_uid": frame.uid,
                **({"role": frame.role} if session.mode == "DIRECTIONAL" else {}),
                "context_uid": frame.context_uid,
                "context_name": frame.context_name,
                "context_digest": frame.context_digest,
                "memories": [memory.to_dict() for memory in frame.memories],
                **(
                    {"include_descendants": frame.include_descendants}
                    if owner_aware and frame.include_descendants is not None
                    else {}
                ),
                **(
                    {"contexts": [context.to_dict() for context in frame.contexts]}
                    if owner_aware and frame.contexts is not None
                    else {}
                ),
            }
            for frame in session.frames
        ],
        "target_baseline": session.target.to_dict(),
        "turns": [
            {
                "uid": turn.uid,
                "sequence": turn.sequence,
                "revision": turn.revision,
                "scope": turn.scope,
                "issue_uids": list(turn.issue_uids),
                "comment": turn.comment,
                "comment_sha256": hashlib.sha256(
                    turn.comment.encode("utf-8")
                ).hexdigest(),
                "revises_turn_uids": list(turn.revises_turn_uids),
            }
            for turn in session.turns
        ],
        "results": [
            {
                "proposal_uid": proposal.uid,
                **(
                    {"operation": proposal.operation}
                    if session.mode == "DIRECTIONAL"
                    else {}
                ),
                **(
                    {
                        "owner_context": {
                            "uid": proposal.owner_context_uid,
                            "name": proposal.owner_context_name,
                        }
                    }
                    if proposal.owner_context_uid is not None
                    else {}
                ),
                "memory_uid": proposal.memory_uid,
                "disposition": proposal.disposition,
                "content_sha256": hashlib.sha256(
                    proposal.content.encode("utf-8")
                ).hexdigest(),
                "source_members": [
                    member.to_dict() for member in proposal.source_members
                ],
                "grounded_by_turn_uids": list(proposal.grounded_by_turn_uids),
                "relation_uids": list(proposal.relation_uids),
                "reason": proposal.reason,
            }
            for proposal in change_set.proposals
        ],
    }
    if owner is not None:
        record["owner_context_uid"] = owner[0]
        record["owner_context_name"] = owner[1]
    return record


def expected_target_memories(session: MeldSession, change_set) -> tuple[Memory, ...]:
    if session.mode == "SYMMETRIC":
        return tuple(
            Memory(uid=proposal.memory_uid, content=proposal.content)
            for proposal in change_set.proposals
        )
    baseline = session.frames[1]
    expected = [
        Memory(uid=memory.uid, content=memory.content) for memory in baseline.memories
    ]
    position_by_uid = {memory.uid: index for index, memory in enumerate(expected)}
    for proposal in change_set.proposals:
        memory = Memory(uid=proposal.memory_uid, content=proposal.content)
        if proposal.operation == "EDIT":
            expected[position_by_uid[proposal.memory_uid]] = memory
        else:
            position_by_uid[proposal.memory_uid] = len(expected)
            expected.append(memory)
    return tuple(expected)


def affected_meld_owners(
    session: MeldSession,
    change_set,
) -> tuple[tuple[str, str], ...]:
    baseline = session.frames[1]
    ordered = (
        tuple((context.uid, context.name) for context in baseline.contexts)
        if baseline.contexts is not None
        else ((baseline.context_uid, baseline.context_name),)
    )
    requested = {
        (proposal.owner_context_uid, proposal.owner_context_name)
        for proposal in change_set.proposals
    }
    if not requested:
        requested.add((baseline.context_uid, baseline.context_name))
    result = tuple(identity for identity in ordered if identity in requested)
    if len(result) != len(requested):
        raise MeldApplicationError(
            "A Meld proposal owner is outside the BASELINE scope."
        )
    return result


def expected_owner_memories(
    session: MeldSession,
    change_set,
) -> dict[tuple[str, str], tuple[Memory, ...]]:
    baseline = session.frames[1]
    owner_order = (
        tuple((context.uid, context.name) for context in baseline.contexts)
        if baseline.contexts is not None
        else ((baseline.context_uid, baseline.context_name),)
    )
    expected: dict[tuple[str, str], list[Memory]] = {
        identity: [] for identity in owner_order
    }
    for source in baseline.memories:
        identity = (
            source.owner_context_uid or baseline.context_uid,
            source.owner_context_name or baseline.context_name,
        )
        if identity not in expected:
            raise MeldApplicationError("A BASELINE Memory has an invalid owner.")
        expected[identity].append(Memory(uid=source.uid, content=source.content))
    positions = {
        identity: {memory.uid: index for index, memory in enumerate(memories)}
        for identity, memories in expected.items()
    }
    for proposal in change_set.proposals:
        identity = (proposal.owner_context_uid, proposal.owner_context_name)
        if identity not in expected:
            raise MeldApplicationError(
                "A Meld proposal owner is outside the BASELINE scope."
            )
        memory = Memory(uid=proposal.memory_uid, content=proposal.content)
        if proposal.operation == "EDIT":
            try:
                position = positions[identity][proposal.memory_uid]
            except KeyError as error:
                raise MeldApplicationError(
                    "A directional Meld EDIT does not belong to its target owner."
                ) from error
            expected[identity][position] = memory
        else:
            if proposal.memory_uid in positions[identity]:
                raise MeldApplicationError(
                    "A directional Meld ADD collides with its owner."
                )
            positions[identity][proposal.memory_uid] = len(expected[identity])
            expected[identity].append(memory)
    return {identity: tuple(memories) for identity, memories in expected.items()}


def recover_owner_aware_application(
    *,
    session: MeldSession,
    target: Context,
    change_set,
    checkpoint_store: MemoryStore,
    checkpoint_name_by_public: dict[str, str] | None = None,
) -> tuple[tuple[MeldCheckpointReceipt, ...], tuple[str, ...]] | None:
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
    ):
        return None
    contexts = {
        (context.uid, context.name): context
        for context in walk_meld_target_contexts(target)
    }
    expected = expected_owner_memories(session, change_set)
    owners = affected_meld_owners(session, change_set)
    for identity, wanted in expected.items():
        context = contexts.get(identity)
        if context is None:
            return None
        current = tuple(
            item for item in context.iter_items() if isinstance(item, Memory)
        )
        if [item.uid for item in current] != [item.uid for item in wanted] or [
            item.content for item in current
        ] != [item.content for item in wanted]:
            return None
    receipts: list[MeldCheckpointReceipt] = []
    for context_uid, public_name in owners:
        checkpoint_name = (
            checkpoint_name_by_public.get(public_name, public_name)
            if checkpoint_name_by_public is not None
            else public_name
        )
        checkpoint_uid = None
        for checkpoint in reversed(checkpoint_store.list_checkpoints(checkpoint_name)):
            args = checkpoint.get("args")
            record = args.get("meld") if isinstance(args, dict) else None
            if (
                checkpoint.get("command") == "meld"
                and isinstance(record, dict)
                and record.get("session_uid") == session.uid
                and record.get("change_set_digest") == change_set.digest
                and record.get("owner_context_uid") == context_uid
                and isinstance(checkpoint.get("uid"), str)
            ):
                checkpoint_uid = checkpoint["uid"]
                break
        if checkpoint_uid is None:
            return None
        receipts.append(
            MeldCheckpointReceipt(
                context_uid=context_uid,
                context_name=public_name,
                checkpoint_uid=checkpoint_uid,
            )
        )
    return tuple(receipts), tuple(
        proposal.memory_uid for proposal in change_set.proposals
    )


def recover_meld_application(
    *,
    store: MemoryStore,
    session: MeldSession,
    target: Context,
    change_set,
    checkpoint_store: MemoryStore | None = None,
    checkpoint_context_name: str | None = None,
) -> tuple[str, tuple[str, ...]] | None:
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
    ):
        return None
    result_uids = tuple(proposal.memory_uid for proposal in change_set.proposals)
    expected = expected_target_memories(session, change_set)
    current_items = tuple(target.iter_items())
    if any(not isinstance(item, Memory) for item in current_items):
        return None
    current = tuple(current_items)
    if tuple(memory.uid for memory in current) != tuple(
        memory.uid for memory in expected
    ) or tuple(memory.content for memory in current) != tuple(
        memory.content for memory in expected
    ):
        return None
    receipt_store = checkpoint_store or store
    receipt_name = checkpoint_context_name or target.name
    for checkpoint in reversed(receipt_store.list_checkpoints(receipt_name)):
        if checkpoint.get("command") != "meld":
            continue
        args = checkpoint.get("args")
        record = args.get("meld") if isinstance(args, dict) else None
        if (
            isinstance(record, dict)
            and record.get("session_uid") == session.uid
            and record.get("change_set_digest") == change_set.digest
            and isinstance(checkpoint.get("uid"), str)
        ):
            return checkpoint["uid"], result_uids
    return None


def required_directional_target_permissions(change_set) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                "UPDATE" if proposal.operation == "EDIT" else "CREATE"
                for proposal in change_set.proposals
            }
        )
    )


def validate_owner_aware_grant_permissions(
    session: MeldSession,
    proposals: Iterable,
    *,
    registry,
) -> None:
    binding = session.granted_target
    if binding is None:
        raise MeldApplicationError("Expected a granted directional Meld target.")
    proposal_values = tuple(proposals)
    required = {
        "UPDATE" if proposal.operation == "EDIT" else "CREATE"
        for proposal in proposal_values
    }
    missing = sorted(required - set(binding.permissions))
    if missing:
        raise ProfileError(
            "The BASELINE Grant does not authorize "
            + " + ".join(missing)
            + " required by the proposed Meld changes."
        )
    for proposal in proposal_values:
        permission = "UPDATE" if proposal.operation == "EDIT" else "CREATE"
        view = resolve_granted_context_view(
            proposal.owner_context_name,
            attachment_name=binding.attachment_context_name,
            required_permission=permission,
            registry=registry,
        )
        if (
            view.grant.uid != binding.grant_uid
            or view.grant.revision != binding.grant_revision
            or view.authority.uid != binding.authority_profile_uid
            or view.grantee.uid != binding.grantee_profile_uid
        ):
            raise ProfileError(
                "A planned Meld owner is controlled by a different or changed Grant."
            )


def apply_owner_proposals(direct: Context, proposals: Iterable) -> Context:
    post_image = Context.from_dict(direct.to_dict())
    post_image._store_digest = direct._store_digest
    for proposal in proposals:
        memory = Memory(uid=proposal.memory_uid, content=proposal.content)
        if proposal.operation == "EDIT":
            post_image.replace(memory)
        else:
            if proposal.memory_uid in post_image.memories:
                raise MeldApplicationError(
                    "A directional Meld ADD collides with an existing owner item."
                )
            post_image.add(memory)
    return post_image


def granted_owner_name(binding, public_name: str) -> str:
    if not (
        public_name == binding.public_name
        or public_name.startswith(binding.public_name + "/")
    ):
        raise MeldApplicationError(
            "A directional Meld owner is outside the granted BASELINE namespace."
        )
    return binding.authority_context_name + public_name[len(binding.public_name) :]

class MemoryStoreMeldApplyPort(MeldApplyPort):
    """Preserve Meld's four Store/Grant transactions behind one typed port."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def _with_granted_source_lock(
        self,
        session: MeldSession,
        work: Callable[[], MeldApplyReceipt],
    ) -> MeldApplyReceipt:
        if session.granted_incoming is None:
            return work()
        # The granted read must remain byte-identical from final validation
        # through the participant-owned target checkpoint.
        with authority_grant_snapshot_lock() as registry:
            source_access = revalidate_granted_context_binding(
                session.granted_incoming,
                registry=registry,
            )
            with source_access.store._context_write_lock(source_access.context_name):
                return work()

    def apply_standard_target(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        return self._with_granted_source_lock(
            session,
            lambda: self._apply_standard_target_locked(
                session,
                expected_session_digest=expected_session_digest,
            ),
        )

    def _apply_standard_target_locked(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        store = self._store
        change_set = session.prepare_changes()
        left, right, direct_target = load_bound_meld_contexts(store, session)
        assert_meld_non_target_source_bindings(session, left, right)
        if session.state == "APPLIED":
            assert session.application is not None
            recovered = recover_meld_application(
                store=store,
                session=session,
                target=direct_target,
                change_set=change_set,
            )
            if (
                recovered is None
                or recovered[0] != session.application.checkpoint_uid
                or recovered[1] != session.application.result_memory_uids
            ):
                raise MeldApplicationError(
                    "The applied meld receipt no longer matches the current "
                    "target and checkpoint."
                )
            return MeldApplyReceipt(
                recovered=True,
                checkpoint_uid=session.application.checkpoint_uid,
                result_count=len(session.application.result_memory_uids),
            )
        recovered = recover_meld_application(
            store=store,
            session=session,
            target=direct_target,
            change_set=change_set,
        )
        if recovered is not None:
            checkpoint_uid, result_uids = recovered
            session.record_application(
                change_set_digest=change_set.digest,
                checkpoint_uid=checkpoint_uid,
                result_memory_uids=result_uids,
            )
            store.save_meld_session(
                session,
                expected_session_digest=expected_session_digest,
            )
            return MeldApplyReceipt(True, checkpoint_uid, len(result_uids))
        if context_record_digest(direct_target) != session.target.context_digest:
            raise MeldApplicationError(
                "The meld target changed and does not match a recoverable "
                "prior application."
            )

        target = store.load_for_update(session.target.context_name)
        assert_unapplied_meld_target(session, target)
        for proposal in change_set.proposals:
            memory = Memory(uid=proposal.memory_uid, content=proposal.content)
            if proposal.operation == "EDIT":
                target.replace(memory)
            else:
                target.add(memory)
        description = (
            (
                f"Melded INCOMING '{session.frames[0].context_name}' into "
                f"BASELINE '{target.name}': {len(change_set.proposals)} changes"
            )
            if session.mode == "DIRECTIONAL"
            else (
                f"Melded '{session.frames[0].context_name}' and "
                f"'{session.frames[1].context_name}' into "
                f"'{target.name}': {len(change_set.proposals)} results"
            )
        )
        checkpoint = store.save_meld_target(
            target,
            AutoCheckpoint(
                command="meld",
                args={"meld": meld_checkpoint_record(session, change_set)},
                description=description,
            ),
            expected_context_digest=session.target.context_digest,
            source_bindings=target_save_source_bindings(store, session),
        )
        if checkpoint is None:
            raise MeldApplicationError("Meld application created no checkpoint.")
        result_uids = tuple(proposal.memory_uid for proposal in change_set.proposals)
        session.record_application(
            change_set_digest=change_set.digest,
            checkpoint_uid=checkpoint.uid,
            result_memory_uids=result_uids,
        )
        store.save_meld_session(
            session,
            expected_session_digest=expected_session_digest,
        )
        return MeldApplyReceipt(False, checkpoint.uid, len(result_uids))

    def apply_local_owner_subtree(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        return self._with_granted_source_lock(
            session,
            lambda: self._apply_local_owner_subtree_locked(
                session,
                expected_session_digest=expected_session_digest,
            ),
        )

    def _apply_local_owner_subtree_locked(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        store = self._store
        change_set = session.prepare_changes()
        owners = affected_meld_owners(session, change_set)
        owner_proposals = {
            identity: tuple(
                proposal
                for proposal in change_set.proposals
                if (proposal.owner_context_uid, proposal.owner_context_name) == identity
            )
            for identity in owners
        }
        local_lock_names: set[str] = {name for _uid, name in owners}
        for index, frame in enumerate(session.frames):
            if (
                session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION
                and index == 0
            ):
                continue
            if index == 0 and session.granted_incoming is not None:
                continue
            local_lock_names.update(context.name for context in (frame.contexts or ()))

        receipts: tuple[MeldCheckpointReceipt, ...] | None = None
        result_uids: tuple[str, ...] = ()
        recovered_prior = False
        with store._command_write_lock():
            store._assert_profile_write_allowed()
            with store._context_write_locks(local_lock_names):
                left, right, target = load_bound_meld_contexts(store, session)
                assert_meld_non_target_source_bindings(session, left, right)
                recovered = recover_owner_aware_application(
                    session=session,
                    target=target,
                    change_set=change_set,
                    checkpoint_store=store,
                )
                if recovered is not None:
                    receipts, result_uids = recovered
                    recovered_prior = True
                elif session.state == "APPLIED":
                    raise MeldApplicationError(
                        "The applied Meld receipt no longer matches its target owners."
                    )
                else:
                    assert_unapplied_meld_target(session, target)
                    originals: dict[str, dict[str, object]] = {}
                    expected_digests: dict[str, str] = {}
                    post_images: dict[str, Context] = {}
                    for _context_uid, context_name in owners:
                        direct = store.load_direct(context_name)
                        originals[context_name] = direct.to_dict()
                        expected_digests[context_name] = context_record_digest(direct)
                        post_images[context_name] = apply_owner_proposals(
                            direct,
                            owner_proposals[(_context_uid, context_name)],
                        )
                    command_contexts = [
                        {"uid": context_uid, "name": context_name}
                        for context_uid, context_name in owners
                    ]
                    created: list[MeldCheckpointReceipt] = []
                    written_names: list[str] = []
                    try:
                        for context_uid, context_name in owners:
                            checkpoint = store._save_locked(
                                post_images[context_name],
                                AutoCheckpoint(
                                    command="meld",
                                    args={
                                        "meld": meld_checkpoint_record(
                                            session,
                                            change_set,
                                            owner=(context_uid, context_name),
                                        ),
                                        "command_contexts": command_contexts,
                                    },
                                    description=(
                                        f"Melded INCOMING "
                                        f"'{session.frames[0].context_name}' into "
                                        f"BASELINE subtree "
                                        f"'{session.target.context_name}': "
                                        f"{len(change_set.proposals)} changes"
                                    ),
                                ),
                                expected_context_digest=expected_digests[context_name],
                            )
                            if checkpoint is None:
                                raise MeldApplicationError(
                                    "Directional Meld application created no checkpoint."
                                )
                            written_names.append(context_name)
                            created.append(
                                MeldCheckpointReceipt(
                                    context_uid=context_uid,
                                    context_name=context_name,
                                    checkpoint_uid=checkpoint.uid,
                                )
                            )
                    except Exception:
                        rollback_error: Exception | None = None
                        for context_name in written_names:
                            try:
                                _write_json_atomic(
                                    store._context_file(context_name),
                                    originals[context_name],
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for receipt in created:
                            try:
                                _remove_checkpoint(
                                    store,
                                    receipt.context_name,
                                    receipt.checkpoint_uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Directional Meld failed and its target subtree "
                                "could not be fully rolled back."
                            ) from rollback_error
                        raise
                    receipts = tuple(created)
                    result_uids = tuple(
                        proposal.memory_uid for proposal in change_set.proposals
                    )

        assert receipts
        if session.state == "APPLIED":
            assert session.application is not None
            if (
                session.application.checkpoints != receipts
                or session.application.result_memory_uids != result_uids
            ):
                raise MeldApplicationError(
                    "The applied Meld receipt no longer matches its checkpoints."
                )
            return MeldApplyReceipt(True, receipts[0].checkpoint_uid, len(result_uids))
        session.record_application(
            change_set_digest=change_set.digest,
            checkpoint_uid=receipts[0].checkpoint_uid,
            result_memory_uids=result_uids,
            checkpoints=receipts,
        )
        store.save_meld_session(
            session,
            expected_session_digest=expected_session_digest,
        )
        return MeldApplyReceipt(
            recovered_prior,
            receipts[0].checkpoint_uid,
            len(result_uids),
        )

    def apply_granted_owner_subtree(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        store = self._store
        binding = session.granted_target
        if binding is None:
            raise ValueError("Expected a granted directional Meld target.")
        change_set = session.prepare_changes()
        owners = affected_meld_owners(session, change_set)
        owner_proposals = {
            identity: tuple(
                proposal
                for proposal in change_set.proposals
                if (proposal.owner_context_uid, proposal.owner_context_name) == identity
            )
            for identity in owners
        }

        with authority_grant_snapshot_lock() as registry:
            target_access = revalidate_granted_context_binding(
                binding,
                registry=registry,
            )
            validate_owner_aware_grant_permissions(
                session,
                change_set.proposals,
                registry=registry,
            )
            source_access = (
                revalidate_granted_context_binding(
                    session.granted_incoming,
                    registry=registry,
                )
                if session.granted_incoming is not None
                else ContextAccess(
                    store=store,
                    context_name=session.frames[0].context_name,
                    display_name=session.frames[0].context_name,
                    attachment_name=None,
                    permission="READ",
                )
            )
            authority_store = target_access.store
            source_store = source_access.store
            target_name_by_public = {
                context.name: granted_owner_name(binding, context.name)
                for context in (session.frames[1].contexts or ())
            }
            authority_lock_names = set(target_name_by_public.values())
            if session.granted_incoming is not None:
                source_binding = session.granted_incoming
                source_lock_names = {
                    granted_owner_name(source_binding, context.name)
                    for context in (session.frames[0].contexts or ())
                }
            else:
                source_lock_names = {
                    context.name for context in (session.frames[0].contexts or ())
                }

            recovered_prior = False
            receipts: tuple[MeldCheckpointReceipt, ...] | None = None
            result_uids: tuple[str, ...] = ()
            with ExitStack() as locks:
                if source_store.store_dir != authority_store.store_dir:
                    locks.enter_context(
                        source_store._context_write_locks(source_lock_names)
                    )
                locks.enter_context(authority_store._command_write_lock())
                authority_store._assert_profile_write_allowed()
                if source_store.store_dir == authority_store.store_dir:
                    authority_lock_names.update(source_lock_names)
                locks.enter_context(
                    authority_store._context_write_locks(authority_lock_names)
                )

                left, right, public_target = load_bound_meld_contexts(
                    store,
                    session,
                    registry=registry,
                )
                assert_meld_non_target_source_bindings(session, left, right)
                recovered = recover_owner_aware_application(
                    session=session,
                    target=public_target,
                    change_set=change_set,
                    checkpoint_store=authority_store,
                    checkpoint_name_by_public=target_name_by_public,
                )
                if recovered is not None:
                    receipts, result_uids = recovered
                    recovered_prior = True
                elif session.state == "APPLIED":
                    raise MeldApplicationError(
                        "The applied granted Meld receipt no longer matches "
                        "the authority BASELINE subtree."
                    )
                else:
                    assert_unapplied_meld_target(session, public_target)
                    originals: dict[str, dict[str, object]] = {}
                    expected_digests: dict[str, str] = {}
                    post_images: dict[str, Context] = {}
                    for context_uid, public_name in owners:
                        authority_name = target_name_by_public[public_name]
                        direct = authority_store.load_direct(authority_name)
                        if direct.uid != context_uid:
                            raise ConcurrentContextUpdateError(
                                "A granted BASELINE owner identity changed before Meld."
                            )
                        originals[authority_name] = direct.to_dict()
                        expected_digests[authority_name] = context_record_digest(direct)
                        post_images[authority_name] = apply_owner_proposals(
                            direct,
                            owner_proposals[(context_uid, public_name)],
                        )
                    physical_contexts = [
                        {
                            "uid": context_uid,
                            "name": target_name_by_public[public_name],
                        }
                        for context_uid, public_name in owners
                    ]
                    created: list[tuple[str, MeldCheckpointReceipt]] = []
                    written_names: list[str] = []
                    try:
                        for context_uid, public_name in owners:
                            authority_name = target_name_by_public[public_name]
                            checkpoint = authority_store._save_locked(
                                post_images[authority_name],
                                AutoCheckpoint(
                                    command="meld",
                                    args={
                                        "meld": meld_checkpoint_record(
                                            session,
                                            change_set,
                                            owner=(context_uid, public_name),
                                        ),
                                        "authority_target_context_name": (
                                            binding.authority_context_name
                                        ),
                                        "authority_owner_context_name": authority_name,
                                        "authority_grant": binding.to_dict(),
                                        "command_contexts": physical_contexts,
                                    },
                                    description=(
                                        f"Melded INCOMING "
                                        f"'{session.frames[0].context_name}' into "
                                        f"granted BASELINE subtree "
                                        f"'{session.target.context_name}': "
                                        f"{len(change_set.proposals)} changes"
                                    ),
                                ),
                                expected_context_digest=expected_digests[
                                    authority_name
                                ],
                            )
                            if checkpoint is None:
                                raise MeldApplicationError(
                                    "Granted Meld application created no checkpoint."
                                )
                            written_names.append(authority_name)
                            created.append(
                                (
                                    authority_name,
                                    MeldCheckpointReceipt(
                                        context_uid=context_uid,
                                        context_name=public_name,
                                        checkpoint_uid=checkpoint.uid,
                                    ),
                                )
                            )
                        receipts = tuple(receipt for _name, receipt in created)
                        result_uids = tuple(
                            proposal.memory_uid for proposal in change_set.proposals
                        )
                        session.record_application(
                            change_set_digest=change_set.digest,
                            checkpoint_uid=receipts[0].checkpoint_uid,
                            result_memory_uids=result_uids,
                            checkpoints=receipts,
                        )
                        store.save_meld_session(
                            session,
                            expected_session_digest=expected_session_digest,
                        )
                    except Exception:
                        rollback_error: Exception | None = None
                        for authority_name in written_names:
                            try:
                                _write_json_atomic(
                                    authority_store._context_file(authority_name),
                                    originals[authority_name],
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        for authority_name, receipt in created:
                            try:
                                _remove_checkpoint(
                                    authority_store,
                                    authority_name,
                                    receipt.checkpoint_uid,
                                )
                            except Exception as candidate:
                                rollback_error = rollback_error or candidate
                        if rollback_error is not None:
                            raise RuntimeError(
                                "Granted Meld failed and its authority BASELINE "
                                "subtree could not be fully rolled back."
                            ) from rollback_error
                        raise

            assert receipts
            if recovered_prior:
                if session.state == "APPLIED":
                    assert session.application is not None
                    if (
                        session.application.checkpoints != receipts
                        or session.application.result_memory_uids != result_uids
                    ):
                        raise MeldApplicationError(
                            "The granted Meld receipt no longer matches its "
                            "checkpoints."
                        )
                else:
                    session.record_application(
                        change_set_digest=change_set.digest,
                        checkpoint_uid=receipts[0].checkpoint_uid,
                        result_memory_uids=result_uids,
                        checkpoints=receipts,
                    )
                    store.save_meld_session(
                        session,
                        expected_session_digest=expected_session_digest,
                    )
            return MeldApplyReceipt(
                recovered_prior,
                receipts[0].checkpoint_uid,
                len(result_uids),
            )

    def apply_granted_target(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        store = self._store
        binding = session.granted_target
        if session.mode != "DIRECTIONAL" or binding is None:
            raise ValueError("Expected a granted directional Meld target.")
        change_set = session.prepare_changes()
        required_permissions = required_directional_target_permissions(change_set)

        with authority_grant_snapshot_lock() as registry:
            target_access = revalidate_granted_context_binding(
                binding,
                registry=registry,
            )
            for permission in required_permissions:
                revalidate_granted_context_binding(
                    binding,
                    required_permission=permission,
                    registry=registry,
                )
            source_access = (
                revalidate_granted_context_binding(
                    session.granted_incoming,
                    registry=registry,
                )
                if session.granted_incoming is not None
                else ContextAccess(
                    store=store,
                    context_name=session.frames[0].context_name,
                    display_name=session.frames[0].context_name,
                    attachment_name=None,
                    permission="READ",
                )
            )
            authority_store = target_access.store
            source_store = source_access.store
            source_lock_name = source_access.context_name
            target_lock_name = target_access.context_name

            with ExitStack() as locks:
                if source_store.store_dir != authority_store.store_dir:
                    locks.enter_context(
                        source_store._context_write_lock(source_lock_name)
                    )
                locks.enter_context(authority_store._command_write_lock())
                authority_store._assert_profile_write_allowed()
                authority_names = {target_lock_name}
                if source_store.store_dir == authority_store.store_dir:
                    authority_names.add(source_lock_name)
                locks.enter_context(
                    authority_store._context_write_locks(authority_names)
                )

                left, right, public_target = load_bound_meld_contexts(
                    store,
                    session,
                    registry=registry,
                )
                assert_meld_non_target_source_bindings(session, left, right)
                recovered = recover_meld_application(
                    store=store,
                    session=session,
                    target=public_target,
                    change_set=change_set,
                    checkpoint_store=authority_store,
                    checkpoint_context_name=target_lock_name,
                )
                if session.state == "APPLIED":
                    assert session.application is not None
                    if (
                        recovered is None
                        or recovered[0] != session.application.checkpoint_uid
                        or recovered[1] != session.application.result_memory_uids
                    ):
                        raise MeldApplicationError(
                            "The applied granted Meld receipt no longer matches "
                            "the authority BASELINE and checkpoint."
                        )
                    return MeldApplyReceipt(True, recovered[0], len(recovered[1]))
                if recovered is not None:
                    checkpoint_uid, result_uids = recovered
                    session.record_application(
                        change_set_digest=change_set.digest,
                        checkpoint_uid=checkpoint_uid,
                        result_memory_uids=result_uids,
                    )
                    store.save_meld_session(
                        session,
                        expected_session_digest=expected_session_digest,
                    )
                    return MeldApplyReceipt(
                        True,
                        checkpoint_uid,
                        len(result_uids),
                    )
                assert_unapplied_meld_target(session, public_target)

                direct = authority_store.load_direct(target_lock_name)
                original = direct.to_dict()
                post_image = Context.from_dict(direct.to_dict())
                post_image._store_digest = direct._store_digest
                for proposal in change_set.proposals:
                    memory = Memory(
                        uid=proposal.memory_uid,
                        content=proposal.content,
                    )
                    if proposal.operation == "EDIT":
                        post_image.replace(memory)
                    else:
                        post_image.add(memory)
                checkpoint = None
                try:
                    checkpoint = authority_store._save_locked(
                        post_image,
                        AutoCheckpoint(
                            command="meld",
                            args={
                                "meld": meld_checkpoint_record(session, change_set),
                                "authority_target_context_name": target_lock_name,
                                "authority_grant": binding.to_dict(),
                            },
                            description=(
                                f"Melded INCOMING "
                                f"'{session.frames[0].context_name}' into granted "
                                f"BASELINE '{session.target.context_name}': "
                                f"{len(change_set.proposals)} changes"
                            ),
                        ),
                        expected_context_digest=context_record_digest(direct),
                    )
                    if checkpoint is None:
                        raise MeldApplicationError(
                            "Granted Meld application created no checkpoint."
                        )
                    result_uids = tuple(
                        proposal.memory_uid for proposal in change_set.proposals
                    )
                    session.record_application(
                        change_set_digest=change_set.digest,
                        checkpoint_uid=checkpoint.uid,
                        result_memory_uids=result_uids,
                    )
                    store.save_meld_session(
                        session,
                        expected_session_digest=expected_session_digest,
                    )
                except Exception:
                    rollback_error = None
                    if checkpoint is not None:
                        try:
                            _write_json_atomic(
                                authority_store._context_file(target_lock_name),
                                original,
                            )
                        except Exception as candidate:
                            rollback_error = candidate
                        try:
                            _remove_checkpoint(
                                authority_store,
                                target_lock_name,
                                checkpoint.uid,
                            )
                        except Exception as candidate:
                            rollback_error = rollback_error or candidate
                    if rollback_error is not None:
                        raise RuntimeError(
                            "Granted Meld failed and its authority BASELINE could "
                            "not be fully rolled back."
                        ) from rollback_error
                    raise
        assert checkpoint is not None
        return MeldApplyReceipt(False, checkpoint.uid, len(result_uids))


def execute_meld_apply(
    request: MeldApplyRequest,
    *,
    store: MemoryStore,
) -> MeldApplyResult:
    """Apply one reviewed Meld through the production Store/Grant port."""

    return run_meld_apply(request, port=MemoryStoreMeldApplyPort(store))
