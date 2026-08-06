"""Render opt-in shell integration for interactive command selection."""
from __future__ import annotations

from typing import Annotated

import typer


def render_zsh_init() -> str:
    """Return a zsh wrapper that prefills a selected help command."""
    return """\
# memcommit: make `mem help` place its selection in the next zsh edit buffer.
function mem {
  emulate -L zsh
  if [[ -o interactive && $ZSH_SUBSHELL -eq 0
        && -t 0 && -t 1 && -t 2
        && $# -eq 1 && $1 == help ]]; then
    local _mem_selected _mem_status
    _mem_selected="$(command mem help --emit-selection)"
    _mem_status=$?
    if (( _mem_status != 0 )); then
      return $_mem_status
    fi
    if [[ -z $_mem_selected ]]; then
      return 0
    fi
    if [[ $_mem_selected != mem && $_mem_selected != 'mem '* ]]; then
      builtin print -u2 -- 'mem: invalid command selection'
      return 1
    fi
    case $_mem_selected in
      (*[!A-Za-z0-9_./:=\\ -]*)
        builtin print -u2 -- 'mem: unsafe command selection'
        return 1
        ;;
    esac
    builtin print -rz -- "${_mem_selected} "
    return 0
  fi
  command mem "$@"
}
"""


def cmd(
    shell: Annotated[
        str,
        typer.Argument(help="Shell integration to print (currently: zsh)"),
    ] = "zsh",
) -> None:
    """Print shell code; evaluate it explicitly to enable integration."""
    if shell != "zsh":
        typer.secho(
            f"Error: unsupported shell '{shell}'; currently available: zsh.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    typer.echo(render_zsh_init(), nl=False)
