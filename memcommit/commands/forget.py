from typing import Annotated

import typer


def cmd(info: Annotated[str, typer.Argument(help="Description of memories to forget")]) -> None:
    typer.secho("'mem forget' is not yet implemented.", fg=typer.colors.YELLOW)
