from typing import Annotated

import typer

from memcommit.context import Context, Memory
from memcommit.store import ContextStore


def cmd(uid: Annotated[str, typer.Argument(help="UID (or unambiguous prefix) of the item to remove")]) -> None:
    store = ContextStore()
    try:
        ctx = store.load_current()
    except RuntimeError as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    matches = [k for k in ctx.memories if k.startswith(uid)]
    if not matches:
        typer.secho(f"Error: no item found with uid starting with '{uid}'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if len(matches) > 1:
        typer.secho(f"Ambiguous prefix '{uid}' — matches:", fg=typer.colors.RED, err=True)
        for m in matches:
            typer.echo(f"  {m}")
        raise typer.Exit(1)

    full_uid = matches[0]
    item = ctx.memories[full_uid]
    ctx.remove(full_uid)
    store.save_context(ctx)

    if isinstance(item, Memory):
        typer.secho(f"Removed [{full_uid[:8]}] {item.content}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Removed embedded context '{item.name}' [{full_uid[:8]}]", fg=typer.colors.GREEN)
