"""Command-independent catalog of translations for direct Memory content."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from typing import Iterable
import unicodedata
import uuid

from memcommit.core.context import Context, Memory


TRANSLATION_CATALOG_CONTRACT_VERSION = "translate-v2"
TRANSLATION_CATALOG_CONTEXT_NAME_LIMIT = 20_000
TRANSLATION_CATALOG_SOURCE_UID_LIMIT = 4_096
TRANSLATION_TARGET_CHAR_LIMIT = 500
TRANSLATED_CONTENT_CHAR_LIMIT = 1_000_000

TRANSLATION_ORIGIN_PROVIDER = "PROVIDER"
TRANSLATION_ORIGIN_IMPORTED = "IMPORTED"
TRANSLATION_ORIGIN_MANUAL = "MANUAL"
TRANSLATION_ORIGINS = frozenset(
    {
        TRANSLATION_ORIGIN_PROVIDER,
        TRANSLATION_ORIGIN_IMPORTED,
        TRANSLATION_ORIGIN_MANUAL,
    }
)
TRANSLATION_REVIEW_UNREVIEWED = "UNREVIEWED"
TRANSLATION_REVIEW_VERIFIED = "VERIFIED"
TRANSLATION_REVIEW_STATUSES = frozenset(
    {
        TRANSLATION_REVIEW_UNREVIEWED,
        TRANSLATION_REVIEW_VERIFIED,
    }
)


class TranslationCatalogError(ValueError):
    """Invalid or internally inconsistent Memory translation catalog."""


def _string(
    value: object,
    label: str,
    *,
    limit: int,
    allow_empty: bool = False,
) -> str:
    if (
        not isinstance(value, str)
        or (not allow_empty and not value)
        or len(value) > limit
    ):
        raise TranslationCatalogError(f"Invalid {label}.")
    return value


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(value, label, limit=36)
    try:
        canonical = str(uuid.UUID(text))
    except (AttributeError, TypeError, ValueError) as error:
        raise TranslationCatalogError(f"Invalid {label}.") from error
    if canonical != text:
        raise TranslationCatalogError(f"Invalid {label}.")
    return text


def validate_sha256(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise TranslationCatalogError(f"Invalid {label}.")
    return text


def validate_translation_source_uid(value: object, label: str) -> str:
    text = _string(
        value,
        label,
        limit=TRANSLATION_CATALOG_SOURCE_UID_LIMIT,
    )
    if any(not character.isprintable() for character in text):
        raise TranslationCatalogError(f"Invalid {label}.")
    return text


def _context_name(value: object) -> str:
    text = _string(
        value,
        "translation catalog Context name",
        limit=TRANSLATION_CATALOG_CONTEXT_NAME_LIMIT,
    )
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise TranslationCatalogError("Invalid translation catalog Context name.")
    return text


def validate_translation_target(value: object) -> str:
    text = _string(
        value,
        "translation catalog semantic target",
        limit=TRANSLATION_TARGET_CHAR_LIMIT,
    )
    if text.strip() != text or any(not character.isprintable() for character in text):
        raise TranslationCatalogError("Invalid translation catalog semantic target.")
    return text


def validate_translated_content(value: object) -> str:
    text = _string(
        value,
        "translation catalog translated content",
        limit=TRANSLATED_CONTENT_CHAR_LIMIT,
    )
    if not text.strip() or any(
        unicodedata.category(character) in {"Cc", "Cs"}
        and character not in {"\n", "\t"}
        for character in text
    ):
        raise TranslationCatalogError("Invalid translation catalog translated content.")
    return text


def _timestamp(value: object) -> str:
    text = _string(
        value,
        "translation catalog creation time",
        limit=80,
    )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise TranslationCatalogError(
            "Invalid translation catalog creation time."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TranslationCatalogError("Invalid translation catalog creation time.")
    return text


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TranslationCatalogError(f"Invalid {label}.")
    return value


def _entry_origin(value: object) -> str:
    origin = _string(
        value,
        "translation catalog entry origin",
        limit=40,
    )
    if origin not in TRANSLATION_ORIGINS:
        raise TranslationCatalogError("Invalid translation catalog entry origin.")
    return origin


def _review_status(value: object) -> str:
    status = _string(
        value,
        "translation catalog review status",
        limit=40,
    )
    if status not in TRANSLATION_REVIEW_STATUSES:
        raise TranslationCatalogError("Invalid translation catalog review status.")
    return status


def translation_content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def direct_source_memories(
    context: Context,
    selected_memory_uid: str | None,
) -> tuple[Memory, ...] | None:
    if not isinstance(context, Context):
        return None
    if selected_memory_uid is None:
        return tuple(item for item in context.iter_items() if isinstance(item, Memory))
    source = context.memories.get(selected_memory_uid)
    if not isinstance(source, Memory):
        return None
    return (source,)


def _catalog_contract_version(value: object) -> str:
    version = _string(
        value,
        "translation catalog contract version",
        limit=80,
    )
    if version != TRANSLATION_CATALOG_CONTRACT_VERSION:
        raise TranslationCatalogError(
            "Unsupported translation catalog contract version."
        )
    return version


def _optional_digest(value: object, label: str) -> str | None:
    if value is None:
        return None
    return validate_sha256(value, label)


def _timestamp_value(value: str) -> datetime:
    # Every caller has already passed through _timestamp. Keeping comparison
    # here avoids normalizing a person's original offset representation.
    return datetime.fromisoformat(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TranslationProviderVariant:
    """One provider result with the complete frame evidence it depended on."""

    source_sha256: str
    context_digest: str
    translated_content: str
    response_sha256: str
    generated_at: str

    def __post_init__(self) -> None:
        validate_sha256(self.source_sha256, "provider source content digest")
        validate_sha256(self.context_digest, "provider source Context digest")
        validate_translated_content(self.translated_content)
        validate_sha256(self.response_sha256, "provider response digest")
        _timestamp(self.generated_at)

    def matches(self, memory: Memory, context_digest: str) -> bool:
        validate_sha256(context_digest, "current source Context digest")
        return (
            self.source_sha256 == translation_content_digest(memory.content)
            and self.context_digest == context_digest
        )


@dataclass(frozen=True)
class TranslationCuratedVariant:
    """A person-controlled translation protected from provider refresh."""

    source_sha256: str
    translated_content: str
    origin: str
    review_status: str
    reviewed_content_sha256: str | None
    evidence_sha256: str | None
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        validate_sha256(self.source_sha256, "curated source content digest")
        validate_translated_content(self.translated_content)
        _entry_origin(self.origin)
        _review_status(self.review_status)
        reviewed = _optional_digest(
            self.reviewed_content_sha256,
            "curated reviewed-content digest",
        )
        _optional_digest(
            self.evidence_sha256,
            "curated origin evidence digest",
        )
        created = _timestamp(self.created_at)
        updated = _timestamp(self.updated_at)
        expected_reviewed = (
            translation_content_digest(self.translated_content)
            if self.review_status == TRANSLATION_REVIEW_VERIFIED
            else None
        )
        if reviewed != expected_reviewed:
            raise TranslationCatalogError(
                "A verified curated translation must bind the exact reviewed "
                "text, and an unreviewed translation cannot retain that digest."
            )
        if self.origin == TRANSLATION_ORIGIN_PROVIDER and self.evidence_sha256 is None:
            raise TranslationCatalogError(
                "A provider-origin curated translation requires provider "
                "response evidence."
            )
        if _timestamp_value(updated) < _timestamp_value(created):
            raise TranslationCatalogError(
                "A curated translation cannot be updated before it was created."
            )

    def matches(self, memory: Memory) -> bool:
        return self.source_sha256 == translation_content_digest(memory.content)


@dataclass(frozen=True)
class EffectiveTranslation:
    """The current representation selected from a catalog entry."""

    source_uid: str
    source_sha256: str
    translated_content: str
    origin: str
    review_status: str
    evidence_sha256: str | None
    updated_at: str
    curated: bool


@dataclass(frozen=True)
class TranslationCatalogEntry:
    """One source UID with replaceable provider and protected curated layers."""

    source_uid: str
    provider: TranslationProviderVariant | None
    curated: TranslationCuratedVariant | None

    def __post_init__(self) -> None:
        validate_translation_source_uid(
            self.source_uid, "translation catalog source Memory uid"
        )
        if self.provider is not None and not isinstance(
            self.provider,
            TranslationProviderVariant,
        ):
            raise TranslationCatalogError(
                "Invalid translation catalog provider variant."
            )
        if self.curated is not None and not isinstance(
            self.curated,
            TranslationCuratedVariant,
        ):
            raise TranslationCatalogError(
                "Invalid translation catalog curated variant."
            )
        if self.provider is None and self.curated is None:
            raise TranslationCatalogError(
                "A translation catalog entry requires a provider or curated variant."
            )

    def effective(
        self,
        memory: Memory,
        context_digest: str,
    ) -> EffectiveTranslation | None:
        if self.curated is not None and self.curated.matches(memory):
            return EffectiveTranslation(
                source_uid=self.source_uid,
                source_sha256=self.curated.source_sha256,
                translated_content=self.curated.translated_content,
                origin=self.curated.origin,
                review_status=self.curated.review_status,
                evidence_sha256=self.curated.evidence_sha256,
                updated_at=self.curated.updated_at,
                curated=True,
            )
        if self.provider is not None and self.provider.matches(
            memory,
            context_digest,
        ):
            return EffectiveTranslation(
                source_uid=self.source_uid,
                source_sha256=self.provider.source_sha256,
                translated_content=self.provider.translated_content,
                origin=TRANSLATION_ORIGIN_PROVIDER,
                review_status=TRANSLATION_REVIEW_UNREVIEWED,
                evidence_sha256=self.provider.response_sha256,
                updated_at=self.provider.generated_at,
                curated=False,
            )
        return None


def order_catalog_entries(
    context: Context,
    by_uid: dict[str, TranslationCatalogEntry],
    prior_order: Iterable[str] = (),
) -> tuple[TranslationCatalogEntry, ...]:
    ordered: list[TranslationCatalogEntry] = []
    seen: set[str] = set()
    for item in context.iter_items():
        if isinstance(item, Memory) and item.uid in by_uid:
            ordered.append(by_uid[item.uid])
            seen.add(item.uid)
    # A source edit keeps the same UID and therefore retains its stale curated
    # layer for explicit review. A removed UID is different: retaining it
    # would leave translation text with no reachable source or reset path.
    for uid in prior_order:
        if (
            uid in context.memories
            and isinstance(context.memories[uid], Memory)
            and uid in by_uid
            and uid not in seen
        ):
            ordered.append(by_uid[uid])
            seen.add(uid)
    for uid, entry in by_uid.items():
        if (
            uid in context.memories
            and isinstance(context.memories[uid], Memory)
            and uid not in seen
        ):
            ordered.append(entry)
    return tuple(ordered)


@dataclass(frozen=True)
class MemoryTranslationCatalog:
    """One authoritative same-UID translation catalog per Context and target."""

    context_uid: str
    context_name: str
    target_language: str
    created_at: str
    updated_at: str
    revision: int
    contract_version: str
    entries: tuple[TranslationCatalogEntry, ...]

    def __post_init__(self) -> None:
        _canonical_uuid(self.context_uid, "translation catalog Context uid")
        _context_name(self.context_name)
        validate_translation_target(self.target_language)
        created = _timestamp(self.created_at)
        updated = _timestamp(self.updated_at)
        _positive_int(self.revision, "translation catalog revision")
        _catalog_contract_version(self.contract_version)
        if not isinstance(self.entries, tuple) or any(
            not isinstance(entry, TranslationCatalogEntry) for entry in self.entries
        ):
            raise TranslationCatalogError("Invalid translation catalog entries.")
        source_uids = [entry.source_uid for entry in self.entries]
        if len(source_uids) != len(set(source_uids)):
            raise TranslationCatalogError(
                "Duplicate translation catalog source Memory uid."
            )
        if _timestamp_value(updated) < _timestamp_value(created):
            raise TranslationCatalogError(
                "A translation catalog cannot be updated before creation."
            )

    def _validate_context_identity(self, context: Context) -> None:
        if not isinstance(context, Context) or (
            self.context_uid != context.uid or self.context_name != context.name
        ):
            raise TranslationCatalogError(
                "The translation catalog does not belong to this Context."
            )

    def entry_for(self, source_uid: str) -> TranslationCatalogEntry | None:
        return next(
            (entry for entry in self.entries if entry.source_uid == source_uid),
            None,
        )

    @classmethod
    def empty(
        cls,
        context: Context,
        target_language: str,
        *,
        created_at: str | None = None,
    ) -> "MemoryTranslationCatalog":
        """Create an unsaved catalog seed for manual or imported content."""
        if not isinstance(context, Context):
            raise TranslationCatalogError(
                "Translation catalog source must be a Context."
            )
        timestamp = _timestamp(created_at if created_at is not None else _now())
        return cls(
            context_uid=context.uid,
            context_name=context.name,
            target_language=validate_translation_target(target_language),
            created_at=timestamp,
            updated_at=timestamp,
            revision=1,
            contract_version=TRANSLATION_CATALOG_CONTRACT_VERSION,
            entries=(),
        )

    def with_curated(
        self,
        context: Context,
        source_uid: str,
        translated_content: str,
        *,
        origin: str,
        review_status: str = TRANSLATION_REVIEW_UNREVIEWED,
        evidence_sha256: str | None = None,
        updated_at: str | None = None,
    ) -> "MemoryTranslationCatalog":
        self._validate_context_identity(context)
        uid = validate_translation_source_uid(source_uid, "curated source Memory uid")
        source = context.memories.get(uid)
        if not isinstance(source, Memory):
            raise TranslationCatalogError(
                "A curated translation requires a directly owned source Memory."
            )
        content = validate_translated_content(translated_content)
        checked_origin = _entry_origin(origin)
        checked_status = _review_status(review_status)
        checked_evidence = _optional_digest(
            evidence_sha256,
            "curated origin evidence digest",
        )
        timestamp = _timestamp(updated_at if updated_at is not None else _now())
        previous = self.entry_for(uid)
        source_sha256 = translation_content_digest(source.content)
        reviewed_content_sha256 = (
            translation_content_digest(content)
            if checked_status == TRANSLATION_REVIEW_VERIFIED
            else None
        )
        if previous is not None and previous.curated is not None:
            prior = previous.curated
            if (
                prior.source_sha256 == source_sha256
                and prior.translated_content == content
                and prior.origin == checked_origin
                and prior.review_status == checked_status
                and prior.evidence_sha256 == checked_evidence
            ):
                return self
            curated_created_at = (
                prior.created_at if prior.source_sha256 == source_sha256 else timestamp
            )
        else:
            curated_created_at = timestamp
        curated = TranslationCuratedVariant(
            source_sha256=source_sha256,
            translated_content=content,
            origin=checked_origin,
            review_status=checked_status,
            reviewed_content_sha256=reviewed_content_sha256,
            evidence_sha256=checked_evidence,
            created_at=curated_created_at,
            updated_at=timestamp,
        )
        by_uid = {entry.source_uid: entry for entry in self.entries}
        by_uid[uid] = TranslationCatalogEntry(
            source_uid=uid,
            provider=(None if previous is None else previous.provider),
            curated=curated,
        )
        return replace(
            self,
            updated_at=timestamp,
            revision=self.revision + 1,
            entries=order_catalog_entries(
                context,
                by_uid,
                (entry.source_uid for entry in self.entries),
            ),
        )

    def with_review_status(
        self,
        context: Context,
        context_digest: str,
        source_uid: str,
        review_status: str,
        *,
        updated_at: str | None = None,
    ) -> "MemoryTranslationCatalog":
        self._validate_context_identity(context)
        status = _review_status(review_status)
        uid = validate_translation_source_uid(source_uid, "reviewed source Memory uid")
        source = context.memories.get(uid)
        entry = self.entry_for(uid)
        if not isinstance(source, Memory) or entry is None:
            raise TranslationCatalogError(
                "Review requires a current directly owned translated Memory."
            )
        if entry.curated is not None and not entry.curated.matches(source):
            raise TranslationCatalogError(
                "A stale curated translation must be edited or reset before "
                "reviewing a replacement."
            )
        effective = entry.effective(source, context_digest)
        if effective is None:
            raise TranslationCatalogError(
                "The translation is stale and cannot be reviewed."
            )
        if entry.curated is None and status == TRANSLATION_REVIEW_UNREVIEWED:
            return self
        timestamp = _timestamp(updated_at if updated_at is not None else _now())
        origin = effective.origin
        evidence = effective.evidence_sha256
        return self.with_curated(
            context,
            uid,
            effective.translated_content,
            origin=origin,
            review_status=status,
            evidence_sha256=evidence,
            updated_at=timestamp,
        )

    def without_curated(
        self,
        context: Context,
        source_uid: str,
        *,
        updated_at: str | None = None,
    ) -> "MemoryTranslationCatalog":
        self._validate_context_identity(context)
        uid = validate_translation_source_uid(source_uid, "reset source Memory uid")
        source = context.memories.get(uid)
        if not isinstance(source, Memory):
            raise TranslationCatalogError(
                "Reset requires a directly owned source Memory."
            )
        previous = self.entry_for(uid)
        if previous is None or previous.curated is None:
            return self
        by_uid = {entry.source_uid: entry for entry in self.entries}
        if previous.provider is None:
            del by_uid[uid]
        else:
            by_uid[uid] = TranslationCatalogEntry(
                source_uid=uid,
                provider=previous.provider,
                curated=None,
            )
        timestamp = _timestamp(updated_at if updated_at is not None else _now())
        return replace(
            self,
            updated_at=timestamp,
            revision=self.revision + 1,
            entries=order_catalog_entries(
                context,
                by_uid,
                (entry.source_uid for entry in self.entries),
            ),
        )

    def without_removed_sources(
        self,
        context: Context,
        *,
        updated_at: str | None = None,
    ) -> "MemoryTranslationCatalog":
        """Drop entries whose directly owned source Memory was removed.

        Stale text for an edited source remains reviewable because its UID is
        still present. Removed-source text has no valid selector or reset
        path, so keeping it would create an inaccessible sidecar orphan.
        """
        self._validate_context_identity(context)
        retained = tuple(
            entry
            for entry in self.entries
            if isinstance(context.memories.get(entry.source_uid), Memory)
        )
        if len(retained) == len(self.entries):
            return self
        timestamp = _timestamp(updated_at if updated_at is not None else _now())
        by_uid = {entry.source_uid: entry for entry in retained}
        return replace(
            self,
            updated_at=timestamp,
            revision=self.revision + 1,
            entries=order_catalog_entries(
                context,
                by_uid,
                (entry.source_uid for entry in self.entries),
            ),
        )

    def effective_entries(
        self,
        context: Context,
        context_digest: str,
        selector: str | None = None,
    ) -> tuple[EffectiveTranslation, ...]:
        self._validate_context_identity(context)
        memories = direct_source_memories(context, selector)
        if memories is None:
            raise TranslationCatalogError(
                "The translation selector is not a direct source Memory."
            )
        by_uid = {entry.source_uid: entry for entry in self.entries}
        result: list[EffectiveTranslation] = []
        for memory in memories:
            entry = by_uid.get(memory.uid)
            if entry is None:
                continue
            effective = entry.effective(memory, context_digest)
            if effective is not None:
                result.append(effective)
        return tuple(result)

    def missing_source_uids(
        self,
        context: Context,
        context_digest: str,
        selector: str | None = None,
    ) -> tuple[str, ...]:
        self._validate_context_identity(context)
        memories = direct_source_memories(context, selector)
        if memories is None:
            raise TranslationCatalogError(
                "The translation selector is not a direct source Memory."
            )
        effective = {
            entry.source_uid
            for entry in self.effective_entries(
                context,
                context_digest,
                selector,
            )
        }
        return tuple(memory.uid for memory in memories if memory.uid not in effective)

    def stale_curated_uids(self, context: Context) -> tuple[str, ...]:
        self._validate_context_identity(context)
        result: list[str] = []
        for entry in self.entries:
            if entry.curated is None:
                continue
            source = context.memories.get(entry.source_uid)
            if not isinstance(source, Memory) or not entry.curated.matches(source):
                result.append(entry.source_uid)
        return tuple(result)

    def covers(
        self,
        context: Context,
        context_digest: str,
        selector: str | None = None,
    ) -> bool:
        try:
            return not self.missing_source_uids(
                context,
                context_digest,
                selector,
            )
        except TranslationCatalogError:
            return False
