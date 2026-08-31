"""Capture Help command handoff and init-study-owned shell entry."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = (
    ROOT
    / "agent-records/docs/screenshots/help-init-study-shell-responsibility-20260828"
)
COLUMNS = 180
ROWS = 52
STUDY_NAME = "shell-owned-study"
PARENT_HISTORY_MARKER = "PARENT-HISTORY-MUST-NOT-ENTER-STUDY"

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "shell_responsibility_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _configure_isolated_profile_root(root: Path) -> None:
    """Redirect Profile and Store access without changing the process HOME."""

    import memcommit.application.operations.profiles.profile.config as profile_config
    import memcommit.configuration.config as config_module

    authoring = root / "authoring"
    control = root / "profile-control"
    profile_config.default_store_dir = lambda: authoring
    profile_config.profile_control_dir = lambda: control
    config_module.CONFIG_FILE = authoring / "config.json"


def _run_mem(arguments: list[str]) -> None:
    capture_root = Path(os.environ["MEMCOMMIT_CAPTURE_ROOT"])
    _configure_isolated_profile_root(capture_root)
    if os.environ.pop("MEMCOMMIT_CAPTURE_ANNOUNCE", None) == "1":
        columns, rows = os.get_terminal_size()
        print(f"CAPTURE PTY · {columns}x{rows}")
        print("\x1b[38;2;138;173;244m$\x1b[0m mem " + shlex.join(arguments))

    from memcommit.adapters.console.entrypoint import app

    sys.argv = ["mem", *arguments]
    app()


def _write_mem_wrapper(directory: Path) -> Path:
    wrapper = directory / "mem"
    wrapper.write_text(
        "#!/bin/zsh\n"
        'exec "$MEMCOMMIT_CAPTURE_PYTHON" "$MEMCOMMIT_CAPTURE_SCRIPT" '
        '--mem "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper


def _environment(capture_root: Path, wrapper_directory: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "PATH": str(wrapper_directory) + os.pathsep + environment["PATH"],
            "MEMCOMMIT_CAPTURE_ROOT": str(capture_root),
            "MEMCOMMIT_CAPTURE_PYTHON": sys.executable,
            "MEMCOMMIT_CAPTURE_SCRIPT": str(Path(__file__).resolve()),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _prepare(
    capture_root: Path,
    wrapper_directory: Path,
    arguments: tuple[str, ...],
) -> None:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--mem", *arguments],
        cwd=ROOT,
        env=_environment(capture_root, wrapper_directory),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"Preparation failed: mem {shlex.join(arguments)}\n"
            f"{result.stdout}\n{result.stderr}"
        )


def _spawn(
    capture_root: Path,
    wrapper_directory: Path,
    command: str,
) -> tuple[pexpect.spawn, _BASE._StreamRecorder]:
    recorder = _BASE._StreamRecorder()
    environment = _environment(capture_root, wrapper_directory)
    environment["MEMCOMMIT_CAPTURE_ANNOUNCE"] = "1"
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: _BASE._StreamRecorder, stem: str) -> str:
    _BASE._snapshot(recorder, stem)
    return "\n".join(_BASE._screen(recorder.getvalue()).display).rstrip() + "\n"


def _assert_actual_color_pty(raw: str, *, require_background: bool = True) -> None:
    if f"CAPTURE PTY · {COLUMNS}x{ROWS}" not in raw:
        raise RuntimeError("Capture did not verify the 180x52 PTY.")
    if re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is None:
        raise RuntimeError("Capture stream did not preserve foreground ANSI color.")
    if require_background and re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is None:
        raise RuntimeError("Capture stream did not preserve background ANSI color.")


def _capture_help(capture_root: Path, wrapper_directory: Path) -> None:
    _prepare(capture_root, wrapper_directory, ("init", "capture-context"))
    command = shlex.join(
        [sys.executable, str(Path(__file__).resolve()), "--mem", "help"]
    )
    child, recorder = _spawn(
        capture_root,
        wrapper_directory,
        f"stty rows {ROWS} cols {COLUMNS}; stty size; exec {command}",
    )
    _BASE._wait_for_visible(child, recorder, "CORE CONCEPTS")
    entry = _snapshot(recorder, "01-help-entry")
    assert "mem help · command inventory" in entry

    # A-Z → final operation → seven rows up selects Status. Enter expands its
    # Forms, and Down selects the explicit one-line Status form.
    child.send("\x1b[Z\x1b[C\t\x1b[F" + "\x1b[A" * 7 + "\r\x1b[B")
    _BASE._wait_for_visible(child, recorder, "mem status --short")
    selected = _snapshot(recorder, "02-status-form-selected")
    assert "FORM 2 · mem status --short" in selected

    child.send("\r")
    _BASE._wait_for_visible(child, recorder, "MEM HELP · EDIT SELECTED COMMAND")
    prefilled = _snapshot(recorder, "03-command-editor-prefilled")
    assert "mem status --short" in prefilled

    child.send("\x15--branch")
    _BASE._wait_for_visible(child, recorder, "mem status --branch")
    edited = _snapshot(recorder, "04-command-editor-edited")
    assert "THE OPERATION IS FIXED" in edited
    assert "mem status --branch" in edited

    child.send("\r")
    child.expect(pexpect.EOF, timeout=30)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    result = _snapshot(recorder, "05-child-command-result")
    assert "Profile:" in result
    assert "On context: capture-context" in result
    _assert_actual_color_pty(recorder.getvalue())


def _capture_study(capture_root: Path, wrapper_directory: Path) -> None:
    parent_history = capture_root / "parent-history"
    mem_command = shlex.join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--mem",
            "init-study",
            STUDY_NAME,
        ]
    )
    command = (
        f"stty rows {ROWS} cols {COLUMNS}; stty size; "
        f"fc -p {shlex.quote(str(parent_history))}; "
        f"print -s {shlex.quote(PARENT_HISTORY_MARKER)}; "
        f"{mem_command}; study_code=$?; "
        "print; print -r -- 'PARENT SHELL RESUMED'; "
        "print -r -- 'PARENT HISTORY:'; fc -l -2; exit $study_code"
    )
    child, recorder = _spawn(capture_root, wrapper_directory, command)
    _BASE._wait_for_visible(child, recorder, f"study:{STUDY_NAME}")
    entered = _snapshot(recorder, "06-init-study-shell-entered")
    assert f"Initialized Study run '{STUDY_NAME}'." in entered
    assert "Entering isolated Study shell" in entered

    child.send("fc -l -10\r")
    _BASE._pump(child, seconds=0.8)
    isolated = _snapshot(recorder, "07-study-history-isolated")
    assert PARENT_HISTORY_MARKER not in isolated
    assert "fc -l -10" in isolated

    child.send("mem status --short\r")
    _BASE._wait_for_visible(child, recorder, "practice [OWNED]")
    active = _snapshot(recorder, "08-study-command-active")
    assert "practice [OWNED]" in active

    child.send("exit\r")
    child.expect(pexpect.EOF, timeout=30)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    returned = _snapshot(recorder, "09-parent-shell-returned")
    assert "Exited Study shell · status 0." in returned
    assert "PARENT SHELL RESUMED" in returned
    assert PARENT_HISTORY_MARKER in returned
    # The line-oriented init-study and Status receipts define foreground
    # semantics only; unlike the Help TUI they do not own background fills.
    _assert_actual_color_pty(recorder.getvalue(), require_background=False)


def _write_interaction_log(help_root: Path, study_root: Path) -> None:
    (OUT / "interaction.log").write_text(
        "\n".join(
            (
                f"pty={COLUMNS}x{ROWS}",
                "TERM=xterm-256color",
                "COLORTERM=truecolor",
                "NO_COLOR=unset",
                f"help_profile_root={help_root}",
                "01 command=mem help keys=none mutation=none",
                "02 keys=Shift-Tab,Right,Tab,End,Up×7,Enter,Down mutation=none",
                "03 keys=Enter mutation=none",
                "04 text=Ctrl-U,--branch mutation=none",
                "05 keys=Enter command=mem status --branch mutation=none",
                f"study_profile_root={study_root}",
                f"06 command=mem init-study {STUDY_NAME} mutation=creates-and-selects-Study-Profile-pair",
                "07 command=fc -l -10 mutation=none",
                "08 command=mem status --short mutation=none",
                "09 command=exit mutation=none parent-history-visible-only-after-return",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.png", "*.txt", "*.typescript", "interaction.log"):
        for path in OUT.glob(pattern):
            path.unlink()

    help_root = Path(tempfile.mkdtemp(prefix="memcommit-help-handoff-"))
    study_root = Path(tempfile.mkdtemp(prefix="memcommit-study-shell-"))
    wrapper_directory = Path(tempfile.mkdtemp(prefix="memcommit-capture-bin-"))
    _write_mem_wrapper(wrapper_directory)
    _capture_help(help_root, wrapper_directory)
    _capture_study(study_root, wrapper_directory)
    _write_interaction_log(help_root, study_root)
    print(f"help_root={help_root}")
    print(f"study_root={study_root}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--mem":
        _run_mem(sys.argv[2:])
    else:
        main()
