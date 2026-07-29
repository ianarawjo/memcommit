"""Create, bind, and revise a named common-grounding workbench."""
from __future__ import annotations

from typing import Annotated, Iterable, Optional

import typer

from memcommit.commands.review_shell import safe_terminal_text
from memcommit.context import Context, Memory
from memcommit.ground import (
    DEFAULT_COMPLETION_CRITERION,
    GROUND_SCHEMA_VERSION,
    GroundError,
    GroundSession,
    GroundTargetSpec,
    accepted_ground_case_count,
    bind_ground_workbench,
    create_ground_session,
    propose_ground_case,
    propose_ground_round,
    propose_ground_rule,
    review_ground_item,
    revise_ground_goal,
    revise_ground_requirement,
    select_ground_candidate,
    stale_ground_frames,
    target_requirement_status,
)
from memcommit.store import MemoryStore


def _count_items(session: GroundSession, kind: str) -> int:
    return sum(item.kind == kind for item in session.items)


def _frame_contexts_by_uid(
    contexts: Iterable[Context],
) -> dict[str, Context]:
    return {context.uid: context for context in contexts}


def _accepted_case_count(session: GroundSession, target_uid: str) -> int:
    return accepted_ground_case_count(session, target_uid)


def _render_unbound_snapshot(session: GroundSession) -> str:
    open_issues = sum(
        item.kind == "ISSUE" and item.status != "RESOLVED"
        for item in session.items
    )
    goal = session.goal or "(not yet stated)"
    scope = ", ".join(session.scope) if session.scope else "(unbound)"
    lines = [
        (
            f"GROUND · {safe_terminal_text(session.contract_name)} · "
            f"{session.status}"
        ),
        f"Revision: {session.revision}",
        "",
        "GOAL",
        f"  {safe_terminal_text(goal)}",
        "",
        "COMPLETION",
        f"  {safe_terminal_text(session.completion_criterion)}",
        "",
        f"SCOPE  {safe_terminal_text(scope)}",
        (
            f"RULES {_count_items(session, 'RULE')} · "
            f"CASES {_count_items(session, 'CASE')} · "
            f"UNRESOLVED {open_issues} · "
            f"DECISIONS {_count_items(session, 'DECISION')}"
        ),
        "",
        "No grounding material has been recorded.",
        "The session is ready to bind a Task description and Context frames.",
    ]
    return "\n".join(lines)


def _render_contract_layers(
    session: GroundSession,
    frame_name_by_uid: dict[str, str],
) -> list[str]:
    rules = [item for item in session.items if item.kind == "RULE"]
    cases = [item for item in session.items if item.kind == "CASE"]
    decisions = [item for item in session.items if item.kind == "DECISION"]
    lines = ["2 · WORKING RULES · DISTILLED / INDUCED"]
    if not rules:
        lines.append("  (none yet; distill from the Goal or induct from cases)")
    for item in rules:
        lines.append(
            f"  [{item.status} · {item.rule_provenance}] "
            f"[{item.uid[:8]}] "
            f"{safe_terminal_text(item.content)}"
        )
        if item.rationale:
            lines.append(
                f"    why: {safe_terminal_text(item.rationale)}"
            )
    lines.extend(["", "3 · CASES · FIT / BOUNDARY / CONTRAST"])
    if not cases:
        lines.append("  (none yet; proposed cases do not count as golden)")
    for item in cases:
        targets = ", ".join(
            frame_name_by_uid.get(uid, uid[:8])
            for uid in item.target_context_uids
        )
        related_rules = ", ".join(
            f"[{uid[:8]}]"
            for uid in item.related_uids
            if any(rule.uid == uid for rule in rules)
        )
        source = item.source_refs[0]
        lines.extend(
            [
                (
                    f"  [{item.status} · {item.case_role} · "
                    f"{item.disposition}] "
                    f"[{item.uid[:8]}] "
                    f"{safe_terminal_text(item.content)}"
                ),
                f"    working rule: {related_rules or '(none)'}",
                (
                    f"    source: [{source.memory_uid[:8]}] in "
                    f"{safe_terminal_text(frame_name_by_uid.get(source.context_uid, source.context_uid[:8]))} "
                    f"· sha256:{source.content_digest[:12]}"
                ),
                f"    target: {safe_terminal_text(targets)}",
                (
                    f"    expected: {safe_terminal_text(item.expected)}"
                    if item.expected
                    else "    expected: (none)"
                ),
                f"    why: {safe_terminal_text(item.rationale)}",
            ]
        )
    if decisions:
        lines.extend(
            [
                "",
                f"REVISION LOG · {len(decisions)} decisions",
            ]
        )
        for item in decisions[-5:]:
            lines.append(
                f"  [{item.iteration}] {safe_terminal_text(item.content)} "
                f"— {safe_terminal_text(item.rationale)}"
            )
    return lines


