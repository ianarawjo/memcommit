"""Typer surface for the Ground command workflow."""
from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.ground.command.workflow import (
    GroundCommandRequest,
    run_ground_command,
)


def cmd(
    ground_name: Annotated[
        Optional[str],
        typer.Argument(
            metavar="[GROUND_NAME]",
            show_default=False,
            help=(
                "Portable Ground name to create or resume, or a natural-"
                "language starting request when the value cannot be a "
                "portable name; omit to start from a blank, unsaved frame "
                "outside a terminal or enter the provider-backed chat inside "
                "the Ground session"
            )
        ),
    ] = None,
    request: Annotated[
        Optional[str],
        typer.Option(
            "--request",
            help=(
                "Explicit unsaved starting request; useful when its text "
                "also looks like a portable Ground name"
            ),
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Enter the interactive Ground session launcher",
        ),
    ] = False,
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            help=(
                "Initial Goal from a Context, CONTEXT:UID/UID Memory, or "
                "inline text; materialized as one /goals Memory"
            ),
        ),
    ] = None,
    set_goal: Annotated[
        Optional[str],
        typer.Option(
            "--set-goal",
            help=(
                "Add or replace the one /goals Memory from a Context, "
                "CONTEXT:UID/UID Memory, or inline text"
            ),
        ),
    ] = None,
    add_rule: Annotated[
        Optional[str],
        typer.Option(
            "--add-rule",
            help="Add one reviewed Rule Memory to a physical Ground",
        ),
    ] = None,
    add_example: Annotated[
        Optional[str],
        typer.Option(
            "--add-example",
            help="Add one reviewed Example proposition Memory",
        ),
    ] = None,
    add_relation: Annotated[
        Optional[str],
        typer.Option(
            "--add-relation",
            help="Add one reviewed relationship as an ordinary Memory",
        ),
    ] = None,
    undo_local: Annotated[
        bool,
        typer.Option(
            "--undo",
            help="Undo the latest command owned by this Ground workspace",
        ),
    ] = False,
    if_ground_revision: Annotated[
        Optional[int],
        typer.Option(
            "--if-revision",
            min=0,
            help="Require this exact physical Ground revision",
        ),
    ] = None,
    scope: Annotated[
        Optional[list[str]],
        typer.Option(
            "--scope",
            help="Descriptive scope label for a new Ground; repeatable",
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
    focus_target: Annotated[
        Optional[str],
        typer.Option(
            "--focus-target",
            help=(
                "Show one compact target-focused Ground; may accompany one "
                "Goal or target-requirement revision"
            ),
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
    propose_example: Annotated[
        Optional[str],
        typer.Option(
            "--propose-example",
            help=(
                "Concrete proposition to retain as a version-3 Example; "
                "may be recorded before any Rule"
            ),
        ),
    ] = None,
    example_rule: Annotated[
        Optional[list[str]],
        typer.Option(
            "--example-rule",
            help=(
                "Active Rule uid/prefix explicitly covered by this Example; "
                "repeatable, or omit to cover all active Rules at Fit time"
            ),
        ),
    ] = None,
    example_source: Annotated[
        Optional[str],
        typer.Option(
            "--example-source",
            help=(
                "Optional working-candidate Memory uid/prefix retained as "
                "evidence for this Example"
            ),
        ),
    ] = None,
    example_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--example-target",
            help="Optional materialization target Context; repeatable",
        ),
    ] = None,
    example_input: Annotated[
        Optional[str],
        typer.Option(
            "--example-input",
            help="Optional exact-input projection; requires --example-expected",
        ),
    ] = None,
    example_expected: Annotated[
        Optional[str],
        typer.Option(
            "--example-expected",
            help="Optional exact-output projection; requires --example-input",
        ),
    ] = None,
    propose_rule: Annotated[
        Optional[str],
        typer.Option(
            "--propose-rule",
            help="New Rule; may be proposed before any Ground Memory",
        ),
    ] = None,
    propose_rule_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--propose-rule-target",
            help="Placement target Context for this Rule; repeatable",
        ),
    ] = None,
    fit_rule: Annotated[
        Optional[str],
        typer.Option(
            "--fit-rule",
            help="Existing Rule uid/prefix for a new Ground Memory",
        ),
    ] = None,
    propose_target: Annotated[
        Optional[list[str]],
        typer.Option(
            "--propose-target",
            help="Target Context for this Ground Memory; repeatable",
        ),
    ] = None,
    expected: Annotated[
        Optional[str],
        typer.Option(
            "--expected",
            help=(
                "Expected target wording or result for a proposed "
                "Ground Memory"
            ),
        ),
    ] = None,
    rationale: Annotated[
        Optional[str],
        typer.Option(
            "--rationale",
            help=(
                "Reason for the proposed judgment; optional for a directly "
                "user-stated Rule"
            ),
        ),
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
    set_example_use: Annotated[
        Optional[str],
        typer.Option(
            "--set-example-use",
            help="Existing Ground Example uid/prefix whose USE should change",
        ),
    ] = None,
    use: Annotated[
        Optional[str],
        typer.Option(
            "--use",
            help="INCLUDE or EXCLUDE; requires --set-example-use",
        ),
    ] = None,
    rule_provenance: Annotated[
        Optional[str],
        typer.Option(
            "--rule-provenance",
            help=(
                "USER_STATED or DISTILLED; legacy DISTILLED_FROM_GOAL and "
                "INDUCED_FROM_CASES remain readable; review creates "
                "JOINTLY_REVISED"
            ),
        ),
    ] = None,
    decide: Annotated[
        Optional[str],
        typer.Option(
            "--decide",
            help="Proposed Rule/Ground Memory uid or prefix to review",
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
            help="Replacement accepted-Ground-Memory minimum",
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
            help="Why the Goal or target requirement should change",
        ),
    ] = None,
    upgrade_propositions: Annotated[
        bool,
        typer.Option(
            "--upgrade-propositions",
            help=(
                "Explicitly migrate a bound version-2 Ground to the "
                "proposition-authoritative version-3 schema"
            ),
        ),
    ] = False,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the saved session view",
        ),
    ] = False,
    replace_ground: Annotated[
        bool,
        typer.Option(
            "--replace-ground",
            help="Explicitly replace an existing or malformed named Ground",
        ),
    ] = False,
    if_ground_version: Annotated[
        Optional[str],
        typer.Option(
            "--if-ground-version",
            hidden=True,
        ),
    ] = None,
    if_context_version: Annotated[
        Optional[list[str]],
        typer.Option(
            "--if-context-version",
            hidden=True,
        ),
    ] = None,
    resume_draft: Annotated[
        Optional[str],
        typer.Option(
            "--resume-draft",
            hidden=True,
        ),
    ] = None,
) -> None:
    """Create, inspect, or revise one Ground workspace or legacy session."""
    return run_ground_command(
        GroundCommandRequest(
            ground_name=ground_name,
            request=request,
            sessions=sessions,
            goal=goal,
            set_goal=set_goal,
            add_rule=add_rule,
            add_example=add_example,
            add_relation=add_relation,
            undo_local=undo_local,
            if_ground_revision=if_ground_revision,
            scope=scope,
            description=description,
            raw_context=raw_context,
            derived_context=derived_context,
            publication_target=publication_target,
            placement_target=placement_target,
            blocked_target=blocked_target,
            focus_target=focus_target,
            select=select,
            propose_source=propose_source,
            propose_example=propose_example,
            example_rule=example_rule,
            example_source=example_source,
            example_target=example_target,
            example_input=example_input,
            example_expected=example_expected,
            propose_rule=propose_rule,
            propose_rule_target=propose_rule_target,
            fit_rule=fit_rule,
            propose_target=propose_target,
            expected=expected,
            rationale=rationale,
            case_role=case_role,
            disposition=disposition,
            set_example_use=set_example_use,
            use=use,
            rule_provenance=rule_provenance,
            decide=decide,
            action=action,
            response=response,
            revise_target=revise_target,
            revise_goal=revise_goal,
            requirement_text=requirement_text,
            minimum_cases=minimum_cases,
            blocked_reason=blocked_reason,
            change_reason=change_reason,
            upgrade_propositions=upgrade_propositions,
            snapshot=snapshot,
            replace_ground=replace_ground,
            if_ground_version=if_ground_version,
            if_context_version=if_context_version,
            resume_draft=resume_draft,
        )
    )
