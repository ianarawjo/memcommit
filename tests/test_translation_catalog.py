"""Core meaning and persistence contracts for Memory translation catalogs."""

from __future__ import annotations

import hashlib
import json

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.translate.provider_catalog import (
    update_catalog_from_translation_plan,
)
from memcommit.application.operations.translate.runtime import plan_translation
from memcommit.core.context import AutoCheckpoint, Context
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TRANSLATION_ORIGIN_MANUAL,
    TRANSLATION_REVIEW_UNREVIEWED,
    TRANSLATION_REVIEW_VERIFIED,
    TranslationCatalogError,
)
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.persistence.store.translation_catalog import (
    ConcurrentTranslationCatalogUpdateError,
    decode_translation_catalog_record,
    encode_translation_catalog_record,
    load_translation_catalog,
    save_translation_catalog,
    translation_catalog_record_digest,
)


class PayloadProvider:
    """Return deterministic translations for one strict provider payload."""

    def __init__(self, prefix: str = "EN: "):
        self.prefix = prefix

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split("TRANSLATE PAYLOAD:\n", 1)[1])
        return json.dumps(
            {
                "translations": [
                    {
                        "candidate_id": item["candidate_id"],
                        "translated_content": f"{self.prefix}{item['content']}",
                    }
                    for item in payload["memories"]
                ]
            },
            ensure_ascii=False,
        )


def _saved_context(
    store: MemoryStore,
    name: str = "translation-catalog-test",
    contents: tuple[str, ...] = ("첫 번째", "두 번째"),
) -> Context:
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": name},
            description=f"Initialized '{name}' for translation catalog test",
        ),
    )
    store.set_current(name)
    return context


def _catalog_plan(
    context: Context,
    prefix: str,
    *,
    selector: str | None = None,
):
    return plan_translation(
        context,
        "ko",
        lambda: PayloadProvider(prefix=prefix),
        selector=selector,
        allocate_operation_uid=False,
    )


def _provider_catalog(
    context: Context,
    prefix: str,
    *,
    existing: MemoryTranslationCatalog | None = None,
    created_at: str,
) -> MemoryTranslationCatalog:
    return update_catalog_from_translation_plan(
        _catalog_plan(context, prefix),
        context,
        existing=existing,
        created_at=created_at,
    )


def test_provider_refresh_preserves_curated_override_and_codec_round_trip(
    isolated_store,
):
    source = _saved_context(MemoryStore(), contents=("English A", "English B"))
    first_uid, second_uid = source.ordered_uids()
    initial = _provider_catalog(
        source,
        "OLD: ",
        created_at="2026-01-01T00:00:00+00:00",
    )
    curated = initial.with_curated(
        source,
        first_uid,
        "검수한 A",
        origin=TRANSLATION_ORIGIN_MANUAL,
        review_status=TRANSLATION_REVIEW_VERIFIED,
        updated_at="2026-01-02T00:00:00+00:00",
    )

    refreshed = _provider_catalog(
        source,
        "NEW: ",
        existing=curated,
        created_at="2026-01-03T00:00:00+00:00",
    )

    effective = {
        entry.source_uid: entry
        for entry in refreshed.effective_entries(
            source,
            context_record_digest(source),
        )
    }
    assert effective[first_uid].translated_content == "검수한 A"
    assert effective[first_uid].curated is True
    assert effective[first_uid].review_status == TRANSLATION_REVIEW_VERIFIED
    assert effective[second_uid].translated_content == "NEW: English B"
    assert effective[second_uid].curated is False
    first_record = refreshed.entry_for(first_uid)
    assert first_record is not None and first_record.provider is not None
    assert first_record.provider.translated_content == "NEW: English A"
    record = encode_translation_catalog_record(refreshed)
    assert decode_translation_catalog_record(record) == refreshed


