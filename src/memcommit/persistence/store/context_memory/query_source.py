"""Create, validate, load, and delete persisted Query Sources."""

from __future__ import annotations
import json
import os
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from memcommit.core.context_targeting.naming import validate_portable_context_name

from ..infrastructure.atomic_io import _reject_duplicate_json_keys
from ..infrastructure.protection import _profile_write_guarded
from .records import _context_name_parts


@dataclass(frozen=True)
class QuerySourceEntry:
    """One stable concealed record with an English canonical form."""

    uid: str
    key: str
    canonical_content: str
    translations: tuple[tuple[str, str], ...] = ()

    def content_for(
        self,
        language: str,
        *,
        canonical_language: str = "en",
        fallback_to_canonical: bool = False,
    ) -> str:
        """Select one language without changing this entry's stable identity."""
        if language == canonical_language:
            return self.canonical_content
        translated = dict(self.translations).get(language)
        if translated is not None:
            return translated
        if fallback_to_canonical:
            return self.canonical_content
        # Entry keys are concealed storage metadata.  A missing-language error
        # crosses the query-only boundary into the CLI, so it must not identify
        # which private record failed coverage.
        raise ValueError("Requested query-source translation is unavailable.")


@dataclass(frozen=True)
class QuerySource:
    """Research-only source text kept outside the normal Context namespace.

    ``content`` preserves the original one-string read contract. Construction
    and dataclass serialization are internal entry-oriented records in v2;
    callers obtain sources through ``MemoryStore`` rather than instantiating
    this type directly.
    """

    uid: str
    name: str
    entries: tuple[QuerySourceEntry, ...]
    selected_language: str = "en"
    canonical_language: str = "en"
    fallback_to_canonical: bool = False

    @property
    def contents(self) -> tuple[str, ...]:
        """Return selected entry texts in their persisted order."""
        return tuple(
            entry.content_for(
                self.selected_language,
                canonical_language=self.canonical_language,
                fallback_to_canonical=self.fallback_to_canonical,
            )
            for entry in self.entries
        )

    @property
    def content(self) -> str:
        """Return the provider-facing text used by legacy query callers."""
        return "\n\n".join(self.contents)


