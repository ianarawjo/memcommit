"""Create, ground, resume, and explicitly apply bounded Context melds."""

from __future__ import annotations

import hashlib
import shlex
import sys
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
)
from memcommit.comparison_store import load_comparison_analysis
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.context_locator import resolve_context_locator
from memcommit.commands.granted_context import (
    ContextAccess,
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.derived_policy import (
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.granted_comparison_store import (
    granted_artifact_contexts,
    load_granted_comparison_artifact,
    recursive_comparison_projection,
)
from memcommit.meld import (
    MELD_SCHEMA_VERSION,
    MeldError,
    MeldIssue,
    MeldSession,
    materialize_preservation_assessment,
    meld_accounting,
    meld_canonical_digest,
)
from memcommit.meld_provider import (
    MeldProviderError,
    assess_meld_turn,
)
from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.commands.meld_shell import run_meld_shell
from memcommit.commands.meld_sessions import (
    MeldSessionCatalogEntry,
    MeldSessionCatalogError,
    list_meld_session_catalog,
    reload_selected_meld_session,
)
from memcommit.commands.session_picker import (
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.query_provider import (
    CodexChatGPTProvider,
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)


# A full 150 + 150 Task 2 Meld must return a complete relation ledger and
# proposal set in one call. Live runs can exceed the five-minute Compare-sized
# window, so keep the longer allowance local to Meld rather than weakening
# timeouts for every semantic command.
MELD_AGGREGATE_TIMEOUT_SECONDS = 900


class MeldCommandError(RuntimeError):
    """Safe user-facing orchestration failure."""


def _comparison_prerequisite_error(
    *,
    left: Context,
    right: Context,
    target: Context,
    refresh: bool,
    reason: str,
    create_target: bool = False,
) -> MeldCommandError:
    compare_argv = ["mem", "compare", "--to", right.name]
    if refresh:
        compare_argv.append("--refresh")
    rerun_argv = ["mem", "meld", left.name, right.name]
    if create_target:
        rerun_argv.extend(("--to", target.name))
    lines = [
        reason,
        "Create the exact ordered Compare basis first:",
        f"  {shlex.join(['mem', 'switch', left.name])}",
        f"  {shlex.join(compare_argv)}",
    ]
    if not create_target:
        lines.append(f"  {shlex.join(['mem', 'switch', target.name])}")
    lines.extend(("Then rerun:", f"  {shlex.join(rerun_argv)}"))
    return MeldCommandError("\n".join(lines))


def _load_symmetric_comparison(
    *,
    left: Context,
    right: Context,
    target: Context,
    create_target: bool = False,
) -> ComparisonAnalysis:
    """Load the exact reviewed LEFT→RIGHT basis; never use a reverse slot."""
    try:
        analysis = load_comparison_analysis(left.uid, right.uid)
        if analysis is None:
            artifact = load_granted_comparison_artifact(
                MemoryStore(create=False),
                left.uid,
                right.uid,
            )
            analysis = artifact.analysis if artifact is not None else None
    except ValueError as error:
        raise _comparison_prerequisite_error(
            left=left,
            right=right,
            target=target,
            refresh=True,
            reason="The saved ordered Compare analysis is invalid.",
            create_target=create_target,
        ) from error
    if analysis is None:
        raise _comparison_prerequisite_error(
            left=left,
            right=right,
            target=target,
            refresh=False,
            reason=(
                f"Meld requires a saved Compare analysis for "
                f"'{left.name}' → '{right.name}'."
            ),
            create_target=create_target,
        )
    if (
        not analysis.matches(left, right)
        or analysis.ruleset_version != COMPARISON_RULESET_VERSION
    ):
        raise _comparison_prerequisite_error(
            left=left,
            right=right,
            target=target,
            refresh=True,
            reason=(
                f"The saved Compare analysis for '{left.name}' → "
                f"'{right.name}' is stale."
            ),
            create_target=create_target,
        )
    return analysis


def _session_command(session: MeldSession) -> str:
    """Return one explicit, portable command prefix for this saved meld."""
    if session.mode == "DIRECTIONAL":
        return (
            f"mem meld {session.frames[0].context_name} "
            f"--into {session.frames[1].context_name}"
        )
    return f"mem meld {session.frames[0].context_name} {session.frames[1].context_name}"


def _session_route(session: MeldSession) -> str:
    if session.mode == "DIRECTIONAL":
        return (
            f"INCOMING {session.frames[0].context_name} → "
            f"BASELINE / TARGET {session.frames[1].context_name}"
        )
    return (
        f"{session.frames[0].context_name} + "
        f"{session.frames[1].context_name} → "
        f"{session.target.context_name}"
    )


def _preserve_all_guidance(session: MeldSession) -> str:
    if session.mode == "DIRECTIONAL":
        return (
            "Preserve the BASELINE except where supported INCOMING evidence "
            "explicitly corrects it. Retain supported incoming distinctions "
            "with explicit scope and provenance."
        )
    return (
        "Preserve every remaining supported source distinction with explicit "
        "scope and provenance. Do not present unresolved alternatives as one "
        "consistent rule."
    )


def _connect_meld_provider(provider_factory):
    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        provider.timeout = max(
            provider.timeout,
            MELD_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


def _single_line(value: str, *, limit: int = 90) -> str:
    normalized = " ".join(safe_terminal_text(value).split())
    return (
        normalized
        if len(normalized) <= limit
        else normalized[: limit - 1].rstrip() + "…"
    )


def _issue_selector(
    session: MeldSession,
    selector: str,
) -> MeldIssue:
    assessment = session.current_assessment
    if assessment is None:
        raise MeldCommandError("The meld has no assessed issues.")
    ordered_issues = sorted(
        assessment.issues,
        key=lambda item: 0 if item.priority == "REQUIRED" else 1,
    )
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(ordered_issues):
            return ordered_issues[index - 1]
    matches = [issue for issue in assessment.issues if issue.uid.startswith(selector)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise MeldCommandError(f"No meld issue matches '{selector}'.")
    raise MeldCommandError(f"Meld issue selector '{selector}' is ambiguous.")


def render_meld_session(
    session: MeldSession,
    *,
    expanded_issue_uid: str | None = None,
) -> str:
    """Render one provider-free snapshot over a saved meld session."""
    lines = [
        f"MEM MELD · {session.mode}",
        _session_route(session),
    ]
    if session.comparison_seed is not None:
        lines.append(f"Compare: {session.comparison_seed.analysis.uid[:8]} · IMPORTED")
    lines.append(f"State: {session.state} · Round: {len(session.turns)}")
    assessment = session.current_assessment
    if assessment is None:
        lines.extend(["", "Analysis is pending."])
        return "\n".join(lines)
    accounting = meld_accounting(session)
    lines.extend(
        [
            "",
            "WHAT MEM UNDERSTOOD",
            safe_terminal_text(assessment.overview),
            "",
            (
                f"RELATIONS · {len(assessment.relations)}  "
                f"ISSUES · {len(assessment.issues)}  "
                f"RESULTS · {len(assessment.proposals)}"
            ),
            "",
            "ACCOUNTING",
            (
                f"  Source coverage: {accounting.represented_sources}/"
                f"{accounting.source_memories}"
            ),
            (
                f"  Relation coverage: {accounting.represented_relations}/"
                f"{accounting.primary_relations}"
            ),
            (
                f"  Final Memories: {accounting.final_memories} · "
                f"PRESERVE {accounting.preserve_results} · "
                f"COALESCE {accounting.coalesce_results} · "
                f"SYNTHESIZE {accounting.synthesize_results} · "
                f"USER_ADD {accounting.user_add_results}"
            ),
            (
                f"  Open issues: REQUIRED {accounting.required_issues} · "
                f"HELPFUL {accounting.helpful_issues}"
            ),
            f"  Cross-relation results: {accounting.cross_relation_results}",
        ]
    )
    for index, relation in enumerate(assessment.relations, start=1):
        marker = "?" if relation.status == "UNRESOLVED" else "✓"
        lines.append(
            f"  {marker} R{index}. {relation.kind} · {_single_line(relation.summary)}"
        )
    lines.extend(["", "ISSUES"])
    relation_number = {
        relation.uid: index
        for index, relation in enumerate(assessment.relations, start=1)
    }
    relation_by_uid = {relation.uid: relation for relation in assessment.relations}
    frame_by_uid = {frame.uid: frame for frame in session.frames}
    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in session.frames
        for memory in frame.memories
    }
    if not assessment.issues:
        lines.append("  (none)")
    ordered_issues = sorted(
        assessment.issues,
        key=lambda item: 0 if item.priority == "REQUIRED" else 1,
    )
    for index, issue in enumerate(ordered_issues, start=1):
        expanded = issue.uid == expanded_issue_uid
        pointer = "▾" if expanded else "›"
        issue_title = issue.title
        if issue.priority == "HELPFUL" and len(issue.relation_uids) == 1:
            relation = relation_by_uid[issue.relation_uids[0]]
            issue_title = f"{relation.kind.title()} · {relation.summary}"
        lines.append(
            f"{pointer} {index:>2}. [{issue.priority}] {_single_line(issue_title)}"
        )
        lines.append(f"      WHY · {_single_line(issue.why_it_matters)}")
        for option_index, option in enumerate(issue.options, start=1):
            lines.append(f"      ↳ {option_index}. {_single_line(option.label)}")
            if expanded:
                lines.append(f"         {safe_terminal_text(option.text)}")
        if expanded:
            lines.extend(
                [
                    f"      QUESTION · {safe_terminal_text(issue.question)}",
                    f"      ISSUE UID · {issue.uid}",
                    "      SOURCE MEMORIES",
                ]
            )
            seen_members: set[tuple[str, str]] = set()
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                for member in relation.members:
                    key = (member.frame_uid, member.memory_uid)
                    if key in seen_members:
                        continue
                    seen_members.add(key)
                    frame = frame_by_uid[member.frame_uid]
                    memory = memory_by_key[key]
                    lines.append(
                        "        - "
                        f"[{frame.role}] "
                        f"{safe_terminal_text(frame.context_name)} "
                        f"#{memory.position + 1} [{memory.uid[:8]}] · "
                        f"{safe_terminal_text(memory.content)}"
                    )
            lines.append("      RELATED RELATIONS")
            for relation_uid in issue.relation_uids:
                relation = relation_by_uid[relation_uid]
                lines.append(
                    f"        - R{relation_number[relation_uid]} "
                    f"{relation.kind} · "
                    f"{safe_terminal_text(relation.reason)}"
                )
            affected = [
                proposal
                for proposal in assessment.proposals
                if set(proposal.relation_uids) & set(issue.relation_uids)
            ]
            lines.append("      AFFECTED RESULTS")
            if not affected:
                lines.append("        - unresolved; no target Memory is proposed yet")
            for proposal in affected:
                lines.append(
                    f"        - [{proposal.disposition}] "
                    f"{safe_terminal_text(proposal.content)}"
                )
    lines.extend(
        [
            "",
            (
                "PROPOSED BASELINE CHANGES"
                if session.mode == "DIRECTIONAL"
                else "PROPOSED TARGET MEMORIES"
            ),
        ]
    )
    if not assessment.proposals:
        lines.append(
            (
                "  (no material baseline changes; acceptance records the "
                "resolved zero-change meld)"
                if session.mode == "DIRECTIONAL" and assessment.ready_to_apply
                else "  (none until required issues are grounded)"
            )
        )
    for index, proposal in enumerate(assessment.proposals, start=1):
        marker = "~" if proposal.operation == "EDIT" else "+"
        label = (
            f"{proposal.operation} · {proposal.disposition}"
            if session.mode == "DIRECTIONAL"
            else proposal.disposition
        )
        lines.append(
            f"  {marker} {index:>2}. [{label}] {safe_terminal_text(proposal.content)}"
        )
        lines.append(f"       WHY · {safe_terminal_text(proposal.reason)}")
    if session.state == "AWAITING_REPLY":
        command = _session_command(session)
        lines.extend(
            [
                "",
                f"Resolve one: {command} --issue N --comment TEXT",
                f"Guide all:  {command} --comment TEXT",
                f"Preserve:   {command} --preserve-all",
                f"Defer:      {command} --defer-all",
            ]
        )
    elif session.state == "READY_TO_APPLY":
        lines.extend(
            [
                "",
                (f"Apply exactly this proposal: {_session_command(session)} --accept"),
            ]
        )
    return "\n".join(lines)


def _load_bound_contexts(
    store: MemoryStore,
    session: MeldSession,
) -> tuple[Context, Context, Context]:
    try:
        left = store.load_direct(session.frames[0].context_name)
        right = store.load_direct(session.frames[1].context_name)
    except FileNotFoundError:
        if session.mode != "SYMMETRIC" or session.comparison_seed is None:
            raise
        artifact = load_granted_comparison_artifact(
            store,
            session.frames[0].context_uid,
            session.frames[1].context_uid,
        )
        if artifact is None:
            raise MeldCommandError(
                "The granted Compare basis for this Meld is unavailable."
            )
        left, right = granted_artifact_contexts(store, artifact)
    target = store.load_direct(session.target.context_name)
    return left, right, target


def _resolve_meld_source(
    store: MemoryStore,
    name: str,
    *,
    current_name: str | None,
) -> ContextAccess:
    return resolve_context_access(
        store,
        name,
        current_name=current_name,
        required_permission="READ",
    )


def _load_meld_source(access: ContextAccess) -> Context:
    context = (
        GrantedReadStore(access).load(access.display_name)
        if access.is_granted
        else access.store.load_direct(access.context_name)
    )
    return recursive_comparison_projection(context)


def _assert_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    for frame, context in zip(
        session.frames,
        (left, right),
        strict=True,
    ):
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or context_record_digest(context) != frame.context_digest
        ):
            raise MeldCommandError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def _assert_non_target_source_bindings(
    session: MeldSession,
    left: Context,
    right: Context,
) -> None:
    """Recheck read-only inputs while allowing an applied baseline to differ."""
    for frame, context in zip(
        session.frames,
        (left, right),
        strict=True,
    ):
        if (
            frame.context_uid == session.target.context_uid
            and frame.context_name == session.target.context_name
        ):
            continue
        if (
            context.uid != frame.context_uid
            or context.name != frame.context_name
            or context_record_digest(context) != frame.context_digest
        ):
            raise MeldCommandError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def _assert_unapplied_target(
    session: MeldSession,
    target: Context,
) -> None:
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
        or context_record_digest(target) != session.target.context_digest
    ):
        raise MeldCommandError(
            "The meld target changed after analysis; the proposal is stale."
        )


def _target_save_source_bindings(
    store: MemoryStore,
    session: MeldSession,
) -> tuple[tuple[str, str, str], ...]:
    """Return only live local sources that must stay locked through target CAS."""
    if session.mode == "SYMMETRIC" and session.comparison_seed is not None:
        artifact = load_granted_comparison_artifact(
            store,
            session.frames[0].context_uid,
            session.frames[1].context_uid,
        )
        if artifact is not None and artifact.retention == "RETAINED":
            # The source postures are immutable participant-owned snapshots.
            # Requiring same-name ordinary Contexts here would both fail for a
            # granted alias and incorrectly reintroduce live authority state.
            return ()
    return tuple(
        (frame.context_name, frame.context_uid, frame.context_digest)
        for frame in session.frames
        if (
            frame.context_uid != session.target.context_uid
            or frame.context_name != session.target.context_name
        )
    )


def _assess_and_save(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
    expected_session_digest: str | None,
) -> MeldSession:
    provider = _connect_meld_provider(provider_factory)
    assessment = assess_meld_turn(session, provider)
    # Provider latency creates a real race window. Rebind every source and the
    # target after the call before persisting a claim about them.
    left, right, target = _load_bound_contexts(store, session)
    _assert_source_bindings(session, left, right)
    _assert_unapplied_target(session, target)
    current = session.current_turn
    assert current is not None
    session.record_assessment(current.uid, assessment)
    store.save_meld_session(
        session,
        expected_session_digest=expected_session_digest,
    )
    return session


def _materialize_preservation_and_save(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str | None,
) -> MeldSession:
    """Materialize an exact symmetric preserve-all turn without a provider."""
    assessment = materialize_preservation_assessment(session)
    left, right, target = _load_bound_contexts(store, session)
    _assert_source_bindings(session, left, right)
    _assert_unapplied_target(session, target)
    current = session.current_turn
    assert current is not None
    session.record_assessment(current.uid, assessment)
    store.save_meld_session(
        session,
        expected_session_digest=expected_session_digest,
    )
    return session


def _meld_checkpoint_record(
    session: MeldSession,
    change_set,
) -> dict[str, object]:
    return {
        "schema_version": 2 if session.mode == "DIRECTIONAL" else 1,
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


def _expected_target_memories(
    session: MeldSession,
    change_set,
) -> tuple[Memory, ...]:
    """Build the exact post-image without mutating a loaded Context."""
    if session.mode == "SYMMETRIC":
        return tuple(
            Memory(uid=proposal.memory_uid, content=proposal.content)
            for proposal in change_set.proposals
        )
    baseline = session.frames[1]
    expected = [
        Memory(uid=memory.uid, content=memory.content) for memory in baseline.memories
    ]
    position_by_uid = {memory.uid: position for position, memory in enumerate(expected)}
    for proposal in change_set.proposals:
        candidate = Memory(
            uid=proposal.memory_uid,
            content=proposal.content,
        )
        if proposal.operation == "EDIT":
            expected[position_by_uid[proposal.memory_uid]] = candidate
        else:
            position_by_uid[proposal.memory_uid] = len(expected)
            expected.append(candidate)
    return tuple(expected)


def _recover_application(
    *,
    store: MemoryStore,
    session: MeldSession,
    target: Context,
    change_set,
) -> tuple[str, tuple[str, ...]] | None:
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
    ):
        return None
    result_uids = tuple(proposal.memory_uid for proposal in change_set.proposals)
    expected_memories = _expected_target_memories(session, change_set)
    current_items = tuple(target.iter_items())
    if any(not isinstance(item, Memory) for item in current_items):
        return None
    current_memories = tuple(current_items)
    if tuple(memory.uid for memory in current_memories) != tuple(
        memory.uid for memory in expected_memories
    ):
        return None
    if tuple(memory.content for memory in current_memories) != tuple(
        memory.content for memory in expected_memories
    ):
        return None
    for checkpoint in reversed(store.list_checkpoints(target.name)):
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


def _accept(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
) -> tuple[bool, str, int]:
    change_set = session.prepare_changes()
    left, right, direct_target = _load_bound_contexts(store, session)
    # After a directional application the BASELINE frame intentionally differs
    # from its original snapshot. The target post-image and receipt validate
    # that overlap; every non-target input must remain byte-identical.
    _assert_non_target_source_bindings(session, left, right)
    if session.state == "APPLIED":
        assert session.application is not None
        recovered = _recover_application(
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
            raise MeldCommandError(
                "The applied meld receipt no longer matches the current "
                "target and checkpoint."
            )
        return (
            True,
            session.application.checkpoint_uid,
            len(session.application.result_memory_uids),
        )
    # A zero-change directional meld has the same pre- and post-image. Check
    # for its durable checkpoint even when the Context digest did not change,
    # otherwise a crash between checkpoint and receipt persistence could make
    # a retry create a duplicate checkpoint.
    recovered = _recover_application(
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
        return True, checkpoint_uid, len(result_uids)
    if context_record_digest(direct_target) != session.target.context_digest:
        raise MeldCommandError(
            "The meld target changed and does not match a recoverable prior "
            "application."
        )

    target = store.load_for_update(session.target.context_name)
    _assert_unapplied_target(session, target)
    for proposal in change_set.proposals:
        memory = Memory(
            uid=proposal.memory_uid,
            content=proposal.content,
        )
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
            args={"meld": _meld_checkpoint_record(session, change_set)},
            description=description,
        ),
        expected_context_digest=session.target.context_digest,
        source_bindings=_target_save_source_bindings(store, session),
    )
    if checkpoint is None:
        raise MeldCommandError("Meld application created no checkpoint.")
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
    return False, checkpoint.uid, len(result_uids)


def _run_interactive(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
) -> MeldSession:
    """Run issue and whole-set turns through one shared interactive shell."""
    navigation = ResolutionNavigation()
    while session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}:
        action = run_meld_shell(session, navigation=navigation)
        if action is None:
            break
        expected = meld_canonical_digest(session.to_dict())
        if action.kind == "DEFER_ALL":
            session.keep_review_only()
            store.save_meld_session(
                session,
                expected_session_digest=expected,
            )
            break
        if action.kind == "ACCEPT":
            _accept(
                store=store,
                session=session,
                expected_session_digest=expected,
            )
            break
        if action.kind == "PRESERVE_ALL":
            session.start_turn(
                _preserve_all_guidance(session),
                scope="REMAINING",
            )
            if (
                session.mode == "SYMMETRIC"
                and session.schema_version >= MELD_SCHEMA_VERSION
            ):
                session = _materialize_preservation_and_save(
                    store=store,
                    session=session,
                    expected_session_digest=expected,
                )
                continue
        elif action.kind == "COMMENT_ALL":
            session.start_turn(action.comment, scope="ALL")
        elif action.kind == "COMMENT_ISSUE":
            assessment = session.current_assessment
            assert assessment is not None and action.issue_uid is not None
            issue = next(
                item for item in assessment.issues if item.uid == action.issue_uid
            )
            parts: list[str] = []
            if action.choice_index is not None:
                option = issue.options[action.choice_index]
                parts.append(f"Choose this reading: {option.text}")
            if action.comment:
                parts.append(action.comment)
            session.start_turn(
                "\n\n".join(parts),
                scope="ISSUE",
                issue_uids=(issue.uid,),
            )
        else:
            raise MeldCommandError(
                f"Unsupported interactive meld action '{action.kind}'."
            )
        session = _assess_and_save(
            store=store,
            session=session,
            provider_factory=provider_factory,
            expected_session_digest=expected,
        )
    return session


def start_reviewed_symmetric_meld(
    *,
    store: MemoryStore,
    analysis: ComparisonAnalysis,
    target_name: str,
    create_target: bool,
    provider_factory=connect_codex_chatgpt_provider,
) -> MeldSession:
    """Create and open a target-bound Meld from one exact Compare analysis.

    Compare may collect the target choice, but Meld repeats every source,
    grant, transfer, target, and saved-analysis check before it creates state.
    This keeps the picker a presentation convenience rather than a new
    mutation authority.
    """
    left_name, right_name = (
        analysis.frames[0].context_name,
        analysis.frames[1].context_name,
    )
    if target_name in {left_name, right_name}:
        raise MeldCommandError(
            "The symmetric Meld result must differ from both source Contexts."
        )
    current_name = store.current_context_name()
    left_access = _resolve_meld_source(
        store,
        left_name,
        current_name=current_name,
    )
    right_access = _resolve_meld_source(
        store,
        right_name,
        current_name=current_name,
    )
    authorize_combination((left_access, right_access))
    left_ctx = _load_meld_source(left_access)
    right_ctx = _load_meld_source(right_access)

    if create_target:
        store.assert_context_creatable(target_name)
        target = ops.init(target_name)
    else:
        if not store.context_exists(target_name):
            raise MeldCommandError(f"RESULT Context '{target_name}' no longer exists.")
        target = store.load_direct(target_name)
        if tuple(target.iter_items()):
            raise MeldCommandError(
                f"RESULT Context '{target_name}' is no longer empty."
            )
        if store.load_meld_session(target.uid) is not None:
            raise MeldCommandError(
                f"RESULT Context '{target_name}' already owns a Meld session."
            )

    target_access = ContextAccess(
        store=store,
        context_name=target_name,
        display_name=target_name,
        attachment_name=None,
        permission="READ",
    )
    authorize_derived_transfer(left_access, target_access)
    authorize_derived_transfer(right_access, target_access)
    reviewed = _load_symmetric_comparison(
        left=left_ctx,
        right=right_ctx,
        target=target,
        create_target=create_target,
    )
    if reviewed.uid != analysis.uid:
        raise MeldCommandError(
            "The selected Compare analysis changed before Meld started. "
            "Reopen Compare and choose the target again."
        )
    session = MeldSession.create_symmetric_from_comparison(reviewed, target)
    _assert_source_bindings(session, left_ctx, right_ctx)
    _assert_unapplied_target(session, target)
    if create_target:
        store.create_meld_target_with_session(
            target,
            session,
            AutoCheckpoint(
                command="meld",
                args={
                    "left": left_name,
                    "right": right_name,
                    "to": target_name,
                },
                description=(
                    f"Initialized symmetric Meld result '{target_name}' from "
                    f"'{left_name}' and '{right_name}'"
                ),
            ),
        )
    else:
        store.save_meld_session(session, expected_session_digest=None)
    if sys.stdin.isatty() and sys.stdout.isatty():
        session = _run_interactive(
            store=store,
            session=session,
            provider_factory=provider_factory,
        )
    return session


def _meld_picker_entry(
    entry: MeldSessionCatalogEntry,
) -> SessionPickerEntry:
    """Adapt one target-bound Meld snapshot to the shared session picker."""
    return SessionPickerEntry(
        kind="meld",
        key=entry.key,
        title=entry.title,
        status=entry.status,
        subtitle=entry.subtitle,
        group=entry.group,
        sort_timestamp=entry.modified_timestamp,
        detail=entry.detail,
        reopen_argv=entry.reopen_argv,
    )


def _resume_picked_meld(
    *,
    store: MemoryStore,
    entry: MeldSessionCatalogEntry,
) -> None:
    """Reload, rebind, and open one picker selection without creating state."""
    session = reload_selected_meld_session(store, entry)
    left_ctx, right_ctx, target = _load_bound_contexts(store, session)
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
    ):
        raise MeldCommandError(
            "The selected Meld target identity no longer matches its saved session."
        )
    _assert_non_target_source_bindings(session, left_ctx, right_ctx)
    if session.state != "APPLIED":
        _assert_source_bindings(session, left_ctx, right_ctx)
        _assert_unapplied_target(session, target)

    interactive_ran = sys.stdin.isatty() and sys.stdout.isatty()
    read_only_ran = interactive_ran and session.state in {
        "APPLIED",
        "KEPT_REVIEW_ONLY",
    }
    if interactive_ran:
        if read_only_ran:
            # Terminal states remain durable research artifacts. Reopen the
            # same report surface without controls that could imply another
            # provider turn or a second application.
            run_meld_shell(session, read_only=True)
        else:
            session = _run_interactive(
                store=store,
                session=session,
                provider_factory=connect_codex_chatgpt_provider,
            )
    else:
        typer.echo(render_meld_session(session))
    if interactive_ran:
        if read_only_ran:
            typer.secho(
                "Read-only Meld view closed; saved session unchanged.",
                fg=typer.colors.CYAN,
            )
        else:
            typer.secho(
                "Interactive Meld view closed; any approved turns remain saved.",
                fg=typer.colors.CYAN,
            )
    else:
        typer.secho(
            "Resumed without calling the semantic provider.",
            fg=typer.colors.CYAN,
        )


