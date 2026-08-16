"""MemoryStore, Grant, checkpoint, recovery, and provider adapters for Meld."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import uuid

from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.comparison import COMPARISON_RULESET_VERSION, ComparisonAnalysis
from memcommit.comparison_store import load_comparison_analysis
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.context_targeting.loading import load_context_scope
from memcommit.granted_comparison_store import (
    granted_artifact_contexts,
    load_granted_comparison_artifact,
    recursive_comparison_projection,
)
from memcommit.granted_update_application import _remove_checkpoint
from memcommit.derived_policy import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.meld import (
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MeldCheckpointReceipt,
    MeldFrame,
    MeldSession,
    materialize_preservation_assessment,
    meld_canonical_digest,
)
from memcommit.meld_assessment_application import (
    FrozenMeldAssessment,
    MeldAssessmentPort,
    MeldAssessmentResult,
    MeldProviderFactory,
    run_meld_assessment,
)
from memcommit.meld_application import (
    MeldApplicationError,
    MeldApplyPort,
    MeldApplyReceipt,
    MeldApplyRequest,
    MeldApplyResult,
    run_meld_apply,
)
from memcommit.profiles import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.meld_provider import meld_turn_request_digest
from memcommit.meld_resolution_cache import (
    MeldResolutionBranch,
    configured_meld_cache_identity,
    meld_resolution_cache_key,
)
from memcommit.meld_restart_application import (
    MeldRestartError,
    MeldRestartPort,
    MeldRestartRequest,
    MeldRestartResult,
    run_meld_restart,
)
from memcommit.meld_session_application import (
    MeldDestinationPort,
    MeldDestinationRequest,
    MeldPreservationPort,
    MeldSessionRepository,
    MeldSessionSnapshot,
    run_meld_destination_change,
    run_meld_preservation,
    run_meld_session_defer,
    run_meld_session_open,
)
from memcommit.meld_start_application import (
    MeldStartError,
    MeldStartOrigin,
    MeldStartPort,
    MeldStartRequest,
    MeldStartResult,
    run_meld_start,
)
from memcommit.provider_types import ProviderIdentity
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
    validate_context_name,
)
from memcommit.study_prewarm.meld_resolution import (
    find_installed_meld_resolution_branch,
)
from memcommit.study_prewarm.meld_directional import (
    find_installed_directional_meld_prewarm,
)


def load_meld_source(
    access: ContextAccess,
    *,
    include_descendants: bool = False,
    project: bool = True,
) -> Context:
    """Load one authorized source with Meld's established projection meaning."""

    if include_descendants:
        reader = GrantedReadStore(access) if access.is_granted else access.store
        context = load_context_scope(
            reader,
            access.display_name if access.is_granted else access.context_name,
            include_descendants=True,
        )
    else:
        context = (
            (
                GrantedReadStore(access).load(access.display_name)
                if project
                else GrantedReadStore(access).load_direct(access.display_name)
            )
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
    return recursive_comparison_projection(context) if project else context


def load_local_meld_source(
    store: MemoryStore,
    name: str,
    *,
    include_descendants: bool,
    project: bool = True,
) -> Context:
    """Load one local source under the same exact/descendant projection rules."""

    if not include_descendants:
        return store.load_direct(name)
    context = load_context_scope(store, name, include_descendants=True)
    return recursive_comparison_projection(context) if project else context


def load_bound_meld_contexts(
    store: MemoryStore,
    session: MeldSession,
    *,
    registry=None,
) -> tuple[Context, Context, Context]:
    """Reload the exact frozen frames and application target for one session."""

    if session.mode == "DIRECTIONAL" and (
        session.granted_incoming is not None
        or session.granted_target is not None
    ):
        bindings = (session.granted_incoming, session.granted_target)
        loaded = []
        for frame, binding in zip(session.frames, bindings, strict=True):
            if binding is None:
                access = ContextAccess(
                    store=store,
                    context_name=frame.context_name,
                    display_name=frame.context_name,
                    attachment_name=None,
                    permission="READ",
                )
            else:
                access = revalidate_granted_context_binding(
                    binding,
                    registry=registry,
                )
            loaded.append(
                load_meld_source(
                    access,
                    include_descendants=bool(frame.include_descendants),
                    project=(
                        session.schema_version < MELD_OWNER_AWARE_SCHEMA_VERSION
                    ),
                )
            )
        left, right = loaded
        return left, right, right
    try:
        loaded = []
        for frame in session.frames:
            if (
                session.mode == "DIRECTIONAL"
                and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
            ):
                context = load_context_scope(
                    store,
                    frame.context_name,
                    include_descendants=bool(frame.include_descendants),
                )
            else:
                context = (
                    recursive_comparison_projection(
                        load_context_scope(
                            store,
                            frame.context_name,
                            include_descendants=bool(frame.include_descendants),
                        )
                    )
                    if frame.include_descendants
                    else store.load_direct(frame.context_name)
                )
            loaded.append(context)
        left, right = loaded
    except FileNotFoundError:
        if session.mode != "SYMMETRIC" or session.comparison_seed is None:
            raise
        artifact = load_granted_comparison_artifact(
            store,
            session.frames[0].context_uid,
            session.frames[1].context_uid,
        )
        if artifact is None:
            raise MeldApplicationError(
                "The granted Compare basis for this Meld is unavailable."
            )
        left, right = granted_artifact_contexts(store, artifact)
    target = (
        right
        if session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
        else store.load_direct(session.target.context_name)
    )
    return left, right, target


def meld_bound_frame_digest(frame, context: Context) -> str:
    if frame.contexts is None:
        return context_record_digest(context)
    return MeldFrame.from_context(
        context,
        role=frame.role,
        include_descendants=frame.include_descendants,
        owner_aware=True,
    ).context_digest


def assert_meld_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    """Reject any source identity or digest drift since analysis."""

    for frame, context in zip(session.frames, (left, right), strict=True):
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or meld_bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldApplicationError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def assert_meld_non_target_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    """Recheck read-only inputs while allowing an applied baseline to differ."""

    for frame, context in zip(session.frames, (left, right), strict=True):
        if (
            frame.context_uid == session.target.context_uid
            and frame.context_name == session.target.context_name
        ):
            continue
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or meld_bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldApplicationError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def assert_unapplied_meld_target(session: MeldSession, target: Context) -> None:
    target_digest = (
        meld_bound_frame_digest(session.frames[1], target)
        if session.mode == "DIRECTIONAL"
        else context_record_digest(target)
    )
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
        or target_digest != session.target.context_digest
    ):
        raise MeldApplicationError(
            "The meld target changed after analysis; the proposal is stale."
        )


