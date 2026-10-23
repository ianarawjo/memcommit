"""Persisted Context checkpoint records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class Checkpoint:
    """Point-in-time snapshot of a context's direct state."""

    uid: str
    timestamp: datetime
    snapshot: dict[str, Any]  # result of context.to_dict() at checkpoint time
    command: Optional[str] = None
    command_details: Optional[dict[str, Any]] = None
    checkpoint_message: str | None = None
    auto: bool = False
