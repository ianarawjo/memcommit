"""Capture the one-shot inline provider-free Find route."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-literal-find-inline-20260820"

_BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "mem_find_inline_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _capture_command(
    executable: str, arguments: list[str], stem: str
) -> tuple[str, str]:
    argv = shlex.join([executable, *arguments])
    command = f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; stty size; exec {argv}"
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_BASE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=10,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    child.expect(_BASE.pexpect.EOF, timeout=10)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    raw = recorder.getvalue()
    assert "52 180" in raw
    return raw, _BASE._snapshot(recorder, stem)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    _before_raw, before = _capture_command(
        executable,
        ["status", "-s"],
        "01-before-read-only-status",
    )
    find_raw, result = _capture_command(
        executable,
        ["find", "xxxxxx"],
        "02-inline-pattern-result",
    )
    _after_raw, after = _capture_command(
        executable,
        ["status", "-s"],
        "03-after-read-only-status",
    )

    assert "FIND RESULTS" in result
    assert "PATTERN · xxxxxx · LITERAL" in result
    assert "MATCHED 0 · OCCURRENCES 0" in result
    assert "(no matching Memories)" in result
    assert "MEM FIND" not in result
    assert "\x1b[?1049h" not in find_raw
    assert "\x1b[?1049l" not in find_raw
    assert before == after


if __name__ == "__main__":
    main()
