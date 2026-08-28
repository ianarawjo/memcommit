"""Exact Atomize Grounding change sets and application receipts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from .bindings import (
    AtomizeGroundingBindings,
    AtomizeGroundingError,
    _canonical_uuid,
    _digest,
    _exact_dict,
    _identifiers,
    _list,
    atomize_grounding_canonical_digest,
)
from .review import AtomizeGroundingProposal


@dataclass(frozen=True)
class AtomizeGroundingApplication:
    """Receipt recorded only after a command transaction has succeeded."""

    change_set_digest: str
    checkpoint_uid: str
    proposal_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "change_set_digest": self.change_set_digest,
            "checkpoint_uid": self.checkpoint_uid,
            "proposal_uids": list(self.proposal_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingApplication":
        data = _exact_dict(
            value,
            {"change_set_digest", "checkpoint_uid", "proposal_uids"},
            "atomize grounding application",
        )
        return cls(
            change_set_digest=_digest(
                data["change_set_digest"],
                "atomize grounding change-set digest",
            ),
            checkpoint_uid=_canonical_uuid(
                data["checkpoint_uid"],
                "atomize grounding checkpoint uid",
            ),
            proposal_uids=_identifiers(
                data["proposal_uids"],
                "atomize grounding applied proposal uid",
            ),
        )


@dataclass(frozen=True)
class AtomizeGroundingChangeSet:
    """A pure application plan; creating it does not mutate any Memory."""

    session_uid: str
    turn_uid: str
    context_uid: str
    context_digest: str
    analysis_digest: str
    workbench_digest: str
    response_digest: str
    proposals: tuple[AtomizeGroundingProposal, ...]
    digest: str

    def _payload(self) -> dict[str, object]:
        return {
            "session_uid": self.session_uid,
            "turn_uid": self.turn_uid,
            "context_uid": self.context_uid,
            "context_digest": self.context_digest,
            "analysis_digest": self.analysis_digest,
            "workbench_digest": self.workbench_digest,
            "response_digest": self.response_digest,
            "proposals": [proposal.to_dict() for proposal in self.proposals],
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        session_uid: str,
        turn_uid: str,
        bindings: AtomizeGroundingBindings,
        proposals: Iterable[AtomizeGroundingProposal],
    ) -> "AtomizeGroundingChangeSet":
        parsed = tuple(proposals)
        if not parsed or any(
            not isinstance(proposal, AtomizeGroundingProposal)
            for proposal in parsed
        ):
            raise AtomizeGroundingError(
                "Atomize grounding change sets require accepted proposals."
            )
        draft = cls(
            session_uid=_canonical_uuid(
                session_uid,
                "atomize grounding change-set session uid",
            ),
            turn_uid=_canonical_uuid(
                turn_uid,
                "atomize grounding change-set turn uid",
            ),
            context_uid=bindings.context_uid,
            context_digest=bindings.context_digest,
            analysis_digest=bindings.analysis_digest,
            workbench_digest=bindings.workbench_digest,
            response_digest=bindings.response_digest,
            proposals=parsed,
            digest="",
        )
        return replace(
            draft,
            digest=atomize_grounding_canonical_digest(draft._payload()),
        )

    @classmethod
    def from_dict(cls, value: object) -> "AtomizeGroundingChangeSet":
        data = _exact_dict(
            value,
            {
                "session_uid",
                "turn_uid",
                "context_uid",
                "context_digest",
                "analysis_digest",
                "workbench_digest",
                "response_digest",
                "proposals",
                "digest",
            },
            "atomize grounding change set",
        )
        proposals = tuple(
            AtomizeGroundingProposal.from_dict(item)
            for item in _list(
                data["proposals"],
                "atomize grounding change-set proposals",
            )
        )
        if not proposals or len({item.uid for item in proposals}) != len(
            proposals
        ):
            raise AtomizeGroundingError(
                "Invalid atomize grounding change-set proposals."
            )
        result = cls(
            session_uid=_canonical_uuid(
                data["session_uid"],
                "atomize grounding change-set session uid",
            ),
            turn_uid=_canonical_uuid(
                data["turn_uid"],
                "atomize grounding change-set turn uid",
            ),
            context_uid=_canonical_uuid(
                data["context_uid"],
                "atomize grounding change-set Context uid",
            ),
            context_digest=_digest(
                data["context_digest"],
                "atomize grounding change-set Context digest",
            ),
            analysis_digest=_digest(
                data["analysis_digest"],
                "atomize grounding change-set analysis digest",
            ),
            workbench_digest=_digest(
                data["workbench_digest"],
                "atomize grounding change-set workbench digest",
            ),
            response_digest=_digest(
                data["response_digest"],
                "atomize grounding change-set response digest",
            ),
            proposals=proposals,
            digest=_digest(
                data["digest"],
                "atomize grounding change-set digest",
            ),
        )
        if result.digest != atomize_grounding_canonical_digest(
            result._payload()
        ):
            raise AtomizeGroundingError(
                "Atomize grounding change-set digest does not match."
            )
        return result
