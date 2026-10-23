"""One Profile's identity, provenance, and optional project location."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Profile:
    """Profile data; configuration resolves its project root before registration."""

    uid: str
    name: str
    kind: str
    source: dict[str, object] | None = None
    root_dir: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "name": self.name,
            "kind": self.kind,
            "root_dir": self.root_dir,
        }
        if self.source is not None:
            result["source"] = self.source
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        """Restore supplied values without resolving project configuration."""
        return cls(
            uid=data["uid"],
            name=data["name"],
            kind=data["kind"],
            source=data.get("source"),
            root_dir=data.get("root_dir"),
        )
