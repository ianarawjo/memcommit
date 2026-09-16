"""Receipt for one verified candidate Meld publication."""

from dataclasses import dataclass
from .source_snapshot import _exact_dict, _digest, _canonical_uuid, _unique_identifiers


@dataclass(frozen=True)
class MeldApplication:
    change_set_digest: str
    checkpoint_uid: str
    result_memory_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "change_set_digest": self.change_set_digest,
            "checkpoint_uid": self.checkpoint_uid,
            "result_memory_uids": list(self.result_memory_uids),
        }
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldApplication":
        data = _exact_dict(
            value,
            {"change_set_digest", "checkpoint_uid", "result_memory_uids"},
            "Meld application",
        )
        return cls(
            change_set_digest=_digest(
                data["change_set_digest"], "Meld application digest"
            ),
            checkpoint_uid=_canonical_uuid(
                data["checkpoint_uid"], "Meld checkpoint uid"
            ),
            result_memory_uids=_unique_identifiers(
                data["result_memory_uids"], "Meld result uids", empty=True, uuids=True
            ),
        )
