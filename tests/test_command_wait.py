"""Contracts for synchronous command waiting and transient progress cleanup."""

from __future__ import annotations

from contextvars import ContextVar
import io
import sys
import threading

import pytest

from memcommit.adapters.console.terminal.components.command_wait import run_command_wait


class TerminalStream(io.StringIO):
    def __init__(self, *, tty: bool):
        super().__init__()
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty


def test_wait_executes_once_in_the_callers_context_and_returns_the_exact_result(
    monkeypatch,
):
    output = TerminalStream(tty=True)
    monkeypatch.setattr(sys, "stderr", output)
    attempt = ContextVar("command_wait_test_attempt", default=None)
    token = attempt.set("one-attempt")
    caller = threading.get_ident()
    result = object()
    calls = []

    def work(progress):
        calls.append((threading.get_ident(), attempt.get()))
        progress.update("analyzing relations", step=2)
        return result

    try:
        actual = run_command_wait(
            "COMPARE", "connecting provider", total=2, work=work,
            interactive=True, interval=60,
        )
    finally:
        attempt.reset(token)

    assert actual is result
    assert calls == [(caller, "one-attempt")]
    text = output.getvalue()
    assert "MEM COMPARE · 1/2 · CONNECTING PROVIDER" in text
    assert "MEM COMPARE · 2/2 · ANALYZING RELATIONS" in text
    assert text.endswith("\r")
    assert text.split("\r")[-2].strip() == ""


@pytest.mark.parametrize("failure", [RuntimeError("provider failed"), KeyboardInterrupt()])
def test_wait_propagates_the_same_failure_and_clears_progress(monkeypatch, failure):
    output = TerminalStream(tty=True)
    monkeypatch.setattr(sys, "stderr", output)
    calls = []

    def work(progress):
        calls.append("started")
        progress.update("checking result", step=2)
        raise failure

    with pytest.raises(type(failure)) as caught:
        run_command_wait(
            "AUDIT", "analyzing", total=2, work=work,
            interactive=True, interval=60,
        )

    assert caught.value is failure
    assert calls == ["started"]
    text = output.getvalue()
    assert "CHECKING RESULT" in text
    assert text.endswith("\r")
    assert text.split("\r")[-2].strip() == ""


@pytest.mark.parametrize(
    "stdin_tty,stdout_tty,stderr_tty,interactive,visible",
    [
        (True, True, True, None, True),
        (True, True, False, None, True),
        (True, False, True, None, True),
        (False, True, True, None, True),
        (False, False, False, None, False),
        (True, False, False, None, False),
        (False, False, False, True, True),
        (True, True, True, False, True),
        (True, True, False, False, False),
    ],
)
def test_wait_preserves_stream_detection_and_plain_stdout(
    monkeypatch, stdin_tty, stdout_tty, stderr_tty, interactive, visible,
):
    stdout = TerminalStream(tty=stdout_tty)
    stderr = TerminalStream(tty=stderr_tty)
    monkeypatch.setattr(sys, "stdin", TerminalStream(tty=stdin_tty))
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    def work(_progress):
        print("stable result")

    assert run_command_wait(
        "SEVER", "analyzing", total=1, work=work,
        interactive=interactive, interval=60,
    ) is None

    assert stdout.getvalue() == "stable result\n"
    assert bool(stderr.getvalue()) is visible


@pytest.mark.parametrize("options", [{"total": 0}, {"step": 2}, {"interval": 0}])
def test_invalid_progress_contract_fails_before_work(options):
    kwargs = {"total": 1, "interactive": False, **options}
    with pytest.raises(ValueError):
        run_command_wait(
            "FORGET", "analyzing",
            work=lambda _progress: pytest.fail("invalid progress must not execute work"),
            **kwargs,
        )
