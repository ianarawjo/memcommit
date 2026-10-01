"""Frozen Context fingerprints and durable Update application receipts."""

from __future__ import annotations

from dataclasses import dataclass

from .changes import (
    _is_sha256,
    _require_exact_keys,
    _require_string,
)


@dataclass(frozen=True)
class ContextFingerprint:
    uid: str
    name: str
    digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "uid": self.uid,
            "name": self.name,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> ContextFingerprint:
        data = _require_exact_keys(
            value,
            {"uid", "name", "digest"},
            "Context fingerprint",
        )
        digest = data["digest"]
        if not _is_sha256(digest):
            raise ValueError("Invalid Context fingerprint digest.")
        return cls(
            uid=_require_string(data["uid"], "Context fingerprint uid"),
            name=_require_string(data["name"], "Context fingerprint name"),
            digest=digest,
        )
