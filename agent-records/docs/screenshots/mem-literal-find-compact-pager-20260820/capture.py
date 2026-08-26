"""Capture Find's compact primary-screen result pager at 180 by 52."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-literal-find-compact-pager-20260820"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_find_pager_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT

PROMPT = "(base) KimMunyeong@MacBook-Pro-3 memcommit % "


def _shell_command(argv: str) -> str:
    return "; ".join(
        (
            f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}",
            f"test \"$(stty size)\" = '{_BASE.ROWS} {_BASE.COLUMNS}'",
            f"exec {argv}",
        )
    )


def _capture_command(executable: str, arguments: list[str], stem: str) -> str:
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(shlex.join([executable, *arguments]))],
        cwd=str(ROOT),
        env=_BASE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    child.expect(_BASE.pexpect.EOF, timeout=15)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    return _BASE._snapshot(recorder, stem)


def _spawn_shell(executable: str):
    environment = _BASE._environment()
    # pexpect records the PTY but cannot answer cursor-position probes. This
    # keeps that harness limitation out of the application evidence.
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f"],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    # In zsh prompt syntax ``%%`` emits one literal percent sign.
    quoted_prompt = shlex.quote(PROMPT.replace("%", "%%"))
    child.sendline(
        f"export PS1={quoted_prompt}; export RPS1=''; "
        f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; "
        f"test \"$(stty size)\" = '{_BASE.ROWS} {_BASE.COLUMNS}'; clear"
    )
    child.expect_exact(PROMPT)
    command = shlex.join(
        [
            Path(executable).name,
            "find",
            "construction|entrance",
            "--context",
            "task-1/campus-wiki",
            "--recursive",
            "--regex",
            "--ignore-case",
        ]
    )
    child.sendline(command)
    return child, recorder, command


def _assert_color_primary_screen(raw: str) -> None:
    assert "doesn't support cursor position requests" not in raw
    assert "\x1b[?1049h" not in raw
    assert "\x1b[?1049l" not in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    before = _capture_command(executable, ["status", "-s"], "_before")
    for suffix in (".png", ".txt", ".typescript"):
        (OUT / f"_before{suffix}").unlink()

    child, recorder, command = _spawn_shell(executable)
    _BASE._pump(child, seconds=0.9)
    entry = _BASE._snapshot(recorder, "01-first-page")
    assert command in entry
    assert "SHOWING 1–10 OF 64" in entry
    assert "…" not in entry
    assert re.search(r"(?m)^1 \[[^]]+\] ", entry)
    assert re.search(r"\[[^]]+ m[0-9]+\]", entry)
    assert re.search(r"(?m)^10 \[", entry)
    assert re.search(r"(?m)^11 \[", entry) is None
    assert "during regular opening hours in both the academic term and recess" in entry

    child.send("\x1b[B")
    _BASE._pump(child)
    second = _BASE._snapshot(recorder, "02-second-row-focused")
    assert "SHOWING 1–10 OF 64" in second
    assert "…" not in second
    assert re.search(r"(?m)^2 \[", second)

    child.send("\x1b[C")
    _BASE._pump(child)
    page_two = _BASE._snapshot(recorder, "03-second-page")
    assert "SHOWING 11–20 OF 64" in page_two
    assert "…" not in page_two
    assert re.search(r"(?m)^11 \[", page_two)
    assert re.search(r"(?m)^20 \[", page_two)

    child.send("\x1b[F")
    _BASE._pump(child)
    final_page = _BASE._snapshot(recorder, "04-final-page")
    assert "SHOWING 61–64 OF 64" in final_page
    assert "…" not in final_page
    assert re.search(r"(?m)^61 \[", final_page)
    assert re.search(r"(?m)^64 \[", final_page)

    child.send("q")
    child.expect_exact(PROMPT, timeout=10)
    closed = _BASE._snapshot(recorder, "05-closed-to-shell")
    assert "SHOWING 61–64 OF 64" in closed
    assert closed.rstrip().endswith(PROMPT.rstrip())
    _assert_color_primary_screen(recorder.getvalue())

    child.sendline("exit")
    child.expect(_BASE.pexpect.EOF, timeout=10)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

    after = _capture_command(
        executable,
        ["status", "-s"],
        "06-read-only-status-verification",
    )
    assert before == after


if __name__ == "__main__":
    main()
