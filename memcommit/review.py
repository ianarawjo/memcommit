"""Persistent, non-mutating review state for semantic findings.

The terminal is only a view/controller.  This module owns the durable semantic
state so a review can be resumed after the PTY or controlling agent disconnects.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Literal

from memcommit.context import Context, Memory
from memcommit.findings import AmbiguityReport, Clarification, Interpretation


REVIEW_SCHEMA_VERSION = 1
REVIEW_RESPONSE_CHAR_LIMIT = 20_000
ReviewKind = Literal["ambiguities"]
ReviewSort = Literal["SOURCE", "PRIORITY"]

_INTERPRETATIONS = {"SINGLE", "DOMINANT", "COMPETING"}
_CLARIFICATIONS = {"NONE", "HELPFUL", "REQUIRED"}
_SORT_MODES = {"SOURCE", "PRIORITY"}
_PRIORITY = {"NONE": 0, "HELPFUL": 1, "REQUIRED": 2}


class ReviewError(ValueError):
    """Invalid or stale semantic review state."""


def _exact_dict(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ReviewError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = REVIEW_RESPONSE_CHAR_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value)
        or len(value) > limit
    ):
        raise ReviewError(f"Invalid {label}.")
    return value


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ReviewError(f"Invalid {label}.")
    return value


def direct_context_digest(ctx: Context) -> str:
    """Fingerprint the complete ordered direct-Memory interpretation frame."""
    payload = [
        {"uid": item.uid, "content": item.content}
        for item in ctx.iter_items()
        if isinstance(item, Memory)
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ReviewChoice:
    """One model-proposed reading with a deterministic presentation role."""

    uid: str
    label: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "label": self.label, "text": self.text}

    @classmethod
    def from_dict(cls, value: object) -> "ReviewChoice":
        data = _exact_dict(value, {"uid", "label", "text"}, "review choice")
        return cls(
            uid=_string(data["uid"], "review choice uid", limit=100),
            label=_string(data["label"], "review choice label", limit=100),
            text=_string(data["text"], "review choice text", limit=1_000),
        )


@dataclass(frozen=True)
class ReviewItem:
    """One finding rendered and answered by the shared review shell."""

    uid: str
    source_uids: tuple[str, ...]
    source_order: int
    interpretation: Interpretation
    clarification: Clarification
    reason: str
    question: str
    choices: tuple[ReviewChoice, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "source_uids": list(self.source_uids),
            "source_order": self.source_order,
            "interpretation": self.interpretation,
            "clarification": self.clarification,
            "reason": self.reason,
            "question": self.question,
            "choices": [choice.to_dict() for choice in self.choices],
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReviewItem":
        data = _exact_dict(
            value,
            {
                "uid",
                "source_uids",
                "source_order",
                "interpretation",
                "clarification",
                "reason",
                "question",
                "choices",
            },
            "review item",
        )
        source_uids = data["source_uids"]
        choices = data["choices"]
        interpretation = data["interpretation"]
        clarification = data["clarification"]
        if (
            not isinstance(source_uids, list)
            or not source_uids
            or any(not isinstance(item, str) or not item for item in source_uids)
            or len(set(source_uids)) != len(source_uids)
            or not isinstance(choices, list)
            or not choices
            or not isinstance(interpretation, str)
            or interpretation not in _INTERPRETATIONS
            or not isinstance(clarification, str)
            or clarification not in _CLARIFICATIONS
        ):
            raise ReviewError("Invalid review item.")
        parsed_choices = tuple(
            ReviewChoice.from_dict(choice)
            for choice in choices
        )
        if len({choice.uid for choice in parsed_choices}) != len(parsed_choices):
            raise ReviewError("Duplicate review choice uid.")
        return cls(
            uid=_string(data["uid"], "review item uid", limit=100),
            source_uids=tuple(source_uids),
            source_order=_integer(data["source_order"], "source order"),
            interpretation=interpretation,
            clarification=clarification,
            reason=_string(data["reason"], "review reason", limit=1_000),
            question=_string(
                data["question"],
                "review question",
                empty=True,
                limit=500,
            ),
            choices=parsed_choices,
        )


@dataclass
class ReviewResponse:
    """A selected proposed reading plus one deliberately untyped annotation."""

    selected_choice_uid: str | None = None
    text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_choice_uid": self.selected_choice_uid,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReviewResponse":
        data = _exact_dict(
            value,
            {"selected_choice_uid", "text"},
            "review response",
        )
        selected = data["selected_choice_uid"]
        if selected is not None and (
            not isinstance(selected, str) or not selected
        ):
            raise ReviewError("Invalid selected review choice.")
        return cls(
            selected_choice_uid=selected,
            text=_string(
                data["text"],
                "review response text",
                empty=True,
            ),
        )

    @property
    def answered(self) -> bool:
        return self.selected_choice_uid is not None or bool(self.text.strip())


@dataclass
class ReviewSession:
    """One resumable review over a fixed direct-Context interpretation frame."""

    uid: str
    kind: ReviewKind
    context_uid: str
    context_name: str
    context_digest: str
    items: tuple[ReviewItem, ...]
    responses: dict[str, ReviewResponse] = field(default_factory=dict)
    cursor_uid: str | None = None
    sort_mode: ReviewSort = "SOURCE"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "uid": self.uid,
            "kind": self.kind,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "items": [item.to_dict() for item in self.items],
            "responses": {
                uid: response.to_dict()
                for uid, response in self.responses.items()
            },
            "cursor_uid": self.cursor_uid,
            "sort_mode": self.sort_mode,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReviewSession":
        data = _exact_dict(
            value,
            {
                "schema_version",
                "uid",
                "kind",
                "context_uid",
                "context_name",
                "context_digest",
                "items",
                "responses",
                "cursor_uid",
                "sort_mode",
            },
            "review session",
        )
        if data["schema_version"] != REVIEW_SCHEMA_VERSION:
            raise ReviewError("Unsupported review session schema version.")
        if not isinstance(data["kind"], str) or data["kind"] != "ambiguities":
            raise ReviewError("Unsupported review kind.")
        if (
            not isinstance(data["sort_mode"], str)
            or data["sort_mode"] not in _SORT_MODES
        ):
            raise ReviewError("Invalid review sort mode.")
        items = data["items"]
        responses = data["responses"]
        cursor_uid = data["cursor_uid"]
        if not isinstance(items, list) or not isinstance(responses, dict):
            raise ReviewError("Invalid review session.")
        parsed_items = tuple(ReviewItem.from_dict(item) for item in items)
        item_by_uid = {item.uid: item for item in parsed_items}
        if len(item_by_uid) != len(parsed_items):
            raise ReviewError("Duplicate review item uid.")
        if len({item.source_order for item in parsed_items}) != len(parsed_items):
            raise ReviewError("Duplicate review source order.")
        if cursor_uid is not None and (
            not isinstance(cursor_uid, str)
            or cursor_uid not in item_by_uid
        ):
            raise ReviewError("Invalid review cursor.")

        parsed_responses: dict[str, ReviewResponse] = {}
        for item_uid, response in responses.items():
            if (
                not isinstance(item_uid, str)
                or item_uid not in item_by_uid
                or item_uid in parsed_responses
            ):
                raise ReviewError("Invalid review response target.")
            parsed = ReviewResponse.from_dict(response)
            choice_uids = {
                choice.uid for choice in item_by_uid[item_uid].choices
            }
            if (
                parsed.selected_choice_uid is not None
                and parsed.selected_choice_uid not in choice_uids
            ):
                raise ReviewError("Review response selects an unknown choice.")
            parsed_responses[item_uid] = parsed

        uid = _string(data["uid"], "review session uid", limit=100)
        try:
            uuid.UUID(uid)
        except ValueError as error:
            raise ReviewError("Invalid review session uid.") from error
        digest = _string(
            data["context_digest"],
            "review Context digest",
            limit=64,
        )
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ReviewError("Invalid review Context digest.")
        return cls(
            uid=uid,
            kind="ambiguities",
            context_uid=_string(
                data["context_uid"],
                "review Context uid",
                limit=100,
            ),
            context_name=_string(
                data["context_name"],
                "review Context name",
                limit=500,
            ),
            context_digest=digest,
            items=parsed_items,
            responses=parsed_responses,
            cursor_uid=cursor_uid,
            sort_mode=data["sort_mode"],
        )

    def ordered_items(self) -> list[ReviewItem]:
        if self.sort_mode == "SOURCE":
            return sorted(self.items, key=lambda item: item.source_order)
        return sorted(
            self.items,
            key=lambda item: (
                -_PRIORITY[item.clarification],
                item.source_order,
            ),
        )

    def current_item(self) -> ReviewItem | None:
        ordered = self.ordered_items()
        if not ordered:
            return None
        if self.cursor_uid is None:
            self.cursor_uid = ordered[0].uid
        return next(
            (item for item in ordered if item.uid == self.cursor_uid),
            ordered[0],
        )

    def response_for(self, item_uid: str) -> ReviewResponse:
        if item_uid not in {item.uid for item in self.items}:
            raise ReviewError("Unknown review item.")
        return self.responses.setdefault(item_uid, ReviewResponse())

    def move(self, delta: int) -> None:
        ordered = self.ordered_items()
        if not ordered:
            self.cursor_uid = None
            return
        current = self.current_item()
        assert current is not None
        index = next(
            index
            for index, item in enumerate(ordered)
            if item.uid == current.uid
        )
        index = max(0, min(index + delta, len(ordered) - 1))
        self.cursor_uid = ordered[index].uid

    def select_choice(self, choice_index: int | None) -> None:
        item = self.current_item()
        if item is None:
            return
        response = self.response_for(item.uid)
        if choice_index is None:
            response.selected_choice_uid = None
            return
        if choice_index < 0 or choice_index >= len(item.choices):
            raise ReviewError("Unknown review choice.")
        response.selected_choice_uid = item.choices[choice_index].uid

    def selected_choice_index(self, item: ReviewItem | None = None) -> int | None:
        item = item or self.current_item()
        if item is None:
            return None
        selected = self.response_for(item.uid).selected_choice_uid
        if selected is None:
            return None
        return next(
            index
            for index, choice in enumerate(item.choices)
            if choice.uid == selected
        )

    def toggle_sort(self) -> None:
        self.sort_mode = (
            "PRIORITY" if self.sort_mode == "SOURCE" else "SOURCE"
        )

    @property
    def answered_count(self) -> int:
        return sum(response.answered for response in self.responses.values())


def _reading_labels(
    interpretation: Interpretation,
    count: int,
) -> list[str]:
    if interpretation == "SINGLE":
        return ["SINGLE"]
    if interpretation == "DOMINANT":
        return ["DOMINANT", *(["ALTERNATIVE"] * (count - 1))]
    return ["COMPETING"] * count


def create_ambiguity_review(
    ctx: Context,
    report: AmbiguityReport,
) -> ReviewSession:
    """Convert one finder report into a source-ordered durable review."""
    direct_memories = [
        item for item in ctx.iter_items() if isinstance(item, Memory)
    ]
    source_order = {
        memory.uid: index
        for index, memory in enumerate(direct_memories)
    }
    if report.memory_count != len(direct_memories):
        raise ReviewError("Ambiguity report does not match the Context.")

    items: list[ReviewItem] = []
    seen: set[str] = set()
    for finding in report.findings:
        memory_uid = finding.memory.uid
        if memory_uid not in source_order or memory_uid in seen:
            raise ReviewError("Ambiguity report contains an invalid Memory.")
        seen.add(memory_uid)
        labels = _reading_labels(
            finding.interpretation,
            len(finding.ordinary_readings),
        )
        choices = tuple(
            ReviewChoice(
                uid=f"{memory_uid}:reading:{index}",
                label=label,
                text=reading,
            )
            for index, (label, reading) in enumerate(
                zip(labels, finding.ordinary_readings, strict=True),
                start=1,
            )
        )
        items.append(
            ReviewItem(
                uid=memory_uid,
                source_uids=(memory_uid,),
                source_order=source_order[memory_uid],
                interpretation=finding.interpretation,
                clarification=finding.clarification,
                reason=finding.reason,
                question=finding.question,
                choices=choices,
            )
        )

    items.sort(key=lambda item: item.source_order)
    return ReviewSession(
        uid=str(uuid.uuid4()),
        kind="ambiguities",
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=direct_context_digest(ctx),
        items=tuple(items),
        cursor_uid=items[0].uid if items else None,
    )


def review_matches_context(session: ReviewSession, ctx: Context) -> bool:
    """Return whether a saved review still has its complete local frame."""
    direct_memories = [
        item for item in ctx.iter_items() if isinstance(item, Memory)
    ]
    source_order = {
        memory.uid: index
        for index, memory in enumerate(direct_memories)
    }
    return (
        session.context_uid == ctx.uid
        and session.context_name == ctx.name
        and session.context_digest == direct_context_digest(ctx)
        and all(
            all(source_uid in source_order for source_uid in item.source_uids)
            and item.source_order == source_order[item.source_uids[0]]
            for item in session.items
        )
    )
