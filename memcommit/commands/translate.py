"""CLI boundary for same-UID translation views and materialization."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.command_progress import progressing_provider_factory
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
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
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore, context_record_digest
from memcommit.translate import (
    TranslateError,
    TranslationPlan,
    resolve_translation_selector,
    translation_plan_matches_context,
    validate_translation_target,
)
from memcommit.translation_view import (
    TRANSLATION_ORIGIN_IMPORTED,
    TRANSLATION_ORIGIN_MANUAL,
    TRANSLATION_REVIEW_UNREVIEWED,
    TRANSLATION_REVIEW_VERIFIED,
    TranslationCatalog,
    TranslationViewError,
    translation_catalog_record_digest,
)
from memcommit.translation_view_store import (
    ConcurrentTranslationViewUpdateError,
    load_translation_catalog_for_context,
    save_translation_catalog,
)


_TRANSLATION_IMPORT_SCHEMA_VERSION = 2
_TRANSLATION_IMPORT_SIZE_LIMIT = 5_000_000


@dataclass(frozen=True)
class _CatalogSeed:
    catalog: TranslationCatalog
    logical_digest: str | None
    expected_record_digest: str | None
    expected_legacy_record_digest: str | None
    requires_save: bool


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TranslateError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


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
    ctx: Context,
    catalog: TranslationCatalog,
    *,
    selector: str | None,
    reused: bool,
) -> None:
    """Render current same-UID representations and explicit review state."""
    effective = catalog.effective_entries(ctx, selector)
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
    for item in ctx.iter_items():
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
                safe_terminal_text(entry.translated_content).splitlines()
                or [""]
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
            label = source_object_label(facts)
            typer.echo(
                f"[{label} {item.uid[:8]}] "
                f"{safe_terminal_text(item.target_context_name)}"
                f"#{item.target_memory_uid[:8]} · "
                f"{source_annotation_text(facts)} (not translated)"
            )
    typer.echo("─" * 64)
    stale = catalog.stale_curated_uids(ctx)
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
        typer.secho(
            "Saved translation view.",
            fg=typer.colors.GREEN,
            bold=True,
        )
    typer.echo(
        "No Context or Memory changes; source Memory UIDs remain the anchors."
    )


def _open_or_create_catalog(
    *,
    store: MemoryStore,
    ctx: Context,
    target_language: str,
    selected_memory_uid: str | None,
    refresh: bool,
) -> tuple[TranslationCatalog | None, bool]:
    """Reuse effective entries or publish one provider layer with CAS."""
    seed = _catalog_seed(ctx, target_language)
    existing = seed.catalog if seed.logical_digest is not None else None
    if (
        existing is not None
        and existing.covers(ctx, selected_memory_uid)
        and not refresh
    ):
        if seed.requires_save:
            save_translation_catalog(
                store,
                existing,
                expected_record_digest=seed.expected_record_digest,
                expected_legacy_record_digest=(
                    seed.expected_legacy_record_digest
                ),
                expected_context_digest=context_record_digest(ctx),
            )
        return existing, True

    with progressing_provider_factory(
        "TRANSLATE",
        "translating memories",
        connect_codex_chatgpt_provider,
    ) as provider_factory:
        plan = ops.translate(
            ctx,
            target_language,
            provider_factory,
            selector=selected_memory_uid,
            allocate_operation_uid=False,
        )
    if not plan.proposals:
        if existing is not None and seed.requires_save:
            save_translation_catalog(
                store,
                existing,
                expected_record_digest=seed.expected_record_digest,
                expected_legacy_record_digest=(
                    seed.expected_legacy_record_digest
                ),
                expected_context_digest=context_record_digest(ctx),
            )
        return existing, existing is not None
    catalog = TranslationCatalog.from_plan(
        plan,
        ctx,
        existing=existing,
    )
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=seed.expected_record_digest,
        expected_legacy_record_digest=seed.expected_legacy_record_digest,
        expected_context_digest=plan.context_digest,
    )
    return catalog, False


def _catalog_seed(
    ctx: Context,
    target_language: str,
) -> _CatalogSeed:
    existing, migrated_from_v1 = load_translation_catalog_for_context(
        ctx,
        target_language,
    )
    if existing is None:
        return _CatalogSeed(
            catalog=TranslationCatalog.empty(ctx, target_language),
            logical_digest=None,
            expected_record_digest=None,
            expected_legacy_record_digest=None,
            requires_save=False,
        )
    logical_digest = translation_catalog_record_digest(existing)
    pruned = existing.without_removed_sources(ctx)
    return _CatalogSeed(
        catalog=pruned,
        logical_digest=logical_digest,
        expected_record_digest=(None if migrated_from_v1 else logical_digest),
        expected_legacy_record_digest=(
            logical_digest if migrated_from_v1 else None
        ),
        requires_save=migrated_from_v1 or pruned != existing,
    )


def _save_curated_catalog(
    *,
    store: MemoryStore,
    ctx: Context,
    catalog: TranslationCatalog,
    expected_record_digest: str | None,
    expected_legacy_record_digest: str | None,
    source_digests: dict[str, str],
    expected_context_digest: str | None = None,
) -> None:
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=expected_record_digest,
        expected_legacy_record_digest=expected_legacy_record_digest,
        expected_context_digest=expected_context_digest,
        required_source_digests=source_digests,
    )


def _read_import_payload(source: str) -> tuple[bytes, str]:
    if source == "-":
        raw = sys.stdin.buffer.read(_TRANSLATION_IMPORT_SIZE_LIMIT + 1)
        label = "stdin"
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file():
            raise TranslateError("Translation import must be a regular file.")
        if path.stat().st_size > _TRANSLATION_IMPORT_SIZE_LIMIT:
            raise TranslateError("Translation import is too large.")
        raw = path.read_bytes()
        label = str(path)
    if len(raw) > _TRANSLATION_IMPORT_SIZE_LIMIT:
        raise TranslateError("Translation import is too large.")
    try:
        return raw, raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TranslateError(
            f"Translation import {label!r} must be UTF-8 JSON."
        ) from error


def _parse_import_payload(
    raw: bytes,
    text: str,
    *,
    ctx: Context,
    target_language: str,
) -> tuple[
    tuple[tuple[str, str, str, str], ...],
    str,
    str | None,
]:
    try:
        value = json.loads(text, object_pairs_hook=_strict_json_object)
    except (json.JSONDecodeError, TranslateError) as error:
        raise TranslateError("Translation import is invalid JSON.") from error
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "catalog_digest",
        "context_uid",
        "context_name",
        "target_language",
        "translations",
    }:
        raise TranslateError("Translation import has an invalid top-level schema.")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != _TRANSLATION_IMPORT_SCHEMA_VERSION
    ):
        raise TranslateError("Unsupported translation import schema version.")
    catalog_digest = value["catalog_digest"]
    if catalog_digest is not None and (
        not isinstance(catalog_digest, str)
        or len(catalog_digest) != 64
        or any(c not in "0123456789abcdef" for c in catalog_digest)
    ):
        raise TranslateError("Translation import catalog digest is invalid.")
    if (
        value["context_uid"] != ctx.uid
        or value["context_name"] != ctx.name
        or value["target_language"] != target_language
    ):
        raise TranslateError(
            "Translation import does not match the current Context and target."
        )
    translations = value["translations"]
    if not isinstance(translations, list) or not translations:
        raise TranslateError("Translation import contains no translations.")
    parsed: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for record in translations:
        if not isinstance(record, dict) or set(record) != {
            "source_uid",
            "source_sha256",
            "translated_content",
            "review_status",
        }:
            raise TranslateError("Translation import entry has an invalid schema.")
        source_uid = record["source_uid"]
        source_sha256 = record["source_sha256"]
        translated_content = record["translated_content"]
        review_status = record["review_status"]
        if (
            not isinstance(source_uid, str)
            or source_uid in seen
            or not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(c not in "0123456789abcdef" for c in source_sha256)
            or not isinstance(translated_content, str)
            or not isinstance(review_status, str)
            or review_status not in {
                TRANSLATION_REVIEW_UNREVIEWED,
                TRANSLATION_REVIEW_VERIFIED,
            }
            or (
                not translated_content.strip()
                and review_status != TRANSLATION_REVIEW_UNREVIEWED
            )
        ):
            raise TranslateError("Translation import entry is invalid.")
        source_memory = ctx.memories.get(source_uid)
        if (
            not isinstance(source_memory, Memory)
            or _content_digest(source_memory.content) != source_sha256
        ):
            raise TranslateError(
                "Translation import source UID or source digest is stale."
            )
        seen.add(source_uid)
        parsed.append(
            (
                source_uid,
                source_sha256,
                translated_content,
                review_status,
            )
        )
    return (
        tuple(parsed),
        hashlib.sha256(raw).hexdigest(),
        catalog_digest,
    )


def _export_payload(
    ctx: Context,
    catalog: TranslationCatalog | None,
    *,
    target_language: str,
    selector: str | None,
) -> dict[str, object]:
    effective = (
        {}
        if catalog is None
        else {
            entry.source_uid: entry
            for entry in catalog.effective_entries(ctx, selector)
        }
    )
    memories = tuple(
        item
        for item in ctx.iter_items()
        if isinstance(item, Memory)
        and (selector is None or item.uid == selector)
    )
    return {
        "schema_version": _TRANSLATION_IMPORT_SCHEMA_VERSION,
        "catalog_digest": (
            translation_catalog_record_digest(catalog)
            if catalog is not None
            else None
        ),
        "context_uid": ctx.uid,
        "context_name": ctx.name,
        "target_language": target_language,
        "translations": [
            {
                "source_uid": memory.uid,
                "source_sha256": _content_digest(memory.content),
                "translated_content": (
                    effective[memory.uid].translated_content
                    if memory.uid in effective
                    else ""
                ),
                "review_status": (
                    effective[memory.uid].review_status
                    if memory.uid in effective
                    else TRANSLATION_REVIEW_UNREVIEWED
                ),
            }
            for memory in memories
        ],
    }


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
        raise TranslateError(
            f"Could not write translation export: {error}"
        ) from error


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
            help=(
                "Export an editable strict translation batch; use - for stdout"
            ),
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
                "Apply an explicit --save-as or --in-place materialization "
                "without confirmation"
            ),
        ),
    ] = False,
) -> None:
    store = MemoryStore()
    try:
        sidecar_actions = sum(
            (
                edit,
                set_text is not None,
                input_file is not None,
                export_file is not None,
                verify,
                unverify,
                reset,
            )
        )
        if sidecar_actions > 1:
            raise TranslateError(
                "Use only one of --edit, --set, --input, --export, "
                "--verify, --unverify, or --reset."
            )
        if sidecar_actions and (refresh or save_as is not None or in_place):
            raise TranslateError(
                "Translation view editing/export cannot be combined with "
                "--refresh, --save-as, or --in-place."
            )
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
        selector_required = any(
            (edit, set_text is not None, verify, unverify, reset)
        )
        if selector_required and selected_memory_uid is None:
            raise TranslateError(
                "This translation action requires one direct Memory UID."
            )
        if input_file is not None and selector is not None:
            raise TranslateError(
                "--input carries exact source UIDs and cannot use a selector."
            )
        destination_name = save_as
        if destination_name is not None:
            store.assert_context_creatable(destination_name)

        if export_file is not None:
            catalog, _ = load_translation_catalog_for_context(
                direct_ctx,
                language,
            )
            payload = _export_payload(
                direct_ctx,
                catalog,
                target_language=language,
                selector=selected_memory_uid,
            )
            _write_export_payload(export_file, payload)
            if export_file != "-":
                typer.secho(
                    f"Exported {len(payload['translations'])} translation "
                    f"{'entry' if len(payload['translations']) == 1 else 'entries'} "
                    f"to '{safe_terminal_text(export_file)}'.",
                    fg=typer.colors.GREEN,
                )
            return

        if input_file is not None:
            raw, text = _read_import_payload(input_file)
            parsed, evidence_digest, payload_catalog_digest = (
                _parse_import_payload(
                raw,
                text,
                ctx=direct_ctx,
                target_language=language,
                )
            )
            seed = _catalog_seed(
                direct_ctx,
                language,
            )
            if payload_catalog_digest != seed.logical_digest:
                raise TranslateError(
                    "Translation import was exported from a different "
                    "catalog revision. Export a fresh file and retry."
                )
            catalog = seed.catalog
            candidate = catalog
            source_digests: dict[str, str] = {}
            current_effective = {
                entry.source_uid: entry
                for entry in catalog.effective_entries(direct_ctx)
            }
            changed_count = 0
            for (
                source_uid,
                source_digest,
                translated_content,
                review_status,
            ) in parsed:
                current = current_effective.get(source_uid)
                if not translated_content.strip():
                    if current is not None:
                        raise TranslateError(
                            "Blank imported text cannot delete an existing "
                            "translation; use --reset for one exact UID."
                        )
                    continue
                if (
                    current is not None
                    and current.translated_content == translated_content
                    and current.review_status == review_status
                ):
                    # Round-tripping an untouched export must not convert a
                    # provider result into a curated imported override.
                    continue
                candidate = candidate.with_curated(
                    direct_ctx,
                    source_uid,
                    translated_content,
                    origin=TRANSLATION_ORIGIN_IMPORTED,
                    review_status=review_status,
                    evidence_sha256=evidence_digest,
                )
                source_digests[source_uid] = source_digest
                changed_count += 1
            if candidate != catalog or seed.requires_save:
                _save_curated_catalog(
                    store=store,
                    ctx=direct_ctx,
                    catalog=candidate,
                    expected_record_digest=seed.expected_record_digest,
                    expected_legacy_record_digest=(
                        seed.expected_legacy_record_digest
                    ),
                    source_digests=source_digests,
                    expected_context_digest=(
                        context_record_digest(direct_ctx)
                        if seed.requires_save
                        else None
                    ),
                )
            typer.secho(
                f"Imported {changed_count} changed same-UID translation "
                f"{'entry' if changed_count == 1 else 'entries'}; "
                "untouched rows preserved their provenance.",
                fg=typer.colors.GREEN,
                bold=True,
            )
            _render_catalog(
                direct_ctx,
                candidate,
                selector=None,
                reused=False,
            )
            return

        if selector_required:
            assert selected_memory_uid is not None
            seed = _catalog_seed(
                direct_ctx,
                language,
            )
            catalog = seed.catalog
            source_memory = direct_ctx.memories[selected_memory_uid]
            assert isinstance(source_memory, Memory)
            candidate = catalog
            if edit or set_text is not None:
                existing = {
                    entry.source_uid: entry
                    for entry in catalog.effective_entries(
                        direct_ctx,
                        selected_memory_uid,
                    )
                }.get(selected_memory_uid)
                exact_text = set_text
                if edit:
                    exact_text = typer.edit(
                        text=(
                            existing.translated_content
                            if existing is not None
                            else ""
                        )
                    )
                    if exact_text is None:
                        typer.echo("Translation edit cancelled.")
                        return
                assert exact_text is not None
                if not exact_text.strip():
                    raise TranslateError("Translation text must be non-empty.")
                candidate = catalog.with_curated(
                    direct_ctx,
                    selected_memory_uid,
                    exact_text,
                    origin=TRANSLATION_ORIGIN_MANUAL,
                    review_status=TRANSLATION_REVIEW_UNREVIEWED,
                )
            elif verify or unverify:
                candidate = catalog.with_review_status(
                    direct_ctx,
                    selected_memory_uid,
                    (
                        TRANSLATION_REVIEW_VERIFIED
                        if verify
                        else TRANSLATION_REVIEW_UNREVIEWED
                    ),
                )
            elif reset:
                candidate = catalog.without_curated(
                    direct_ctx,
                    selected_memory_uid,
                )
            if candidate != catalog or seed.requires_save:
                _save_curated_catalog(
                    store=store,
                    ctx=direct_ctx,
                    catalog=candidate,
                    expected_record_digest=seed.expected_record_digest,
                    expected_legacy_record_digest=(
                        seed.expected_legacy_record_digest
                    ),
                    source_digests={
                        selected_memory_uid: _content_digest(
                            source_memory.content
                        )
                    },
                    expected_context_digest=(
                        context_record_digest(direct_ctx)
                        if seed.requires_save
                        else None
                    ),
                )
            _render_catalog(
                direct_ctx,
                candidate,
                selector=selected_memory_uid,
                reused=(candidate == catalog),
            )
            return

        catalog, reused = _open_or_create_catalog(
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

    if catalog is None:
        typer.echo(
            f"Context '{direct_ctx.name}' has no directly owned Memories "
            "to translate."
        )
        return

    if destination_name is None and not in_place:
        _render_catalog(
            direct_ctx,
            catalog,
            selector=selected_memory_uid,
            reused=reused,
        )
        return

    try:
        plan = catalog.to_translation_plan(
            direct_ctx,
            selected_memory_uid,
        )
        if plan.provider_response_sha256 is None:
            raise TranslationViewError(
                "Materialization currently requires one provider-generated "
                "batch. Curated or mixed translation views remain same-UID "
                "sidecars until their provenance schema is defined."
            )
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
    if not yes:
        if destination_name is None:
            confirmation = (
                f"Add {len(plan.proposals)} translated "
                f"{'copy' if len(plan.proposals) == 1 else 'copies'}?"
            )
            approved = typer.confirm(confirmation, default=False)
        else:
            from memcommit.commands.save_location_review import (
                review_save_location,
            )

            reviewed_destination = review_save_location(
                destination_name,
                validate=store.assert_context_creatable,
                apply_label="create translated Context",
            )
            approved = reviewed_destination is not None
            if reviewed_destination is not None:
                destination_name = reviewed_destination
        if not approved:
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
                store.create_context_with_sources(
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
                    source_bindings=(
                        (
                            plan.context_name,
                            plan.context_uid,
                            plan.context_digest,
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