def walk_meld_target_contexts(root: Context) -> tuple[Context, ...]:
    contexts: list[Context] = []
    seen: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen:
            return
        seen.add(context.uid)
        contexts.append(context)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    return tuple(contexts)


def target_save_source_bindings(
    store: MemoryStore,
    session: MeldSession,
) -> tuple[tuple[str, str, str], ...]:
    """Return live local sources that must stay locked through target CAS."""

    if session.mode == "SYMMETRIC" and session.comparison_seed is not None:
        artifact = load_granted_comparison_artifact(
            store,
            session.frames[0].context_uid,
            session.frames[1].context_uid,
        )
        if artifact is not None and artifact.retention == "RETAINED":
            return ()
    bindings: list[tuple[str, str, str]] = []
    for index, frame in enumerate(session.frames):
        if (
            frame.context_uid == session.target.context_uid
            and frame.context_name == session.target.context_name
        ) or (
            session.mode == "DIRECTIONAL"
            and index == 0
            and session.granted_incoming is not None
        ):
            continue
        if session.mode == "SYMMETRIC" and frame.include_descendants:
            scope = load_context_scope(
                store,
                frame.context_name,
                include_descendants=True,
            )
            projected = recursive_comparison_projection(scope)
            if (
                projected.uid != frame.context_uid
                or projected.name != frame.context_name
                or context_record_digest(projected) != frame.context_digest
            ):
                raise MeldApplicationError(
                    f"Source Context '{frame.context_name}' changed after this "
                    "meld was analyzed."
                )
            physical_contexts = tuple(
                store.load_direct(context.name)
                for context in walk_meld_target_contexts(scope)
            )
            bindings.extend(
                (context.name, context.uid, context_record_digest(context))
                for context in physical_contexts
            )
            reloaded_scope = load_context_scope(
                store,
                frame.context_name,
                include_descendants=True,
            )
            if (
                context_record_digest(
                    recursive_comparison_projection(reloaded_scope)
                )
                != frame.context_digest
            ):
                raise MeldApplicationError(
                    f"Source Context '{frame.context_name}' changed after this "
                    "meld was analyzed."
                )
            continue
        bindings.append((frame.context_name, frame.context_uid, frame.context_digest))
    return tuple(bindings)


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
        "schema_version": 3 if owner_aware else 2 if session.mode == "DIRECTIONAL" else 1,
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
    if target.uid != session.target.context_uid or target.name != session.target.context_name:
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
    if target.uid != session.target.context_uid or target.name != session.target.context_name:
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


