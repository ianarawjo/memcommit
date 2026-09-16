"""Strict JSON record format for Memory translation catalogs."""

from __future__ import annotations

import hashlib
import json

from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TranslationCatalogEntry,
    TranslationCatalogError,
    TranslationCuratedVariant,
    TranslationProviderVariant,
)


TRANSLATION_CATALOG_SCHEMA_VERSION = 2


def _exact_record(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise TranslationCatalogError(f"Invalid {label} record.")
    return value


def _provider_record(
    value: TranslationProviderVariant,
) -> dict[str, object]:
    return {
        "source_sha256": value.source_sha256,
        "context_digest": value.context_digest,
        "translated_content": value.translated_content,
        "response_sha256": value.response_sha256,
        "generated_at": value.generated_at,
    }


def _decode_provider_record(value: object) -> TranslationProviderVariant:
    data = _exact_record(
        value,
        {
            "source_sha256",
            "context_digest",
            "translated_content",
            "response_sha256",
            "generated_at",
        },
        "translation provider",
    )
    return TranslationProviderVariant(
        source_sha256=data["source_sha256"],  # type: ignore[arg-type]
        context_digest=data["context_digest"],  # type: ignore[arg-type]
        translated_content=data["translated_content"],  # type: ignore[arg-type]
        response_sha256=data["response_sha256"],  # type: ignore[arg-type]
        generated_at=data["generated_at"],  # type: ignore[arg-type]
    )


def _curated_record(
    value: TranslationCuratedVariant,
) -> dict[str, object]:
    return {
        "source_sha256": value.source_sha256,
        "translated_content": value.translated_content,
        "origin": value.origin,
        "review_status": value.review_status,
        "reviewed_content_sha256": value.reviewed_content_sha256,
        "evidence_sha256": value.evidence_sha256,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
    }


def _decode_curated_record(value: object) -> TranslationCuratedVariant:
    data = _exact_record(
        value,
        {
            "source_sha256",
            "translated_content",
            "origin",
            "review_status",
            "reviewed_content_sha256",
            "evidence_sha256",
            "created_at",
            "updated_at",
        },
        "translation curated",
    )
    return TranslationCuratedVariant(
        source_sha256=data["source_sha256"],  # type: ignore[arg-type]
        translated_content=data["translated_content"],  # type: ignore[arg-type]
        origin=data["origin"],  # type: ignore[arg-type]
        review_status=data["review_status"],  # type: ignore[arg-type]
        reviewed_content_sha256=data["reviewed_content_sha256"],  # type: ignore[arg-type]
        evidence_sha256=data["evidence_sha256"],  # type: ignore[arg-type]
        created_at=data["created_at"],  # type: ignore[arg-type]
        updated_at=data["updated_at"],  # type: ignore[arg-type]
    )


def _entry_record(value: TranslationCatalogEntry) -> dict[str, object]:
    return {
        "source_uid": value.source_uid,
        "provider": (
            None if value.provider is None else _provider_record(value.provider)
        ),
        "curated": (None if value.curated is None else _curated_record(value.curated)),
    }


def _decode_entry_record(value: object) -> TranslationCatalogEntry:
    data = _exact_record(
        value,
        {"source_uid", "provider", "curated"},
        "translation catalog entry",
    )
    return TranslationCatalogEntry(
        source_uid=data["source_uid"],  # type: ignore[arg-type]
        provider=(
            None
            if data["provider"] is None
            else _decode_provider_record(data["provider"])
        ),
        curated=(
            None if data["curated"] is None else _decode_curated_record(data["curated"])
        ),
    )


def encode_translation_catalog_record(
    catalog: MemoryTranslationCatalog,
) -> dict[str, object]:
    """Encode one validated catalog into its complete durable record."""
    if not isinstance(catalog, MemoryTranslationCatalog):
        raise TypeError("Expected a MemoryTranslationCatalog.")
    return {
        "schema_version": TRANSLATION_CATALOG_SCHEMA_VERSION,
        "context_uid": catalog.context_uid,
        "context_name": catalog.context_name,
        "target_language": catalog.target_language,
        "created_at": catalog.created_at,
        "updated_at": catalog.updated_at,
        "revision": catalog.revision,
        "contract_version": catalog.contract_version,
        "entries": [_entry_record(entry) for entry in catalog.entries],
    }


def decode_translation_catalog_record(
    value: object,
) -> MemoryTranslationCatalog:
    """Decode one exact durable record into the core catalog model."""
    data = _exact_record(
        value,
        {
            "schema_version",
            "context_uid",
            "context_name",
            "target_language",
            "created_at",
            "updated_at",
            "revision",
            "contract_version",
            "entries",
        },
        "translation catalog",
    )
    if type(data["schema_version"]) is not int or (
        data["schema_version"] != TRANSLATION_CATALOG_SCHEMA_VERSION
    ):
        raise TranslationCatalogError("Unsupported translation catalog schema version.")
    raw_entries = data["entries"]
    if not isinstance(raw_entries, list):
        raise TranslationCatalogError("Invalid translation catalog entries.")
    return MemoryTranslationCatalog(
        context_uid=data["context_uid"],  # type: ignore[arg-type]
        context_name=data["context_name"],  # type: ignore[arg-type]
        target_language=data["target_language"],  # type: ignore[arg-type]
        created_at=data["created_at"],  # type: ignore[arg-type]
        updated_at=data["updated_at"],  # type: ignore[arg-type]
        revision=data["revision"],  # type: ignore[arg-type]
        contract_version=data["contract_version"],  # type: ignore[arg-type]
        entries=tuple(_decode_entry_record(entry) for entry in raw_entries),
    )


def translation_catalog_record_digest(
    value: MemoryTranslationCatalog | dict[str, object],
) -> str:
    """Hash one validated record canonically for compare-and-swap."""
    record = (
        encode_translation_catalog_record(value)
        if isinstance(value, MemoryTranslationCatalog)
        else encode_translation_catalog_record(decode_translation_catalog_record(value))
    )
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
