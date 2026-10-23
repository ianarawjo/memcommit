"""Context identities in frozen Update inputs and application receipts."""

from __future__ import annotations

from dataclasses import dataclass

from .changes import (
    _require_exact_keys,
    _require_string,
)


@dataclass(frozen=True)
class ContextFingerprint:
    uid: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "uid": self.uid,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, value: object) -> ContextFingerprint:
        data = _require_exact_keys(
            value,
            {"uid", "name"}
            | ({"digest"} if isinstance(value, dict) and "digest" in value else set()),
            "Context fingerprint",
        )
        return cls(
            uid=_require_string(data["uid"], "Context fingerprint uid"),
            name=_require_string(data["name"], "Context fingerprint name"),
        )
