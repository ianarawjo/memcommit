"""Typed resume receipts for Ground workspaces that do not exist yet.

A draft is deliberately not a Ground workspace or an ordinary Context.  It
retains one already validated blank-shell proposal so the person can leave the
TUI and resume without repeating provider inference.  Physical creation and
its exact approval remain owned by the Ground workspace application boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal
import unicodedata
import uuid


GROUND_WORKSPACE_DRAFT_SCHEMA_VERSION = 1
GroundWorkspaceDraftOrigin = Literal["USER_EXACT", "AGENT_SUGGESTED"]
_MULTILINE_CONTROLS = frozenset({"\n", "\t"})


class GroundWorkspaceDraftError(ValueError):
    """A hidden Ground draft receipt is invalid or no longer current."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _text(
    value: object,
    *,
    label: str,
    empty: bool = False,
    limit: int = 100_000,
    allowed_controls: frozenset[str] = frozenset(),
) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise GroundWorkspaceDraftError(f"Ground draft {label} is invalid.")
    if not empty and not value.strip():
        raise GroundWorkspaceDraftError(f"Ground draft {label} is invalid.")
    if any(
        unicodedata.category(character) == "Cc"
        and character not in allowed_controls
        for character in value
    ):
        raise GroundWorkspaceDraftError(f"Ground draft {label} is invalid.")
    return value


def _timestamp_value(value: object, *, label: str) -> str:
    text = _text(value, label=label, limit=64)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise GroundWorkspaceDraftError(
            f"Ground draft {label} is invalid."
        ) from error
    if parsed.tzinfo is None:
        raise GroundWorkspaceDraftError(f"Ground draft {label} is invalid.")
    return text


