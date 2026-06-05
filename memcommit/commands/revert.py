from typing import Annotated

import typer

from memcommit.store import MemoryStore


def cmd(
    uid: Annotated[str, typer.Argument(help="UID (or unambiguous prefix) of the checkpoint to revert to")],
) -> None:
    store = MemoryStore()
    name = store.current_context_name()
    if not name:
        typer.secho("No current context. Run 'mem init <name>' first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        pre_cp, target_cp = store.revert(name, uid)
    except (KeyError, ValueError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    target_ts = target_cp.timestamp.strftime("%Y-%m-%d %H:%M")
    typer.secho(f"Reverted to [{target_cp.uid[:8]}] ({target_ts}).", fg=typer.colors.GREEN)
    typer.secho(f"Pre-revert state saved as [{pre_cp.uid[:8]}]  (revert to it to undo).", dim=True)
