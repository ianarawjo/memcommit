"""Capture default Trace viewers and the piped fallback in a 180x52 color PTY."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/trace-default-viewer-20260831"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("trace_default_viewer_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment(task_home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(task_home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _run_setup(executable: str, environment: dict[str, str], *args: str) -> None:
    subprocess.run(
        [executable, *args],
        cwd=ROOT,
        env=environment,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _context_record(task_home: Path) -> dict[str, object]:
    path = task_home / ".mem/contexts/practice/rules/context.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _store_digest(task_home: Path) -> str:
    digest = hashlib.sha256()
    store = task_home / ".mem"
    for path in sorted(item for item in store.rglob("*") if item.is_file()):
        digest.update(path.relative_to(store).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _spawn_shell(
    shell_command: str,
    *,
    environment: dict[str, str],
) -> tuple[pexpect.spawn, object]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", shell_command],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _spawn_viewer(
    command: list[str],
    *,
    environment: dict[str, str],
    completion: str,
) -> tuple[pexpect.spawn, object]:
    joined = shlex.join(command)
    shell_command = f"""
set -e
stty rows {ROWS} cols {COLUMNS} onlcr
printf 'LIVE COLOR PTY · '
stty size
printf 'PROFILE · ISOLATED CAPTURE · CURRENT · practice/rules\n'
printf '\n$ {joined}\n'
{joined}
command_exit_code=$?
test "$command_exit_code" -eq 0
printf '\n{completion} · EXIT %s · READ-ONLY\n' "$command_exit_code"
""".strip()
    return _spawn_shell(shell_command, environment=environment)


def _wait_for_screen(
    child: pexpect.spawn,
    recorder: object,
    expected: str,
    *,
    seconds: float = 10.0,
) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _BASE._pump(child, seconds=0.1)
        visible = "\n".join(_BASE._screen(recorder.getvalue()).display)
        if expected in visible:
            return visible
    raise RuntimeError(f"Capture did not render expected text: {expected}")


def _capture_viewer(
    command: list[str],
    *,
    environment: dict[str, str],
    task_home: Path,
    expected: str,
    completion: str,
    entry_stem: str,
    scrolled_stem: str,
    closed_stem: str,
) -> str:
    before = _store_digest(task_home)
    child, recorder = _spawn_viewer(
        command,
        environment=environment,
        completion=completion,
    )
    entry = _wait_for_screen(child, recorder, expected)
    assert "TRACE REPORT" in entry
    assert "read-only" in entry
    _BASE._snapshot(recorder, entry_stem)

    child.send("\x1b[6~")
    _BASE._pump(child, seconds=0.7)
    scrolled = "\n".join(_BASE._screen(recorder.getvalue()).display)
    assert scrolled != entry
    _BASE._snapshot(recorder, scrolled_stem)

    child.send("\x1b")
    child.expect(completion)
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    assert _store_digest(task_home) == before
    _BASE._snapshot(recorder, closed_stem)
    raw = recorder.getvalue()
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    return raw


def _capture_piped_fallback(
    executable: str,
    *,
    environment: dict[str, str],
    task_home: Path,
    memory_uid: str,
) -> str:
    before = _store_digest(task_home)
    command = [
        executable,
        "trace",
        memory_uid,
        "--context",
        "practice/rules",
        "--limit",
        "3",
    ]
    joined = shlex.join(command)
    completion = "PIPED TRACE VERIFIED"
    shell_command = f"""
set -e
stty rows {ROWS} cols {COLUMNS} onlcr
printf 'LIVE COLOR PTY · '
stty size
printf 'PROFILE · ISOLATED CAPTURE · CURRENT · practice/rules\n'
printf '\n$ {joined} | sed -n 1,24p\n'
{joined} | sed -n '1,24p'
printf '\n{completion} · EXIT 0 · STORE DIGEST UNCHANGED\n'
""".strip()
    child, recorder = _spawn_shell(shell_command, environment=environment)
    child.expect(completion)
    child.expect(pexpect.EOF)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    assert _store_digest(task_home) == before
    _BASE._snapshot(recorder, "07-piped-trace-static-read-only")
    raw = recorder.getvalue()
    assert "TRACE · practice/rules" in raw
    assert "SHOWING 3 OF" in raw
    assert "TRACE REPORT" not in raw
    return raw


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mem-trace-viewer-capture-") as raw_home:
        task_home = Path(raw_home)
        environment = _environment(task_home)
        _run_setup(executable, environment, "init", "practice/rules")
        _run_setup(
            executable,
            environment,
            "add",
            "Trace subject version 00 keeps one deliberately long sentence for wrapped Viewer evidence.",
        )
        record = _context_record(task_home)
        memories = record.get("memories")
        assert isinstance(memories, dict) and len(memories) == 1
        memory_uid = next(iter(memories))
        for revision in range(1, 15):
            _run_setup(
                executable,
                environment,
                "edit",
                memory_uid,
                f"Trace subject version {revision:02d} keeps one deliberately long sentence for wrapped Viewer evidence.",
            )
        for content in (
            "A separate policy Memory remains independent.",
            "A second supporting Memory makes Context lineage visibly mixed.",
            "A final note keeps the newest Context operation distinct.",
        ):
            _run_setup(executable, environment, "add", content)

        _capture_viewer(
            [executable, "trace", "practice/rules", "--all"],
            environment=environment,
            task_home=task_home,
            expected="CONTEXT LINEAGE",
            completion="CONTEXT TRACE VIEWER CLOSED",
            entry_stem="01-context-trace-viewer-entry",
            scrolled_stem="02-context-trace-viewer-scrolled",
            closed_stem="03-context-trace-viewer-closed",
        )
        _capture_viewer(
            [
                executable,
                "trace",
                memory_uid,
                "--context",
                "practice/rules",
                "--all",
            ],
            environment=environment,
            task_home=task_home,
            expected="LINEAGE",
            completion="MEMORY TRACE VIEWER CLOSED",
            entry_stem="04-memory-trace-viewer-entry",
            scrolled_stem="05-memory-trace-viewer-scrolled",
            closed_stem="06-memory-trace-viewer-closed",
        )
        _capture_piped_fallback(
            executable,
            environment=environment,
            task_home=task_home,
            memory_uid=memory_uid,
        )


if __name__ == "__main__":
    main()