def _query_source_language(value: object, *, field: str) -> str:
    """Validate one normalized, BCP-47-like language identifier."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a normalized language identifier.")
    parts = value.split("-")
    if (
        not 2 <= len(parts[0]) <= 8
        or not parts[0].isascii()
        or not parts[0].isalpha()
        or parts[0] != parts[0].lower()
        or any(
            not 1 <= len(part) <= 8
            or not part.isascii()
            or not part.isalnum()
            or part != part.lower()
            for part in parts[1:]
        )
    ):
        raise ValueError(f"{field} must be a normalized language identifier.")
    return value


def _query_source_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text.")
    return value


def _query_source_entry_key(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 200
        or any(
            not character.isprintable()
            or unicodedata.category(character) in {"Cc", "Cf", "Cs"}
            for character in value
        )
    ):
        raise ValueError(
            "Query source entry key must be 1-200 visible characters "
            "without surrounding whitespace."
        )
    return value


def _query_source_entry_uid(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Query source entry uid must be a canonical UUID.")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Query source entry uid must be a canonical UUID.") from error
    canonical = str(parsed)
    if value != canonical:
        raise ValueError("Query source entry uid must be a canonical UUID.")
    return canonical


def _query_source_translations(
    value: object,
    *,
    canonical_language: str,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        raise ValueError("Query source entry translations must be an object.")
    translations: list[tuple[str, str]] = []
    for raw_language, raw_content in value.items():
        language = _query_source_language(
            raw_language,
            field="Query source translation language",
        )
        if language == canonical_language:
            raise ValueError(
                "Query source translations must not repeat the canonical "
                f"'{canonical_language}' content."
            )
        translations.append(
            (
                language,
                _query_source_text(
                    raw_content,
                    field=f"Query source '{language}' translation",
                ),
            )
        )
    return tuple(sorted(translations))


def _query_source_entry_from_record(
    value: object,
    *,
    canonical_language: str,
    allow_missing_uid: bool,
) -> QuerySourceEntry:
    if isinstance(value, QuerySourceEntry):
        value = {
            "uid": value.uid,
            "key": value.key,
            "canonical_content": value.canonical_content,
            "translations": dict(value.translations),
        }
    if not isinstance(value, dict):
        raise ValueError("Each query source entry must be an object.")
    allowed = {"uid", "key", "canonical_content", "translations"}
    required = {"key", "canonical_content"}
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise ValueError(
            "Query source entry fields must be key, canonical_content, "
            "optional uid, and optional translations."
        )
    raw_uid = value.get("uid")
    if raw_uid is None:
        if not allow_missing_uid:
            raise ValueError("Persisted query source entry has no uid.")
        entry_uid = str(uuid.uuid4())
    else:
        entry_uid = _query_source_entry_uid(raw_uid)
    translations = _query_source_translations(
        value.get("translations", {}),
        canonical_language=canonical_language,
    )
    return QuerySourceEntry(
        uid=entry_uid,
        key=_query_source_entry_key(value.get("key")),
        canonical_content=_query_source_text(
            value.get("canonical_content"),
            field="Query source canonical content",
        ),
        translations=translations,
    )


class _QuerySourceStoreMixin:
    @staticmethod
    def _canonical_query_source_uid(source_uid: str) -> str:
        if not isinstance(source_uid, str):
            raise ValueError("Query source uid must be a canonical UUID.")
        try:
            parsed = uuid.UUID(source_uid)
        except (AttributeError, TypeError, ValueError) as e:
            raise ValueError("Query source uid must be a canonical UUID.") from e
        canonical = str(parsed)
        if source_uid != canonical:
            raise ValueError("Query source uid must be a canonical UUID.")
        return canonical

    def _query_source_dir(self, source_uid: str) -> Path:
        canonical = self._canonical_query_source_uid(source_uid)
        if self.query_sources_dir.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        source_dir = self.query_sources_dir / canonical
        if source_dir.is_symlink():
            raise ValueError("Query source directory cannot be a symbolic link.")
        root = self.query_sources_dir.resolve()
        resolved = source_dir.resolve(strict=False)
        if root not in resolved.parents:
            raise ValueError("Query source path escapes query source storage.")
        return source_dir

    def _query_source_file(self, source_uid: str) -> Path:
        source_file = self._query_source_dir(source_uid) / "source.json"
        if source_file.is_symlink():
            raise ValueError("Query source file cannot be a symbolic link.")
        return source_file

    def create_query_source(self, name: str, content: str) -> QuerySource:
        """
        Store a concealed research source outside normal Context storage.

        This is UI-level concealment for a study prototype, not a security
        boundary. The local user can still read files under ~/.mem.
        """
        return self.create_bilingual_query_source(
            name,
            entries=(
                {
                    "key": "content",
                    "canonical_content": content,
                },
            ),
        )

    @_profile_write_guarded
    def create_bilingual_query_source(
        self,
        name: str,
        entries: Iterable[QuerySourceEntry | dict[str, object]],
    ) -> QuerySource:
        """Store stable English entries and optional concealed translations.

        The method name reflects the study-fixture use case, while the record
        format accepts more than one non-English language. Entry ``uid`` values
        are generated when omitted and may be supplied as canonical UUIDs by a
        deterministic fixture builder.
        """
        validate_portable_context_name(name)
        canonical_language = "en"
        try:
            raw_entries = tuple(entries)
        except TypeError as error:
            raise ValueError("Query source entries must be iterable.") from error
        if not raw_entries:
            raise ValueError("Query source must contain at least one entry.")
        source_entries = tuple(
            _query_source_entry_from_record(
                entry,
                canonical_language=canonical_language,
                allow_missing_uid=True,
            )
            for entry in raw_entries
        )
        entry_uids = [entry.uid for entry in source_entries]
        entry_keys = [entry.key for entry in source_entries]
        if len(entry_uids) != len(set(entry_uids)):
            raise ValueError("Query source entry uids must be unique.")
        if len(entry_keys) != len(set(entry_keys)):
            raise ValueError("Query source entry keys must be unique.")
        if self.query_sources_dir.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        self.query_sources_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.query_sources_dir, 0o700)

        source = QuerySource(
            uid=str(uuid.uuid4()),
            name=name,
            entries=source_entries,
        )
        source_dir = self._query_source_dir(source.uid)
        source_file = self._query_source_file(source.uid)
        source_dir.mkdir(mode=0o700)
        os.chmod(source_dir, 0o700)
        try:
            with open(source_file, "x", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": 2,
                        "uid": source.uid,
                        "name": source.name,
                        "canonical_language": canonical_language,
                        "entries": [
                            {
                                "uid": entry.uid,
                                "key": entry.key,
                                "canonical_content": entry.canonical_content,
                                "translations": dict(entry.translations),
                            }
                            for entry in source.entries
                        ],
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
                f.flush()
                os.fsync(f.fileno())
            os.chmod(source_file, 0o600)
        except Exception:
            if source_file.exists() and not source_file.is_symlink():
                source_file.unlink()
            source_dir.rmdir()
            raise
        return source

    def load_query_source(
        self,
        source_uid: str,
        *,
        expected_name: str,
        language: str = "en",
        fallback_to_canonical: bool = False,
    ) -> QuerySource:
        """Load one concealed source, selecting entry text in ``language``.

        A requested translation must cover every entry. Callers that
        deliberately accept a mixed-language result may opt into canonical
        English fallback explicitly.
        """
        canonical_source_uid = self._canonical_query_source_uid(source_uid)
        _context_name_parts(expected_name)
        selected_language = _query_source_language(
            language,
            field="Query source language",
        )
        if not isinstance(fallback_to_canonical, bool):
            raise ValueError("Query source fallback_to_canonical must be a boolean.")
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        with open(source_file, encoding="utf-8") as f:
            data = json.load(f, object_pairs_hook=_reject_duplicate_json_keys)
        if not isinstance(data, dict):
            raise ValueError("Query source identity or structure is invalid.")
        schema_version = data.get("schema_version")
        if schema_version == 1 and type(schema_version) is int:
            if set(data) != {"schema_version", "uid", "name", "content"}:
                raise ValueError("Query source identity or structure is invalid.")
            content = _query_source_text(
                data.get("content"),
                field="Query source content",
            )
            legacy_entry_uid = str(
                uuid.uuid5(
                    uuid.UUID(canonical_source_uid),
                    "legacy-query-source-content",
                )
            )
            canonical_language = "en"
            entries = (
                QuerySourceEntry(
                    uid=legacy_entry_uid,
                    key="legacy-content",
                    canonical_content=content,
                ),
            )
        elif schema_version == 2 and type(schema_version) is int:
            if set(data) != {
                "schema_version",
                "uid",
                "name",
                "canonical_language",
                "entries",
            }:
                raise ValueError("Query source identity or structure is invalid.")
            canonical_language = _query_source_language(
                data.get("canonical_language"),
                field="Query source canonical language",
            )
            if canonical_language != "en":
                raise ValueError(
                    "Query source canonical language must be English ('en')."
                )
            raw_entries = data.get("entries")
            if not isinstance(raw_entries, list) or not raw_entries:
                raise ValueError(
                    "Query source must contain at least one persisted entry."
                )
            entries = tuple(
                _query_source_entry_from_record(
                    entry,
                    canonical_language=canonical_language,
                    allow_missing_uid=False,
                )
                for entry in raw_entries
            )
            entry_uids = [entry.uid for entry in entries]
            entry_keys = [entry.key for entry in entries]
            if len(entry_uids) != len(set(entry_uids)):
                raise ValueError("Query source entry uids must be unique.")
            if len(entry_keys) != len(set(entry_keys)):
                raise ValueError("Query source entry keys must be unique.")
        else:
            raise ValueError("Query source identity or structure is invalid.")
        if data.get("uid") != canonical_source_uid or data.get("name") != expected_name:
            raise ValueError("Query source identity or structure is invalid.")

        # Resolve the full source now so an absent translation fails before a
        # partially usable QuerySource can reach the provider.
        for entry in entries:
            entry.content_for(
                selected_language,
                canonical_language=canonical_language,
                fallback_to_canonical=fallback_to_canonical,
            )
        return QuerySource(
            uid=data["uid"],
            name=data["name"],
            entries=entries,
            selected_language=selected_language,
            canonical_language=canonical_language,
            fallback_to_canonical=fallback_to_canonical,
        )

    @_profile_write_guarded
    def delete_query_source(self, source_uid: str) -> None:
        """Delete one exact hidden source, used to roll back failed setup."""
        source_dir = self._query_source_dir(source_uid)
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        source_file.unlink()
        source_dir.rmdir()
