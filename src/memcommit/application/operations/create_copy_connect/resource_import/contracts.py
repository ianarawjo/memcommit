"""Typed plans and results shared by resource-specific import flows."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.core.context import Memory


@dataclass(frozen=True)
class ContextImportResult:
    """Receipt for one Context or lexical Context-tree import."""

    source_profile: str
    source_context: str
    target_contexts: tuple[str, ...]
    context_count: int
    memory_count: int
    recursive: bool


@dataclass(frozen=True)
class MemoryImportResult:
    """Receipt for one directly owned Memory import."""

    source_profile: str
    source_context: str
    target_context: str
    memory: Memory


@dataclass(frozen=True)
class ContextImportPlan:
    """Frozen identities and counts shown before one Context import."""

    source_profile: str
    source_profile_uid: str
    target_profile: str
    target_profile_uid: str
    source_context: str
    target_contexts: tuple[str, ...]
    source_context_versions: tuple[tuple[str, str, str], ...]
    context_count: int
    memory_count: int
    recursive: bool


@dataclass(frozen=True)
class MemoryImportPlan:
    """Frozen identities shown before one direct Memory import."""

    source_profile: str
    source_profile_uid: str
    target_profile: str
    target_profile_uid: str
    source_context: str
    source_context_uid: str
    source_context_digest: str
    source_memory_uid: str
    source_memory_content_sha256: str
    target_context: str
    target_context_uid: str
    target_context_digest: str
