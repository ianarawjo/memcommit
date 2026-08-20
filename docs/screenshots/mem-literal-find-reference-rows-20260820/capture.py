"""Capture compact literal Find rows and the complete interactive Viewer."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shlex
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-literal-find-reference-rows-20260820"

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_find_reference_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _shell_command(argv: str) -> str:
    # Verify the live geometry without printing ``52 180`` into product evidence.
    return "; ".join(
        (
            f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}",
            f"test \"$(stty size)\" = '{_BASE.ROWS} {_BASE.COLUMNS}'",
            f"exec {argv}",
        )
    )


def _capture_command(
    executable: str,
    arguments: list[str],
    stem: str,
) -> tuple[str, str]:
    argv = shlex.join([executable, *arguments])
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(argv)],
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
    raw = recorder.getvalue()
    assert "52 180" not in raw
    assert "\x1b[?1049h" not in raw
    assert "\x1b[?1049l" not in raw
    return raw, _BASE._snapshot(recorder, stem)


def _spawn_tui(executable: str):
    arguments = [
        "find",
        "construction",
        "--context",
        "task-1/campus-wiki",
        "--recursive",
        "--ignore-case",
        "--tui",
    ]
    recorder = _BASE._Recorder()
    environment = _BASE._environment()
    # pexpect does not answer terminal cursor-position reports. Real terminals
    # do; disable that probe so recorder limitations do not become screenshot
    # content in this primary-screen TUI.
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        [
            "-f",
            "-c",
            _shell_command(shlex.join([executable, *arguments])),
        ],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _assert_tui_color(raw: str) -> None:
    assert "52 180" not in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)
    for obsolete in (
        "05-tui-complete-reference-rows",
        "06-tui-second-row-focused",
        "07-tui-focused-row-copied",
        "08-read-only-status-verification",
        "06-tui-empty-range-staged",
    ):
        for suffix in (".png", ".txt", ".typescript"):
            (OUT / f"{obsolete}{suffix}").unlink(missing_ok=True)

    _before_raw, before = _capture_command(executable, ["status", "-s"], "_before")
    for suffix in (".png", ".txt", ".typescript"):
        (OUT / f"_before{suffix}").unlink()

    _normal_raw, normal = _capture_command(
        executable,
        [
            "find",
            "construction",
            "--context",
            "task-1/campus-wiki",
            "--recursive",
            "--ignore-case",
        ],
        "01-inline-two-reference-rows",
    )
    assert "MATCHED 2 · OCCURRENCES 2" in normal
    assert "SPANS" not in normal
    assert re.search(r"(?m)^1 \[[^]]+\] Outdoor Parking Lot C", normal)
    assert re.search(r"(?m)^2 \[[^]]+\] Do not infer the scope", normal)
    assert len(re.findall(r"\[[^]]+ m[0-9]+\]", normal)) == 2

    _broad_raw, broad = _capture_command(
        executable,
        [
            "find",
            "construction|entrance",
            "--context",
            "task-1/campus-wiki",
            "--recursive",
            "--regex",
            "--ignore-case",
            "--plain",
        ],
        "02-inline-bounded-preview",
    )
    assert "MATCHED 64 · OCCURRENCES 71 · SHOWING 1–10 OF 64" in broad
    assert "…" not in broad
    assert re.search(r"(?m)^10 \[", broad)
    assert re.search(r"(?m)^11 \[", broad) is None
    assert "54 more matches not shown" in broad
    assert "during regular opening hours in both the academic term and recess" in broad
    assert "that they used on a previous visit" in broad

    _empty_raw, empty = _capture_command(
        executable,
        [
            "find",
            "construction",
            "--context",
            "task-1/campus-wiki",
            "--ignore-case",
        ],
        "03-inline-empty-scope",
    )
    assert "SCANNED 0 · MATCHED 0 · OCCURRENCES 0" in empty
    assert "(scope contains no searchable Memories)" in empty

    child, recorder = _spawn_tui(executable)
    _BASE._pump(child, seconds=0.9)
    entry = _BASE._snapshot(recorder, "04-tui-entry")
    assert "MEM FIND" in entry
    assert "construction" in entry
    assert "SCOPE" in entry
    assert "FIND · ENTER PATTERN TO RUN" in entry
    assert "CONTEXT ·" in entry
    assert "CONTEXTS · PROFILE" not in entry

    child.send("\x1b[Z" * 4)
    child.send("\r")
    _BASE._pump(child)
    browse = _BASE._snapshot(recorder, "05-tui-browse-open")
    assert "CONTEXTS · PROFILE OR CHECKED READABLE CONTEXTS" in browse
    assert "ALL READABLE CONTEXTS" in browse

    child.send("\x1b[B")
    child.send(" ")
    _BASE._pump(child)
    excluded = _BASE._snapshot(recorder, "06-tui-descendant-excluded")
    assert "1 ROOTS · 6 CONTEXTS" in excluded

    child.send(" ")
    _BASE._pump(child)
    restored_range = _BASE._snapshot(recorder, "07-tui-range-restored")
    assert "1 ROOTS · 7 CONTEXTS" in restored_range

    child.send("\t")
    _BASE._pump(child)
    collapsed = _BASE._snapshot(recorder, "08-tui-browse-closed")
    assert "CONTEXTS · PROFILE OR CHECKED READABLE CONTEXTS" not in collapsed
    assert "[ BROWSE ]" in collapsed

    child.send("\t" * 4)
    child.send("\r")
    _BASE._pump(child, seconds=0.8)
    complete = _BASE._snapshot(recorder, "09-tui-complete-reference-rows")
    assert "COMPLETE · 2 MEMORIES · 2 OCCURRENCES" in complete
    assert re.search(r"1 \[[^]]+\] Outdoor Parking Lot C", complete)
    assert re.search(r"2 \[[^]]+\] Do not infer the scope", complete)
    assert "SPANS" not in complete

    child.send("\x1b[B")
    _BASE._pump(child)
    second = _BASE._snapshot(recorder, "10-tui-second-row-focused")
    assert re.search(r"2 \[[^]]+\] Do not infer the scope", second)

    child.send("y")
    _BASE._pump(child)
    copied = _BASE._snapshot(recorder, "11-tui-focused-row-copied")
    assert "COPIED FOCUSED MATCH" in copied
    _assert_tui_color(recorder.getvalue())

    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=10)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

    _after_raw, after = _capture_command(
        executable,
        ["status", "-s"],
        "12-read-only-status-verification",
    )
    assert before == after


if __name__ == "__main__":
    main()
