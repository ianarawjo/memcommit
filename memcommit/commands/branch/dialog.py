"""Compatibility facade for Branch's shared compact endpoint adapter."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.interfaces.tui.operations.branch import (
    choose_branch_endpoint_setup,
)


@dataclass(frozen=True)
class BranchCreationReceipt:
    """One frozen Source range and exact require-new branch target."""

    source_name: str
    target_name: str
    include_descendants: bool = False

    @property
    def new_name(self) -> str:
        """Compatibility spelling for callers that only accepted new targets."""

        return self.target_name


def choose_branch_creation(
    local_names: Sequence[str],
    *,
    current: str | None,
    suggest_name: Callable[[str], str],
    validate_name: Callable[[str], None],
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> BranchCreationReceipt | None:
    """Translate the interface-owned Branch selection into its legacy receipt."""

    if require_tty and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise ValueError("Interactive Branch setup requires a terminal.")
    selected = choose_branch_endpoint_setup(
        local_names,
        current=current,
        suggest_name=suggest_name,
        validate_name=validate_name,
        app_input=app_input,
        app_output=app_output,
        require_tty=False,
    )
    if selected is None:
        return None
    return BranchCreationReceipt(
        source_name=selected.source_name,
        target_name=selected.target_name,
        include_descendants=selected.include_descendants,
    )
