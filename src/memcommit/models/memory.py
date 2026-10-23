"""One atomic Memory with durable identity and exact content."""

from __future__ import annotations

import uuid
from typing import Any


class Memory:
    """Atomic chunk of information."""

    def __init__(self, uid: str, content: str):
        self.uid = uid
        self.content = content

    @classmethod
    def create(cls, content: str) -> Memory:
        return cls(uid=str(uuid.uuid4()), content=content)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "memory", "uid": self.uid, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls(uid=data["uid"], content=data["content"])
