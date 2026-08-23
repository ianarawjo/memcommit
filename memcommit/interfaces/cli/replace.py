"""Plain projections for deterministic Replace plans and receipts."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.replace_application import FrozenReplacePlan, ReplaceApplyResult


def render_replace_plan(plan: FrozenReplacePlan) -> str:
    replacement = (
        "(empty · remove matched text)"
        if plan.request.replacement == ""
        else safe_terminal_text(plan.request.replacement)
    )
    lines = [
        "REPLACE PLAN · READY FOR REVIEW",
        (
            f"PATTERN · {safe_terminal_text(plan.request.pattern)}"
            f" · {plan.request.mode}"
            f" · {'IGNORE CASE' if plan.request.ignore_case else 'CASE SENSITIVE'}"
        ),
        f"REPLACEMENT · {replacement}",
        (
            f"STATUS · REVIEW REQUIRED · CONTEXTS {plan.scanned_context_count}"
            f" · MEMORIES {plan.scanned_memory_count}"
            f" · MATCHED {plan.matched_memory_count}"
            f" · CHANGED {plan.changed_memory_count}"
            f" · OCCURRENCES {plan.occurrence_count}"
        ),
        f"PLAN DIGEST · {plan.plan_digest}",
    ]
    for context in plan.contexts:
        if not context.matches:
            continue
        lines.extend(("", f"CONTEXT · {safe_terminal_text(context.context_name)}"))
        for match in context.matches:
            spans = ", ".join(f"{span.start}:{span.end}" for span in match.spans)
            lines.extend(
                (
                    f"  MEMORY [{match.memory_uid[:8]}] · SPANS {spans}",
                    f"  - {safe_terminal_text(match.before_content)}",
                    f"  + {safe_terminal_text(match.after_content)}",
                )
            )
    if plan.matched_memory_count == 0:
        lines.extend(("", "(no matching Memories)"))
    elif plan.changed_memory_count == 0:
        lines.extend(("", "(matches found, but replacement would change no content)"))
    return "\n".join(lines)


def render_replace_apply_result(result: ReplaceApplyResult) -> str:
    if result.applied:
        occurrence = "occurrence" if result.occurrence_count == 1 else "occurrences"
        memory = "Memory" if result.changed_memory_count == 1 else "Memories"
        if len(result.checkpoints) == 1:
            location = (
                " in '" + safe_terminal_text(result.checkpoints[0].context_name) + "'"
            )
        else:
            location = f" across {len(result.checkpoints)} Contexts"
        return "\n".join(
            (
                (
                    f"Replaced {result.occurrence_count} {occurrence} in "
                    f"{result.changed_memory_count} {memory}{location}."
                ),
                "Undo can restore this command.",
            )
        )
    if result.matched_memory_count == 0:
        return "No matches. Nothing changed."
    occurrence = "occurrence" if result.occurrence_count == 1 else "occurrences"
    memory = "Memory" if result.matched_memory_count == 1 else "Memories"
    return (
        f"Found {result.occurrence_count} {occurrence} in "
        f"{result.matched_memory_count} {memory}, but replacement changed no content. "
        "Nothing changed."
    )


__all__ = ["render_replace_apply_result", "render_replace_plan"]
