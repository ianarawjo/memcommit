"""Filesystem repository for Context-bound Memory translation catalogs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import uuid

import memcommit.persistence.store as store_module
from memcommit.core.context import Memory
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TranslationCatalogError,
    translation_content_digest,
    validate_sha256,
    validate_translation_target,
)
from memcommit.persistence.store.translation_catalog.record_format import (
    decode_translation_catalog_record,
    encode_translation_catalog_record,
    translation_catalog_record_digest,
)


class ConcurrentTranslationCatalogUpdateError(RuntimeError):
    """The source Context or its translation catalog changed concurrently."""


_FINAL_CATALOG_NAME = re.compile(r"^([0-9a-f-]{36})--([0-9a-f]{64})--catalog\.json$")
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f-]{36})--([0-9a-f]{64})--catalog"
    r"\.json\.write-([0-9a-f]{32})$"
)


def translation_catalogs_dir() -> Path:
    """Resolve the catalog root against the active MemoryStore root."""
    # Keep the durable fixture directory stable while Python ownership moves.
    # Renaming fixture trees is a separate storage-layout decision.
    return store_module.STORE_DIR / "translation-views"


def _canonical_uuid(value: str, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label}.") from error
    if canonical != value:
        raise ValueError(f"Invalid {label}.")
    return canonical


def translation_catalog_path(
    context_uid: str,
    target_language: str,
) -> Path:
    """Return the authoritative slot for one Context and semantic target."""
    context = _canonical_uuid(
        context_uid,
        "translation catalog source Context uid",
    )
    target = validate_translation_target(target_language)
    language_digest = hashlib.sha256(target.encode("utf-8")).hexdigest()
    root = translation_catalogs_dir()
    if root.is_symlink():
        raise ValueError("Translation catalog storage cannot be a symbolic link.")
    if root.exists() and not root.is_dir():
        raise ValueError("Translation catalog storage is invalid.")
    return root / f"{context}--{language_digest}--catalog.json"


def load_translation_catalog(
    context_uid: str,
    target_language: str,
) -> MemoryTranslationCatalog | None:
    """Load one exact catalog slot without creating store state."""
    path = translation_catalog_path(context_uid, target_language)
    if path.is_symlink():
        raise ValueError("Translation catalog storage is invalid.")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError("Translation catalog storage is invalid.")
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(
                file,
                object_pairs_hook=store_module._reject_duplicate_json_keys,
            )
        catalog = decode_translation_catalog_record(value)
    except (
        json.JSONDecodeError,
        OSError,
        TranslationCatalogError,
        ValueError,
    ) as error:
        raise ValueError("Saved translation catalog is invalid.") from error
    if (
        catalog.context_uid != context_uid
        or catalog.target_language != target_language
        or translation_catalog_path(
            catalog.context_uid,
            catalog.target_language,
        )
        != path
    ):
        raise ValueError("Saved translation catalog does not match its storage key.")
    return catalog


def _validate_expected_digest(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return validate_sha256(
            value,
            "expected translation catalog record digest",
        )
    except TranslationCatalogError as error:
        raise ValueError(str(error)) from error


def save_translation_catalog(
    store: store_module.MemoryStore,
    catalog: MemoryTranslationCatalog,
    *,
    expected_record_digest: str | None,
    expected_context_digest: str | None = None,
    required_source_digests: dict[str, str] | None = None,
) -> None:
    """Publish one complete catalog under its source and catalog CAS locks.

    The application chooses either a complete Context binding for provider
    work or exact Memory bindings for curation. This repository enforces those
    preconditions inside the same lock interval as publication.
    """
    if not isinstance(store, store_module.MemoryStore):
        raise TypeError("Expected a MemoryStore.")
    if not isinstance(catalog, MemoryTranslationCatalog):
        raise TypeError("Expected a MemoryTranslationCatalog.")
    record = encode_translation_catalog_record(catalog)
    if decode_translation_catalog_record(record) != catalog:
        raise ValueError("Translation catalog changed during save validation.")
    expected = _validate_expected_digest(expected_record_digest)
    expected_context = _validate_expected_digest(expected_context_digest)
    source_bindings = required_source_digests or {}
    if not isinstance(source_bindings, dict):
        raise ValueError("Invalid required translation source bindings.")
    checked_bindings: dict[str, str] = {}
    for source_uid, source_digest in source_bindings.items():
        if not isinstance(source_uid, str):
            raise ValueError("Invalid required translation source Memory uid.")
        checked_bindings[source_uid] = _validate_expected_digest(source_digest) or ""
    path = translation_catalog_path(
        catalog.context_uid,
        catalog.target_language,
    )

    # Catalog publication shares the Context writer lock because the saved
    # representation is meaningful only for that exact source identity. The
    # graph lock precedes it so rename cannot race or invert lock order.
    with (
        store._context_graph_lock(exclusive=False),
        store._context_write_lock(catalog.context_name),
        store.profile_write_guard(),
    ):
        try:
            current_context = store.load_direct(catalog.context_name)
        except FileNotFoundError as error:
            raise ConcurrentTranslationCatalogUpdateError(
                "The translation catalog source Context no longer exists."
            ) from error
        if (
            current_context.uid != catalog.context_uid
            or current_context.name != catalog.context_name
        ):
            raise ConcurrentTranslationCatalogUpdateError(
                "The translation catalog source Context was replaced."
            )
        if expected_context is not None and (
            store_module.context_record_digest(current_context) != expected_context
        ):
            raise ConcurrentTranslationCatalogUpdateError(
                "The translation catalog source Context changed before the "
                "provider result could be saved."
            )
        for source_uid, source_digest in checked_bindings.items():
            source = current_context.memories.get(source_uid)
            if (
                not isinstance(source, Memory)
                or translation_content_digest(source.content) != source_digest
            ):
                raise ConcurrentTranslationCatalogUpdateError(
                    "A translation source Memory changed before its curated "
                    "translation could be saved."
                )
        if any(
            not isinstance(
                current_context.memories.get(entry.source_uid),
                Memory,
            )
            for entry in catalog.entries
        ):
            raise ConcurrentTranslationCatalogUpdateError(
                "A translation source Memory was removed before the catalog "
                "could be saved."
            )

        current = load_translation_catalog(
            catalog.context_uid,
            catalog.target_language,
        )
        current_digest = (
            translation_catalog_record_digest(current) if current is not None else None
        )
        if current_digest != expected:
            raise ConcurrentTranslationCatalogUpdateError(
                "The translation catalog changed before this update could be saved."
            )

        root = translation_catalogs_dir()
        if root.exists() and (not root.is_dir() or root.is_symlink()):
            raise ValueError("Translation catalog storage is invalid.")
        root.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Translation catalog storage is invalid.")
        store_module._write_json_atomic(path, record)


def translation_catalog_paths_for_context(
    context_uid: str,
) -> tuple[Path, ...]:
    """Preflight catalog files and atomic temporaries for one Context."""
    canonical = _canonical_uuid(
        context_uid,
        "translation catalog source Context uid",
    )
    root = translation_catalogs_dir()
    if not root.exists():
        if root.is_symlink():
            raise ValueError("Translation catalog storage is invalid.")
        return ()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Translation catalog storage is invalid.")
    matches: list[Path] = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Translation catalog storage is invalid.")
        match = _FINAL_CATALOG_NAME.fullmatch(path.name)
        if match is None:
            match = _ATOMIC_TEMP_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError("Translation catalog storage is invalid.")
        stored_context = _canonical_uuid(
            match.group(1),
            "stored translation catalog source Context uid",
        )
        if canonical == stored_context:
            matches.append(path)
    return tuple(sorted(matches))


def delete_translation_catalog_paths(paths: tuple[Path, ...]) -> None:
    """Delete an exact preflighted set and prune an empty catalog root."""
    root = translation_catalogs_dir()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Translation catalog storage is invalid.")
    for path in paths:
        if path.parent != root or path.is_symlink():
            raise ValueError("Translation catalog storage changed during delete.")
        if not path.exists():
            continue
        if not path.is_file():
            raise ValueError("Translation catalog storage changed during delete.")
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    if root.exists():
        try:
            root.rmdir()
        except OSError:
            pass
