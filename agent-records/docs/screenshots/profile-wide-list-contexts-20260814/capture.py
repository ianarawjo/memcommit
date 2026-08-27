"""Capture Profile-wide List and Context browsers in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/profile-wide-list-contexts-20260814"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"
LEFT = "\x1b[D"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("profile_browser_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn(command: str, completion: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    shell_command = f"""
set -eu
printf 'LIVE PTY · '
stty size
printf 'PRE-BROWSE PROFILE/CURRENT\n'
mem profile current
before="$(python -c 'from memcommit.persistence.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
{command}
after="$(python -c 'from memcommit.persistence.store import MemoryStore; print(MemoryStore().current_context_name() or "<none>")')"
printf 'POST-BROWSE PROFILE/CURRENT\n'
mem profile current
test "$before" = "$after"
printf '{completion}\n'
""".strip()
    child = pexpect.spawn(
        "zsh",
        ["-lc", shell_command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _close_and_verify(
    child: pexpect.spawn,
    recorder: io.StringIO,
    *,
    completion: str,
    stem: str,
) -> None:
    child.send("q")
    child.expect(completion)
    child.expect(pexpect.EOF)
    _snapshot(recorder, stem)


def _capture_direct_list() -> None:
    child, recorder = _spawn(
        "mem list task-2/participant/proposal-workspace",
        "DIRECT LIST READ-ONLY VERIFIED · CURRENT CONTEXT UNCHANGED",
    )
    try:
        child.expect("List · task-2/participant/proposal-workspace")
        _BASE._pump(child)
        _snapshot(recorder, "01-list-entry-full-profile")

        child.send(LEFT)
        _BASE._pump(child)
        _snapshot(recorder, "02-list-hide-focused-memories")

        child.send(LEFT)
        _BASE._pump(child)
        _snapshot(recorder, "03-list-parent-navigation")

        _close_and_verify(
            child,
            recorder,
            completion="DIRECT LIST READ-ONLY VERIFIED",
            stem="04-list-close-read-only-verification",
        )
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_recursive_list() -> None:
    child, recorder = _spawn(
        "mem list -R task-2/advisor1",
        "RECURSIVE LIST READ-ONLY VERIFIED · CURRENT CONTEXT UNCHANGED",
    )
    try:
        child.expect("List · task-2/advisor1")
        _BASE._pump(child, seconds=1.0)
        _snapshot(recorder, "05-list-recursive-selected-subtree")
        _close_and_verify(
            child,
            recorder,
            completion="RECURSIVE LIST READ-ONLY VERIFIED",
            stem="06-list-recursive-close-verification",
        )
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_contexts() -> None:
    child, recorder = _spawn(
        "mem contexts",
        "CONTEXTS READ-ONLY VERIFIED · CURRENT CONTEXT UNCHANGED",
    )
    try:
        child.expect("Browse Contexts")
        _BASE._pump(child)
        _snapshot(recorder, "07-contexts-current-in-full-profile")

        child.send(DOWN)
        _BASE._pump(child)
        _snapshot(recorder, "08-contexts-readable-grant-focus")

        child.send(DOWN * 2)
        _BASE._pump(child)
        _snapshot(recorder, "09-contexts-query-only-orientation")

        _close_and_verify(
            child,
            recorder,
            completion="CONTEXTS READ-ONLY VERIFIED",
            stem="10-contexts-close-read-only-verification",
        )
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_direct_list()
    _capture_recursive_list()
    _capture_contexts()

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "52 180" in raw
    assert "38;" in raw
    assert any(
        "7" in codes.split(";") for codes in re.findall("\x1b\\[([0-9;]*)m", raw)
    )


if __name__ == "__main__":
    main()
