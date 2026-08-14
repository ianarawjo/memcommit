"""Create, ground, resume, and explicitly apply bounded Context melds."""

from __future__ import annotations

import hashlib
import shlex
import sys
from contextlib import ExitStack
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonInput,
)
from memcommit.comparison_provider import (
    ComparisonProviderError,
    analyze_comparison,
)
from memcommit.comparison_store import load_comparison_analysis
from memcommit.commands.comparison_execution import (
    comparison_wait_view,
    connect_comparison_provider,
    ensure_comparison_analysis,
    install_prepared_comparison_analysis,
)
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.context_targeting.loading import load_context_scope
from memcommit.context_locator import resolve_context_locator
from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.commands.command_wait import (
    CommandWaitView,
    build_report_loading_view,
    run_command_wait,
)
from memcommit.commands.endpoint_setup_flows import choose_meld_setup
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
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MELD_SCHEMA_VERSION,
    MeldCheckpointReceipt,
    MeldError,
    MeldFrame,
    MeldIssue,
    MeldRepairableAssessmentError,
    MeldSession,
    materialize_preservation_assessment,
    meld_accounting,
    meld_canonical_digest,
)
from memcommit.meld_provider import (
    MeldProviderError,
    assess_meld_turn,
    repair_meld_assessment,
)
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.commands.meld_shell import run_meld_shell
from memcommit.commands.meld_sessions import (
    MeldSessionCatalogEntry,
    MeldSessionCatalogError,
    list_meld_session_catalog,
    reload_selected_meld_session,
)
from memcommit.commands.session_picker import (
    SessionNewReceipt,
    SessionOpenReceipt,
    SessionPickerEntry,
    choose_session,
)
from memcommit.query_provider import (
    CodexChatGPTProvider,
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.profile_config import ProfileConfigError, load_profile_registry
from memcommit.profiles import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.granted_update_application import _remove_checkpoint
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
    validate_context_name,
)
from memcommit.study_prewarm.registry import StudyPrewarmRegistryError


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
    include_descendants: tuple[bool, bool] = (False, False),
    directional: bool = False,
) -> MeldCommandError:
    compare_argv = [
        "mem",
        "compare",
        "--from",
        left.name,
        "--to",
        right.name,
    ]
    if include_descendants[0]:
        compare_argv.append("--reference-descendants")
    if include_descendants[1]:
        compare_argv.append("--compared-descendants")
    if refresh:
        compare_argv.append("--refresh")
    rerun_argv = (
        ["mem", "meld", left.name, "--into", right.name]
        if directional
        else ["mem", "meld", left.name, right.name]
    )
    if include_descendants[0]:
        rerun_argv.append("--left-descendants")
    if include_descendants[1]:
        rerun_argv.append("--right-descendants")
    if create_target and not directional:
        rerun_argv.extend(("--to", target.name))
    lines = [
        reason,
        "Create the exact ordered Compare basis first:",
        f"  {shlex.join(compare_argv)}",
    ]
    if not create_target and not directional:
        lines.append(f"  {shlex.join(['mem', 'switch', target.name])}")
    lines.extend(("Then rerun:", f"  {shlex.join(rerun_argv)}"))
    return MeldCommandError("\n".join(lines))


def _load_symmetric_comparison(
    *,
    left: Context,
    right: Context,
    target: Context,
    create_target: bool = False,
    include_descendants: tuple[bool, bool] = (False, False),
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
            include_descendants=include_descendants,
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
            include_descendants=include_descendants,
        )
    if (
        not analysis.matches(left, right)
        or analysis.include_descendants != include_descendants
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
            include_descendants=include_descendants,
        )
    return analysis


def _analyze_symmetric_comparison_basis(
    comparison_input: ComparisonInput,
    *,
    target_name: str,
) -> ComparisonAnalysis:
    """Create a missing or stale symmetric basis without changing current."""

    def compare_frames(progress):
        provider = connect_comparison_provider(
            connect_codex_chatgpt_provider
        )
        progress.update("analyzing ordered source relations", step=2)
        return analyze_comparison(comparison_input, provider)

    confirmed_inputs = _symmetric_comparison_wait_context_view(
        comparison_input,
        target_name=target_name,
    )
    return run_command_wait(
        "MELD",
        "preparing ordered Compare basis",
        total=2,
        work=compare_frames,
        # The destination keys retain one meaning across every wait: Report is
        # the default R/r surface, while I/i exposes all three frozen operands
        # so a cross-task current Context cannot look implicit.
        return_view=build_report_loading_view(
            "MELD",
            sections=(
                "What mem understood",
                "Both",
                "Differences",
                "Items",
            ),
        ),
        context_view=confirmed_inputs,
    )


def _symmetric_comparison_wait_context_view(
    comparison_input: ComparisonInput,
    *,
    target_name: str,
) -> CommandWaitView:
    """Show all three frozen symmetric operands while Compare is pending."""

    base = comparison_wait_view(comparison_input)
    assert isinstance(base.text, str)
    source_text = base.text.partition(
        "\nThe comparison report will replace this setup"
    )[0]
    return CommandWaitView(
        title="MELD CONFIRMED INPUTS · READ-ONLY",
        text=(
            source_text.rstrip()
            + "\n\n"
            + f"RESULT C · {safe_terminal_text(target_name)}\n"
            + "  TARGET STATE · UNCHANGED WHILE COMPARE RUNS\n\n"
            + "The ordered Compare basis will be saved before the Meld "
            + "target and session are published."
        ),
    )


