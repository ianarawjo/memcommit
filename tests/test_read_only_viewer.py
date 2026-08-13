"""Contracts for the common framed report Viewer."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.interfaces.tui.viewers.read_only import run_read_only_viewer


def test_read_only_viewer_supports_shared_navigation_and_back_close():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[6~\x1b[F\x7f")
        run_read_only_viewer(
            "first\nsecond\nthird\nfourth",
            title="RATIONALE REPORT",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