def _browse_saved_meld_sessions(store: MemoryStore) -> None:
    """Select one saved Meld by metadata, then reopen its exact persisted route."""
    catalog = list_meld_session_catalog(store)
    if not catalog:
        typer.echo("No saved Meld sessions.")
        return
    by_key = {entry.key: entry for entry in catalog}
    receipt = choose_session(
        tuple(_meld_picker_entry(entry) for entry in catalog),
        title="MELD SESSIONS · RECENTLY MODIFIED",
        new_receipt=None,
    )
    if receipt is None:
        return
    if not isinstance(receipt, SessionOpenReceipt) or receipt.kind != "meld":
        raise MeldCommandError("Meld session picker returned an invalid receipt.")
    entry = by_key.get(receipt.key)
    if entry is None or receipt.argv != entry.reopen_argv:
        raise MeldCommandError("Meld session picker returned an invalid receipt.")
    # The argv is a user-visible receipt, not an instruction to execute.  The
    # target UID reload below is authoritative and its saved frames are bound
    # again before any workbench is opened.
    _resume_picked_meld(store=store, entry=entry)


def cmd(
    left: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "First PEER source, or INCOMING in the canonical "
                "INCOMING --into BASELINE form; omit with --into to use the "
                "current Context, and omit positional Contexts with --from"
            )
        ),
    ] = None,
    right: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Second PEER source; directional forms use --into BASELINE "
                "or --from INCOMING instead"
            )
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help=(
                "Canonical directional form: use authoritative BASELINE as "
                "the target for positional or current INCOMING"
            ),
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=(
                "Create a new empty RESULT Context for a symmetric "
                "LEFT RIGHT meld without switching Contexts"
            ),
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Convenience form: meld INCOMING into the current "
                "authoritative BASELINE; normalized to INCOMING --into "
                "BASELINE"
            ),
        ),
    ] = None,
    issue: Annotated[
        Optional[str],
        typer.Option(
            "--issue",
            help="Issue number or unique uid prefix for this comment",
        ),
    ] = None,
    choice: Annotated[
        Optional[int],
        typer.Option(
            "--choice",
            min=1,
            help="Choose one displayed reading for --issue",
        ),
    ] = None,
    comment: Annotated[
        Optional[str],
        typer.Option(
            "--comment",
            help="Explain one issue or guide all remaining relations",
        ),
    ] = None,
    preserve_all: Annotated[
        bool,
        typer.Option(
            "--preserve-all",
            help="Ask to retain every remaining source distinction",
        ),
    ] = False,
    defer_all: Annotated[
        bool,
        typer.Option(
            "--defer-all",
            help="Close as review-only without applying the target",
        ),
    ] = False,
    accept: Annotated[
        bool,
        typer.Option(
            "--accept",
            help="Apply the exact ready proposal without another model call",
        ),
    ] = False,
    restart: Annotated[
        bool,
        typer.Option(
            "--restart",
            help=(
                "Replace the saved review session after rechecking its bound Contexts"
            ),
        ),
    ] = False,
    revision: Annotated[
        Optional[str],
        typer.Option(
            "--revision",
            help="How the comment relates to prior dialogue",
        ),
    ] = None,
    revises_turn: Annotated[
        list[str] | None,
        typer.Option(
            "--revises-turn",
            help="Prior turn uid for a correction or retraction",
        ),
    ] = None,
    expand: Annotated[
        Optional[str],
        typer.Option(
            "--expand",
            help="Render one issue's complete options provider-free",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Browse and reopen an existing saved Meld session",
        ),
    ] = False,
) -> None:
    """Meld peers, or directionally use --into/--from Context roles."""
    action_count = sum(
        (
            comment is not None or choice is not None,
            preserve_all,
            defer_all,
            accept,
            restart,
        )
    )
    if action_count > 1:
        typer.secho(
            "Meld error: use one comment, preserve, defer, accept, or restart action.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if expand is not None and action_count:
        typer.secho(
            "Meld error: --expand cannot be combined with a semantic or "
            "terminal action.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if choice is not None and issue is None:
        typer.secho(
            "Meld error: --choice requires --issue.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if issue is not None and comment is None and choice is None:
        typer.secho(
            "Meld error: --issue requires --comment or --choice.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if (revision is not None or revises_turn) and comment is None and choice is None:
        typer.secho(
            "Meld error: --revision and --revises-turn require a comment or choice.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if from_ is not None and into is not None:
        typer.secho(
            "Meld error: --from and --into are alternative directional "
            "spellings and cannot be combined.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if to is not None and (into is not None or from_ is not None):
        typer.secho(
            "Meld error: --to creates a symmetric result and cannot be "
            "combined with directional --into or --from.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if from_ is not None and (left is not None or right is not None):
        typer.secho(
            "Meld error: --from supplies INCOMING and cannot be combined "
            "with positional Contexts.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    browse_by_default = (
        left is None
        and right is None
        and into is None
        and to is None
        and from_ is None
        and issue is None
        and choice is None
        and comment is None
        and not preserve_all
        and not defer_all
        and not accept
        and not restart
        and revision is None
        and not revises_turn
        and expand is None
    )
    if sessions and not browse_by_default:
        typer.secho(
            "Meld error: --sessions cannot be combined with Context operands "
            "or Meld actions.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore(create=False)
    try:
        if sessions or browse_by_default:
            _browse_saved_meld_sessions(store)
            return
        current_name = store.current_context_name()
        create_target = False
        if from_ is not None:
            if not current_name:
                raise MeldCommandError(
                    "No current BASELINE Context. Switch to the intended "
                    "baseline before using --from."
                )
            requested_mode = "DIRECTIONAL"
            # Both roles are fixed from one current-name snapshot.  The
            # convenience spelling must resume the same target-scoped session
            # as the portable INCOMING --into BASELINE form.
            left_name = resolve_context_locator(
                from_,
                current=current_name,
            )
            right_name = current_name
            target_name = right_name
            start_command = shlex.join(["mem", "meld", left_name, "--into", right_name])
        elif into is None:
            if left is None or right is None:
                raise MeldCommandError(
                    "Symmetric meld requires LEFT and RIGHT Contexts. For a "
                    "directional meld, use 'mem meld --into BASELINE' or "
                    "'mem meld INCOMING --into BASELINE'; when the current "
                    "Context is BASELINE, use 'mem meld --from INCOMING'."
                )
            if to is None and not current_name:
                raise MeldCommandError(
                    "No current target Context. Run 'mem init TARGET' first."
                )
            requested_mode = "SYMMETRIC"
            left_name = resolve_context_locator(left, current=current_name)
            right_name = resolve_context_locator(right, current=current_name)
            if to is None:
                assert current_name is not None
                target_name = current_name
                start_command = "mem meld LEFT RIGHT"
            else:
                # A result name creates a new identity, so it deliberately does
                # not pass through the existing-Context locator resolver.
                target_name = to
                create_target = True
                start_command = shlex.join(
                    ["mem", "meld", left_name, right_name, "--to", target_name]
                )
        else:
            if right is not None:
                raise MeldCommandError(
                    "Directional meld accepts at most one positional INCOMING "
                    "Context. Use 'mem meld INCOMING --into BASELINE', or omit "
                    "INCOMING to use the current Context."
                )
            requested_mode = "DIRECTIONAL"
            if left is None:
                if not current_name:
                    raise MeldCommandError(
                        "No current INCOMING Context. Supply one explicitly or "
                        "switch to it before using --into."
                    )
                left_name = current_name
            else:
                left_name = resolve_context_locator(
                    left,
                    current=current_name,
                )
            right_name = resolve_context_locator(
                into,
                current=current_name,
            )
            target_name = right_name
            start_command = shlex.join(["mem", "meld", left_name, "--into", right_name])

        if left_name == right_name:
            if requested_mode == "DIRECTIONAL":
                raise MeldCommandError(
                    "INCOMING and BASELINE must be distinct Contexts."
                )
            raise MeldCommandError("The two PEER source Contexts must be distinct.")
        if requested_mode == "SYMMETRIC" and target_name in {
            left_name,
            right_name,
        }:
            raise MeldCommandError(
                "The two PEER sources and active target must be distinct Contexts."
            )
        if create_target:
            if store.context_exists(target_name):
                raise MeldCommandError(
                    f"RESULT Context '{target_name}' already exists. Choose "
                    "a new name; --to never adopts or overwrites an existing "
                    "Context."
                )
            target = ops.init(target_name)
            session = None
        else:
            target = store.load_direct(target_name)
            session = store.load_meld_session(target.uid)
        left_access: ContextAccess | None = None
        right_access: ContextAccess | None = None
        if requested_mode == "SYMMETRIC" and session is None:
            left_access = _resolve_meld_source(
                store,
                left_name,
                current_name=current_name,
            )
            right_access = _resolve_meld_source(
                store,
                right_name,
                current_name=current_name,
            )
            target_access = (
                ContextAccess(
                    store=store,
                    context_name=target_name,
                    display_name=target_name,
                    attachment_name=None,
                    permission="READ",
                )
                if create_target
                else resolve_context_access(
                    store,
                    target_name,
                    current_name=current_name,
                    required_permission="READ",
                )
            )
            if target_access.is_granted:
                raise MeldCommandError(
                    "Symmetric granted-source Meld currently requires a local "
                    "participant target."
                )
            authorize_combination((left_access, right_access))
            authorize_derived_transfer(left_access, target_access)
            authorize_derived_transfer(right_access, target_access)
        elif requested_mode == "DIRECTIONAL":
            if not store.context_exists(left_name):
                raise MeldCommandError(
                    f"INCOMING Context '{left_name}' does not exist."
                )
            if not store.context_exists(right_name):
                raise MeldCommandError(
                    f"BASELINE Context '{right_name}' does not exist."
                )
        if session is None:
            if any(
                (
                    comment is not None,
                    choice,
                    preserve_all,
                    defer_all,
                    accept,
                    restart,
                )
            ):
                raise MeldCommandError(
                    f"Start the meld with a plain '{start_command}' first."
                )
            left_ctx = (
                _load_meld_source(left_access)
                if left_access is not None
                else store.load_direct(left_name)
            )
            right_ctx = (
                _load_meld_source(right_access)
                if right_access is not None
                else store.load_direct(right_name)
            )
            if requested_mode == "DIRECTIONAL":
                session = MeldSession.create_directional(
                    left_ctx,
                    right_ctx,
                )
                session.start_initial_analysis()
                session = _assess_and_save(
                    store=store,
                    session=session,
                    provider_factory=connect_codex_chatgpt_provider,
                    expected_session_digest=None,
                )
            else:
                comparison = _load_symmetric_comparison(
                    left=left_ctx,
                    right=right_ctx,
                    target=target,
                    create_target=create_target,
                )
                session = MeldSession.create_symmetric_from_comparison(
                    comparison,
                    target,
                )
                # Importing Compare is provider-free, but the exact source and
                # empty-target bindings still need one last local recheck
                # before the target-scoped session is made durable.
                _assert_source_bindings(session, left_ctx, right_ctx)
                _assert_unapplied_target(session, target)
                if create_target:
                    store.create_meld_target_with_session(
                        target,
                        session,
                        AutoCheckpoint(
                            command="meld",
                            args={
                                "left": left_name,
                                "right": right_name,
                                "to": target_name,
                            },
                            description=(
                                f"Initialized symmetric Meld result "
                                f"'{target_name}' from '{left_name}' and "
                                f"'{right_name}'"
                            ),
                        ),
                    )
                else:
                    store.save_meld_session(
                        session,
                        expected_session_digest=None,
                    )
            if sys.stdin.isatty() and sys.stdout.isatty():
                session = _run_interactive(
                    store=store,
                    session=session,
                    provider_factory=connect_codex_chatgpt_provider,
                )
            typer.echo(render_meld_session(session))
            return

        if restart:
            prior_digest = meld_canonical_digest(session.to_dict())
            if requested_mode == "SYMMETRIC":
                # Restart is defined by the newly supplied ordered pair, not
                # by the old session's frames. Reusing the bound frames here
                # would silently turn RIGHT LEFT into the prior LEFT RIGHT
                # Compare basis and defeat the exact-order review contract.
                restart_left_access = _resolve_meld_source(
                    store,
                    left_name,
                    current_name=current_name,
                )
                restart_right_access = _resolve_meld_source(
                    store,
                    right_name,
                    current_name=current_name,
                )
                authorize_combination((restart_left_access, restart_right_access))
                restart_target_access = ContextAccess(
                    store=store,
                    context_name=target.name,
                    display_name=target.name,
                    attachment_name=None,
                    permission="READ",
                )
                authorize_derived_transfer(
                    restart_left_access,
                    restart_target_access,
                )
                authorize_derived_transfer(
                    restart_right_access,
                    restart_target_access,
                )
                left_ctx = _load_meld_source(restart_left_access)
                right_ctx = _load_meld_source(restart_right_access)
            else:
                left_ctx = (
                    _load_meld_source(left_access)
                    if left_access is not None
                    else store.load_direct(left_name)
                )
                right_ctx = (
                    _load_meld_source(right_access)
                    if right_access is not None
                    else store.load_direct(right_name)
                )
            if requested_mode == "DIRECTIONAL":
                replacement = MeldSession.create_directional(
                    left_ctx,
                    right_ctx,
                )
                replacement.start_initial_analysis()
                session = _assess_and_save(
                    store=store,
                    session=replacement,
                    provider_factory=connect_codex_chatgpt_provider,
                    expected_session_digest=prior_digest,
                )
            else:
                comparison = _load_symmetric_comparison(
                    left=left_ctx,
                    right=right_ctx,
                    target=target,
                )
                replacement = MeldSession.create_symmetric_from_comparison(
                    comparison,
                    target,
                )
                _assert_source_bindings(
                    replacement,
                    left_ctx,
                    right_ctx,
                )
                _assert_unapplied_target(replacement, target)
                store.save_meld_session(
                    replacement,
                    expected_session_digest=prior_digest,
                )
                session = replacement
            if sys.stdin.isatty() and sys.stdout.isatty():
                session = _run_interactive(
                    store=store,
                    session=session,
                    provider_factory=connect_codex_chatgpt_provider,
                )
            typer.echo(render_meld_session(session))
            return

        if session.mode != requested_mode:
            raise MeldCommandError(
                "The target already has a saved meld with a different "
                "authority mode. Use --restart to replace it."
            )
        saved_names = tuple(frame.context_name for frame in session.frames)
        sources_match = (
            saved_names == (left_name, right_name)
            if requested_mode == "DIRECTIONAL"
            else set(saved_names) == {left_name, right_name}
        )
        if not sources_match:
            raise MeldCommandError(
                "The target already has a meld from different sources. Use "
                "--restart to replace it."
            )
        expected_session_digest = meld_canonical_digest(session.to_dict())
        left_ctx, right_ctx, target = _load_bound_contexts(store, session)
        _assert_non_target_source_bindings(session, left_ctx, right_ctx)
        if session.state != "APPLIED" and not accept:
            _assert_source_bindings(session, left_ctx, right_ctx)
            _assert_unapplied_target(session, target)

        if accept:
            recovered, checkpoint_uid, result_count = _accept(
                store=store,
                session=session,
                expected_session_digest=expected_session_digest,
            )
            typer.echo(render_meld_session(session))
            if recovered:
                typer.secho(
                    "Recovered the prior meld application; no duplicate "
                    "checkpoint was created.",
                    fg=typer.colors.YELLOW,
                )
            else:
                noun = (
                    "meld changes" if session.mode == "DIRECTIONAL" else "meld results"
                )
                typer.secho(
                    f"Applied {result_count} {noun} in checkpoint "
                    f"[{checkpoint_uid[:8]}].",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
            return

        if defer_all:
            session.keep_review_only()
            store.save_meld_session(
                session,
                expected_session_digest=expected_session_digest,
            )
            typer.echo(render_meld_session(session))
            typer.secho(
                "Deferred this meld without changing the target.",
                fg=typer.colors.YELLOW,
            )
            return

        if preserve_all:
            session.start_turn(
                _preserve_all_guidance(session),
                scope="REMAINING",
            )
            if (
                session.mode == "SYMMETRIC"
                and session.schema_version >= MELD_SCHEMA_VERSION
            ):
                session = _materialize_preservation_and_save(
                    store=store,
                    session=session,
                    expected_session_digest=expected_session_digest,
                )
            else:
                session = _assess_and_save(
                    store=store,
                    session=session,
                    provider_factory=connect_codex_chatgpt_provider,
                    expected_session_digest=expected_session_digest,
                )
            typer.echo(render_meld_session(session))
            return

        if comment is not None or choice is not None:
            selected_issue = (
                _issue_selector(session, issue) if issue is not None else None
            )
            text_parts: list[str] = []
            if choice is not None:
                assert selected_issue is not None
                if choice > len(selected_issue.options):
                    raise MeldCommandError(
                        f"Issue has only {len(selected_issue.options)} choices."
                    )
                option = selected_issue.options[choice - 1]
                text_parts.append(f"Choose this reading: {option.text}")
            if comment is not None and comment.strip():
                text_parts.append(comment)
            turn_comment = "\n\n".join(text_parts)
            revision_value = (revision or "extend").strip().upper()
            if revision_value not in {
                "CONFIRM",
                "EXTEND",
                "CORRECT",
                "RETRACT",
            }:
                raise MeldCommandError(
                    "--revision must be confirm, extend, correct, or retract."
                )
            revises = tuple(revises_turn or ())
            if revises and revision_value not in {"CORRECT", "RETRACT"}:
                raise MeldCommandError(
                    "--revises-turn is valid only with --revision correct or retract."
                )
            session.start_turn(
                turn_comment,
                scope=("ISSUE" if selected_issue is not None else "ALL"),
                issue_uids=(
                    (selected_issue.uid,) if selected_issue is not None else ()
                ),
                revision=revision_value,  # type: ignore[arg-type]
                revises_turn_uids=revises,
            )
            session = _assess_and_save(
                store=store,
                session=session,
                provider_factory=connect_codex_chatgpt_provider,
                expected_session_digest=expected_session_digest,
            )
            typer.echo(render_meld_session(session))
            return

        expanded_uid = None
        if expand is not None:
            expanded_uid = _issue_selector(session, expand).uid
        interactive_ran = (
            expand is None
            and sys.stdin.isatty()
            and sys.stdout.isatty()
            and session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}
        )
        if interactive_ran:
            session = _run_interactive(
                store=store,
                session=session,
                provider_factory=connect_codex_chatgpt_provider,
            )
        typer.echo(
            render_meld_session(
                session,
                expanded_issue_uid=expanded_uid,
            )
        )
        if interactive_ran:
            typer.secho(
                "Interactive meld state saved.",
                fg=typer.colors.CYAN,
            )
        else:
            typer.secho(
                "Resumed without calling the semantic provider.",
                fg=typer.colors.CYAN,
            )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        ConcurrentContextUpdateError,
        MeldError,
        MeldProviderError,
        MeldCommandError,
        MeldSessionCatalogError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
    ) as error:
        typer.secho(f"Meld error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
