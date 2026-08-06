"""zsh command-prefill integration and its CLI transport boundary."""
from __future__ import annotations

import errno
import os
import pty
import shutil
import subprocess

import pytest
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.commands.help_inventory as help_inventory
from memcommit.cli import app
from memcommit.commands.shell_init import render_zsh_init


runner = CliRunner(mix_stderr=False)


def test_shell_init_prints_valid_zsh_without_editing_files():
    result = runner.invoke(app, ["shell-init", "zsh"])

    assert result.exit_code == 0
    assert "command mem help --emit-selection" in result.output
    assert 'print -rz -- "${_mem_selected} "' in result.output
    assert 'command mem "$@"' in result.output

    zsh = shutil.which("zsh")
    if zsh is not None:
        checked = subprocess.run(
            [zsh, "-n"],
            input=result.output,
            text=True,
            capture_output=True,
            check=False,
        )
        assert checked.returncode == 0, checked.stderr


def test_shell_init_rejects_unsupported_shell():
    result = runner.invoke(app, ["shell-init", "bash"])

    assert result.exit_code == 1
    assert "unsupported shell 'bash'" in result.stderr


def test_emit_selection_reserves_stdout_for_one_command(monkeypatch):
    monkeypatch.setattr(
        help_inventory,
        "_selection_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        help_inventory,
        "_selection_output",
        DummyOutput,
    )
    monkeypatch.setattr(
        help_inventory,
        "run_help_selector",
        lambda entries, **kwargs: help_inventory.HelpSelection(
            command_name="impact",
            command_line="mem impact --from [source] --to [target]",
        ),
    )

    result = runner.invoke(app, ["help", "--emit-selection"])

    assert result.exit_code == 0
    assert result.output == "mem impact --from [source] --to [target]\n"


def test_emit_selection_cancel_emits_nothing(monkeypatch):
    monkeypatch.setattr(
        help_inventory,
        "_selection_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        help_inventory,
        "_selection_output",
        DummyOutput,
    )
    monkeypatch.setattr(
        help_inventory,
        "run_help_selector",
        lambda entries, **kwargs: None,
    )

    result = runner.invoke(app, ["help", "--emit-selection"])

    assert result.exit_code == 0
    assert result.output == ""


def test_emit_selection_requires_a_terminal():
    result = runner.invoke(app, ["help", "--emit-selection"])

    assert result.exit_code == 1
    assert "requires an interactive terminal" in result.stderr


@pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh is unavailable")
@pytest.mark.parametrize(
    "selected_command",
    (
        'mem add "[memory]"',
        "mem checkpoint",
        'mem checkpoint "[message]"',
        'mem query [query_view]#[memory_handle] "[question]"',
    ),
)
def test_generated_wrapper_prefills_and_delegates(tmp_path, selected_command):
    executable = tmp_path / "mem"
    executable.write_text(
        """#!/bin/zsh
if [[ $1 == help && $2 == --emit-selection ]]; then
  print -r -- "$MEM_TEST_SELECTION"
else
  print -r -- "delegated:$*"
fi
"""
    )
    executable.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment['PATH']}"
    environment["MEMCOMMIT_ZSH_INIT"] = render_zsh_init()
    environment["MEM_TEST_SELECTION"] = selected_command
    script = """\
eval "$MEMCOMMIT_ZSH_INIT"
mem help
IFS= read -rz selected
print -r -- "buffer=$selected"
mem status
"""

    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        [shutil.which("zsh"), "-f", "-ic", script],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=environment,
        close_fds=True,
    )
    os.close(slave_fd)
    chunks: list[bytes] = []
    try:
        while True:
            try:
                chunk = os.read(master_fd, 4096)
            except OSError as error:
                if error.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(master_fd)
    returncode = process.wait(timeout=5)
    output = b"".join(chunks).decode(errors="replace").replace("\r", "")

    assert returncode == 0, output
    assert f"buffer={selected_command} " in output
    assert "delegated:status" in output
