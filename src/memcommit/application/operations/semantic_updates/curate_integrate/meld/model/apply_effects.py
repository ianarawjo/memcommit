"""Exact Meld change sets and durable Apply effects and receipts."""

from __future__ import annotations

from dataclasses import dataclass

from .integration_proposal import MeldProposal, MeldTurn, meld_turn_evidence_payload
from .source_snapshot import (
    MELD_NAME_LIMIT,
    MeldError,
    MeldFrame,
    MeldMode,
    MeldTarget,
    _MODES,
    _array,
    _canonical_uuid,
    _digest,
    _exact_dict,
    _literal,
    _string,
    _unique_identifiers,
    meld_canonical_digest,
)


@dataclass(frozen=True)
class MeldChangeSet:
    session_uid: str
    turn_uid: str
    mode: MeldMode
    target_uid: str
    target_digest: str
    source_frame_digests: tuple[tuple[str, str], ...]
    turn_digests: tuple[tuple[str, str], ...]
    proposals: tuple[MeldProposal, ...]
    digest: str

    def _payload(self) -> dict[str, object]:
        return {
            "session_uid": self.session_uid,
            "turn_uid": self.turn_uid,
            "mode": self.mode,
            "target_uid": self.target_uid,
            "target_digest": self.target_digest,
            "source_frame_digests": [
                {"frame_uid": frame_uid, "digest": digest}
                for frame_uid, digest in self.source_frame_digests
            ],
            "turn_digests": [
                {"turn_uid": turn_uid, "digest": digest}
                for turn_uid, digest in self.turn_digests
            ],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
        }

    @classmethod
    def create(
        cls,
        *,
        session_uid: str,
        turn_uid: str,
        mode: MeldMode,
        target: MeldTarget,
        frames: tuple[MeldFrame, ...],
        turns: tuple[MeldTurn, ...],
        proposals: tuple[MeldProposal, ...],
    ) -> "MeldChangeSet":
        payload = {
            "session_uid": session_uid,
            "turn_uid": turn_uid,
            "mode": mode,
            "target_uid": target.context_uid,
            "target_digest": target.context_digest,
            "source_frame_digests": [
                {
                    "frame_uid": frame.uid,
                    "digest": frame.context_digest,
                }
                for frame in frames
            ],
            "turn_digests": [
                {
                    "turn_uid": turn.uid,
                    "digest": meld_canonical_digest(meld_turn_evidence_payload(turn)),
                }
                for turn in turns
            ],
            "proposals": [proposal.to_dict() for proposal in proposals],
        }
        return cls.from_dict(
            {
                **payload,
                "digest": meld_canonical_digest(payload),
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, value: object) -> "MeldChangeSet":
        data = _exact_dict(
            value,
            {
                "session_uid",
                "turn_uid",
                "mode",
                "target_uid",
                "target_digest",
                "source_frame_digests",
                "turn_digests",
                "proposals",
                "digest",
            },
            "meld change set",
        )
        source_frame_digests: list[tuple[str, str]] = []
        for item in _array(
            data["source_frame_digests"],
            "meld change-set source frame digests",
        ):
            record = _exact_dict(
                item,
                {"frame_uid", "digest"},
                "meld change-set source frame digest",
            )
            source_frame_digests.append(
                (
                    _canonical_uuid(
                        record["frame_uid"],
                        "meld change-set frame uid",
                    ),
                    _digest(
                        record["digest"],
                        "meld change-set frame digest",
                    ),
                )
            )
        turn_digests: list[tuple[str, str]] = []
        for item in _array(
            data["turn_digests"],
            "meld change-set turn digests",
        ):
            record = _exact_dict(
                item,
                {"turn_uid", "digest"},
                "meld change-set turn digest",
            )
            turn_digests.append(
                (
                    _canonical_uuid(
                        record["turn_uid"],
                        "meld change-set turn uid",
                    ),
                    _digest(
                        record["digest"],
                        "meld change-set turn digest",
                    ),
                )
            )
        proposals = tuple(
            MeldProposal.from_dict(item)
            for item in _array(
                data["proposals"],
                "meld change-set proposals",
            )
        )
        mode = _literal(
            data["mode"],
            _MODES,
            "meld change-set mode",
        )
        if (
            not source_frame_digests
            or len({uid for uid, _ in source_frame_digests})
            != len(source_frame_digests)
            or not turn_digests
            or len({uid for uid, _ in turn_digests}) != len(turn_digests)
            or (
                mode == "SYMMETRIC"
                and (
                    not proposals
                    or any(proposal.operation != "ADD" for proposal in proposals)
                )
            )
        ):
            raise MeldError("Invalid meld change set.")
        result = cls(
            session_uid=_canonical_uuid(
                data["session_uid"],
                "meld change-set session uid",
            ),
            turn_uid=_canonical_uuid(
                data["turn_uid"],
                "meld change-set turn uid",
            ),
            mode=mode,  # type: ignore[arg-type]
            target_uid=_canonical_uuid(
                data["target_uid"],
                "meld change-set target uid",
            ),
            target_digest=_digest(
                data["target_digest"],
                "meld change-set target digest",
            ),
            source_frame_digests=tuple(source_frame_digests),
            turn_digests=tuple(turn_digests),
            proposals=proposals,
            digest=_digest(data["digest"], "meld change-set digest"),
        )
        frame_uids = {frame_uid for frame_uid, _ in result.source_frame_digests}
        turn_uids = {turn_uid for turn_uid, _ in result.turn_digests}
        if (
            result.turn_uid not in turn_uids
            or any(
                member.frame_uid not in frame_uids
                for proposal in result.proposals
                for member in proposal.source_members
            )
            or any(
                not set(proposal.grounded_by_turn_uids) <= turn_uids
                for proposal in result.proposals
            )
            or any(
                proposal.disposition == "USER_ADD" and proposal.source_members
                for proposal in result.proposals
            )
            or any(
                proposal.disposition != "USER_ADD" and not proposal.source_members
                for proposal in result.proposals
            )
        ):
            raise MeldError("Invalid meld change-set evidence.")
        if result.digest != meld_canonical_digest(result._payload()):
            raise MeldError("Meld change-set digest does not match.")
        return result


@dataclass(frozen=True)
class MeldCheckpointReceipt:
    context_uid: str
    context_name: str
    checkpoint_uid: str

    def to_dict(self) -> dict[str, str]:
        return {
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "checkpoint_uid": self.checkpoint_uid,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldCheckpointReceipt":
        data = _exact_dict(
            value,
            {"context_uid", "context_name", "checkpoint_uid"},
            "meld checkpoint receipt",
        )
        return cls(
            context_uid=_canonical_uuid(
                data["context_uid"],
                "meld checkpoint owner Context uid",
            ),
            context_name=_string(
                data["context_name"],
                "meld checkpoint owner Context name",
                limit=MELD_NAME_LIMIT,
            ),
            checkpoint_uid=_canonical_uuid(
                data["checkpoint_uid"],
                "meld application checkpoint uid",
            ),
        )


@dataclass(frozen=True)
class MeldApplication:
    change_set_digest: str
    checkpoint_uid: str
    result_memory_uids: tuple[str, ...]
    checkpoints: tuple[MeldCheckpointReceipt, ...] = ()

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "change_set_digest": self.change_set_digest,
            "checkpoint_uid": self.checkpoint_uid,
            "result_memory_uids": list(self.result_memory_uids),
        }
        if self.checkpoints:
            result["checkpoints"] = [item.to_dict() for item in self.checkpoints]
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldApplication":
        keys = {
            "change_set_digest",
            "checkpoint_uid",
            "result_memory_uids",
        }
        if isinstance(value, dict) and "checkpoints" in value:
            keys.add("checkpoints")
        data = _exact_dict(value, keys, "meld application")
        checkpoints = tuple(
            MeldCheckpointReceipt.from_dict(item)
            for item in _array(data.get("checkpoints", []), "meld checkpoints")
        )
        identities = [(item.context_uid, item.context_name) for item in checkpoints]
        if (
            len(identities) != len(set(identities))
            or len({item.context_uid for item in checkpoints}) != len(checkpoints)
            or len({item.context_name for item in checkpoints}) != len(checkpoints)
            or len({item.checkpoint_uid for item in checkpoints}) != len(checkpoints)
            or (checkpoints and checkpoints[0].checkpoint_uid != data["checkpoint_uid"])
        ):
            raise MeldError("Invalid meld application checkpoints.")
        return cls(
            change_set_digest=_digest(
                data["change_set_digest"],
                "meld application change-set digest",
            ),
            checkpoint_uid=_canonical_uuid(
                data["checkpoint_uid"],
                "meld application checkpoint uid",
            ),
            result_memory_uids=_unique_identifiers(
                data["result_memory_uids"],
                "meld application result Memory uids",
                empty=True,
                uuids=True,
            ),
            checkpoints=checkpoints,
        )
