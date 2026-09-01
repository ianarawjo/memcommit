"""Typed retained-checkpoint read scopes independent of current Context use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, TypeAlias
import uuid


CheckpointReadKind: TypeAlias = Literal["REFERENCE", "EMBED"]


class CheckpointReadValueError(ValueError):
    """A checkpoint-read scope is malformed or internally contradictory."""


def _canonical_uid(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise CheckpointReadValueError(f"{field} must be a canonical UUID.")
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise CheckpointReadValueError(
            f"{field} must be a canonical UUID."
        ) from error
    if value != canonical:
        raise CheckpointReadValueError(f"{field} must be a canonical UUID.")
    return canonical


@dataclass(frozen=True, slots=True)
class CheckpointReference:
    """An immutable exact set of retained checkpoint identities."""

    checkpoint_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        canonical = tuple(
            _canonical_uid(uid, field="Checkpoint uid")
            for uid in self.checkpoint_uids
        )
        if not canonical:
            raise CheckpointReadValueError(
                "Checkpoint Reference requires at least one checkpoint."
            )
        if len(set(canonical)) != len(canonical):
            raise CheckpointReadValueError(
                "Checkpoint Reference checkpoints must be unique."
            )
        object.__setattr__(self, "checkpoint_uids", canonical)


@dataclass(frozen=True, slots=True)
class CheckpointEmbed:
    """A retained checkpoint anchor whose same-Context future stays readable."""

    checkpoint_uid: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "checkpoint_uid",
            _canonical_uid(self.checkpoint_uid, field="Checkpoint uid"),
        )


CheckpointReadScope: TypeAlias = CheckpointReference | CheckpointEmbed


@dataclass(frozen=True, slots=True)
class CheckpointRead:
    """One Context-bound Reference or Embed retained-history right."""

    context_uid: str
    scope: CheckpointReadScope

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "context_uid",
            _canonical_uid(self.context_uid, field="Checkpoint Context uid"),
        )
        if not isinstance(self.scope, (CheckpointReference, CheckpointEmbed)):
            raise CheckpointReadValueError("Checkpoint read scope is invalid.")

    @classmethod
    def reference(
        cls,
        context_uid: str,
        checkpoint_uids: tuple[str, ...],
    ) -> CheckpointRead:
        return cls(context_uid, CheckpointReference(checkpoint_uids))

    @classmethod
    def embed(cls, context_uid: str, checkpoint_uid: str) -> CheckpointRead:
        return cls(context_uid, CheckpointEmbed(checkpoint_uid))

    @property
    def kind(self) -> CheckpointReadKind:
        return "REFERENCE" if isinstance(self.scope, CheckpointReference) else "EMBED"

    def to_dict(self) -> dict[str, object]:
        if isinstance(self.scope, CheckpointReference):
            return {
                "kind": "REFERENCE",
                "context_uid": self.context_uid,
                "checkpoint_uids": list(self.scope.checkpoint_uids),
            }
        return {
            "kind": "EMBED",
            "context_uid": self.context_uid,
            "checkpoint_uid": self.scope.checkpoint_uid,
        }

    @classmethod
    def from_dict(cls, value: object) -> CheckpointRead:
        if not isinstance(value, Mapping):
            raise CheckpointReadValueError("Checkpoint read must be an object.")
        kind = value.get("kind")
        if kind == "REFERENCE":
            if set(value) != {"kind", "context_uid", "checkpoint_uids"}:
                raise CheckpointReadValueError("Checkpoint Reference is invalid.")
            raw_uids = value.get("checkpoint_uids")
            if not isinstance(raw_uids, list):
                raise CheckpointReadValueError(
                    "Checkpoint Reference checkpoints must be a list."
                )
            return cls.reference(
                value.get("context_uid"),  # type: ignore[arg-type]
                tuple(raw_uids),
            )
        if kind == "EMBED":
            if set(value) != {"kind", "context_uid", "checkpoint_uid"}:
                raise CheckpointReadValueError("Checkpoint Embed is invalid.")
            return cls.embed(
                value.get("context_uid"),  # type: ignore[arg-type]
                value.get("checkpoint_uid"),  # type: ignore[arg-type]
            )
        raise CheckpointReadValueError("Checkpoint read kind is invalid.")


def canonical_checkpoint_reads(value: object) -> tuple[CheckpointRead, ...]:
    """Validate and deduplicate one ordered collection of checkpoint rights."""

    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise CheckpointReadValueError("Checkpoint reads must be a list.")
    reads = tuple(
        raw if isinstance(raw, CheckpointRead) else CheckpointRead.from_dict(raw)
        for raw in value
    )
    if len(set(reads)) != len(reads):
        raise CheckpointReadValueError("Checkpoint reads must be unique.")
    return reads


__all__ = [
    "CheckpointEmbed",
    "CheckpointRead",
    "CheckpointReadKind",
    "CheckpointReadScope",
    "CheckpointReadValueError",
    "CheckpointReference",
    "canonical_checkpoint_reads",
]