def _ensure_symmetric_comparison(
    *,
    store: MemoryStore,
    left_access: ContextAccess,
    right_access: ContextAccess,
    left: Context,
    right: Context,
    target_name: str,
    current_name: str | None,
    include_descendants: tuple[bool, bool] = (False, False),
) -> ComparisonAnalysis:
    """Return the exact durable LEFT→RIGHT basis, creating it when needed."""

    from memcommit.study_prewarm.compare import (
        EquivalentComparePrewarmMatch,
        find_declared_equivalent_compare_analysis,
        find_declared_projected_compare_analysis,
        record_equivalent_compare_prewarm,
        record_exact_compare_prewarm,
        record_projected_compare_prewarm,
    )

    equivalent_match: EquivalentComparePrewarmMatch | None = None

    def equivalent(comparison_input):
        nonlocal equivalent_match
        equivalent_match = find_declared_equivalent_compare_analysis(
            store=store,
            comparison_input=comparison_input,
            current_name=current_name,
            registry_snapshot=load_profile_registry(),
        )
        if equivalent_match is None:
            equivalent_match = find_declared_projected_compare_analysis(
                store=store,
                comparison_input=comparison_input,
                current_name=current_name,
                registry_snapshot=load_profile_registry(),
            )
        return equivalent_match.analysis if equivalent_match is not None else None

    execution = ensure_comparison_analysis(
        store=store,
        reference_access=left_access,
        compared_access=right_access,
        reference=left,
        compared=right,
        current_name=current_name,
        include_descendants=include_descendants,
        require_durable=True,
        analyze=lambda comparison_input: _analyze_symmetric_comparison_basis(
            comparison_input,
            target_name=target_name,
        ),
        equivalent=equivalent,
    )
    if (
        execution.origin == "EQUIVALENT_SCOPE_PREWARM"
        and equivalent_match is not None
    ):
        if equivalent_match.origin == "EXACT_PREWARM":
            record_exact_compare_prewarm(
                store,
                entry_key=equivalent_match.entry_key,
                analysis=execution.analysis,
            )
        else:
            recorder = (
                record_projected_compare_prewarm
                if equivalent_match.origin == "PROJECTED_PREWARM"
                else record_equivalent_compare_prewarm
            )
            recorder(
                store,
                entry_key=equivalent_match.entry_key,
                analysis=execution.analysis,
                prepared_context_names=equivalent_match.prepared_context_names,
            )
    return execution.analysis


def _load_directional_comparison(
    *,
    store: MemoryStore,
    incoming_access: ContextAccess,
    baseline_access: ContextAccess,
    incoming: Context,
    baseline: Context,
    current_name: str | None,
    include_descendants: tuple[bool, bool] = (False, False),
) -> ComparisonAnalysis | None:
    """Load an exact ordered basis when present, retaining legacy fallback.

    Existing Directional sessions predate the Compare contract. Absence keeps
    that compatible one-shot path, while any present artifact must be current:
    silently ignoring a stale reviewed basis would make two identical commands
    appear Compare-backed while using different semantics.
    """
    try:
        analysis = load_comparison_analysis(incoming.uid, baseline.uid)
        if analysis is None:
            artifact = load_granted_comparison_artifact(
                store,
                incoming.uid,
                baseline.uid,
            )
            analysis = artifact.analysis if artifact is not None else None
    except ValueError as error:
        raise _comparison_prerequisite_error(
            left=incoming,
            right=baseline,
            target=baseline,
            refresh=True,
            reason="The saved ordered Directional Compare analysis is invalid.",
            include_descendants=include_descendants,
            directional=True,
        ) from error
    if analysis is None:
        comparison_input = ComparisonInput.from_contexts(
            incoming,
            baseline,
            reference_descendants=include_descendants[0],
            compared_descendants=include_descendants[1],
        )
        from memcommit.study_prewarm.compare import (
            record_equivalent_compare_prewarm,
            record_projected_compare_prewarm,
        )
        from memcommit.study_prewarm.meld_directional import (
            find_installed_equivalent_directional_comparison,
        )

        equivalent = find_installed_equivalent_directional_comparison(
            store=store,
            comparison_input=comparison_input,
            registry_snapshot=load_profile_registry(),
        )
        if equivalent is None:
            return None
        installed = install_prepared_comparison_analysis(
            store=store,
            reference_access=incoming_access,
            compared_access=baseline_access,
            reference=incoming,
            compared=baseline,
            current_name=current_name,
            include_descendants=include_descendants,
            analysis=equivalent.analysis,
        )
        recorder = (
            record_projected_compare_prewarm
            if equivalent.origin == "PROJECTED_PREWARM"
            else record_equivalent_compare_prewarm
        )
        recorder(
            store,
            entry_key=equivalent.entry_key,
            analysis=installed.analysis,
            prepared_context_names=equivalent.prepared_context_names,
        )
        return installed.analysis
    if (
        not analysis.matches(incoming, baseline)
        or analysis.include_descendants != include_descendants
        or analysis.ruleset_version != COMPARISON_RULESET_VERSION
    ):
        raise _comparison_prerequisite_error(
            left=incoming,
            right=baseline,
            target=baseline,
            refresh=True,
            reason=(
                f"The saved Directional Compare analysis for '{incoming.name}' → "
                f"'{baseline.name}' is stale."
            ),
            include_descendants=include_descendants,
            directional=True,
        )
    return analysis