def _start_comparison(
    request: MeldStartRequest | MeldRestartRequest,
    *,
    store: MemoryStore,
    left: Context,
    right: Context,
    error_type: type[RuntimeError] = MeldStartError,
) -> ComparisonAnalysis | None:
    if request.incoming_memory is not None or request.baseline_memory is not None:
        return None
    analysis = request.comparison
    if analysis is None:
        analysis = load_comparison_analysis(
            left.uid,
            right.uid,
            store=store,
        )
        if analysis is None:
            artifact = load_granted_comparison_artifact(store, left.uid, right.uid)
            analysis = artifact.analysis if artifact is not None else None
    if analysis is None:
        if request.mode == "DIRECTIONAL":
            return None
        raise error_type(
            "Symmetric Meld requires an exact saved ordered Compare analysis."
        )
    if (
        not analysis.matches(left, right)
        or analysis.include_descendants
        != (request.left_descendants, request.right_descendants)
        or analysis.ruleset_version != COMPARISON_RULESET_VERSION
    ):
        raise error_type("The saved ordered Compare analysis is stale.")
    return analysis


def _execute_initial_meld(
    request: MeldStartRequest | MeldRestartRequest,
    *,
    store: MemoryStore,
    provider_factory,
    expected_session_digest: str | None,
    create_target: bool,
    error_type: type[RuntimeError],
) -> tuple[MeldSession, MeldStartOrigin]:
    """Build and publish one initial review under a create-or-replace token."""

    current_name = store.current_context_name()
    left_access = resolve_context_access(
        store,
        request.left_name,
        current_name=current_name,
        required_permission="READ",
    )
    right_access = resolve_context_access(
        store,
        request.right_name,
        current_name=current_name,
        required_permission="READ",
    )
    authorize_combination((left_access, right_access))

    if request.mode == "DIRECTIONAL":
        authorize_derived_transfer(left_access, right_access)
        retention = analysis_retention((left_access, right_access))
        if retention is None:
            raise error_type(
                "The directional Meld cannot retain its reviewed analysis."
            )
        authorize_analysis_save(
            (left_access, right_access),
            retention=retention,
        )
        target_access = right_access
    else:
        if create_target:
            store.assert_context_creatable(request.target_name)
            target_access = ContextAccess(
                store=store,
                context_name=request.target_name,
                display_name=request.target_name,
                attachment_name=None,
                permission="READ",
            )
        else:
            target_access = resolve_context_access(
                store,
                request.target_name,
                current_name=current_name,
                required_permission="READ",
            )
            if target_access.is_granted:
                raise error_type("Symmetric Meld requires a local Result Context.")
        authorize_derived_transfer(left_access, target_access)
        authorize_derived_transfer(right_access, target_access)

    project = request.mode == "SYMMETRIC"
    left = load_meld_source(
        left_access,
        include_descendants=request.left_descendants,
        project=project,
    )
    right = load_meld_source(
        right_access,
        include_descendants=request.right_descendants,
        project=project,
    )

    if request.mode == "DIRECTIONAL":
        target = right
    elif create_target:
        target = Context(uid=str(uuid.uuid4()), name=request.target_name)
    else:
        target = store.load_direct(request.target_name)
        if tuple(target.iter_items()):
            raise error_type("Symmetric Meld Result must remain empty.")

    prior = store.load_meld_session(target.uid)
    if expected_session_digest is None:
        if prior is not None:
            raise error_type("The Meld target already owns a saved session.")
    else:
        if prior is None:
            raise ConcurrentContextUpdateError(
                "The Meld session disappeared before restart."
            )
        if meld_canonical_digest(prior.to_dict()) != expected_session_digest:
            raise ConcurrentContextUpdateError(
                "The Meld session changed before restart."
            )

    comparison = _start_comparison(
        request,
        store=store,
        left=recursive_comparison_projection(left),
        right=recursive_comparison_projection(right),
        error_type=error_type,
    )
    if request.mode == "DIRECTIONAL":
        granted_incoming = (
            freeze_granted_context_binding(left_access)
            if left_access.is_granted
            else None
        )
        granted_target = (
            freeze_granted_context_binding(right_access)
            if right_access.is_granted
            else None
        )
        session = (
            MeldSession.create_directional(
                left,
                right,
                incoming_descendants=request.left_descendants,
                baseline_descendants=request.right_descendants,
                granted_incoming=granted_incoming,
                granted_target=granted_target,
                incoming_memory_selector=request.incoming_memory,
                baseline_memory_selector=request.baseline_memory,
            )
            if comparison is None
            else MeldSession.create_directional_from_comparison(
                comparison,
                left,
                right,
                granted_incoming=granted_incoming,
                granted_target=granted_target,
            )
        )
        session.start_initial_analysis()
        prepared = find_installed_directional_meld_prewarm(
            store=store,
            current=session,
        )
        if prepared is None:
            frozen, assessment_port = prepare_meld_assessment(
                session,
                store=store,
                expected_session_digest=expected_session_digest,
            )
            session = execute_meld_assessment(
                frozen,
                port=assessment_port,
                provider_factory=provider_factory,
            ).session
            origin = "PROVIDER"
        else:
            session = prepared.session
            left_live, right_live, target_live = load_bound_meld_contexts(
                store,
                session,
            )
            assert_meld_source_bindings(session, left_live, right_live)
            assert_unapplied_meld_target(session, target_live)
            if session.granted_target is not None:
                assessment = session.current_assessment
                assert assessment is not None
                with authority_grant_snapshot_lock() as registry:
                    revalidate_granted_context_binding(
                        session.granted_target,
                        registry=registry,
                    )
                    validate_owner_aware_grant_permissions(
                        session,
                        assessment.proposals,
                        registry=registry,
                    )
            store.save_meld_session(
                session,
                expected_session_digest=expected_session_digest,
            )
            origin = prepared.origin
    else:
        assert comparison is not None
        session = MeldSession.create_symmetric_from_comparison(comparison, target)
        assert_meld_source_bindings(session, left, right)
        assert_unapplied_meld_target(session, target)
        if create_target:
            store.create_meld_target_with_session(
                target,
                session,
                AutoCheckpoint(
                    command="meld",
                    args={
                        "left": request.left_name,
                        "right": request.right_name,
                        "to": request.target_name,
                    },
                    description=(
                        f"Initialized symmetric Meld result "
                        f"'{request.target_name}' from "
                        f"'{request.left_name}' and '{request.right_name}'"
                    ),
                ),
            )
        else:
            store.save_meld_session(
                session,
                expected_session_digest=expected_session_digest,
            )
        origin = "SAVED_COMPARISON"
    return session, origin


