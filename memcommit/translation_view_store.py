"""Persistence for deterministic latest translation-view slots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import uuid

import memcommit.store as store_module
from memcommit.translation_view import (
    TranslationView,
    TranslationViewError,
    _source_uid,
    _target_language,
    translation_view_record_digest,
)


class ConcurrentTranslationViewUpdateError(RuntimeError):
    """A source Context or deterministic translation-view slot changed."""


_FINAL_VIEW_NAME = re.compile(
    r"^([0-9a-f-]{36})--([0-9a-f]{64})--"
    r"(all|memory-[0-9a-f]{64})\.json$"
)
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f-]{36})--([0-9a-f]{64})--"
    r"(all|memory-[0-9a-f]{64})"
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
    with store._context_write_lock(view.context_name):
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
