"""One English completion receipt for both Merge methods."""

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.merge.receipt import MergeReceipt


def _count(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def render_merge_receipt(result: MergeReceipt) -> str:
    summary = result.summary
    method_label = "LITERAL" if summary.method == "LITERAL" else "SEMANTIC"
    sources = " + ".join(
        f"{display_escape_text(name)} ({_count(count, 'note')})"
        for name, count in summary.sources
    )
    targets = " + ".join(
        f"{display_escape_text(name)} ({before} → {after} notes)"
        for name, before, after in summary.targets
    )
    conflict_summary = (
        "No conflicts found."
        if summary.decisions_applied == 0 and summary.issues_left_unresolved == 0
        else f"{_count(summary.decisions_applied, 'decision')} applied · {_count(summary.issues_left_unresolved, 'issue')} left unresolved"
    )
    return "\n".join(
        (
            f"MERGE APPLIED · {method_label}",
            f"{sources} → {targets}",
            conflict_summary,
            f"RECEIPT · {display_escape_text(result.checkpoint_uid)}",
            "RECOVERY · mem undo",
        )
    )
