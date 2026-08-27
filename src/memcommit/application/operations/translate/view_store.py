"""Operation-owned persistence for deterministic translation-view slots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import uuid

import memcommit.persistence.store as store_module
from memcommit.core.context import Context, Memory
from memcommit.application.operations.translate.view import (
    TranslationCatalog,
    TranslationView,
    TranslationViewError,
    _source_uid,
    _target_language,
    translation_catalog_record_digest,
    translation_view_record_digest,
)


class ConcurrentTranslationViewUpdateError(RuntimeError):
    """A source Context or deterministic translation-view slot changed."""


_FINAL_VIEW_NAME = re.compile(
    r"^([0-9a-f-]{36})--([0-9a-f]{64})--"
    r"(catalog|all|memory-[0-9a-f]{64})\.json$"
)
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f-]{36})--([0-9a-f]{64})--"
    r"(catalog|all|memory-[0-9a-f]{64})"
    r"\.json\.write-([0-9a-f]{32})$"
)


def translation_views_dir() -> Path:
    """Resolve against the runtime store root for isolated stores/tests."""
    return store_module.STORE_DIR / "translation-views"


def _canonical_uuid(value: str, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label}.") from error
    if canonical != value:
        raise ValueError(f"Invalid {label}.")
    return canonical


def _slot_scope(selected_memory_uid: str | None) -> str:
    if selected_memory_uid is None:
        return "all"
    selected = _source_uid(
        selected_memory_uid,
        "translation view selected source Memory uid",
    )
    # Source UIDs are identities, not filenames.  Hashing supports legacy
    # printable UIDs without allowing path syntax into the artifact root.
    return "memory-" + hashlib.sha256(
        selected.encode("utf-8")
    ).hexdigest()


def translation_view_path(
    context_uid: str,
    target_language: str,
    selected_memory_uid: str | None = None,
) -> Path:
    """Return the deterministic slot for one exact language and source scope."""
    context = _canonical_uuid(
        context_uid,
        "translation view source Context uid",
    )
    language = _target_language(target_language)
    language_digest = hashlib.sha256(
        language.encode("utf-8")
    ).hexdigest()
    scope = _slot_scope(selected_memory_uid)
    root = translation_views_dir()
    if root.is_symlink():
        raise ValueError(
            "Translation view storage cannot be a symbolic link."
        )
    if root.exists() and not root.is_dir():
        raise ValueError("Translation view storage is invalid.")
    return root / f"{context}--{language_digest}--{scope}.json"


def translation_catalog_path(
    context_uid: str,
    target_language: str,
) -> Path:
    """Return the one authoritative v2 slot for a Context-language pair."""
    context = _canonical_uuid(
        context_uid,
        "translation catalog source Context uid",
    )
    language = _target_language(target_language)
    language_digest = hashlib.sha256(
        language.encode("utf-8")
    ).hexdigest()
    root = translation_views_dir()
    if root.is_symlink():
        raise ValueError(
            "Translation view storage cannot be a symbolic link."
        )
    if root.exists() and not root.is_dir():
        raise ValueError("Translation view storage is invalid.")
    return root / f"{context}--{language_digest}--catalog.json"


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_translation_view(
    context_uid: str,
    target_language: str,
    selected_memory_uid: str | None = None,
) -> TranslationView | None:
    """Load one deterministic latest slot without creating store state."""
    path = translation_view_path(
        context_uid,
        target_language,
        selected_memory_uid,
    )
    if path.is_symlink():
        raise ValueError("Translation view storage is invalid.")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError("Translation view storage is invalid.")
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(
                file,
                object_pairs_hook=_strict_json_object,
            )
        view = TranslationView.from_dict(value)
    except (
        json.JSONDecodeError,
        TranslationViewError,
        ValueError,
    ) as error:
        raise ValueError("Saved translation view is invalid.") from error
    if (
        view.context_uid != context_uid
        or view.target_language != target_language
        or view.selected_memory_uid != selected_memory_uid
        or translation_view_path(
            view.context_uid,
            view.target_language,
            view.selected_memory_uid,
        )
        != path
    ):
        raise ValueError(
            "Saved translation view does not match its storage key."
        )
    return view


def load_translation_catalog(
    context_uid: str,
    target_language: str,
) -> TranslationCatalog | None:
    """Load the v2 catalog slot without reading or rewriting legacy views."""
    path = translation_catalog_path(context_uid, target_language)
    if path.is_symlink():
        raise ValueError("Translation view storage is invalid.")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError("Translation view storage is invalid.")
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(
                file,
                object_pairs_hook=_strict_json_object,
            )
        catalog = TranslationCatalog.from_dict(value)
    except (
        json.JSONDecodeError,
        TranslationViewError,
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
        raise ValueError(
            "Saved translation catalog does not match its storage key."
        )
    return catalog


def _load_legacy_views_for_target(
    context_uid: str,
    target_language: str,
) -> tuple[TranslationView, ...]:
    """Read every v1 scope for lazy, non-persisting catalog migration."""
    context = _canonical_uuid(
        context_uid,
        "translation view source Context uid",
    )
    language = _target_language(target_language)
    language_digest = hashlib.sha256(
        language.encode("utf-8")
    ).hexdigest()
    root = translation_views_dir()
    if not root.exists():
        if root.is_symlink():
            raise ValueError("Translation view storage is invalid.")
        return ()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Translation view storage is invalid.")
    prefix = f"{context}--{language_digest}--"
    views: list[TranslationView] = []
    for path in sorted(root.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Translation view storage is invalid.")
        if not path.name.startswith(prefix):
            continue
        match = _FINAL_VIEW_NAME.fullmatch(path.name)
        if match is None or match.group(3) == "catalog":
            continue
        try:
            with open(path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_strict_json_object,
                )
            view = TranslationView.from_dict(value)
        except (
            json.JSONDecodeError,
            TranslationViewError,
            ValueError,
        ) as error:
            raise ValueError("Saved translation view is invalid.") from error
        if (
            view.context_uid != context
            or view.target_language != language
            or translation_view_path(
                view.context_uid,
                view.target_language,
                view.selected_memory_uid,
            )
            != path
        ):
            raise ValueError(
                "Saved translation view does not match its storage key."
            )
        views.append(view)
    return tuple(views)


def load_translation_catalog_for_context(
    context: Context,
    target_language: str,
) -> tuple[TranslationCatalog | None, bool]:
    """Load v2, or compose valid v1 views in memory without writing them.

    The boolean is true only for a legacy-derived in-memory catalog. Callers
    must use an expected catalog digest of ``None`` for its first v2 save.
    """
    if not isinstance(context, Context):
        raise TypeError("Expected a Context.")
    context_uid = context.uid
    target = _target_language(target_language)
    catalog = load_translation_catalog(context_uid, target)
    if catalog is not None:
        if catalog.context_name != context.name:
            raise ValueError(
                "Saved translation catalog does not match its source Context."
            )
        return catalog, False
    legacy_views = _load_legacy_views_for_target(context_uid, target)
    migrated = TranslationCatalog.from_legacy_views(
        context,
        target,
        legacy_views,
    )
    return migrated, migrated is not None


def _validate_expected_digest(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value
        )
    ):
        raise ValueError(
            "Invalid expected translation view record digest."
        )
    return value


def save_translation_view(
    store: store_module.MemoryStore,
    view: TranslationView,
    *,
    expected_record_digest: str | None,
) -> None:
    """CAS-save a view while its exact source Context remains locked."""
    if not isinstance(store, store_module.MemoryStore):
        raise TypeError("Expected a MemoryStore.")
    if not isinstance(view, TranslationView):
        raise TypeError("Expected a TranslationView.")
    restored = TranslationView.from_dict(view.to_dict())
    if restored != view:
        raise ValueError(
            "Translation view changed during save validation."
        )
    expected = _validate_expected_digest(expected_record_digest)
    path = translation_view_path(
        view.context_uid,
        view.target_language,
        view.selected_memory_uid,
    )

    # The source lock is also this Context-bound slot's cooperative writer
    # lock.  The record-digest CAS prevents a slower provider call from
    # replacing a newer view while requiring no synthetic artifact identity.
    # Rename scans and migrates Context-bound translation artifacts. The
    # graph lock must precede the Context lock so a late provider result can
    # neither recreate an old-name artifact nor deadlock the migration.
    with (
        store._context_graph_lock(exclusive=False),
        store._context_write_lock(view.context_name),
        store.profile_write_guard(),
    ):
        try:
            current_context = store.load_direct(view.context_name)
        except FileNotFoundError as error:
            raise ConcurrentTranslationViewUpdateError(
                "The translation view source Context no longer exists."
            ) from error
        if not view.matches(current_context):
            raise ConcurrentTranslationViewUpdateError(
                "The translation view is stale because the source Context "
                "changed while Translate was generating it; the new view "
                "was not saved."
            )

        # Once a v2 catalog exists it is the authoritative slot. Allowing a
        # late v1 writer to succeed would create a valid-looking update that
        # every subsequent read silently ignores.
        if load_translation_catalog(
            view.context_uid,
            view.target_language,
        ) is not None:
            raise ConcurrentTranslationViewUpdateError(
                "The legacy translation view cannot be saved after its v2 "
                "catalog has been created."
            )

        current = load_translation_view(
            view.context_uid,
            view.target_language,
            view.selected_memory_uid,
        )
        current_digest = (
            translation_view_record_digest(current)
            if current is not None
            else None
        )
        if current_digest != expected:
            raise ConcurrentTranslationViewUpdateError(
                "The translation view slot changed before this view could "
                "be saved."
            )

        root = translation_views_dir()
        if root.exists() and (
            not root.is_dir() or root.is_symlink()
        ):
            raise ValueError("Translation view storage is invalid.")
        root.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or (
            path.exists() and not path.is_file()
        ):
            raise ValueError("Translation view storage is invalid.")
        store_module._write_json_atomic(path, view.to_dict())


def save_translation_catalog(
    store: store_module.MemoryStore,
    catalog: TranslationCatalog,
    *,
    expected_record_digest: str | None,
    expected_legacy_record_digest: str | None = None,
    expected_context_digest: str | None = None,
    required_source_digests: dict[str, str] | None = None,
) -> None:
    """CAS-save v2 while preserving stale curated entries outside the write.

    Provider publication supplies ``expected_context_digest`` because one
    aggregate model call saw that complete frame. Manual/imported mutations
    instead supply only the exact source bindings they reviewed. This keeps an
    unrelated stale entry from preventing a safe edit without weakening the
    selected source check.
    """
    if not isinstance(store, store_module.MemoryStore):
        raise TypeError("Expected a MemoryStore.")
    if not isinstance(catalog, TranslationCatalog):
        raise TypeError("Expected a TranslationCatalog.")
    restored = TranslationCatalog.from_dict(catalog.to_dict())
    if restored != catalog:
        raise ValueError(
            "Translation catalog changed during save validation."
        )
    expected = _validate_expected_digest(expected_record_digest)
    expected_legacy = _validate_expected_digest(
        expected_legacy_record_digest
    )
    expected_context = _validate_expected_digest(expected_context_digest)
    source_bindings = required_source_digests or {}
    if not isinstance(source_bindings, dict):
        raise ValueError("Invalid required translation source bindings.")
    checked_bindings: dict[str, str] = {}
    for source_uid, source_digest in source_bindings.items():
        checked_uid = _source_uid(
            source_uid,
            "required translation source Memory uid",
        )
        checked_bindings[checked_uid] = _validate_expected_digest(
            source_digest
        ) or ""
    path = translation_catalog_path(
        catalog.context_uid,
        catalog.target_language,
    )

    with (
        store._context_graph_lock(exclusive=False),
        store._context_write_lock(catalog.context_name),
        store.profile_write_guard(),
    ):
        try:
            current_context = store.load_direct(catalog.context_name)
        except FileNotFoundError as error:
            raise ConcurrentTranslationViewUpdateError(
                "The translation catalog source Context no longer exists."
            ) from error
        if (
            current_context.uid != catalog.context_uid
            or current_context.name != catalog.context_name
        ):
            raise ConcurrentTranslationViewUpdateError(
                "The translation catalog source Context was replaced."
            )
        if (
            expected_context is not None
            and store_module.context_record_digest(current_context)
            != expected_context
        ):
            raise ConcurrentTranslationViewUpdateError(
                "The translation catalog source Context changed before the "
                "provider result could be saved."
            )
        for source_uid, source_digest in checked_bindings.items():
            source = current_context.memories.get(source_uid)
            if (
                not isinstance(source, Memory)
                or hashlib.sha256(source.content.encode("utf-8")).hexdigest()
                != source_digest
            ):
                raise ConcurrentTranslationViewUpdateError(
                    "A translation source Memory changed before its curated "
                    "translation could be saved."
                )
        # The candidate is a complete catalog. Even a manually edited A entry
        # must not reintroduce an unrelated B entry removed after the caller's
        # snapshot. Edited sources keep their UID and remain valid here;
        # removed sources require the caller to reload and prune first.
        if any(
            not isinstance(
                current_context.memories.get(entry.source_uid),
                Memory,
            )
            for entry in catalog.entries
        ):
            raise ConcurrentTranslationViewUpdateError(
                "A translation source Memory was removed before the catalog "
                "could be saved."
            )

        current = load_translation_catalog(
            catalog.context_uid,
            catalog.target_language,
        )
        current_digest = (
            translation_catalog_record_digest(current)
            if current is not None
            else None
        )
        if current_digest != expected:
            raise ConcurrentTranslationViewUpdateError(
                "The translation catalog changed before this update could be "
                "saved."
            )
        if current is None:
            # v1 writers use this same Context lock. Recompose the legacy
            # source while holding it so a lazy migration cannot silently
            # shadow a newer v1 write that landed after the initial read.
            legacy_catalog = TranslationCatalog.from_legacy_views(
                current_context,
                catalog.target_language,
                _load_legacy_views_for_target(
                    catalog.context_uid,
                    catalog.target_language,
                ),
            )
            legacy_digest = (
                translation_catalog_record_digest(legacy_catalog)
                if legacy_catalog is not None
                else None
            )
            if legacy_digest != expected_legacy:
                raise ConcurrentTranslationViewUpdateError(
                    "The legacy translation view changed before migration "
                    "could be saved."
                )

        root = translation_views_dir()
        if root.exists() and (
            not root.is_dir() or root.is_symlink()
        ):
            raise ValueError("Translation view storage is invalid.")
        root.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or (
            path.exists() and not path.is_file()
        ):
            raise ValueError("Translation view storage is invalid.")
        store_module._write_json_atomic(path, catalog.to_dict())


def translation_view_paths_for_context(
    context_uid: str,
) -> tuple[Path, ...]:
    """Preflight and return every saved or temporary view for one Context."""
    canonical = _canonical_uuid(
        context_uid,
        "translation view source Context uid",
    )
    root = translation_views_dir()
    if not root.exists():
        if root.is_symlink():
            raise ValueError("Translation view storage is invalid.")
        return ()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Translation view storage is invalid.")
    matches: list[Path] = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Translation view storage is invalid.")
        match = _FINAL_VIEW_NAME.fullmatch(path.name)
        if match is None:
            match = _ATOMIC_TEMP_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError("Translation view storage is invalid.")
        stored_context = _canonical_uuid(
            match.group(1),
            "stored translation view source Context uid",
        )
        if canonical == stored_context:
            matches.append(path)
    return tuple(sorted(matches))


def delete_translation_view_paths(paths: tuple[Path, ...]) -> None:
    """Delete an exact preflighted set and prune an empty view root."""
    root = translation_views_dir()
    if root.is_symlink() or (
        root.exists() and not root.is_dir()
    ):
        raise ValueError("Translation view storage is invalid.")
    for path in paths:
        if path.parent != root or path.is_symlink():
            raise ValueError(
                "Translation view storage changed during delete."
            )
        if not path.exists():
            # Concurrent deletion may already have reached the same desired
            # privacy result for this exact source-bound artifact.
            continue
        if not path.is_file():
            raise ValueError(
                "Translation view storage changed during delete."
            )
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    if root.exists():
        try:
            root.rmdir()
        except OSError:
            pass