def render_ground_snapshot(
    session: GroundSession,
    contexts: Iterable[Context] | None = None,
) -> str:
    """Render a stable, control-character-safe grounding frame."""
    if session.schema_version != GROUND_SCHEMA_VERSION:
        lines = _render_unbound_snapshot(session).splitlines()
        lines.extend(["", "METHOD READINGS"])
        for reference in session.references:
            lines.extend(
                [
                    (
                        f"  [{reference.reading_status} · agent-suggested] "
                        f"{safe_terminal_text(reference.title)}"
                    ),
                    f"    {safe_terminal_text(reference.url)}",
                ]
            )
        lines.extend(
            [
                "",
                "No Context or Memory changes have been applied.",
                "No checkpoint has been created.",
            ]
        )
        return "\n".join(lines)

    contexts_loaded = contexts is not None
    current_contexts = tuple(contexts or ())
    current_by_uid = _frame_contexts_by_uid(current_contexts)
    stale_names = (
        set(stale_ground_frames(session, current_contexts))
        if contexts_loaded
        else set()
    )
    frame_by_uid = {frame.context_uid: frame for frame in session.frames}
    frame_name_by_uid = {
        frame.context_uid: frame.context_name for frame in session.frames
    }
    raw = next(
        frame for frame in session.frames if frame.role == "RAW_EVIDENCE"
    )
    derived = next(
        frame
        for frame in session.frames
        if frame.role == "WORKING_CANDIDATES"
    )
    target_frames = [
        frame
        for frame in session.frames
        if frame.role in {"PUBLICATION_TARGET", "PLACEMENT_TARGET"}
    ]
    freshness = (
        "FRESH"
        if contexts_loaded and not stale_names
        else ("STALE" if contexts_loaded else "BOUND")
    )
    lines = [
        (
            f"GROUND · {safe_terminal_text(session.contract_name)} · "
            f"{session.status} · {freshness}"
        ),
        f"Revision: {session.revision}",
        "",
        "SOURCE BRIEF · FIXED INPUT",
        f"  {safe_terminal_text(session.brief.content)}",
        "",
        "1 · GOAL · EDITABLE CONTRACT",
        f"  {safe_terminal_text(session.goal or '(not yet stated)')}",
        (
            "  completion: "
            f"{safe_terminal_text(session.completion_criterion)}"
        ),
        "",
        "  GOAL SUCCESS CRITERIA · TARGETS",
        (
            "    The Goal and criteria may be revised when cases expose "
            "a bad boundary."
        ),
    ]
    for requirement in session.requirements:
        frame = frame_by_uid[requirement.target_context_uid]
        status = target_requirement_status(session, requirement)
        accepted = _accepted_case_count(session, frame.context_uid)
        lines.append(
            f"    [{status:<7}] {safe_terminal_text(frame.context_name)} "
            f"· {frame.direct_memory_count} direct Memories "
            f"· {accepted}/{requirement.minimum_accepted_cases} accepted "
            f"[{requirement.uid[:8]}]"
        )
        lines.append(
            f"               {safe_terminal_text(requirement.description)}"
        )
        if requirement.blocked_reason:
            lines.append(
                "               BLOCKED: "
                + safe_terminal_text(requirement.blocked_reason)
            )

    lines.extend(["", *_render_contract_layers(session, frame_name_by_uid)])
    lines.extend(
        [
            "",
            "WORKBENCH",
            (
                f"  {raw.direct_memory_count} RAW → "
                f"{derived.direct_memory_count} CANDIDATES → "
                f"{len(target_frames)} TARGETS"
            ),
        ]
    )
    display_role = {
        "RAW_EVIDENCE": "RAW",
        "WORKING_CANDIDATES": "DERIVED",
    }
    for frame in (raw, derived):
        marker = (
            "STALE"
            if frame.context_name in stale_names
            else ("FRESH" if contexts_loaded else "BOUND")
        )
        lines.append(
            f"  [{marker}] {display_role[frame.role]:<7} "
            f"{safe_terminal_text(frame.context_name)} "
            f"· {frame.direct_memory_count} Memories"
        )
    lines.append(
        "  TARGETS "
        f"{len(target_frames)} · DIRECT MEMORIES "
        f"{sum(frame.direct_memory_count for frame in target_frames)}"
    )

    candidate_context = current_by_uid.get(derived.context_uid)
    candidate_memories = (
        [
            item
            for item in candidate_context.iter_items()
            if isinstance(item, Memory)
        ]
        if candidate_context is not None
        else []
    )
    lines.extend(["", "SELECTED CANDIDATE"])
    if derived.direct_memory_count == 0:
        lines.append("  (none; 0/0)")
    elif candidate_memories and session.cursor_position < len(candidate_memories):
        memory = candidate_memories[session.cursor_position]
        lines.extend(
            [
                (
                    f"  {session.cursor_position + 1}/"
                    f"{len(candidate_memories)} [{memory.uid[:8]}]"
                ),
                f"  {safe_terminal_text(memory.content)}",
            ]
        )
    else:
        lines.append(
            f"  {session.cursor_position + 1}/"
            f"{derived.direct_memory_count} (content not loaded)"
        )

    if stale_names:
        lines.extend(
            [
                "",
                "STALE FRAMES",
                *[
                    f"  {safe_terminal_text(name)}"
                    for name in sorted(stale_names)
                ],
                "  Contract changes and case decisions are blocked.",
            ]
        )

    lines.extend(["", "METHOD READINGS"])
    for reference in session.references:
        lines.append(
            f"  [{reference.reading_status} · agent-suggested] "
            f"{safe_terminal_text(reference.title)}"
        )
    lines.extend(
        [
            "",
            "Grounding changed only this named contract.",
            "No Context or Memory changes have been applied.",
            "No checkpoint has been created.",
        ]
    )
    return "\n".join(lines)


