"""Revert-owned editable command grammar, exact effects, and approval receipt."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.adapters.console.terminal.components.command_editor.form import (
    CommandForm,
    CommandFormField,
    resolve_displayed_command_value,
)
from memcommit.adapters.console.terminal.components.command_editor.model import (
    CommandReview,
)
from memcommit.adapters.console.terminal.components.history.model import (
    HistoryDetailContent,
    HistoryDetailView,
    HistoryPickerItem,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text


@dataclass(frozen=True)
class RevertSelectionReceipt:
    """Exact local Revert selection; execution still revalidates its frozen frame."""

    context_name: str
    checkpoint_uid: str
    keep_history: bool = True


REVERT_COMMAND_FORM = CommandForm(
    command=("mem", "revert"),
    usage=("mem revert CHECKPOINT --context CONTEXT (--keep | --discard-newer)"),
    fields=(
        CommandFormField(
            "CHECKPOINT",
            "one exact checkpoint UID or unambiguous prefix",
        ),
        CommandFormField(
            "--context CONTEXT",
            "the frozen local Context whose state will be restored",
        ),
        CommandFormField(
            "--keep | --discard-newer",
            "the explicit newer-checkpoint retention policy",
        ),
    ),
)


def parse_revert_command_argv(
    argv: Sequence[str],
    *,
    context_name: str,
    entries: Sequence[HistoryPickerItem],
) -> tuple[str, bool]:
    """Resolve one editable Revert command against the frozen visible frame."""

    values = tuple(argv)
    if values[:2] != ("mem", "revert"):
        raise ValueError("Editable Revert commands must start with 'mem revert'.")
    if len(values) != 6:
        raise ValueError(
            "Editable Revert commands require CHECKPOINT --context CONTEXT "
            "and one explicit --keep or --discard-newer policy."
        )
    selector, context_flag, displayed_context, policy = values[2:]
    if context_flag not in {"--context", "-c"}:
        raise ValueError("Editable Revert commands require --context CONTEXT.")
    resolve_displayed_command_value(
        displayed_context,
        (context_name,),
        label="Revert --context Context",
    )
    policy_by_flag = {
        "--keep": True,
        "-k": True,
        "--discard-newer": False,
    }
    if policy not in policy_by_flag:
        raise ValueError("Editable Revert commands require --keep or --discard-newer.")
    matches = tuple(entry.uid for entry in entries if entry.uid.startswith(selector))
    if not matches:
        raise ValueError(
            f"Checkpoint selector '{selector}' is not available in this review."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Checkpoint selector '{selector}' matches {len(matches)} visible "
            "checkpoints."
        )
    return matches[0], policy_by_flag[policy]


def revert_exact_command_review(
    *,
    context_name: str,
    checkpoint_uid: str,
    keep_history: bool,
    affected_checkpoints: Sequence[tuple[str, str]] | None = None,
) -> CommandReview:
    """Project the final editable Revert boundary as one explicit command."""

    if not checkpoint_uid:
        raise ValueError("Select a checkpoint before reviewing Revert.")
    policy = "--keep" if keep_history else "--discard-newer"
    retention = (
        "Every currently visible checkpoint remains active."
        if keep_history
        else (
            "Newer active checkpoint files are removed; the recovery checkpoint "
            "retains their supported recovery metadata."
        )
    )
    affected = tuple(affected_checkpoints or ((context_name, checkpoint_uid),))
    if (
        not affected
        or len({name for name, _uid in affected}) != len(affected)
        or any(not name or not uid for name, uid in affected)
    ):
        raise ValueError("Revert review received invalid checkpoint membership.")
    effects = (
        (
            f"Only Context '{context_name}' may be restored.",
            f"The exact target is checkpoint [{checkpoint_uid[:8]}].",
            retention,
        )
        if len(affected) == 1
        else (
            f"The complete checkpoint unit will restore {len(affected)} Contexts.",
            *tuple(
                f"Context '{name}' uses checkpoint [{uid[:8]}]."
                for name, uid in affected
            ),
            retention,
        )
    )
    return CommandReview(
        argv=(
            "mem",
            "revert",
            checkpoint_uid,
            "--context",
            context_name,
            policy,
        ),
        effects=effects,
    )


def append_revert_review(
    rendered: HistoryDetailContent,
    review: CommandReview,
) -> HistoryDetailContent:
    """Keep exact operation effects beside the selected revision's detail."""

    unit_review = "\n".join(
        (
            "",
            "AFFECTED CHECKPOINT UNIT · REVIEW BEFORE APPLY",
            *("  " + display_escape_text(effect) for effect in review.effects),
        )
    )

    def append(content: str | StyleAndTextTuples) -> str | StyleAndTextTuples:
        if isinstance(content, str):
            return content.rstrip() + "\n" + unit_review
        return [*content, ("class:report-neutral", "\n" + unit_review)]

    if isinstance(rendered, HistoryDetailView):
        return HistoryDetailView(
            content=append(rendered.content),
            unit_start_lines=rendered.unit_start_lines,
            unit_label=rendered.unit_label,
        )
    return append(rendered)