def _string_tuple(
    value: object,
    *,
    label: str,
    maximum: int,
    empty_items: bool = False,
    allowed_controls: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise GroundWorkspaceDraftError(f"Ground draft {label} is invalid.")
    result = tuple(
        _text(
            item,
            label=label,
            empty=empty_items,
            allowed_controls=allowed_controls,
        )
        for item in value
    )
    return result


@dataclass(frozen=True)
class GroundWorkspaceRuleDraft:
    content: str
    rationale: str
    origin: GroundWorkspaceDraftOrigin
    source_spans: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(
            self.content,
            label="Rule content",
            allowed_controls=_MULTILINE_CONTROLS,
        )
        _text(
            self.rationale,
            label="Rule rationale",
            empty=True,
            allowed_controls=_MULTILINE_CONTROLS,
        )
        if self.origin not in {"USER_EXACT", "AGENT_SUGGESTED"}:
            raise GroundWorkspaceDraftError("Ground draft Rule origin is invalid.")
        _string_tuple(
            self.source_spans,
            label="Rule source spans",
            maximum=4,
            allowed_controls=_MULTILINE_CONTROLS,
        )
        if len(set(self.source_spans)) != len(self.source_spans):
            raise GroundWorkspaceDraftError(
                "Ground draft Rule source provenance is invalid."
            )
        if (self.origin == "USER_EXACT") != bool(self.source_spans):
            raise GroundWorkspaceDraftError(
                "Ground draft Rule source provenance is invalid."
            )
        if self.origin == "USER_EXACT" and not any(
            self.content in span for span in self.source_spans
        ):
            raise GroundWorkspaceDraftError(
                "Ground draft Rule source provenance is invalid."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "rationale": self.rationale,
            "origin": self.origin,
            "source_spans": list(self.source_spans),
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundWorkspaceRuleDraft":
        if not isinstance(value, dict) or set(value) != {
            "content",
            "rationale",
            "origin",
            "source_spans",
        }:
            raise GroundWorkspaceDraftError("Ground draft Rule is invalid.")
        return cls(
            content=_text(
                value["content"],
                label="Rule content",
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            rationale=_text(
                value["rationale"],
                label="Rule rationale",
                empty=True,
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            origin=value["origin"],  # type: ignore[arg-type]
            source_spans=_string_tuple(
                value["source_spans"],
                label="Rule source spans",
                maximum=4,
                allowed_controls=_MULTILINE_CONTROLS,
            ),
        )


@dataclass(frozen=True)
class GroundWorkspaceMemoryDraft:
    content: str
    expected: str
    rationale: str
    case_role: Literal["FIT", "BOUNDARY", "CONTRAST"]
    disposition: Literal["INCLUDE", "EXCLUDE", "UNRESOLVED"]
    rule_draft_index: int
    origin: GroundWorkspaceDraftOrigin
    source_spans: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(
            self.content,
            label="Memory content",
            allowed_controls=_MULTILINE_CONTROLS,
        )
        _text(
            self.expected,
            label="Memory expected value",
            empty=True,
            allowed_controls=_MULTILINE_CONTROLS,
        )
        _text(
            self.rationale,
            label="Memory rationale",
            empty=True,
            allowed_controls=_MULTILINE_CONTROLS,
        )
        if self.case_role not in {"FIT", "BOUNDARY", "CONTRAST"}:
            raise GroundWorkspaceDraftError("Ground draft Memory role is invalid.")
        if self.disposition not in {"INCLUDE", "EXCLUDE", "UNRESOLVED"}:
            raise GroundWorkspaceDraftError(
                "Ground draft Memory disposition is invalid."
            )
        if self.origin == "AGENT_SUGGESTED" and self.disposition != "UNRESOLVED":
            raise GroundWorkspaceDraftError(
                "Ground draft Memory disposition is invalid."
            )
        if self.disposition == "INCLUDE" and not self.expected.strip():
            raise GroundWorkspaceDraftError(
                "Ground draft Memory expected value is invalid."
            )
        if (
            isinstance(self.rule_draft_index, bool)
            or not isinstance(self.rule_draft_index, int)
            or self.rule_draft_index < 0
        ):
            raise GroundWorkspaceDraftError(
                "Ground draft Memory Rule link is invalid."
            )
        if self.origin not in {"USER_EXACT", "AGENT_SUGGESTED"}:
            raise GroundWorkspaceDraftError("Ground draft Memory origin is invalid.")
        _string_tuple(
            self.source_spans,
            label="Memory source spans",
            maximum=4,
            allowed_controls=_MULTILINE_CONTROLS,
        )
        if len(set(self.source_spans)) != len(self.source_spans):
            raise GroundWorkspaceDraftError(
                "Ground draft Memory source provenance is invalid."
            )
        if (self.origin == "USER_EXACT") != bool(self.source_spans):
            raise GroundWorkspaceDraftError(
                "Ground draft Memory source provenance is invalid."
            )
        if self.origin == "USER_EXACT" and (
            not any(self.content in span for span in self.source_spans)
            or (
                self.expected
                and not any(self.expected in span for span in self.source_spans)
            )
        ):
            raise GroundWorkspaceDraftError(
                "Ground draft Memory source provenance is invalid."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "expected": self.expected,
            "rationale": self.rationale,
            "case_role": self.case_role,
            "disposition": self.disposition,
            "rule_draft_index": self.rule_draft_index,
            "origin": self.origin,
            "source_spans": list(self.source_spans),
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundWorkspaceMemoryDraft":
        if not isinstance(value, dict) or set(value) != {
            "content",
            "expected",
            "rationale",
            "case_role",
            "disposition",
            "rule_draft_index",
            "origin",
            "source_spans",
        }:
            raise GroundWorkspaceDraftError("Ground draft Memory is invalid.")
        return cls(
            content=_text(
                value["content"],
                label="Memory content",
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            expected=_text(
                value["expected"],
                label="Memory expected value",
                empty=True,
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            rationale=_text(
                value["rationale"],
                label="Memory rationale",
                empty=True,
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            case_role=value["case_role"],  # type: ignore[arg-type]
            disposition=value["disposition"],  # type: ignore[arg-type]
            rule_draft_index=value["rule_draft_index"],  # type: ignore[arg-type]
            origin=value["origin"],  # type: ignore[arg-type]
            source_spans=_string_tuple(
                value["source_spans"],
                label="Memory source spans",
                maximum=4,
                allowed_controls=_MULTILINE_CONTROLS,
            ),
        )


@dataclass(frozen=True)
class GroundWorkspaceDraft:
    """One profile-local proposal receipt for a not-yet-created workspace."""

    uid: str
    workspace_name: str
    goal: str
    understanding: str
    question: str
    submitted_turns: tuple[str, ...]
    rule_drafts: tuple[GroundWorkspaceRuleDraft, ...]
    memory_drafts: tuple[GroundWorkspaceMemoryDraft, ...]
    created_at: str
    updated_at: str
    revision: int = 0
    schema_version: int = GROUND_WORKSPACE_DRAFT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        try:
            canonical_uid = str(uuid.UUID(self.uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise GroundWorkspaceDraftError(
                "Ground draft identity is invalid."
            ) from error
        if canonical_uid != self.uid:
            raise GroundWorkspaceDraftError("Ground draft identity is invalid.")
        _text(self.workspace_name, label="workspace name", limit=512)
        _text(self.goal, label="Goal")
        _text(
            self.understanding,
            label="understanding",
            allowed_controls=_MULTILINE_CONTROLS,
        )
        _text(
            self.question,
            label="question",
            allowed_controls=_MULTILINE_CONTROLS,
        )
        _string_tuple(
            self.submitted_turns,
            label="submitted turns",
            maximum=64,
            allowed_controls=_MULTILINE_CONTROLS,
        )
        if any(
            not isinstance(value, GroundWorkspaceRuleDraft)
            for value in self.rule_drafts
        ):
            raise GroundWorkspaceDraftError("Ground draft Rules are invalid.")
        if any(
            not isinstance(value, GroundWorkspaceMemoryDraft)
            for value in self.memory_drafts
        ):
            raise GroundWorkspaceDraftError("Ground draft Memories are invalid.")
        if len(self.rule_drafts) > 4 or len(self.memory_drafts) > 3:
            raise GroundWorkspaceDraftError("Ground draft preview count is invalid.")
        if any(
            memory.rule_draft_index > len(self.rule_drafts)
            for memory in self.memory_drafts
        ):
            raise GroundWorkspaceDraftError(
                "Ground draft Memory Rule link is invalid."
            )
        created = _timestamp_value(self.created_at, label="created time")
        updated = _timestamp_value(self.updated_at, label="updated time")
        if datetime.fromisoformat(updated) < datetime.fromisoformat(created):
            raise GroundWorkspaceDraftError("Ground draft timestamps are invalid.")
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise GroundWorkspaceDraftError("Ground draft revision is invalid.")
        if self.schema_version != GROUND_WORKSPACE_DRAFT_SCHEMA_VERSION:
            raise GroundWorkspaceDraftError(
                "Unsupported Ground draft schema version."
            )

    @classmethod
    def create(
        cls,
        *,
        workspace_name: str,
        goal: str,
        understanding: str,
        question: str,
        submitted_turns: tuple[str, ...],
        rule_drafts: tuple[GroundWorkspaceRuleDraft, ...] = (),
        memory_drafts: tuple[GroundWorkspaceMemoryDraft, ...] = (),
    ) -> "GroundWorkspaceDraft":
        now = _timestamp()
        return cls(
            uid=str(uuid.uuid4()),
            workspace_name=workspace_name,
            goal=goal,
            understanding=understanding,
            question=question,
            submitted_turns=submitted_turns,
            rule_drafts=rule_drafts,
            memory_drafts=memory_drafts,
            created_at=now,
            updated_at=now,
        )

    def revise(
        self,
        *,
        workspace_name: str,
        goal: str,
        understanding: str,
        question: str,
        submitted_turns: tuple[str, ...],
        rule_drafts: tuple[GroundWorkspaceRuleDraft, ...],
        memory_drafts: tuple[GroundWorkspaceMemoryDraft, ...],
    ) -> "GroundWorkspaceDraft":
        return replace(
            self,
            workspace_name=workspace_name,
            goal=goal,
            understanding=understanding,
            question=question,
            submitted_turns=submitted_turns,
            rule_drafts=rule_drafts,
            memory_drafts=memory_drafts,
            updated_at=_timestamp(),
            revision=self.revision + 1,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.schema_version,
            "uid": self.uid,
            "workspace_name": self.workspace_name,
            "goal": self.goal,
            "understanding": self.understanding,
            "question": self.question,
            "submitted_turns": list(self.submitted_turns),
            "rule_drafts": [item.to_dict() for item in self.rule_drafts],
            "memory_drafts": [item.to_dict() for item in self.memory_drafts],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, value: object) -> "GroundWorkspaceDraft":
        if not isinstance(value, dict) or set(value) != {
            "version",
            "uid",
            "workspace_name",
            "goal",
            "understanding",
            "question",
            "submitted_turns",
            "rule_drafts",
            "memory_drafts",
            "created_at",
            "updated_at",
            "revision",
        }:
            raise GroundWorkspaceDraftError("Ground draft record is invalid.")
        rules = value["rule_drafts"]
        memories = value["memory_drafts"]
        if not isinstance(rules, list) or not isinstance(memories, list):
            raise GroundWorkspaceDraftError("Ground draft previews are invalid.")
        return cls(
            uid=value["uid"],  # type: ignore[arg-type]
            workspace_name=_text(
                value["workspace_name"],
                label="workspace name",
                limit=512,
            ),
            goal=_text(value["goal"], label="Goal"),
            understanding=_text(
                value["understanding"],
                label="understanding",
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            question=_text(
                value["question"],
                label="question",
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            submitted_turns=_string_tuple(
                value["submitted_turns"],
                label="submitted turns",
                maximum=64,
                allowed_controls=_MULTILINE_CONTROLS,
            ),
            rule_drafts=tuple(
                GroundWorkspaceRuleDraft.from_dict(item) for item in rules
            ),
            memory_drafts=tuple(
                GroundWorkspaceMemoryDraft.from_dict(item) for item in memories
            ),
            created_at=_timestamp_value(
                value["created_at"],
                label="created time",
            ),
            updated_at=_timestamp_value(
                value["updated_at"],
                label="updated time",
            ),
            revision=value["revision"],  # type: ignore[arg-type]
            schema_version=value["version"],  # type: ignore[arg-type]
        )


def ground_workspace_draft_digest(value: GroundWorkspaceDraft) -> str:
    """Return the canonical digest used by draft CAS and launcher evidence."""

    restored = GroundWorkspaceDraft.from_dict(value.to_dict())
    encoded = json.dumps(
        restored.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "GROUND_WORKSPACE_DRAFT_SCHEMA_VERSION",
    "GroundWorkspaceDraft",
    "GroundWorkspaceDraftError",
    "GroundWorkspaceMemoryDraft",
    "GroundWorkspaceRuleDraft",
    "ground_workspace_draft_digest",
]
