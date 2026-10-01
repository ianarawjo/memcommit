"""Applied Update changes and completion evidence in terminal scrollback."""

from __future__ import annotations

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change_text,
)
from memcommit.application.capabilities.reviewing.memory_diff import (
    update_operation_change,
)

from memcommit.application.operations.update.model import (
    UpdateReceipt,
)


def render_update_receipt(receipt: UpdateReceipt, *, color: bool = False) -> str:
    """Render terminal Update success without reopening its full report."""

    edits, additions, removals = (
        sum(op.operation == kind for op in receipt.plan.operations)
        for kind in ("edit", "add", "remove")
    )
    checkpoints = receipt.application.checkpoints
    target_label = display_escape_text(receipt.inputs.target_name)
    source_label = (
        display_escape_text(receipt.inputs.instruction.text)
        if receipt.inputs.instruction is not None
        else display_escape_text(receipt.inputs.inline_source_content)
        if receipt.inputs.inline_source_content is not None
        else display_escape_text(receipt.inputs.source_name)
    )
    lines = [
        f"UPDATE APPLIED {target_label}",
        f"{source_label} -> {target_label}",
    ]
    if (
        receipt.inputs.instruction is not None
        and receipt.inputs.source_memory_uid is not None
    ):
        lines.append(
            "FROM MEMORY · "
            + display_escape_text(
                f"[{receipt.inputs.source_name}:{receipt.inputs.source_memory_uid[:8]}]"
            )
        )
    lines.append(f"EFFECTS · ADD {additions} · EDIT {edits} · REMOVE {removals}")
    if receipt.plan.operations:
        lines.append("")
    lines.extend(
        render_inline_memory_change_text(
            update_operation_change(operation),
            identity=f"[memory {operation.memory_uid[:8]}]"
            if operation.owner_context_name == receipt.inputs.target_name
            else None,
            color=color,
        )
        for operation in receipt.plan.operations
    )
    lines.extend(("", f"RECEIPT · {receipt.uid}"))
    if not receipt.plan.operations:
        lines.insert(1, "OUTCOME · NO CHANGE · no Context checkpoint")
    if receipt.inputs.goal_focus is not None:
        lines.append(
            "GOAL FOCUS · "
            f"{receipt.inputs.goal_focus.kind} · {display_escape_text(receipt.inputs.goal_focus.label)} · "
            f"{len(receipt.inputs.goal_focus.items)} ITEM"
            f"{'S' if len(receipt.inputs.goal_focus.items) != 1 else ''}"
        )
    if checkpoints:
        lines.append(
            "CHECKPOINTS · "
            + " · ".join(
                f"{display_escape_text(item.context_name)} [{item.checkpoint_uid}]"
                for item in checkpoints
            )
        )
    lines.append(f"REVIEW · mem review update --session {receipt.uid}")
    if receipt.inputs.granted_target is None and checkpoints:
        lines.append("RECOVERY · mem undo")
    elif receipt.inputs.granted_target is not None:
        lines.append("RECOVERY · governed by the granted authority owner")
    return "\n".join(lines)


__all__ = ["render_update_receipt"]
