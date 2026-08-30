"""Generate exact-count, explicitly unverified Rule or Case proposals."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.makemore.proposal import (
    render_makemore_plain,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.operations.makemore.model import (
    MakemoreError,
    MakemoreMode,
)
from memcommit.application.operations.makemore.application import (
    MakemoreRequest,
    MakemoreResult,
)
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_operand,
)
from memcommit.application.operations.makemore.add_runtime import (
    FrozenMakemoreSource,
    PreparedMakemoreAdd,
    apply_prepared_makemore_add,
    freeze_makemore_context_source,
    prepare_makemore_add,
)
from memcommit.application.operations.ground.makemore import (
    FrozenGroundMakemore,
    GroundMakemoreResult,
    apply_ground_makemore_result,
    execute_ground_makemore,
    freeze_ground_makemore,
)
from memcommit.adapters.console.terminal.components.applied_memory_preview import (
    render_applied_memory_preview,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    resolve_memorization_target,
    resolve_semantic_result_endpoints,
)
from memcommit.persistence.store import MemoryStore


def cmd(
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            "-g",
            help=(
                "Goal focus as a Context, CONTEXT:UID/UID Memory, or inline "
                "text; alone it is also the Goal Source for Rule generation"
            ),
        ),
    ] = None,
    rule: Annotated[
        Optional[list[str]],
        typer.Option(
            "--rule",
            help=(
                "Rule to expand into suggested Case propositions; repeat for "
                "more Rules"
            ),
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help="Existing Source Context (defaults to current)",
        ),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help="Existing Context that receives generated Memories (defaults to current)",
        ),
    ] = None,
    as_role: Annotated[
        str,
        typer.Option(
            "--as",
            help="Interpret Context Source Memories as rules (default) or one goal",
        ),
    ] = "rules",
    number: Annotated[
        Optional[int],
        typer.Option(
            "--number",
            "--n",
            "-n",
            min=1,
            help="Exact positive proposal count (default 3; no fixed maximum)",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help=(
                "Require generated Cases to pass independent Source Rule "
                "Conformance and Fit before Add"
            ),
        ),
    ] = False,
    ground: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help="Use one exact saved Ground revision instead of inline input",
        ),
    ] = None,
    adopt: Annotated[
        bool,
        typer.Option(
            "--adopt",
            help=(
                "Explicitly add the complete physical-Ground proposal to its "
                "/rules or /examples lane"
            ),
        ),
    ] = False,
    from_goal: Annotated[
        bool,
        typer.Option(
            "--from-goal",
            help="With --ground, propose Rules from its Goal",
        ),
    ] = False,
    from_rules: Annotated[
        bool,
        typer.Option(
            "--from-rules",
            help=("With --ground, propose Case propositions from its active Rules"),
        ),
    ] = False,
) -> None:
    """Generate Rules or Cases and add them to an existing Context."""

    try:
        frozen_ground: FrozenGroundMakemore | None = None
        ground_result: GroundMakemoreResult | None = None
        ground_store: MemoryStore | None = None
        prepared: PreparedMakemoreAdd | None = None
        ordinary_store: MemoryStore | None = None
        ordinary_source: FrozenMakemoreSource | None = None
        ordinary_target: str | None = None
        if ground is not None:
            if source_name is not None or target_name is not None or as_role != "rules":
                raise MakemoreError(
                    "--ground cannot be combined with --from, --to, or --as."
                )
            if goal is not None or rule:
                raise MakemoreError(
                    "Use --ground or inline --goal/--rule input, not both."
                )
            if from_goal == from_rules:
                raise MakemoreError(
                    "With --ground, choose exactly one of --from-goal or --from-rules."
                )
            ground_store = MemoryStore(create=False)
            frozen_ground = freeze_ground_makemore(
                ground_store,
                ground_name=ground,
                direction="GOAL_TO_RULES" if from_goal else "RULES_TO_CASES",
                number=number,
                strict=strict,
            )
            request = frozen_ground.request
        else:
            if adopt:
                raise MakemoreError("--adopt requires --ground.")
            if from_goal or from_rules:
                raise MakemoreError("--from-goal/--from-rules require --ground.")
            ordinary_store = MemoryStore(create=False)
            snapshot = ContextOperandSnapshot.capture(ordinary_store)
            goal_focus = (
                freeze_goal_focus_operand(
                    ordinary_store,
                    goal,
                    current_name=snapshot.current_name,
                )
                if goal is not None
                else None
            )
            inline_rules = bool(rule)
            if source_name is not None and inline_rules:
                raise MakemoreError(
                    "Inline --rule input cannot be combined with --from."
                )
            context_source = source_name is not None or (
                not inline_rules and goal_focus is None
            )
            if not context_source:
                if as_role != "rules":
                    raise MakemoreError("--as applies only to a Context Source.")
                if inline_rules:
                    request = MakemoreRequest(
                        rules=tuple(rule or ()),
                        goal_focus=goal_focus,
                        number=number,
                        strict=strict,
                    )
                else:
                    assert goal_focus is not None
                    if len(goal_focus.items) != 1:
                        raise MakemoreError(
                            "Standalone --goal requires one Goal item; use --from "
                            "with --as goal for an exact one-Memory Goal Source."
                        )
                    request = MakemoreRequest(
                        goal=goal_focus.text,
                        goal_focus=goal_focus,
                        number=number,
                        strict=strict,
                    )
                ordinary_target = resolve_memorization_target(
                    target_locator=target_name,
                    current=snapshot.current_name,
                )
            else:
                endpoints = resolve_semantic_result_endpoints(
                    source_locator=source_name,
                    target_locator=target_name,
                    current=snapshot.current_name,
                )
                if as_role not in {"goal", "rules"}:
                    raise MakemoreError("Makemore --as must be 'goal' or 'rules'.")
                ordinary_source = freeze_makemore_context_source(
                    ordinary_store,
                    context_name=endpoints.source_name,
                    role=as_role,
                    number=number,
                    strict=strict,
                    goal_focus=goal_focus,
                )
                request = ordinary_source.request
                ordinary_target = endpoints.target_name

        def execute(value: MakemoreRequest) -> MakemoreResult:
            nonlocal prepared, ground_result
            with CommandProgress(
                "MAKEMORE",
                "generating review proposals",
                total=1,
            ) as progress:
                if frozen_ground is not None and ground_store is not None:
                    ground_result = execute_ground_makemore(
                        frozen_ground,
                        store=ground_store,
                        provider_factory=connect_semantic_provider,
                    )
                    result = ground_result.makemore
                else:
                    assert ordinary_store is not None
                    assert ordinary_target is not None
                    prepared = prepare_makemore_add(
                        store=ordinary_store,
                        request=value,
                        target_name=ordinary_target,
                        provider_factory=connect_semantic_provider,
                        source=ordinary_source,
                        will_apply=True,
                    )
                    result = prepared.result
                progress.update("proposal ready", step=1)
                return result

        result = execute(request)
        if frozen_ground is not None:
            render_makemore_plain(result)
            if adopt:
                if ground_result is None or ground_store is None:
                    raise MakemoreError("Makemore produced no Ground proposal.")
                receipt = apply_ground_makemore_result(
                    ground_result,
                    store=ground_store,
                )
                typer.secho(
                    f"MAKEMORE ADOPTED · {display_escape_text(receipt.workspace_name)}"
                    f"/{receipt.lane}",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
                typer.echo(
                    f"EFFECTS · ADD {len(receipt.memory_uids)} MEMORIES · "
                    f"GROUND REVISION {receipt.revision}"
                )
                typer.echo(f"UNDO · mem ground {receipt.workspace_name} --undo")
            return
        if result is None or prepared is None or ordinary_store is None:
            raise MakemoreError("Makemore produced no addable proposal.")
        receipt = apply_prepared_makemore_add(prepared, store=ordinary_store)
        typer.secho(
            f"MAKEMORE APPLIED · {display_escape_text(receipt.target_name)}",
            fg=typer.colors.GREEN,
            bold=True,
        )
        source_label = receipt.source_name or "INLINE"
        typer.echo(
            f"MODE · {prepared.result.analysis.mode.value} · "
            "VERIFICATION · UNVERIFIED · "
            f"QUALITY · {prepared.result.analysis.quality_policy.value}"
        )
        typer.echo(
            f"SOURCE · {display_escape_text(source_label)} · "
            f"TARGET · {display_escape_text(receipt.target_name)}"
        )
        typer.echo(f"EFFECTS · ADD {receipt.count} MEMORIES")
        analysis = prepared.result.analysis
        added_contents = (
            tuple(item.content for item in analysis.rules)
            if analysis.mode is MakemoreMode.GOAL_TO_RULES
            else tuple(item.proposition for item in analysis.cases)
        )
        render_applied_memory_preview(receipt.memory_uids, added_contents)
        typer.echo(f"REVIEW · mem review makemore --receipt {receipt.checkpoint_uid}")
        typer.echo("UNDO · mem undo")
    except (
        MakemoreError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Makemore error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
