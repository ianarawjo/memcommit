"""CLI boundary for saved translation views and explicit materialization."""
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.translate import (
    TranslateError,
    TranslationPlan,
    resolve_translation_selector,
    translation_plan_matches_context,
    validate_translation_target,
)
from memcommit.translation_view import (
    TranslationView,
    TranslationViewError,
    translation_view_record_digest,
)
from memcommit.translation_view_store import (
    ConcurrentTranslationViewUpdateError,
    load_translation_view,
    save_translation_view,
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


def _render_view(
    ctx: Context,
    view: TranslationView,
    *,
    reused: bool,
) -> None:
    """Render one saved language lens without inventing result identities."""
    by_source_uid = {
        entry.source_uid: entry
        for entry in view.entries
    }
    typer.echo()
    typer.secho(
        f"Translation view: '{view.context_name}' → "
        f"{view.target_language}",
        bold=True,
    )
    typer.echo(
        f"  {len(view.entries)} translated "
        f"{'Memory' if len(view.entries) == 1 else 'Memories'}"
    )
    typer.echo("─" * 64)
    for item in ctx.iter_items():
        entry = by_source_uid.get(item.uid)
        if isinstance(item, Memory):
            if entry is None:
                continue
            typer.secho(
                f"[{item.uid[:8]}] {view.target_language} view",
                fg=typer.colors.CYAN,
            )
            for line in (
                safe_terminal_text(entry.translated_content).splitlines()
                or [""]
            ):
                typer.echo(f"  {line}")
            continue
        if view.selected_memory_uid is not None:
            continue
        if isinstance(item, Context):
            typer.echo(
                f"[context {item.uid[:8]}] "
                f"{safe_terminal_text(item.name)} (not translated)"
            )
        elif isinstance(item, QueryContextRef):
            typer.echo(
                f"[query   {item.uid[:8]}] "
                f"{safe_terminal_text(item.name)} "
                "(query-only; not translated)"
            )
        elif isinstance(item, MemoryRef):
            typer.echo(
                f"[ref     {item.uid[:8]}] "
                f"{safe_terminal_text(item.target_context_name)}"
                f"#{item.target_memory_uid[:8]} (not translated)"
            )
    typer.echo("─" * 64)
    if reused:
        typer.secho(
            "Reused saved translation view; the provider was not called.",
            fg=typer.colors.CYAN,
        )
    else:
        typer.secho(
            "Saved translation view.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    typer.echo(
        "No Context or Memory changes; source Memory UIDs remain the anchors."
    )


def _open_or_create_view(
    *,
    store: MemoryStore,
    ctx: Context,
    target_language: str,
    selected_memory_uid: str | None,
    refresh: bool,
) -> tuple[TranslationView | None, bool]:
    """Reuse one exact saved view or atomically replace its deterministic slot."""
    existing = load_translation_view(
        ctx.uid,
        target_language,
        selected_memory_uid,
    )
    if (
        existing is not None
        and existing.matches(ctx)
        and not refresh
    ):
        return existing, True

    plan = ops.translate(
        ctx,
        target_language,
        connect_codex_chatgpt_provider,
        selector=selected_memory_uid,
        allocate_operation_uid=False,
    )
    if not plan.proposals:
        return None, False
    view = TranslationView.from_plan(plan, ctx)
    save_translation_view(
        store,
        view,
        expected_record_digest=(
            translation_view_record_digest(existing)
            if existing is not None
            else None
        ),
    )
    return view, False


def cmd(
    target_language: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help=(
                "Semantic translation target (quote multi-word specs): "
                "language, locale, register, audience, or terminology"
            ),
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
                "Materialize the translation view as a new Context and "
                "switch to it"
            ),
        ),
    ] = None,
    in_place: Annotated[
        bool,
        typer.Option(
            "--in-place",
            help=(
                "Materialize translated siblings in the source Context"
            ),
        ),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help=(
                "Generate and replace the saved view even when an exact one "
                "can be reused"
            ),
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help=(
                "Apply an explicit --save-as or --in-place materialization "
                "without confirmation"
            ),
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        if in_place and save_as is not None:
            raise TranslateError(
                "--save-as and --in-place cannot be used together."
            )
        if yes and save_as is None and not in_place:
            raise TranslateError(
                "--yes applies only with --save-as CONTEXT or --in-place. "
                "Bare 'mem translate' saves a view without changing a Context."
            )
        direct_ctx = store.load_current_direct()
        language = validate_translation_target(target_language)
        selected_memory_uid = resolve_translation_selector(
            direct_ctx,
            selector,
        )
        destination_name = save_as
        if destination_name is not None:
            store.assert_context_creatable(destination_name)
        view, reused = _open_or_create_view(
            store=store,
            ctx=direct_ctx,
            target_language=language,
            selected_memory_uid=selected_memory_uid,
            refresh=refresh,
        )
    except (
        ConcurrentTranslationViewUpdateError,
        OSError,
        RuntimeError,
        TranslationViewError,
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

    if view is None:
        typer.echo(
            f"Context '{direct_ctx.name}' has no directly owned Memories "
            "to translate."
        )
        return

    if destination_name is None and not in_place:
        _render_view(direct_ctx, view, reused=reused)
        return

    try:
        plan = view.to_translation_plan(direct_ctx)
    except TranslationViewError as error:
        typer.secho(
            f"Translate error: {error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    operation_uid = plan.operation_uid
    if not isinstance(operation_uid, str):
        typer.secho(
            "Translate error: materialization identity was not allocated.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if reused:
        typer.secho(
            "Reusing the saved translation view; the provider was not called.",
            fg=typer.colors.CYAN,
        )
    else:
        typer.secho(
            "Saved the translation view before materialization review.",
            fg=typer.colors.CYAN,
        )
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
        typer.echo(
            "Aborted — the translation view remains saved; "
            "no Context changes made."
        )
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
                        + (
                            "translation"
                            if len(result.translations) == 1
                            else "translations"
                        )
                        + " "
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
                            "operation_uid": operation_uid,
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
                            f"[{operation_uid[:8]}]"
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
                            + (
                                "Memory"
                                if len(result.translations) == 1
                                else "Memories"
                            )
                            + " "
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