@dataclass
class MemoryStoreMeldStartPort(MeldStartPort):
    """Authorize and publish a new target-scoped Meld without interface code."""

    store: MemoryStore

    def start(
        self,
        request: MeldStartRequest,
        *,
        provider_factory,
    ) -> MeldStartResult:
        session, origin = _execute_initial_meld(
            request,
            store=self.store,
            provider_factory=provider_factory,
            expected_session_digest=None,
            create_target=request.create_target,
            error_type=MeldStartError,
        )
        return MeldStartResult(
            session=session,
            origin=origin,
            created_target=request.create_target,
        )


def execute_meld_start(
    request: MeldStartRequest,
    *,
    store: MemoryStore,
    provider_factory,
) -> MeldStartResult:
    """Start one complete Meld through the production Store/Grant adapter."""

    return run_meld_start(
        request,
        port=MemoryStoreMeldStartPort(store),
        provider_factory=provider_factory,
    )


@dataclass
class MemoryStoreMeldRestartPort(MeldRestartPort):
    """CAS-replace an existing target-scoped Meld without interface code."""

    store: MemoryStore

    def restart(
        self,
        request: MeldRestartRequest,
        *,
        provider_factory,
    ) -> MeldRestartResult:
        session, origin = _execute_initial_meld(
            request,
            store=self.store,
            provider_factory=provider_factory,
            expected_session_digest=request.expected_version,
            create_target=False,
            error_type=MeldRestartError,
        )
        return MeldRestartResult(session=session, origin=origin)


