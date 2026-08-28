"""Plain terminal projection for Dedun plans and receipts."""

from __future__ import annotations

import typer

from memcommit.application.operations.dedun.application import DedunReceipt, FrozenDedunPlan
from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)


def _line(label: str, value: str) -> None:
    typer.echo(f"{label} · {display_escape_text(value)}")


def _semantic_line(label: str, value: str, role: SemanticColorRole) -> None:
    typer.secho(label, fg=semantic_color_rgb(role), bold=True, nl=False)
    typer.echo(" · " + display_escape_text(value))


def render_dedun_plan_plain(plan: FrozenDedunPlan) -> None:
    typer.secho("DEDUN · CONFIRMED EXACT + SEMANTIC REDUNDANCIES", bold=True)
    _line("CONTEXT", plan.display_name)
    _line("REVISION", plan.revision)
    _line(
        "GROUPS",
        str(len(plan.components) + len(plan.exact_item_groups)),
    )
    for index, component in enumerate(plan.components, 1):
        typer.echo()
        typer.secho(f"COMPONENT {index} · {component.uid}", bold=True)
        for member in component.members:
            marker = (
                "RECOMMENDED SURVIVOR"
                if member.uid == component.recommended_survivor_uid
                else "MEMBER"
            )
            value = f"[{member.uid}] #{member.ordinal} · {member.content}"
            if marker == "RECOMMENDED SURVIVOR":
                _semantic_line(marker, value, SemanticColorRole.ADD)
            else:
                _line(marker, value)
        for evidence in component.evidence:
            _line(
                "EVIDENCE",
                f"{evidence.relation} · {evidence.left_uid} ↔ {evidence.right_uid}",
            )
            _line("WHY", evidence.reason)
    for offset, group in enumerate(plan.exact_item_groups, 1):
        index = len(plan.components) + offset
        typer.echo()
        typer.secho(f"COMPONENT {index} · {group.item_kind}", bold=True)
        _semantic_line(
            "RECOMMENDED SURVIVOR",
            f"[{group.survivor_uid}] · {group.summary}",
            SemanticColorRole.ADD,
        )
        for uid in group.absorbed_uids:
            _line("MEMBER", f"[{uid}] · {group.summary}")
        _line("EVIDENCE", "EXACT · same role-specific identity")
    typer.echo()
    typer.echo(
        "APPLY · rerun every --evidence, then add one "
        "--survivor COMPONENT=MEMORY per component, --expected-revision "
        f"{plan.revision}, and --apply"
    )


def render_dedun_receipt(receipt: DedunReceipt) -> None:
    typer.secho("DEDUN APPLIED", fg=typer.colors.GREEN, bold=True)
    _line("CONTEXT", receipt.context_name)
    _line("REVISION", receipt.revision)
    _line("COMPONENTS", str(len(receipt.selections)))
    _semantic_line(
        "SURVIVORS",
        ", ".join(receipt.survivor_uids),
        SemanticColorRole.ADD,
    )
    _semantic_line(
        "ABSORBED",
        ", ".join(receipt.absorbed_uids),
        SemanticColorRole.REMOVE,
    )
    _line("RECEIPT", receipt.checkpoint_uid)
    _line("CHECKPOINT", receipt.checkpoint_uid)
    _line("REVIEW", f"mem review dedun --receipt {receipt.checkpoint_uid}")
    _line("RECOVERY", "mem undo")


__all__ = ["render_dedun_plan_plain", "render_dedun_receipt"]
