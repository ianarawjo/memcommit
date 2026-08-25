"""Capture Context Trace and one-shot Diff in a real 180x52 color PTY."""

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


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/context-history-one-shot-diff-20260825"
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
_SPEC = importlib.util.spec_from_file_location("context_history_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _run_setup(
    executable: str,
    environment: dict[str, str],
    *args: str,
) -> None:
    subprocess.run(
        [executable, *args],
        cwd=ROOT,
        env=environment,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _context_record(home: Path) -> dict[str, object]:
    path = home / ".mem/contexts/practice/rules/context.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _checkpoint_uid(home: Path, command: str) -> str:
    checkpoint_dir = home / ".mem/contexts/practice/rules/checkpoints"
    matches = []
    for path in checkpoint_dir.glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("command") == command:
            uid = value.get("uid")
            if isinstance(uid, str):
                matches.append(uid)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {command!r} checkpoint, found {matches!r}.")
    return matches[0]


def _store_digest(home: Path) -> str:
    digest = hashlib.sha256()
    store = home / ".mem"
    for path in sorted(item for item in store.rglob("*") if item.is_file()):
        digest.update(path.relative_to(store).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _spawn(
    command: list[str],
    *,
    environment: dict[str, str],
    completion: str,
    allow_failure: bool = False,
) -> tuple[pexpect.spawn, object]:
    joined = shlex.join(command)
    failure_guard = "set +e" if allow_failure else "set -e"
    status_check = (
        'test "$status" -eq 1'
        if allow_failure
        else 'test "$status" -eq 0'
    )
    shell_command = f"""
{failure_guard}
stty rows {ROWS} cols {COLUMNS} onlcr
printf 'LIVE COLOR PTY · '
stty size
printf 'PROFILE · ISOLATED CAPTURE · CURRENT · practice/rules\n'
printf '\n$ {joined}\n'
{joined}
command_exit_code=$?
{status_check.replace('$status', '$command_exit_code')}
printf '\n{completion} · EXIT %s · READ-ONLY\n' "$command_exit_code"
""".strip()
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


def _wait_for_screen(
    child: pexpect.spawn,
    recorder: object,
    expected: str,
    *,
    seconds: float = 10.0,
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _BASE._pump(child, seconds=0.1)
        visible = "\n".join(_BASE._screen(recorder.getvalue()).display)
        if expected in visible:
            return
    raise RuntimeError(f"Capture did not render expected text: {expected}")


def _complete_line_capture(
    executable: str,
    environment: dict[str, str],
    home: Path,
    *,
    args: tuple[str, ...],
    completion: str,
    stem: str,
    allow_failure: bool = False,
) -> str:
    before = _store_digest(home)
    child, recorder = _spawn(
        [executable, *args],
        environment=environment,
        completion=completion,
        allow_failure=allow_failure,
    )
    child.expect(completion)
    child.expect(pexpect.EOF)
    child.close()
    if not allow_failure:
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    assert _store_digest(home) == before
    _BASE._snapshot(recorder, stem)
    return recorder.getvalue()


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mem-context-history-capture-") as raw_home:
        home = Path(raw_home)
        environment = _environment(home)
        _run_setup(executable, environment, "init", "practice/rules")
        fruits = (
            "a is apple",
            "b is banana",
            "c is cherry",
            "d is date",
            "e is elderberry",
            "f is fig",
            "g is grape",
            "h is honeydew",
            "i is ita palm",
            "j is jujube",
        )
        for value in fruits[:3]:
            _run_setup(executable, environment, "add", value)
        record = _context_record(home)
        memories = record.get("memories")
        assert isinstance(memories, dict)
        cherry_uid = next(
            uid
            for uid, item in memories.items()
            if isinstance(uid, str)
            and isinstance(item, dict)
            and item.get("content") == "c is cherry"
        )
        _run_setup(
            executable,
            environment,
            "edit",
            cherry_uid,
            "c is clementine",
        )
        edit_checkpoint = _checkpoint_uid(home, "edit")
        for value in fruits[3:]:
            _run_setup(executable, environment, "add", value)

        before = _store_digest(home)
        child, recorder = _spawn(
            [executable, "trace", "practice/rules", "--tui", "--all"],
            environment=environment,
            completion="TRACE VIEWER CLOSED",
        )
        _wait_for_screen(child, recorder, "CONTEXT LINEAGE")
        entry = "\n".join(_BASE._screen(recorder.getvalue()).display)
        assert "LATEST FIRST" in entry
        assert "CHECKPOINT" in entry
        _BASE._snapshot(recorder, "01-context-trace-viewer-entry")

        child.send("\x1b[6~")
        _BASE._pump(child, seconds=0.7)
        scrolled = "\n".join(_BASE._screen(recorder.getvalue()).display)
        assert scrolled != entry
        _BASE._snapshot(recorder, "02-context-trace-viewer-scrolled")

        child.send("\x1b")
        child.expect("TRACE VIEWER CLOSED")
        child.expect(pexpect.EOF)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
        assert _store_digest(home) == before
        _BASE._snapshot(recorder, "03-context-trace-viewer-closed")
        viewer_raw = recorder.getvalue()
        assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", viewer_raw) is not None
        assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", viewer_raw) is not None

        plain_raw = _complete_line_capture(
            executable,
            environment,
            home,
            args=("trace", "practice/rules", "--plain", "--limit", "3"),
            completion="TRACE PLAIN VERIFIED",
            stem="04-context-trace-plain-verification",
        )
        assert "[CONTEXT]" in plain_raw and "SHOWING 3 OF" in plain_raw

        latest_raw = _complete_line_capture(
            executable,
            environment,
            home,
            args=("diff", "practice/rules"),
            completion="LATEST CHECKPOINT DIFF VERIFIED",
            stem="05-diff-latest-checkpoint-result",
        )
        assert "CHECKPOINT · THIS CHECKPOINT VS PREVIOUS" in latest_raw
        assert "REVISION DIFF" in latest_raw

        exact_raw = _complete_line_capture(
            executable,
            environment,
            home,
            args=("diff", edit_checkpoint),
            completion="EXACT CHECKPOINT DIFF VERIFIED",
            stem="06-diff-exact-checkpoint-result",
        )
        assert edit_checkpoint in exact_raw
        assert "c is cherry" in exact_raw and "c is clementine" in exact_raw

        typo_raw = _complete_line_capture(
            executable,
            environment,
            home,
            args=("diff", "pracitce/rules", "--stat"),
            completion="TYPO FAILURE VERIFIED",
            stem="07-diff-context-typo-suggestion",
            allow_failure=True,
        )
        assert "Did you mean 'practice/rules'?" in typo_raw
        assert "\x1b[" in typo_raw


if __name__ == "__main__":
    main()
