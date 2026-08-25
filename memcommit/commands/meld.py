"""Create, ground, resume, and explicitly apply bounded Context melds."""

from __future__ import annotations

import shlex
import sys
from typing import Annotated, Optional

import typer

from memcommit.comparison import (
    ComparisonAnalysis,
)
from memcommit.comparison_provider import (
    ComparisonProviderError,
)
from memcommit.context import Context
from memcommit.context_targeting.loading import load_context_scope
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.context_targeting.memory_focus import (
    MemoryFocusError,
    resolve_memory_focus,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.commands.command_wait import (
    CommandWaitView,
    run_command_wait,
)
from memcommit.commands.meld_setup import choose_meld_setup
from memcommit.derived_policy import (
    analysis_retention,
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.granted_comparison_store import (
    granted_artifact_contexts,
    load_granted_comparison_artifact,
    recursive_comparison_projection,
)
from memcommit.meld import (
    INLINE_MELD_CONTEXT_NAME,
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MELD_SCHEMA_VERSION,
    MeldError,
    MeldFrame,
    MeldIssue,
    MeldSession,
    inline_meld_context,
    meld_accounting,
    meld_canonical_digest,
)
from memcommit.meld_provider import (
    MeldProviderError,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.meld_start_application import MeldStartRequest
from memcommit.meld_restart_application import MeldRestartRequest
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.interfaces.tui.operations.meld.screen import run_meld_shell
from memcommit.commands.meld_sessions import (
    MeldSessionCatalogEntry,
    MeldSessionCatalogError,
    list_meld_session_catalog,
    reload_selected_meld_session,
)
from memcommit.interfaces.tui.components.operation_launcher.session import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import (
    ProfileError,
)
from memcommit.context_naming import validate_portable_context_name
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)
from memcommit.study_prewarm.registry import StudyPrewarmRegistryError


class MeldCommandError(RuntimeError):
    """Safe user-facing orchestration failure."""


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _session_command(session: MeldSession) -> str:
    """Return one explicit, portable command prefix for this saved meld."""
    left, right = session.frames
    if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION:
        parts = [
            "mem",
            "meld",
            "--memory",
            left.memories[0].content,
            "--into",
            right.context_name,
        ]
    else:
        parts = ["mem", "meld", left.context_name, right.context_name]
    if left.include_descendants:
        parts.append("--left-descendants")
    if session.mode == "DIRECTIONAL":
        if right.include_descendants:
            parts.append("--right-descendants")
    else:
        if right.include_descendants:
            parts.append("--right-descendants")
        parts.extend(("--to", session.target.context_name))
    return shlex.join(parts)


def _session_route(session: MeldSession) -> str:
    if session.mode == "DIRECTIONAL":
        incoming_label = (
            "INLINE MEMORY"
            if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION
            else session.frames[0].context_name
        )
        return (
            f"INCOMING {incoming_label} → "
            f"BASELINE / TARGET {session.frames[1].context_name}"
        )
    return (
        f"{session.frames[0].context_name} + "
        f"{session.frames[1].context_name} → "
        f"{session.target.context_name}"
    )


def _session_scope(session: MeldSession) -> str:
    left, right = session.frames
    left_label = (
        "SELECTED + ALL DESCENDANTS"
        if left.include_descendants
        else "SELECTED GRAPH ONLY"
    )
    right_label = (
        "SELECTED + ALL DESCENDANTS"
        if right.include_descendants
        else "SELECTED GRAPH ONLY"
    )
    return f"SCOPE · A {left_label} · B {right_label}"


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


def _single_line(value: str, *, limit: int = 90) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


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
        _session_scope(session),
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
        if (
            session.mode == "DIRECTIONAL"
            and len(session.frames[1].contexts or ()) > 1
            and proposal.owner_context_name is not None
        ):
            lines.append(
                "       OWNER · " + safe_terminal_text(proposal.owner_context_name)
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
    elif session.state == "APPLIED" and session.granted_target is None:
        lines.extend(["", "RECOVERY · mem undo"])
    return "\n".join(lines)


def render_meld_receipt(
    session: MeldSession,
    *,
    recovered: bool = False,
) -> str:
    """Render terminal Meld success without reopening its analysis Viewer."""

    if session.state != "APPLIED" or session.application is None:
        raise MeldCommandError("Meld receipt requires an applied session.")
    assessment = session.current_assessment
    proposals = assessment.proposals if assessment is not None else ()
    additions = sum(item.operation == "ADD" for item in proposals)
    edits = sum(item.operation == "EDIT" for item in proposals)
    lines = [
        f"MELD APPLIED · {session.mode} · {session.target.context_name}",
        f"EFFECTS · ADD {additions} · EDIT {edits}",
        f"RESULT MEMORIES · {len(session.application.result_memory_uids)}",
        f"RECEIPT · {session.uid}",
        f"CHECKPOINT · {session.application.checkpoint_uid}",
        f"REVIEW · mem review meld --session {session.uid}",
    ]
    if recovered:
        lines.append("RECOVERY STATUS · prior application recovered; no duplicate write")
    elif session.granted_target is None:
        lines.append("RECOVERY · mem undo")
    else:
        lines.append("RECOVERY · governed by the granted authority owner")
    return "\n".join(lines)


def render_meld_incomplete_receipt(session: MeldSession) -> str:
    """Return saved execution state without echoing the retained report."""

    assessment = session.current_assessment
    issues = assessment.issues if assessment is not None else ()
    required = sum(issue.priority == "REQUIRED" for issue in issues)
    optional = len(issues) - required
    state_label = {
        "AWAITING_REPLY": "NEEDS INPUT",
        "READY_TO_APPLY": "READY",
        "KEPT_REVIEW_ONLY": "DEFERRED",
        "PENDING_ANALYSIS": "PENDING",
    }.get(session.state, session.state.replace("_", " "))
    route = _session_route(session)
    return "\n".join(
        [
            f"MELD {state_label} · {session.mode} · {session.target.context_name}",
            f"ROUTE · {route}",
            f"JUDGMENTS · REQUIRED {required} · OPTIONAL {optional}",
            f"SESSION · {session.uid}",
            "SOURCE · UNCHANGED",
            f"IMPACT · mem impact meld --session {session.uid}",
            "RESUME · mem meld --sessions",
        ]
    )


def _load_bound_contexts(
    store: MemoryStore,
    session: MeldSession,
    *,
    registry=None,
) -> tuple[Context, Context, Context]:
    if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION:
        left = inline_meld_context(session)
        baseline = session.frames[1]
        right = load_context_scope(
            store,
            baseline.context_name,
            include_descendants=bool(baseline.include_descendants),
        )
        return left, right, right
    if session.mode == "DIRECTIONAL" and (
        session.granted_incoming is not None or session.granted_target is not None
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
                _load_meld_source(
                    access,
                    include_descendants=bool(frame.include_descendants),
                    project=(session.schema_version < MELD_OWNER_AWARE_SCHEMA_VERSION),
                )
            )
        left, right = loaded
        # Directional BASELINE is the target. Loading it through the frozen
        # endpoint preserves its public identity while reading authority data.
        return left, right, right
    try:
        loaded: list[Context] = []
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
            raise MeldCommandError(
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


def _is_inline_memory_operand(
    store: MemoryStore,
    value: str,
    *,
    current_name: str | None,
) -> bool:
    """Classify only unambiguously non-Context one-operand text as Memory."""

    resolved = resolve_context_locator(value, current=current_name)
    if store.context_exists(resolved):
        return False
    try:
        validate_portable_context_name(value)
    except ValueError:
        return True
    return False


def _load_meld_source(
    access: ContextAccess,
    *,
    include_descendants: bool = False,
    project: bool = True,
) -> Context:
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


def _load_local_meld_source(
    store: MemoryStore,
    name: str,
    *,
    include_descendants: bool,
    project: bool = True,
) -> Context:
    if not include_descendants:
        return store.load_direct(name)
    context = load_context_scope(
        store,
        name,
        include_descendants=True,
    )
    return recursive_comparison_projection(context) if project else context


def _bound_frame_digest(frame, context: Context) -> str:
    if frame.contexts is None:
        return context_record_digest(context)
    return MeldFrame.from_context(
        context,
        role=frame.role,
        include_descendants=frame.include_descendants,
        owner_aware=True,
    ).context_digest


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
            or _bound_frame_digest(frame, context) != frame.context_digest
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
            or _bound_frame_digest(frame, context) != frame.context_digest
        ):
            raise MeldCommandError(
                f"Source Context '{frame.context_name}' changed after this "
                "meld was analyzed."
            )


def _assert_unapplied_target(
    session: MeldSession,
    target: Context,
) -> None:
    target_digest = (
        _bound_frame_digest(session.frames[1], target)
        if session.mode == "DIRECTIONAL"
        else context_record_digest(target)
    )
    if (
        target.uid != session.target.context_uid
        or target.name != session.target.context_name
        or target_digest != session.target.context_digest
    ):
        raise MeldCommandError(
            "The meld target changed after analysis; the proposal is stale."
        )


def _meld_wait_view(session: MeldSession) -> CommandWaitView:
    """Restore the last complete Meld report beneath one pending turn.

    A newly started turn intentionally has no assessment, so rendering the
    live object would replace the participant's report with only "pending".
    Reconstruct the immediately preceding durable view for display only and
    keep the submitted turn visibly separate. Initial analysis has no prior
    report and remains on the shared one-line progress contract.
    """

    current = session.current_turn
    if current is None or current.assessment is not None or len(session.turns) <= 1:
        raise ValueError(
            "A Meld wait report requires a submitted turn after a completed "
            "assessment."
        )

    prior_turn = session.turns[-2]
    assert prior_turn.assessment is not None
    prior_payload = session.to_dict()
    prior_payload["turns"] = [turn.to_dict() for turn in session.turns[:-1]]
    prior_payload["state"] = (
        "READY_TO_APPLY" if prior_turn.assessment.ready_to_apply else "AWAITING_REPLY"
    )
    prior_session = MeldSession.from_dict(prior_payload)
    pending_lines = [
        render_meld_session(prior_session),
        "",
        "PENDING TURN · SUBMITTED",
        f"SCOPE · {current.scope}",
    ]
    if current.issue_uids:
        pending_lines.append(
            "ISSUES · " + ", ".join(uid[:8] for uid in current.issue_uids)
        )
    if current.comment:
        pending_lines.extend(["", "COMMENT", safe_terminal_text(current.comment)])
    return CommandWaitView(
        title="PREVIOUS MELD REPORT",
        text=_meld_wait_fragments("\n".join(pending_lines)),
    )


def _meld_wait_context_view(session: MeldSession) -> CommandWaitView:
    """Show the exact route, scopes, and submitted turn frozen for analysis."""

    lines = [
        f"MEM MELD · {session.mode} · INPUTS CONFIRMED",
        _session_route(session),
        _session_scope(session),
        "",
        "SOURCE FRAMES",
    ]
    for frame in session.frames:
        scope = (
            "INCLUDE DESCENDANTS" if frame.include_descendants else "THIS CONTEXT ONLY"
        )
        lines.extend(
            [
                f"  {frame.role} · {safe_terminal_text(frame.context_name)}",
                f"    SCOPE · {scope}",
                f"    MEMORIES · {len(frame.memories)}",
            ]
        )
    lines.extend(
        [
            "",
            f"TARGET · {safe_terminal_text(session.target.context_name)}",
            "TARGET · CHANGES APPLY HERE AFTER REVIEW",
        ]
    )
    current = session.current_turn
    if current is not None:
        lines.extend(
            [
                "",
                "SUBMITTED TURN",
                f"  SCOPE · {current.scope}",
            ]
        )
        if current.issue_uids:
            lines.append(
                "  ISSUES · " + ", ".join(uid[:8] for uid in current.issue_uids)
            )
        if current.comment:
            lines.extend(["", "COMMENT", safe_terminal_text(current.comment)])
    return CommandWaitView(
        title="MELD INPUTS",
        text="\n".join(lines),
    )


def _meld_wait_fragments(text: str) -> list[tuple[str, str]]:
    """Retain Meld report semantics on the shared read-only return pane."""

    section_headings = {
        "WHAT MEM UNDERSTOOD",
        "ACCOUNTING",
        "ISSUES",
        "PROPOSED BASELINE CHANGES",
        "PROPOSED TARGET MEMORIES",
        "PENDING TURN · SUBMITTED · NOT YET INCORPORATED",
        "COMMENT",
    }
    lines = text.splitlines()
    fragments: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        style = ""
        if line in section_headings:
            style = "class:section"
        elif line.startswith(("  + ", "  ~ ")):
            # A proposed target/baseline Memory is the only object text on the
            # compact report. Explanations and surrounding chrome stay white.
            style = "class:memory-object"
        fragments.append((style, line + ("\n" if index < len(lines) - 1 else "")))
    return fragments


def _assess_and_save(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
    expected_session_digest: str | None,
) -> MeldSession:
    from memcommit.operations.meld.runtime import (
        execute_prepared_meld_turn,
        prepare_pending_meld_turn,
    )
    from memcommit.meld_session_application import PendingMeldTurn

    prepared = prepare_pending_meld_turn(
        PendingMeldTurn(
            session=session,
            expected_version=expected_session_digest,
        ),
        store=store,
    )

    def connected_provider():
        return provider_factory()

    if not prepared.provider_required:
        return execute_prepared_meld_turn(
            prepared,
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("A cached Meld assessment connected a provider.")
            ),
        ).session

    def assess(progress):
        def observe(stage: str) -> None:
            if stage == "ANALYZING":
                progress.update("analyzing meld turn", step=2)
            elif stage == "REPAIRING":
                progress.update("repairing invalid meld turn", step=2)

        return execute_prepared_meld_turn(
            prepared,
            provider_factory=connected_provider,
            observer=observe,
        ).session

    if len(session.turns) > 1:
        return run_command_wait(
            "MELD",
            "connecting provider",
            total=2,
            work=assess,
            return_view=_meld_wait_view(session),
            context_view=_meld_wait_context_view(session),
        )
    return run_command_wait(
        "MELD",
        "connecting provider",
        total=2,
        work=assess,
    )


def _accept(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
) -> tuple[bool, str, int]:
    """Hand one explicitly accepted Meld to the operation-owned Apply service."""

    from memcommit.operations.meld.application import MeldApplyRequest
    from memcommit.operations.meld.runtime import execute_meld_apply

    receipt = execute_meld_apply(
        MeldApplyRequest(
            session=session,
            expected_session_digest=expected_session_digest,
        ),
        store=store,
    ).receipt
    return receipt.recovered, receipt.checkpoint_uid, receipt.result_count


def _complete_default_terminal_execution(
    *,
    store: MemoryStore,
    session: MeldSession,
) -> MeldSession:
    """Finish a normal terminal Meld without opening a response turn.

    Symmetric Compare already supplies an exhaustive relation ledger.  Meld
    materializes that ledger conservatively in the same initial turn, then
    applies any decision-complete local result.  Granted-target writes retain
    their explicit authority approval boundary, and unresolved directional
    analyses remain terminal incomplete receipts rather than conversations.
    """

    if not _interactive_terminal():
        return session
    if session.mode == "SYMMETRIC" and session.state == "AWAITING_REPLY":
        expected = meld_canonical_digest(session.to_dict())
        session.complete_initial_preservation()
        store.save_meld_session(
            session,
            expected_session_digest=expected,
        )
    if session.state == "READY_TO_APPLY" and session.granted_target is None:
        _accept(
            store=store,
            session=session,
            expected_session_digest=meld_canonical_digest(session.to_dict()),
        )
        applied = store.load_meld_session(session.target.context_uid)
        if applied is None or applied.state != "APPLIED":
            raise MeldCommandError(
                "Meld Apply completed without a reloadable applied receipt."
            )
        session = applied
    return session


def _run_interactive(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
    allow_apply: bool = True,
    analysis_origin: str | None = None,
) -> MeldSession:
    """Run issue and whole-set turns through one shared interactive shell."""
    from memcommit.commands.resolution_workbench_shell import ResolutionDestination
    from memcommit.operations.meld.runtime import (
        execute_meld_destination_change,
        execute_meld_preservation,
        execute_meld_session_defer,
    )
    from memcommit.meld_session_application import (
        MeldDestinationRequest,
        MeldSessionSnapshot,
        prepare_meld_preservation_turn,
    )
    from memcommit.meld_resolution_application import (
        MeldResolutionTurnRequest,
        prepare_meld_resolution_turn,
    )

    if analysis_origin is None and session.comparison_seed is not None:
        from memcommit.study_prewarm.compare import (
            installed_compare_prewarm_origin,
        )

        analysis_origin = installed_compare_prewarm_origin(
            store,
            session.comparison_seed.analysis,
        )
    navigation = ResolutionNavigation()
    while session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}:

        def validate_destination(name: str) -> None:
            validate_portable_context_name(name)
            if name == session.target.context_name:
                return
            descendants = tuple(
                candidate
                for candidate in store.list_context_names()
                if candidate.startswith(session.target.context_name + "/")
            )
            if descendants:
                raise ValueError(
                    "A symmetric Meld save location with descendants cannot "
                    "be moved from the review workbench."
                )
            store.plan_context_rename(session.target.context_name, name)

        destination = (
            ResolutionDestination(
                value=session.target.context_name,
                state="CURRENT TARGET",
                validate=validate_destination,
                context_names=tuple(store.list_context_names()),
                current_context=store.current_context_name(),
            )
            if allow_apply and session.mode == "SYMMETRIC"
            else None
        )
        # Each visible option is a provider-free local branch. Persist only
        # its exact issue/option selection (and optional explanation) while
        # the person reviews; the provider sees the choices together only
        # after the workbench builds one explicit whole-ledger action.
        choice_branches = (
            store.load_meld_choice_branches(session)
            if session.current_assessment is not None
            else None
        )

        def load_choice(issue_uid: str) -> tuple[str | None, str]:
            assert choice_branches is not None
            return choice_branches.response_for(issue_uid)

        def save_choice(
            issue_uid: str,
            option_uid: str | None,
            explanation: str,
        ) -> None:
            nonlocal choice_branches
            assert choice_branches is not None
            choice_branches = choice_branches.with_response(
                session,
                issue_uid=issue_uid,
                option_uid=option_uid,
                explanation=explanation,
            )
            store.save_meld_choice_branches(session, choice_branches)

        action = run_meld_shell(
            session,
            navigation=navigation,
            review_only=not allow_apply,
            destination=destination,
            analysis_origin=analysis_origin,
            draft_loader=(load_choice if choice_branches is not None else None),
            draft_saver=(save_choice if choice_branches is not None else None),
        )
        if action is None:
            break
        expected = meld_canonical_digest(session.to_dict())
        snapshot = MeldSessionSnapshot(session=session, version_token=expected)
        if action.kind == "CHANGE_DESTINATION":
            if destination is None or action.destination is None:
                raise MeldCommandError("This Meld cannot change its save location.")
            validate_destination(action.destination)
            if action.destination != session.target.context_name:
                session = execute_meld_destination_change(
                    MeldDestinationRequest(
                        snapshot=snapshot,
                        destination_name=action.destination,
                    ),
                    store=store,
                ).session
            continue
        if action.kind == "DEFER_ALL":
            session = execute_meld_session_defer(snapshot, store=store).session
            break
        if action.kind == "ACCEPT":
            if not allow_apply:
                raise MeldCommandError("Review cannot apply a Meld target.")
            _accept(
                store=store,
                session=session,
                expected_session_digest=expected,
            )
            break
        if action.kind == "PRESERVE_ALL":
            pending = prepare_meld_preservation_turn(
                snapshot,
                guidance=_preserve_all_guidance(session),
            )
            session = pending.session
            if (
                session.mode == "SYMMETRIC"
                and session.schema_version >= MELD_SCHEMA_VERSION
            ):
                session = execute_meld_preservation(pending, store=store).session
                continue
        elif action.kind == "COMMENT_ALL":
            session = prepare_meld_resolution_turn(
                MeldResolutionTurnRequest(
                    snapshot=snapshot,
                    comment=action.comment,
                )
            ).session
        elif action.kind == "COMMENT_ISSUE":
            assert action.issue_uid is not None
            session = prepare_meld_resolution_turn(
                MeldResolutionTurnRequest(
                    snapshot=snapshot,
                    issue_uid=action.issue_uid,
                    option_uid=action.option_uid,
                    comment=action.comment,
                )
            ).session
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


def run_meld_review(
    *,
    store: MemoryStore,
    session: MeldSession,
    provider_factory,
) -> MeldSession:
    """Run semantic Meld review turns without exposing target application."""
    return _run_interactive(
        store=store,
        session=session,
        provider_factory=provider_factory,
        allow_apply=False,
    )


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
    from memcommit.operations.meld.runtime import execute_meld_start

    session = execute_meld_start(
        MeldStartRequest(
            mode="SYMMETRIC",
            left_name=left_name,
            right_name=right_name,
            target_name=target_name,
            left_descendants=analysis.include_descendants[0],
            right_descendants=analysis.include_descendants[1],
            create_target=create_target,
            comparison=analysis,
        ),
        store=store,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("Symmetric Meld start connected a provider.")
        ),
    ).session
    return _complete_default_terminal_execution(store=store, session=session)


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

    interactive_ran = _interactive_terminal()
    terminal_session = session.state in {
        "APPLIED",
        "KEPT_REVIEW_ONLY",
    }
    if interactive_ran:
        if session.state == "APPLIED":
            typer.echo(render_meld_receipt(session))
        elif session.state == "KEPT_REVIEW_ONLY":
            typer.echo(f"MELD DEFERRED · {session.target.context_name}")
            typer.echo(f"SESSION · {session.uid}")
            typer.echo("SOURCE · UNCHANGED")
            typer.echo("RESUME · mem meld --sessions")
        else:
            session = _complete_default_terminal_execution(
                store=store,
                session=session,
            )
            if session.state == "APPLIED":
                typer.echo(render_meld_receipt(session))
                terminal_session = True
            else:
                typer.echo(render_meld_incomplete_receipt(session))
    else:
        typer.echo(
            render_meld_receipt(session)
            if session.state == "APPLIED"
            else render_meld_incomplete_receipt(session)
        )
    if interactive_ran:
        if not terminal_session:
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
    if not catalog and not (sys.stdin.isatty() and sys.stdout.isatty()):
        typer.echo("No saved Meld sessions.")
        return
    by_key = {entry.key: entry for entry in catalog}
    receipt = choose_session(
        tuple(_meld_picker_entry(entry) for entry in catalog),
        title="MELD SESSIONS · RECENTLY MODIFIED",
        new_receipt=SessionNewReceipt(kind="meld", argv=("mem", "meld")),
    )
    if receipt is None:
        return
    if isinstance(receipt, SessionNewReceipt):
        if receipt.kind != "meld" or receipt.argv != ("mem", "meld"):
            raise MeldCommandError("Meld session picker returned an invalid receipt.")
        _start_new_meld_from_setup(store)
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


