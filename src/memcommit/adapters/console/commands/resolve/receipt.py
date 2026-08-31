"""Durable Apply receipt projection for Resolve."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.resolve.application import ResolveReceipt


def _line(label: str, value: str) -> None:
    typer.secho(f"{label} · {display_escape_text(value)}")


def render_resolve_receipt(
    receipt: ResolveReceipt,
    *,
    verification: str | None = None,
) -> None:
    """Render one durable exact Apply receipt."""

    if verification is None:
        verification = "POST-IMAGE CHECKED"
    typer.secho(
        f"RESOLVE · {display_escape_text(receipt.context_name)}",
        bold=True,
    )
    effect_counts = (
        ("CREATE", len(receipt.created_uids)),
        ("UPDATE", len(receipt.updated_uids)),
        ("DELETE", len(receipt.deleted_uids)),
    )
    effects = " · ".join(
        f"{kind} {count}" for kind, count in effect_counts if count
    )
    if not effects:
        effects = "NO MEMORY CHANGES"
    _line("APPLIED", f"{effects} · {verification}")
    if receipt.unresolved_issue_uids:
        _line("UNRESOLVED", str(len(receipt.unresolved_issue_uids)))
    _line("CHECKPOINT", receipt.checkpoint_uid)
    _line(
        "REVIEW",
        f"mem review resolve --receipt {receipt.checkpoint_uid}",
    )
    _line("RECOVERY", "mem undo")


__all__ = ["render_resolve_receipt"]
