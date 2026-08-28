"""Execute CLI actions against persisted JSON Ground sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from memcommit.application.operations.ground.model import (
    GroundError,
    GroundSession,
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
    is_bound_ground_schema,
    propose_ground_case,
    propose_ground_example,
    propose_ground_round,
    propose_ground_rule,
    resolve_ground_requirement,
    review_ground_item,
    revise_ground_goal,
    revise_ground_requirement,
    select_ground_candidate,
    set_ground_example_use,
    stale_ground_frames,
    upgrade_ground_to_propositions,
)
from memcommit.core.context import Memory
from memcommit.persistence.store import (
    ConcurrentGroundUpdateError,
    MemoryStore,
    ground_session_record_digest,
)

from .. import open as open_workflow
from . import dialogue as session_dialogue
from . import inspect as session_inspect
from . import review as session_review

if TYPE_CHECKING:
    from ..command import GroundCommandRequest


@dataclass(frozen=True)
class SessionActionSelection:
    """Classify the mutually exclusive actions owned by GroundSession."""

    bind_requested: bool
    proposal_requested: bool
    decision_requested: bool
    requirement_requested: bool
    example_use_requested: bool
    select_requested: bool
    upgrade_requested: bool

    @classmethod
    def from_request(
        cls,
        request: GroundCommandRequest,
    ) -> SessionActionSelection:
        return cls(
            bind_requested=any(
                value is not None
                for value in (
                    request.description,
                    request.raw_context,
                    request.derived_context,
                    request.publication_target,
                    request.placement_target,
                    request.blocked_target,
                )
            ),
            proposal_requested=any(
                value is not None
                for value in (
                    request.propose_source,
                    request.propose_example,
                    request.example_rule,
                    request.example_source,
                    request.example_target,
                    request.example_input,
                    request.example_expected,
                    request.propose_rule,
                    request.propose_rule_target,
                    request.fit_rule,
                    request.propose_target,
                    request.expected,
                    request.rationale,
                    request.case_role,
                    request.disposition,
                    request.rule_provenance,
                )
            ),
            decision_requested=any(
                value is not None
                for value in (request.decide, request.action, request.response)
            ),
            requirement_requested=any(
                value is not None
                for value in (
                    request.revise_target,
                    request.revise_goal,
                    request.requirement_text,
                    request.minimum_cases,
                    request.blocked_reason,
                    request.change_reason,
                )
            ),
            example_use_requested=any(
                value is not None for value in (request.set_example_use, request.use)
            ),
            select_requested=request.select is not None,
            upgrade_requested=request.upgrade_propositions,
        )

    @property
    def count(self) -> int:
        return sum(
            (
                self.bind_requested,
                self.select_requested,
                self.proposal_requested,
                self.decision_requested,
                self.requirement_requested,
                self.example_use_requested,
                self.upgrade_requested,
            )
        )


def _parse_blocked_targets(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, reason = value.partition("=")
        if not separator or not name.strip() or not reason.strip():
            raise GroundError("--blocked-target must use CONTEXT=REASON.")
        if name in result:
            raise GroundError("A blocked target was supplied more than once.")
        result[name] = reason
    return result


def run_ground_session_command(
    request: GroundCommandRequest,
    *,
    ground_name: str,
    selection: SessionActionSelection,
    plain_named_tui_requested: bool,
) -> None:
    """Run the persisted GroundSession branch after top-level routing."""
    goal = request.goal
    scope = request.scope
    description = request.description
    raw_context = request.raw_context
    derived_context = request.derived_context
    publication_target = request.publication_target
    placement_target = request.placement_target
    blocked_target = request.blocked_target
    focus_target = request.focus_target
    select = request.select
    propose_source = request.propose_source
    propose_example = request.propose_example
    example_rule = request.example_rule
    example_source = request.example_source
    example_target = request.example_target
    example_input = request.example_input
    example_expected = request.example_expected
    propose_rule = request.propose_rule
    propose_rule_target = request.propose_rule_target
    fit_rule = request.fit_rule
    propose_target = request.propose_target
    expected = request.expected
    rationale = request.rationale
    case_role = request.case_role
    disposition = request.disposition
    set_example_use = request.set_example_use
    use = request.use
    rule_provenance = request.rule_provenance
    decide = request.decide
    action = request.action
    response = request.response
    revise_target = request.revise_target
    revise_goal = request.revise_goal
    requirement_text = request.requirement_text
    minimum_cases = request.minimum_cases
    blocked_reason = request.blocked_reason
    change_reason = request.change_reason
    upgrade_propositions = request.upgrade_propositions
    snapshot = request.snapshot
    replace_ground = request.replace_ground
    if_ground_version = request.if_ground_version
    if_context_version = request.if_context_version

    bind_requested = selection.bind_requested
    proposal_requested = selection.proposal_requested
    decision_requested = selection.decision_requested
    requirement_requested = selection.requirement_requested
    example_use_requested = selection.example_use_requested
    action_count = selection.count

    # Keep the legacy internal name localized; versioned session JSON still
    # uses contract_name, while the CLI presents the user-facing Ground model.
    contract_name = ground_name
    store = MemoryStore(create=False)
    try:
        expected_ground_state = session_review._parse_ground_version_token(
            if_ground_version
        )
        expected_context_versions = tuple(
            session_review._parse_context_version_token(value)
            for value in (if_context_version or ())
        )
        if expected_ground_state is not None and (action_count != 1 or replace_ground):
            raise GroundError(
                "The expected Ground version guard requires exactly one "
                "non-replacement Ground action."
            )
        if expected_context_versions and (
            expected_ground_state is None or not bind_requested
        ):
            raise GroundError(
                "Expected Context version guards require one guarded binding action."
            )

        loaded_session: GroundSession | None = None

        def save_ground(
            value: GroundSession,
            *,
            replace: bool = False,
        ) -> None:
            if expected_ground_state is not None:
                expected_kwargs = {
                    "expected_uid": expected_ground_state[0],
                    "expected_revision": expected_ground_state[1],
                    "expected_digest": expected_ground_state[2],
                }
            elif loaded_session is not None and not replace:
                # Ordinary CLI writers participate in the same CAS boundary
                # as TUI-reviewed commands. Otherwise a stale unguarded
                # writer could overwrite a newer guarded update.
                expected_kwargs = {
                    "expected_uid": loaded_session.uid,
                    "expected_revision": loaded_session.revision,
                    "expected_digest": ground_session_record_digest(loaded_session),
                }
            else:
                expected_kwargs = {}
            store.save_ground_session(
                value,
                replace=replace,
                verify_bound_frames=(is_bound_ground_schema(value.schema_version)),
                **expected_kwargs,
            )

        if snapshot and focus_target is not None:
            raise GroundError("Choose either --snapshot or --focus-target, not both.")
        if focus_target is not None and bind_requested:
            raise GroundError(
                "--focus-target requires an already bound Ground. Bind it "
                "first, then focus it in a read-only command."
            )
        if action_count > 1:
            raise GroundError(
                "Bind, select, propose, decide, change Example USE, and "
                "revise-target are separate grounding actions."
            )
        if focus_target is not None and action_count == 1 and not requirement_requested:
            raise GroundError(
                "--focus-target currently combines only with one Goal or "
                "target-requirement revision."
            )
        session = None if replace_ground else store.load_ground_session(contract_name)
        loaded_session = session
        created = session is None
        if session is not None and any(value is not None for value in (goal, scope)):
            raise GroundError(
                "The grounding session already exists. Start it without "
                "creation options, or use --replace-ground explicitly."
            )
        if session is None:
            session = create_ground_session(
                contract_name,
                goal=goal or "",
                scope=tuple(scope or ()),
            )
        if focus_target is not None:
            if not is_bound_ground_schema(session.schema_version):
                raise GroundError(
                    "--focus-target requires an existing bound Ground or "
                    "an explicit binding in the same command."
                )
            # A view modifier must be valid before an action is saved. This
            # keeps a typo in --focus-target from turning one approved command
            # into a hidden mutation followed by a rendering error.
            focused_requirement, _ = session_inspect._focused_target(
                session,
                focus_target,
            )
            if revise_target is not None:
                revised_requirement = resolve_ground_requirement(
                    session,
                    revise_target,
                )
                if revised_requirement.uid != focused_requirement.uid:
                    raise GroundError(
                        "--focus-target and --revise-target must identify "
                        "the same target so the command displays its own "
                        "effect."
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
                    description="",
                    blocked_reason=blocked.get(publication_target, ""),
                ),
                *(
                    GroundTargetSpec(
                        context_name=name,
                        role="PLACEMENT_TARGET",
                        description="",
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
            if expected_context_versions:
                session_review._assert_expected_binding_frames(
                    session,
                    expected_context_versions,
                )
            save_ground(
                session,
                replace=replace_ground,
            )
            action_label = "bound"
        elif select is not None:
            contexts = session_review._load_bound_contexts(store, session)
            session = select_ground_candidate(
                session,
                select - 1,
                current_contexts=contexts,
            )
            save_ground(session)
            action_label = "selected"
        elif proposal_requested:
            contexts = session_review._load_bound_contexts(store, session)
            if not is_bound_ground_schema(session.schema_version):
                raise GroundError(
                    "Bind the grounding session before proposing Rules or "
                    "Ground Memories."
                )
            if stale_ground_frames(session, contexts):
                raise GroundError(
                    "Grounding workbench is stale. Create a new named "
                    "Ground, or use --replace-ground and bind fresh frames."
                )
            native_example_requested = any(
                value is not None
                for value in (
                    propose_example,
                    example_rule,
                    example_source,
                    example_target,
                    example_input,
                    example_expected,
                )
            )
            legacy_proposal_requested = any(
                value is not None
                for value in (
                    propose_source,
                    propose_rule,
                    propose_rule_target,
                    fit_rule,
                    propose_target,
                    expected,
                    rule_provenance,
                )
            )
            if native_example_requested and legacy_proposal_requested:
                raise GroundError(
                    "Propose one native Example or one legacy Rule/Ground "
                    "Memory per command, not both."
                )
            if native_example_requested:
                if propose_example is None:
                    raise GroundError(
                        "Native Example options require --propose-example."
                    )
                candidate_context_uid: str | None = None
                source_memory_uid: str | None = None
                if example_source is not None:
                    if not example_source.strip():
                        raise GroundError(
                            "The Example source selector cannot be blank."
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
                    matches = [
                        item
                        for item in candidate_context.iter_items()
                        if isinstance(item, Memory)
                        and item.uid.startswith(example_source)
                    ]
                    if len(matches) != 1:
                        raise GroundError("The Example source is missing or ambiguous.")
                    candidate_context_uid = candidate_context.uid
                    source_memory_uid = matches[0].uid
                session = propose_ground_example(
                    session,
                    proposition=propose_example,
                    rationale=rationale or "",
                    current_contexts=contexts,
                    rule_selectors=tuple(example_rule or ()),
                    source_context_uid=candidate_context_uid,
                    source_memory_uid=source_memory_uid,
                    target_context_names=tuple(example_target or ()),
                    input_text=example_input or "",
                    expected_output=example_expected or "",
                    case_role=(case_role or "FIT").upper(),
                    disposition=(disposition or "INCLUDE").upper(),
                )
            elif propose_rule is not None and fit_rule is not None:
                raise GroundError(
                    "Propose a new Rule or fit a Ground Memory to an existing "
                    "Rule, not both."
                )
            else:
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
            if (
                not native_example_requested
                and propose_rule is not None
                and not case_requested
            ):
                effective_provenance = (
                    rule_provenance
                    or ("USER_STATED" if rationale is None else "DISTILLED")
                ).upper()
                if rationale is None and effective_provenance != "USER_STATED":
                    raise GroundError("A derived rule proposal requires --rationale.")
                session = propose_ground_rule(
                    session,
                    rule=propose_rule,
                    rationale=rationale or "",
                    current_contexts=contexts,
                    rule_provenance=effective_provenance,
                    target_context_names=tuple(propose_rule_target or ()),
                )
            elif not native_example_requested:
                case_disposition = (disposition or "INCLUDE").upper()
                if (
                    propose_source is None
                    or not propose_target
                    or rationale is None
                    or (case_disposition == "INCLUDE" and expected is None)
                ):
                    raise GroundError(
                        "A Ground Memory proposal requires --propose-source, "
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
                    raise GroundError("The proposed source selector cannot be blank.")
                matches = [
                    item
                    for item in candidate_context.iter_items()
                    if isinstance(item, Memory) and item.uid.startswith(propose_source)
                ]
                if len(matches) != 1:
                    raise GroundError("The proposed source is missing or ambiguous.")
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
                        rule_provenance=(rule_provenance or "DISTILLED").upper(),
                    )
                else:
                    raise GroundError(
                        "A Ground Memory proposal requires --fit-rule, or "
                        "--propose-rule to create and link a new rule."
                    )
            save_ground(session)
            action_label = "proposed"
        elif decision_requested:
            if decide is None or action is None:
                raise GroundError("A decision requires both --decide and --action.")
            contexts = session_review._load_bound_contexts(store, session)
            session = review_ground_item(
                session,
                decide,
                action=action,
                response=response or "",
                current_contexts=contexts,
            )
            save_ground(session)
            action_label = action.casefold()
        elif example_use_requested:
            if set_example_use is None or use is None:
                raise GroundError(
                    "Changing Example USE requires both --set-example-use and --use."
                )
            contexts = session_review._load_bound_contexts(store, session)
            session = set_ground_example_use(
                session,
                set_example_use,
                use=use,
                current_contexts=contexts,
            )
            save_ground(session)
            action_label = "updated Example USE"
        elif requirement_requested:
            if change_reason is None:
                raise GroundError("A Goal or target revision requires --change-reason.")
            contexts = session_review._load_bound_contexts(store, session)
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
                    raise GroundError("A target revision requires --revise-target.")
                session = revise_ground_requirement(
                    session,
                    revise_target,
                    description=requirement_text,
                    minimum_accepted_cases=minimum_cases,
                    blocked_reason=blocked_reason,
                    reason=change_reason,
                    current_contexts=contexts,
                )
            save_ground(session)
            action_label = "revised Ground"
        elif upgrade_propositions:
            session = upgrade_ground_to_propositions(session)
            save_ground(session)
            action_label = "upgraded to proposition schema"
        elif created:
            save_ground(
                session,
                replace=replace_ground,
            )
    except (
        FileNotFoundError,
        ConcurrentGroundUpdateError,
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

    if plain_named_tui_requested:
        outcome = session_dialogue._run_existing_ground_shell(session)
        if outcome == "BACK_TO_PICKER":
            open_workflow._run_ground_session_picker(store)
        return

    if focus_target is not None:
        try:
            contexts = session_review._load_bound_contexts(
                store,
                session,
                tolerate_missing=True,
            )
            typer.echo(
                session_inspect.render_ground_focus(
                    session,
                    focus_target,
                    contexts,
                )
            )
        except (
            FileNotFoundError,
            GroundError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Ground error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        return

    if snapshot:
        try:
            contexts = (
                session_review._load_bound_contexts(
                    store,
                    session,
                    tolerate_missing=True,
                )
                if is_bound_ground_schema(session.schema_version)
                else None
            )
        except (
            FileNotFoundError,
            GroundError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            typer.secho(
                f"Ground error: {error}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo(session_inspect.render_ground_snapshot(session, contexts))
        return

    typer.secho(
        f"Grounding session '{session.contract_name}' {action_label}.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(
        f"Revision {session.revision}: "
        f"{session_inspect._count_items(session, 'RULE')} rules, "
        f"{session_inspect._count_items(session, 'CASE')} Ground Memories, "
        f"{session_inspect._count_items(session, 'DECISION')} decisions."
    )
    typer.echo(f"Inspect it with 'mem ground {session.contract_name} --snapshot'.")
    typer.echo("No Context or Context Memory changes applied. No checkpoint created.")