def _start_new_meld_from_setup(store: MemoryStore) -> None:
    """Collect one new Meld request without browsing saved sessions."""
    receipt = choose_meld_setup(store)
    if receipt is None:
        typer.echo("New Meld cancelled; no session was created.")
        return
    left = receipt.left_name
    right = receipt.right_name
    if receipt.mode == "directional":
        start_kwargs = {
            "left": left,
            "into": right,
            "left_descendants": receipt.left_descendants,
            "right_descendants": receipt.right_descendants,
        }
        if receipt.left_memory_uid is not None:
            start_kwargs["incoming_memory"] = receipt.left_memory_uid
        if receipt.right_memory_uid is not None:
            start_kwargs["baseline_memory"] = receipt.right_memory_uid
        cmd(**start_kwargs)
        return

    if receipt.target_name is None:
        raise MeldCommandError("Symmetric Meld setup omitted result C.")
    cmd(
        left=left,
        right=right,
        to=receipt.target_name,
        left_descendants=receipt.left_descendants,
        right_descendants=receipt.right_descendants,
    )


def cmd(
    left: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Directional INCOMING A, or symmetric PEER A when RESULT/--to "
                "is supplied; an unambiguously non-Context sole sentence is "
                "inline Memory content"
            )
        ),
    ] = None,
    right: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Directional BASELINE B, or symmetric PEER B when RESULT/--to "
                "is supplied"
            )
        ),
    ] = None,
    result: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Symmetric RESULT C; equivalent to --to and created when absent"
            )
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help=(
                "Explicit directional BASELINE alias for 'mem meld INCOMING BASELINE'"
            ),
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=(
                "Symmetric RESULT C alias for the third positional Context; "
                "created when absent"
            ),
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Directional INCOMING alias for 'mem meld INCOMING' when the "
                "current Context supplies BASELINE"
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
    expect_session: Annotated[
        Optional[str],
        typer.Option(
            "--expect-session",
            metavar="SHA256",
            help="Require the exact saved Meld revision reviewed for this turn",
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
            help="Enter the interactive Meld session launcher",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only the selected LEFT/INCOMING and RIGHT/BASELINE roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both Meld roots",
        ),
    ] = False,
    left_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--left-descendants/--left-root-only",
            legacy_root_only_option_alias("left"),
            help="Include all readable descendants under PEER or INCOMING A",
        ),
    ] = None,
    right_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--right-descendants/--right-root-only",
            legacy_root_only_option_alias("right"),
            help=(
                "Include readable descendants under PEER B, or writable "
                "owner Contexts under directional BASELINE B"
            ),
        ),
    ] = None,
    memory: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            help=(
                "Use exact text as one process-local INCOMING Memory; the "
                "current Context or --into supplies BASELINE"
            ),
        ),
    ] = None,
    incoming_memory: Annotated[
        Optional[str],
        typer.Option(
            "--incoming-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "In directional Meld, select one INCOMING Memory while its "
                "neighbors remain non-actionable context"
            ),
        ),
    ] = None,
    baseline_memory: Annotated[
        Optional[str],
        typer.Option(
            "--baseline-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "In directional Meld, restrict mutation to one BASELINE Memory "
                "while its neighbors remain non-actionable context"
            ),
        ),
    ] = None,
) -> None:
    """Meld INCOMING Context/Memory into BASELINE; add RESULT for peers."""
    scope_flags_supplied = (
        direct
        or recursive
        or left_descendants is not None
        or right_descendants is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        left_descendants, right_descendants = resolve_descendant_scopes(
            preset=preset,
            explicit=(left_descendants, right_descendants),
        )
    except (TypeError, ValueError) as error:
        typer.secho(
            f"Meld error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
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
    if expect_session is not None and not (
        comment is not None or choice is not None or preserve_all or defer_all
    ):
        typer.secho(
            "Meld error: --expect-session is valid only for a semantic or defer turn.",
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
    if result is not None and to is not None:
        typer.secho(
            "Meld error: supply symmetric RESULT C either positionally or with "
            "--to, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if (to is not None or result is not None) and (
        into is not None or from_ is not None
    ):
        typer.secho(
            "Meld error: symmetric RESULT C/--to cannot be combined with "
            "directional --into or --from.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if from_ is not None and any(value is not None for value in (left, right, result)):
        typer.secho(
            "Meld error: --from supplies INCOMING and cannot be combined "
            "with positional Contexts.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if memory is not None and any(
        value is not None
        for value in (left, right, result, to, from_, incoming_memory)
    ):
        typer.secho(
            "Meld error: --memory supplies INCOMING content and cannot be "
            "combined with positional sources, symmetric RESULT, --from, or "
            "--incoming-memory.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    browse_by_default = (
        left is None
        and right is None
        and result is None
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
        and not left_descendants
        and not right_descendants
        and incoming_memory is None
        and baseline_memory is None
        and memory is None
        and revision is None
        and not revises_turn
        and expect_session is None
        and expand is None
        and not scope_flags_supplied
    )
    if sessions and not browse_by_default:
        typer.secho(
            "Meld error: --sessions cannot be combined with source operands "
            "or Meld actions.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)

    store = MemoryStore(create=False)
    try:
        if sessions:
            _browse_saved_meld_sessions(store)
            return
        if browse_by_default:
            _start_new_meld_from_setup(store)
            return
        current_name = store.current_context_name()
        create_target = False
        explicit_result = result if result is not None else to
        incoming_text = memory
        if incoming_text is not None:
            requested_mode = "DIRECTIONAL"
            if left_descendants:
                raise MeldCommandError(
                    "Inline --memory cannot be combined with INCOMING descendants."
                )
            left_name = INLINE_MELD_CONTEXT_NAME
            if into is not None:
                right_name = resolve_context_locator(into, current=current_name)
            else:
                if not current_name:
                    raise MeldCommandError(
                        "Inline --memory uses the current Context as BASELINE, "
                        "but no current Context is available. Supply --into BASELINE."
                    )
                right_name = current_name
            target_name = right_name
            start_command = shlex.join(
                ["mem", "meld", "--memory", incoming_text, "--into", right_name]
            )
        elif from_ is not None:
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
            start_command = shlex.join(["mem", "meld", left_name, right_name])
        elif into is not None:
            if right is not None or result is not None:
                raise MeldCommandError(
                    "Directional --into accepts at most one positional INCOMING "
                    "Context. Use 'mem meld INCOMING BASELINE' instead."
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
            start_command = shlex.join(["mem", "meld", left_name, right_name])
        elif explicit_result is not None:
            if left is None or right is None:
                raise MeldCommandError(
                    "Symmetric Meld requires PEER A and PEER B before RESULT C. "
                    "Use 'mem meld PEER_A PEER_B --to RESULT_C' or "
                    "'mem meld PEER_A PEER_B RESULT_C'."
                )
            requested_mode = "SYMMETRIC"
            left_name = resolve_context_locator(left, current=current_name)
            right_name = resolve_context_locator(right, current=current_name)
            # RESULT C can be created, so its exact name deliberately does not
            # pass through the existing-Context locator resolver. Existing
            # empty or exactly session-bound results retain that same name.
            target_name = explicit_result
            start_command = shlex.join(
                ["mem", "meld", left_name, right_name, "--to", target_name]
            )
        elif left is not None and right is not None:
            requested_mode = "DIRECTIONAL"
            left_name = resolve_context_locator(left, current=current_name)
            right_name = resolve_context_locator(right, current=current_name)
            target_name = right_name
            start_command = shlex.join(["mem", "meld", left_name, right_name])
        elif left is not None:
            if not current_name:
                raise MeldCommandError(
                    "'mem meld INCOMING' uses the current Context as BASELINE, "
                    "but no current Context is available. Supply "
                    "'mem meld INCOMING BASELINE'."
                )
            requested_mode = "DIRECTIONAL"
            if _is_inline_memory_operand(
                store,
                left,
                current_name=current_name,
            ):
                incoming_text = left
                if left_descendants:
                    raise MeldCommandError(
                        "Inline Memory input cannot be combined with INCOMING "
                        "descendants."
                    )
                left_name = INLINE_MELD_CONTEXT_NAME
            else:
                left_name = resolve_context_locator(left, current=current_name)
            right_name = current_name
            target_name = right_name
            start_command = shlex.join(
                ["mem", "meld", "--memory", incoming_text]
                if incoming_text is not None
                else ["mem", "meld", left_name]
            )
        else:
            raise MeldCommandError(
                "Starting Meld requires INCOMING, INCOMING BASELINE, or "
                "PEER_A PEER_B RESULT_C Contexts."
            )

        if requested_mode == "DIRECTIONAL":
            if incoming_memory is not None and left_descendants:
                raise MeldCommandError(
                    "--incoming-memory cannot be combined with --left-descendants."
                )
            if baseline_memory is not None and right_descendants:
                raise MeldCommandError(
                    "--baseline-memory cannot be combined with --right-descendants."
                )
            start_parts = (
                ["mem", "meld", "--memory", incoming_text, "--into", right_name]
                if incoming_text is not None
                else ["mem", "meld", left_name, right_name]
            )
            if left_descendants:
                start_parts.append("--left-descendants")
            if right_descendants:
                start_parts.append("--right-descendants")
            if incoming_memory is not None:
                start_parts.extend(("--incoming-memory", incoming_memory))
            if baseline_memory is not None:
                start_parts.extend(("--baseline-memory", baseline_memory))
        else:
            if incoming_memory is not None or baseline_memory is not None:
                raise MeldCommandError(
                    "Memory scope flags are supported only by directional Meld."
                )
            start_parts = ["mem", "meld", left_name]
            if left_descendants:
                start_parts.append("--left-descendants")
            start_parts.append(right_name)
            if right_descendants:
                start_parts.append("--right-descendants")
            start_parts.extend(("--to", target_name))
        start_command = shlex.join(start_parts)

        if left_name == right_name:
            if requested_mode == "DIRECTIONAL":
                raise MeldCommandError(
                    "Directional Meld requires different INCOMING and BASELINE "
                    f"Contexts; both resolved to '{left_name}'."
                )
            raise MeldCommandError("The two PEER source Contexts must be distinct.")
        if requested_mode == "SYMMETRIC" and target_name in {
            left_name,
            right_name,
        }:
            raise MeldCommandError(
                "Symmetric Meld requires PEER A, PEER B, and RESULT C to be "
                f"distinct; RESULT '{target_name}' is also a PEER source."
            )
        left_access: ContextAccess | None = None
        right_access: ContextAccess | None = None
        if requested_mode == "DIRECTIONAL":
            right_access = _resolve_meld_source(
                store,
                right_name,
                current_name=current_name,
            )
            if incoming_text is not None:
                if right_access.is_granted:
                    raise MeldCommandError(
                        "Inline-Memory Meld currently requires a local "
                        "BASELINE/Target."
                    )
            else:
                left_access = _resolve_meld_source(
                    store,
                    left_name,
                    current_name=current_name,
                )
                authorize_combination((left_access, right_access))
                authorize_derived_transfer(left_access, right_access)
                retention = analysis_retention((left_access, right_access))
                if retention is None:
                    raise ProfileError(
                        "The directional Meld cannot save analysis under the "
                        "available Grants."
                    )
                authorize_analysis_save(
                    (left_access, right_access),
                    retention=retention,
                )

        if requested_mode == "SYMMETRIC" and not store.context_exists(target_name):
            create_target = True
        if create_target:
            # The runtime allocates and publishes the real Context atomically
            # with its session. This placeholder carries only the reviewed name
            # through the CLI's provider-free Compare prerequisite flow.
            target = Context(uid="", name=target_name)
            session = None
        else:
            target = (
                _load_meld_source(right_access)
                if requested_mode == "DIRECTIONAL" and right_access is not None
                else store.load_direct(target_name)
            )
            session = store.load_meld_session(target.uid)
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
            request = MeldStartRequest(
                mode=requested_mode,
                left_name=left_name,
                right_name=right_name,
                target_name=target_name,
                left_descendants=left_descendants,
                right_descendants=right_descendants,
                create_target=create_target,
                incoming_memory=incoming_memory,
                baseline_memory=baseline_memory,
                incoming_text=incoming_text,
            )
            from memcommit.operations.meld.runtime import (
                execute_meld_start,
                prepare_meld_start,
            )

            prepared = prepare_meld_start(request, store=store)
            directional_prewarm_origin = (
                prepared.directional_prewarm.origin
                if prepared.directional_prewarm is not None
                else None
            )
            if prepared.provider_required:

                def start_meld(progress):
                    def connected_provider():
                        provider = connect_codex_chatgpt_provider()
                        progress.update("analyzing meld turn", step=2)
                        return provider

                    return execute_meld_start(
                        request,
                        store=store,
                        provider_factory=connected_provider,
                        prepared=prepared,
                    )

                stage = (
                    "connecting provider"
                    if requested_mode == "DIRECTIONAL"
                    else "preparing ordered Compare basis"
                )
                started = run_command_wait(
                    "MELD",
                    stage,
                    total=2,
                    work=start_meld,
                )
            else:
                started = execute_meld_start(
                    request,
                    store=store,
                    provider_factory=lambda: (_ for _ in ()).throw(
                        AssertionError("A prepared Meld start connected a provider.")
                    ),
                    prepared=prepared,
                )
            session = started.session
            if requested_mode == "DIRECTIONAL":
                directional_prewarm_origin = (
                    started.origin if started.origin != "PROVIDER" else None
                )
            session = _complete_default_terminal_execution(
                store=store,
                session=session,
            )
            if requested_mode == "DIRECTIONAL" and directional_prewarm_origin:
                label = (
                    "EXACT PREWARM"
                    if directional_prewarm_origin == "EXACT_PREWARM"
                    else "EQUIVALENT SCOPE PREWARM"
                    if directional_prewarm_origin == "EQUIVALENT_SCOPE_PREWARM"
                    else "PROJECTED PREWARM"
                )
                phase = "INITIAL ANALYSIS" if len(session.turns) > 1 else "ANALYSIS"
                typer.echo(f"{phase} · {label} · PROVIDER NOT CALLED")
            typer.echo(
                render_meld_receipt(session)
                if session.state == "APPLIED"
                else render_meld_incomplete_receipt(session)
            )
            return

        if restart:
            prior_digest = meld_canonical_digest(session.to_dict())
            restart_request = MeldRestartRequest(
                mode=requested_mode,
                left_name=left_name,
                right_name=right_name,
                target_name=target_name,
                expected_version=prior_digest,
                left_descendants=left_descendants,
                right_descendants=right_descendants,
                incoming_memory=incoming_memory,
                baseline_memory=baseline_memory,
                incoming_text=incoming_text,
            )
            from memcommit.operations.meld.runtime import (
                execute_meld_restart,
                prepare_meld_restart,
            )

            prepared = prepare_meld_restart(restart_request, store=store)
            if prepared.provider_required:

                def restart_meld(progress):
                    def connected_provider():
                        provider = connect_codex_chatgpt_provider()
                        progress.update("analyzing meld turn", step=2)
                        return provider

                    return execute_meld_restart(
                        restart_request,
                        store=store,
                        provider_factory=connected_provider,
                        prepared=prepared,
                    )

                stage = (
                    "connecting provider"
                    if requested_mode == "DIRECTIONAL"
                    else "preparing ordered Compare basis"
                )
                restarted = run_command_wait(
                    "MELD",
                    stage,
                    total=2,
                    work=restart_meld,
                )
            else:
                restarted = execute_meld_restart(
                    restart_request,
                    store=store,
                    provider_factory=lambda: (_ for _ in ()).throw(
                        AssertionError("A prepared Meld restart connected a provider.")
                    ),
                    prepared=prepared,
                )
            session = restarted.session
            session = _complete_default_terminal_execution(
                store=store,
                session=session,
            )
            typer.echo(
                render_meld_receipt(session)
                if session.state == "APPLIED"
                else render_meld_incomplete_receipt(session)
            )
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
        sources_match = sources_match and tuple(
            bool(frame.include_descendants) for frame in session.frames
        ) == (left_descendants, right_descendants)
        sources_match = sources_match and (
            (
                session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION
                and len(session.frames[0].memories) == 1
                and session.frames[0].memories[0].content == incoming_text
            )
            if incoming_text is not None
            else session.schema_version != MELD_INLINE_MEMORY_SCHEMA_VERSION
        )
        for selector, frame, label in (
            (incoming_memory, session.frames[0], "INCOMING Memory"),
            (baseline_memory, session.frames[1], "BASELINE Memory"),
        ):
            requested_uid = None
            if selector is not None:
                try:
                    focus = resolve_memory_focus(
                        (*frame.memories, *frame.context_evidence),
                        selector,
                        label=label,
                    )
                except MemoryFocusError as error:
                    raise MeldCommandError(str(error)) from error
                requested_uid = focus.selected_uid
            sources_match = sources_match and (
                frame.selected_memory_uid == requested_uid
            )
        if not sources_match:
            raise MeldCommandError(
                "The target already has a meld from different sources. Use "
                "--restart to replace it."
            )
        expected_session_digest = meld_canonical_digest(session.to_dict())
        if (
            expect_session is not None
            and expect_session != expected_session_digest
        ):
            raise MeldCommandError(
                "The saved Meld session changed after this command was reviewed. "
                "Reopen it and rebuild the turn command."
            )
        from memcommit.operations.meld.runtime import (
            execute_meld_preservation,
            execute_meld_session_defer,
        )
        from memcommit.meld_session_application import (
            MeldSessionSnapshot,
            prepare_meld_preservation_turn,
        )
        from memcommit.meld_resolution_application import (
            MeldResolutionTurnRequest,
            prepare_meld_resolution_turn,
        )

        session_snapshot = MeldSessionSnapshot(
            session=session,
            version_token=expected_session_digest,
        )
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
            typer.echo(render_meld_receipt(session, recovered=recovered))
            return

        if defer_all:
            session = execute_meld_session_defer(
                session_snapshot,
                store=store,
            ).session
            typer.echo(render_meld_incomplete_receipt(session))
            typer.secho(
                "Deferred this meld without changing the target.",
                fg=typer.colors.YELLOW,
            )
            return

        if preserve_all:
            pending = prepare_meld_preservation_turn(
                session_snapshot,
                guidance=_preserve_all_guidance(session),
            )
            session = pending.session
            if (
                session.mode == "SYMMETRIC"
                and session.schema_version >= MELD_SCHEMA_VERSION
            ):
                session = execute_meld_preservation(pending, store=store).session
            else:
                session = _assess_and_save(
                    store=store,
                    session=session,
                    provider_factory=connect_codex_chatgpt_provider,
                    expected_session_digest=expected_session_digest,
                )
            typer.echo(render_meld_incomplete_receipt(session))
            return

        if comment is not None or choice is not None:
            selected_issue = (
                _issue_selector(session, issue) if issue is not None else None
            )
            option_uid = None
            if choice is not None:
                assert selected_issue is not None
                if choice > len(selected_issue.options):
                    raise MeldCommandError(
                        f"Issue has only {len(selected_issue.options)} choices."
                    )
                option_uid = selected_issue.options[choice - 1].uid
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
            session = prepare_meld_resolution_turn(
                MeldResolutionTurnRequest(
                    snapshot=session_snapshot,
                    comment=comment or "",
                    issue_uid=(
                        selected_issue.uid if selected_issue is not None else None
                    ),
                    option_uid=option_uid,
                    revision=revision_value,  # type: ignore[arg-type]
                    revises_turn_uids=revises,
                )
            ).session
            session = _assess_and_save(
                store=store,
                session=session,
                provider_factory=connect_codex_chatgpt_provider,
                expected_session_digest=expected_session_digest,
            )
            typer.echo(render_meld_incomplete_receipt(session))
            return

        expanded_uid = None
        if expand is not None:
            expanded_uid = _issue_selector(session, expand).uid
        interactive_ran = (
            expand is None
            and _interactive_terminal()
            and session.state not in {"APPLIED", "KEPT_REVIEW_ONLY"}
        )
        if interactive_ran:
            session = _complete_default_terminal_execution(
                store=store,
                session=session,
            )
        typer.echo(
            render_meld_receipt(session)
            if session.state == "APPLIED"
            else render_meld_session(
                session,
                expanded_issue_uid=expanded_uid,
            )
            if expanded_uid is not None
            else render_meld_incomplete_receipt(session)
        )
        if interactive_ran:
            typer.secho(
                (
                    "Meld completed without an opinion-submission turn."
                    if session.state == "APPLIED"
                    else "Meld ended without opening a response turn."
                ),
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
        ComparisonProviderError,
        ConcurrentContextUpdateError,
        MeldError,
        MeldProviderError,
        MeldCommandError,
        MeldSessionCatalogError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        StudyPrewarmRegistryError,
    ) as error:
        typer.secho(f"Meld error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
