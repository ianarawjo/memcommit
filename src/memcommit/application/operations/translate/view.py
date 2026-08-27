"""Strict durable projections of translated direct Memory content.

A translation view is saved provider output, but it is not a Context or a
collection of new Memory occurrences.  It therefore carries no artifact UID
and its entries retain only the existing source Memory UIDs.  A fresh
operation UID is allocated only when a caller explicitly converts the view
back into a materializable :class:`TranslationPlan`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable
import unicodedata
import uuid

from memcommit.core.context import Context, Memory
from memcommit.persistence.store import context_record_digest
from memcommit.application.operations.translate.runtime import (
    TRANSLATED_CONTENT_CHAR_LIMIT,
    TRANSLATION_TARGET_CHAR_LIMIT,
    TranslationPlan,
    TranslationProposal,
    translation_plan_matches_context,
)


TRANSLATION_VIEW_SCHEMA_VERSION = 1
TRANSLATION_VIEW_CONTRACT_VERSION = "translate-v1"
TRANSLATION_CATALOG_SCHEMA_VERSION = 2
TRANSLATION_CATALOG_CONTRACT_VERSION = "translate-v2"
TRANSLATION_VIEW_NAME_LIMIT = 20_000
TRANSLATION_VIEW_SOURCE_UID_LIMIT = 4_096

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


class TranslationViewError(ValueError):
    """Invalid, unsupported, or internally inconsistent translation view."""


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise TranslationViewError(f"Invalid {label}.")
    return value


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
        raise TranslationViewError(f"Invalid {label}.")
    return value


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(value, label, limit=36)
    try:
        canonical = str(uuid.UUID(text))
    except (AttributeError, TypeError, ValueError) as error:
        raise TranslationViewError(f"Invalid {label}.") from error
    if canonical != text:
        raise TranslationViewError(f"Invalid {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise TranslationViewError(f"Invalid {label}.")
    return text


def _source_uid(value: object, label: str) -> str:
    text = _string(
        value,
        label,
        limit=TRANSLATION_VIEW_SOURCE_UID_LIMIT,
    )
    if any(not character.isprintable() for character in text):
        raise TranslationViewError(f"Invalid {label}.")
    return text


def _context_name(value: object) -> str:
    text = _string(
        value,
        "translation view Context name",
        limit=TRANSLATION_VIEW_NAME_LIMIT,
    )
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in text
    ):
        raise TranslationViewError(
            "Invalid translation view Context name."
        )
    return text


def _target_language(value: object) -> str:
    text = _string(
        value,
        "translation view semantic target",
        limit=TRANSLATION_TARGET_CHAR_LIMIT,
    )
    if text.strip() != text or any(
        not character.isprintable() for character in text
    ):
        raise TranslationViewError(
            "Invalid translation view semantic target."
        )
    return text


def _translated_content(value: object) -> str:
    text = _string(
        value,
        "translation view translated content",
        limit=TRANSLATED_CONTENT_CHAR_LIMIT,
    )
    if (
        not text.strip()
        or any(
            unicodedata.category(character) in {"Cc", "Cs"}
            and character not in {"\n", "\t"}
            for character in text
        )
    ):
        raise TranslationViewError(
            "Invalid translation view translated content."
        )
    return text


def _timestamp(value: object) -> str:
    text = _string(
        value,
        "translation view creation time",
        limit=80,
    )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise TranslationViewError(
            "Invalid translation view creation time."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TranslationViewError(
            "Invalid translation view creation time."
        )
    return text


def _contract_version(value: object) -> str:
    version = _string(
        value,
        "translation view contract version",
        limit=80,
    )
    if version != TRANSLATION_VIEW_CONTRACT_VERSION:
        raise TranslationViewError(
            "Unsupported translation view contract version."
        )
    return version


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TranslationViewError(f"Invalid {label}.")
    return value


def _entry_origin(value: object) -> str:
    origin = _string(
        value,
        "translation view entry origin",
        limit=40,
    )
    if origin not in TRANSLATION_ORIGINS:
        raise TranslationViewError(
            "Invalid translation view entry origin."
        )
    return origin


def _review_status(value: object) -> str:
    status = _string(
        value,
        "translation view review status",
        limit=40,
    )
    if status not in TRANSLATION_REVIEW_STATUSES:
        raise TranslationViewError(
            "Invalid translation view review status."
        )
    return status


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _direct_source_memories(
    context: Context,
    selected_memory_uid: str | None,
) -> tuple[Memory, ...] | None:
    if not isinstance(context, Context):
        return None
    if selected_memory_uid is None:
        return tuple(
            item
            for item in context.iter_items()
            if isinstance(item, Memory)
        )
    source = context.memories.get(selected_memory_uid)
    if not isinstance(source, Memory):
        return None
    return (source,)


@dataclass(frozen=True)
class TranslationViewEntry:
    """One translated representation anchored to an existing source Memory."""

    source_uid: str
    source_sha256: str
    translated_content: str

    def __post_init__(self) -> None:
        _source_uid(
            self.source_uid,
            "translation view source Memory uid",
        )
        _digest(
            self.source_sha256,
            "translation view source content digest",
        )
        _translated_content(self.translated_content)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_uid": self.source_uid,
            "source_sha256": self.source_sha256,
            "translated_content": self.translated_content,
        }

    @classmethod
    def from_dict(cls, value: object) -> "TranslationViewEntry":
        data = _exact_dict(
            value,
            {
                "source_uid",
                "source_sha256",
                "translated_content",
            },
            "translation view entry",
        )
        return cls(
            source_uid=_source_uid(
                data["source_uid"],
                "translation view source Memory uid",
            ),
            source_sha256=_digest(
                data["source_sha256"],
                "translation view source content digest",
            ),
            translated_content=_translated_content(
                data["translated_content"]
            ),
        )


@dataclass(frozen=True)
class TranslationView:
    """Saved translated text bound to one direct Context and language lens."""

    context_uid: str
    context_name: str
    context_digest: str
    target_language: str
    selected_memory_uid: str | None
    created_at: str
    contract_version: str
    provider_response_sha256: str | None
    entries: tuple[TranslationViewEntry, ...]

    def __post_init__(self) -> None:
        _canonical_uuid(
            self.context_uid,
            "translation view Context uid",
        )
        _context_name(self.context_name)
        _digest(
            self.context_digest,
            "translation view Context record digest",
        )
        _target_language(self.target_language)
        if self.selected_memory_uid is not None:
            _source_uid(
                self.selected_memory_uid,
                "translation view selected source Memory uid",
            )
        _timestamp(self.created_at)
        _contract_version(self.contract_version)
        if self.provider_response_sha256 is not None:
            _digest(
                self.provider_response_sha256,
                "translation view provider response digest",
            )
        if (
            not isinstance(self.entries, tuple)
            or any(
                not isinstance(entry, TranslationViewEntry)
                for entry in self.entries
            )
            or not self.entries
        ):
            raise TranslationViewError(
                "A saved translation view requires at least one valid entry."
            )
        source_uids = [entry.source_uid for entry in self.entries]
        if len(source_uids) != len(set(source_uids)):
            raise TranslationViewError(
                "Duplicate translation view source Memory uid."
            )
        if self.selected_memory_uid is not None and (
            len(self.entries) != 1
            or self.entries[0].source_uid
            != self.selected_memory_uid
        ):
            raise TranslationViewError(
                "A selected-Memory translation view must contain exactly "
                "that source Memory."
            )
        if self.provider_response_sha256 is None:
            raise TranslationViewError(
                "A saved translation view requires a provider response digest."
            )

    @classmethod
    def from_translation_plan(
        cls,
        plan: TranslationPlan,
        context: Context,
        *,
        created_at: str | None = None,
        contract_version: str = TRANSLATION_VIEW_CONTRACT_VERSION,
    ) -> "TranslationView":
        """Discard plan identity and save only its exact read projection."""
        if not isinstance(plan, TranslationPlan):
            raise TranslationViewError(
                "Translation view requires a TranslationPlan."
            )
        if not isinstance(context, Context):
            raise TranslationViewError(
                "Translation view source must be a Context."
            )
        if not translation_plan_matches_context(plan, context):
            raise TranslationViewError(
                "The translation plan is stale because the Context changed."
            )

        memories = _direct_source_memories(
            context,
            plan.selected_memory_uid,
        )
        if memories is None:
            raise TranslationViewError(
                "The translation plan does not select a direct source Memory."
            )
        proposals = plan.proposals
        if (
            not isinstance(proposals, tuple)
            or len(proposals) != len(memories)
        ):
            raise TranslationViewError(
                "The translation plan does not cover its exact source scope."
            )
        timestamp = (
            created_at
            if created_at is not None
            else datetime.now(timezone.utc).isoformat()
        )
        entries: list[TranslationViewEntry] = []
        for memory, proposal in zip(memories, proposals, strict=True):
            if (
                not isinstance(proposal, TranslationProposal)
                or proposal.source_uid != memory.uid
                or proposal.source_content != memory.content
            ):
                raise TranslationViewError(
                    "The translation plan does not match its source Memories."
                )
            entries.append(
                TranslationViewEntry(
                    source_uid=memory.uid,
                    source_sha256=_content_digest(memory.content),
                    translated_content=proposal.translated_content,
                )
            )

        # Round-tripping through the strict parser keeps this constructor and
        # disk deserialization on one validation contract without retaining
        # the plan's operation UID.
        return cls.from_dict(
            {
                "schema_version": TRANSLATION_VIEW_SCHEMA_VERSION,
                "context_uid": plan.context_uid,
                "context_name": plan.context_name,
                "context_digest": plan.context_digest,
                "target_language": plan.target_language,
                "selected_memory_uid": plan.selected_memory_uid,
                "created_at": timestamp,
                "contract_version": contract_version,
                "provider_response_sha256": (
                    plan.provider_response_sha256
                ),
                "entries": [entry.to_dict() for entry in entries],
            }
        )

    @classmethod
    def from_plan(
        cls,
        plan: TranslationPlan,
        context: Context,
        *,
        created_at: str | None = None,
        contract_version: str = TRANSLATION_VIEW_CONTRACT_VERSION,
    ) -> "TranslationView":
        """Short alias for :meth:`from_translation_plan`."""
        return cls.from_translation_plan(
            plan,
            context,
            created_at=created_at,
            contract_version=contract_version,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRANSLATION_VIEW_SCHEMA_VERSION,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "target_language": self.target_language,
            "selected_memory_uid": self.selected_memory_uid,
            "created_at": self.created_at,
            "contract_version": self.contract_version,
            "provider_response_sha256": (
                self.provider_response_sha256
            ),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, value: object) -> "TranslationView":
        data = _exact_dict(
            value,
            {
                "schema_version",
                "context_uid",
                "context_name",
                "context_digest",
                "target_language",
                "selected_memory_uid",
                "created_at",
                "contract_version",
                "provider_response_sha256",
                "entries",
            },
            "translation view",
        )
        schema_version = data["schema_version"]
        if (
            type(schema_version) is not int
            or schema_version != TRANSLATION_VIEW_SCHEMA_VERSION
        ):
            raise TranslationViewError(
                "Unsupported translation view schema version."
            )
        raw_entries = data["entries"]
        if not isinstance(raw_entries, list):
            raise TranslationViewError(
                "Invalid translation view entries."
            )
        selected = data["selected_memory_uid"]
        if selected is not None:
            selected = _source_uid(
                selected,
                "translation view selected source Memory uid",
            )
        provider_digest = data["provider_response_sha256"]
        if provider_digest is not None:
            provider_digest = _digest(
                provider_digest,
                "translation view provider response digest",
            )
        return cls(
            context_uid=_canonical_uuid(
                data["context_uid"],
                "translation view Context uid",
            ),
            context_name=_context_name(data["context_name"]),
            context_digest=_digest(
                data["context_digest"],
                "translation view Context record digest",
            ),
            target_language=_target_language(data["target_language"]),
            selected_memory_uid=selected,
            created_at=_timestamp(data["created_at"]),
            contract_version=_contract_version(
                data["contract_version"]
            ),
            provider_response_sha256=provider_digest,
            entries=tuple(
                TranslationViewEntry.from_dict(entry)
                for entry in raw_entries
            ),
        )

    def matches(self, context: Context) -> bool:
        """Return whether this remains an exact projection of ``context``."""
        if not isinstance(context, Context):
            return False
        if (
            self.context_uid != context.uid
            or self.context_name != context.name
            or self.context_digest != context_record_digest(context)
        ):
            return False
        memories = _direct_source_memories(
            context,
            self.selected_memory_uid,
        )
        if memories is None or len(memories) != len(self.entries):
            return False
        return all(
            entry.source_uid == memory.uid
            and entry.source_sha256 == _content_digest(memory.content)
            for memory, entry in zip(memories, self.entries, strict=True)
        )

    def to_translation_plan(self, context: Context) -> TranslationPlan:
        """Create the fresh operation identity used only for materialization."""
        if not self.matches(context):
            raise TranslationViewError(
                "The translation view is stale because the Context changed."
            )
        proposals = tuple(
            TranslationProposal(
                source_uid=entry.source_uid,
                source_content=context.memories[
                    entry.source_uid
                ].content,
                translated_content=entry.translated_content,
            )
            for entry in self.entries
        )
        return TranslationPlan(
            operation_uid=str(uuid.uuid4()),
            context_uid=self.context_uid,
            context_name=self.context_name,
            context_digest=self.context_digest,
            target_language=self.target_language,
            selected_memory_uid=self.selected_memory_uid,
            proposals=proposals,
            provider_response_sha256=self.provider_response_sha256,
        )


def translation_view_record_digest(
    value: TranslationView | dict[str, object],
) -> str:
    """Hash one complete validated view record canonically for slot CAS."""
    record = (
        value.to_dict()
        if isinstance(value, TranslationView)
        else TranslationView.from_dict(value).to_dict()
    )
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _catalog_contract_version(value: object) -> str:
    version = _string(
        value,
        "translation catalog contract version",
        limit=80,
    )
    if version != TRANSLATION_CATALOG_CONTRACT_VERSION:
        raise TranslationViewError(
            "Unsupported translation catalog contract version."
        )
    return version


def _optional_digest(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _digest(value, label)


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
        _digest(self.source_sha256, "provider source content digest")
        _digest(self.context_digest, "provider source Context digest")
        _translated_content(self.translated_content)
        _digest(self.response_sha256, "provider response digest")
        _timestamp(self.generated_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256,
            "context_digest": self.context_digest,
            "translated_content": self.translated_content,
            "response_sha256": self.response_sha256,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, value: object) -> "TranslationProviderVariant":
        data = _exact_dict(
            value,
            {
                "source_sha256",
                "context_digest",
                "translated_content",
                "response_sha256",
                "generated_at",
            },
            "translation provider variant",
        )
        return cls(
            source_sha256=_digest(
                data["source_sha256"],
                "provider source content digest",
            ),
            context_digest=_digest(
                data["context_digest"],
                "provider source Context digest",
            ),
            translated_content=_translated_content(
                data["translated_content"]
            ),
            response_sha256=_digest(
                data["response_sha256"],
                "provider response digest",
            ),
            generated_at=_timestamp(data["generated_at"]),
        )

    def matches(self, context: Context, memory: Memory) -> bool:
        return (
            self.source_sha256 == _content_digest(memory.content)
            and self.context_digest == context_record_digest(context)
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
        _digest(self.source_sha256, "curated source content digest")
        _translated_content(self.translated_content)
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
            _content_digest(self.translated_content)
            if self.review_status == TRANSLATION_REVIEW_VERIFIED
            else None
        )
        if reviewed != expected_reviewed:
            raise TranslationViewError(
                "A verified curated translation must bind the exact reviewed "
                "text, and an unreviewed translation cannot retain that digest."
            )
        if (
            self.origin == TRANSLATION_ORIGIN_PROVIDER
            and self.evidence_sha256 is None
        ):
            raise TranslationViewError(
                "A provider-origin curated translation requires provider "
                "response evidence."
            )
        if _timestamp_value(updated) < _timestamp_value(created):
            raise TranslationViewError(
                "A curated translation cannot be updated before it was created."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256,
            "translated_content": self.translated_content,
            "origin": self.origin,
            "review_status": self.review_status,
            "reviewed_content_sha256": self.reviewed_content_sha256,
            "evidence_sha256": self.evidence_sha256,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: object) -> "TranslationCuratedVariant":
        data = _exact_dict(
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
            "translation curated variant",
        )
        return cls(
            source_sha256=_digest(
                data["source_sha256"],
                "curated source content digest",
            ),
            translated_content=_translated_content(
                data["translated_content"]
            ),
            origin=_entry_origin(data["origin"]),
            review_status=_review_status(data["review_status"]),
            reviewed_content_sha256=_optional_digest(
                data["reviewed_content_sha256"],
                "curated reviewed-content digest",
            ),
            evidence_sha256=_optional_digest(
                data["evidence_sha256"],
                "curated origin evidence digest",
            ),
            created_at=_timestamp(data["created_at"]),
            updated_at=_timestamp(data["updated_at"]),
        )

    def matches(self, memory: Memory) -> bool:
        return self.source_sha256 == _content_digest(memory.content)


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
        _source_uid(self.source_uid, "translation catalog source Memory uid")
        if self.provider is not None and not isinstance(
            self.provider,
            TranslationProviderVariant,
        ):
            raise TranslationViewError(
                "Invalid translation catalog provider variant."
            )
        if self.curated is not None and not isinstance(
            self.curated,
            TranslationCuratedVariant,
        ):
            raise TranslationViewError(
                "Invalid translation catalog curated variant."
            )
        if self.provider is None and self.curated is None:
            raise TranslationViewError(
                "A translation catalog entry requires a provider or curated "
                "variant."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_uid": self.source_uid,
            "provider": (
                None if self.provider is None else self.provider.to_dict()
            ),
            "curated": (
                None if self.curated is None else self.curated.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "TranslationCatalogEntry":
        data = _exact_dict(
            value,
            {"source_uid", "provider", "curated"},
            "translation catalog entry",
        )
        return cls(
            source_uid=_source_uid(
                data["source_uid"],
                "translation catalog source Memory uid",
            ),
            provider=(
                None
                if data["provider"] is None
                else TranslationProviderVariant.from_dict(data["provider"])
            ),
            curated=(
                None
                if data["curated"] is None
                else TranslationCuratedVariant.from_dict(data["curated"])
            ),
        )

    def effective(
        self,
        context: Context,
        memory: Memory,
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
        if self.provider is not None and self.provider.matches(context, memory):
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


def _catalog_entry_order(
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
class TranslationCatalog:
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
        _target_language(self.target_language)
        created = _timestamp(self.created_at)
        updated = _timestamp(self.updated_at)
        _positive_int(self.revision, "translation catalog revision")
        _catalog_contract_version(self.contract_version)
        if (
            not isinstance(self.entries, tuple)
            or any(
                not isinstance(entry, TranslationCatalogEntry)
                for entry in self.entries
            )
        ):
            raise TranslationViewError(
                "Invalid translation catalog entries."
            )
        source_uids = [entry.source_uid for entry in self.entries]
        if len(source_uids) != len(set(source_uids)):
            raise TranslationViewError(
                "Duplicate translation catalog source Memory uid."
            )
        if _timestamp_value(updated) < _timestamp_value(created):
            raise TranslationViewError(
                "A translation catalog cannot be updated before creation."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TRANSLATION_CATALOG_SCHEMA_VERSION,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "target_language": self.target_language,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision": self.revision,
            "contract_version": self.contract_version,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, value: object) -> "TranslationCatalog":
        data = _exact_dict(
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
        schema_version = data["schema_version"]
        if (
            type(schema_version) is not int
            or schema_version != TRANSLATION_CATALOG_SCHEMA_VERSION
        ):
            raise TranslationViewError(
                "Unsupported translation catalog schema version."
            )
        raw_entries = data["entries"]
        if not isinstance(raw_entries, list):
            raise TranslationViewError("Invalid translation catalog entries.")
        return cls(
            context_uid=_canonical_uuid(
                data["context_uid"],
                "translation catalog Context uid",
            ),
            context_name=_context_name(data["context_name"]),
            target_language=_target_language(data["target_language"]),
            created_at=_timestamp(data["created_at"]),
            updated_at=_timestamp(data["updated_at"]),
            revision=_positive_int(
                data["revision"],
                "translation catalog revision",
            ),
            contract_version=_catalog_contract_version(
                data["contract_version"]
            ),
            entries=tuple(
                TranslationCatalogEntry.from_dict(entry)
                for entry in raw_entries
            ),
        )

    def _validate_context_identity(self, context: Context) -> None:
        if not isinstance(context, Context) or (
            self.context_uid != context.uid
            or self.context_name != context.name
        ):
            raise TranslationViewError(
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
    ) -> "TranslationCatalog":
        """Create an unsaved catalog seed for manual or imported content."""
        if not isinstance(context, Context):
            raise TranslationViewError(
                "Translation catalog source must be a Context."
            )
        timestamp = _timestamp(created_at if created_at is not None else _now())
        return cls(
            context_uid=context.uid,
            context_name=context.name,
            target_language=_target_language(target_language),
            created_at=timestamp,
            updated_at=timestamp,
            revision=1,
            contract_version=TRANSLATION_CATALOG_CONTRACT_VERSION,
            entries=(),
        )

    @classmethod
    def from_translation_plan(
        cls,
        plan: TranslationPlan,
        context: Context,
        *,
        existing: "TranslationCatalog | None" = None,
        created_at: str | None = None,
    ) -> "TranslationCatalog":
        if not isinstance(plan, TranslationPlan):
            raise TranslationViewError(
                "Translation catalog requires a TranslationPlan."
            )
        if not isinstance(context, Context) or not translation_plan_matches_context(
            plan,
            context,
        ):
            raise TranslationViewError(
                "The translation plan is stale because the Context changed."
            )
        if plan.provider_response_sha256 is None:
            raise TranslationViewError(
                "Provider catalog updates require a provider response digest."
            )
        memories = _direct_source_memories(context, plan.selected_memory_uid)
        if memories is None or len(memories) != len(plan.proposals):
            raise TranslationViewError(
                "The translation plan does not cover its exact source scope."
            )
        if existing is not None:
            existing._validate_context_identity(context)
            if existing.target_language != plan.target_language:
                raise TranslationViewError(
                    "The translation plan target does not match the catalog."
                )
        timestamp = _timestamp(created_at if created_at is not None else _now())
        by_uid = (
            {entry.source_uid: entry for entry in existing.entries}
            if existing is not None
            else {}
        )
        for memory, proposal in zip(memories, plan.proposals, strict=True):
            if (
                not isinstance(proposal, TranslationProposal)
                or proposal.source_uid != memory.uid
                or proposal.source_content != memory.content
            ):
                raise TranslationViewError(
                    "The translation plan does not match its source Memories."
                )
            previous = by_uid.get(memory.uid)
            by_uid[memory.uid] = TranslationCatalogEntry(
                source_uid=memory.uid,
                provider=TranslationProviderVariant(
                    source_sha256=_content_digest(memory.content),
                    context_digest=plan.context_digest,
                    translated_content=proposal.translated_content,
                    response_sha256=plan.provider_response_sha256,
                    generated_at=timestamp,
                ),
                curated=(None if previous is None else previous.curated),
            )
        prior_order = (
            tuple(entry.source_uid for entry in existing.entries)
            if existing is not None
            else ()
        )
        return cls(
            context_uid=plan.context_uid,
            context_name=plan.context_name,
            target_language=plan.target_language,
            created_at=(timestamp if existing is None else existing.created_at),
            updated_at=timestamp,
            revision=(1 if existing is None else existing.revision + 1),
            contract_version=TRANSLATION_CATALOG_CONTRACT_VERSION,
            entries=_catalog_entry_order(context, by_uid, prior_order),
        )

    @classmethod
    def from_plan(
        cls,
        plan: TranslationPlan,
        context: Context,
        *,
        existing: "TranslationCatalog | None" = None,
        created_at: str | None = None,
    ) -> "TranslationCatalog":
        return cls.from_translation_plan(
            plan,
            context,
            existing=existing,
            created_at=created_at,
        )

    @classmethod
    def from_legacy_views(
        cls,
        context: Context,
        target_language: str,
        views: Iterable[TranslationView],
    ) -> "TranslationCatalog | None":
        target = _target_language(target_language)
        candidates: dict[
            str,
            tuple[datetime, TranslationProviderVariant],
        ] = {}
        timestamps: list[str] = []
        for view in views:
            if (
                not isinstance(view, TranslationView)
                or view.target_language != target
                or not view.matches(context)
                or view.provider_response_sha256 is None
            ):
                continue
            generated = _timestamp(view.created_at)
            timestamps.append(generated)
            moment = _timestamp_value(generated)
            for entry in view.entries:
                variant = TranslationProviderVariant(
                    source_sha256=entry.source_sha256,
                    context_digest=view.context_digest,
                    translated_content=entry.translated_content,
                    response_sha256=view.provider_response_sha256,
                    generated_at=generated,
                )
                current = candidates.get(entry.source_uid)
                if current is None or moment > current[0]:
                    candidates[entry.source_uid] = (moment, variant)
                elif moment == current[0] and (
                    current[1].translated_content
                    != variant.translated_content
                ):
                    raise TranslationViewError(
                        "Conflicting legacy translation views have the same "
                        "creation time; refresh or edit that Memory explicitly."
                    )
        if not candidates:
            return None
        by_uid = {
            uid: TranslationCatalogEntry(
                source_uid=uid,
                provider=variant,
                curated=None,
            )
            for uid, (_, variant) in candidates.items()
        }
        created = min(timestamps, key=_timestamp_value)
        updated = max(timestamps, key=_timestamp_value)
        return cls(
            context_uid=context.uid,
            context_name=context.name,
            target_language=target,
            created_at=created,
            updated_at=updated,
            revision=1,
            contract_version=TRANSLATION_CATALOG_CONTRACT_VERSION,
            entries=_catalog_entry_order(context, by_uid),
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
    ) -> "TranslationCatalog":
        self._validate_context_identity(context)
        uid = _source_uid(source_uid, "curated source Memory uid")
        source = context.memories.get(uid)
        if not isinstance(source, Memory):
            raise TranslationViewError(
                "A curated translation requires a directly owned source Memory."
            )
        content = _translated_content(translated_content)
        checked_origin = _entry_origin(origin)
        checked_status = _review_status(review_status)
        checked_evidence = _optional_digest(
            evidence_sha256,
            "curated origin evidence digest",
        )
        timestamp = _timestamp(updated_at if updated_at is not None else _now())
        previous = self.entry_for(uid)
        source_digest = _content_digest(source.content)
        reviewed_digest = (
            _content_digest(content)
            if checked_status == TRANSLATION_REVIEW_VERIFIED
            else None
        )
        if previous is not None and previous.curated is not None:
            prior = previous.curated
            if (
                prior.source_sha256 == source_digest
                and prior.translated_content == content
                and prior.origin == checked_origin
                and prior.review_status == checked_status
                and prior.evidence_sha256 == checked_evidence
            ):
                return self
            curated_created_at = (
                prior.created_at
                if prior.source_sha256 == source_digest
                else timestamp
            )
        else:
            curated_created_at = timestamp
        curated = TranslationCuratedVariant(
            source_sha256=source_digest,
            translated_content=content,
            origin=checked_origin,
            review_status=checked_status,
            reviewed_content_sha256=reviewed_digest,
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
            entries=_catalog_entry_order(
                context,
                by_uid,
                (entry.source_uid for entry in self.entries),
            ),
        )

    def with_review_status(
        self,
        context: Context,
        source_uid: str,
        review_status: str,
        *,
        updated_at: str | None = None,
    ) -> "TranslationCatalog":
        self._validate_context_identity(context)
        status = _review_status(review_status)
        uid = _source_uid(source_uid, "reviewed source Memory uid")
        source = context.memories.get(uid)
        entry = self.entry_for(uid)
        if not isinstance(source, Memory) or entry is None:
            raise TranslationViewError(
                "Review requires a current directly owned translated Memory."
            )
        if (
            entry.curated is not None
            and not entry.curated.matches(source)
        ):
            raise TranslationViewError(
                "A stale curated translation must be edited or reset before "
                "reviewing a replacement."
            )
        effective = entry.effective(context, source)
        if effective is None:
            raise TranslationViewError(
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
    ) -> "TranslationCatalog":
        self._validate_context_identity(context)
        uid = _source_uid(source_uid, "reset source Memory uid")
        source = context.memories.get(uid)
        if not isinstance(source, Memory):
            raise TranslationViewError(
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
            entries=_catalog_entry_order(
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
    ) -> "TranslationCatalog":
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
            entries=_catalog_entry_order(
                context,
                by_uid,
                (entry.source_uid for entry in self.entries),
            ),
        )

    def effective_entries(
        self,
        context: Context,
        selector: str | None = None,
    ) -> tuple[EffectiveTranslation, ...]:
        self._validate_context_identity(context)
        memories = _direct_source_memories(context, selector)
        if memories is None:
            raise TranslationViewError(
                "The translation selector is not a direct source Memory."
            )
        by_uid = {entry.source_uid: entry for entry in self.entries}
        result: list[EffectiveTranslation] = []
        for memory in memories:
            entry = by_uid.get(memory.uid)
            if entry is None:
                continue
            effective = entry.effective(context, memory)
            if effective is not None:
                result.append(effective)
        return tuple(result)

    def missing_source_uids(
        self,
        context: Context,
        selector: str | None = None,
    ) -> tuple[str, ...]:
        self._validate_context_identity(context)
        memories = _direct_source_memories(context, selector)
        if memories is None:
            raise TranslationViewError(
                "The translation selector is not a direct source Memory."
            )
        effective = {
            entry.source_uid
            for entry in self.effective_entries(context, selector)
        }
        return tuple(
            memory.uid for memory in memories if memory.uid not in effective
        )

    def stale_curated_uids(self, context: Context) -> tuple[str, ...]:
        self._validate_context_identity(context)
        result: list[str] = []
        for entry in self.entries:
            if entry.curated is None:
                continue
            source = context.memories.get(entry.source_uid)
            if (
                not isinstance(source, Memory)
                or not entry.curated.matches(source)
            ):
                result.append(entry.source_uid)
        return tuple(result)

    def covers(self, context: Context, selector: str | None = None) -> bool:
        try:
            return not self.missing_source_uids(context, selector)
        except TranslationViewError:
            return False

    def to_translation_plan(
        self,
        context: Context,
        selector: str | None = None,
    ) -> TranslationPlan:
        if not self.covers(context, selector):
            raise TranslationViewError(
                "The translation catalog has missing or stale translations."
            )
        memories = _direct_source_memories(context, selector)
        assert memories is not None
        effective_by_uid = {
            entry.source_uid: entry
            for entry in self.effective_entries(context, selector)
        }
        effective = tuple(
            effective_by_uid[memory.uid] for memory in memories
        )
        provider_digests = {
            item.evidence_sha256
            for item in effective
            if item.origin == TRANSLATION_ORIGIN_PROVIDER
            and item.evidence_sha256 is not None
        }
        # Verification freezes provider text into the curated layer. Even
        # though its historical origin remains PROVIDER, it is no longer the
        # untouched one-call batch required by materialization provenance.
        provider_only = all(
            item.origin == TRANSLATION_ORIGIN_PROVIDER and not item.curated
            for item in effective
        )
        provider_digest = (
            next(iter(provider_digests))
            if provider_only and len(provider_digests) == 1
            else None
        )
        return TranslationPlan(
            operation_uid=str(uuid.uuid4()),
            context_uid=self.context_uid,
            context_name=self.context_name,
            context_digest=context_record_digest(context),
            target_language=self.target_language,
            selected_memory_uid=selector,
            proposals=tuple(
                TranslationProposal(
                    source_uid=memory.uid,
                    source_content=memory.content,
                    translated_content=effective_by_uid[
                        memory.uid
                    ].translated_content,
                )
                for memory in memories
            ),
            provider_response_sha256=provider_digest,
        )


def translation_catalog_record_digest(
    value: TranslationCatalog | dict[str, object],
) -> str:
    """Hash one complete validated v2 catalog canonically for CAS."""
    record = (
        value.to_dict()
        if isinstance(value, TranslationCatalog)
        else TranslationCatalog.from_dict(value).to_dict()
    )
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
