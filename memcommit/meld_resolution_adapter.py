"""Pure projection from durable Meld state into the common workbench.

Meld remains authoritative for relation judgments, replacement assessments,
readiness, and application.  This adapter only gives the shared interactive
surface enough exact, UID-addressed data to render the current revision.
"""

from __future__ import annotations

from memcommit.meld import MeldProposal, MeldSession, meld_accounting
from memcommit.resolution_workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOption,
    ResolutionResult,
    ResolutionWorkbenchView,
)


def _route(session: MeldSession) -> str:
    if session.mode == "DIRECTIONAL":
        frame_by_role = {frame.role: frame for frame in session.frames}
        incoming = frame_by_role["INCOMING"]
        return (
            f"INCOMING {incoming.context_name} → "
            f"BASELINE / TARGET {session.target.context_name}"
        )
    return (
        f"{session.frames[0].context_name} + "
        f"{session.frames[1].context_name} → "
        f"{session.target.context_name}"
    )


def _proposal_marker(session: MeldSession, proposal: MeldProposal) -> str:
    if session.mode == "DIRECTIONAL" and proposal.operation == "EDIT":
        return "~"
    return "+"


def _proposal_label(session: MeldSession, proposal: MeldProposal) -> str:
    if session.mode == "DIRECTIONAL":
        return f"{proposal.operation} · {proposal.disposition}"
    return proposal.disposition


def _memory_location(fallback_context: str, content: str) -> tuple[str, str]:
    """Avoid repeating a recursive Context prefix in both metadata and text."""
    if content.startswith("[") and "] " in content:
        prefix, body = content[1:].split("] ", 1)
        if prefix == fallback_context or prefix.startswith(f"{fallback_context}/"):
            return prefix, body
    return fallback_context, content


