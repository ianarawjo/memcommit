"""CLI application boundary for translated sibling Memories."""
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.review_shell import safe_terminal_text
from memcommit.context import AutoCheckpoint
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.translate import TranslateError, TranslationPlan


def _render_text(prefix: str, value: str) -> None:
    lines = safe_terminal_text(value).splitlines() or [""]
    typer.echo(f"  {prefix} {lines[0]}")
    continuation = " " * (len(prefix) + 3)
    for line in lines[1:]:
        typer.echo(f"{continuation}{line}")


def _render_preview(plan: TranslationPlan) -> None:
    count = len(plan.proposals)
    typer.echo()
    typer.secho(
        f"Proposed {count} "
        f"{'translation' if count == 1 else 'translations'} to "
        f"{plan.target_language} in '{plan.context_name}'",
        bold=True,
    )
    typer.echo("─" * 64)
    for proposal in plan.proposals:
        typer.secho(f"[{proposal.source_uid[:8]}]", fg=typer.colors.CYAN)
        _render_text("-", proposal.source_content)
        _render_text("+", proposal.translated_content)
    typer.echo("─" * 64)


def cmd(
    target_language: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help="Target language name or language tag",
            show_default=True,
        ),
    ] = "English",
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Optional UID (or unambiguous prefix) of one direct Memory; "
                "omit to translate every direct Memory"
            )
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Add the validated translations without confirmation",
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        direct_ctx = store.load_current_direct()
        plan = ops.translate(
            direct_ctx,
            target_language,
            connect_codex_chatgpt_provider,
            selector=selector,
        )
    except (
        OSError,
        RuntimeError,
        ValueError,
        QueryProviderError,
        TranslateError,
    ) as error:
        typer.secho(
            f"Translate error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not plan.proposals:
        typer.echo(
            f"Context '{plan.context_name}' has no directly owned Memories "
            "to translate."
        )
        return

    _render_preview(plan)
    if not yes and not typer.confirm(
        f"Add {len(plan.proposals)} translated "
        f"{'copy' if len(plan.proposals) == 1 else 'copies'}?",
        default=False,
    ):
        typer.echo("Aborted — no changes made.")
        return

    try:
        if store.current_context_name() != plan.context_name:
            raise TranslateError(
                "The current Context changed while translations were being "
                "prepared; no translations were added."
            )
        # The provider and human confirmation can take minutes. Reload through
        # the direct path and validate the complete snapshot before creating a
        # result UID. Context.from_dict retains every pointer record as an
        # opaque placeholder, so this direct-only mutation can save faithfully
        # without opening MemoryRef targets or embedded Contexts.
        ctx = store.load_direct(plan.context_name)
        result = ops.apply_translation(ctx, plan)
        store.save(
            ctx,
            AutoCheckpoint(
                command="translate",
                args=result.checkpoint_args(),
                description=(
                    f"Added {len(result.translations)} "
                    f"{'translation' if len(result.translations) == 1 else 'translations'} "
                    f"to {plan.target_language}"
                ),
            ),
            expected_context_digest=plan.context_digest,
        )
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        TranslateError,
    ) as error:
        typer.secho(
            f"Translate error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Added {len(result.translations)} translated "
        f"{'Memory' if len(result.translations) == 1 else 'Memories'} "
        f"to '{ctx.name}' in {plan.target_language}.",
        fg=typer.colors.GREEN,
        bold=True,
    )
    for translation in result.translations:
        typer.echo(
            f"  [{translation.source_uid[:8]}] -> "
            f"[{translation.result.uid[:8]}]"
        )
