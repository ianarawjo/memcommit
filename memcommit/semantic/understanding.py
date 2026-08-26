"""Shared, source-linked semantic understanding summaries.

An understanding summary is the reusable comprehension unit embedded in
operations such as Atomize and Compare.  It says what Mem understood from one
bounded evidence frame; it does not describe an operation's transformation,
unresolved work, or authority to mutate that frame.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping


UNDERSTANDING_TEXT_LIMIT = 20_000
_LIST_LINE = re.compile(r"\s*(?:[-*•]\s+|\d+[.)]\s+)")


class UnderstandingError(ValueError):
    """Invalid or unsupported understanding-summary data."""


@dataclass(frozen=True)
class UnderstandingSummary:
    """One concise semantic account linked to its bounded source evidence."""

    text: str
    source_uids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.text, str)
            or len(self.text) > UNDERSTANDING_TEXT_LIMIT
            or not isinstance(self.source_uids, tuple)
            or any(not isinstance(uid, str) or not uid for uid in self.source_uids)
            or len(set(self.source_uids)) != len(self.source_uids)
        ):
            raise UnderstandingError("Invalid understanding summary.")

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "source_uids": list(self.source_uids),
        }


def understanding_text_schema(
    *,
    limit: int = UNDERSTANDING_TEXT_LIMIT,
    empty: bool = False,
) -> dict[str, object]:
    """Return the shared one-paragraph provider schema used by composed calls."""
    return {
        "type": "string",
        "minLength": 0 if empty else 1,
        "maxLength": limit,
        "description": (
            "One concise natural-language report paragraph in complete "
            "sentences explaining what Mem understood from the bounded input. "
            "Do not use bullets, numbered lists, headings, key-value records, "
            "opaque IDs, or operation counts."
        ),
    }


def source_linked_understanding_schema(
    source_ids: tuple[str, ...],
    *,
    limit: int = UNDERSTANDING_TEXT_LIMIT,
    empty: bool = False,
    require_sources: bool = True,
) -> dict[str, object]:
    """Return a strict source-linked schema for a standalone summary unit."""
    return {
        "type": "object",
        "properties": {
            "text": understanding_text_schema(limit=limit, empty=empty),
            "source_ids": {
                "type": "array",
                "minItems": 1 if source_ids and require_sources else 0,
                "maxItems": len(source_ids),
                "items": (
                    {"type": "string", "enum": list(source_ids)}
                    if source_ids
                    else {"type": "string"}
                ),
            },
        },
        "required": ["text", "source_ids"],
        "additionalProperties": False,
    }


def normalize_understanding_text(
    value: object,
    *,
    empty: bool = False,
    limit: int = UNDERSTANDING_TEXT_LIMIT,
) -> str:
    """Validate report prose without truncating away semantic qualifications."""
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise UnderstandingError("Invalid understanding summary text.")
    text = " ".join(value.split())
    if text and any(
        _LIST_LINE.match(line)
        for line in value.splitlines()
        if line.strip()
    ):
        raise UnderstandingError(
            "An understanding summary must be report prose, not a list."
        )
    return text


def parse_source_linked_understanding(
    value: object,
    *,
    source_uid_by_id: Mapping[str, str],
    limit: int = UNDERSTANDING_TEXT_LIMIT,
) -> UnderstandingSummary:
    """Map temporary provider aliases back to exact local source identities."""
    if not isinstance(value, dict) or set(value) != {"text", "source_ids"}:
        raise UnderstandingError("Invalid source-linked understanding summary.")
    raw_ids = value["source_ids"]
    if (
        not isinstance(raw_ids, list)
        or len(raw_ids) > len(source_uid_by_id)
        or any(not isinstance(alias, str) or alias not in source_uid_by_id for alias in raw_ids)
        or len(set(raw_ids)) != len(raw_ids)
    ):
        raise UnderstandingError("Invalid understanding summary sources.")
    text = normalize_understanding_text(value["text"], limit=limit)
    if text and source_uid_by_id and not raw_ids:
        raise UnderstandingError(
            "A non-empty understanding summary requires source evidence."
        )
    # One durable Memory may be visible through more than one authorized
    # Context alias. The provider cites temporary aliases, while the portable
    # understanding cites durable evidence identities; preserve first-seen
    # order without fabricating duplicate durable citations.
    source_uids = tuple(dict.fromkeys(source_uid_by_id[alias] for alias in raw_ids))
    return UnderstandingSummary(text=text, source_uids=source_uids)
