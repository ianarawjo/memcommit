"""Current Audit–Resolve–Update session and its durable lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, replace
from .candidate import MeldCandidateReview
from .apply_effects import MeldApplication
from .source_snapshot import (
    MELD_CANDIDATE_SCHEMA_VERSION,
    MeldError,
    MeldFrame,
    MeldMode,
    MeldState,
    MeldTarget,
    _array,
    _canonical_uuid,
    _exact_dict,
    _literal,
    _MODES,
    _STATES,
)


@dataclass
class MeldSession:
    uid: str
    mode: MeldMode
    frames: tuple[MeldFrame, ...]
    target: MeldTarget
    candidate_review: MeldCandidateReview | None = None
    state: MeldState = "PENDING_ANALYSIS"
    application: MeldApplication | None = None
    schema_version: int = MELD_CANDIDATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "uid": self.uid,
            "mode": self.mode,
            "frames": [frame.to_dict() for frame in self.frames],
            "target": self.target.to_dict(),
            "state": self.state,
            "candidate_review": self.candidate_review.to_dict()
            if self.candidate_review
            else None,
            "application": self.application.to_dict() if self.application else None,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldSession":
        if (
            not isinstance(value, dict)
            or type(value.get("schema_version")) is not int
            or value["schema_version"] != MELD_CANDIDATE_SCHEMA_VERSION
        ):
            raise MeldError(
                "Unsupported Meld session schema; start a new candidate Meld."
            )
        data = _exact_dict(
            value,
            {
                "schema_version",
                "uid",
                "mode",
                "frames",
                "target",
                "state",
                "candidate_review",
                "application",
            },
            "Meld candidate session",
        )
        session = cls(
            uid=_canonical_uuid(data["uid"], "Meld session uid"),
            mode=_literal(data["mode"], _MODES, "Meld mode"),
            frames=tuple(
                MeldFrame.from_dict(item)
                for item in _array(data["frames"], "Meld frames")
            ),
            target=MeldTarget.from_dict(data["target"]),
            state=_literal(data["state"], _STATES, "Meld state"),
            candidate_review=MeldCandidateReview.from_dict(data["candidate_review"]),
            application=None
            if data["application"] is None
            else MeldApplication.from_dict(data["application"]),
        )
        session.validate()
        return session

    def record_review(self, review: MeldCandidateReview) -> None:
        if self.state not in {"PENDING_ANALYSIS", "AWAITING_REPLY"}:
            raise MeldError("Only an active Meld may receive a candidate review.")
        self._transition(
            candidate_review=review, state="AWAITING_REPLY", application=None
        )

    def record_application(
        self, review: MeldCandidateReview, application: MeldApplication
    ) -> None:
        if self.state != "AWAITING_REPLY":
            raise MeldError("Only a reviewed Meld may be applied.")
        self._transition(
            candidate_review=review, state="APPLIED", application=application
        )

    def _transition(self, **changes) -> None:
        # Validate before publishing fields so rejected transitions leave the session intact.
        updated = replace(self, **changes)
        updated.validate()
        for name, value in changes.items():
            setattr(self, name, value)

    def validate(self) -> None:
        """Validate the complete frozen candidate and publication receipt."""

        if (
            type(self.schema_version) is not int
            or self.schema_version != MELD_CANDIDATE_SCHEMA_VERSION
        ):
            raise MeldError("Unsupported Meld session schema.")
        _canonical_uuid(self.uid, "Meld session uid")
        _literal(self.mode, _MODES, "Meld mode")
        if len(self.frames) != 2 or self.candidate_review is None:
            raise MeldError(
                "A candidate Meld session requires two Sources and a review."
            )
        if (
            len({frame.uid for frame in self.frames}) != 2
            or len({frame.context_uid for frame in self.frames}) != 2
            or len({frame.context_name for frame in self.frames}) != 2
        ):
            raise MeldError("Candidate Meld Source frames must be distinct.")
        if self.mode == "SYMMETRIC":
            if any(frame.role != "PEER" for frame in self.frames):
                raise MeldError("Symmetric candidate Meld requires two PEER frames.")
            if self.target.context_uid in {
                frame.context_uid for frame in self.frames
            } or self.target.context_name in {
                frame.context_name for frame in self.frames
            }:
                raise MeldError("Symmetric candidate target overlaps a Source.")
        else:
            incoming, baseline = self.frames
            if incoming.role != "INCOMING" or baseline.role != "BASELINE":
                raise MeldError(
                    "Directional candidate Meld requires INCOMING and BASELINE."
                )
            if (
                self.target.context_uid != baseline.context_uid
                or self.target.context_name != baseline.context_name
                or self.target.context_digest != baseline.context_digest
            ):
                raise MeldError("Directional candidate target must match its BASELINE.")
        source_keys = {
            (frame.uid, memory.uid)
            for frame in self.frames
            for memory in frame.memories
        }
        claim_keys = {
            (claim.frame_uid, claim.memory_uid)
            for claim in self.candidate_review.source_claims
        }
        if claim_keys != source_keys or len(claim_keys) != len(
            self.candidate_review.source_claims
        ):
            raise MeldError(
                "Candidate Meld must bind every Source Memory exactly once."
            )
        source_by_key = {
            (frame.uid, memory.uid): (frame, memory)
            for frame in self.frames
            for memory in frame.memories
        }
        for claim in self.candidate_review.source_claims:
            frame, memory = source_by_key[(claim.frame_uid, claim.memory_uid)]
            if (
                claim.context_uid != frame.context_uid
                or claim.context_name != frame.context_name
                or claim.content != memory.content
            ):
                raise MeldError(
                    "Candidate Meld Source claim changed its frozen evidence."
                )
        if self.state not in {
            "AWAITING_REPLY",
            "UNDONE",
            "APPLIED",
        }:
            raise MeldError("Candidate Meld has an invalid lifecycle state.")
        if any(frame.include_descendants for frame in self.frames):
            raise MeldError("Candidate Meld supports direct Source frames only.")
        if self.state in {"APPLIED", "UNDONE"}:
            if self.application is None:
                raise MeldError(
                    "Applied candidate Meld requires an application receipt."
                )
            validated = MeldApplication.from_dict(self.application.to_dict())
            from memcommit.core.context import Memory

            expected = tuple(
                item.uid
                for item in self.candidate_review.candidate.iter_items()
                if isinstance(item, Memory)
            )
            if validated.result_memory_uids != expected or self.candidate_review.issues:
                raise MeldError("Meld receipt does not match its verified candidate.")
        elif self.application is not None:
            raise MeldError(
                "Only an applied or undone candidate Meld may retain a receipt."
            )

    def restore_application(
        self, application: MeldApplication, *, direction: str
    ) -> None:
        """Undo/Redo retain the exact receipt; neither reopens semantic execution."""
        expected, following = (
            ("APPLIED", "UNDONE") if direction == "undo" else ("UNDONE", "APPLIED")
        )
        if (
            direction not in {"undo", "redo"}
            or self.state != expected
            or self.application != application
        ):
            raise MeldError(
                "Meld restoration does not match its exact application receipt."
            )
        self._transition(state=following)