def test_empty_catalog_accepts_first_curated_translation_without_provider(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    source_uid = source.ordered_uids()[0]
    catalog = MemoryTranslationCatalog.empty(
        source,
        "ko",
        created_at="2026-01-01T00:00:00+00:00",
    ).with_curated(
        source,
        source_uid,
        "한국어",
        origin=TRANSLATION_ORIGIN_MANUAL,
        review_status=TRANSLATION_REVIEW_VERIFIED,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    source_digest = hashlib.sha256(b"English").hexdigest()

    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=None,
        required_source_digests={source_uid: source_digest},
    )

    loaded = load_translation_catalog(source.uid, "ko")
    assert loaded == catalog
    assert loaded is not None
    effective = loaded.effective_entries(source, context_record_digest(source))
    assert len(effective) == 1
    assert effective[0].translated_content == "한국어"
    assert effective[0].curated is True


def test_source_edit_retains_stale_curated_and_uses_new_provider(isolated_store):
    source = _saved_context(MemoryStore(), contents=("English",))
    source_uid = source.ordered_uids()[0]
    catalog = _provider_catalog(
        source,
        "OLD: ",
        created_at="2026-01-01T00:00:00+00:00",
    ).with_curated(
        source,
        source_uid,
        "검수 번역",
        origin=TRANSLATION_ORIGIN_MANUAL,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    ops.edit(source, source_uid, "Changed English")

    refreshed = _provider_catalog(
        source,
        "NEW: ",
        existing=catalog,
        created_at="2026-01-03T00:00:00+00:00",
    )

    entry = refreshed.entry_for(source_uid)
    assert entry is not None and entry.curated is not None
    assert entry.curated.translated_content == "검수 번역"
    assert refreshed.stale_curated_uids(source) == (source_uid,)
    effective = refreshed.effective_entries(
        source,
        context_record_digest(source),
    )
    assert effective[0].translated_content == "NEW: Changed English"
    assert effective[0].curated is False


def test_verify_freezes_provider_and_reset_exposes_latest_provider(isolated_store):
    source = _saved_context(MemoryStore(), contents=("English",))
    source_uid = source.ordered_uids()[0]
    generated = _provider_catalog(
        source,
        "FIRST: ",
        created_at="2026-01-01T00:00:00+00:00",
    )
    digest = context_record_digest(source)
    verified = generated.with_review_status(
        source,
        digest,
        source_uid,
        TRANSLATION_REVIEW_VERIFIED,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    refreshed = _provider_catalog(
        source,
        "SECOND: ",
        existing=verified,
        created_at="2026-01-03T00:00:00+00:00",
    )
    effective = refreshed.effective_entries(source, digest)[0]
    assert effective.translated_content == "FIRST: English"
    assert effective.review_status == TRANSLATION_REVIEW_VERIFIED

    reset = refreshed.without_curated(
        source,
        source_uid,
        updated_at="2026-01-04T00:00:00+00:00",
    )
    effective = reset.effective_entries(source, digest)[0]
    assert effective.translated_content == "SECOND: English"
    assert effective.review_status == TRANSLATION_REVIEW_UNREVIEWED
    assert effective.curated is False


def test_catalog_prunes_entries_for_removed_source_uids(isolated_store):
    source = _saved_context(MemoryStore(), contents=("English",))
    source_uid = source.ordered_uids()[0]
    catalog = _provider_catalog(
        source,
        "KO: ",
        created_at="2026-01-01T00:00:00+00:00",
    )
    ops.remove(source, source_uid)

    pruned = catalog.without_removed_sources(source)

    assert pruned.entry_for(source_uid) is None


def test_catalog_cas_allows_unrelated_context_change_for_curated_source(
    isolated_store,
):
    store = MemoryStore()
    source = _saved_context(store, contents=("English A", "English B"))
    first_uid = source.ordered_uids()[0]
    catalog = _provider_catalog(
        source,
        "KO: ",
        created_at="2026-01-01T00:00:00+00:00",
    )
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=None,
        expected_context_digest=context_record_digest(source),
    )
    original_digest = translation_catalog_record_digest(catalog)

    concurrent = store.load_for_update(source.name)
    ops.add(concurrent, "Unrelated new Memory")
    store.save(concurrent)
    edited = catalog.with_curated(
        source,
        first_uid,
        "수동 번역",
        origin=TRANSLATION_ORIGIN_MANUAL,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    save_translation_catalog(
        store,
        edited,
        expected_record_digest=original_digest,
        required_source_digests={first_uid: hashlib.sha256(b"English A").hexdigest()},
    )

    assert load_translation_catalog(source.uid, "ko") == edited
    with pytest.raises(
        ConcurrentTranslationCatalogUpdateError,
        match="catalog changed",
    ):
        save_translation_catalog(
            store,
            catalog,
            expected_record_digest=original_digest,
        )


def test_curated_save_rejects_an_unrelated_removed_catalog_source(isolated_store):
    store = MemoryStore()
    source = _saved_context(store, contents=("English A", "English B"))
    first_uid, second_uid = source.ordered_uids()
    catalog = _provider_catalog(
        source,
        "KO: ",
        created_at="2026-01-01T00:00:00+00:00",
    )
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=None,
        expected_context_digest=context_record_digest(source),
    )
    edited = catalog.with_curated(
        source,
        first_uid,
        "수동 A",
        origin=TRANSLATION_ORIGIN_MANUAL,
        updated_at="2026-01-02T00:00:00+00:00",
    )
    concurrent = store.load_for_update(source.name)
    ops.remove(concurrent, second_uid)
    store.save(concurrent)

    with pytest.raises(
        ConcurrentTranslationCatalogUpdateError,
        match="source Memory was removed",
    ):
        save_translation_catalog(
            store,
            edited,
            expected_record_digest=translation_catalog_record_digest(catalog),
            required_source_digests={
                first_uid: hashlib.sha256(b"English A").hexdigest()
            },
        )
    assert load_translation_catalog(source.uid, "ko") == catalog


@pytest.mark.parametrize("schema_version", [1, 1.0, 2.0, True])
def test_catalog_record_rejects_non_v2_integer_schema(
    isolated_store,
    schema_version,
):
    source = _saved_context(MemoryStore(), contents=("English",))
    catalog = _provider_catalog(
        source,
        "KO: ",
        created_at="2026-01-01T00:00:00+00:00",
    )
    record = encode_translation_catalog_record(catalog)
    record["schema_version"] = schema_version

    with pytest.raises(TranslationCatalogError, match="schema version"):
        decode_translation_catalog_record(record)


def test_provider_save_rejects_concurrent_source_frame_change(isolated_store):
    store = MemoryStore()
    source = _saved_context(store, contents=("English",))
    catalog = _provider_catalog(
        source,
        "KO: ",
        created_at="2026-01-01T00:00:00+00:00",
    )
    concurrent = store.load_for_update(source.name)
    ops.add(concurrent, "Changed during provider call")
    store.save(concurrent)

    with pytest.raises(
        ConcurrentTranslationCatalogUpdateError,
        match="Context changed",
    ):
        save_translation_catalog(
            store,
            catalog,
            expected_record_digest=None,
            expected_context_digest=context_record_digest(source),
        )
    assert load_translation_catalog(source.uid, "ko") is None
