"""The console has one route per complete command invocation."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app


@pytest.mark.parametrize(
    "command",
    (
        "consolidate",
        "dedun",
        "distill",
        "elaborate",
        "find",
        "fit",
        "log",
        "replace",
        "resolve",
        "summarize",
        "trace",
    ),
)
@pytest.mark.parametrize("retired_option", ("--plain", "--tui"))
def test_console_presentation_mode_options_are_rejected(
    command: str,
    retired_option: str,
) -> None:
    result = CliRunner().invoke(app, [command, retired_option])

    assert result.exit_code == 2
    assert f"No such option: {retired_option}" in result.output
