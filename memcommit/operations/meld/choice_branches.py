"""Durable provider-free choices staged against one Meld assessment."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.operations.meld.model import (
    MELD_TEXT_LIMIT,
    MeldAssessment,
    MeldSession,
    meld_canonical_digest,
)


MELD_CHOICE_BRANCH_SET_KIND = "MELD_CHOICE_BRANCH_SET"
MELD_CHOICE_BRANCH_SET_SCHEMA_VERSION = 1


class MeldChoiceBranchError(ValueError):
    """A saved local Meld choice is malformed or stale."""


def _assessment_digest(assessment: MeldAssessment) -> str:
    return meld_canonical_digest(assessment.to_dict())


@dataclass(frozen=True)
class MeldChoiceBranch:
    """One reviewed option or custom response, without a semantic outcome."""

    issue_uid: str
    option_uid: str | None
    explanation: str

    @classmethod
    def from_dict(cls, value: object) -> "MeldChoiceBranch":
        if not isinstance(value, dict) or set(value) != {
            "issue_uid",
            "option_uid",
            "explanation",
        }:
            raise MeldChoiceBranchError("Saved Meld choice branch is invalid.")
        issue_uid = value.get("issue_uid")
        option_uid = value.get("option_uid")
        explanation = value.get("explanation")
        if (
            not isinstance(issue_uid, str)
            or not issue_uid
            or (option_uid is not None and (not isinstance(option_uid, str) or not option_uid))
            or not isinstance(explanation, str)
            or len(explanation) > MELD_TEXT_LIMIT
            or (option_uid is None and not explanation.strip())
        ):
            raise MeldChoiceBranchError("Saved Meld choice branch is invalid.")
        return cls(
            issue_uid=issue_uid,
            option_uid=option_uid,
            explanation=explanation,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "issue_uid": self.issue_uid,
            "option_uid": self.option_uid,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class MeldChoiceBranchSet:
    """The sparse selected branches for one exact visible assessment.

    The record intentionally contains no provider completion, proposal, or
    synthetic delta.  Its only authority is to restore what the person staged
    before one later whole-ledger reconciliation.
    """

    session_uid: str
    target_context_uid: str
    assessment_digest: str
    branches: tuple[MeldChoiceBranch, ...] = ()

    @classmethod
    def empty(cls, session: MeldSession) -> "MeldChoiceBranchSet":
        assessment = session.current_assessment
        if assessment is None:
            raise MeldChoiceBranchError(
                "Meld choices require a completed current assessment."
            )
        return cls(
            session_uid=session.uid,
            target_context_uid=session.target.context_uid,
            assessment_digest=_assessment_digest(assessment),
        )

    @classmethod
    def from_dict(cls, value: object) -> "MeldChoiceBranchSet":
        if not isinstance(value, dict) or set(value) != {
            "kind",
            "schema_version",
            "session_uid",
            "target_context_uid",
            "assessment_digest",
            "branches",
        }:
            raise MeldChoiceBranchError("Saved Meld choice branches are invalid.")
        raw_branches = value.get("branches")
        if (
            value.get("kind") != MELD_CHOICE_BRANCH_SET_KIND
            or value.get("schema_version")
            != MELD_CHOICE_BRANCH_SET_SCHEMA_VERSION
            or not isinstance(value.get("session_uid"), str)
            or not value.get("session_uid")
            or not isinstance(value.get("target_context_uid"), str)
            or not value.get("target_context_uid")
            or not isinstance(value.get("assessment_digest"), str)
            or len(value.get("assessment_digest")) != 64
            or not isinstance(raw_branches, list)
        ):
            raise MeldChoiceBranchError("Saved Meld choice branches are invalid.")
        branches = tuple(MeldChoiceBranch.from_dict(item) for item in raw_branches)
        if len({branch.issue_uid for branch in branches}) != len(branches):
            raise MeldChoiceBranchError("Saved Meld choice branches are invalid.")
        return cls(
            session_uid=value["session_uid"],
            target_context_uid=value["target_context_uid"],
            assessment_digest=value["assessment_digest"],
            branches=branches,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": MELD_CHOICE_BRANCH_SET_KIND,
            "schema_version": MELD_CHOICE_BRANCH_SET_SCHEMA_VERSION,
            "session_uid": self.session_uid,
            "target_context_uid": self.target_context_uid,
            "assessment_digest": self.assessment_digest,
            "branches": [branch.to_dict() for branch in self.branches],
        }

    def matches(self, session: MeldSession) -> bool:
        assessment = session.current_assessment
        return bool(
            assessment is not None
            and self.session_uid == session.uid
            and self.target_context_uid == session.target.context_uid
            and self.assessment_digest == _assessment_digest(assessment)
        )

    def validated_for(self, session: MeldSession) -> "MeldChoiceBranchSet":
        if not self.matches(session):
            raise MeldChoiceBranchError(
                "Saved Meld choices belong to a different assessment."
            )
        assert session.current_assessment is not None
        issues = {issue.uid: issue for issue in session.current_assessment.issues}
        for branch in self.branches:
            issue = issues.get(branch.issue_uid)
            if issue is None or (
                branch.option_uid is not None
                and branch.option_uid not in {option.uid for option in issue.options}
            ):
                raise MeldChoiceBranchError(
                    "Saved Meld choice no longer exists in this assessment."
                )
        return self

    def response_for(self, issue_uid: str) -> tuple[str | None, str]:
        for branch in self.branches:
            if branch.issue_uid == issue_uid:
                return branch.option_uid, branch.explanation
        return None, ""

    def with_response(
        self,
        session: MeldSession,
        *,
        issue_uid: str,
        option_uid: str | None,
        explanation: str,
    ) -> "MeldChoiceBranchSet":
        self.validated_for(session)
        assert session.current_assessment is not None
        issue = next(
            (item for item in session.current_assessment.issues if item.uid == issue_uid),
            None,
        )
        if issue is None or (
            option_uid is not None
            and option_uid not in {option.uid for option in issue.options}
        ):
            raise MeldChoiceBranchError("Meld returned an unknown local choice.")
        try:
            branch = MeldChoiceBranch.from_dict(
                {
                    "issue_uid": issue_uid,
                    "option_uid": option_uid,
                    "explanation": explanation,
                }
            )
        except MeldChoiceBranchError:
            if option_uid is None and not explanation.strip():
                branch = None
            else:
                raise
        updated = [item for item in self.branches if item.issue_uid != issue_uid]
        if branch is not None:
            updated.append(branch)
        result = MeldChoiceBranchSet(
            session_uid=self.session_uid,
            target_context_uid=self.target_context_uid,
            assessment_digest=self.assessment_digest,
            branches=tuple(sorted(updated, key=lambda item: item.issue_uid)),
        )
        return MeldChoiceBranchSet.from_dict(result.to_dict()).validated_for(session)
