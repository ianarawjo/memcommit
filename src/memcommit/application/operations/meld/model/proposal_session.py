"""Durable Meld proposal-session construction, lifecycle, and accounting."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import Iterable

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    MEMORY_RELATION_RULESET_VERSION,
    MemoryRelationAnalysis,
)
from memcommit.application.operations.update.model import GrantedUpdateTarget
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import context_record_digest

from .apply_effects import MeldApplication, MeldChangeSet, MeldCheckpointReceipt
from .candidate import MeldCandidateReview
from .integration_proposal import (
    MeldAssessment,
    MeldProposal,
    MeldTurn,
    _relation_analysis_meld_assessment,
    _relation_analysis_meld_frames,
    _relation_local_preservation_assessment,
    directional_relation_basis_assessment,
    validate_meld_turn_lineage,
)
from .source_snapshot import (
    INLINE_MELD_CONTEXT_NAME,
    MELD_CANDIDATE_SCHEMA_VERSION,
    MELD_RELATION_ANALYSIS_SCHEMA_VERSION,
    MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION,
    MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION,
    MELD_GRANTED_SCHEMA_VERSION,
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MELD_LEGACY_SCHEMA_VERSION,
    MELD_MEMORY_FOCUS_SCHEMA_VERSION,
    MELD_OWNER_AWARE_SCHEMA_VERSION,
    MELD_SCHEMA_VERSION,
    MELD_TEXT_LIMIT,
    MeldRelationAnalysisSeed,
    MeldError,
    MeldFrame,
    MeldMode,
    MeldRepairableAssessmentError,
    MeldRevision,
    MeldState,
    MeldTarget,
    MeldTurnScope,
    _MODES,
    _STATES,
    _array,
    _canonical_uuid,
    _exact_dict,
    _literal,
    meld_canonical_digest,
)


@dataclass
class MeldSession:
    uid: str
    mode: MeldMode
    frames: tuple[MeldFrame, ...]
    target: MeldTarget
    schema_version: int = MELD_LEGACY_SCHEMA_VERSION
    relation_analysis_seed: MeldRelationAnalysisSeed | None = None
    granted_incoming: GrantedUpdateTarget | None = None
    granted_target: GrantedUpdateTarget | None = None
    state: MeldState = "PENDING_ANALYSIS"
    turns: tuple[MeldTurn, ...] = ()
    application: MeldApplication | None = None
    candidate_review: MeldCandidateReview | None = None

    @classmethod
    def create_symmetric(
        cls,
        left: Context,
        right: Context,
        target: Context,
    ) -> "MeldSession":
        if left.uid == right.uid or left.name == right.name:
            raise MeldError("Meld source Contexts must be distinct.")
        if target.uid in {left.uid, right.uid} or target.name in {
            left.name,
            right.name,
        }:
            raise MeldError("Symmetric meld target must differ from both sources.")
        session = cls(
            uid=str(uuid.uuid4()),
            mode="SYMMETRIC",
            frames=(
                MeldFrame.from_context(left, role="PEER"),
                MeldFrame.from_context(right, role="PEER"),
            ),
            target=MeldTarget.from_context(target),
        )
        return cls.from_dict(session.to_dict())

    @classmethod
    def create_symmetric_from_relation_analysis(
        cls,
        analysis: MemoryRelationAnalysis,
        target: Context,
    ) -> "MeldSession":
        """Start one target-bound Meld from exact peer-relation analysis."""
        seed = MeldRelationAnalysisSeed.create(analysis)
        frames = _relation_analysis_meld_frames(seed.analysis)
        if target.uid in {frame.context_uid for frame in frames} or (
            target.name in {frame.context_name for frame in frames}
        ):
            raise MeldError("Symmetric meld target must differ from both sources.")
        session = cls(
            uid=str(uuid.uuid4()),
            mode="SYMMETRIC",
            frames=frames,
            target=MeldTarget.from_context(target),
            schema_version=MELD_SCHEMA_VERSION,
            relation_analysis_seed=seed,
        )
        session = cls.from_dict(session.to_dict())
        turn = session.start_initial_analysis()
        session.record_assessment(
            turn.uid,
            _relation_analysis_meld_assessment(seed.analysis),
        )
        return session

    @classmethod
    def create_symmetric_from_comparison(
        cls,
        analysis: MemoryRelationAnalysis,
        target: Context,
    ) -> "MeldSession":
        """Compatibility entry point for the persisted comparison schema."""

        return cls.create_symmetric_from_relation_analysis(analysis, target)

    @classmethod
    def create_directional(
        cls,
        incoming: Context,
        baseline: Context,
        *,
        incoming_descendants: bool | None = None,
        baseline_descendants: bool | None = None,
        granted_incoming: GrantedUpdateTarget | None = None,
        granted_target: GrantedUpdateTarget | None = None,
        incoming_memory_selector: str | None = None,
        baseline_memory_selector: str | None = None,
    ) -> "MeldSession":
        """Bind one incoming Context to an authoritative mutable baseline."""
        if incoming.uid == baseline.uid or incoming.name == baseline.name:
            raise MeldError(
                "Directional meld requires distinct INCOMING and BASELINE Contexts."
            )
        incoming_frame = MeldFrame.from_context(
            incoming,
            role="INCOMING",
            include_descendants=incoming_descendants,
            owner_aware=True,
            memory_selector=incoming_memory_selector,
        )
        baseline_frame = MeldFrame.from_context(
            baseline,
            role="BASELINE",
            include_descendants=baseline_descendants,
            owner_aware=True,
            memory_selector=baseline_memory_selector,
        )
        session = cls(
            uid=str(uuid.uuid4()),
            mode="DIRECTIONAL",
            frames=(incoming_frame, baseline_frame),
            target=MeldTarget.from_baseline_context(
                baseline,
                context_digest=baseline_frame.context_digest,
            ),
            # Owner-aware directional sessions freeze every Context in each
            # selected scope; public names alone are not stable authority.
            schema_version=(
                MELD_MEMORY_FOCUS_SCHEMA_VERSION
                if (
                    incoming_memory_selector is not None
                    or baseline_memory_selector is not None
                )
                else MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION
            ),
            granted_incoming=granted_incoming,
            granted_target=granted_target,
        )
        return cls.from_dict(session.to_dict())

    @classmethod
    def create_directional_from_memory(
        cls,
        content: str,
        baseline: Context,
        *,
        baseline_descendants: bool | None = None,
        baseline_memory_selector: str | None = None,
    ) -> "MeldSession":
        """Bind one process-local Memory frame to an existing BASELINE.

        The synthetic Context shape exists only to reuse Meld's complete frame,
        relation, and provenance contracts.  Its identity and content are
        retained in the saved session; it is never a MemoryStore locator.
        """

        if not isinstance(content, str) or not content.strip():
            raise MeldError("Inline Meld Memory content must be nonempty text.")
        if len(content) > MELD_TEXT_LIMIT:
            raise MeldError("Inline Meld Memory content is too long.")
        incoming = Context(
            uid=str(uuid.uuid4()),
            name=INLINE_MELD_CONTEXT_NAME,
        )
        incoming.add(Memory(uid=str(uuid.uuid4()), content=content))
        session = cls.create_directional(
            incoming,
            baseline,
            incoming_descendants=False,
            baseline_descendants=baseline_descendants,
            baseline_memory_selector=baseline_memory_selector,
        )
        session.schema_version = MELD_INLINE_MEMORY_SCHEMA_VERSION
        return cls.from_dict(session.to_dict())

    @classmethod
    def create_directional_from_relation_analysis(
        cls,
        analysis: MemoryRelationAnalysis,
        incoming: Context,
        baseline: Context,
        *,
        granted_incoming: GrantedUpdateTarget | None = None,
        granted_target: GrantedUpdateTarget | None = None,
    ) -> "MeldSession":
        """Bind Directional materialization to exact peer-relation analysis."""
        seed = MeldRelationAnalysisSeed.create(analysis)
        if incoming.uid == baseline.uid or incoming.name == baseline.name:
            raise MeldError(
                "Directional meld requires distinct INCOMING and BASELINE Contexts."
            )
        incoming_descendants, baseline_descendants = seed.analysis.include_descendants
        incoming_memory_selector = analysis.frames[0].selected_memory_uid
        baseline_memory_selector = analysis.frames[1].selected_memory_uid
        incoming_frame = MeldFrame.from_context(
            incoming,
            role="INCOMING",
            include_descendants=incoming_descendants,
            owner_aware=True,
            memory_selector=incoming_memory_selector,
        )
        baseline_frame = MeldFrame.from_context(
            baseline,
            role="BASELINE",
            include_descendants=baseline_descendants,
            owner_aware=True,
            memory_selector=baseline_memory_selector,
        )
        schema_version = (
            MELD_INLINE_MEMORY_SCHEMA_VERSION
            if incoming.name == INLINE_MELD_CONTEXT_NAME
            else MELD_MEMORY_FOCUS_SCHEMA_VERSION
            if (
                incoming_memory_selector is not None
                or baseline_memory_selector is not None
            )
            else MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION
        )
        session = cls(
            uid=str(uuid.uuid4()),
            mode="DIRECTIONAL",
            frames=(incoming_frame, baseline_frame),
            target=MeldTarget.from_baseline_context(
                baseline,
                context_digest=baseline_frame.context_digest,
            ),
            schema_version=schema_version,
            relation_analysis_seed=seed,
            granted_incoming=granted_incoming,
            granted_target=granted_target,
        )
        return cls.from_dict(session.to_dict())

    @classmethod
    def create_directional_from_comparison(
        cls,
        analysis: MemoryRelationAnalysis,
        incoming: Context,
        baseline: Context,
        *,
        granted_incoming: GrantedUpdateTarget | None = None,
        granted_target: GrantedUpdateTarget | None = None,
    ) -> "MeldSession":
        """Compatibility entry point for the persisted comparison schema."""

        return cls.create_directional_from_relation_analysis(
            analysis,
            incoming,
            baseline,
            granted_incoming=granted_incoming,
            granted_target=granted_target,
        )

    @property
    def comparison_seed(self) -> MeldRelationAnalysisSeed | None:
        """Expose the legacy session attribute without retaining its ownership."""

        return self.relation_analysis_seed

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "uid": self.uid,
            "mode": self.mode,
            "frames": [frame.to_dict() for frame in self.frames],
            "target": self.target.to_dict(),
            "state": self.state,
            "turns": [turn.to_dict() for turn in self.turns],
            "application": (
                self.application.to_dict() if self.application is not None else None
            ),
        }
        if (
            MELD_RELATION_ANALYSIS_SCHEMA_VERSION
            <= self.schema_version
            < MELD_CANDIDATE_SCHEMA_VERSION
        ):
            result["comparison_seed"] = (
                self.relation_analysis_seed.to_dict()
                if self.relation_analysis_seed is not None
                else None
            )
        if self.schema_version >= MELD_GRANTED_SCHEMA_VERSION:
            result["granted_incoming"] = (
                None
                if self.granted_incoming is None
                else self.granted_incoming.to_dict()
            )
            result["granted_target"] = (
                None if self.granted_target is None else self.granted_target.to_dict()
            )
        if self.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
            result["candidate_review"] = (
                None
                if self.candidate_review is None
                else self.candidate_review.to_dict()
            )
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldSession":
        if not isinstance(value, dict):
            raise MeldError("Invalid meld session.")
        schema_version = value.get("schema_version")
        if isinstance(schema_version, bool) or schema_version not in {
            MELD_LEGACY_SCHEMA_VERSION,
            MELD_RELATION_ANALYSIS_SCHEMA_VERSION,
            MELD_SCHEMA_VERSION,
            MELD_GRANTED_SCHEMA_VERSION,
            MELD_OWNER_AWARE_SCHEMA_VERSION,
            MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION,
            MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION,
            MELD_MEMORY_FOCUS_SCHEMA_VERSION,
            MELD_INLINE_MEMORY_SCHEMA_VERSION,
            MELD_CANDIDATE_SCHEMA_VERSION,
        }:
            raise MeldError("Unsupported meld session schema version.")
        keys = {
            "schema_version",
            "uid",
            "mode",
            "frames",
            "target",
            "state",
            "turns",
            "application",
        }
        if (
            MELD_RELATION_ANALYSIS_SCHEMA_VERSION
            <= schema_version
            < MELD_CANDIDATE_SCHEMA_VERSION
        ):
            keys.add("comparison_seed")
        if schema_version >= MELD_GRANTED_SCHEMA_VERSION:
            keys.update({"granted_incoming", "granted_target"})
        if schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
            keys.add("candidate_review")
        data = _exact_dict(
            value,
            keys,
            "meld session",
        )
        frames = tuple(
            MeldFrame.from_dict(item)
            for item in _array(data["frames"], "meld session frames")
        )
        turns = tuple(
            MeldTurn.from_dict(item)
            for item in _array(data["turns"], "meld session turns")
        )
        raw_application = data["application"]
        raw_relation_analysis_seed = (
            data["comparison_seed"]
            if (
                MELD_RELATION_ANALYSIS_SCHEMA_VERSION
                <= schema_version
                < MELD_CANDIDATE_SCHEMA_VERSION
            )
            else None
        )
        session = cls(
            uid=_canonical_uuid(data["uid"], "meld session uid"),
            mode=_literal(
                data["mode"],
                _MODES,
                "meld session mode",
            ),  # type: ignore[arg-type]
            frames=frames,
            target=MeldTarget.from_dict(data["target"]),
            schema_version=schema_version,
            relation_analysis_seed=(
                None
                if raw_relation_analysis_seed is None
                else MeldRelationAnalysisSeed.from_dict(raw_relation_analysis_seed)
            ),
            granted_incoming=(
                None
                if schema_version < MELD_GRANTED_SCHEMA_VERSION
                or data["granted_incoming"] is None
                else GrantedUpdateTarget.from_dict(data["granted_incoming"])
            ),
            granted_target=(
                None
                if schema_version < MELD_GRANTED_SCHEMA_VERSION
                or data["granted_target"] is None
                else GrantedUpdateTarget.from_dict(data["granted_target"])
            ),
            state=_literal(
                data["state"],
                _STATES,
                "meld session state",
            ),  # type: ignore[arg-type]
            turns=turns,
            application=(
                None
                if raw_application is None
                else MeldApplication.from_dict(raw_application)
            ),
            candidate_review=(
                None
                if schema_version != MELD_CANDIDATE_SCHEMA_VERSION
                or data["candidate_review"] is None
                else MeldCandidateReview.from_dict(data["candidate_review"])
            ),
        )
        session._validate()
        return session

    @property
    def current_turn(self) -> MeldTurn | None:
        return self.turns[-1] if self.turns else None

    @property
    def current_assessment(self) -> MeldAssessment | None:
        turn = self.current_turn
        return turn.assessment if turn is not None else None

    @property
    def user_turns(self) -> tuple[MeldTurn, ...]:
        return self.turns[1:] if self.turns else ()

    def start_initial_analysis(self) -> MeldTurn:
        if self.turns or self.state != "PENDING_ANALYSIS":
            raise MeldError("Meld initial analysis is already started.")
        turn = MeldTurn.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "sequence": 0,
                "revision": "INITIAL",
                "scope": "ALL",
                "issue_uids": [],
                "comment": "",
                "revises_turn_uids": [],
                "assessment": None,
            }
        )
        self.turns = (turn,)
        self._validate()
        return turn

    def start_turn(
        self,
        comment: str,
        *,
        scope: MeldTurnScope,
        issue_uids: Iterable[str] = (),
        revision: MeldRevision = "EXTEND",
        revises_turn_uids: Iterable[str] = (),
    ) -> MeldTurn:
        if self.state in {"PENDING_ANALYSIS", "APPLIED", "KEPT_REVIEW_ONLY"}:
            raise MeldError(f"Cannot add a turn while meld is {self.state}.")
        if self.current_turn is None or self.current_turn.assessment is None:
            raise MeldError("The prior meld turn has not been assessed.")
        parsed_issue_uids = tuple(issue_uids)
        current_issue_uids = {issue.uid for issue in self.current_assessment.issues}
        if scope == "ISSUE":
            if (
                not parsed_issue_uids
                or not set(parsed_issue_uids) <= current_issue_uids
            ):
                raise MeldError(
                    "Issue-scoped meld turn names an unknown current issue."
                )
        elif parsed_issue_uids:
            raise MeldError("Only an issue-scoped meld turn may name issue uids.")
        turn = MeldTurn.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "sequence": len(self.turns),
                "revision": revision,
                "scope": scope,
                "issue_uids": list(parsed_issue_uids),
                "comment": comment,
                "revises_turn_uids": list(revises_turn_uids),
                "assessment": None,
            }
        )
        self.turns = (*self.turns, turn)
        self.state = "AWAITING_REPLY"
        self.application = None
        self._validate()
        return turn

    def record_assessment(
        self,
        turn_uid: str,
        assessment: MeldAssessment,
    ) -> None:
        if self.current_turn is None or self.current_turn.uid != turn_uid:
            raise MeldError("Only the latest meld turn can be assessed.")
        if self.current_turn.assessment is not None:
            raise MeldError("The latest meld turn is already assessed.")
        if not isinstance(assessment, MeldAssessment):
            raise MeldError("Invalid meld assessment.")
        self.turns = (
            *self.turns[:-1],
            replace(self.current_turn, assessment=assessment),
        )
        self.state = "READY_TO_APPLY" if assessment.ready_to_apply else "AWAITING_REPLY"
        self._validate()

    def complete_initial_preservation(self) -> None:
        """Materialize one conservative symmetric result without a user turn.

        Peer-relation analysis supplies the exhaustive ledger, while Meld owns the
        target materialization.  Default terminal execution resolves that
        boundary by coalescing equivalents and otherwise preserving each
        source Memory independently; it must not fabricate a submitted
        response merely to make the initial analysis applicable.
        """

        turn = self.current_turn
        assessment = self.current_assessment
        if (
            self.mode != "SYMMETRIC"
            or self.schema_version < MELD_SCHEMA_VERSION
            or self.state != "AWAITING_REPLY"
            or turn is None
            or turn.sequence != 0
            or assessment is None
            or self.application is not None
        ):
            raise MeldError(
                "Conservative Meld completion requires one unapplied initial "
                "symmetric assessment."
            )
        completed = _relation_local_preservation_assessment(
            self,
            assessment,
            turn_uid=turn.uid,
            user_grounded=False,
        )
        self.turns = (*self.turns[:-1], replace(turn, assessment=completed))
        self.state = "READY_TO_APPLY"
        self._validate()

    def prepare_changes(self) -> MeldChangeSet:
        # The exact change set remains derivable after application so retry
        # recovery can verify the saved receipt and current target instead of
        # treating an APPLIED flag as sufficient evidence.
        if self.state not in {"READY_TO_APPLY", "APPLIED"}:
            raise MeldError("Meld is not ready to apply.")
        turn = self.current_turn
        assessment = self.current_assessment
        assert turn is not None and assessment is not None
        return MeldChangeSet.create(
            session_uid=self.uid,
            turn_uid=turn.uid,
            mode=self.mode,
            target=self.target,
            frames=self.frames,
            turns=self.turns,
            proposals=assessment.proposals,
        )

    def keep_review_only(self) -> None:
        if self.state == "APPLIED":
            raise MeldError("An applied meld cannot become review-only.")
        self.state = "KEPT_REVIEW_ONLY"
        self.application = None
        self._validate()

    def record_application(
        self,
        *,
        change_set_digest: str,
        checkpoint_uid: str,
        result_memory_uids: Iterable[str],
        checkpoints: Iterable[MeldCheckpointReceipt] = (),
    ) -> None:
        change_set = self.prepare_changes()
        if change_set.digest != change_set_digest:
            raise MeldError("Applied meld change-set digest does not match.")
        result_uids = tuple(result_memory_uids)
        if result_uids != tuple(
            proposal.memory_uid for proposal in change_set.proposals
        ):
            raise MeldError("Applied meld result identities do not match.")
        self.application = MeldApplication.from_dict(
            {
                "change_set_digest": change_set_digest,
                "checkpoint_uid": checkpoint_uid,
                "result_memory_uids": list(result_uids),
                **(
                    {"checkpoints": [item.to_dict() for item in checkpoints]}
                    if self.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
                    else {}
                ),
            }
        )
        self.state = "APPLIED"
        self._validate()

    def clear_application(
        self,
        *,
        change_set_digest: str,
        checkpoint_uid: str,
        checkpoints: Iterable[MeldCheckpointReceipt] = (),
    ) -> None:
        """Return one exact applied session to its reviewed ready state."""
        if self.state != "APPLIED" or self.application is None:
            raise MeldError("Meld application is not currently applied.")
        checkpoint_receipts = tuple(checkpoints)
        if (
            self.application.change_set_digest != change_set_digest
            or self.application.checkpoint_uid != checkpoint_uid
            or (
                checkpoint_receipts
                and self.application.checkpoints != checkpoint_receipts
            )
        ):
            raise MeldError("Meld application receipt does not match this undo.")
        self.application = None
        self.state = "READY_TO_APPLY"
        self._validate()

    def _validate(self) -> None:
        if self.schema_version not in {
            MELD_LEGACY_SCHEMA_VERSION,
            MELD_RELATION_ANALYSIS_SCHEMA_VERSION,
            MELD_SCHEMA_VERSION,
            MELD_GRANTED_SCHEMA_VERSION,
            MELD_OWNER_AWARE_SCHEMA_VERSION,
            MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION,
            MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION,
            MELD_MEMORY_FOCUS_SCHEMA_VERSION,
            MELD_INLINE_MEMORY_SCHEMA_VERSION,
            MELD_CANDIDATE_SCHEMA_VERSION,
        }:
            raise MeldError("Unsupported meld session schema version.")
        if self.schema_version == MELD_CANDIDATE_SCHEMA_VERSION:
            self._validate_candidate_session()
            return
        if self.candidate_review is not None:
            raise MeldError("A legacy Meld session cannot contain a candidate review.")
        if self.schema_version == MELD_LEGACY_SCHEMA_VERSION:
            if self.relation_analysis_seed is not None:
                raise MeldError(
                    "A legacy meld session cannot contain a relation-analysis seed."
                )
        elif self.mode == "SYMMETRIC" and self.relation_analysis_seed is None:
            raise MeldError("A current meld session requires a relation-analysis seed.")
        if self.schema_version < MELD_GRANTED_SCHEMA_VERSION and (
            self.granted_incoming is not None or self.granted_target is not None
        ):
            raise MeldError("A legacy meld session cannot contain Grant bindings.")
        if len(self.frames) != 2:
            raise MeldError("Context meld requires exactly two source frames.")
        if any(frame.selected_memory_uid is not None for frame in self.frames) and (
            self.mode != "DIRECTIONAL"
            or self.schema_version
            not in {
                MELD_MEMORY_FOCUS_SCHEMA_VERSION,
                MELD_INLINE_MEMORY_SCHEMA_VERSION,
            }
        ):
            raise MeldError(
                "Context-only Meld evidence requires a focused directional session."
            )
        if self.schema_version == MELD_MEMORY_FOCUS_SCHEMA_VERSION and (
            self.mode != "DIRECTIONAL"
            or not any(frame.selected_memory_uid is not None for frame in self.frames)
        ):
            raise MeldError(
                "A focused Meld session must be directional and directly analyzed."
            )
        if self.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION:
            incoming = self.frames[0]
            fingerprints = incoming.contexts or ()
            ephemeral = Context(uid=incoming.context_uid, name=incoming.context_name)
            for memory in incoming.memories:
                ephemeral.add(Memory(uid=memory.uid, content=memory.content))
            if (
                self.mode != "DIRECTIONAL"
                or self.granted_incoming is not None
                or self.granted_target is not None
                or incoming.context_name != INLINE_MELD_CONTEXT_NAME
                or incoming.include_descendants is not False
                or len(incoming.memories) != 1
                or incoming.context_evidence
                or incoming.selected_memory_uid is not None
                or len(fingerprints) != 1
                or fingerprints[0].uid != incoming.context_uid
                or fingerprints[0].name != incoming.context_name
                or incoming.memories[0].owner_context_uid != incoming.context_uid
                or incoming.memories[0].owner_context_name != incoming.context_name
                or (
                    fingerprints
                    and fingerprints[0].digest != context_record_digest(ephemeral)
                )
            ):
                raise MeldError(
                    "An inline-Memory Meld requires one process-local INCOMING "
                    "Memory and one bound BASELINE."
                )
        if len({frame.uid for frame in self.frames}) != len(self.frames):
            raise MeldError("Duplicate meld frame identity.")
        if len({frame.context_uid for frame in self.frames}) != len(self.frames) or len(
            {frame.context_name for frame in self.frames}
        ) != len(self.frames):
            raise MeldError("Duplicate meld source Context.")
        if self.mode == "SYMMETRIC":
            if self.target.context_uid in {
                frame.context_uid for frame in self.frames
            } or self.target.context_name in {
                frame.context_name for frame in self.frames
            }:
                raise MeldError("Symmetric meld target overlaps a source Context.")
            if any(frame.role != "PEER" for frame in self.frames):
                raise MeldError("Symmetric meld requires two PEER frames.")
        else:
            if (
                self.schema_version == MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION
                and self.relation_analysis_seed is None
            ):
                raise MeldError(
                    "A relation-based directional meld requires its ordered seed."
                )
            if (
                self.schema_version < MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION
                and self.relation_analysis_seed is not None
            ):
                raise MeldError(
                    "A legacy directional meld cannot contain a relation-analysis seed."
                )
            incoming, baseline = self.frames
            if incoming.role != "INCOMING" or baseline.role != "BASELINE":
                raise MeldError(
                    "Directional meld requires ordered INCOMING and BASELINE frames."
                )
            if (
                self.target.context_uid != baseline.context_uid
                or self.target.context_name != baseline.context_name
                or self.target.context_digest != baseline.context_digest
            ):
                raise MeldError(
                    "Directional meld target must exactly match its BASELINE frame."
                )
            if self.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION and (
                incoming.contexts is None
                or baseline.contexts is None
                or not all(
                    memory.owner_context_uid is not None
                    for frame in (incoming, baseline)
                    for memory in frame.memories
                )
            ):
                raise MeldError(
                    "Owner-aware directional meld requires complete Context ownership."
                )
            if self.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION:
                incoming_contexts = incoming.contexts or ()
                baseline_contexts = baseline.contexts or ()
                if {context.uid for context in incoming_contexts} & {
                    context.uid for context in baseline_contexts
                } or {context.name for context in incoming_contexts} & {
                    context.name for context in baseline_contexts
                }:
                    raise MeldError(
                        "Directional INCOMING and BASELINE scopes must not overlap."
                    )
            if (
                self.target.context_uid == incoming.context_uid
                or self.target.context_name == incoming.context_name
            ):
                raise MeldError(
                    "Directional meld target overlaps its INCOMING Context."
                )
            for binding, frame, label in (
                (self.granted_incoming, incoming, "INCOMING"),
                (self.granted_target, baseline, "BASELINE"),
            ):
                if binding is not None and binding.access_name != frame.context_name:
                    raise MeldError(
                        f"Directional {label} Grant binding does not match its frame."
                    )

        if self.relation_analysis_seed is not None:
            analysis = self.relation_analysis_seed.analysis
            if analysis.ruleset_version != MEMORY_RELATION_RULESET_VERSION:
                raise MeldError(
                    "Meld relation-analysis seed uses an unsupported ruleset."
                )
            if self.mode == "SYMMETRIC":
                expected_frames = _relation_analysis_meld_frames(analysis)
                if tuple(frame.to_dict() for frame in self.frames) != tuple(
                    frame.to_dict() for frame in expected_frames
                ):
                    raise MeldError(
                        "Meld source frames do not match their relation-analysis seed."
                    )
            else:
                directional_relation_basis_assessment(
                    analysis,
                    (self.frames[0], self.frames[1]),
                )

        known_turn_uids: list[str] = []
        seen_turn_uids: set[str] = set()
        seen_pending = False
        for sequence, turn in enumerate(self.turns):
            if turn.sequence != sequence:
                raise MeldError("Meld turn sequence is not contiguous.")
            if turn.uid in seen_turn_uids:
                raise MeldError("Duplicate meld turn uid.")
            validate_meld_turn_lineage(
                sequence=sequence,
                revision=turn.revision,
                revises_turn_uids=turn.revises_turn_uids,
                known_turn_uids=known_turn_uids,
            )
            if sequence == 0:
                if turn.comment or turn.scope != "ALL" or turn.issue_uids:
                    raise MeldError(
                        "Initial meld analysis must cover ALL without a "
                        "synthetic user comment."
                    )
            elif not turn.comment.strip():
                raise MeldError("A user meld turn requires a comment.")
            if turn.assessment is None:
                seen_pending = True
                if sequence != len(self.turns) - 1:
                    raise MeldError("Only the latest meld turn may await assessment.")
            elif seen_pending:
                raise MeldError("An assessed meld turn follows a pending turn.")
            else:
                self._validate_assessment(turn)
            known_turn_uids.append(turn.uid)
            seen_turn_uids.add(turn.uid)

        if (
            self.mode == "SYMMETRIC"
            and self.relation_analysis_seed is not None
            and self.turns
            and self.turns[0].assessment is not None
        ):
            imported = _relation_analysis_meld_assessment(
                self.relation_analysis_seed.analysis,
                include_materialization_review=(
                    self.schema_version >= MELD_SCHEMA_VERSION
                ),
            )
            accepted_turn_zero = {meld_canonical_digest(imported.to_dict())}
            if self.schema_version >= MELD_SCHEMA_VERSION:
                accepted_turn_zero.add(
                    meld_canonical_digest(
                        _relation_local_preservation_assessment(
                            self,
                            imported,
                            turn_uid=self.turns[0].uid,
                            user_grounded=False,
                        ).to_dict()
                    )
                )
            if (
                meld_canonical_digest(self.turns[0].assessment.to_dict())
                not in accepted_turn_zero
            ):
                raise MeldError(
                    "Meld turn zero does not match its imported relation analysis."
                )

        if not self.turns:
            if self.state != "PENDING_ANALYSIS" or self.application is not None:
                raise MeldError("Invalid empty meld session state.")
            return
        latest = self.current_turn
        assert latest is not None
        assessment = latest.assessment
        if assessment is None:
            if self.state not in {
                "PENDING_ANALYSIS",
                "AWAITING_REPLY",
                "KEPT_REVIEW_ONLY",
            }:
                raise MeldError("Pending meld turn has an invalid state.")
        elif self.state == "PENDING_ANALYSIS":
            raise MeldError("An assessed meld turn cannot remain PENDING_ANALYSIS.")
        elif self.state == "READY_TO_APPLY" and not assessment.ready_to_apply:
            raise MeldError("READY meld state has a non-ready assessment.")
        elif self.state == "AWAITING_REPLY" and assessment.ready_to_apply:
            raise MeldError("Ready meld assessment cannot await a reply.")
        if self.state == "APPLIED":
            if (
                assessment is None
                or not assessment.ready_to_apply
                or self.application is None
            ):
                raise MeldError("Invalid applied meld state.")
            expected = MeldChangeSet.create(
                session_uid=self.uid,
                turn_uid=latest.uid,
                mode=self.mode,
                target=self.target,
                frames=self.frames,
                turns=self.turns,
                proposals=assessment.proposals,
            )
            if (
                self.application.change_set_digest != expected.digest
                or self.application.result_memory_uids
                != tuple(proposal.memory_uid for proposal in expected.proposals)
            ):
                raise MeldError(
                    "Applied meld receipt does not match its exact proposal."
                )
            if self.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION:
                baseline = self.frames[1]
                requested_owners = {
                    (
                        proposal.owner_context_uid,
                        proposal.owner_context_name,
                    )
                    for proposal in expected.proposals
                }
                if not requested_owners:
                    requested_owners.add((baseline.context_uid, baseline.context_name))
                ordered_owners = tuple(
                    (context.uid, context.name)
                    for context in (baseline.contexts or ())
                    if (context.uid, context.name) in requested_owners
                )
                receipt_owners = tuple(
                    (receipt.context_uid, receipt.context_name)
                    for receipt in self.application.checkpoints
                )
                if receipt_owners != ordered_owners:
                    raise MeldError(
                        "Owner-aware meld receipt does not cover its exact targets."
                    )
        elif self.application is not None:
            raise MeldError("Only an applied meld may retain an application.")

    def _validate_candidate_session(self) -> None:
        """Validate the Audit→Resolve→Update session independently of legacy turns."""

        if self.relation_analysis_seed is not None or self.turns:
            raise MeldError(
                "A candidate Meld session cannot contain relation analysis or turns."
            )
        if len(self.frames) != 2 or self.candidate_review is None:
            raise MeldError("A candidate Meld session requires two Sources and a review.")
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
                raise MeldError(
                    "Directional candidate target must match its BASELINE."
                )
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
            "READY_TO_APPLY",
            "KEPT_REVIEW_ONLY",
            "APPLIED",
        }:
            raise MeldError("Candidate Meld has an invalid lifecycle state.")
        if self.state == "APPLIED":
            if self.application is None:
                raise MeldError("Applied candidate Meld requires an application receipt.")
        elif self.application is not None:
            raise MeldError("Only an applied candidate Meld may retain a receipt.")

    def _validate_assessment(self, turn: MeldTurn) -> None:
        assessment = turn.assessment
        assert assessment is not None
        if (
            self.mode == "DIRECTIONAL"
            and self.relation_analysis_seed is not None
            and turn.sequence == 0
        ):
            basis = directional_relation_basis_assessment(
                self.relation_analysis_seed.analysis,
                (self.frames[0], self.frames[1]),
            )
            if tuple(relation.to_dict() for relation in assessment.relations) != tuple(
                relation.to_dict() for relation in basis.relations
            ):
                raise MeldError(
                    "Directional meld turn zero changed its imported relation ledger."
                )
            issue_by_uid = {issue.uid: issue for issue in assessment.issues}
            if any(
                issue.uid not in issue_by_uid
                or issue_by_uid[issue.uid].to_dict() != issue.to_dict()
                for issue in basis.issues
            ):
                raise MeldError(
                    "Directional meld turn zero changed an imported relation issue."
                )
        incoming_frame = self.frames[0] if self.mode == "DIRECTIONAL" else None
        baseline_frame = self.frames[1] if self.mode == "DIRECTIONAL" else None
        baseline_memory_by_uid = (
            {memory.uid: memory for memory in baseline_frame.memories}
            if baseline_frame is not None
            else {}
        )
        source_memory_uids = {
            memory.uid for frame in self.frames for memory in frame.memories
        }
        memory_keys = {
            (frame.uid, memory.uid)
            for frame in self.frames
            for memory in frame.memories
        }
        relation_member_keys: list[tuple[str, str]] = []
        relation_members_by_uid: dict[str, set[tuple[str, str]]] = {}
        relation_by_uid = {relation.uid: relation for relation in assessment.relations}
        for relation in assessment.relations:
            members = {
                (member.frame_uid, member.memory_uid) for member in relation.members
            }
            if not members <= memory_keys:
                raise MeldError("Meld relation references an unknown source Memory.")
            member_frame_uids = {member.frame_uid for member in relation.members}
            if relation.kind == "DISTINCT" and len(member_frame_uids) != 1:
                raise MeldError(
                    "A DISTINCT meld relation must belong to one source frame."
                )
            if relation.kind != "DISTINCT" and len(member_frame_uids) < 2:
                raise MeldError(
                    "A cross-source meld relation requires both source frames."
                )
            relation_member_keys.extend(members)
            relation_members_by_uid[relation.uid] = members
        # One primary group per source prevents a hidden Cartesian pair list
        # while still allowing one-to-many and many-to-one relations.
        if set(relation_member_keys) != memory_keys or len(relation_member_keys) != len(
            memory_keys
        ):
            raise MeldError(
                "Every source Memory must appear in exactly one primary meld relation."
            )
        required_relation_uids = {
            relation_uid
            for issue in assessment.issues
            if issue.priority == "REQUIRED"
            for relation_uid in issue.relation_uids
        }
        unresolved_relation_uids = {
            relation.uid
            for relation in assessment.relations
            if relation.status == "UNRESOLVED"
        }
        if not unresolved_relation_uids <= required_relation_uids:
            raise MeldError(
                "Every unresolved meld relation requires a visible REQUIRED issue."
            )
        known_turn_uids = {
            prior.uid for prior in self.turns if prior.sequence <= turn.sequence
        }
        actual_user_turn_uids = {
            prior.uid for prior in self.turns if 0 < prior.sequence <= turn.sequence
        }
        proposed_source_keys: set[tuple[str, str]] = set()
        proposed_relation_uids: set[str] = set()
        proposals_by_relation: dict[str, list[MeldProposal]] = defaultdict(list)
        for proposal in assessment.proposals:
            source_keys = {
                (member.frame_uid, member.memory_uid)
                for member in proposal.source_members
            }
            if not source_keys <= memory_keys:
                raise MeldError("Meld proposal cites an unknown source Memory.")
            linked_keys = {
                key
                for relation_uid in proposal.relation_uids
                for key in relation_members_by_uid[relation_uid]
            }
            if source_keys and not source_keys <= linked_keys:
                raise MeldError("Meld proposal source is outside its linked relation.")
            if not set(proposal.grounded_by_turn_uids) <= known_turn_uids:
                raise MeldError("Meld proposal cites an unknown or future user turn.")
            if proposal.disposition == "USER_ADD" and (
                proposal.source_members
                or not (set(proposal.grounded_by_turn_uids) & actual_user_turn_uids)
            ):
                raise MeldError(
                    "A user-added meld proposal must cite a user turn and "
                    "must not claim PEER source evidence."
                )
            if proposal.disposition != "USER_ADD" and not proposal.source_members:
                raise MeldError(
                    "A source-derived meld proposal must cite source Memory evidence."
                )
            if proposal.disposition != "USER_ADD":
                proposed_source_keys.update(source_keys)
                proposed_relation_uids.update(proposal.relation_uids)
                for relation_uid in proposal.relation_uids:
                    proposals_by_relation[relation_uid].append(proposal)
            if self.mode == "SYMMETRIC":
                if proposal.operation != "ADD":
                    raise MeldError(
                        "Symmetric Context meld may only ADD to its empty target."
                    )
                if proposal.owner_context_uid is not None:
                    raise MeldError(
                        "A symmetric meld proposal cannot name a source owner."
                    )
                continue

            assert incoming_frame is not None and baseline_frame is not None
            baseline_context_identities = {
                (context.uid, context.name)
                for context in (baseline_frame.contexts or ())
            }
            if (
                self.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
                and (
                    proposal.owner_context_uid,
                    proposal.owner_context_name,
                )
                not in baseline_context_identities
            ):
                raise MeldError(
                    "A directional meld proposal owner is outside the BASELINE scope."
                )
            incoming_evidence = any(
                frame_uid == incoming_frame.uid for frame_uid, _ in source_keys
            )
            if (
                baseline_frame.selected_memory_uid is not None
                and proposal.operation != "EDIT"
            ):
                raise MeldError(
                    "A Memory-focused BASELINE may edit only its selected Memory."
                )
            if proposal.disposition == "USER_ADD":
                if proposal.operation != "ADD":
                    raise MeldError(
                        "A user-added directional meld result must use ADD."
                    )
            elif not incoming_evidence:
                raise MeldError(
                    "A directional meld change must cite INCOMING Memory evidence."
                )
            if proposal.operation == "EDIT":
                target_memory = baseline_memory_by_uid.get(proposal.memory_uid)
                if (
                    target_memory is None
                    or (
                        baseline_frame.uid,
                        proposal.memory_uid,
                    )
                    not in source_keys
                ):
                    raise MeldError(
                        "A directional EDIT must target and cite one BASELINE Memory."
                    )
                if proposal.content == target_memory.content:
                    raise MeldError(
                        "A directional EDIT must materially change its BASELINE Memory."
                    )
                if self.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION and (
                    proposal.owner_context_uid != target_memory.owner_context_uid
                    or proposal.owner_context_name != target_memory.owner_context_name
                ):
                    raise MeldError(
                        "A directional EDIT owner must match its BASELINE Memory."
                    )
            elif proposal.memory_uid in source_memory_uids:
                raise MeldError("A directional ADD must use a fresh Memory uid.")
        if (
            self.schema_version >= MELD_DIRECTIONAL_PRESERVATION_SCHEMA_VERSION
            and self.mode == "DIRECTIONAL"
            and assessment.ready_to_apply
        ):
            assert incoming_frame is not None
            incoming_memory_by_key = {
                (incoming_frame.uid, memory.uid): memory
                for memory in incoming_frame.memories
            }
            if any(
                proposal.disposition != "USER_ADD" and len(proposal.relation_uids) != 1
                for proposal in assessment.proposals
            ):
                raise MeldRepairableAssessmentError(
                    "A preservation-first directional result must belong to "
                    "exactly one primary relation."
                )
            for relation_uid, relation in relation_by_uid.items():
                relation_proposals = proposals_by_relation.get(relation_uid, [])
                relation_incoming = {
                    key
                    for key in relation_members_by_uid[relation_uid]
                    if key[0] == incoming_frame.uid
                }
                if relation.kind == "EQUIVALENT":
                    if relation_proposals:
                        raise MeldRepairableAssessmentError(
                            "An EQUIVALENT directional relation is already "
                            "represented by the BASELINE and must not create a change."
                        )
                    continue
                if relation.kind not in {"DISTINCT", "COMPATIBLE", "SCOPED"}:
                    continue

                incoming_occurrences: Counter[tuple[str, str]] = Counter()
                for proposal in relation_proposals:
                    proposal_incoming = {
                        (member.frame_uid, member.memory_uid)
                        for member in proposal.source_members
                        if member.frame_uid == incoming_frame.uid
                    }
                    incoming_occurrences.update(proposal_incoming)
                    user_grounded = bool(
                        set(proposal.grounded_by_turn_uids) & actual_user_turn_uids
                    )
                    if len(proposal_incoming) > 1:
                        if (
                            relation.kind not in {"COMPATIBLE", "SCOPED"}
                            or proposal.disposition != "SYNTHESIZE"
                            or not user_grounded
                        ):
                            raise MeldRepairableAssessmentError(
                                "Combining directional INCOMING Memories requires "
                                "an explicit user-grounded relation-local SYNTHESIZE "
                                "result."
                            )
                        continue
                    if len(proposal_incoming) != 1:
                        raise MeldRepairableAssessmentError(
                            "A directional source-derived change must represent "
                            "INCOMING Memory evidence."
                        )
                    incoming_key = next(iter(proposal_incoming))
                    incoming_memory = incoming_memory_by_key[incoming_key]
                    # Relation classification remains host-owned. Directional
                    # authority may still materialize one already-resolved
                    # relation as an exact BASELINE edit; that is a target
                    # policy, not permission to regroup or relabel evidence.
                    initial_directional_edit = (
                        turn.sequence == 0
                        and self.relation_analysis_seed is not None
                        and proposal.operation == "EDIT"
                        and proposal.disposition == "SYNTHESIZE"
                    )
                    if (
                        not (
                            proposal.operation == "ADD"
                            and proposal.disposition == "PRESERVE"
                            and proposal.content == incoming_memory.content
                        )
                        and not initial_directional_edit
                        and not (proposal.disposition == "SYNTHESIZE" and user_grounded)
                    ):
                        raise MeldRepairableAssessmentError(
                            "An uncombined directional INCOMING Memory must be "
                            "added once with its exact content, materialized as "
                            "one relation-bound initial BASELINE edit, or grounded "
                            "by an explicit user turn."
                        )
                repeated_initial_edit_keys: set[tuple[str, str]] = set()
                if turn.sequence == 0 and self.relation_analysis_seed is not None:
                    for incoming_key, count in incoming_occurrences.items():
                        matching = [
                            proposal
                            for proposal in relation_proposals
                            if incoming_key
                            in {
                                (member.frame_uid, member.memory_uid)
                                for member in proposal.source_members
                                if member.frame_uid == incoming_frame.uid
                            }
                        ]
                        if (
                            count > 1
                            and len({proposal.memory_uid for proposal in matching})
                            == count
                            and all(
                                proposal.operation == "EDIT"
                                and proposal.disposition == "SYNTHESIZE"
                                for proposal in matching
                            )
                        ):
                            # One reviewed correction may route to several
                            # exact BASELINE owners. Repetition is target
                            # placement, not duplicate relation coverage.
                            repeated_initial_edit_keys.add(incoming_key)
                if set(incoming_occurrences) != relation_incoming or any(
                    count != 1 and incoming_key not in repeated_initial_edit_keys
                    for incoming_key, count in incoming_occurrences.items()
                ):
                    raise MeldRepairableAssessmentError(
                        "A ready directional DISTINCT, COMPATIBLE, or SCOPED "
                        "relation must materialize every INCOMING Memory exactly once."
                    )
        if (
            self.schema_version >= MELD_SCHEMA_VERSION
            and self.mode == "SYMMETRIC"
            and assessment.ready_to_apply
        ):
            if any(
                proposal.disposition != "USER_ADD" and len(proposal.relation_uids) != 1
                for proposal in assessment.proposals
            ):
                raise MeldError(
                    "A preservation-first symmetric result must belong to "
                    "exactly one primary relation."
                )
            for relation_uid, relation in relation_by_uid.items():
                relation_proposals = proposals_by_relation.get(relation_uid, [])
                relation_members = relation_members_by_uid[relation_uid]
                if not relation_proposals:
                    raise MeldError(
                        "Every resolved symmetric relation requires a material result."
                    )
                if relation.kind == "EQUIVALENT":
                    if (
                        len(relation_proposals) != 1
                        or relation_proposals[0].disposition != "COALESCE"
                        or {
                            (member.frame_uid, member.memory_uid)
                            for member in relation_proposals[0].source_members
                        }
                        != relation_members
                    ):
                        raise MeldError(
                            "An EQUIVALENT relation must produce exactly one "
                            "complete COALESCE result."
                        )
                    continue
                for proposal in relation_proposals:
                    proposal_sources = {
                        (member.frame_uid, member.memory_uid)
                        for member in proposal.source_members
                    }
                    if len(proposal_sources) == 1:
                        if proposal.disposition != "PRESERVE":
                            raise MeldError(
                                "A single-source symmetric result must preserve "
                                "one independently useful source Memory."
                            )
                    elif relation.kind in {"COMPATIBLE", "SCOPED"}:
                        if proposal.disposition != "SYNTHESIZE" or not (
                            set(proposal.grounded_by_turn_uids) & actual_user_turn_uids
                        ):
                            raise MeldError(
                                "Combining COMPATIBLE or SCOPED Memories "
                                "requires an explicit user-grounded SYNTHESIZE "
                                "result."
                            )
                if relation.kind == "DISTINCT" and (
                    len(relation_proposals) != len(relation_members)
                    or any(
                        len(proposal.source_members) != 1
                        for proposal in relation_proposals
                    )
                ):
                    raise MeldError(
                        "A DISTINCT relation must preserve every source Memory "
                        "as its own result."
                    )
        if (
            self.mode == "SYMMETRIC"
            and assessment.ready_to_apply
            and (
                proposed_source_keys != memory_keys
                or proposed_relation_uids
                != {relation.uid for relation in assessment.relations}
            )
        ):
            raise MeldError(
                "A ready symmetric meld must represent every source Memory "
                "and primary relation in its exact result proposal."
            )


def inline_meld_context(session: MeldSession) -> Context:
    """Reconstruct the immutable process-local INCOMING Context view."""

    if (
        not isinstance(session, MeldSession)
        or session.schema_version != MELD_INLINE_MEMORY_SCHEMA_VERSION
    ):
        raise MeldError("Expected an inline-Memory Meld session.")
    frame = session.frames[0]
    context = Context(uid=frame.context_uid, name=frame.context_name)
    for memory in frame.memories:
        context.add(Memory(uid=memory.uid, content=memory.content))
    fingerprints = frame.contexts or ()
    if len(fingerprints) != 1 or fingerprints[0].digest != context_record_digest(
        context
    ):
        raise MeldError("Inline Meld Memory evidence does not match its frame.")
    return context


@dataclass(frozen=True)
class MeldAccounting:
    """Host-computed source-to-result accounting for one current assessment."""

    source_memories: int
    represented_sources: int
    primary_relations: int
    represented_relations: int
    final_memories: int
    preserve_results: int
    coalesce_results: int
    synthesize_results: int
    user_add_results: int
    required_issues: int
    helpful_issues: int
    cross_relation_results: int


def meld_accounting(session: MeldSession) -> MeldAccounting:
    """Compute exact accounting without trusting provider-authored counts."""
    if not isinstance(session, MeldSession):
        raise TypeError("Expected a MeldSession.")
    assessment = session.current_assessment
    source_count = sum(len(frame.memories) for frame in session.frames)
    if assessment is None:
        return MeldAccounting(
            source_memories=source_count,
            represented_sources=0,
            primary_relations=0,
            represented_relations=0,
            final_memories=0,
            preserve_results=0,
            coalesce_results=0,
            synthesize_results=0,
            user_add_results=0,
            required_issues=0,
            helpful_issues=0,
            cross_relation_results=0,
        )
    represented_sources = {
        (member.frame_uid, member.memory_uid)
        for proposal in assessment.proposals
        for member in proposal.source_members
    }
    represented_relations = {
        relation_uid
        for proposal in assessment.proposals
        for relation_uid in proposal.relation_uids
    }
    dispositions = Counter(proposal.disposition for proposal in assessment.proposals)
    priorities = Counter(issue.priority for issue in assessment.issues)
    return MeldAccounting(
        source_memories=source_count,
        represented_sources=len(represented_sources),
        primary_relations=len(assessment.relations),
        represented_relations=len(represented_relations),
        final_memories=len(assessment.proposals),
        preserve_results=dispositions["PRESERVE"],
        coalesce_results=dispositions["COALESCE"],
        synthesize_results=dispositions["SYNTHESIZE"],
        user_add_results=dispositions["USER_ADD"],
        required_issues=priorities["REQUIRED"],
        helpful_issues=priorities["HELPFUL"],
        cross_relation_results=sum(
            proposal.disposition != "USER_ADD" and len(proposal.relation_uids) != 1
            for proposal in assessment.proposals
        ),
    )


def materialize_preservation_assessment(session: MeldSession) -> MeldAssessment:
    """Build an exact provider-free preserve-all result for symmetric v3 Meld."""
    if not isinstance(session, MeldSession):
        raise TypeError("Expected a MeldSession.")
    if session.mode != "SYMMETRIC" or session.schema_version < MELD_SCHEMA_VERSION:
        raise MeldError(
            "Provider-free preservation requires a symmetric schema v3 meld."
        )
    turn = session.current_turn
    if turn is None or turn.assessment is not None or len(session.turns) < 2:
        raise MeldError(
            "Provider-free preservation requires one pending user meld turn."
        )
    prior = session.turns[-2].assessment
    if prior is None:
        raise MeldError("Provider-free preservation requires a prior assessment.")
    return _relation_local_preservation_assessment(
        session,
        prior,
        turn_uid=turn.uid,
        user_grounded=True,
    )
