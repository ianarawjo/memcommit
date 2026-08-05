"""Pure Update-plan projection for the common resolution workbench.

Update currently has no issue-resolution artifact.  Its rows are therefore
labelled planned changes, carry no semantic actions, and make no claim that an
empty issue ledger was assessed or resolved.
"""
from __future__ import annotations

from memcommit.resolution_workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMetric,
    ResolutionWorkbenchView,
)
from memcommit.update import (
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
        ResolutionDetailBlock(
            heading="MEMORY UID",
            text=operation.memory_uid,
        ),
    ]
    if isinstance(operation, (EditOperation, RemoveOperation)):
        blocks.append(
            ResolutionDetailBlock(
                heading="BEFORE",
                text=operation.old_content,
            )
        )
    if isinstance(operation, (EditOperation, AddOperation)):
        blocks.append(
            ResolutionDetailBlock(
                heading="AFTER",
                text=operation.new_content,
            )
        )
    blocks.extend(
        (
            ResolutionDetailBlock(
                heading="REASON",
                text=operation.reason,
            ),
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
        priority="PLANNED",
        title=(
            f"{kind} {operation.owner_context_name} "
            f"Memory [{operation.memory_uid}]"
        ),
        summary=operation.reason,
        blocks=tuple(blocks),
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
            isinstance(operation, EditOperation)
            for operation in session.operations
        )
        add_count = sum(
            isinstance(operation, AddOperation)
            for operation in session.operations
        )
        remove_count = sum(
            isinstance(operation, RemoveOperation)
            for operation in session.operations
        )
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
            overview=(
                "This saved Update artifact records exact planned changes. "
                "It is not an issue-resolution assessment."
            ),
            list_label="PLANNED CHANGES",
            items=items,
            empty_message="No planned changes are recorded in this Update artifact.",
            results_label="APPLICATION",
            results=(),
            capabilities=frozenset(),
            accept_enabled=False,
            input_locked=False,
        )


def project_update_resolution(session: UpdateSession) -> ResolutionWorkbenchView:
    """Return a read-only common projection of one exact Update plan."""
    return UpdateResolutionWorkbenchAdapter(session).view()
