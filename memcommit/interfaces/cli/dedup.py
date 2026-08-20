"""Plain terminal projection for semantic Dedun plans and receipts."""

from __future__ import annotations

import typer

from memcommit.dedup_application import DedupReceipt, FrozenDedupPlan
from memcommit.interfaces.console.text import display_escape_text


def _line(label: str, value: str) -> None:
    typer.echo(f"{label} · {display_escape_text(value)}")


def render_dedup_plan_plain(plan: FrozenDedupPlan) -> None:
    typer.secho("DEDUN · CONFIRMED SEMANTIC REDUNDANCIES", bold=True)
    _line("CONTEXT", plan.display_name)
    _line("REVISION", plan.revision)
    _line("COMPONENTS", str(len(plan.components)))
    for index, component in enumerate(plan.components, 1):
        typer.echo()
        typer.secho(f"COMPONENT {index} · {component.uid}", bold=True)
        for member in component.members:
            marker = (
                "RECOMMENDED SURVIVOR"
                if member.uid == component.recommended_survivor_uid
                else "MEMBER"
            )
            _line(
                marker,
                f"[{member.uid}] #{member.ordinal} · {member.content}",
            )
        for evidence in component.evidence:
            _line(
                "EVIDENCE",
                f"{evidence.relation} · {evidence.left_uid} ↔ {evidence.right_uid}",
            )
            _line("WHY", evidence.reason)
    typer.echo()
    typer.echo(
        "APPLY · rerun every --evidence, then add one "
        "--survivor COMPONENT=MEMORY per component, --expected-revision "
        f"{plan.revision}, and --apply"
    )


def render_dedup_receipt(receipt: DedupReceipt) -> None:
    typer.secho("DEDUN APPLIED", fg=typer.colors.GREEN, bold=True)
    _line("CONTEXT", receipt.context_name)
    _line("REVISION", receipt.revision)
    _line("COMPONENTS", str(len(receipt.selections)))
    _line("SURVIVORS", ", ".join(receipt.survivor_uids))
    _line("ABSORBED", ", ".join(receipt.absorbed_uids))
    _line("CHECKPOINT", receipt.checkpoint_uid)
    _line("RECOVERY", "mem undo")


__all__ = ["render_dedup_plan_plain", "render_dedup_receipt"]
