"""Typed values for one append-only Elaborate revision."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal


ELABORATE_SEPARATOR = "\n\n"
ElaborateDisposition = Literal["EXPAND", "KEEP"]


@dataclass(frozen=True)
class ElaborateSource:
    """One directly owned Memory exposed under a temporary provider alias."""

    alias: str
    memory_uid: str
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.alias, str) or not self.alias:
            raise ValueError("Elaborate source alias must be nonempty text.")
        if not isinstance(self.memory_uid, str) or not self.memory_uid:
            raise ValueError("Elaborate source Memory uid must be nonempty text.")
        if not isinstance(self.content, str):
            raise ValueError("Elaborate source content must be text.")


@dataclass(frozen=True)
class ElaborateFrame:
    """One exact target and its read-only direct-Memory context."""

    context_uid: str
    context_name: str
    context_digest: str
    target_alias: str
    sources: tuple[ElaborateSource, ...]

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (
                self.context_uid,
                self.context_name,
                self.context_digest,
                self.target_alias,
            )
        ):
            raise ValueError("Elaborate frame identity is incomplete.")
        if (
            not isinstance(self.sources, tuple)
            or not self.sources
            or any(not isinstance(source, ElaborateSource) for source in self.sources)
        ):
            raise ValueError("Elaborate frame requires directly owned Memories.")
        aliases = tuple(source.alias for source in self.sources)
        uids = tuple(source.memory_uid for source in self.sources)
        if len(set(aliases)) != len(aliases) or len(set(uids)) != len(uids):
            raise ValueError("Elaborate frame repeats a source identity.")
        if self.target_alias not in aliases:
            raise ValueError("Elaborate target is absent from its source frame.")
        if not self.target.content.strip():
            raise ValueError("Elaborate target Memory must contain nonblank text.")

    @property
    def target(self) -> ElaborateSource:
        return next(
            source for source in self.sources if source.alias == self.target_alias
        )


@dataclass(frozen=True)
class ElaborateRevision:
    """A provider-supported continuation and its deterministic same-UID result."""

    context_uid: str
    context_name: str
    context_digest: str
    memory_uid: str
    disposition: ElaborateDisposition
    original_content: str
    continuation: str
    content: str
    reason: str
    source_memory_uids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.disposition not in {"EXPAND", "KEEP"}:
            raise ValueError("Elaborate revision disposition is invalid.")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.context_uid,
                self.context_name,
                self.context_digest,
                self.memory_uid,
                self.original_content,
                self.reason,
            )
        ):
            raise ValueError("Elaborate revision is incomplete.")
        if not isinstance(self.continuation, str) or not isinstance(self.content, str):
            raise ValueError("Elaborate revision content must be text.")
        if (
            not isinstance(self.source_memory_uids, tuple)
            or not self.source_memory_uids
            or any(
                not isinstance(uid, str) or not uid
                for uid in self.source_memory_uids
            )
            or len(set(self.source_memory_uids)) != len(self.source_memory_uids)
        ):
            raise ValueError("Elaborate revision requires distinct source Memories.")
        if self.memory_uid not in self.source_memory_uids:
            raise ValueError("Elaborate revision must cite its target Memory.")

        if self.disposition == "KEEP":
            if self.continuation or self.content != self.original_content:
                raise ValueError("KEEP cannot append or replace Memory content.")
            return

        if not self.continuation.strip():
            raise ValueError("EXPAND requires a nonblank continuation.")
        expected = self.original_content + ELABORATE_SEPARATOR + self.continuation
        if self.content != expected:
            raise ValueError(
                "Elaborate result must preserve the original byte-for-byte and "
                "append only the proposed continuation."
            )

    @property
    def changed(self) -> bool:
        return self.disposition == "EXPAND"

    @property
    def revision(self) -> str:
        encoded = json.dumps(
            {
                "context_uid": self.context_uid,
                "context_digest": self.context_digest,
                "memory_uid": self.memory_uid,
                "disposition": self.disposition,
                "continuation": self.continuation,
                "reason": self.reason,
                "source_memory_uids": self.source_memory_uids,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ELABORATE_SEPARATOR",
    "ElaborateDisposition",
    "ElaborateFrame",
    "ElaborateRevision",
    "ElaborateSource",
]
