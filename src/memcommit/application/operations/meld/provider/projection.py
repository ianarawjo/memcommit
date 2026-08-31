"""Stable aliases and provider-visible Meld payload projection."""

from __future__ import annotations

from dataclasses import dataclass, replace

from memcommit.application.operations.meld.model import (
    MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION,
    MeldAssessment,
    MeldMember,
    MeldProposal,
    MeldSession,
    directional_relation_basis_assessment,
)

from .contract import MeldProviderError


@dataclass(frozen=True)
class _ProviderView:
    memory_by_id: dict[str, MeldMember]
    memory_id_by_key: dict[tuple[str, str], str]
    memory_owner_by_id: dict[str, tuple[str, str] | None]
    target_context_by_id: dict[str, tuple[str, str]]
    target_context_id_by_identity: dict[tuple[str, str], str]
    frame_ids: tuple[str, str]
    turn_by_id: dict[str, str]
    turn_id_by_uid: dict[str, str]
    prior_relation_by_id: dict[str, str]
    prior_relation_records: dict[str, dict[str, object]]
    prior_issue_by_id: dict[str, str]
    prior_proposal_by_id: dict[str, str]
    payload: dict[str, object]

def _split_relation_payloads(
    records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    paired: list[dict[str, object]] = []
    distinct: list[dict[str, object]] = []
    for record in records:
        if record["kind"] != "DISTINCT":
            paired.append(record)
            continue
        left_ids = record["left_memory_ids"]
        right_ids = record["right_memory_ids"]
        if not isinstance(left_ids, list) or not isinstance(right_ids, list):
            raise MeldProviderError("Invalid prior DISTINCT relation.")
        side = "LEFT" if left_ids else "RIGHT"
        memory_ids = left_ids if left_ids else right_ids
        distinct.append(
            {
                "relation_key": record["relation_key"],
                "side": side,
                "memory_ids": memory_ids,
                "kind": "DISTINCT",
                "status": record["status"],
                "summary": record["summary"],
                "reason": record["reason"],
            }
        )
    return paired, distinct


def _assessment_provider_payload(
    session: MeldSession,
    assessment: MeldAssessment,
    view: _ProviderView,
) -> tuple[
    dict[str, object],
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    """Project one decoded assessment back into its provider-visible aliases."""
    relation_id_by_uid = {
        relation.uid: f"r{index:06d}"
        for index, relation in enumerate(assessment.relations, start=1)
    }
    issue_id_by_uid = {
        issue.uid: f"i{index:06d}"
        for index, issue in enumerate(assessment.issues, start=1)
    }
    proposal_id_by_uid = {
        proposal.uid: f"p{index:06d}"
        for index, proposal in enumerate(assessment.proposals, start=1)
    }
    relation_records = [
        {
            "relation_key": relation_id_by_uid[relation.uid],
            "left_memory_ids": [
                view.memory_id_by_key[(member.frame_uid, member.memory_uid)]
                for member in relation.members
                if member.frame_uid == session.frames[0].uid
            ],
            "right_memory_ids": [
                view.memory_id_by_key[(member.frame_uid, member.memory_uid)]
                for member in relation.members
                if member.frame_uid == session.frames[1].uid
            ],
            "kind": relation.kind,
            "status": relation.status,
            "summary": relation.summary,
            "reason": relation.reason,
        }
        for relation in assessment.relations
    ]
    paired_relations, distinct_relations = _split_relation_payloads(
        relation_records
    )
    results: list[dict[str, object]] = []
    for proposal in assessment.proposals:
        result: dict[str, object] = {
            "result_key": proposal_id_by_uid[proposal.uid],
            "disposition": proposal.disposition,
            "content": proposal.content,
            "reason": proposal.reason,
            "relation_keys": [
                relation_id_by_uid[uid] for uid in proposal.relation_uids
            ],
            "source_memory_ids": [
                view.memory_id_by_key[(member.frame_uid, member.memory_uid)]
                for member in proposal.source_members
            ],
            "grounded_turn_ids": [
                view.turn_id_by_uid[uid]
                for uid in proposal.grounded_by_turn_uids
            ],
        }
        if session.mode == "DIRECTIONAL":
            baseline = session.frames[1]
            result["operation"] = proposal.operation
            result["target_memory_ids"] = (
                [view.memory_id_by_key[(baseline.uid, proposal.memory_uid)]]
                if proposal.operation == "EDIT"
                else []
            )
            if len(view.target_context_by_id) > 1:
                owner_identity = (
                    proposal.owner_context_uid,
                    proposal.owner_context_name,
                )
                result["target_context_id"] = (
                    view.target_context_id_by_identity[owner_identity]
                )
        results.append(result)

    return (
        {
            "overview": assessment.overview,
            "paired_relations": paired_relations,
            "distinct_relations": distinct_relations,
            "issues": [
                {
                    "issue_key": issue_id_by_uid[issue.uid],
                    "relation_keys": [
                        relation_id_by_uid[uid] for uid in issue.relation_uids
                    ],
                    "priority": issue.priority,
                    "title": issue.title,
                    "question": issue.question,
                    "why_it_matters": issue.why_it_matters,
                    "options": [
                        {"label": option.label, "text": option.text}
                        for option in issue.options
                    ],
                }
                for issue in assessment.issues
            ],
            "results": results,
            "ready_to_apply": assessment.ready_to_apply,
        },
        {alias: uid for uid, alias in relation_id_by_uid.items()},
        {alias: uid for uid, alias in issue_id_by_uid.items()},
        {alias: uid for uid, alias in proposal_id_by_uid.items()},
    )


def _provider_view(session: MeldSession) -> _ProviderView:
    if session.current_turn is None:
        raise MeldProviderError("No meld turn is awaiting analysis.")
    if session.current_turn.assessment is not None:
        raise MeldProviderError("The current meld turn is already assessed.")
    memory_by_id: dict[str, MeldMember] = {}
    memory_id_by_key: dict[tuple[str, str], str] = {}
    memory_owner_by_id: dict[str, tuple[str, str] | None] = {}
    target_context_by_id: dict[str, tuple[str, str]] = {}
    target_context_id_by_identity: dict[tuple[str, str], str] = {}
    if session.mode == "DIRECTIONAL":
        baseline = session.frames[1]
        target_context_identities = (
            [(context.uid, context.name) for context in baseline.contexts]
            if baseline.contexts
            else [(baseline.context_uid, baseline.context_name)]
        )
        for context_index, identity in enumerate(
            target_context_identities,
            start=1,
        ):
            context_id = f"k{context_index:06d}"
            target_context_by_id[context_id] = identity
            target_context_id_by_identity[identity] = context_id
    frame_ids = (
        ("left", "right") if session.mode == "SYMMETRIC" else ("incoming", "baseline")
    )
    frame_payloads: list[dict[str, object]] = []
    for frame_index, (frame, frame_id) in enumerate(
        zip(session.frames, frame_ids, strict=True),
        start=1,
    ):
        memories: list[dict[str, object]] = []
        for memory_index, memory in enumerate(frame.memories, start=1):
            memory_id = f"m{frame_index}_{memory_index:06d}"
            member = MeldMember(
                frame_uid=frame.uid,
                memory_uid=memory.uid,
            )
            memory_by_id[memory_id] = member
            memory_id_by_key[(frame.uid, memory.uid)] = memory_id
            owner = (
                (memory.owner_context_uid, memory.owner_context_name)
                if memory.owner_context_uid is not None
                and memory.owner_context_name is not None
                else None
            )
            memory_owner_by_id[memory_id] = owner
            memory_payload: dict[str, object] = {
                    "memory_id": memory_id,
                    "position": memory.position,
                    "content": memory.content,
                    "content_sha256": memory.content_digest,
                }
            if owner is not None:
                memory_payload["owner_context_name"] = owner[1]
                if frame.role == "BASELINE":
                    memory_payload["target_context_id"] = (
                        target_context_id_by_identity[owner]
                    )
            memories.append(memory_payload)
        frame_payload: dict[str, object] = {
            "frame_id": frame_id,
            "role": frame.role,
            "context_name": frame.context_name,
            "memories": memories,
        }
        if frame.selected_memory_uid is not None:
            # The provider needs the role-level boundary even when the frozen
            # Context contains no neighboring evidence entries.
            frame_payload["memory_focus"] = True
        if frame.context_evidence:
            frame_payload["context_evidence"] = [
                {
                    "context_id": f"c{frame_index}_{index:06d}",
                    "position": memory.position,
                    "content": memory.content,
                    "content_sha256": memory.content_digest,
                    **(
                        {"owner_context_name": memory.owner_context_name}
                        if memory.owner_context_name is not None
                        else {}
                    ),
                }
                for index, memory in enumerate(
                    frame.context_evidence,
                    start=1,
                )
            ]
        frame_payloads.append(frame_payload)

    turn_by_id: dict[str, str] = {}
    turn_id_by_uid: dict[str, str] = {}
    history: list[dict[str, object]] = []
    for turn_index, turn in enumerate(session.user_turns, start=1):
        turn_id = f"t{turn_index:06d}"
        turn_by_id[turn_id] = turn.uid
        turn_id_by_uid[turn.uid] = turn_id
        if turn.assessment is not None:
            history.append(
                {
                    "turn_id": turn_id,
                    "revision": turn.revision,
                    "scope": turn.scope,
                    "comment": turn.comment,
                    "revises_turn_ids": [
                        turn_id_by_uid[uid]
                        for uid in turn.revises_turn_uids
                        if uid in turn_id_by_uid
                    ],
                }
            )

    prior_relation_by_id: dict[str, str] = {}
    prior_relation_records: dict[str, dict[str, object]] = {}
    prior_issue_by_id: dict[str, str] = {}
    prior_proposal_by_id: dict[str, str] = {}
    previous: dict[str, object] | None = None

    def prior_result_payload(
        proposal: MeldProposal,
        *,
        result_key: str,
        relation_id_by_uid: dict[str, str],
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "result_key": result_key,
            "disposition": proposal.disposition,
            "content": proposal.content,
            "reason": proposal.reason,
            "relation_keys": [
                relation_id_by_uid[uid] for uid in proposal.relation_uids
            ],
            "source_memory_ids": [
                memory_id_by_key[(member.frame_uid, member.memory_uid)]
                for member in proposal.source_members
            ],
            "grounded_turn_ids": [
                turn_id_by_uid[uid] for uid in proposal.grounded_by_turn_uids
            ],
        }
        if session.mode == "DIRECTIONAL":
            baseline = session.frames[1]
            payload["operation"] = proposal.operation
            payload["target_memory_ids"] = (
                [memory_id_by_key[(baseline.uid, proposal.memory_uid)]]
                if proposal.operation == "EDIT"
                else []
            )
            if len(target_context_by_id) > 1:
                owner_identity = (
                    proposal.owner_context_uid,
                    proposal.owner_context_name,
                )
                payload["target_context_id"] = target_context_id_by_identity[
                    owner_identity
                ]
        return payload

    if len(session.turns) > 1:
        prior_assessment = session.turns[-2].assessment
        assert prior_assessment is not None
        relation_id_by_uid: dict[str, str] = {}
        issue_id_by_uid: dict[str, str] = {}
        proposal_id_by_uid: dict[str, str] = {}
        for index, relation in enumerate(
            prior_assessment.relations,
            start=1,
        ):
            alias = f"r{index:06d}"
            prior_relation_by_id[alias] = relation.uid
            relation_id_by_uid[relation.uid] = alias
        for index, issue in enumerate(prior_assessment.issues, start=1):
            alias = f"i{index:06d}"
            prior_issue_by_id[alias] = issue.uid
            issue_id_by_uid[issue.uid] = alias
        for index, proposal in enumerate(
            prior_assessment.proposals,
            start=1,
        ):
            alias = f"p{index:06d}"
            prior_proposal_by_id[alias] = proposal.uid
            proposal_id_by_uid[proposal.uid] = alias
        previous_relations = [
            {
                "relation_key": relation_id_by_uid[relation.uid],
                "left_memory_ids": [
                    memory_id_by_key[(member.frame_uid, member.memory_uid)]
                    for member in relation.members
                    if member.frame_uid == session.frames[0].uid
                ],
                "right_memory_ids": [
                    memory_id_by_key[(member.frame_uid, member.memory_uid)]
                    for member in relation.members
                    if member.frame_uid == session.frames[1].uid
                ],
                "kind": relation.kind,
                "status": relation.status,
                "summary": relation.summary,
                "reason": relation.reason,
            }
            for relation in prior_assessment.relations
        ]
        previous_paired, previous_distinct = _split_relation_payloads(
            previous_relations
        )
        previous = {
            "overview": prior_assessment.overview,
            "paired_relations": previous_paired,
            "distinct_relations": previous_distinct,
            "issues": [
                {
                    "issue_key": issue_id_by_uid[issue.uid],
                    "relation_keys": [
                        relation_id_by_uid[uid] for uid in issue.relation_uids
                    ],
                    "priority": issue.priority,
                    "title": issue.title,
                    "question": issue.question,
                    "why_it_matters": issue.why_it_matters,
                    "options": [
                        {
                            "label": option.label,
                            "text": option.text,
                        }
                        for option in issue.options
                    ],
                }
                for issue in prior_assessment.issues
            ],
            "results": [
                prior_result_payload(
                    proposal,
                    result_key=proposal_id_by_uid[proposal.uid],
                    relation_id_by_uid=relation_id_by_uid,
                )
                for proposal in prior_assessment.proposals
            ],
        }
        prior_relation_records = {
            record["relation_key"]: record for record in previous_relations
        }

    current = session.current_turn
    assert current is not None
    current_turn_id = turn_id_by_uid.get(current.uid)
    if current.sequence > 0:
        assert current_turn_id is not None
    current_payload = {
        "turn_id": current_turn_id,
        "revision": current.revision,
        "scope": current.scope,
        "issue_ids": [
            next(alias for alias, uid in prior_issue_by_id.items() if uid == issue_uid)
            for issue_uid in current.issue_uids
        ],
        "comment": current.comment,
        "revises_turn_ids": [turn_id_by_uid[uid] for uid in current.revises_turn_uids],
    }
    payload: dict[str, object] = {
        "mode": session.mode,
        "authority": (
            ("Both PEER sources have equal authority. Neither source wins by default.")
            if session.mode == "SYMMETRIC"
            else (
                "INCOMING may extend or correct the BASELINE only where the "
                "supplied evidence supports an exact change. Preserve every "
                "other BASELINE Memory."
            )
        ),
        "target": {
            "context_name": session.target.context_name,
            "contexts": [
                {
                    "target_context_id": context_id,
                    "context_name": identity[1],
                }
                for context_id, identity in target_context_by_id.items()
            ],
            "must_remain_empty_until_acceptance": (session.mode == "SYMMETRIC"),
            "must_remain_unchanged_until_acceptance": True,
        },
        "frames": frame_payloads,
        "history": history,
        "previous": previous,
        "current_turn": current_payload,
    }
    view = _ProviderView(
        memory_by_id=memory_by_id,
        memory_id_by_key=memory_id_by_key,
        memory_owner_by_id=memory_owner_by_id,
        target_context_by_id=target_context_by_id,
        target_context_id_by_identity=target_context_id_by_identity,
        frame_ids=frame_ids,
        turn_by_id=turn_by_id,
        turn_id_by_uid=turn_id_by_uid,
        prior_relation_by_id=prior_relation_by_id,
        prior_relation_records=prior_relation_records,
        prior_issue_by_id=prior_issue_by_id,
        prior_proposal_by_id=prior_proposal_by_id,
        payload=payload,
    )
    if (
        session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_DIRECTIONAL_RELATION_SCHEMA_VERSION
        and session.relation_analysis_seed is not None
        and current.sequence == 0
    ):
        basis = directional_relation_basis_assessment(
            session.relation_analysis_seed.analysis,
            (session.frames[0], session.frames[1]),
        )
        (
            basis_payload,
            basis_relations,
            basis_issues,
            _basis_proposals,
        ) = _assessment_provider_payload(session, basis, view)
        # Keep the provider field stable for cached completions and Study
        # prewarms; its Python owner is now the peer-relation capability.
        payload["comparison_basis"] = basis_payload
        view = replace(
            view,
            # Stable aliases let the decoder retain the exact reviewed relation
            # identities while still requiring a complete returned ledger.
            prior_relation_by_id=basis_relations,
            prior_relation_records={},
            prior_issue_by_id=basis_issues,
            payload=payload,
        )
    return view
