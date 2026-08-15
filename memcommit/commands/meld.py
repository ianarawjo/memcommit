"""Create, ground, resume, and explicitly apply bounded Context melds."""

from __future__ import annotations

import shlex
import sys
from typing import Annotated, Optional

import typer

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
from memcommit.context import Context
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
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MELD_SCHEMA_VERSION,
    MeldError,
    MeldFrame,
    MeldIssue,
    MeldSession,
    meld_accounting,
    meld_canonical_digest,
)
from memcommit.meld_provider import (
    MeldProviderError,
)
from memcommit.meld_start_application import MeldStartRequest
from memcommit.meld_restart_application import MeldRestartRequest
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
)
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
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
    from memcommit.meld_runtime import (
        execute_meld_assessment,
        prepare_meld_assessment,
    )

    frozen, assessment_port = prepare_meld_assessment(
        session,
        store=store,
        expected_session_digest=expected_session_digest,
    )

    def connected_provider():
        return _connect_meld_provider(provider_factory)

    if frozen.cached_completion is not None:
        return execute_meld_assessment(
            frozen,
            port=assessment_port,
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

        return execute_meld_assessment(
            frozen,
            port=assessment_port,
            provider_factory=connected_provider,
            observer=observe,
        ).session

    return run_command_wait(
        "MELD",
        "connecting provider",
        total=2,
        work=assess,
        return_view=_meld_wait_view(session),
        context_view=_meld_wait_context_view(session),
    )


def _accept(
    *,
    store: MemoryStore,
    session: MeldSession,
    expected_session_digest: str,
) -> tuple[bool, str, int]:
    """Hand one explicitly accepted Meld to its existing Apply dispatcher."""

    from memcommit.application_flow import run_application_flow
    from memcommit.meld_application import MeldApplyRequest
    from memcommit.meld_application_flow import MeldApplicationFlowPort
    from memcommit.meld_runtime import execute_meld_apply

    def apply_reviewed(reviewed: MeldSession, expected: str) -> tuple[bool, str, int]:
        receipt = execute_meld_apply(
            MeldApplyRequest(
                session=reviewed,
                expected_session_digest=expected,
            ),
            store=store,
        ).receipt
        return receipt.recovered, receipt.checkpoint_uid, receipt.result_count

    flow = run_application_flow(
        session,
        port=MeldApplicationFlowPort(
            expected_session_digest=expected_session_digest,
            applier=apply_reviewed,
        ),
    )
    if flow.applied is None:  # Final acceptance cannot cancel inside the port.
        raise MeldCommandError("Accepted Meld Apply was cancelled internally.")
    return flow.applied


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
    from memcommit.meld_runtime import (
        execute_meld_destination_change,
        execute_meld_preservation,
        execute_meld_session_defer,
    )
    from memcommit.meld_session_application import (
        MeldDestinationRequest,
        MeldSessionSnapshot,
        MeldTurnRequest,
        prepare_meld_preservation_turn,
        prepare_meld_turn,
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
        snapshot = MeldSessionSnapshot(session=session, version_token=expected)
        if action.kind == "CHANGE_DESTINATION":
            if destination is None or action.destination is None:
                raise MeldCommandError(
                    "This Meld cannot change its save location."
                )
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
            session = prepare_meld_turn(
                MeldTurnRequest(
                    snapshot=snapshot,
                    comment=action.comment,
                    scope="ALL",
                )
            ).session
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
            session = prepare_meld_turn(
                MeldTurnRequest(
                    snapshot=snapshot,
                    comment="\n\n".join(parts),
                    scope="ISSUE",
                    issue_uids=(issue.uid,),
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
    from memcommit.meld_runtime import execute_meld_start

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
            comparison: ComparisonAnalysis | None = None
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
            from memcommit.meld_runtime import execute_meld_start

            request = MeldStartRequest(
                mode=requested_mode,
                left_name=left_name,
                right_name=right_name,
                target_name=target_name,
                left_descendants=left_descendants,
                right_descendants=right_descendants,
                create_target=create_target,
                comparison=comparison,
            )
            if requested_mode == "DIRECTIONAL" and prewarm is None:
                provisional = session

                def start_meld(progress):
                    def connected_provider():
                        provider = _connect_meld_provider(
                            connect_codex_chatgpt_provider
                        )
                        progress.update("analyzing meld turn", step=2)
                        return provider

                    return execute_meld_start(
                        request,
                        store=store,
                        provider_factory=connected_provider,
                    )

                started = run_command_wait(
                    "MELD",
                    "connecting provider",
                    total=2,
                    work=start_meld,
                    return_view=_meld_wait_view(provisional),
                    context_view=_meld_wait_context_view(provisional),
                )
            else:
                started = execute_meld_start(
                    request,
                    store=store,
                    provider_factory=lambda: (_ for _ in ()).throw(
                        AssertionError("A prepared Meld start connected a provider.")
                    ),
                )
            session = started.session
            if requested_mode == "DIRECTIONAL":
                directional_prewarm_origin = (
                    started.origin if started.origin != "PROVIDER" else None
                )
                meld_analysis_origin = directional_prewarm_origin
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
            # Restart is defined by the newly supplied ordered pair, not by
            # the old session's frames. The CLI loads a provisional frame only
            # for prerequisite and wait-surface decisions; runtime owns the
            # authoritative revalidation and exact-version replacement.
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
            left_ctx = _load_meld_source(
                restart_left_access,
                include_descendants=left_descendants,
                project=requested_mode == "SYMMETRIC",
            )
            right_ctx = _load_meld_source(
                restart_right_access,
                include_descendants=right_descendants,
                project=requested_mode == "SYMMETRIC",
            )
            comparison = None
            prewarm = None
            if requested_mode == "DIRECTIONAL":
                granted_incoming = (
                    freeze_granted_context_binding(restart_left_access)
                    if restart_left_access.is_granted
                    else None
                )
                granted_target = (
                    freeze_granted_context_binding(restart_right_access)
                    if restart_right_access.is_granted
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
                from memcommit.study_prewarm.meld_directional import (
                    find_installed_directional_meld_prewarm,
                )

                prewarm = find_installed_directional_meld_prewarm(
                    store=store,
                    current=replacement,
                    registry_snapshot=load_profile_registry(),
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
            from memcommit.meld_runtime import execute_meld_restart

            restart_request = MeldRestartRequest(
                mode=requested_mode,
                left_name=left_name,
                right_name=right_name,
                target_name=target_name,
                expected_version=prior_digest,
                left_descendants=left_descendants,
                right_descendants=right_descendants,
                comparison=comparison,
            )
            if requested_mode == "DIRECTIONAL" and prewarm is None:

                def restart_meld(progress):
                    def connected_provider():
                        provider = _connect_meld_provider(
                            connect_codex_chatgpt_provider
                        )
                        progress.update("analyzing meld turn", step=2)
                        return provider

                    return execute_meld_restart(
                        restart_request,
                        store=store,
                        provider_factory=connected_provider,
                    )

                restarted = run_command_wait(
                    "MELD",
                    "connecting provider",
                    total=2,
                    work=restart_meld,
                    return_view=_meld_wait_view(replacement),
                    context_view=_meld_wait_context_view(replacement),
                )
            else:
                restarted = execute_meld_restart(
                    restart_request,
                    store=store,
                    provider_factory=lambda: (_ for _ in ()).throw(
                        AssertionError("A prepared Meld restart connected a provider.")
                    ),
                )
            session = restarted.session
            if sys.stdin.isatty() and sys.stdout.isatty():
                session = _run_interactive(
                    store=store,
                    session=session,
                    provider_factory=connect_codex_chatgpt_provider,
                    analysis_origin=(
                        restarted.origin if restarted.origin != "PROVIDER" else None
                    ),
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
        from memcommit.meld_runtime import (
            execute_meld_preservation,
            execute_meld_session_defer,
        )
        from memcommit.meld_session_application import (
            MeldSessionSnapshot,
            MeldTurnRequest,
            prepare_meld_preservation_turn,
            prepare_meld_turn,
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
            session = execute_meld_session_defer(
                session_snapshot,
                store=store,
            ).session
            typer.echo(render_meld_session(session))
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
            session = prepare_meld_turn(
                MeldTurnRequest(
                    snapshot=session_snapshot,
                    comment=turn_comment,
                    scope=("ISSUE" if selected_issue is not None else "ALL"),
                    issue_uids=(
                        (selected_issue.uid,) if selected_issue is not None else ()
                    ),
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
