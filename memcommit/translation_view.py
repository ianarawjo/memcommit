"""Strict durable projections of translated direct Memory content.

A translation view is saved provider output, but it is not a Context or a
collection of new Memory occurrences.  It therefore carries no artifact UID
and its entries retain only the existing source Memory UIDs.  A fresh
operation UID is allocated only when a caller explicitly converts the view
back into a materializable :class:`TranslationPlan`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import unicodedata
import uuid

from memcommit.context import Context, Memory
from memcommit.store import context_record_digest
from memcommit.translate import (
    TRANSLATED_CONTENT_CHAR_LIMIT,
    TRANSLATION_TARGET_CHAR_LIMIT,
    TranslationPlan,
    TranslationProposal,
    translation_plan_matches_context,
)


TRANSLATION_VIEW_SCHEMA_VERSION = 1
TRANSLATION_VIEW_CONTRACT_VERSION = "translate-v1"
TRANSLATION_VIEW_NAME_LIMIT = 20_000
TRANSLATION_VIEW_SOURCE_UID_LIMIT = 4_096


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
    """Saved translated text bound to one exact direct Context record."""

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
                "created_at": (
                    created_at
                    if created_at is not None
                    else datetime.now(timezone.utc).isoformat()
                ),
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
            isinstance(schema_version, bool)
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
