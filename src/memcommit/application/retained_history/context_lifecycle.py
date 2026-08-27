"""Profile-scoped lifecycle metadata for ordinary Contexts.

The ledger deliberately stores no Memory text or restorable Context snapshot.
Its job is to retain stable identity and deletion-boundary metadata after the
Context-owned files and checkpoints have been destroyed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid


CONTEXT_LIFECYCLE_SCHEMA_VERSION = 1
CONTEXT_DELETED = "CONTEXT_DELETED"
PREVIOUS_CHECKPOINT_NONE = "NONE"
PREVIOUS_CHECKPOINT_RECORDED = "RECORDED"
PREVIOUS_CHECKPOINT_UNREADABLE = "UNREADABLE"
_PREVIOUS_CHECKPOINT_STATUSES = frozenset(
    {
        PREVIOUS_CHECKPOINT_NONE,
        PREVIOUS_CHECKPOINT_RECORDED,
        PREVIOUS_CHECKPOINT_UNREADABLE,
    }
)


def _uuid(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a canonical UUID.")
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a canonical UUID.") from error
    if canonical != value:
        raise ValueError(f"{field} must be a canonical UUID.")
    return value


def _nonempty_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be non-empty text.")
    return value


def _digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field} must be a SHA-256 digest.")
    return value


def _timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Context lifecycle timestamp must be ISO-8601 text.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            "Context lifecycle timestamp must be valid ISO-8601 text."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Context lifecycle timestamp must include a timezone.")
    return value


@dataclass(frozen=True)
class ContextLifecycleEvent:
    """One immutable Profile-ledger event for an ordinary Context identity."""

    event_uid: str
    operation_id: str
    timestamp: str
    kind: str
    context_uid: str
    last_context_name: str
    last_context_digest: str
    previous_checkpoint_status: str
    previous_checkpoint_uid: str | None
    previous_checkpoint_digest: str | None
    descendants_preserved: bool

    @classmethod
    def deleted(
        cls,
        *,
        context_uid: str,
        last_context_name: str,
        last_context_digest: str,
        previous_checkpoint_status: str,
        previous_checkpoint_uid: str | None,
        previous_checkpoint_digest: str | None,
    ) -> "ContextLifecycleEvent":
        """Create metadata for one reviewed exact-Context deletion."""
        return cls(
            event_uid=str(uuid.uuid4()),
            operation_id=str(uuid.uuid4()),
            timestamp=datetime.now().astimezone().isoformat(),
            kind=CONTEXT_DELETED,
            context_uid=context_uid,
            last_context_name=last_context_name,
            last_context_digest=last_context_digest,
            previous_checkpoint_status=previous_checkpoint_status,
            previous_checkpoint_uid=previous_checkpoint_uid,
            previous_checkpoint_digest=previous_checkpoint_digest,
            descendants_preserved=True,
        ).validated()

    def validated(self) -> "ContextLifecycleEvent":
        _uuid(self.event_uid, field="Context lifecycle event uid")
        _uuid(self.operation_id, field="Context lifecycle operation id")
        _timestamp(self.timestamp)
        if self.kind != CONTEXT_DELETED:
            raise ValueError("Unsupported Context lifecycle event kind.")
        # Legacy Context identities are intentionally opaque non-empty strings;
        # deletion must not make old stores undeletable by requiring UUIDs here.
        _nonempty_text(self.context_uid, field="Context lifecycle Context uid")
        _nonempty_text(
            self.last_context_name,
            field="Context lifecycle last Context name",
        )
        _digest(
            self.last_context_digest,
            field="Context lifecycle last Context digest",
        )
        if self.previous_checkpoint_status not in _PREVIOUS_CHECKPOINT_STATUSES:
            raise ValueError(
                "Context lifecycle previous checkpoint status is invalid."
            )
        if self.previous_checkpoint_uid is not None:
            _nonempty_text(
                self.previous_checkpoint_uid,
                field="Context lifecycle previous checkpoint uid",
            )
        if self.previous_checkpoint_digest is not None:
            _digest(
                self.previous_checkpoint_digest,
                field="Context lifecycle previous checkpoint digest",
            )
        checkpoint_metadata_present = (
            self.previous_checkpoint_uid is not None
            and self.previous_checkpoint_digest is not None
        )
        if self.previous_checkpoint_status == PREVIOUS_CHECKPOINT_RECORDED:
            valid_checkpoint_state = checkpoint_metadata_present
        else:
            valid_checkpoint_state = (
                self.previous_checkpoint_uid is None
                and self.previous_checkpoint_digest is None
            )
        if not valid_checkpoint_state:
            raise ValueError(
                "Previous checkpoint metadata does not match its status."
            )
        if self.descendants_preserved is not True:
            raise ValueError(
                "Exact Context deletion events must preserve descendants."
            )
        return self

    def to_dict(self) -> dict[str, object]:
        self.validated()
        return {
            "schema_version": CONTEXT_LIFECYCLE_SCHEMA_VERSION,
            "event_uid": self.event_uid,
            "operation_id": self.operation_id,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "context_uid": self.context_uid,
            "last_context_name": self.last_context_name,
            "last_context_digest": self.last_context_digest,
            "previous_checkpoint_status": self.previous_checkpoint_status,
            "previous_checkpoint_uid": self.previous_checkpoint_uid,
            "previous_checkpoint_digest": self.previous_checkpoint_digest,
            "descendants_preserved": self.descendants_preserved,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ContextLifecycleEvent":
        if not isinstance(data, dict):
            raise ValueError("Context lifecycle event must be a JSON object.")
        expected_fields = {
            "schema_version",
            "event_uid",
            "operation_id",
            "timestamp",
            "kind",
            "context_uid",
            "last_context_name",
            "last_context_digest",
            "previous_checkpoint_status",
            "previous_checkpoint_uid",
            "previous_checkpoint_digest",
            "descendants_preserved",
        }
        if set(data) != expected_fields:
            raise ValueError("Context lifecycle event fields are invalid.")
        if data.get("schema_version") != CONTEXT_LIFECYCLE_SCHEMA_VERSION:
            raise ValueError("Context lifecycle schema version is unsupported.")
        if type(data.get("descendants_preserved")) is not bool:
            raise ValueError(
                "Context lifecycle descendants_preserved must be a boolean."
            )
        event = cls(
            event_uid=data.get("event_uid"),  # type: ignore[arg-type]
            operation_id=data.get("operation_id"),  # type: ignore[arg-type]
            timestamp=data.get("timestamp"),  # type: ignore[arg-type]
            kind=data.get("kind"),  # type: ignore[arg-type]
            context_uid=data.get("context_uid"),  # type: ignore[arg-type]
            last_context_name=data.get("last_context_name"),  # type: ignore[arg-type]
            last_context_digest=data.get("last_context_digest"),  # type: ignore[arg-type]
            previous_checkpoint_status=data.get("previous_checkpoint_status"),  # type: ignore[arg-type]
            previous_checkpoint_uid=data.get("previous_checkpoint_uid"),  # type: ignore[arg-type]
            previous_checkpoint_digest=data.get("previous_checkpoint_digest"),  # type: ignore[arg-type]
            descendants_preserved=data["descendants_preserved"],
        )
        return event.validated()
