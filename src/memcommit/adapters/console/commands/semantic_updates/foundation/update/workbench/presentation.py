"""Project exact Update plans into the common console Resolution workbench."""

from __future__ import annotations

from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionWorkbenchView,
)
from memcommit.application.operations.semantic_updates.foundation.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    SourceReference,
    UpdateOperation,
    UpdateSession,
    operation_digest,
)


def _source_references(refs: tuple[SourceReference, ...]) -> str:
    if not refs:
        return "No source references were recorded."
    return "\n\n".join(
        (
            f"{index}. Context {ref.context_name} [{ref.context_uid}]\n"
            f"Memory [{ref.memory_uid}]\n"
            f"Content SHA-256: {ref.content_digest}"
        )
        for index, ref in enumerate(refs, start=1)
    )


def _operation_item(
    operation: UpdateOperation,
    *,
    session_status: str,
) -> ResolutionItem:
    kind = operation.operation.upper()
    blocks: list[ResolutionDetailBlock] = [
        ResolutionDetailBlock(
            heading="OWNER",
            text=(
                f"Context {operation.owner_context_name} "
                f"[{operation.owner_context_uid}]"
            ),
        ),
        ResolutionDetailBlock(heading="MEMORY UID", text=operation.memory_uid),
    ]
    if isinstance(operation, (EditOperation, RemoveOperation)):
        blocks.append(ResolutionDetailBlock(heading="BEFORE", text=operation.old_content))
    if isinstance(operation, (EditOperation, AddOperation)):
        blocks.append(ResolutionDetailBlock(heading="AFTER", text=operation.new_content))
    blocks.extend(
        (
            ResolutionDetailBlock(heading="REASON", text=operation.reason),
            ResolutionDetailBlock(
                heading="SOURCE REFERENCES",
                text=_source_references(operation.source_refs),
            ),
        )
    )
    return ResolutionItem(
        uid=(
            f"{operation.operation}:{operation.owner_context_uid}:"
            f"{operation.memory_uid}"
        ),
        kind=kind,
        status=(
            "APPLIED"
            if session_status == "applied"
            else "UNDONE"
            if session_status == "undone"
            else "PLANNED"
        ),
        priority="CHANGE",
        title=f"{operation.owner_context_name} Memory [{operation.memory_uid}]",
        summary=operation.reason,
        role="CHANGE",
        obligation="NONE",
        response_state="NOT_APPLICABLE",
        blocks=tuple(blocks),
        commentable=False,
    )


class UpdateResolutionWorkbenchAdapter:
    """Expose exact saved operations without inventing an issue lifecycle."""

    def __init__(self, session: UpdateSession):
        if not isinstance(session, UpdateSession):
            raise TypeError("Expected an UpdateSession.")
        self._session = session

    def view(self) -> ResolutionWorkbenchView:
        session = self._session
        items = tuple(
            _operation_item(operation, session_status=session.status)
            for operation in session.operations
        )
        edit_count = sum(
            isinstance(operation, EditOperation) for operation in session.operations
        )
        add_count = sum(
            isinstance(operation, AddOperation) for operation in session.operations
        )
        remove_count = sum(
            isinstance(operation, RemoveOperation) for operation in session.operations
        )
        locations = tuple(
            dict.fromkeys(
                operation.owner_context_name for operation in session.operations
            )
        )
        location_text = (
            "no target Context locations"
            if not locations
            else (
                f"the target Context {locations[0]}"
                if len(locations) == 1
                else f"{len(locations)} target Context locations"
            )
        )
        overview = {
            "impact": (
                "Mem matched the verified Source against the Target and planned "
                "only the exact target Memory changes shown below. Nothing has "
                "been applied."
            ),
            "staged": (
                "The exact target Memory changes are staged and bound to this "
                "Source and Target revision. Apply remains separate."
            ),
            "applied": (
                "The exact target Memory changes shown below were applied to the "
                "recorded Target revision."
            ),
            "undone": (
                "The recorded target Memory changes were undone; this artifact "
                "still describes the exact reversible transition."
            ),
        }.get(session.status, "This Update records exact target Memory changes.")
        return ResolutionWorkbenchView(
            operation="UPDATE",
            artifact_uid=session.uid,
            revision=f"{session.status}:{operation_digest(session.operations)}",
            title="MEM UPDATE",
            route=f"SOURCE {session.source_name} → TARGET {session.target_name}",
            status=session.status.upper(),
            metrics=(
                ResolutionMetric("EDITS", str(edit_count)),
                ResolutionMetric("ADDITIONS", str(add_count)),
                ResolutionMetric("REMOVALS", str(remove_count)),
                ResolutionMetric("CHANGES", str(len(items))),
            ),
            context_locations=(
                ResolutionContextLocation("SOURCE", session.source_name),
                ResolutionContextLocation("TARGET", session.target_name),
            ),
            overview=overview,
            overview_sections=(ResolutionOverviewSection("plan", "PLAN", overview),),
            list_label="PLANNED CHANGES",
            items=items,
            empty_message="No planned changes are recorded in this Update artifact.",
            results_label="APPLICATION",
            results=(),
            capabilities=(
                frozenset({"ACCEPT"}) if session.status == "staged" else frozenset()
            ),
            accept_enabled=session.status == "staged",
            input_locked=False,
            report_items_summary=ResolutionDetailBlock(
                heading="WHAT WILL CHANGE",
                text=(
                    f"{len(items)} exact target Memory changes in {location_text}: "
                    f"{edit_count} EDIT, {add_count} ADD, and {remove_count} REMOVE. "
                    "Impact shows each located before/after transition once; exact "
                    "reason and source provenance remain inspectable in Items."
                ),
            ),
        )


def project_update_resolution(session: UpdateSession) -> ResolutionWorkbenchView:
    """Return a read-only common projection of one exact Update plan."""

    return UpdateResolutionWorkbenchAdapter(session).view()


__all__ = ["UpdateResolutionWorkbenchAdapter", "project_update_resolution"]
