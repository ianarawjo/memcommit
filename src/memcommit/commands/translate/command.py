"""CLI adapter for operation-owned Translate orchestration."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Annotated, Optional

import typer

from memcommit.commands.shared.command_progress import progressing_provider_factory
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.application.operations.translate.application import (
    PreparedTranslation,
    TranslateRequest,
    prepare_translation,
)
from memcommit.application.operations.translate.catalog_application import (
    TRANSLATION_IMPORT_SIZE_LIMIT,
)
from memcommit.application.operations.translate.materialization import (
    TranslationMaterializationResult,
    apply_translation_materialization,
)
from memcommit.application.operations.translate.runtime import TranslateError, TranslationPlan
from memcommit.application.operations.translate.view import (
    TranslationCatalog,
    TranslationViewError,
)
from memcommit.infrastructure.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.source_projection.model import (
    SourceDisplayFacts,
    SourceForm,
    SourceReach,
    SourceState,
)
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_object_label,
)
from memcommit.persistence.store import MemoryStore


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


def _render_catalog(
    context: Context,
    catalog: TranslationCatalog,
    *,
    selector: str | None,
    reused: bool,
) -> None:
    """Render current same-UID representations and explicit review state."""

    effective = catalog.effective_entries(context, selector)
    by_source_uid = {entry.source_uid: entry for entry in effective}
    typer.echo()
    typer.secho(
        f"Translation view: '{catalog.context_name}' → "
        f"{catalog.target_language}",
        bold=True,
    )
    typer.echo(
        f"  {len(effective)} translated "
        f"{'Memory' if len(effective) == 1 else 'Memories'}"
    )
    typer.echo("─" * 64)
    for item in context.iter_items():
        entry = by_source_uid.get(item.uid)
        if isinstance(item, Memory):
            if entry is None:
                continue
            typer.secho(
                f"[{item.uid[:8]}] {catalog.target_language} · "
                f"{entry.origin} · {entry.review_status}",
                fg=typer.colors.CYAN,
            )
            for line in (
                safe_terminal_text(entry.translated_content).splitlines() or [""]
            ):
                typer.echo(f"  {line}")
            continue
        if selector is not None:
            continue
        if isinstance(item, Context):
            facts = SourceDisplayFacts(reach=SourceReach.VIA_EMBED)
            typer.echo(
                f"[{source_object_label(facts)} {item.uid[:8]}] "
                f"{safe_terminal_text(item.name)} · "
                f"{source_annotation_text(facts)} (not translated)"
            )
        elif isinstance(item, QueryContextRef):
            label = source_object_label(SourceForm.QUERY_VIEW)
            typer.echo(
                f"[{label} {item.uid[:8]}] "
                f"{safe_terminal_text(item.name)} (not translated)"
            )
        elif isinstance(item, MemoryRef):
            facts = SourceDisplayFacts(
                form=SourceForm.MEMORY_REF,
                states=(
                    (SourceState.READ_ONLY,)
                    if item.is_resolved
                    else (SourceState.DANGLING,)
                ),
            )
            typer.echo(
                f"[{source_object_label(facts)} {item.uid[:8]}] "
                f"{safe_terminal_text(item.target_context_name)}"
                f"#{item.target_memory_uid[:8]} · "
                f"{source_annotation_text(facts)} (not translated)"
            )
    typer.echo("─" * 64)
    stale = catalog.stale_curated_uids(context)
    if stale:
        typer.secho(
            f"{len(stale)} curated "
            f"{'translation is' if len(stale) == 1 else 'translations are'} "
            "stale and preserved for review.",
            fg=typer.colors.YELLOW,
        )
    if reused:
        typer.secho(
            "Reused saved translation view; the provider was not called.",
            fg=typer.colors.CYAN,
        )
    else:
        typer.secho("Saved translation view.", fg=typer.colors.GREEN, bold=True)
    typer.echo(
        "No Context or Memory changes; source Memory UIDs remain the anchors."
    )


def _read_import_payload(source: str) -> tuple[bytes, str]:
    if source == "-":
        raw = sys.stdin.buffer.read(TRANSLATION_IMPORT_SIZE_LIMIT + 1)
        label = "stdin"
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file():
            raise TranslateError("Translation import must be a regular file.")
        if path.stat().st_size > TRANSLATION_IMPORT_SIZE_LIMIT:
            raise TranslateError("Translation import is too large.")
        raw = path.read_bytes()
        label = str(path)
    if len(raw) > TRANSLATION_IMPORT_SIZE_LIMIT:
        raise TranslateError("Translation import is too large.")
    try:
        return raw, raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TranslateError(
            f"Translation import {label!r} must be UTF-8 JSON."
        ) from error


def _write_export_payload(destination: str, payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if destination == "-":
        typer.echo(rendered, nl=False)
        return
    path = Path(destination)
    if path.is_symlink() or path.exists():
        raise TranslateError(
            "Translation export destination already exists or is unsafe."
        )
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    except OSError as error:
        raise TranslateError(f"Could not write translation export: {error}") from error


def _provider_scope():
    return progressing_provider_factory(
        "TRANSLATE",
        "translating memories",
        connect_codex_chatgpt_provider,
    )


def _render_prepared_nonmaterialization(
    prepared: PreparedTranslation,
    *,
    export_file: str | None,
) -> bool:
    """Render a completed nonmaterializing result; return whether handled."""

    if prepared.kind == "CANCELLED":
        typer.echo("Translation edit cancelled.")
        return True
    if prepared.kind == "EMPTY":
        typer.echo(
            f"Context '{prepared.context.name}' has no directly owned Memories "
            "to translate."
        )
        return True
    if prepared.kind == "EXPORT":
        assert prepared.export_payload is not None
        assert prepared.export_destination is not None
        _write_export_payload(
            prepared.export_destination,
            prepared.export_payload,
        )
        if prepared.export_destination != "-":
            translations = prepared.export_payload["translations"]
            assert isinstance(translations, list)
            typer.secho(
                f"Exported {len(translations)} translation "
                f"{'entry' if len(translations) == 1 else 'entries'} "
                f"to '{safe_terminal_text(export_file or '')}'.",
                fg=typer.colors.GREEN,
            )
        return True
    if prepared.kind == "IMPORT":
        assert prepared.catalog is not None
        typer.secho(
            f"Imported {prepared.changed_count} changed same-UID translation "
            f"{'entry' if prepared.changed_count == 1 else 'entries'}; "
            "untouched rows preserved their provenance.",
            fg=typer.colors.GREEN,
            bold=True,
        )
        _render_catalog(
            prepared.context,
            prepared.catalog,
            selector=None,
            reused=False,
        )
        return True
    if prepared.kind == "VIEW":
        assert prepared.catalog is not None
        _render_catalog(
            prepared.context,
            prepared.catalog,
            selector=prepared.selected_memory_uid,
            reused=prepared.reused,
        )
        return True
    return False


def _render_materialization_receipt(
    result: TranslationMaterializationResult,
) -> None:
    plan = result.plan
    if result.created_context:
        message = (
            f"Created translated Context '{result.destination.name}' from "
            f"'{plan.context_name}' with {len(result.translations)} translated "
            f"{'Memory' if len(result.translations) == 1 else 'Memories'} "
            f"in {plan.target_language} and switched to it."
        )
    else:
        message = (
            f"Added {len(result.translations)} translated "
            f"{'Memory' if len(result.translations) == 1 else 'Memories'} "
            f"to '{result.destination.name}' in {plan.target_language}."
        )
    typer.secho(message, fg=typer.colors.GREEN, bold=True)
    for translation in result.translations:
        typer.echo(
            f"  [{translation.source_uid[:8]}] -> "
            f"[{translation.result.uid[:8]}]"
        )


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
                "Auto-typed existing Context, Memory UID/prefix, or "
                "CONTEXT:UID; omit to translate the current Context"
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
            help="Materialize translated siblings in the source Context",
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
    edit: Annotated[
        bool,
        typer.Option(
            "--edit",
            help=(
                "Edit the selected same-UID translation in $EDITOR; "
                "does not change the source Memory"
            ),
        ),
    ] = False,
    set_text: Annotated[
        Optional[str],
        typer.Option(
            "--set",
            metavar="TEXT",
            help="Set the selected same-UID translation exactly",
        ),
    ] = None,
    input_file: Annotated[
        Optional[str],
        typer.Option(
            "--input",
            metavar="JSON",
            help=(
                "Import a strict source-hash-bound translation batch; "
                "use - for stdin"
            ),
        ),
    ] = None,
    export_file: Annotated[
        Optional[str],
        typer.Option(
            "--export",
            metavar="JSON",
            help="Export an editable strict translation batch; use - for stdout",
        ),
    ] = None,
    verify: Annotated[
        bool,
        typer.Option(
            "--verify",
            help="Mark the selected current translation as reviewed",
        ),
    ] = False,
    unverify: Annotated[
        bool,
        typer.Option(
            "--unverify",
            help="Mark the selected current translation as unreviewed",
        ),
    ] = False,
    reset: Annotated[
        bool,
        typer.Option(
            "--reset",
            help=(
                "Remove the selected curated layer and reveal any current "
                "provider translation"
            ),
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help=(
                "Bypass --save-as location review; accepted with --in-place "
                "for compatibility"
            ),
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    snapshot = ContextOperandSnapshot.capture(store)
    try:
        prepared = prepare_translation(
            store,
            TranslateRequest(
                target_language=target_language,
                selector=selector,
                save_as=save_as,
                in_place=in_place,
                refresh=refresh,
                edit=edit,
                set_text=set_text,
                import_source=input_file,
                export_destination=export_file,
                verify=verify,
                unverify=unverify,
                reset=reset,
                materialization_approved=yes,
            ),
            current_name=snapshot.current_name,
            provider_scope=_provider_scope,
            editor=lambda text: typer.edit(text=text),
            import_loader=_read_import_payload,
        )
        if _render_prepared_nonmaterialization(
            prepared,
            export_file=export_file,
        ):
            return
        assert prepared.kind == "MATERIALIZE"
        assert prepared.plan is not None
        destination_name = prepared.destination_name
        if prepared.reused:
            typer.secho(
                "Reusing the saved translation view; the provider was not called.",
                fg=typer.colors.CYAN,
            )
        else:
            typer.secho(
                "Saved the translation view for materialization.",
                fg=typer.colors.CYAN,
            )
        _render_preview(prepared.plan, destination_name=destination_name)
        if destination_name is not None and not yes:
            from memcommit.commands.shared.save_location_review import (
                review_save_location,
            )

            reviewed_destination = review_save_location(
                destination_name,
                validate=store.assert_context_creatable,
                apply_label="create translated Context",
            )
            if reviewed_destination is None:
                typer.echo(
                    "Aborted — the translation view remains saved; "
                    "no Context changes made."
                )
                return
            destination_name = reviewed_destination
        result = apply_translation_materialization(
            store,
            prepared.plan,
            destination_name=destination_name,
        )
    except (
        OSError,
        QueryProviderError,
        RuntimeError,
        TranslationViewError,
        TranslateError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(f"Translate error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    _render_materialization_receipt(result)
