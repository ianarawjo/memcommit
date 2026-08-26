"""Capture terminal-independent Log output in an isolated real color PTY."""

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


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-static-log-20260820"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("static_log_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _write_isolated_mem_wrapper(directory: Path) -> Path:
    executable = directory / "mem"
    executable.write_text(
        f"""#!{sys.executable}
import os
from pathlib import Path

import memcommit.store as store_module

store_module.STORE_DIR = Path(os.environ["MEMCOMMIT_CAPTURE_STORE"])

from memcommit.cli import app

app()
""",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _environment(*, wrapper_dir: Path, store_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "PATH": str(wrapper_dir) + os.pathsep + environment["PATH"],
            "MEMCOMMIT_CAPTURE_STORE": str(store_dir),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _setup_fixture(environment: dict[str, str]) -> None:
    def run(*arguments: str) -> str:
        completed = subprocess.run(
            ("mem", *arguments),
            cwd=ROOT,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Fixture command failed ({shlex.join(('mem', *arguments))}): "
                f"{completed.stderr}"
            )
        return completed.stdout

    run("init", "archive")
    run("add", "Archived launch note.")
    run("checkpoint", "archive baseline")

    run("init", "notes")
    added = run("add", "Review the static Log contract.")
    match = re.search(r"\[([0-9a-f]{8,36})\]", added)
    if match is None:
        raise RuntimeError(f"Could not recover the fixture Memory UID: {added!r}")
    memory_uid = match.group(1)
    run("edit", memory_uid, "Review the colored static Log contract.")
    run("remove", memory_uid)
    run("undo")
    run("redo")

    run("init", "notes/embedded")
    run("add", "Embedded child note.")
    run("embed", "notes/embedded", "--into", "notes")
    run("switch", "notes")
    run("checkpoint", "reviewed semantic palette")


def _capture(
    arguments: tuple[str, ...],
    *,
    stem: str,
    environment: dict[str, str],
    expected_title: str,
) -> str:
    command = shlex.join(("mem", *arguments))
    shell_command = f"""
set -eu
stty rows {ROWS} cols {COLUMNS}
printf 'LIVE COLOR PTY · '
stty size
before="$(mem pwd)"
printf 'CURRENT CONTEXT · %s\n' "$before"
printf '\n$ {command}\n'
{command}
after="$(mem pwd)"
test "$before" = "$after"
printf '\nLOG COMPLETE · NO INTERACTIVE UI · CURRENT UNCHANGED · %s\n' "$after"
""".strip()
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", shell_command],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        child.expect("LOG COMPLETE · NO INTERACTIVE UI")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

    raw = recorder.getvalue()
    assert "52 180" in raw
    assert expected_title in raw
    assert "\x1b[1m" in raw
    assert "\x1b[?1049h" not in raw
    _BASE._snapshot(recorder, stem)
    return raw


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-static-log-capture-") as temporary:
        temporary_root = Path(temporary)
        wrapper_dir = temporary_root / "bin"
        wrapper_dir.mkdir()
        _write_isolated_mem_wrapper(wrapper_dir)
        environment = _environment(
            wrapper_dir=wrapper_dir,
            store_dir=temporary_root / "store",
        )
        _setup_fixture(environment)

        bare = _capture(
            ("log",),
            stem="01-current-context-static-log",
            environment=environment,
            expected_title="Log for 'notes':",
        )
        explicit = _capture(
            ("log", "--context", "archive"),
            stem="02-explicit-context-static-log",
            environment=environment,
            expected_title="Log for 'archive':",
        )

        assert "archive baseline" not in bare
        assert "archive baseline" in explicit
        assert "reviewed semantic palette" in bare
        assert "reviewed semantic palette" not in explicit

        # The static report keeps its textual contract while the trusted action
        # column gains the canonical semantic foregrounds.
        for rgb in (
            "138;173;244",  # create/add blue
            "238;212;159",  # embed yellow
            "166;218;149",  # edit green
            "237;135;150",  # remove red
            "245;169;127",  # undo/revert peach
            "183;189;248",  # redo lavender
            "201;173;147",  # history/manual checkpoint brown
        ):
            assert f"38;2;{rgb}" in bare, rgb


if __name__ == "__main__":
    main()
