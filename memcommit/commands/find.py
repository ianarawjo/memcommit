from typing import Annotated

import typer


def cmd(query: Annotated[str, typer.Argument(help="Natural language query to find matching memories")]) -> None:
    typer.secho("'mem find' is not yet implemented.", fg=typer.colors.YELLOW)
