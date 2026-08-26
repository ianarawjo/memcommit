"""Typed in-process review state for one batch Forget analysis."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.context import Context, Memory
from memcommit.selective_curation import CurationAnalysis, CurationDecision, CurationItem
from memcommit.semantic.changes import EditChange, ProposedChange, RemoveChange


ForgetSelection = Literal["RECOMMENDED", "KEEP", "DELETE", "CUSTOM"]


class ForgetReviewError(ValueError):
    pass


@dataclass(frozen=True)
class ForgetCandidate:
    uid: str
    decision: CurationDecision
    # Retain the frozen Source beside its decision so neither the report nor
    # the materializer needs to reopen a live Context during review.
    source: CurationItem
    selection: ForgetSelection = "RECOMMENDED"
    custom_content: str = ""

    def selected_action(self) -> tuple[str, str]:
        if self.selection == "KEEP":
            return "KEEP", self.source.content
        if self.selection == "DELETE":
            return "DROP", ""
        if self.selection == "CUSTOM":
            return "TRANSFORM", self.custom_content
        return self.decision.action, self.decision.proposed_content

@dataclass(frozen=True)
class ForgetReview:
    uid: str
    revision: int
    context_name: str
    context_uid: str
    instruction: str
    overview: str
    candidates: tuple[ForgetCandidate, ...]

    @classmethod
    def create(
        cls,
        context: Context,
        instruction: str,
        analysis: CurationAnalysis,
    ) -> "ForgetReview":
        review_uid = str(uuid.uuid4())
        sources = {
            uid: CurationItem(uid, item.content, context.name)
            for uid, item in context.iter_entries()
            if isinstance(item, Memory)
        }
        if {decision.source_uid for decision in analysis.decisions} != set(sources):
            raise ForgetReviewError(
                "Forget decisions do not cover the reviewed Source frame."
            )
        return cls(
            uid=review_uid,
            revision=1,
            context_name=context.name,
            context_uid=context.uid,
            instruction=instruction,
            overview=analysis.overview,
            candidates=tuple(
                ForgetCandidate(
                    uid=str(uuid.uuid5(uuid.UUID(review_uid), decision.source_uid)),
                    decision=decision,
                    source=sources[decision.source_uid],
                )
                for decision in analysis.decisions
            ),
        )

    def select(
        self,
        candidate_uid: str,
        selection: ForgetSelection,
        custom_content: str = "",
    ) -> "ForgetReview":
        if selection == "CUSTOM" and not custom_content.strip():
            raise ForgetReviewError("Custom Forget wording cannot be empty.")
        if selection != "CUSTOM" and custom_content:
            raise ForgetReviewError("Only a custom Forget selection stores text.")
        found = False
        candidates = []
        for candidate in self.candidates:
            if candidate.uid != candidate_uid:
                candidates.append(candidate)
                continue
            found = True
            candidates.append(
                replace(
                    candidate,
                    selection=selection,
                    custom_content=custom_content if selection == "CUSTOM" else "",
                )
            )
        if not found:
            raise ForgetReviewError("Unknown Forget candidate.")
        return replace(self, revision=self.revision + 1, candidates=tuple(candidates))

    def revise(
        self,
        context: Context,
        analysis: CurationAnalysis,
    ) -> "ForgetReview":
        """Replace provider decisions while preserving process-local identity.

        Provider feedback is a new semantic turn over the same frozen Source,
        not a new durable session. Keeping the review UID and advancing the
        revision lets non-terminal adapters reject stale selections without
        inventing persisted Forget state.
        """

        if context.name != self.context_name or context.uid != self.context_uid:
            raise ForgetReviewError(
                "Forget revision must use the original frozen Source Context."
            )
        revised = ForgetReview.create(context, self.instruction, analysis)
        candidates = tuple(
            replace(
                candidate,
                uid=str(uuid.uuid5(uuid.UUID(self.uid), candidate.source.uid)),
            )
            for candidate in revised.candidates
        )
        return replace(
            revised,
            uid=self.uid,
            revision=self.revision + 1,
            candidates=candidates,
        )

    def changes(self) -> list[ProposedChange]:
        changes: list[ProposedChange] = []
        for candidate in self.candidates:
            action, content = candidate.selected_action()
            if action == "DROP":
                changes.append(
                    RemoveChange(
                        uid=candidate.source.uid,
                        content=candidate.source.content,
                        reason=candidate.decision.rationale,
                    )
                )
            elif action == "TRANSFORM":
                changes.append(
                    EditChange(
                        uid=candidate.source.uid,
                        old_content=candidate.source.content,
                        new_content=content,
                        reason=candidate.decision.rationale,
                    )
                )
        return changes
