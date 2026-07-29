"""CLI boundary for derived-Context and explicit in-place translation."""
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.review_shell import safe_terminal_text
from memcommit.context import AutoCheckpoint, Memory
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.translate import (
    TranslateError,
    TranslationPlan,
    default_translation_context_name,
    translation_plan_matches_context,
)


def _render_text(prefix: str, value: str) -> None:
    lines = safe_terminal_text(value).splitlines() or [""]
    typer.echo(f"  {prefix} {lines[0]}")
    continuation = " " * (len(prefix) + 3)
    for line in lines[1:]:
        typer.echo(f"{continuation}{line}")


def _render_preview(
    plan: TranslationPlan,
    *,
    destination_name: str | None,
) -> None:
    count = len(plan.proposals)
    typer.echo()
    if destination_name is None:
        heading = (
            f"Proposed {count} "
            f"{'translation' if count == 1 else 'translations'} to "
            f"{plan.target_language} in '{plan.context_name}'"
        )
    else:
        heading = (
            f"Proposed {count} "
            f"{'translation' if count == 1 else 'translations'} to "
            f"{plan.target_language}\n"
            f"Source: '{plan.context_name}'\n"
            f"New Context: '{destination_name}'"
        )
    typer.secho(heading, bold=True)
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
    save_as: Annotated[
        Optional[str],
        typer.Option(
            "--save-as",
            metavar="CONTEXT",
            help=(
                "Override the automatically derived destination Context name"
            ),
        ),
    ] = None,
    in_place: Annotated[
        bool,
        typer.Option(
            "--in-place",
            help=(
                "Keep the source Context current and add translated siblings "
                "there instead of creating a derived Context"
            ),
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Apply the validated translations without confirmation",
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        if in_place and save_as is not None:
            raise TranslateError(
                "--save-as and --in-place cannot be used together."
            )
        direct_ctx = store.load_current_direct()
        destination_name = (
            None
            if in_place
            else (
                save_as
                or default_translation_context_name(
                    direct_ctx.name,
                    target_language,
                )
            )
        )
        if destination_name is not None:
            store.assert_context_creatable(destination_name)
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

    _render_preview(plan, destination_name=destination_name)
    if destination_name is None:
        confirmation = (
            f"Add {len(plan.proposals)} translated "
            f"{'copy' if len(plan.proposals) == 1 else 'copies'}?"
        )
    else:
        confirmation = (
            f"Create translated Context '{destination_name}' and switch to it?"
        )
    if not yes and not typer.confirm(confirmation, default=False):
        typer.echo("Aborted — no changes made.")
        return

    try:
        if store.current_context_name() != plan.context_name:
            raise TranslateError(
                "The current Context changed while translations were being "
                "prepared; no translations were added."
            )
        source = store.load_direct(plan.context_name)
        if destination_name is None:
            result = ops.apply_translation(source, plan)
            store.save(
                source,
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
            destination = source
        else:
            result = ops.derive_translation_context(
                source,
                plan,
                destination_name,
            )
            created = False
            try:
                store.create_context(
                    result.baseline,
                    AutoCheckpoint(
                        command="init",
                        args={
                            "name": destination_name,
                            "source_context": {
                                "uid": plan.context_uid,
                                "name": plan.context_name,
                                "digest": plan.context_digest,
                            },
                            "operation_uid": plan.operation_uid,
                            "target_language": plan.target_language,
                            "memory_uids": [
                                item.uid
                                for item in result.baseline.iter_items()
                                if isinstance(item, Memory)
                            ],
                        },
                        description=(
                            f"Initialized '{destination_name}' from "
                            f"'{plan.context_name}' before translation "
                            f"[{plan.operation_uid[:8]}]"
                        ),
                    ),
                )
                created = True
                # The final derived frame was built from this exact baseline.
                # Carry its just-persisted digest so a concurrent destination
                # writer cannot be overwritten between the two checkpoints.
                result.context._store_digest = (
                    result.baseline._store_digest
                )
                store.save(
                    result.context,
                    AutoCheckpoint(
                        command="translate",
                        args=result.checkpoint_args(),
                        description=(
                            f"Replaced {len(result.translations)} source "
                            f"{'Memory' if len(result.translations) == 1 else 'Memories'} "
                            f"with translations to {plan.target_language}"
                        ),
                    ),
                    expected_context_digest=result.baseline._store_digest,
                )
                latest_source = store.load_direct(plan.context_name)
                if not translation_plan_matches_context(
                    plan,
                    latest_source,
                ):
                    raise TranslateError(
                        "The source Context changed while the translated "
                        "Context was being created; the destination was not "
                        "selected."
                    )
                if store.current_context_name() != plan.context_name:
                    raise TranslateError(
                        "The current Context changed while the translated "
                        "Context was being created; the destination was not "
                        "selected."
                    )
                store.set_current_context_if(
                    plan.context_name,
                    destination_name,
                    expected_context_uid=result.context.uid,
                    expected_context_digest=(
                        result.context._store_digest or ""
                    ),
                )
                destination = result.context
            except Exception as error:
                if created:
                    # Once a Context is published, another process may already
                    # have switched to or referenced it without changing its
                    # own digest. Automatic deletion could therefore create a
                    # dangling external pointer. Preserve the durable frame
                    # and make the partial outcome explicit instead.
                    raise TranslateError(
                        f"Translation failed ({error}); destination "
                        f"'{destination_name}' was preserved for manual "
                        "inspection and the source was not changed."
                    ) from error
                raise
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

    if destination_name is None:
        message = (
            f"Added {len(result.translations)} translated "
            f"{'Memory' if len(result.translations) == 1 else 'Memories'} "
            f"to '{destination.name}' in {plan.target_language}."
        )
    else:
        message = (
            f"Created translated Context '{destination.name}' from "
            f"'{plan.context_name}' with {len(result.translations)} translated "
            f"{'Memory' if len(result.translations) == 1 else 'Memories'} "
            f"in {plan.target_language} and switched to it."
        )
    typer.secho(message, fg=typer.colors.GREEN, bold=True)
    for translation in result.translations:
        typer.echo(
            f"  [{translation.source_uid[:8]}] -> "
            f"[{translation.result.uid[:8]}]"
        )
