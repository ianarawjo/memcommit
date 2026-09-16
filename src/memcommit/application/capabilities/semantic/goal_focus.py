"""Operation-neutral Goal relevance-focus values.

A Goal focus selects and audits semantic output; it is not Source evidence.
The same typed frame can be projected from process-local text, one ordinary
Memory, an ordinary Context, or a physical Ground ``/goals`` lane without
changing the durable representation owned by those sources.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal


GoalFocusKind = Literal["INLINE", "MEMORY", "CONTEXT", "GROUND"]


class GoalFocusError(ValueError):
    """One Goal focus operand or frozen projection is invalid."""


@dataclass(frozen=True, slots=True)
class GoalFocusItem:
    """One ordered proposition participating in a Goal relevance focus."""

    alias: str
    content: str
    context_name: str | None = None
    context_uid: str | None = None
    memory_uid: str | None = None
    content_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.alias, str) or not self.alias:
            raise GoalFocusError("A Goal focus item requires an alias.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise GoalFocusError("A Goal focus item requires nonblank content.")
        durable = self.memory_uid is not None
        if durable != (self.context_name is not None):
            raise GoalFocusError(
                "A durable Goal focus item requires both Context and Memory identity."
            )
        if durable and (
            not self.context_uid
            or not self.content_digest
            or len(self.content_digest) != 64
        ):
            raise GoalFocusError(
                "A durable Goal focus item requires exact Context and content bindings."
            )
        if not durable and any(
            value is not None
            for value in (self.context_uid, self.content_digest)
        ):
            raise GoalFocusError(
                "An inline Goal focus item cannot carry durable bindings."
            )

    def prompt_record(self) -> dict[str, object]:
        """Return the provider-visible proposition without private Store digests."""

        return {
            "goal_id": self.alias,
            "content": self.content,
            "source": (
                "INLINE"
                if self.memory_uid is None
                else {
                    "context": self.context_name,
                    "memory_uid": self.memory_uid,
                }
            ),
        }

    def identity_record(self) -> dict[str, object]:
        """Return the complete exact identity used by receipts and cache keys."""

        return {
            "alias": self.alias,
            "content": self.content,
            "context_name": self.context_name,
            "context_uid": self.context_uid,
            "memory_uid": self.memory_uid,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True, slots=True)
class FrozenGoalFocus:
    """One exact ordered Goal frame frozen before semantic provider access."""

    kind: GoalFocusKind
    label: str
    items: tuple[GoalFocusItem, ...]
    context_name: str | None = None
    context_uid: str | None = None
    context_digest: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"INLINE", "MEMORY", "CONTEXT", "GROUND"}:
            raise GoalFocusError("A Goal focus has an invalid source kind.")
        if not isinstance(self.label, str) or not self.label:
            raise GoalFocusError("A Goal focus requires a display label.")
        if not self.items or any(
            not isinstance(item, GoalFocusItem) for item in self.items
        ):
            raise GoalFocusError("A Goal focus requires at least one typed item.")
        aliases = tuple(item.alias for item in self.items)
        if len(aliases) != len(set(aliases)):
            raise GoalFocusError("Goal focus aliases must be unique.")
        if self.kind == "INLINE":
            if len(self.items) != 1 or any(
                value is not None
                for value in (
                    self.context_name,
                    self.context_uid,
                    self.context_digest,
                )
            ):
                raise GoalFocusError(
                    "An inline Goal focus must contain one process-local item."
                )
        elif not self.context_name or not self.context_uid or not self.context_digest:
            raise GoalFocusError(
                "A stored Goal focus requires an exact Context binding."
            )

    @property
    def text(self) -> str:
        """Return a compatibility text projection without losing item boundaries.

        Existing single-Goal provider contracts retain their exact historical
        text. A multi-Memory Context is rendered with stable aliases rather
        than silently concatenated into one fabricated durable proposition.
        """

        if len(self.items) == 1:
            return self.items[0].content
        return "\n".join(f"[{item.alias}] {item.content}" for item in self.items)

    @property
    def digest(self) -> str:
        payload = {
            "kind": self.kind,
            "label": self.label,
            "items": [item.identity_record() for item in self.items],
            "context_name": self.context_name,
            "context_uid": self.context_uid,
            "context_digest": self.context_digest,
        }
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

    def prompt_record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "label": self.label,
            "items": [item.prompt_record() for item in self.items],
        }

    def receipt_record(self) -> dict[str, object]:
        return {
            **self.prompt_record(),
            "digest": self.digest,
            "context_name": self.context_name,
            "context_uid": self.context_uid,
            "context_digest": self.context_digest,
            "items": [item.identity_record() for item in self.items],
        }

    @classmethod
    def from_receipt_record(cls, value: object) -> "FrozenGoalFocus":
        """Decode the exact authored receipt shape without accepting extras."""

        if not isinstance(value, dict) or set(value) != {
            "kind",
            "label",
            "items",
            "digest",
            "context_name",
            "context_uid",
            "context_digest",
        }:
            raise GoalFocusError("A saved Goal focus receipt is invalid.")
        raw_items = value["items"]
        if not isinstance(raw_items, list):
            raise GoalFocusError("A saved Goal focus item frame is invalid.")
        items: list[GoalFocusItem] = []
        for raw in raw_items:
            if not isinstance(raw, dict) or set(raw) != {
                "alias",
                "content",
                "context_name",
                "context_uid",
                "memory_uid",
                "content_digest",
            }:
                raise GoalFocusError("A saved Goal focus item is invalid.")
            items.append(
                GoalFocusItem(
                    alias=raw["alias"],
                    content=raw["content"],
                    context_name=raw["context_name"],
                    context_uid=raw["context_uid"],
                    memory_uid=raw["memory_uid"],
                    content_digest=raw["content_digest"],
                )
            )
        focus = cls(
            kind=value["kind"],
            label=value["label"],
            items=tuple(items),
            context_name=value["context_name"],
            context_uid=value["context_uid"],
            context_digest=value["context_digest"],
        )
        if value["digest"] != focus.digest:
            raise GoalFocusError("A saved Goal focus digest is invalid.")
        return focus


def inline_goal_focus(content: str) -> FrozenGoalFocus:
    """Create one process-local Goal focus without fabricated durable identity."""

    if not isinstance(content, str) or not content.strip():
        raise GoalFocusError("Inline Goal focus text must be nonblank.")
    normalized = content.strip()
    return FrozenGoalFocus(
        kind="INLINE",
        label="INLINE",
        items=(GoalFocusItem(alias="g000001", content=normalized),),
    )


__all__ = [
    "FrozenGoalFocus",
    "GoalFocusError",
    "GoalFocusItem",
    "GoalFocusKind",
    "inline_goal_focus",
]