def execute_meld_restart(
    request: MeldRestartRequest,
    *,
    store: MemoryStore,
    provider_factory,
) -> MeldRestartResult:
    """Restart one Meld through the production Store/Grant adapter."""

    return run_meld_restart(
        request,
        port=MemoryStoreMeldRestartPort(store),
        provider_factory=provider_factory,
    )


@dataclass
class MemoryStoreMeldSessionRepository(MeldSessionRepository):
    """Target-scoped Meld persistence with opaque canonical-digest CAS tokens."""

    store: MemoryStore

    @staticmethod
    def _snapshot(session: MeldSession) -> MeldSessionSnapshot:
        return MeldSessionSnapshot(
            session=session,
            version_token=meld_canonical_digest(session.to_dict()),
        )

    def load(self, target_context_uid: str) -> MeldSessionSnapshot:
        session = self.store.load_meld_session(target_context_uid)
        if session is None:
            raise FileNotFoundError(
                f"No saved Meld session for target {target_context_uid!r}."
            )
        return self._snapshot(session)

    def replace(
        self,
        session: MeldSession,
        *,
        expected_version: str,
    ) -> MeldSessionSnapshot:
        self.store.save_meld_session(
            session,
            expected_session_digest=expected_version,
        )
        return self._snapshot(session)


@dataclass
class MemoryStoreMeldPreservationPort(MeldPreservationPort):
    """Revalidate and publish one provider-free symmetric preserve-all turn."""

    store: MemoryStore

    def materialize(
        self,
        snapshot: MeldSessionSnapshot,
        session: MeldSession,
    ) -> MeldSessionSnapshot:
        assessment = materialize_preservation_assessment(session)
        left, right, target = load_bound_meld_contexts(self.store, session)
        assert_meld_source_bindings(session, left, right)
        assert_unapplied_meld_target(session, target)
        current = session.current_turn
        assert current is not None
        session.record_assessment(current.uid, assessment)
        return MemoryStoreMeldSessionRepository(self.store).replace(
            session,
            expected_version=snapshot.version_token,
        )


@dataclass
class MemoryStoreMeldDestinationPort(MeldDestinationPort):
    """Relocate one empty symmetric Result and its target-scoped session."""

    store: MemoryStore

    def relocate(self, request: MeldDestinationRequest) -> MeldSessionSnapshot:
        destination = request.destination_name
        validate_context_name(destination)
        session = request.snapshot.session
        descendants = tuple(
            name
            for name in self.store.list_context_names()
            if name.startswith(session.target.context_name + "/")
        )
        if descendants:
            raise ValueError(
                "A symmetric Meld save location with descendants cannot be moved "
                "from the review workbench."
            )
        current = MemoryStoreMeldSessionRepository(self.store).load(
            session.target.context_uid
        )
        if current.version_token != request.snapshot.version_token:
            raise MeldApplicationError(
                "The Meld session changed before its destination could move."
            )
        plan = self.store.plan_context_rename(
            session.target.context_name,
            destination,
        )
        self.store.rename_contexts(plan)
        relocated = self.store.load_meld_session(session.target.context_uid)
        if relocated is None or relocated.uid != session.uid:
            raise MeldApplicationError(
                "The relocated Meld session could not be reloaded."
            )
        return MemoryStoreMeldSessionRepository._snapshot(relocated)


