"""Render actual Sync file effects and committed automatic settings."""

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text as escape
from memcommit.adapters.console.terminal.core.theme import (
    semantic_action_role,
    semantic_color_rgb,
)


def render_sync_receipt(result):
    if result.conflict_choice:
        typer.echo(
            "Used "
            + ("mem" if result.conflict_choice == "mem" else "external files")
            + " for all conflicts; both versions are retained as checkpoints."
        )
        for name, uid in result.revert_checkpoint_uids:
            typer.echo(f"  REVERT · {escape(name)} [CHECKPOINT {uid[:8]}]")
    if result.context_effects:
        typer.echo(f"Synced project documents. [sync {result.run_uid[:8]}]")
        for action, name, target in result.context_effects:
            role = semantic_action_role(action)
            label = (
                typer.style(action, fg=semantic_color_rgb(role), bold=True)
                if role
                else action
            )
            typer.echo(
                f"  {label} CONTEXT · {escape(name)}"
                + (f" → {escape(target)}" if target else "")
            )
    if result.checkpoint_uids and not result.context_effects:
        for (name, checkpoint_uid), path in zip(
            result.checkpoint_uids, result.inbound_paths
        ):
            typer.echo(
                f"External file changes: {escape(path)} [CHECKPOINT {checkpoint_uid[:8]}]"
            )
            counts = {
                action: sum(
                    effect.context_name == name and effect.action == action
                    for effect in result.memory_effects
                )
                for action in ("EDIT", "ADD", "REMOVE", "REORDER")
            }
            typer.echo(
                f"  {counts['EDIT']} edited · {counts['ADD']} added · {counts['REMOVE']} removed"
                + (" · order changed" if counts["REORDER"] else "")
            )
    if result.run_uid and not result.checkpoint_uids:
        typer.echo(
            f"Synced {len(result.context_names)} Context(s). [sync {result.run_uid[:8]}]"
        )
    elif not result.run_uid:
        typer.echo(
            f"Sync checked {len(result.context_names)} Context(s); files already match."
        )
    for effect in result.effects:
        if result.checkpoint_uids and effect.action == "UNCHANGED":
            continue
        role = semantic_action_role(effect.action)
        label = (
            typer.style(effect.action, fg=semantic_color_rgb(role), bold=True)
            if role
            else effect.action
        )
        typer.echo("  " + label + " · " + escape(effect.path))


def render_sync_error(error):
    typer.echo("Sync failed: " + escape(str(error)), err=True)
