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
    lines = [
        "REPLACE COMPLETE" if result.applied else "REPLACE COMPLETE · NO CHANGES",
        f"PLAN DIGEST · {result.plan_digest}",
        (
            f"STATUS · {'APPLIED' if result.applied else 'NO-OP'}"
            f" · MATCHED {result.matched_memory_count}"
            f" · CHANGED {result.changed_memory_count}"
            f" · OCCURRENCES {result.occurrence_count}"
            f" · CHECKPOINTS {len(result.checkpoints)}"
        ),
    ]
    for checkpoint in result.checkpoints:
        lines.append(
            f"  {safe_terminal_text(checkpoint.context_name)}"
            f" [{checkpoint.context_uid[:8]}]"
            f" · checkpoint [{checkpoint.checkpoint_uid[:8]}]"
        )
    return "\n".join(lines)


__all__ = ["render_replace_apply_result", "render_replace_plan"]
