"""Requests for Store-owned automatic checkpoint creation."""

from dataclasses import dataclass
from typing import Any


@dataclass
class AutoCheckpointRequest:
    """Identify the command whose saved Context needs a checkpoint."""

    command: str
    command_details: dict[str, Any]
