"""Study shell lifecycle owned by the init-study command."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import click
import typer

import memcommit.adapters.console.commands.system_study_tools.init_study.study_shell as study_shell


def _tty_stream():
    return SimpleNamespace(isatty=lambda: True)


def test_nested_study_invocation_does_not_open_another_shell(monkeypatch) -> None:
    monkeypatch.setattr(study_shell.sys, "stdin", _tty_stream())
    monkeypatch.setattr(study_shell.sys, "stdout", _tty_stream())
    monkeypatch.setattr(study_shell.sys, "stderr", _tty_stream())

    assert study_shell.should_enter_study_shell(environment={})
    assert not study_shell.should_enter_study_shell(
        environment={study_shell.STUDY_SHELL_ENV: "1"}
    )


def test_study_shell_uses_disposable_zsh_configuration_and_history() -> None:
    calls = []

    def fake_runner(argv, *, check, env):
        calls.append((argv, check, env))
        return subprocess.CompletedProcess(argv, 0)

    exit_code = study_shell.run_study_shell(
        "coffee-run",
        shell_path="/bin/zsh",
        runner=fake_runner,
        environment={"PATH": "/usr/bin:/bin"},
    )

    assert exit_code == 0
    argv, check, environment = calls[0]
    assert argv == ("/bin/zsh", "-d", "-f", "-i")
    assert check is False
    assert environment[study_shell.STUDY_SHELL_ENV] == "1"
    assert environment[study_shell.STUDY_PROFILE_ENV] == "coffee-run"
    assert environment["SAVEHIST"] == "0"
    assert environment["HISTFILE"].endswith("/history")
    assert environment["ZDOTDIR"] == environment["HISTFILE"].removesuffix("/history")


def test_study_shell_is_scheduled_for_root_context_close(monkeypatch) -> None:
    events = []
    monkeypatch.setattr(study_shell.shutil, "which", lambda _name: "/bin/zsh")

    def fake_runner(argv, *, check, env):
        events.append((argv, env[study_shell.STUDY_PROFILE_ENV]))
        return subprocess.CompletedProcess(argv, 0)

    context = typer.Context(click.Command("init-study"))
    study_shell.schedule_study_shell(
        context,
        "coffee-run",
        runner=fake_runner,
    )
    assert events == []

    context.close()

    assert events == [(("/bin/zsh", "-d", "-f", "-i"), "coffee-run")]
