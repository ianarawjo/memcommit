import sys
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.command_wait import (
    CommandWaitView,
    build_report_loading_view,
    run_command_wait,
)
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.forget_setup_workbench import choose_forget_setup
from memcommit.commands.granted_context import (
    authorized_context_mutation,
    context_access_display_facts,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.context import AutoCheckpoint, Context
from memcommit.forget_resolution_adapter import ForgetResolutionWorkbenchAdapter
from memcommit.forget_review import ForgetReview, ForgetSelection
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.provider_types import ProviderIdentity
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.resolution_workbench import ResolutionNavigation
from memcommit.semantic.changes import EditChange, RemoveChange, ProposedChange, apply_changes
from memcommit.store import MemoryStore


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _provider_label(provider: object) -> str:
    identity = getattr(provider, "identity", None)
    if isinstance(identity, ProviderIdentity):
        return identity.display_name()
    model = getattr(provider, "model", None)
    return str(model) if model else "configured semantic provider"


def _forget_analysis_stage(ctx: Context) -> str:
    """Describe the one honest blocking boundary without implying percent progress."""

    return f"analyzing {len(ctx.memories)} source memories x 1 instruction"


def _forget_wait_view(ctx: Context, info: str) -> CommandWaitView:
    """Show the reviewed input because no Forget report exists pre-analysis."""

    text = "\n".join(
        [
            "MEM FORGET · FROZEN INPUT · RESULT PENDING",
            "",
            f"SOURCE · {safe_terminal_text(ctx.name)} · THIS CONTEXT ONLY",
            f"FROZEN MEMORIES · {len(ctx.memories)}",
            "SOURCE STATE · UNCHANGED",
            "",
            "INSTRUCTION",
            safe_terminal_text(info),
            "",
            "The review report will replace this setup after the provider returns.",
        ]
    )
    return CommandWaitView(title="FORGET CONFIRMED INPUTS · READ-ONLY", text=text)


def _run_resolution_forget(
    ctx: Context,
    info: str,
    llm: object,
) -> list[ProposedChange]:
    from memcommit.commands.resolution_workbench_shell import (
        run_resolution_workbench_shell,
    )

    # Forget remains one whole-frame provider turn. Only its host execution is
    # moved off the foreground so Help can be explored without partitioning or
    # changing the semantic request.
    analysis, _history = run_command_wait(
        "FORGET",
        _forget_analysis_stage(ctx),
        total=1,
        work=lambda _progress: ops.analyze_forget(ctx, info, llm),
        return_view=build_report_loading_view(
            "FORGET",
            sections=("What mem understood", "Review decisions", "To do"),
        ),
        context_view=_forget_wait_view(ctx, info),
    )
    if not analysis.decisions:
        typer.echo("Nothing to apply.")
        return []
    review = ForgetReview.create(ctx, info, analysis)
    navigation = ResolutionNavigation()
    while True:
        action = run_resolution_workbench_shell(
            ForgetResolutionWorkbenchAdapter(review).view,
            navigation=navigation,
            terminal_label="Interactive Forget",
            snapshot_hint=(
                "Run 'mem forget INSTRUCTION' in a terminal to review the batch."
            ),
            review_and_apply=True,
            split_viewer_items=True,
        )
        if action.kind == "CLOSE":
            return []
        if action.kind == "ACCEPT":
            changes = review.changes()
            apply_changes(ctx, changes)
            return changes
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise ValueError("Unsupported Forget workbench action.")
        if action.comment.strip():
            review = review.select(
                action.item_uid,
                "CUSTOM",
                action.comment.strip(),
            )
            continue
        suffix = (action.option_uid or "").rpartition(":")[2]
        selection: ForgetSelection | None = {
            "recommended": "RECOMMENDED",
            "keep": "KEEP",
            "delete": "DELETE",
        }.get(suffix)  # type: ignore[assignment]
        if selection is None:
            raise ValueError("Unsupported Forget decision.")
        review = review.select(action.item_uid, selection)


def _required_permissions(changes: list[ProposedChange]) -> tuple[str, ...]:
    permissions = {
        "DELETE" if isinstance(change, RemoveChange) else "UPDATE"
        for change in changes
    }
    return tuple(sorted(permissions))


def _print_proposals(proposals: list[ProposedChange], query: str) -> None:
    typer.echo()
    typer.secho(f'Proposed changes for "{query}"', bold=True)
    typer.echo("-" * 56)
    if not proposals:
        typer.secho("  (no changes proposed - nothing matched)", dim=True)
        typer.echo("-" * 56)
        return

    for i, change in enumerate(proposals, 1):
        if isinstance(change, RemoveChange):
            typer.secho(f'  {i}  REMOVE  [{change.uid[:8]}]  "{change.content}"', fg=typer.colors.RED, bold=True)
            typer.secho(f"       Reason: {change.reason}", dim=True)
        elif isinstance(change, EditChange):
            typer.secho(f'  {i}  EDIT    [{change.uid[:8]}]  "{change.old_content}"', fg=typer.colors.YELLOW, bold=True)
            typer.secho(f'         -> "{change.new_content}"', fg=typer.colors.GREEN)
            typer.secho(f"       Reason: {change.reason}", dim=True)
        typer.echo()

    typer.echo("-" * 56)


def _run_interactive_forget(
    ctx: Context,
    info: str,
    llm: object,
) -> list[ProposedChange]:
    if _interactive_terminal():
        return _run_resolution_forget(ctx, info, llm)
    typer.secho(f"Consulting {_provider_label(llm)!r}...", dim=True)
    # The shared wait is intentionally silent outside a TTY, preserving the
    # stable redirected output while keeping one orchestration path.
    proposals, history = run_command_wait(
        "FORGET",
        _forget_analysis_stage(ctx),
        total=1,
        work=lambda _progress: ops.forget(ctx, info, llm),
    )

    while True:
        _print_proposals(proposals, info)

        if not proposals:
            typer.echo("Nothing to apply.")
            return []

        n = len(proposals)
        label = "change" if n == 1 else "changes"
        typer.echo(f"Apply {'this' if n == 1 else 'these'} {n} {label}?")
        typer.secho("  y = apply    n = abort    r = revise with feedback", dim=True)
        decision = typer.prompt(">", default="", show_default=False).strip()

        if decision.lower() in ("y", "yes"):
            apply_changes(ctx, proposals)
            removes = sum(1 for c in proposals if isinstance(c, RemoveChange))
            edits = sum(1 for c in proposals if isinstance(c, EditChange))
            parts = (
                ([f"{removes} removed"] if removes else [])
                + ([f"{edits} edited"] if edits else [])
            )
            typer.secho(f"Done: {', '.join(parts)}.", fg=typer.colors.GREEN)
            return proposals

        if decision.lower() in ("n", "no"):
            typer.echo("Aborted - no changes made.")
            return []

        feedback = decision if not decision.lower().startswith("r") else ""
        if not feedback:
            feedback = typer.prompt("Describe what to change", default="", show_default=False).strip()
        if not feedback:
            continue

        typer.secho(f"Revising with {_provider_label(llm)!r}...", dim=True)
        proposals, history = ops.revise_forget(feedback, llm, history, ctx)


def cmd(
    info: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Description of Memories to forget; omit in a terminal to "
                "enter an instruction and select one direct Source"
            ),
        ),
    ] = None,
) -> None:
    if info is None and not _interactive_terminal():
        typer.secho(
            "Forget error: INSTRUCTION is required outside a terminal. In a "
            "terminal, run 'mem forget' to open the interactive Forget setup.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    active_store = MemoryStore()
    try:
        context_snapshot = ContextOperandSnapshot.capture(active_store)
        access = resolve_context_access(
            active_store,
            None,
            current_name=context_snapshot.current_name,
            required_permission="READ",
        )
        if info is None:
            catalog = freeze_profile_readable_context_catalog(
                active_store,
                access,
                include_query_routes=False,
            )
            names = tuple(catalog.list_context_names())
            annotations = {
                name: context_access_display_facts(catalog.access_for(name))
                for name in names
                if catalog.access_for(name).is_granted
            }
            receipt = choose_forget_setup(
                names,
                current=access.display_name,
                annotations=annotations,
            )
            if receipt is None:
                typer.echo("Forget cancelled.")
                return
            # The receipt names a row from this frozen public catalog. Preserve
            # its exact Grant/store binding instead of consulting current again.
            access = catalog.access_for(receipt.context_name)
            info = receipt.instruction
        store = access.store
        ctx = store.load_direct(access.context_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        assert info is not None
        provider = connect_codex_chatgpt_provider()
        applied = _run_interactive_forget(ctx, info, provider)
    except (OSError, QueryProviderError, RuntimeError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    if applied:
        removes = [c for c in applied if isinstance(c, RemoveChange)]
        edits = [c for c in applied if isinstance(c, EditChange)]
        parts = []
        if removes:
            parts.append(f'removed "{removes[0].content[:40]}"' if len(removes) == 1 else f"removed {len(removes)}")
        if edits:
            parts.append(f'edited "{edits[0].old_content[:40]}"' if len(edits) == 1 else f"edited {len(edits)}")
        try:
            with authorized_context_mutation(
                access,
                required_permissions=_required_permissions(applied),
            ):
                checkpoint = store.save(
                    ctx,
                    AutoCheckpoint(
                        command="forget",
                        args={
                            "query": info,
                            **grant_checkpoint_args(access),
                        },
                        description=f'Forgot ({info[:40]}): {", ".join(parts)}',
                    ),
                )
        except (OSError, ProfileConfigError, ProfileError, ValueError) as error:
            typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if _interactive_terminal():
            effects = []
            if removes:
                effects.append(f"{len(removes)} removed")
            if edits:
                effects.append(f"{len(edits)} edited")
            checkpoint_label = (
                f" · checkpoint [{checkpoint.uid[:8]}]"
                if checkpoint is not None
                else ""
            )
            typer.secho(
                "Forget applied · SOURCE "
                f"{safe_terminal_text(access.display_name)} · "
                f"{', '.join(effects)}{checkpoint_label}",
                fg=typer.colors.GREEN,
            )