def _load_bound_contexts(
    store: MemoryStore,
    session: GroundSession,
    *,
    tolerate_missing: bool = False,
) -> tuple[Context, ...]:
    contexts: list[Context] = []
    for frame in session.frames:
        try:
            contexts.append(store.load(frame.context_name))
        except FileNotFoundError:
            if not tolerate_missing:
                raise
    return tuple(contexts)


def _parse_blocked_targets(
    values: list[str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, reason = value.partition("=")
        if not separator or not name.strip() or not reason.strip():
            raise GroundError(
                "--blocked-target must use CONTEXT=REASON."
            )
        if name in result:
            raise GroundError("A blocked target was supplied more than once.")
        result[name] = reason
    return result


def cmd(
    contract_name: Annotated[
        str,
        typer.Argument(
            help=(
                "Portable name of the grounding contract to create or resume"
            )
        ),
    ],
    goal: Annotated[
        Optional[str],
        typer.Option("--goal", help="Goal for a new grounding contract"),
    ] = None,
    completion: Annotated[
        Optional[str],
        typer.Option(
            "--completion",
            help="Explicit completion criterion for a new contract",
        ),
    ] = None,
    scope: Annotated[
        Optional[list[str]],
        typer.Option(
            "--scope",
            help="Descriptive scope label for a new contract; repeatable",
        ),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option(
            "--description",
            help="Task description copied into an explicit frame binding",
        ),
    ] = None,
    raw_context: Annotated[
        Optional[str],
        typer.Option(
            "--raw-context",
            help="Raw-evidence Context for an explicit frame binding",
        ),
    ] = None,
    derived_context: Annotated[
        Optional[str],
        typer.Option(
            "--derived-context",
            help="Working-candidate Context for an explicit frame binding",
        ),
    ] = None,
    publication_target: Annotated[
        Optional[str],
        typer.Option(
            "--publication-target",
            help="Publication target Context for an explicit binding",
        ),
    ] = None,
    placement_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--placement-target",
            help="Placement target Context; repeat for every required slot",
        ),
    ] = None,
    blocked_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--blocked-target",
            metavar="CONTEXT=REASON",
            help="Record one known target-fixture gap; repeatable",
        ),
    ] = None,
    select: Annotated[
        Optional[int],
        typer.Option(
            "--select",
            min=1,
            help="Select one 1-based working-candidate position",
        ),
    ] = None,
    propose_source: Annotated[
        Optional[str],
        typer.Option(
            "--propose-source",
            help="Working-candidate Memory uid or unambiguous prefix",
        ),
    ] = None,
    propose_rule: Annotated[
        Optional[str],
        typer.Option(
            "--propose-rule",
            help="New Working Rule; may be proposed before any case",
        ),
    ] = None,
    fit_rule: Annotated[
        Optional[str],
        typer.Option(
            "--fit-rule",
            help="Existing Working Rule uid/prefix for a new case",
        ),
    ] = None,
    propose_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--propose-target",
            help="Target Context for this case; repeatable",
        ),
    ] = None,
    expected: Annotated[
        Optional[str],
        typer.Option(
            "--expected",
            help="Expected target wording or result for a proposed case",
        ),
    ] = None,
    rationale: Annotated[
        Optional[str],
        typer.Option("--rationale", help="Reason for the proposed judgment"),
    ] = None,
    case_role: Annotated[
        Optional[str],
        typer.Option(
            "--case-role",
            help="FIT, BOUNDARY, or CONTRAST",
        ),
    ] = None,
    disposition: Annotated[
        Optional[str],
        typer.Option(
            "--disposition",
            help="INCLUDE, EXCLUDE, or UNRESOLVED",
        ),
    ] = None,
    rule_provenance: Annotated[
        Optional[str],
        typer.Option(
            "--rule-provenance",
            help=(
                "USER_STATED, DISTILLED_FROM_GOAL, "
                "or INDUCED_FROM_CASES; review creates JOINTLY_REVISED"
            ),
        ),
    ] = None,
    decide: Annotated[
        Optional[str],
        typer.Option(
            "--decide",
            help="Proposed rule/case uid or prefix to review",
        ),
    ] = None,
    action: Annotated[
        Optional[str],
        typer.Option(
            "--action",
            help="ACCEPT, REFINE, DEFER, or REJECT",
        ),
    ] = None,
    response: Annotated[
        Optional[str],
        typer.Option(
            "--response",
            help="Review note, or replacement text for REFINE",
        ),
    ] = None,
    revise_target: Annotated[
        Optional[str],
        typer.Option(
            "--revise-target",
            help="Target name or requirement uid/prefix to revise",
        ),
    ] = None,
    revise_goal: Annotated[
        Optional[str],
        typer.Option(
            "--revise-goal",
            help="Replacement top-level working Goal",
        ),
    ] = None,
    requirement_text: Annotated[
        Optional[str],
        typer.Option(
            "--requirement-text",
            help="Replacement target requirement",
        ),
    ] = None,
    minimum_cases: Annotated[
        Optional[int],
        typer.Option(
            "--minimum-cases",
            min=1,
            help="Replacement accepted-case minimum",
        ),
    ] = None,
    blocked_reason: Annotated[
        Optional[str],
        typer.Option(
            "--blocked-reason",
            help="Replacement gap; pass an empty string to clear it",
        ),
    ] = None,
    change_reason: Annotated[
        Optional[str],
        typer.Option(
            "--change-reason",
            help="Why the upper target contract should change",
        ),
    ] = None,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the complete stable session frame",
        ),
    ] = False,
    replace_ground: Annotated[
        bool,
        typer.Option(
            "--replace-ground",
            help="Explicitly replace an existing or malformed named session",
        ),
    ] = False,
) -> None:
    """Persist grounding judgments without applying them to Contexts."""
    store = MemoryStore(create=False)
    bind_requested = any(
        value is not None
        for value in (
            description,
            raw_context,
            derived_context,
            publication_target,
            placement_target,
            blocked_target,
        )
    )
    proposal_requested = any(
        value is not None
        for value in (
            propose_source,
            propose_rule,
            fit_rule,
            propose_target,
            expected,
            rationale,
            case_role,
            disposition,
            rule_provenance,
        )
    )
    decision_requested = any(
        value is not None for value in (decide, action, response)
    )
    requirement_requested = any(
        value is not None
        for value in (
            revise_target,
            revise_goal,
            requirement_text,
            minimum_cases,
            blocked_reason,
            change_reason,
        )
    )
    action_count = sum(
        (
            bind_requested,
            select is not None,
            proposal_requested,
            decision_requested,
            requirement_requested,
        )
    )
    try:
        if action_count > 1:
            raise GroundError(
                "Bind, select, propose, decide, and revise-target are "
                "separate grounding actions."
            )
        session = (
            None
            if replace_ground
            else store.load_ground_session(contract_name)
        )
        created = session is None
        if session is not None and any(
            value is not None for value in (goal, completion, scope)
        ):
            raise GroundError(
                "The grounding session already exists. Start it without "
                "creation options, or use --replace-ground explicitly."
            )
        if session is None:
            session = create_ground_session(
                contract_name,
                goal=goal or "",
                completion_criterion=(
                    completion
                    if completion is not None
                    else DEFAULT_COMPLETION_CRITERION
                ),
                scope=tuple(scope or ()),
            )

        action_label = "created" if created else "resumed"
        if bind_requested:
            if (
                description is None
                or raw_context is None
                or derived_context is None
                or publication_target is None
            ):
                raise GroundError(
                    "Binding requires --description, --raw-context, "
                    "--derived-context, and --publication-target."
                )
            blocked = _parse_blocked_targets(blocked_target or [])
            target_names = (
                publication_target,
                *(placement_target or ()),
            )
            if len(set(target_names)) != len(target_names):
                raise GroundError("A target Context was supplied more than once.")
            unknown_blocked = set(blocked) - set(target_names)
            if unknown_blocked:
                raise GroundError(
                    "Blocked targets must also be bound targets: "
                    + ", ".join(sorted(unknown_blocked))
                )
            raw = store.load(raw_context)
            derived = store.load(derived_context)
            targets = tuple(store.load(name) for name in target_names)
            specs = (
                GroundTargetSpec(
                    context_name=publication_target,
                    role="PUBLICATION_TARGET",
                    description=(
                        "Maintain the organizational baseline and publish "
                        "every supported campus-facing change."
                    ),
                    blocked_reason=blocked.get(publication_target, ""),
                ),
                *(
                    GroundTargetSpec(
                        context_name=name,
                        role="PLACEMENT_TARGET",
                        description=(
                            "Establish at least one approved, traceable "
                            "placement case for this local category."
                        ),
                        blocked_reason=blocked.get(name, ""),
                    )
                    for name in (placement_target or ())
                ),
            )
            session = bind_ground_workbench(
                session,
                description=description,
                raw_context=raw,
                derived_context=derived,
                target_contexts=targets,
                target_requirements=specs,
            )
            store.save_ground_session(
                session,
                replace=replace_ground,
            )
            action_label = "bound"
        elif select is not None:
            contexts = _load_bound_contexts(store, session)
            session = select_ground_candidate(
                session,
                select - 1,
                current_contexts=contexts,
            )
            store.save_ground_session(session)
            action_label = "selected"
        elif proposal_requested:
            contexts = _load_bound_contexts(store, session)
            if session.schema_version != GROUND_SCHEMA_VERSION:
                raise GroundError(
                    "Bind the grounding session before proposing rules or "
                    "cases."
                )
            if stale_ground_frames(session, contexts):
                raise GroundError(
                    "Grounding workbench is stale. Create a new named "
                    "contract, or use --replace-ground and bind fresh frames."
                )
            if propose_rule is not None and fit_rule is not None:
                raise GroundError(
                    "Propose a new rule or fit a case to an existing rule, "
                    "not both."
                )
            case_requested = any(
                value is not None
                for value in (
                    propose_source,
                    fit_rule,
                    propose_target,
                    expected,
                    case_role,
                    disposition,
                )
            )
            if propose_rule is not None and not case_requested:
                if rationale is None:
                    raise GroundError(
                        "A rule proposal requires --rationale."
                    )
                session = propose_ground_rule(
                    session,
                    rule=propose_rule,
                    rationale=rationale,
                    current_contexts=contexts,
                    rule_provenance=(
                        rule_provenance or "DISTILLED_FROM_GOAL"
                    ).upper(),
                )
            else:
                case_disposition = (disposition or "INCLUDE").upper()
                if (
                    propose_source is None
                    or not propose_target
                    or rationale is None
                    or (
                        case_disposition == "INCLUDE"
                        and expected is None
                    )
                ):
                    raise GroundError(
                        "A case proposal requires --propose-source, "
                        "--propose-target, --rationale, and --expected for "
                        "INCLUDE."
                    )
                candidate_frame = next(
                    frame
                    for frame in session.frames
                    if frame.role == "WORKING_CANDIDATES"
                )
                candidate_context = next(
                    context
                    for context in contexts
                    if context.uid == candidate_frame.context_uid
                )
                if not propose_source.strip():
                    raise GroundError(
                        "The proposed source selector cannot be blank."
                    )
                matches = [
                    item
                    for item in candidate_context.iter_items()
                    if isinstance(item, Memory)
                    and item.uid.startswith(propose_source)
                ]
                if len(matches) != 1:
                    raise GroundError(
                        "The proposed source is missing or ambiguous."
                    )
                if fit_rule is not None:
                    if rule_provenance is not None:
                        raise GroundError(
                            "--rule-provenance applies only to a new rule."
                        )
                    session = propose_ground_case(
                        session,
                        rule_selector=fit_rule,
                        case=matches[0].content,
                        source_context_uid=candidate_context.uid,
                        source_memory_uid=matches[0].uid,
                        target_context_names=tuple(propose_target),
                        expected=expected or "",
                        rationale=rationale,
                        current_contexts=contexts,
                        case_role=(case_role or "FIT").upper(),
                        disposition=case_disposition,
                    )
                elif propose_rule is not None:
                    session = propose_ground_round(
                        session,
                        rule=propose_rule,
                        case=matches[0].content,
                        source_context_uid=candidate_context.uid,
                        source_memory_uid=matches[0].uid,
                        target_context_names=tuple(propose_target),
                        expected=expected or "",
                        rationale=rationale,
                        current_contexts=contexts,
                        case_role=(case_role or "FIT").upper(),
                        disposition=case_disposition,
                        rule_provenance=(
                            rule_provenance or "INDUCED_FROM_CASES"
                        ).upper(),
                    )
                else:
                    raise GroundError(
                        "A case proposal requires --fit-rule, or "
                        "--propose-rule to create and link a new rule."
                    )
            store.save_ground_session(session)
            action_label = "proposed"
        elif decision_requested:
            if decide is None or action is None:
                raise GroundError(
                    "A decision requires both --decide and --action."
                )
            contexts = _load_bound_contexts(store, session)
            session = review_ground_item(
                session,
                decide,
                action=action,
                response=response or "",
                current_contexts=contexts,
            )
            store.save_ground_session(session)
            action_label = action.casefold()
        elif requirement_requested:
            if change_reason is None:
                raise GroundError(
                    "A Goal or target revision requires --change-reason."
                )
            contexts = _load_bound_contexts(store, session)
            if revise_goal is not None:
                if (
                    revise_target is not None
                    or requirement_text is not None
                    or minimum_cases is not None
                    or blocked_reason is not None
                ):
                    raise GroundError(
                        "Revise either the Goal or one target requirement."
                    )
                session = revise_ground_goal(
                    session,
                    revise_goal,
                    reason=change_reason,
                    current_contexts=contexts,
                )
            else:
                if revise_target is None:
                    raise GroundError(
                        "A target revision requires --revise-target."
                    )
                session = revise_ground_requirement(
                    session,
                    revise_target,
                    description=requirement_text,
                    minimum_accepted_cases=minimum_cases,
                    blocked_reason=blocked_reason,
                    reason=change_reason,
                    current_contexts=contexts,
                )
            store.save_ground_session(session)
            action_label = "revised contract"
        elif created:
            store.save_ground_session(
                session,
                replace=replace_ground,
            )
    except (
        FileNotFoundError,
        GroundError,
        OSError,
        StopIteration,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            f"Ground error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if snapshot:
        try:
            contexts = (
                _load_bound_contexts(
                    store,
                    session,
                    tolerate_missing=True,
                )
                if session.schema_version == GROUND_SCHEMA_VERSION
                else None
            )
        except (FileNotFoundError, GroundError, OSError, TypeError, ValueError) as error:
            typer.secho(
                f"Ground error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(render_ground_snapshot(session, contexts))
        return

    typer.secho(
        f"Grounding session '{session.contract_name}' {action_label}.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(
        f"Revision {session.revision}: "
        f"{_count_items(session, 'RULE')} rules, "
        f"{_count_items(session, 'CASE')} cases, "
        f"{_count_items(session, 'DECISION')} decisions."
    )
    typer.echo(
        f"Inspect it with 'mem ground {session.contract_name} --snapshot'."
    )
    typer.echo("No Context or Memory changes applied. No checkpoint created.")
