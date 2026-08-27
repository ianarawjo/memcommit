"""Terminal-independent orchestration for every Translate view mode."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal

from memcommit.context import Context, Memory
from memcommit.context_targeting.loading import resolve_local_context_memory_target
from memcommit.context_targeting.model import ContextTarget, DirectMemoryTarget
from memcommit.operations.translate.catalog_application import (
    ParsedTranslationImport,
    build_translation_export,
    content_digest,
    load_translation_catalog_seed,
    parse_translation_import,
    save_curated_translation_catalog,
)
from memcommit.operations.translate.runtime import (
    TranslateError,
    TranslationPlan,
    TranslationProvider,
    plan_translation,
    resolve_translation_selector,
    validate_translation_target,
)
from memcommit.operations.translate.view import (
    TRANSLATION_ORIGIN_IMPORTED,
    TRANSLATION_ORIGIN_MANUAL,
    TRANSLATION_REVIEW_UNREVIEWED,
    TRANSLATION_REVIEW_VERIFIED,
    TranslationCatalog,
    TranslationViewError,
)
from memcommit.operations.translate.view_store import (
    load_translation_catalog_for_context,
    save_translation_catalog,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


TranslateResultKind = Literal[
    "CANCELLED",
    "EMPTY",
    "EXPORT",
    "IMPORT",
    "MATERIALIZE",
    "VIEW",
]
ProviderFactory = Callable[[], TranslationProvider]
ProviderFactoryScope = Callable[
    [], AbstractContextManager[ProviderFactory]
]
TranslationEditor = Callable[[str], str | None]
TranslationImportLoader = Callable[[str], tuple[bytes, str]]


@dataclass(frozen=True)
class TranslateRequest:
    """One complete Translate request independent of argv and terminal state."""

    target_language: str = "English"
    selector: str | None = None
    save_as: str | None = None
    in_place: bool = False
    refresh: bool = False
    edit: bool = False
    set_text: str | None = None
    import_source: str | None = None
    export_destination: str | None = None
    verify: bool = False
    unverify: bool = False
    reset: bool = False
    materialization_approved: bool = False


@dataclass(frozen=True)
class PreparedTranslation:
    """Typed outcome of Translate planning before optional Context Apply."""

    kind: TranslateResultKind
    context: Context
    target_language: str
    selected_memory_uid: str | None
    catalog: TranslationCatalog | None = None
    reused: bool = False
    export_payload: dict[str, object] | None = None
    changed_count: int = 0
    plan: TranslationPlan | None = None
    destination_name: str | None = None
    export_destination: str | None = None


def _sidecar_action_count(request: TranslateRequest) -> int:
    return sum(
        (
            request.edit,
            request.set_text is not None,
            request.import_source is not None,
            request.export_destination is not None,
            request.verify,
            request.unverify,
            request.reset,
        )
    )


def validate_translate_request(request: TranslateRequest) -> TranslateRequest:
    """Reject contradictory modes before Store or provider work."""

    if not isinstance(request, TranslateRequest):
        raise TypeError("Translate requires a TranslateRequest.")
    sidecar_actions = _sidecar_action_count(request)
    if sidecar_actions > 1:
        raise TranslateError(
            "Use only one of --edit, --set, --input, --export, "
            "--verify, --unverify, or --reset."
        )
    if sidecar_actions and (
        request.refresh or request.save_as is not None or request.in_place
    ):
        raise TranslateError(
            "Translation view editing/export cannot be combined with "
            "--refresh, --save-as, or --in-place."
        )
    if request.in_place and request.save_as is not None:
        raise TranslateError("--save-as and --in-place cannot be used together.")
    if request.materialization_approved and (
        request.save_as is None and not request.in_place
    ):
        raise TranslateError(
            "--yes applies only with --save-as CONTEXT or --in-place. "
            "Bare 'mem translate' saves a view without changing a Context."
        )
    return request


def _open_or_create_catalog(
    *,
    store: MemoryStore,
    context: Context,
    target_language: str,
    selected_memory_uid: str | None,
    refresh: bool,
    provider_scope: ProviderFactoryScope | None,
) -> tuple[TranslationCatalog | None, bool]:
    """Reuse effective entries or publish one provider layer with CAS."""

    seed = load_translation_catalog_seed(context, target_language)
    existing = seed.catalog if seed.logical_digest is not None else None
    if (
        existing is not None
        and existing.covers(context, selected_memory_uid)
        and not refresh
    ):
        if seed.requires_save:
            save_translation_catalog(
                store,
                existing,
                expected_record_digest=seed.expected_record_digest,
                expected_legacy_record_digest=seed.expected_legacy_record_digest,
                expected_context_digest=context_record_digest(context),
            )
        return existing, True

    if provider_scope is None:
        raise TranslateError("Translate requires a provider for this view.")
    with provider_scope() as provider_factory:
        plan = plan_translation(
            context,
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
                expected_legacy_record_digest=seed.expected_legacy_record_digest,
                expected_context_digest=context_record_digest(context),
            )
        return existing, existing is not None
    catalog = TranslationCatalog.from_plan(plan, context, existing=existing)
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=seed.expected_record_digest,
        expected_legacy_record_digest=seed.expected_legacy_record_digest,
        expected_context_digest=plan.context_digest,
    )
    return catalog, False


def _apply_import(
    *,
    store: MemoryStore,
    context: Context,
    target_language: str,
    parsed: ParsedTranslationImport,
) -> tuple[TranslationCatalog, int]:
    seed = load_translation_catalog_seed(context, target_language)
    if parsed.catalog_digest != seed.logical_digest:
        raise TranslateError(
            "Translation import was exported from a different catalog "
            "revision. Export a fresh file and retry."
        )
    catalog = seed.catalog
    candidate = catalog
    source_digests: dict[str, str] = {}
    current_effective = {
        entry.source_uid: entry
        for entry in catalog.effective_entries(context)
    }
    changed_count = 0
    for (
        source_uid,
        source_digest,
        translated_content,
        review_status,
    ) in parsed.entries:
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
            # An untouched export must retain provider/curated provenance.
            continue
        candidate = candidate.with_curated(
            context,
            source_uid,
            translated_content,
            origin=TRANSLATION_ORIGIN_IMPORTED,
            review_status=review_status,
            evidence_sha256=parsed.evidence_digest,
        )
        source_digests[source_uid] = source_digest
        changed_count += 1
    if candidate != catalog or seed.requires_save:
        save_curated_translation_catalog(
            store=store,
            context=context,
            catalog=candidate,
            seed=seed,
            source_digests=source_digests,
        )
    return candidate, changed_count


def _apply_single_curated_action(
    *,
    store: MemoryStore,
    context: Context,
    target_language: str,
    selected_memory_uid: str,
    request: TranslateRequest,
    editor: TranslationEditor | None,
) -> tuple[TranslationCatalog | None, bool]:
    seed = load_translation_catalog_seed(context, target_language)
    catalog = seed.catalog
    source_memory = context.memories[selected_memory_uid]
    assert isinstance(source_memory, Memory)
    candidate = catalog
    if request.edit or request.set_text is not None:
        existing = {
            entry.source_uid: entry
            for entry in catalog.effective_entries(context, selected_memory_uid)
        }.get(selected_memory_uid)
        exact_text = request.set_text
        if request.edit:
            if editor is None:
                raise TranslateError("Translate edit requires an editor adapter.")
            exact_text = editor(
                existing.translated_content if existing is not None else ""
            )
            if exact_text is None:
                return None, False
        assert exact_text is not None
        if not exact_text.strip():
            raise TranslateError("Translation text must be non-empty.")
        candidate = catalog.with_curated(
            context,
            selected_memory_uid,
            exact_text,
            origin=TRANSLATION_ORIGIN_MANUAL,
            review_status=TRANSLATION_REVIEW_UNREVIEWED,
        )
    elif request.verify or request.unverify:
        candidate = catalog.with_review_status(
            context,
            selected_memory_uid,
            (
                TRANSLATION_REVIEW_VERIFIED
                if request.verify
                else TRANSLATION_REVIEW_UNREVIEWED
            ),
        )
    elif request.reset:
        candidate = catalog.without_curated(context, selected_memory_uid)

    if candidate != catalog or seed.requires_save:
        save_curated_translation_catalog(
            store=store,
            context=context,
            catalog=candidate,
            seed=seed,
            source_digests={
                selected_memory_uid: content_digest(source_memory.content)
            },
        )
    return candidate, candidate == catalog


def prepare_translation(
    store: MemoryStore,
    request: TranslateRequest,
    *,
    current_name: str | None,
    provider_scope: ProviderFactoryScope | None = None,
    editor: TranslationEditor | None = None,
    import_loader: TranslationImportLoader | None = None,
) -> PreparedTranslation:
    """Execute every non-Context-mutating Translate mode and prepare Apply."""

    request = validate_translate_request(request)
    auto_target = (
        resolve_local_context_memory_target(
            store,
            request.selector,
            current=current_name,
        )
        if request.selector is not None
        else None
    )
    selected_operand: str | None = None
    if isinstance(auto_target, DirectMemoryTarget):
        source_name = auto_target.context_name
        selected_operand = auto_target.memory_uid
    elif isinstance(auto_target, ContextTarget):
        source_name = auto_target.context_name
    else:
        source_name = current_name
    if source_name is None:
        raise TranslateError(
            "No current context. Pass a Context or run 'mem init <name>' first."
        )
    context = store.load_direct(source_name)
    target_language = validate_translation_target(request.target_language)
    selected_memory_uid = resolve_translation_selector(context, selected_operand)
    materializing = request.save_as is not None or request.in_place
    if materializing and current_name != context.name:
        raise TranslateError(
            "Translation materialization requires the selected Source to be "
            "the current Context; switch to it first."
        )
    selector_required = any(
        (
            request.edit,
            request.set_text is not None,
            request.verify,
            request.unverify,
            request.reset,
        )
    )
    if selector_required and selected_memory_uid is None:
        raise TranslateError(
            "This translation action requires one direct Memory UID."
        )
    if request.import_source is not None and selected_memory_uid is not None:
        raise TranslateError(
            "--input carries exact source UIDs and cannot use a selector."
        )
    if request.save_as is not None:
        store.assert_context_creatable(request.save_as)

    if request.export_destination is not None:
        catalog, _ = load_translation_catalog_for_context(
            context,
            target_language,
        )
        return PreparedTranslation(
            kind="EXPORT",
            context=context,
            target_language=target_language,
            selected_memory_uid=selected_memory_uid,
            catalog=catalog,
            export_payload=build_translation_export(
                context,
                catalog,
                target_language=target_language,
                selector=selected_memory_uid,
            ),
            export_destination=request.export_destination,
        )

    if request.import_source is not None:
        if import_loader is None:
            raise TranslateError("Translate import requires an input adapter.")
        import_raw, import_text = import_loader(request.import_source)
        parsed = parse_translation_import(
            import_raw,
            import_text,
            context=context,
            target_language=target_language,
        )
        catalog, changed_count = _apply_import(
            store=store,
            context=context,
            target_language=target_language,
            parsed=parsed,
        )
        return PreparedTranslation(
            kind="IMPORT",
            context=context,
            target_language=target_language,
            selected_memory_uid=None,
            catalog=catalog,
            changed_count=changed_count,
        )

    if selector_required:
        assert selected_memory_uid is not None
        catalog, reused = _apply_single_curated_action(
            store=store,
            context=context,
            target_language=target_language,
            selected_memory_uid=selected_memory_uid,
            request=request,
            editor=editor,
        )
        if catalog is None:
            return PreparedTranslation(
                kind="CANCELLED",
                context=context,
                target_language=target_language,
                selected_memory_uid=selected_memory_uid,
            )
        return PreparedTranslation(
            kind="VIEW",
            context=context,
            target_language=target_language,
            selected_memory_uid=selected_memory_uid,
            catalog=catalog,
            reused=reused,
        )

    catalog, reused = _open_or_create_catalog(
        store=store,
        context=context,
        target_language=target_language,
        selected_memory_uid=selected_memory_uid,
        refresh=request.refresh,
        provider_scope=provider_scope,
    )
    if catalog is None:
        return PreparedTranslation(
            kind="EMPTY",
            context=context,
            target_language=target_language,
            selected_memory_uid=selected_memory_uid,
        )
    if not materializing:
        return PreparedTranslation(
            kind="VIEW",
            context=context,
            target_language=target_language,
            selected_memory_uid=selected_memory_uid,
            catalog=catalog,
            reused=reused,
        )

    plan = catalog.to_translation_plan(context, selected_memory_uid)
    if plan.provider_response_sha256 is None:
        raise TranslationViewError(
            "Materialization currently requires one provider-generated batch. "
            "Curated or mixed translation views remain same-UID sidecars until "
            "their provenance schema is defined."
        )
    if not isinstance(plan.operation_uid, str):
        raise TranslateError("Materialization identity was not allocated.")
    return PreparedTranslation(
        kind="MATERIALIZE",
        context=context,
        target_language=target_language,
        selected_memory_uid=selected_memory_uid,
        catalog=catalog,
        reused=reused,
        plan=plan,
        destination_name=request.save_as,
    )
