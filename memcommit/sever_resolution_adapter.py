"""Pure Sever projection into the shared interactive Resolution Workbench."""

from __future__ import annotations

from memcommit.resolution_workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOption,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.sever import SeverSession, sever_record_digest


class SeverResolutionWorkbenchAdapter:
    def __init__(self, session: SeverSession):
        self.session = session

    def view(self) -> ResolutionWorkbenchView:
        session = self.session
        criteria_by_uid = {memory.uid: memory for memory in session.criteria.memories}
        selection_option = {
            "RECOMMENDED": "recommended",
            "AS_WRITTEN": "as-written",
            "EXCLUDE": "exclude",
            "CUSTOM": None,
        }
        items: list[ResolutionItem] = []
        for candidate in session.candidates:
            source = session.source_memory(candidate.source_memory_uid)
            cited = [criteria_by_uid[uid] for uid in candidate.criterion_memory_uids]
            criterion_text = (
                "\n\n".join(
                    f"{memory.context_name} · [{memory.uid[:8]}]\n{memory.content}"
                    for memory in cited
                )
                or "No individual criterion Memory was cited."
            )
            selected = selection_option[candidate.selection]
            items.append(
                ResolutionItem(
                    uid=candidate.uid,
                    kind="DISCLOSURE",
                    status=candidate.selection,
                    priority="REVIEW",
                    title=f"{source.context_name} · [{source.uid[:8]}]",
                    summary=candidate.rationale,
                    question="Choose the exact outbound treatment for this Memory.",
                    options=(
                        ResolutionOption(
                            uid=f"{candidate.uid}:recommended",
                            label=f"Use recommendation · {candidate.recommendation}",
                            text=(candidate.proposed_content or "Do not include this Memory."),
                        ),
                        ResolutionOption(
                            uid=f"{candidate.uid}:as-written",
                            label="Send as written",
                            text=source.content,
                        ),
                        ResolutionOption(
                            uid=f"{candidate.uid}:exclude",
                            label="Do not send",
                            text="Exclude this source Memory from the local outbound draft.",
                        ),
                    ),
                    selected_option_uid=(
                        None if selected is None else f"{candidate.uid}:{selected}"
                    ),
                    blocks=(
                        ResolutionDetailBlock(heading="SOURCE", text=source.content),
                        ResolutionDetailBlock(
                            heading="RECOMMENDED OUTBOUND",
                            text=candidate.proposed_content or "(excluded)",
                        ),
                        ResolutionDetailBlock(heading="CRITERIA", text=criterion_text),
                    ),
                )
            )
        results = tuple(
            ResolutionResult(
                uid=candidate.uid,
                marker="−" if candidate.selection == "EXCLUDE" else "+",
                label=(
                    candidate.selection
                    if candidate.selection != "RECOMMENDED"
                    else candidate.recommendation
                ),
                text=(
                    "Excluded from outbound draft."
                    if candidate.selection == "EXCLUDE"
                    else candidate.custom_content
                    if candidate.selection == "CUSTOM"
                    else session.source_memory(candidate.source_memory_uid).content
                    if candidate.selection == "AS_WRITTEN"
                    else candidate.proposed_content or "Excluded from outbound draft."
                ),
                reason=candidate.rationale,
            )
            for candidate in session.candidates
        )
        return ResolutionWorkbenchView(
            operation="sever",
            artifact_uid=session.uid,
            revision=sever_record_digest(session),
            title="MEM SEVER · LOCAL DISCLOSURE REVIEW",
            route=(
                f"SOURCE {session.source.root_name} × CRITERIA "
                f"{session.criteria.root_name} → OUTPUT {session.output_name}"
            ),
            status=f"{session.state} · NOT SENT",
            metrics=(
                ResolutionMetric(label="SOURCE", value=str(len(session.source.memories))),
                ResolutionMetric(label="CRITERIA", value="1 Context"),
                ResolutionMetric(label="OUTBOUND", value=str(len(session.outbound()))),
            ),
            overview=(
                session.overview
                + "\n\nOnly this one Criteria Context influenced the proposal. "
                "Query-only views were not opened or sent to the provider."
            ),
            list_label="SOURCE MEMORIES",
            items=tuple(items),
            empty_message="No source Memories.",
            results_label="LOCAL OUTBOUND DRAFT · NOT SENT",
            results=results,
            capabilities=(
                frozenset()
                if session.state == "APPLIED"
                else frozenset({"SUBMIT_ITEM", "ACCEPT"})
            ),
            accept_enabled=session.state == "REVIEWING",
            input_locked=session.state == "APPLIED",
        )
