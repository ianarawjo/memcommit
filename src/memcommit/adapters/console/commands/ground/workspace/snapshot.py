"""Stable non-interactive snapshot of a physical Ground workspace."""

from __future__ import annotations

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.ground.workspace_model import GroundWorkspace
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


def _direct_item_label(value: object) -> str:
    if isinstance(value, MemoryRef):
        return "MEMORY REF"
    if isinstance(value, QueryContextRef):
        return "QUERY CONTEXT"
    if isinstance(value, Context):
        return "CONTEXT"
    return "MEMORY"


def _context_summary(context: Context) -> str:
    count = len(tuple(context.iter_items()))
    return f"{count} direct item" + ("" if count == 1 else "s")


def render_ground_workspace_snapshot(workspace: GroundWorkspace) -> str:
    """Return one stable read-only projection without terminal side effects."""

    lines = [
        f"GROUND WORKSPACE · {safe_terminal_text(workspace.name)}",
        (
            f"STATUS · {workspace.manifest.status} · "
            f"REVISION {workspace.manifest.revision}"
        ),
        "",
        "CONTEXTS",
    ]
    for context in workspace.all_contexts:
        suffix = " · ROOT" if context.uid == workspace.uid else ""
        lines.append(
            f"  {safe_terminal_text(context.name)} · "
            f"{_context_summary(context)}{suffix}"
        )
    lines.extend(("", "CONTENTS"))
    any_items = False
    for context in workspace.lane_contexts:
        items = tuple(context.iter_items())
        if not items:
            continue
        any_items = True
        lines.append(f"  /{context.name.rsplit('/', 1)[-1]}")
        for item in items:
            if isinstance(item, Memory):
                value = safe_terminal_text(item.content).replace("\n", " ")
            elif isinstance(item, MemoryRef):
                value = f"{item.target_context_name} [{item.target_memory_uid[:8]}]"
            else:
                value = item.name
            lines.append(
                f"    [{item.uid[:8]}] {_direct_item_label(item)} · "
                f"{safe_terminal_text(value)}"
            )
    if not any_items:
        lines.append("  (empty)")
    lines.extend(
        (
            "",
            "Ground workspace Contexts and Memories are physical Store records.",
            "Global current Context: unchanged.",
        )
    )
    return "\n".join(lines)


__all__ = ["render_ground_workspace_snapshot"]
