"""Capture real task-data and edge-case executions of inline Find."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-literal-find-edge-cases-20260820"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_find_edge_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _capture_command(
    executable: str,
    arguments: list[str],
    stem: str,
    *,
    expected_exit: int = 0,
) -> tuple[str, str]:
    argv = shlex.join([executable, *arguments])
    displayed = "$ " + shlex.join(["mem", *arguments])
    command = "; ".join(
        (
            f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}",
            "stty size",
            f"print -r -- {shlex.quote(displayed)}",
            f"exec {argv}",
        )
    )
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
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
    assert child.exitstatus == expected_exit, (child.exitstatus, child.signalstatus)
    raw = recorder.getvalue()
    assert "52 180" in raw
    return raw, _BASE._snapshot(recorder, stem)


def _assert_inline(raw: str) -> None:
    assert "\x1b[?1049h" not in raw
    assert "\x1b[?1049l" not in raw


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    _before_raw, before = _capture_command(executable, ["status", "-s"], "_before")
    for suffix in (".png", ".txt", ".typescript"):
        (OUT / f"_before{suffix}").unlink()

    normal_raw, normal = _capture_command(
        executable,
        ["find", "Memory", "--ignore-case"],
        "01-normal-ignore-case-match",
    )
    assert "MATCHED 1 · OCCURRENCES 3" in normal
    assert "AI agent memory" in normal

    name_raw, name_result = _capture_command(
        executable,
        [
            "find",
            "task",
            "--context",
            "task-1/campus-wiki",
            "--recursive",
            "--ignore-case",
        ],
        "02-context-name-is-not-content",
    )
    assert "SCANNED 300 · MATCHED 0 · OCCURRENCES 0" in name_result

    direct_raw, direct = _capture_command(
        executable,
        [
            "find",
            "construction",
            "--context",
            "task-1/campus-wiki",
            "--ignore-case",
        ],
        "03-direct-parent-has-no-memory-source",
    )
    assert "SCANNED 0 · MATCHED 0 · OCCURRENCES 0" in direct

    recursive_raw, recursive = _capture_command(
        executable,
        [
            "find",
            "construction",
            "--context",
            "task-1/campus-wiki",
            "--recursive",
            "--ignore-case",
        ],
        "04-recursive-scope-finds-embedded-content",
    )
    assert "SCANNED 300 · MATCHED 2 · OCCURRENCES 2" in recursive
    assert "temporary-parking" in recursive
    assert "facility-updates" in recursive

    literal_raw, literal = _capture_command(
        executable,
        [
            "find",
            ".*",
            "--context",
            "task-1/campus-wiki",
            "--recursive",
        ],
        "05-regex-metacharacters-remain-literal",
    )
    assert "PATTERN · .* · LITERAL" in literal
    assert "MATCHED 0 · OCCURRENCES 0" in literal

    broad_raw, broad = _capture_command(
        executable,
        [
            "find",
            "construction|entrance",
            "--context",
            "task-1/campus-wiki",
            "--recursive",
            "--regex",
            "--ignore-case",
        ],
        "06-broad-explicit-regex-floods-terminal",
    )
    assert "MATCHED 64 · OCCURRENCES 71" in broad_raw
    assert broad_raw.count("\n") > _BASE.ROWS
    assert "[64]" in broad

    invalid_raw, invalid = _capture_command(
        executable,
        ["find", "^|", "--regex"],
        "07-zero-width-regex-rejected",
        expected_exit=1,
    )
    assert "must consume at least one character" in invalid

    _after_raw, after = _capture_command(
        executable,
        ["status", "-s"],
        "08-read-only-status-verification",
    )
    assert before.replace("$ mem status -s", "") == after.replace("$ mem status -s", "")

    for raw in (
        normal_raw,
        name_raw,
        direct_raw,
        recursive_raw,
        literal_raw,
        broad_raw,
        invalid_raw,
    ):
        _assert_inline(raw)


if __name__ == "__main__":
    main()
