"""Typed catalog import, export, and curation support for Translate."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from memcommit.core.context import Context, Memory
from memcommit.application.operations.translate.runtime import TranslateError
from memcommit.application.operations.translate.view import (
    TRANSLATION_REVIEW_UNREVIEWED,
    TRANSLATION_REVIEW_VERIFIED,
    TranslationCatalog,
    translation_catalog_record_digest,
)
from memcommit.application.operations.translate.view_store import (
    load_translation_catalog_for_context,
    save_translation_catalog,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


TRANSLATION_IMPORT_SCHEMA_VERSION = 2
TRANSLATION_IMPORT_SIZE_LIMIT = 5_000_000


@dataclass(frozen=True)
class TranslationCatalogSeed:
    """Current logical catalog plus exact legacy/current CAS expectations."""

    catalog: TranslationCatalog
    logical_digest: str | None
    expected_record_digest: str | None
    expected_legacy_record_digest: str | None
    requires_save: bool


@dataclass(frozen=True)
class ParsedTranslationImport:
    """One complete source-bound imported translation batch."""

    entries: tuple[tuple[str, str, str, str], ...]
    evidence_digest: str
    catalog_digest: str | None


def content_digest(content: str) -> str:
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


def load_translation_catalog_seed(
    context: Context,
    target_language: str,
) -> TranslationCatalogSeed:
    """Load, consolidate, and prune one catalog without publishing it."""

    existing, migrated_from_v1 = load_translation_catalog_for_context(
        context,
        target_language,
    )
    if existing is None:
        return TranslationCatalogSeed(
            catalog=TranslationCatalog.empty(context, target_language),
            logical_digest=None,
            expected_record_digest=None,
            expected_legacy_record_digest=None,
            requires_save=False,
        )
    logical_digest = translation_catalog_record_digest(existing)
    pruned = existing.without_removed_sources(context)
    return TranslationCatalogSeed(
        catalog=pruned,
        logical_digest=logical_digest,
        expected_record_digest=(None if migrated_from_v1 else logical_digest),
        expected_legacy_record_digest=(
            logical_digest if migrated_from_v1 else None
        ),
        requires_save=migrated_from_v1 or pruned != existing,
    )


def save_curated_translation_catalog(
    *,
    store: MemoryStore,
    context: Context,
    catalog: TranslationCatalog,
    seed: TranslationCatalogSeed,
    source_digests: dict[str, str],
) -> None:
    """Publish one curated candidate against its exact source and slot seed."""

    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=seed.expected_record_digest,
        expected_legacy_record_digest=seed.expected_legacy_record_digest,
        expected_context_digest=(
            context_record_digest(context) if seed.requires_save else None
        ),
        required_source_digests=source_digests,
    )


def parse_translation_import(
    raw: bytes,
    text: str,
    *,
    context: Context,
    target_language: str,
) -> ParsedTranslationImport:
    """Validate one strict source-digest-bound import without publication."""

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
        or value["schema_version"] != TRANSLATION_IMPORT_SCHEMA_VERSION
    ):
        raise TranslateError("Unsupported translation import schema version.")
    catalog_digest = value["catalog_digest"]
    if catalog_digest is not None and (
        not isinstance(catalog_digest, str)
        or len(catalog_digest) != 64
        or any(character not in "0123456789abcdef" for character in catalog_digest)
    ):
        raise TranslateError("Translation import catalog digest is invalid.")
    if (
        value["context_uid"] != context.uid
        or value["context_name"] != context.name
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
            or any(
                character not in "0123456789abcdef"
                for character in source_sha256
            )
            or not isinstance(translated_content, str)
            or not isinstance(review_status, str)
            or review_status
            not in {
                TRANSLATION_REVIEW_UNREVIEWED,
                TRANSLATION_REVIEW_VERIFIED,
            }
            or (
                not translated_content.strip()
                and review_status != TRANSLATION_REVIEW_UNREVIEWED
            )
        ):
            raise TranslateError("Translation import entry is invalid.")
        source_memory = context.memories.get(source_uid)
        if (
            not isinstance(source_memory, Memory)
            or content_digest(source_memory.content) != source_sha256
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
    return ParsedTranslationImport(
        entries=tuple(parsed),
        evidence_digest=hashlib.sha256(raw).hexdigest(),
        catalog_digest=catalog_digest,
    )


def build_translation_export(
    context: Context,
    catalog: TranslationCatalog | None,
    *,
    target_language: str,
    selector: str | None,
) -> dict[str, object]:
    """Build the strict editable batch for one exact catalog revision."""

    effective = (
        {}
        if catalog is None
        else {
            entry.source_uid: entry
            for entry in catalog.effective_entries(context, selector)
        }
    )
    memories = tuple(
        item
        for item in context.iter_items()
        if isinstance(item, Memory)
        and (selector is None or item.uid == selector)
    )
    return {
        "schema_version": TRANSLATION_IMPORT_SCHEMA_VERSION,
        "catalog_digest": (
            translation_catalog_record_digest(catalog)
            if catalog is not None
            else None
        ),
        "context_uid": context.uid,
        "context_name": context.name,
        "target_language": target_language,
        "translations": [
            {
                "source_uid": memory.uid,
                "source_sha256": content_digest(memory.content),
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