class MeldResolutionWorkbenchAdapter:
    """Expose one saved Meld revision without calling its provider or store."""

    def __init__(self, session: MeldSession):
        if not isinstance(session, MeldSession):
            raise TypeError("Expected a MeldSession.")
        self._session = session

    def view(self) -> ResolutionWorkbenchView:
        session = self._session
        turn = session.current_turn
        assessment = session.current_assessment
        revision = (
            f"{session.state}:{turn.uid}"
            if turn is not None
            else f"{session.state}:NO_TURN"
        )
        relation_count = len(assessment.relations) if assessment else 0
        proposal_count = len(assessment.proposals) if assessment else 0
        accounting = meld_accounting(session)

        if assessment is None:
            items: tuple[ResolutionItem, ...] = ()
            results: tuple[ResolutionResult, ...] = ()
            overview = ""
        else:
            relation_by_uid = {
                relation.uid: relation for relation in assessment.relations
            }
            relation_number = {
                relation.uid: index
                for index, relation in enumerate(assessment.relations, start=1)
            }
            frame_by_uid = {frame.uid: frame for frame in session.frames}
            memory_by_key = {
                (frame.uid, memory.uid): memory
                for frame in session.frames
                for memory in frame.memories
            }
            projected_items: list[ResolutionItem] = []
            ordered_issues = sorted(
                assessment.issues,
                key=lambda issue: 0 if issue.priority == "REQUIRED" else 1,
            )
            for issue in ordered_issues:
                seen_members: set[tuple[str, str]] = set()
                source_lines: list[str] = []
                relation_lines: list[str] = []
                relation_kinds: list[str] = []
                for relation_uid in issue.relation_uids:
                    relation = relation_by_uid[relation_uid]
                    if relation.kind not in relation_kinds:
                        relation_kinds.append(relation.kind)
                    relation_lines.append(
                        f"R{relation_number[relation_uid]} · "
                        f"{relation.kind} · {relation.status}\n"
                        f"{relation.summary}\nWHY · {relation.reason}"
                    )
                    for member in relation.members:
                        key = (member.frame_uid, member.memory_uid)
                        if key in seen_members:
                            continue
                        seen_members.add(key)
                        frame = frame_by_uid[member.frame_uid]
                        memory = memory_by_key[key]
                        location, content = _memory_location(
                            frame.context_name,
                            memory.content,
                        )
                        role = "" if session.mode == "SYMMETRIC" else f"{frame.role} · "
                        source_lines.append(
                            f"{role}{location} · #{memory.position + 1} "
                            f"· [{memory.uid[:8]}]\n{content}"
                        )
                affected = [
                    proposal
                    for proposal in assessment.proposals
                    if set(proposal.relation_uids) & set(issue.relation_uids)
                ]
                affected_lines = [
                    (
                        f"{_proposal_marker(session, proposal)} "
                        f"[{_proposal_label(session, proposal)}] "
                        f"Memory [{proposal.memory_uid[:8]}]\n"
                        f"{proposal.content}\nWHY · {proposal.reason}"
                    )
                    for proposal in affected
                ]
                if not affected_lines:
                    affected_lines.append(
                        "No target Memory is proposed for these relations yet."
                    )
                issue_title = issue.title
                if issue.priority == "HELPFUL" and len(issue.relation_uids) == 1:
                    relation = relation_by_uid[issue.relation_uids[0]]
                    issue_title = f"{relation.kind.title()} · {relation.summary}"
                projected_items.append(
                    ResolutionItem(
                        uid=issue.uid,
                        kind=" / ".join(relation_kinds) or "MELD",
                        status="OPEN",
                        priority=issue.priority,
                        title=issue_title,
                        summary=issue.why_it_matters,
                        question=issue.question,
                        options=tuple(
                            ResolutionOption(
                                uid=option.uid,
                                label=option.label,
                                text=option.text,
                            )
                            for option in issue.options
                        ),
                        blocks=(
                            ResolutionDetailBlock(
                                heading="EVIDENCE",
                                text="\n\n".join(source_lines),
                            ),
                            ResolutionDetailBlock(
                                heading="RELATIONS",
                                text="\n\n".join(relation_lines),
                            ),
                            ResolutionDetailBlock(
                                heading="PROPOSED RESULT",
                                text="\n\n".join(affected_lines),
                            ),
                        ),
                    )
                )
            items = tuple(projected_items)
            results = tuple(
                ResolutionResult(
                    uid=proposal.uid,
                    marker=_proposal_marker(session, proposal),
                    label=_proposal_label(session, proposal),
                    text=proposal.content,
                    reason=proposal.reason,
                )
                for proposal in assessment.proposals
            )
            overview = (
                f"{assessment.overview}\n\n"
                "ACCOUNTING\n"
                f"Source coverage · {accounting.represented_sources}/"
                f"{accounting.source_memories}\n"
                f"Relation coverage · {accounting.represented_relations}/"
                f"{accounting.primary_relations}\n"
                f"Final Memories · {accounting.final_memories} "
                f"(PRESERVE {accounting.preserve_results} · "
                f"COALESCE {accounting.coalesce_results} · "
                f"SYNTHESIZE {accounting.synthesize_results} · "
                f"USER_ADD {accounting.user_add_results})\n"
                f"Open issues · REQUIRED {accounting.required_issues} · "
                f"HELPFUL {accounting.helpful_issues}\n"
                f"Cross-relation results · {accounting.cross_relation_results}"
            )

        active = assessment is not None and session.state in {
            "AWAITING_REPLY",
            "READY_TO_APPLY",
        }
        capabilities = (
            frozenset(
                {
                    "SUBMIT_ITEM",
                    "SUBMIT_ALL",
                    "PRESERVE_ALL",
                    "DEFER",
                    "ACCEPT",
                }
            )
            if active
            else frozenset()
        )
        ready = bool(
            active
            and session.state == "READY_TO_APPLY"
            and assessment is not None
            and assessment.ready_to_apply
        )
        return ResolutionWorkbenchView(
            operation="MELD",
            artifact_uid=session.uid,
            revision=revision,
            title=f"MEM MELD · {session.mode}",
            route=_route(session),
            status=session.state,
            metrics=(
                ResolutionMetric("MODE", session.mode),
                ResolutionMetric("RELATIONS", str(relation_count)),
                ResolutionMetric(
                    "ISSUES",
                    (
                        f"{accounting.required_issues} required + "
                        f"{accounting.helpful_issues} helpful"
                    ),
                ),
                ResolutionMetric(
                    "CHANGES" if session.mode == "DIRECTIONAL" else "RESULTS",
                    str(proposal_count),
                ),
                ResolutionMetric(
                    "SOURCE COVERAGE",
                    f"{accounting.represented_sources}/{accounting.source_memories}",
                ),
            ),
            overview=overview,
            list_label="ISSUES",
            items=items,
            empty_message="No current Meld issues.",
            results_label=(
                "PROPOSED BASELINE CHANGES"
                if session.mode == "DIRECTIONAL"
                else "PROPOSED TARGET MEMORIES"
            ),
            results=results,
            capabilities=capabilities,
            accept_enabled=ready,
            input_locked=(assessment is None),
        )


def project_meld_resolution(session: MeldSession) -> ResolutionWorkbenchView:
    """Return the common view for one complete saved Meld revision."""
    return MeldResolutionWorkbenchAdapter(session).view()
