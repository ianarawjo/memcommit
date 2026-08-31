"""Private latest-slot cache for validated rationale inferences.

The cache deliberately stores neither the provider prompt nor the candidate
frame as separate fields. Its input digest binds a validated inference to that
exact input, while the saved record retains only identities and the small
rendered result needed to reconstruct a rationale report. That result can
still paraphrase or quote an ordinary Memory, so it shares the Context's
privacy lifetime.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
import uuid

import memcommit.persistence.store as store_module


CACHE_SCHEMA_VERSION = 3
# Persisted cache contract, intentionally independent of the Python owner path.
INFERENCE_CONTRACT = "memcommit.rationale.context-inference.v5"
PROVIDER_CONTRACT = "memcommit.query-provider.rationale-inference.v5"

_EXPLANATION_CHAR_LIMIT = 480
_MEMORY_UID_CHAR_LIMIT = 4_096
_ITEM_LIMIT = 8
_CACHE_FILE_BYTE_LIMIT = 256_000
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_FINAL_INFERENCE_NAME = re.compile(r"^([0-9a-f]{64})\.json$")
_ATOMIC_TEMP_NAME = re.compile(
    r"^\.([0-9a-f]{64})\.json\.write-([0-9a-f]{32})$"
)


def _nonempty_text(value: object, label: str, limit: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
    ):
        raise ValueError(f"Invalid {label}.")
    return value


def _memory_uid(value: object, label: str) -> str:
    return _nonempty_text(value, label, _MEMORY_UID_CHAR_LIMIT)


def _canonical_uuid(value: object, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))  # type: ignore[arg-type]
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label}.") from error
    if canonical != value:
        raise ValueError(f"Invalid {label}.")
    return canonical


def _input_digest(value: object) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError("Invalid rationale inference input digest.")
    return value


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class CachedRationaleInference:
    """Provider-independent, already validated rationale inference."""

    explanation: str
    support_memory_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        _nonempty_text(
            self.explanation,
            "cached rationale explanation",
            _EXPLANATION_CHAR_LIMIT,
        )
        normalized = unicodedata.normalize("NFC", self.explanation.strip())
        if (
            self.explanation != normalized
            or "\n" in self.explanation
            or "\r" in self.explanation
            or any(
                unicodedata.category(char) == "Cc"
                for char in self.explanation
            )
        ):
            raise ValueError("Invalid cached rationale explanation.")
        if (
            not isinstance(self.support_memory_uids, tuple)
            or len(self.support_memory_uids) > _ITEM_LIMIT
        ):
            raise ValueError("Invalid cached rationale support Memories.")
        for memory_uid in self.support_memory_uids:
            _memory_uid(memory_uid, "cached rationale support Memory uid")
        if len(set(self.support_memory_uids)) != len(
            self.support_memory_uids
        ):
            raise ValueError("Invalid cached rationale support Memories.")

    def to_dict(self) -> dict[str, object]:
        return {
            "explanation": self.explanation,
            "support_memory_uids": list(self.support_memory_uids),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> CachedRationaleInference:
        if (
            not isinstance(value, dict)
            or set(value) != {"explanation", "support_memory_uids"}
        ):
            raise ValueError("Invalid cached rationale inference.")
        support = value["support_memory_uids"]
        if not isinstance(support, list):
            raise ValueError("Invalid cached rationale inference.")
        return cls(
            explanation=value["explanation"],  # type: ignore[arg-type]
            support_memory_uids=tuple(support),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class StoredRationaleInference:
    """One validated latest rationale projection discovered for search."""

    context_uid: str
    selected_memory_uid: str
    input_digest: str
    inference: CachedRationaleInference


def rationale_inferences_dir() -> Path:
    """Resolve the cache root at call time for profile/test isolation."""
    return store_module.STORE_DIR / "rationale-inferences"


def rationale_inference_input_digest(
    *,
    context_uid: str,
    selected_memory_uid: str,
    prompt: str,
    output_schema: dict[str, object],
) -> str:
    """Bind an inference to the complete provider-facing request contract."""
    context = _canonical_uuid(
        context_uid,
        "rationale inference Context uid",
    )
    selected = _memory_uid(
        selected_memory_uid,
        "rationale inference selected Memory uid",
    )
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("Invalid rationale inference prompt.")
    if not isinstance(output_schema, dict):
        raise ValueError("Invalid rationale inference output schema.")
    value = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "inference_contract": INFERENCE_CONTRACT,
        "provider_contract": PROVIDER_CONTRACT,
        "context_uid": context,
        "selected_memory_uid": selected,
        "prompt": prompt,
        "output_schema": output_schema,
    }
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Invalid rationale inference output schema."
        ) from error
    return hashlib.sha256(encoded).hexdigest()


def rationale_inference_path(
    context_uid: str,
    selected_memory_uid: str,
) -> Path:
    """Return one latest slot without placing a raw Memory uid in its path."""
    context = _canonical_uuid(
        context_uid,
        "rationale inference Context uid",
    )
    selected = _memory_uid(
        selected_memory_uid,
        "rationale inference selected Memory uid",
    )
    root = rationale_inferences_dir()
    if root.is_symlink():
        raise ValueError(
            "Rationale inference cache cannot be a symbolic link."
        )
    if root.exists() and not root.is_dir():
        raise ValueError("Rationale inference cache storage is invalid.")
    context_dir = root / context
    if context_dir.is_symlink() or (
        context_dir.exists() and not context_dir.is_dir()
    ):
        raise ValueError("Rationale inference cache storage is invalid.")
    selected_digest = hashlib.sha256(selected.encode("utf-8")).hexdigest()
    return context_dir / f"{selected_digest}.json"


def _cache_record(
    *,
    context_uid: str,
    selected_memory_uid: str,
    input_digest: str,
    inference: CachedRationaleInference,
) -> dict[str, object]:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "inference_contract": INFERENCE_CONTRACT,
        "provider_contract": PROVIDER_CONTRACT,
        "context_uid": context_uid,
        "selected_memory_uid": selected_memory_uid,
        "input_digest": input_digest,
        "inference": inference.to_dict(),
    }


def load_rationale_inference(
    context_uid: str,
    selected_uid: str,
    input_digest: str,
) -> CachedRationaleInference | None:
    """Load the latest slot only when every request binding still matches."""
    context = _canonical_uuid(
        context_uid,
        "rationale inference Context uid",
    )
    selected = _memory_uid(
        selected_uid,
        "rationale inference selected Memory uid",
    )
    digest = _input_digest(input_digest)
    path = rationale_inference_path(context, selected)
    if path.is_symlink():
        raise ValueError("Rationale inference cache storage is invalid.")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError("Rationale inference cache storage is invalid.")

    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or details.st_size > _CACHE_FILE_BYTE_LIMIT
        ):
            raise ValueError("Saved rationale inference is invalid.")
        with os.fdopen(descriptor, encoding="utf-8") as file:
            descriptor = None
            encoded = file.read(_CACHE_FILE_BYTE_LIMIT + 1)
        if len(encoded.encode("utf-8")) > _CACHE_FILE_BYTE_LIMIT:
            raise ValueError("Saved rationale inference is invalid.")
        value = json.loads(
            encoded,
            object_pairs_hook=_strict_json_object,
        )
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "inference_contract",
            "provider_contract",
            "context_uid",
            "selected_memory_uid",
            "input_digest",
            "inference",
        }:
            raise ValueError("Saved rationale inference is invalid.")
        schema_version = value["schema_version"]
        inference_contract = value["inference_contract"]
        provider_contract = value["provider_contract"]
        stored_digest = _input_digest(value["input_digest"])
        if (
            type(schema_version) is not int
            or not isinstance(inference_contract, str)
            or not inference_contract
            or not isinstance(provider_contract, str)
            or not provider_contract
            or value["context_uid"] != context
            or value["selected_memory_uid"] != selected
        ):
            raise ValueError("Saved rationale inference is invalid.")
        # Contract upgrades and ordinary Context changes are expected misses,
        # not cache corruption.  Only matching records reach deserialization.
        if (
            schema_version != CACHE_SCHEMA_VERSION
            or inference_contract != INFERENCE_CONTRACT
            or provider_contract != PROVIDER_CONTRACT
            or stored_digest != digest
        ):
            return None
        inference = CachedRationaleInference.from_dict(value["inference"])
    except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
        raise ValueError("Saved rationale inference is invalid.") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return inference


def save_rationale_inference(
    context_uid: str,
    selected_uid: str,
    input_digest: str,
    inference: CachedRationaleInference,
) -> None:
    """Atomically replace one latest slot with a validated inference."""
    context = _canonical_uuid(
        context_uid,
        "rationale inference Context uid",
    )
    selected = _memory_uid(
        selected_uid,
        "rationale inference selected Memory uid",
    )
    digest = _input_digest(input_digest)
    if not isinstance(inference, CachedRationaleInference):
        raise TypeError("Expected a CachedRationaleInference.")
    restored = CachedRationaleInference.from_dict(inference.to_dict())
    path = rationale_inference_path(context, selected)
    record = _cache_record(
        context_uid=context,
        selected_memory_uid=selected,
        input_digest=digest,
        inference=restored,
    )
    if len(
        json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8")
    ) > _CACHE_FILE_BYTE_LIMIT:
        raise ValueError("Rationale inference is too large to cache.")

    with store_module.MemoryStore(create=False).profile_write_guard():
        root = rationale_inferences_dir()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Rationale inference cache storage is invalid.")
        root.chmod(0o700)
        context_dir = path.parent
        context_dir.mkdir(exist_ok=True, mode=0o700)
        if context_dir.is_symlink() or not context_dir.is_dir():
            raise ValueError("Rationale inference cache storage is invalid.")
        context_dir.chmod(0o700)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Rationale inference cache storage is invalid.")
        store_module._write_json_atomic(path, record)
        path.chmod(0o600)


def rationale_inference_paths_for_context(
    context_uid: str,
) -> tuple[Path, ...]:
    """Preflight every final or atomic temporary file in one subtree."""
    context = _canonical_uuid(
        context_uid,
        "rationale inference Context uid",
    )
    root = rationale_inferences_dir()
    if root.is_symlink():
        raise ValueError("Rationale inference cache storage is invalid.")
    if not root.exists():
        return ()
    if not root.is_dir():
        raise ValueError("Rationale inference cache storage is invalid.")
    context_dir = root / context
    if context_dir.is_symlink():
        raise ValueError("Rationale inference cache storage is invalid.")
    if not context_dir.exists():
        return ()
    if not context_dir.is_dir():
        raise ValueError("Rationale inference cache storage is invalid.")

    paths: list[Path] = []
    for path in context_dir.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Rationale inference cache storage is invalid.")
        if (
            _FINAL_INFERENCE_NAME.fullmatch(path.name) is None
            and _ATOMIC_TEMP_NAME.fullmatch(path.name) is None
        ):
            raise ValueError("Rationale inference cache storage is invalid.")
        paths.append(path)
    return tuple(sorted(paths))


def list_rationale_inferences(
    context_uid: str,
) -> tuple[StoredRationaleInference, ...]:
    """Read every validated final rationale slot for one owned Context.

    Search needs the already-saved inference, not the original provider prompt
    or a newly inferred rationale. Atomic scratch files are deliberately
    ignored; malformed final records fail closed through the normal loader.
    """
    context = _canonical_uuid(
        context_uid,
        "rationale inference Context uid",
    )
    records: list[StoredRationaleInference] = []
    for path in rationale_inference_paths_for_context(context):
        if _ATOMIC_TEMP_NAME.fullmatch(path.name) is not None:
            continue
        try:
            with open(path, encoding="utf-8") as file:
                value = json.load(file, object_pairs_hook=_strict_json_object)
        except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
            raise ValueError("Saved rationale inference is invalid.") from error
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "inference_contract",
            "provider_contract",
            "context_uid",
            "selected_memory_uid",
            "input_digest",
            "inference",
        }:
            raise ValueError("Saved rationale inference is invalid.")
        selected = _memory_uid(
            value["selected_memory_uid"],
            "stored rationale inference selected Memory uid",
        )
        digest = _input_digest(value["input_digest"])
        inference = load_rationale_inference(context, selected, digest)
        if inference is None:
            # Old contracts are safe cache misses for Rationale and equally
            # unsuitable as current searchable evidence.
            continue
        records.append(
            StoredRationaleInference(
                context_uid=context,
                selected_memory_uid=selected,
                input_digest=digest,
                inference=inference,
            )
        )
    return tuple(records)


def delete_rationale_inference_paths(paths: tuple[Path, ...]) -> None:
    """Delete an exact preflighted set and prune empty cache directories."""
    if not isinstance(paths, tuple):
        raise TypeError("Expected rationale inference cache paths as a tuple.")
    root = rationale_inferences_dir()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Rationale inference cache storage is invalid.")

    context_dirs: set[Path] = set()
    for path in paths:
        if not isinstance(path, Path):
            raise TypeError("Expected rationale inference cache Paths.")
        context_dir = path.parent
        if context_dir.parent != root:
            raise ValueError(
                "Rationale inference cache changed during delete."
            )
        _canonical_uuid(
            context_dir.name,
            "stored rationale inference Context uid",
        )
        if (
            _FINAL_INFERENCE_NAME.fullmatch(path.name) is None
            and _ATOMIC_TEMP_NAME.fullmatch(path.name) is None
        ):
            raise ValueError(
                "Rationale inference cache changed during delete."
            )
        if context_dir.is_symlink() or (
            context_dir.exists() and not context_dir.is_dir()
        ):
            raise ValueError(
                "Rationale inference cache changed during delete."
            )
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(
                "Rationale inference cache changed during delete."
            )
        context_dirs.add(context_dir)

    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    for context_dir in sorted(context_dirs):
        if context_dir.exists():
            try:
                context_dir.rmdir()
            except OSError:
                pass
    if root.exists():
        try:
            root.rmdir()
        except OSError:
            pass
