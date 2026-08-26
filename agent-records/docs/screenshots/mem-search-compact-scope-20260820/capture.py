"""Capture actual semantic Search with shared compact Scope."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shlex
import shutil
import time


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-search-compact-scope-20260820"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_search_scope_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _shell_command(argv: str) -> str:
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
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", _shell_command(shlex.join([executable, *arguments]))],
        cwd=str(ROOT),
        env=_BASE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    child.expect(_BASE.pexpect.EOF, timeout=20)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    return recorder.getvalue(), _BASE._snapshot(recorder, stem)


def _spawn_search(executable: str):
    arguments = [
        "search",
        "--context",
        "task-1/campus-wiki",
        "--recursive",
        "--limit",
        "5",
    ]
    environment = _BASE._environment()
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    recorder = _BASE._Recorder()
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
        timeout=45,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _assert_tui_color(raw: str) -> None:
    assert "52 180" not in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def _wait_for_results(child, recorder, *, timeout: float = 40.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _BASE._pump(child, seconds=0.45)
        plain = _BASE._plain(recorder.getvalue())
        if "RESULT(S) · SCOPE FROZEN" in plain:
            return plain
        if "SEARCH FAILED" in plain:
            raise AssertionError(plain)
    raise AssertionError("Timed out waiting for the actual Search provider turn.")


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    _before_raw, before = _capture_command(executable, ["status", "-s"], "_before")
    for suffix in (".png", ".txt", ".typescript"):
        (OUT / f"_before{suffix}").unlink()

    child, recorder = _spawn_search(executable)
    _BASE._pump(child, seconds=0.9)
    entry = _BASE._snapshot(recorder, "01-search-entry")
    assert "MEM SEARCH · INTERACTIVE" in entry
    assert "SCOPE" in entry
    assert "SEARCH · ENTER TO RUN" in entry
    assert "CONTEXTS · PROFILE" not in entry

    child.send("\x1b[Z" * 3)
    child.send("\r")
    _BASE._pump(child)
    browse = _BASE._snapshot(recorder, "02-browse-open")
    assert "CONTEXTS · PROFILE OR CHECKED READABLE CONTEXTS" in browse
    assert "ALL READABLE CONTEXTS" in browse

    child.send("\x1b[B")
    child.send(" ")
    _BASE._pump(child)
    excluded = _BASE._snapshot(recorder, "03-descendant-excluded")
    assert "1 ROOTS · 6 CONTEXTS" in excluded

    child.send(" ")
    child.send("\t")
    _BASE._pump(child)
    collapsed = _BASE._snapshot(recorder, "04-browse-closed")
    assert "1 ROOTS · 7 CONTEXTS" in collapsed
    assert "CONTEXTS · PROFILE OR CHECKED READABLE CONTEXTS" not in collapsed

    child.send("\t" * 3)
    child.send("construction zone")
    _BASE._pump(child)
    typed = _BASE._snapshot(recorder, "05-query-entered")
    assert "construction zone" in typed
    assert "Enter a query to search the selected scope." in typed

    child.send("\r")
    _BASE._pump(child, seconds=0.25)
    searching = _BASE._snapshot(recorder, "06-searching-frozen-scope")
    assert "SEARCHING" in searching
    assert "scope frozen" in searching

    complete_plain = _wait_for_results(child, recorder)
    complete = _BASE._snapshot(recorder, "07-complete-results")
    assert "1 [6a37c02f] Outdoor Parking Lot C" in complete
    assert (
        "[task-1/campus-wiki/temporary-parking · READ GRANT · MEMORY]"
        in complete
    )
    assert "…" not in complete
    assert "SAVE AS" in complete
    assert "RESULT(S) · SCOPE FROZEN" in complete_plain

    child.send(" ")
    _BASE._pump(child)
    checked = _BASE._snapshot(recorder, "08-first-result-checked")
    assert "CHECKED RESULT 1 · 1 TOTAL" in checked
    assert "SAVE 1 CHECKED AS COPY" in checked
    _assert_tui_color(recorder.getvalue())

    child.send("\x03")
    child.expect(_BASE.pexpect.EOF, timeout=10)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)

    _after_raw, after = _capture_command(
        executable,
        ["status", "-s"],
        "09-read-only-status-verification",
    )
    assert before == after


if __name__ == "__main__":
    main()
