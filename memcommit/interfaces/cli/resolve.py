"""Plain terminal projection for typed Resolve analyses and receipts."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.resolve_application import (
    ResolveAnalysis,
    ResolveCandidate,
    ResolveReceipt,
)


def _line(label: str, value: str, *, color: str | None = None) -> None:
    typer.secho(
        f"{label} · {display_escape_text(value)}",
        fg=color,
    )


def _candidate(candidate: ResolveCandidate, index: int) -> None:
    typer.echo()
    typer.secho(f"CANDIDATE {index} · {candidate.uid}", bold=True)
    _line("SUMMARY", candidate.summary)
    _line(
        "MINIMUM COST",
        (
            f"DELETE {candidate.cost.deletes} · CREATE {candidate.cost.creates} · "
            f"UPDATE {candidate.cost.updates} · CHANGED UNITS "
            f"{candidate.cost.changed_units}"
        ),
    )
    for effect in candidate.effects:
        typer.secho(
            f"  {effect.kind} · [{effect.memory_uid[:8]}]",
            fg=(
                typer.colors.RED
                if effect.kind == "DELETE"
                else typer.colors.GREEN
                if effect.kind == "CREATE"
                else typer.colors.YELLOW
            ),
            bold=True,
        )
        if effect.old_content is not None:
            _line("    BEFORE", effect.old_content)
        if effect.new_content is not None:
            _line("    AFTER", effect.new_content)
        _line("    WHY", effect.reason)
        _line(
            "    SOURCES",
            ", ".join(uid[:8] for uid in effect.source_memory_uids),
        )
    _line("VERIFIED", candidate.verification_reason, color=typer.colors.GREEN)
    _line("FIT", f"YES · {candidate.fit.reason}", color=typer.colors.GREEN)


def render_resolve_plain(analysis: ResolveAnalysis) -> None:
    """Render a complete process-local proposal without applying it."""

    typer.secho("RESOLVE · FIT REPAIR", bold=True)
    _line("CONTEXT", analysis.frame.display_name)
    _line("REVISION", analysis.frame.revision)
    _line("STATUS", analysis.status)
    _line("REQUESTED EFFECTS", ", ".join(analysis.frame.request.requested_effects))
    _line(
        "ALLOWED EFFECTS",
        ", ".join(analysis.frame.allowed_effects) or "NONE",
    )
    if analysis.frame.denied_effects:
        _line(
            "DENIED EFFECTS",
            ", ".join(analysis.frame.denied_effects),
            color=typer.colors.YELLOW,
        )
    if analysis.initial_fit is not None:
        _line(
            "INITIAL FIT",
            f"{analysis.initial_fit.verdict} · {analysis.initial_fit.reason}",
        )
    if analysis.question:
        _line("QUESTION", analysis.question)
    for index, candidate in enumerate(analysis.candidates, 1):
        _candidate(candidate, index)
    if analysis.candidates:
        typer.echo()
        typer.echo(
            "APPLY · rerun with --candidate <full-id> --expected-revision "
            f"{analysis.frame.revision} --apply"
        )
        typer.echo(
            "The candidate id hashes the exact effect post-image; regeneration "
            "fails closed if that candidate is unavailable."
        )


def render_resolve_receipt(receipt: ResolveReceipt) -> None:
    """Render one durable exact Apply receipt."""

    typer.secho("RESOLVE APPLIED", fg=typer.colors.GREEN, bold=True)
    _line("CONTEXT", receipt.context_name)
    _line("CANDIDATE", receipt.candidate_uid)
    _line("REVISION", receipt.revision)
    _line("CREATED", str(len(receipt.created_uids)))
    _line("UPDATED", str(len(receipt.updated_uids)))
    _line("DELETED", str(len(receipt.deleted_uids)))
    _line("CHECKPOINT", receipt.checkpoint_uid)
    _line("RECOVERY", "mem undo")


__all__ = ["render_resolve_plain", "render_resolve_receipt"]