def execute_meld_session_open(
    target_context_uid: str,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_session_open(
        target_context_uid,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_session_defer(
    snapshot: MeldSessionSnapshot,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_session_defer(
        snapshot,
        repository=MemoryStoreMeldSessionRepository(store),
    )


def execute_meld_preservation(
    pending,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_preservation(
        pending,
        port=MemoryStoreMeldPreservationPort(store),
    )


def execute_meld_destination_change(
    request: MeldDestinationRequest,
    *,
    store: MemoryStore,
) -> MeldSessionSnapshot:
    return run_meld_destination_change(
        request,
        port=MemoryStoreMeldDestinationPort(store),
    )


@dataclass(frozen=True)
class _MeldAssessmentToken:
    owner: object
    cacheable: bool
    request_digest: str | None
    configured_provider: dict[str, object] | None
    cached_branch: MeldResolutionBranch | None
    branch_from_study_prewarm: bool


class MemoryStoreMeldAssessmentPort(MeldAssessmentPort):
    """Freeze hidden resolution branches and publish one assessed session CAS."""

    def __init__(self, store: MemoryStore):
        self._store = store
        self._owner = object()

    def freeze(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str | None,
    ) -> FrozenMeldAssessment:
        current = session.current_turn
        cacheable = (
            current is not None
            and current.sequence > 0
            and current.scope in {"ALL", "REMAINING"}
        )
        request_digest: str | None = None
        configured_provider: dict[str, object] | None = None
        cached_branch = None
        from_study_prewarm = False
        if cacheable:
            request_digest = meld_turn_request_digest(session)
            configured_provider = configured_meld_cache_identity()
            cache_key = meld_resolution_cache_key(
                request_digest,
                configured_provider,
            )
            cached_branch = self._store.load_meld_resolution_branch(cache_key)
            if cached_branch is None:
                cached_branch = find_installed_meld_resolution_branch(
                    store=self._store,
                    branch_key=cache_key,
                )
                from_study_prewarm = cached_branch is not None
        return FrozenMeldAssessment(
            session=session,
            expected_session_digest=expected_session_digest,
            cached_completion=(
                cached_branch.completion if cached_branch is not None else None
            ),
            token=_MeldAssessmentToken(
                owner=self._owner,
                cacheable=cacheable,
                request_digest=request_digest,
                configured_provider=configured_provider,
                cached_branch=cached_branch,
                branch_from_study_prewarm=from_study_prewarm,
            ),
        )

    def commit(
        self,
        frozen: FrozenMeldAssessment,
        *,
        session: MeldSession,
        assessment,
        completion: str | None,
        origin_provider: object | None,
    ) -> MeldSession:
        token = frozen.token
        if not isinstance(token, _MeldAssessmentToken) or token.owner is not self._owner:
            raise MeldApplicationError(
                "Meld assessment binding belongs to another runtime port."
            )
        left, right, target = load_bound_meld_contexts(self._store, session)
        assert_meld_source_bindings(session, left, right)
        assert_unapplied_meld_target(session, target)
        if session.granted_target is not None:
            if session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION:
                with authority_grant_snapshot_lock() as registry:
                    revalidate_granted_context_binding(
                        session.granted_target,
                        registry=registry,
                    )
                    validate_owner_aware_grant_permissions(
                        session,
                        assessment.proposals,
                        registry=registry,
                    )
            else:
                required = {
                    "UPDATE" if proposal.operation == "EDIT" else "CREATE"
                    for proposal in assessment.proposals
                }
                missing = sorted(
                    required - set(session.granted_target.permissions)
                )
                if missing:
                    raise ProfileError(
                        "The BASELINE Grant does not authorize "
                        + " + ".join(missing)
                        + " required by the proposed Meld changes."
                    )
        if token.cacheable and (
            token.cached_branch is None or token.branch_from_study_prewarm
        ):
            if token.cached_branch is None:
                if (
                    token.request_digest is None
                    or token.configured_provider is None
                    or completion is None
                ):
                    raise MeldApplicationError(
                        "Meld cache publication lacks complete provider evidence."
                    )
                branch = MeldResolutionBranch.create(
                    session=session,
                    request_digest=token.request_digest,
                    configured_provider=token.configured_provider,
                    origin_provider=(
                        origin_provider
                        if isinstance(origin_provider, ProviderIdentity)
                        else None
                    ),
                    completion=completion,
                )
            else:
                branch = token.cached_branch
            self._store.save_meld_resolution_branch(branch)
        self._store.save_meld_session(
            session,
            expected_session_digest=frozen.expected_session_digest,
        )
        return session


def prepare_meld_assessment(
    session: MeldSession,
    *,
    store: MemoryStore,
    expected_session_digest: str | None,
) -> tuple[FrozenMeldAssessment, MemoryStoreMeldAssessmentPort]:
    """Freeze one assessment and return its owning production port."""

    port = MemoryStoreMeldAssessmentPort(store)
    return (
        port.freeze(
            session,
            expected_session_digest=expected_session_digest,
        ),
        port,
    )


def execute_meld_assessment(
    frozen: FrozenMeldAssessment,
    *,
    port: MemoryStoreMeldAssessmentPort,
    provider_factory: MeldProviderFactory,
    observer=None,
) -> MeldAssessmentResult:
    """Execute one frozen semantic turn through its owning production port."""

    return run_meld_assessment(
        frozen,
        port=port,
        provider_factory=provider_factory,
        observer=observer,
    )


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
                if (proposal.owner_context_uid, proposal.owner_context_name)
                == identity
            )
            for identity in owners
        }
        local_lock_names: set[str] = {name for _uid, name in owners}
        for index, frame in enumerate(session.frames):
            if index == 0 and session.granted_incoming is not None:
                continue
            local_lock_names.update(
                context.name for context in (frame.contexts or ())
            )

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
                if (proposal.owner_context_uid, proposal.owner_context_name)
                == identity
            )
            for identity in owners
        }

        with authority_grant_snapshot_lock() as registry:
            target_access = revalidate_granted_context_binding(
                binding,
                registry=registry,
            )
            authority_source = target_access.view.authority.source or {}
            if (
                target_access.view.authority.name.casefold() == "study-baseline"
                or authority_source.get("kind") == "STUDY_BASELINE"
            ):
                raise MeldApplicationError(
                    "The fixed study-baseline Profile cannot be updated."
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
                                expected_context_digest=expected_digests[authority_name],
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
                            proposal.memory_uid
                            for proposal in change_set.proposals
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
            authority_source = target_access.view.authority.source or {}
            if (
                target_access.view.authority.name.casefold() == "study-baseline"
                or authority_source.get("kind") == "STUDY_BASELINE"
            ):
                raise MeldApplicationError(
                    "The fixed study-baseline Profile cannot be updated."
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


__all__ = [
    "MemoryStoreMeldApplyPort",
    "MemoryStoreMeldAssessmentPort",
    "MemoryStoreMeldDestinationPort",
    "MemoryStoreMeldPreservationPort",
    "MemoryStoreMeldSessionRepository",
    "MemoryStoreMeldStartPort",
    "assert_meld_non_target_source_bindings",
    "assert_meld_source_bindings",
    "assert_unapplied_meld_target",
    "execute_meld_apply",
    "execute_meld_assessment",
    "execute_meld_destination_change",
    "execute_meld_preservation",
    "execute_meld_session_defer",
    "execute_meld_session_open",
    "execute_meld_start",
    "load_bound_meld_contexts",
    "load_local_meld_source",
    "load_meld_source",
    "meld_bound_frame_digest",
    "prepare_meld_assessment",
]