def _session_command(session: MeldSession) -> str:
    """Return one explicit, portable command prefix for this saved meld."""
    left, right = session.frames
    parts = ["mem", "meld", left.context_name]
    if left.include_descendants:
        parts.append("--left-descendants")
    if session.mode == "DIRECTIONAL":
        parts.extend(("--into", right.context_name))
        if right.include_descendants:
            parts.append("--right-descendants")
    else:
        parts.append(right.context_name)
        if right.include_descendants:
            parts.append("--right-descendants")
    return shlex.join(parts)


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


def _connect_meld_provider(provider_factory):
    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        provider.timeout = max(
            provider.timeout,
            MELD_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


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
                "       OWNER · "
                + safe_terminal_text(proposal.owner_context_name)
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
    *,
    registry=None,
) -> tuple[Context, Context, Context]:
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
                _load_meld_source(
                    access,
                    include_descendants=bool(frame.include_descendants),
                    project=(
                        session.schema_version < MELD_OWNER_AWARE_SCHEMA_VERSION
                    ),
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
                raise MeldCommandError(
                    f"Source Context '{frame.context_name}' changed after this "
                    "meld was analyzed."
                )
            # A projected subtree digest cannot be compared to the root's
            # physical context.json under the store lock. Freeze every exact
            # local owner instead so the complete projection remains stable
            # through target CAS.
            physical_contexts = tuple(
                store.load_direct(context.name)
                for context in _walk_meld_target_contexts(scope)
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
            reloaded_projection = recursive_comparison_projection(reloaded_scope)
            if context_record_digest(reloaded_projection) != frame.context_digest:
                raise MeldCommandError(
                    f"Source Context '{frame.context_name}' changed after this "
                    "meld was analyzed."
                )
            continue
        bindings.append(
            (frame.context_name, frame.context_uid, frame.context_digest)
        )
    return tuple(bindings)


def _meld_wait_view(session: MeldSession) -> CommandWaitView:
    """Restore the last complete Meld report beneath one pending turn.

    A newly started turn intentionally has no assessment, so rendering the
    live object would replace the participant's report with only "pending".
    Reconstruct the immediately preceding durable view for display only and
    keep the submitted turn visibly separate. Initial analysis has no prior
    report and therefore shows its frozen route and pending state instead.
    """

    current = session.current_turn
    if current is None or current.assessment is not None or len(session.turns) <= 1:
        result_section = (
            "Proposed baseline changes"
            if session.mode == "DIRECTIONAL"
            else "Proposed target Memories"
        )
        return build_report_loading_view(
            "MELD",
            sections=(
                "What mem understood",
                "Relations",
                "Issues",
                result_section,
            ),
        )

    prior_turn = session.turns[-2]
    assert prior_turn.assessment is not None
    prior_payload = session.to_dict()
    prior_payload["turns"] = [turn.to_dict() for turn in session.turns[:-1]]
    prior_payload["state"] = (
        "READY_TO_APPLY"
        if prior_turn.assessment.ready_to_apply
        else "AWAITING_REPLY"
    )
    prior_session = MeldSession.from_dict(prior_payload)
    pending_lines = [
        render_meld_session(prior_session),
        "",
        "PENDING TURN · SUBMITTED · NOT YET INCORPORATED",
        f"SCOPE · {current.scope}",
    ]
    if current.issue_uids:
        pending_lines.append(
            "ISSUES · " + ", ".join(uid[:8] for uid in current.issue_uids)
        )
    if current.comment:
        pending_lines.extend(["", "COMMENT", safe_terminal_text(current.comment)])
    return CommandWaitView(
        title="PREVIOUS MELD REPORT · READ-ONLY",
        text=_meld_wait_fragments("\n".join(pending_lines)),
    )


def _meld_wait_context_view(session: MeldSession) -> CommandWaitView:
    """Show the exact route, scopes, and submitted turn frozen for analysis."""

    lines = [
        f"MEM MELD · {session.mode} · FROZEN INPUTS",
        _session_route(session),
        _session_scope(session),
        "",
        "SOURCE FRAMES",
    ]
    for frame in session.frames:
        scope = (
            "INCLUDE DESCENDANTS"
            if frame.include_descendants
            else "THIS CONTEXT ONLY"
        )
        lines.extend(
            [
                f"  {frame.role} · {safe_terminal_text(frame.context_name)}",
                f"    SCOPE · {scope}",
                f"    FROZEN MEMORIES · {len(frame.memories)}",
            ]
        )
    lines.extend(
        [
            "",
            f"TARGET · {safe_terminal_text(session.target.context_name)}",
            "TARGET STATE · UNCHANGED WHILE ANALYSIS RUNS",
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
        title="MELD CONFIRMED INPUTS · READ-ONLY",
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
    # This boundary is shared by initial analysis and every ISSUE/ALL follow-up.
    # Keep response incorporation on the same visible wait surface: Task 2
    # showed that a long second provider turn otherwise looks like a frozen
    # review even though the indivisible semantic call is still running.
    def assess(progress):
        provider = _connect_meld_provider(provider_factory)
        progress.update("analyzing meld turn", step=2)
        assessment = assess_meld_turn(session, provider)
        try:
            candidate = MeldSession.from_dict(session.to_dict())
            current = candidate.current_turn
            assert current is not None
            candidate.record_assessment(current.uid, assessment)
        except MeldRepairableAssessmentError as validation_error:
            # A decoded provider response may violate a cross-record invariant
            # that JSON Schema cannot express. Repair it once in the same
            # frozen turn; the validation error is not user evidence and no
            # partial proposal is published or applied.
            progress.update("repairing invalid meld turn", step=2)
            try:
                assessment = repair_meld_assessment(
                    session,
                    assessment,
                    str(validation_error),
                    provider,
                )
                candidate = MeldSession.from_dict(session.to_dict())
                current = candidate.current_turn
                assert current is not None
                candidate.record_assessment(current.uid, assessment)
            except MeldError as repair_error:
                raise MeldError(
                    "Meld validation repair failed after the initial response "
                    f"was rejected ({validation_error}): {repair_error}"
                ) from repair_error
        return candidate, assessment

    session, assessment = run_command_wait(
        "MELD",
        "connecting provider",
        total=2,
        work=assess,
        return_view=_meld_wait_view(session),
        context_view=_meld_wait_context_view(session),
    )
    # Provider latency creates a real race window. Rebind every source and the
    # target after the final call before persisting a claim about them.
    left, right, target = _load_bound_contexts(store, session)
    _assert_source_bindings(session, left, right)
    _assert_unapplied_target(session, target)
    if session.granted_target is not None:
        if session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION:
            with authority_grant_snapshot_lock() as registry:
                revalidate_granted_context_binding(
                    session.granted_target,
                    registry=registry,
                )
                _validate_owner_aware_grant_permissions(
                    session,
                    assessment.proposals,
                    registry=registry,
                )
        else:
            required = {
                "UPDATE" if proposal.operation == "EDIT" else "CREATE"
                for proposal in assessment.proposals
            }
            missing = sorted(required - set(session.granted_target.permissions))
            if missing:
                raise ProfileError(
                    "The BASELINE Grant does not authorize "
                    + " + ".join(missing)
                    + " required by the proposed Meld changes."
                )
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
    *,
    owner: tuple[str, str] | None = None,
) -> dict[str, object]:
    owner_aware = (
        session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
    )
    record: dict[str, object] = {
        "schema_version": (
            3
            if owner_aware
            else 2
            if session.mode == "DIRECTIONAL"
            else 1
        ),
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
                    {
                        "contexts": [
                            context.to_dict() for context in frame.contexts
                        ]
                    }
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


def _walk_meld_target_contexts(root: Context) -> tuple[Context, ...]:
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


def _affected_meld_owners(session: MeldSession, change_set) -> tuple[tuple[str, str], ...]:
    """Return target owners in the frozen BASELINE's canonical scope order."""
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
        # A zero-change acceptance still needs one durable command checkpoint.
        requested.add((baseline.context_uid, baseline.context_name))
    result = tuple(identity for identity in ordered if identity in requested)
    if len(result) != len(requested):
        raise MeldCommandError("A Meld proposal owner is outside the BASELINE scope.")
    return result


def _expected_owner_memories(
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
    for memory in baseline.memories:
        identity = (
            memory.owner_context_uid or baseline.context_uid,
            memory.owner_context_name or baseline.context_name,
        )
        if identity not in expected:
            raise MeldCommandError("A BASELINE Memory has an invalid owner.")
        expected[identity].append(Memory(uid=memory.uid, content=memory.content))
    positions = {
        identity: {memory.uid: index for index, memory in enumerate(memories)}
        for identity, memories in expected.items()
    }
    for proposal in change_set.proposals:
        identity = (proposal.owner_context_uid, proposal.owner_context_name)
        if identity not in expected:
            raise MeldCommandError("A Meld proposal owner is outside the BASELINE scope.")
        memory = Memory(uid=proposal.memory_uid, content=proposal.content)
        if proposal.operation == "EDIT":
            try:
                positions[identity][proposal.memory_uid]
            except KeyError as error:
                raise MeldCommandError(
                    "A directional Meld EDIT does not belong to its target owner."
                ) from error
            expected[identity][positions[identity][proposal.memory_uid]] = memory
        else:
            if proposal.memory_uid in positions[identity]:
                raise MeldCommandError("A directional Meld ADD collides with its owner.")
            positions[identity][proposal.memory_uid] = len(expected[identity])
            expected[identity].append(memory)
    return {identity: tuple(memories) for identity, memories in expected.items()}


def _recover_owner_aware_application(
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
        for context in _walk_meld_target_contexts(target)
    }
    expected = _expected_owner_memories(session, change_set)
    owners = _affected_meld_owners(session, change_set)
    # Recovery proves the complete selected BASELINE post-image, not merely
    # the owners this proposal happened to change. Otherwise unrelated drift
    # could be mistaken for a successfully completed prior application.
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


def _recover_application(
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


def _required_directional_target_permissions(change_set) -> tuple[str, ...]:
    required = {
        "UPDATE" if proposal.operation == "EDIT" else "CREATE"
        for proposal in change_set.proposals
    }
    return tuple(sorted(required))


def _validate_owner_aware_grant_permissions(
    session: MeldSession,
    proposals,
    *,
    registry,
) -> None:
    """Recheck each owner against the most-specific live Grant.

    A recursive root Grant can be narrowed below the root. The frozen root
    binding therefore cannot authorize every descendant write by itself.
    """
    binding = session.granted_target
    if binding is None:
        raise MeldCommandError("Expected a granted directional Meld target.")
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
                "A planned Meld owner is controlled by a different or "
                "changed Grant."
            )


def _apply_owner_proposals(
    direct: Context,
    proposals,
) -> Context:
    post_image = Context.from_dict(direct.to_dict())
    post_image._store_digest = direct._store_digest
    for proposal in proposals:
        memory = Memory(uid=proposal.memory_uid, content=proposal.content)
        if proposal.operation == "EDIT":
            post_image.replace(memory)
        else:
            if proposal.memory_uid in post_image.memories:
                raise MeldCommandError(
                    "A directional Meld ADD collides with an existing owner item."
                )
            post_image.add(memory)
    return post_image


def _granted_owner_name(binding, public_name: str) -> str:
    if not (
        public_name == binding.public_name
        or public_name.startswith(binding.public_name + "/")
    ):
        raise MeldCommandError(
            "A directional Meld owner is outside the granted BASELINE namespace."
        )
    # The selected public root may be a descendant of the Grant's resource
    # root. Map relative to the exact frozen endpoint, not the broader Grant.
    return binding.authority_context_name + public_name[len(binding.public_name) :]


def _accept_owner_aware_local(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
) -> tuple[bool, str, int]:
    """Apply one directional subtree Meld without flattening owner Contexts."""
    change_set = session.prepare_changes()
    owners = _affected_meld_owners(session, change_set)
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
        if index == 0 and session.granted_incoming is not None:
            continue
        local_lock_names.update(
            context.name
            for context in (frame.contexts or ())
        )

    receipts: tuple[MeldCheckpointReceipt, ...] | None = None
    recovered_result_uids: tuple[str, ...] = ()
    recovered_prior = False
    with store._command_write_lock():
        store._assert_profile_write_allowed()
        with store._context_write_locks(local_lock_names):
            left, right, target = _load_bound_contexts(store, session)
            _assert_non_target_source_bindings(session, left, right)
            recovered = _recover_owner_aware_application(
                session=session,
                target=target,
                change_set=change_set,
                checkpoint_store=store,
            )
            if recovered is not None:
                receipts, recovered_result_uids = recovered
                recovered_prior = True
            elif session.state == "APPLIED":
                raise MeldCommandError(
                    "The applied Meld receipt no longer matches its target owners."
                )
            else:
                _assert_unapplied_target(session, target)
                originals: dict[str, dict[str, object]] = {}
                expected_digests: dict[str, str] = {}
                post_images: dict[str, Context] = {}
                for _context_uid, context_name in owners:
                    direct = store.load_direct(context_name)
                    originals[context_name] = direct.to_dict()
                    expected_digests[context_name] = context_record_digest(direct)
                    post_images[context_name] = _apply_owner_proposals(
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
                                    "meld": _meld_checkpoint_record(
                                        session,
                                        change_set,
                                        owner=(context_uid, context_name),
                                    ),
                                    "command_contexts": command_contexts,
                                },
                                description=(
                                    f"Melded INCOMING '{session.frames[0].context_name}' "
                                    f"into BASELINE subtree '{session.target.context_name}': "
                                    f"{len(change_set.proposals)} changes"
                                ),
                            ),
                            expected_context_digest=expected_digests[context_name],
                        )
                        if checkpoint is None:
                            raise MeldCommandError(
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
                recovered_result_uids = tuple(
                    proposal.memory_uid for proposal in change_set.proposals
                )

    assert receipts
    if session.state == "APPLIED":
        assert session.application is not None
        if (
            session.application.checkpoints != receipts
            or session.application.result_memory_uids != recovered_result_uids
        ):
            raise MeldCommandError(
                "The applied Meld receipt no longer matches its checkpoints."
            )
        return True, receipts[0].checkpoint_uid, len(recovered_result_uids)
    session.record_application(
        change_set_digest=change_set.digest,
        checkpoint_uid=receipts[0].checkpoint_uid,
        result_memory_uids=recovered_result_uids,
        checkpoints=receipts,
    )
    store.save_meld_session(
        session,
        expected_session_digest=expected_session_digest,
    )
    return recovered_prior, receipts[0].checkpoint_uid, len(recovered_result_uids)


def _accept_owner_aware_granted(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
) -> tuple[bool, str, int]:
    binding = session.granted_target
    if binding is None:
        raise ValueError("Expected a granted directional Meld target.")
    change_set = session.prepare_changes()
    owners = _affected_meld_owners(session, change_set)
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
        authority_source = target_access.view.authority.source or {}
        if (
            target_access.view.authority.name.casefold() == "study-baseline"
            or authority_source.get("kind") == "STUDY_BASELINE"
        ):
            raise MeldCommandError(
                "The fixed study-baseline Profile cannot be updated."
            )
        _validate_owner_aware_grant_permissions(
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
            context.name: _granted_owner_name(binding, context.name)
            for context in (session.frames[1].contexts or ())
        }
        authority_lock_names = set(target_name_by_public.values())
        if session.granted_incoming is not None:
            source_binding = session.granted_incoming
            source_lock_names = {
                _granted_owner_name(source_binding, context.name)
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

            left, right, public_target = _load_bound_contexts(
                store,
                session,
                registry=registry,
            )
            _assert_non_target_source_bindings(session, left, right)
            recovered = _recover_owner_aware_application(
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
                raise MeldCommandError(
                    "The applied granted Meld receipt no longer matches "
                    "the authority BASELINE subtree."
                )
            else:
                _assert_unapplied_target(session, public_target)
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
                    post_images[authority_name] = _apply_owner_proposals(
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
                                    "meld": _meld_checkpoint_record(
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
                                    f"Melded INCOMING '{session.frames[0].context_name}' "
                                    f"into granted BASELINE subtree "
                                    f"'{session.target.context_name}': "
                                    f"{len(change_set.proposals)} changes"
                                ),
                            ),
                            expected_context_digest=expected_digests[authority_name],
                        )
                        if checkpoint is None:
                            raise MeldCommandError(
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
                    raise MeldCommandError(
                        "The granted Meld receipt no longer matches its checkpoints."
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
        return recovered_prior, receipts[0].checkpoint_uid, len(result_uids)


def _accept_granted_directional(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
) -> tuple[bool, str, int]:
    """Apply a directional Meld to the authority-owned BASELINE.

    The participant owns the review session, while the authority owns the
    mutable Context and checkpoint.  Keep the Grant registry and all source
    and target records frozen until the authority write is verified; if the
    participant receipt cannot be saved, restore that write before returning.
    """

    binding = session.granted_target
    if session.mode != "DIRECTIONAL" or binding is None:
        raise ValueError("Expected a granted directional Meld target.")
    if session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION:
        return _accept_owner_aware_granted(
            store=store,
            session=session,
            expected_session_digest=expected_session_digest,
        )
    change_set = session.prepare_changes()
    required_permissions = _required_directional_target_permissions(change_set)

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
            raise MeldCommandError(
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

            left, right, public_target = _load_bound_contexts(
                store,
                session,
                registry=registry,
            )
            _assert_non_target_source_bindings(session, left, right)
            recovered = _recover_application(
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
                    raise MeldCommandError(
                        "The applied granted Meld receipt no longer matches "
                        "the authority BASELINE and checkpoint."
                    )
                return True, recovered[0], len(recovered[1])
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
            _assert_unapplied_target(session, public_target)

            direct = authority_store.load_direct(target_lock_name)
            original = direct.to_dict()
            post_image = Context.from_dict(direct.to_dict())
            post_image._store_digest = direct._store_digest
            for proposal in change_set.proposals:
                memory = Memory(uid=proposal.memory_uid, content=proposal.content)
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
                            "meld": _meld_checkpoint_record(session, change_set),
                            "authority_target_context_name": target_lock_name,
                            "authority_grant": binding.to_dict(),
                        },
                        description=(
                            f"Melded INCOMING '{session.frames[0].context_name}' "
                            f"into granted BASELINE '{session.target.context_name}': "
                            f"{len(change_set.proposals)} changes"
                        ),
                    ),
                    expected_context_digest=context_record_digest(direct),
                )
                if checkpoint is None:
                    raise MeldCommandError(
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
    return False, checkpoint.uid, len(result_uids)


def _accept(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
    _granted_source_locked: bool = False,
) -> tuple[bool, str, int]:
    if session.mode == "DIRECTIONAL" and session.granted_target is not None:
        return _accept_granted_directional(
            store=store,
            session=session,
            expected_session_digest=expected_session_digest,
        )
    if session.granted_incoming is not None and not _granted_source_locked:
        # A granted read source must remain byte-identical from final
        # revalidation through the participant target checkpoint.  The local
        # save path cannot name an authority Context in its source lock set.
        with authority_grant_snapshot_lock() as registry:
            source_access = revalidate_granted_context_binding(
                session.granted_incoming,
                registry=registry,
            )
            with source_access.store._context_write_lock(
                source_access.context_name
            ):
                return _accept(
                    store=store,
                    session=session,
                    expected_session_digest=expected_session_digest,
                    _granted_source_locked=True,
                )
    if (
        session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
    ):
        return _accept_owner_aware_local(
            store=store,
            session=session,
            expected_session_digest=expected_session_digest,
        )
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
    allow_apply: bool = True,
    analysis_origin: str | None = None,
) -> MeldSession:
    """Run issue and whole-set turns through one shared interactive shell."""
    from memcommit.commands.resolution_workbench_shell import ResolutionDestination

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
            validate_context_name(name)
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
        action = run_meld_shell(
            session,
            navigation=navigation,
            review_only=not allow_apply,
            destination=destination,
            analysis_origin=analysis_origin,
        )
        if action is None:
            break
        expected = meld_canonical_digest(session.to_dict())
        if action.kind == "CHANGE_DESTINATION":
            if destination is None or action.destination is None:
                raise MeldCommandError(
                    "This Meld cannot change its save location."
                )
            validate_destination(action.destination)
            if action.destination != session.target.context_name:
                plan = store.plan_context_rename(
                    session.target.context_name,
                    action.destination,
                )
                store.rename_contexts(plan)
                relocated = store.load_meld_session(session.target.context_uid)
                if relocated is None or relocated.uid != session.uid:
                    raise MeldCommandError(
                        "The relocated Meld session could not be reloaded."
                    )
                session = relocated
            continue
        if action.kind == "DEFER_ALL":
            session.keep_review_only()
            store.save_meld_session(
                session,
                expected_session_digest=expected,
            )
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
    left_ctx = _load_meld_source(
        left_access,
        include_descendants=analysis.include_descendants[0],
    )
    right_ctx = _load_meld_source(
        right_access,
        include_descendants=analysis.include_descendants[1],
    )

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
        include_descendants=analysis.include_descendants,
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
        _start_new_meld_from_picker(store)
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


def _start_new_meld_from_picker(store: MemoryStore) -> None:
    """Collect the complete mode and endpoint shape in one setup shell."""
    receipt = choose_meld_setup(store)
    if receipt is None:
        typer.echo("New Meld cancelled; no session was created.")
        return
    left = receipt.left_name
    right = receipt.right_name
    if receipt.mode == "directional":
        cmd(
            left=left,
            into=right,
            left_descendants=receipt.left_descendants,
            right_descendants=receipt.right_descendants,
        )
        return

    if receipt.target_name is None:
        raise MeldCommandError("Symmetric Meld setup omitted result C.")
    current_name = store.current_context_name()
    left_access = _resolve_meld_source(
        store,
        left,
        current_name=current_name,
    )
    right_access = _resolve_meld_source(
        store,
        right,
        current_name=current_name,
    )
    left_ctx = _load_meld_source(
        left_access,
        include_descendants=receipt.left_descendants,
    )
    right_ctx = _load_meld_source(
        right_access,
        include_descendants=receipt.right_descendants,
    )
    analysis = _ensure_symmetric_comparison(
        store=store,
        left_access=left_access,
        right_access=right_access,
        left=left_ctx,
        right=right_ctx,
        target_name=receipt.target_name,
        current_name=current_name,
        include_descendants=(
            receipt.left_descendants,
            receipt.right_descendants,
        ),
    )
    session = start_reviewed_symmetric_meld(
        store=store,
        analysis=analysis,
        target_name=receipt.target_name,
        create_target=receipt.create_target,
    )
    typer.echo(render_meld_session(session))


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
            help="Enter the interactive Meld session launcher",
        ),
    ] = False,
    left_descendants: Annotated[
        bool,
        typer.Option(
            "--left-descendants/--left-only",
            help="Include all readable descendants under PEER or INCOMING A",
        ),
    ] = False,
    right_descendants: Annotated[
        bool,
        typer.Option(
            "--right-descendants/--right-only",
            help=(
                "Include readable descendants under PEER B, or writable "
                "owner Contexts under directional BASELINE B"
            ),
        ),
    ] = False,
) -> None:
    """Meld peers, or directionally update an authoritative BASELINE."""
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
        and not left_descendants
        and not right_descendants
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

        if requested_mode == "DIRECTIONAL":
            start_parts = ["mem", "meld", left_name]
            if left_descendants:
                start_parts.append("--left-descendants")
            start_parts.extend(("--into", right_name))
            if right_descendants:
                start_parts.append("--right-descendants")
        else:
            start_parts = ["mem", "meld", left_name]
            if left_descendants:
                start_parts.append("--left-descendants")
            start_parts.append(right_name)
            if right_descendants:
                start_parts.append("--right-descendants")
            if create_target:
                start_parts.extend(("--to", target_name))
        start_command = shlex.join(start_parts)

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
        left_access: ContextAccess | None = None
        right_access: ContextAccess | None = None
        if requested_mode == "DIRECTIONAL":
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
            left_ctx = (
                _load_meld_source(
                    left_access,
                    include_descendants=left_descendants,
                    project=requested_mode != "DIRECTIONAL",
                )
                if left_access is not None
                else _load_local_meld_source(
                    store,
                    left_name,
                    include_descendants=left_descendants,
                    project=requested_mode != "DIRECTIONAL",
                )
            )
            right_ctx = (
                _load_meld_source(
                    right_access,
                    include_descendants=right_descendants,
                    project=requested_mode != "DIRECTIONAL",
                )
                if right_access is not None
                else _load_local_meld_source(
                    store,
                    right_name,
                    include_descendants=right_descendants,
                    project=requested_mode != "DIRECTIONAL",
                )
            )
            meld_analysis_origin: str | None = None
            if requested_mode == "DIRECTIONAL":
                granted_incoming = (
                    freeze_granted_context_binding(left_access)
                    if left_access is not None and left_access.is_granted
                    else None
                )
                granted_target = (
                    freeze_granted_context_binding(right_access)
                    if right_access is not None and right_access.is_granted
                    else None
                )
                comparison = _load_directional_comparison(
                    store=store,
                    incoming_access=(
                        left_access
                        if left_access is not None
                        else resolve_context_access(
                            store,
                            left_name,
                            current_name=current_name,
                            required_permission="READ",
                        )
                    ),
                    baseline_access=(
                        right_access
                        if right_access is not None
                        else resolve_context_access(
                            store,
                            right_name,
                            current_name=current_name,
                            required_permission="READ",
                        )
                    ),
                    incoming=recursive_comparison_projection(left_ctx),
                    baseline=recursive_comparison_projection(right_ctx),
                    current_name=current_name,
                    include_descendants=(
                        left_descendants,
                        right_descendants,
                    ),
                )
                session = (
                    MeldSession.create_directional(
                        left_ctx,
                        right_ctx,
                        incoming_descendants=left_descendants,
                        baseline_descendants=right_descendants,
                        granted_incoming=granted_incoming,
                        granted_target=granted_target,
                    )
                    if comparison is None
                    else MeldSession.create_directional_from_comparison(
                        comparison,
                        left_ctx,
                        right_ctx,
                        granted_incoming=granted_incoming,
                        granted_target=granted_target,
                    )
                )
                session.start_initial_analysis()
                from memcommit.study_prewarm.meld_directional import (
                    find_installed_directional_meld_prewarm,
                )

                prewarm = find_installed_directional_meld_prewarm(
                    store=store,
                    current=session,
                    registry_snapshot=load_profile_registry(),
                )
                directional_prewarm_origin = (
                    prewarm.origin if prewarm is not None else None
                )
                meld_analysis_origin = directional_prewarm_origin
                if prewarm is None:
                    session = _assess_and_save(
                        store=store,
                        session=session,
                        provider_factory=connect_codex_chatgpt_provider,
                        expected_session_digest=None,
                    )
                else:
                    session = prewarm.session
                    _assert_source_bindings(session, left_ctx, right_ctx)
                    _assert_unapplied_target(session, right_ctx)
                    if session.granted_target is not None:
                        with authority_grant_snapshot_lock() as registry:
                            revalidate_granted_context_binding(
                                session.granted_target,
                                registry=registry,
                            )
                            assessment = session.current_assessment
                            assert assessment is not None
                            _validate_owner_aware_grant_permissions(
                                session,
                                assessment.proposals,
                                registry=registry,
                            )
                    store.save_meld_session(
                        session,
                        expected_session_digest=None,
                    )
            else:
                assert left_access is not None
                assert right_access is not None
                comparison = _ensure_symmetric_comparison(
                    store=store,
                    left_access=left_access,
                    right_access=right_access,
                    left=left_ctx,
                    right=right_ctx,
                    target_name=target.name,
                    current_name=current_name,
                    include_descendants=(
                        left_descendants,
                        right_descendants,
                    ),
                )
                from memcommit.study_prewarm.compare import (
                    installed_compare_prewarm_origin,
                )

                meld_analysis_origin = installed_compare_prewarm_origin(
                    store,
                    comparison,
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
                    analysis_origin=meld_analysis_origin,
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
                left_ctx = _load_meld_source(
                    restart_left_access,
                    include_descendants=left_descendants,
                )
                right_ctx = _load_meld_source(
                    restart_right_access,
                    include_descendants=right_descendants,
                )
            else:
                left_ctx = (
                    _load_meld_source(
                        left_access,
                        include_descendants=left_descendants,
                        project=False,
                    )
                    if left_access is not None
                    else _load_local_meld_source(
                        store,
                        left_name,
                        include_descendants=left_descendants,
                        project=False,
                    )
                )
                right_ctx = (
                    _load_meld_source(
                        right_access,
                        include_descendants=right_descendants,
                        project=False,
                    )
                    if right_access is not None
                    else _load_local_meld_source(
                        store,
                        right_name,
                        include_descendants=right_descendants,
                        project=False,
                    )
                )
            if requested_mode == "DIRECTIONAL":
                granted_incoming = (
                    freeze_granted_context_binding(left_access)
                    if left_access is not None and left_access.is_granted
                    else None
                )
                granted_target = (
                    freeze_granted_context_binding(right_access)
                    if right_access is not None and right_access.is_granted
                    else None
                )
                comparison = _load_directional_comparison(
                    store=store,
                    incoming_access=restart_left_access,
                    baseline_access=restart_right_access,
                    incoming=recursive_comparison_projection(left_ctx),
                    baseline=recursive_comparison_projection(right_ctx),
                    current_name=current_name,
                    include_descendants=(
                        left_descendants,
                        right_descendants,
                    ),
                )
                replacement = (
                    MeldSession.create_directional(
                        left_ctx,
                        right_ctx,
                        incoming_descendants=left_descendants,
                        baseline_descendants=right_descendants,
                        granted_incoming=granted_incoming,
                        granted_target=granted_target,
                    )
                    if comparison is None
                    else MeldSession.create_directional_from_comparison(
                        comparison,
                        left_ctx,
                        right_ctx,
                        granted_incoming=granted_incoming,
                        granted_target=granted_target,
                    )
                )
                replacement.start_initial_analysis()
                session = _assess_and_save(
                    store=store,
                    session=replacement,
                    provider_factory=connect_codex_chatgpt_provider,
                    expected_session_digest=prior_digest,
                )
            else:
                comparison = _ensure_symmetric_comparison(
                    store=store,
                    left_access=restart_left_access,
                    right_access=restart_right_access,
                    left=left_ctx,
                    right=right_ctx,
                    target_name=target.name,
                    current_name=current_name,
                    include_descendants=(
                        left_descendants,
                        right_descendants,
                    ),
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
        sources_match = sources_match and tuple(
            bool(frame.include_descendants) for frame in session.frames
        ) == (left_descendants, right_descendants)
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
