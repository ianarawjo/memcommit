"""Strict, retained state for one local disclosure-severing review."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.update import GrantedUpdateTarget


SEVER_SCHEMA_VERSION = 1
SeverDecision = Literal[
    "SEND_AS_WRITTEN",
    "SEND_REDACTED",
    "SEND_SUMMARY",
    "SEND_PREFERENCE_OR_POLICY",
    "DO_NOT_SEND",
]
SeverSelection = Literal["RECOMMENDED", "AS_WRITTEN", "EXCLUDE", "CUSTOM"]
SeverState = Literal["REVIEWING", "APPLIED"]

_DECISIONS = {
    "SEND_AS_WRITTEN",
    "SEND_REDACTED",
    "SEND_SUMMARY",
    "SEND_PREFERENCE_OR_POLICY",
    "DO_NOT_SEND",
}
_SELECTIONS = {"RECOMMENDED", "AS_WRITTEN", "EXCLUDE", "CUSTOM"}


class SeverError(ValueError):
    """A Sever artifact or state transition is invalid."""


def _text(value: object, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise SeverError(f"Invalid Sever {label}.")
    return value


def _uuid(value: object, label: str) -> str:
    text = _text(value, label)
    try:
        canonical = str(uuid.UUID(text))
    except ValueError as error:
        raise SeverError(f"Invalid Sever {label}.") from error
    if canonical != text:
        raise SeverError(f"Invalid Sever {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SeverError(f"Invalid Sever {label}.")
    return text


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SeverError(f"Invalid Sever {label}.")
    return value


@dataclass(frozen=True)
class SeverMemory:
    uid: str
    context_name: str
    content: str

    def __post_init__(self) -> None:
        _uuid(self.uid, "Memory uid")
        _text(self.context_name, "Memory owner")
        _text(self.content, "Memory content")

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "context_name": self.context_name, "content": self.content}

    @classmethod
    def from_dict(cls, value: object) -> "SeverMemory":
        data = _exact(value, {"uid", "context_name", "content"}, "Memory")
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True)
class SeverContextBinding:
    """One retained ordinary Context frame and its direct CAS set."""

    root_uid: str
    root_name: str
    frame_digest: str
    contexts: tuple[tuple[str, str, str], ...]
    memories: tuple[SeverMemory, ...]
    granted: dict[str, object] | None = None
    include_descendants: bool = True

    def __post_init__(self) -> None:
        _uuid(self.root_uid, "Context uid")
        _text(self.root_name, "Context name")
        _digest(self.frame_digest, "Context frame digest")
        if not self.contexts or any(
            not isinstance(item, tuple)
            or len(item) != 3
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
            or not isinstance(item[2], str)
            for item in self.contexts
        ):
            raise SeverError("Invalid Sever Context bindings.")
        for name, uid, digest in self.contexts:
            _text(name, "bound Context name")
            _uuid(uid, "bound Context uid")
            _digest(digest, "bound Context digest")
        if len({memory.uid for memory in self.memories}) != len(self.memories):
            raise SeverError("Duplicate Sever Memory uid.")
        if type(self.include_descendants) is not bool:
            raise SeverError("Invalid Sever descendant scope.")
        if self.granted is not None:
            if not isinstance(self.granted, dict):
                raise SeverError("Invalid Sever granted binding.")
            try:
                normalized = GrantedUpdateTarget.from_dict(self.granted).to_dict()
            except ValueError as error:
                raise SeverError("Invalid Sever granted binding.") from error
            if normalized != self.granted:
                raise SeverError("Invalid Sever granted binding.")

    def to_dict(self) -> dict[str, object]:
        return {
            "root_uid": self.root_uid,
            "root_name": self.root_name,
            "frame_digest": self.frame_digest,
            "contexts": [
                {"name": name, "uid": uid, "digest": digest}
                for name, uid, digest in self.contexts
            ],
            "memories": [memory.to_dict() for memory in self.memories],
            "granted": self.granted,
            "include_descendants": self.include_descendants,
        }

    @classmethod
    def from_dict(cls, value: object) -> "SeverContextBinding":
        if not isinstance(value, dict):
            raise SeverError("Invalid Sever Context binding.")
        legacy_keys = {
            "root_uid", "root_name", "frame_digest", "contexts", "memories", "granted"
        }
        if frozenset(value) not in {
            frozenset(legacy_keys),
            frozenset(legacy_keys | {"include_descendants"}),
        }:
            raise SeverError("Invalid Sever Context binding.")
        data = value
        raw_contexts = data["contexts"]
        raw_memories = data["memories"]
        if not isinstance(raw_contexts, list) or not isinstance(raw_memories, list):
            raise SeverError("Invalid Sever Context binding.")
        contexts: list[tuple[str, str, str]] = []
        for item in raw_contexts:
            record = _exact(item, {"name", "uid", "digest"}, "bound Context")
            contexts.append((record["name"], record["uid"], record["digest"]))  # type: ignore[arg-type]
        return cls(
            root_uid=data["root_uid"],  # type: ignore[arg-type]
            root_name=data["root_name"],  # type: ignore[arg-type]
            frame_digest=data["frame_digest"],  # type: ignore[arg-type]
            contexts=tuple(contexts),
            memories=tuple(SeverMemory.from_dict(item) for item in raw_memories),
            granted=data["granted"],  # type: ignore[arg-type]
            include_descendants=data.get("include_descendants", True),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class SeverCandidate:
    uid: str
    source_memory_uid: str
    recommendation: SeverDecision
    proposed_content: str
    rationale: str
    criterion_memory_uids: tuple[str, ...]
    selection: SeverSelection = "RECOMMENDED"
    custom_content: str = ""

    def __post_init__(self) -> None:
        _uuid(self.uid, "candidate uid")
        _uuid(self.source_memory_uid, "candidate source uid")
        if self.recommendation not in _DECISIONS:
            raise SeverError("Invalid Sever recommendation.")
        _text(self.proposed_content, "proposed content", empty=True)
        _text(self.rationale, "candidate rationale")
        if self.recommendation == "DO_NOT_SEND":
            if self.proposed_content:
                raise SeverError("Excluded Sever candidates cannot have outbound content.")
        elif not self.proposed_content.strip():
            raise SeverError("Included Sever candidates require outbound content.")
        if self.selection not in _SELECTIONS:
            raise SeverError("Invalid Sever selection.")
        if self.selection == "CUSTOM" and not self.custom_content.strip():
            raise SeverError("Custom Sever selection requires content.")
        if self.selection != "CUSTOM" and self.custom_content:
            raise SeverError("Only a custom Sever selection may store custom content.")
        if len(set(self.criterion_memory_uids)) != len(self.criterion_memory_uids):
            raise SeverError("Duplicate Sever criterion reference.")

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "source_memory_uid": self.source_memory_uid,
            "recommendation": self.recommendation,
            "proposed_content": self.proposed_content,
            "rationale": self.rationale,
            "criterion_memory_uids": list(self.criterion_memory_uids),
            "selection": self.selection,
            "custom_content": self.custom_content,
        }

    @classmethod
    def from_dict(cls, value: object) -> "SeverCandidate":
        data = _exact(
            value,
            {
                "uid", "source_memory_uid", "recommendation", "proposed_content",
                "rationale", "criterion_memory_uids", "selection", "custom_content",
            },
            "candidate",
        )
        refs = data["criterion_memory_uids"]
        if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
            raise SeverError("Invalid Sever criterion references.")
        return cls(
            uid=data["uid"],  # type: ignore[arg-type]
            source_memory_uid=data["source_memory_uid"],  # type: ignore[arg-type]
            recommendation=data["recommendation"],  # type: ignore[arg-type]
            proposed_content=data["proposed_content"],  # type: ignore[arg-type]
            rationale=data["rationale"],  # type: ignore[arg-type]
            criterion_memory_uids=tuple(refs),
            selection=data["selection"],  # type: ignore[arg-type]
            custom_content=data["custom_content"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class SeverApplication:
    output_context_uid: str
    checkpoint_uid: str
    result_memory_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "output_context_uid": self.output_context_uid,
            "checkpoint_uid": self.checkpoint_uid,
            "result_memory_uids": list(self.result_memory_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "SeverApplication":
        data = _exact(
            value,
            {"output_context_uid", "checkpoint_uid", "result_memory_uids"},
            "application",
        )
        uids = data["result_memory_uids"]
        if not isinstance(uids, list):
            raise SeverError("Invalid Sever result Memory uids.")
        return cls(
            output_context_uid=_uuid(data["output_context_uid"], "output Context uid"),
            checkpoint_uid=_uuid(data["checkpoint_uid"], "checkpoint uid"),
            result_memory_uids=tuple(_uuid(item, "result Memory uid") for item in uids),
        )


@dataclass(frozen=True)
class SeverSession:
    uid: str
    revision: int
    state: SeverState
    source: SeverContextBinding
    criteria: SeverContextBinding
    output_name: str
    overview: str
    candidates: tuple[SeverCandidate, ...]
    application: SeverApplication | None = None

    def __post_init__(self) -> None:
        _uuid(self.uid, "session uid")
        if not isinstance(self.revision, int) or isinstance(self.revision, bool) or self.revision < 1:
            raise SeverError("Invalid Sever revision.")
        if self.state not in {"REVIEWING", "APPLIED"}:
            raise SeverError("Invalid Sever state.")
        _text(self.output_name, "output name")
        _text(self.overview, "overview")
        if not self.candidates:
            raise SeverError("A Sever session requires candidates.")
        source_uids = {memory.uid for memory in self.source.memories}
        criterion_uids = {memory.uid for memory in self.criteria.memories}
        if len({candidate.source_memory_uid for candidate in self.candidates}) != len(self.candidates):
            raise SeverError("Duplicate Sever source candidate.")
        if {candidate.source_memory_uid for candidate in self.candidates} != source_uids:
            raise SeverError("Sever candidates must cover every source Memory exactly once.")
        if any(not set(candidate.criterion_memory_uids) <= criterion_uids for candidate in self.candidates):
            raise SeverError("Sever candidate cites an unavailable criterion Memory.")
        if (self.state == "APPLIED") != (self.application is not None):
            raise SeverError("Invalid Sever application state.")

    def source_memory(self, uid: str) -> SeverMemory:
        matches = [memory for memory in self.source.memories if memory.uid == uid]
        if len(matches) != 1:
            raise SeverError("Unknown Sever source Memory.")
        return matches[0]

    def select(self, candidate_uid: str, selection: SeverSelection, custom: str = "") -> "SeverSession":
        if self.state != "REVIEWING":
            raise SeverError("An applied Sever session cannot be edited.")
        updated: list[SeverCandidate] = []
        found = False
        for candidate in self.candidates:
            if candidate.uid != candidate_uid:
                updated.append(candidate)
                continue
            found = True
            updated.append(
                replace(
                    candidate,
                    selection=selection,
                    custom_content=custom if selection == "CUSTOM" else "",
                )
            )
        if not found:
            raise SeverError("Unknown Sever candidate.")
        return replace(self, revision=self.revision + 1, candidates=tuple(updated))

    def outbound(self) -> tuple[tuple[SeverCandidate, SeverMemory, str], ...]:
        results: list[tuple[SeverCandidate, SeverMemory, str]] = []
        for candidate in self.candidates:
            source = self.source_memory(candidate.source_memory_uid)
            if candidate.selection == "EXCLUDE":
                continue
            if candidate.selection == "AS_WRITTEN":
                content = source.content
            elif candidate.selection == "CUSTOM":
                content = candidate.custom_content
            elif candidate.recommendation == "DO_NOT_SEND":
                continue
            else:
                content = candidate.proposed_content
            results.append((candidate, source, content))
        return tuple(results)

    def with_application(self, application: SeverApplication) -> "SeverSession":
        if self.state != "REVIEWING":
            raise SeverError("Only a reviewing Sever session can be applied.")
        return replace(
            self,
            revision=self.revision + 1,
            state="APPLIED",
            application=application,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SEVER_SCHEMA_VERSION,
            "uid": self.uid,
            "revision": self.revision,
            "state": self.state,
            "source": self.source.to_dict(),
            "criteria": self.criteria.to_dict(),
            "output_name": self.output_name,
            "overview": self.overview,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "application": self.application.to_dict() if self.application else None,
        }

    @classmethod
    def from_dict(cls, value: object) -> "SeverSession":
        data = _exact(
            value,
            {
                "schema_version", "uid", "revision", "state", "source", "criteria",
                "output_name", "overview", "candidates", "application",
            },
            "session",
        )
        if data["schema_version"] != SEVER_SCHEMA_VERSION:
            raise SeverError("Unsupported Sever schema version.")
        candidates = data["candidates"]
        if not isinstance(candidates, list):
            raise SeverError("Invalid Sever candidates.")
        return cls(
            uid=data["uid"],  # type: ignore[arg-type]
            revision=data["revision"],  # type: ignore[arg-type]
            state=data["state"],  # type: ignore[arg-type]
            source=SeverContextBinding.from_dict(data["source"]),
            criteria=SeverContextBinding.from_dict(data["criteria"]),
            output_name=data["output_name"],  # type: ignore[arg-type]
            overview=data["overview"],  # type: ignore[arg-type]
            candidates=tuple(SeverCandidate.from_dict(item) for item in candidates),
            application=(
                None
                if data["application"] is None
                else SeverApplication.from_dict(data["application"])
            ),
        )


def sever_record_digest(value: SeverSession | dict[str, object]) -> str:
    record = value.to_dict() if isinstance(value, SeverSession) else SeverSession.from_dict(value).to_dict()
    encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def sever_frame_digest(
    *,
    root_uid: str,
    root_name: str,
    contexts: tuple[tuple[str, str, str], ...],
    memories: tuple[SeverMemory, ...],
    include_descendants: bool = True,
) -> str:
    payload = {
        "root_uid": root_uid,
        "root_name": root_name,
        "contexts": [list(item) for item in contexts],
        "memories": [memory.to_dict() for memory in memories],
        "include_descendants": include_descendants,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
