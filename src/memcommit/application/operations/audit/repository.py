"""Persistence port for immutable completed Audit records."""

from __future__ import annotations

from typing import Protocol

from .model import QualityAuditSession


class AuditRecordRepository(Protocol):
    """Store and retrieve completed Audits by their stable UID."""

    def create(self, record: QualityAuditSession) -> None:
        """Create one immutable record; reject an existing UID."""

    def load(self, uid: str) -> QualityAuditSession:
        """Load one exact completed Audit."""

    def list(self) -> tuple[QualityAuditSession, ...]:
        """List all completed Audits visible in this repository."""

    def modified_at(self, uid: str) -> float | None:
        """Return repository modification time when the record still exists."""


__all__ = ["AuditRecordRepository"]
