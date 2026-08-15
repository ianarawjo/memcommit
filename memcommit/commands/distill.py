"""Distill evidence-bound Rules from one Context into a reviewed proposal."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.commands.command_progress import CommandProgress
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.distill import DistillError
from memcommit.distill_application import (
    DistillApplyRequest,
    DistillRequest,
    DistillResult,
)
from memcommit.distill_runtime import execute_distill, execute_distill_apply
from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.store import MemoryStore, validate_context_name


def render_distill(result: DistillResult) -> str:
    """Render the complete proposal without implying that it was applied."""

    analysis = result.analysis
    lines = [
        f"DISTILL · {safe_terminal_text(analysis.source.context_name)}",
        "STATUS · REVIEW ONLY · SOURCE UNCHANGED · "
        + (
            "RECURSIVE"
            if analysis.source.include_descendants
            else "DIRECT"
        ),
        "",
        "GOAL",
        safe_terminal_text(analysis.goal or "(none; distill the Context on its own terms)"),
        "",
        "WHAT MEM UNDERSTOOD",
        safe_terminal_text(analysis.overview),
        "",
        f"PROPOSED RULES · {len(analysis.rules)}",
    ]
    for index, rule in enumerate(analysis.rules, 1):
        sources = ", ".join(uid[:8] for uid in rule.support_memory_uids) or "none"
        boundaries = ", ".join(uid[:8] for uid in rule.boundary_memory_uids) or "none"
        lines.extend(
            [
                "",
                f"{index}. [{rule.uid[:8]}] {safe_terminal_text(rule.content)}",
                "   FROM GOAL · " + ("YES" if rule.goal_support else "NO"),
                f"   SUPPORT · {sources}",
                f"   BOUNDARY · {boundaries}",
                f"   WHY · {safe_terminal_text(rule.rationale)}",
            ]
        )
    lines.extend(
        [
            "",
            f"OUTSIDE PROPOSED RULES · {len(analysis.outside_memory_uids)} Memories",
            "No Result Context or checkpoint has been created.",
        ]
    )
    return "\n".join(lines)


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing local Context to distill by canonical name or explicit "
                "relative locator (defaults to current)"
            )
        ),
    ] = None,
    goal: Annotated[
        Optional[str],
        typer.Option(
            "--goal",
            "-g",
            help="Optional Goal that constrains or supports the Rules",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only directly owned Memories in the selected Context",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include readable lexical descendants and embedded Contexts",
        ),
    ] = False,
    save_as: Annotated[
        Optional[str],
        typer.Option(
            "--save-as",
            help="Fresh local Context name for the reviewed Rules",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Create --save-as from this exact proposal without a TTY prompt",
        ),
    ] = False,
) -> None:
    """Distill reusable Rules; Source is unchanged and Apply requires a new Result."""

    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)
        if apply and save_as is None:
            raise DistillError("--apply requires --save-as RESULT_CONTEXT.")
        store = MemoryStore(create=False)
        if save_as is not None:
            validate_context_name(save_as)
            if store.context_exists(save_as):
                raise DistillError(
                    f"Distill Result Context already exists: '{save_as}'."
                )
        with CommandProgress(
            "DISTILL",
            "freezing source",
            total=2,
        ) as progress:
            def connect_provider():
                progress.update("distilling Rules", step=2)
                return connect_semantic_provider()

            result = execute_distill(
                request=DistillRequest(
                    context_locator=context_name,
                    goal=goal,
                    include_descendants=traversal.include_descendants,
                    follow_embeds=traversal.follow_embeds,
                ),
                store=store,
                provider_factory=connect_provider,
            )
        typer.echo(render_distill(result))

        should_apply = apply
        if save_as is not None and not apply and sys.stdin.isatty() and sys.stdout.isatty():
            should_apply = typer.confirm(
                f"Create '{save_as}' from these exact {len(result.analysis.rules)} Rules?",
                default=False,
            )
        if should_apply:
            assert save_as is not None
            receipt = execute_distill_apply(
                DistillApplyRequest(result=result, output_name=save_as),
                store=store,
            )
            typer.echo("")
            typer.secho(
                f"Created Distill Result '{receipt.output_name}' with "
                f"{len(receipt.result_memory_uids)} Rules; Source unchanged.",
                fg=typer.colors.GREEN,
            )
            typer.echo(f"CHECKPOINT · {receipt.checkpoint_uid[:8]} · RECOVERY · mem undo")
        elif save_as is not None:
            typer.echo(
                f"RESULT · {safe_terminal_text(save_as)} · NOT CREATED · "
                "rerun with --apply only after reviewing this proposal"
            )
    except (
        DistillError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Distill error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
