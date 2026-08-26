"""Capture focused Context/Memory clipboard actions in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import sys

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "docs/screenshots/context-picker-clipboard-20260813"
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "context_picker_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _memory_rows(name: str):
    from memcommit.commands.shared.context_picker import ContextMemoryRow

    if name == "task-1/description":
        return (
            ContextMemoryRow(
                "memory 2db26309",
                "Imagine that you are a campus facilities coordinator responsible "
                "for maintaining a university organizational wiki used by campus "
                "members, visitors, and AI agents. The Main Building of the campus "
                "is under construction, and you have just finished collecting and "
                "verifying all resulting changes in your local work memory.",
            ),
        )
    return ()


def _run_success_child() -> None:
    from memcommit.commands.shared.context_picker import choose_context

    writes: list[str] = []
    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    receipt = choose_context(
        (
            "practice",
            "task-1",
            "task-1/description",
            "task-1/participant",
            "task-1/participant/construction-updates",
            "task-2",
            "task-3",
        ),
        current="task-1",
        virtual_names=(
            "task-1/campus-wiki",
            "task-1/campus-wiki/facilities",
        ),
        selectable_virtual_names={
            "task-1/campus-wiki",
            "task-1/campus-wiki/facilities",
        },
        virtual_annotations={
            "task-1/campus-wiki": (
                "READ GRANT · PERMISSIONS CREATE + READ + UPDATE + DELETE + "
                "QUERY + DERIVE + COMBINE + EXPORT"
            ),
            "task-1/campus-wiki/facilities": (
                "READ GRANT · PERMISSIONS CREATE + READ + UPDATE + DELETE + "
                "QUERY + DERIVE + COMBINE + EXPORT"
            ),
        },
        memory_loader=_memory_rows,
        initially_expand_selected=True,
        initially_show_memories=True,
        clipboard_writer=writes.append,
        title="Select a Context · semantic clipboard",
    )
    print(
        "PICKER CLOSED · NO CONTEXT SWITCH RECEIPT · NO STORE MUTATION"
        if receipt is None
        else f"UNEXPECTED RECEIPT {receipt!r}"
    )
    for index, text in enumerate(writes, start=1):
        print(
            f"CLIPBOARD WRITE {index} · PHYSICAL LINES {len(text.splitlines())} "
            f"· UTF-8 BYTES {len(text.encode('utf-8'))}"
        )
        for line_index, line in enumerate(text.splitlines(), start=1):
            print(f"  {line_index}: {line}")
    print(
        "MEMORY y/Y IDENTICAL · "
        + ("YES" if len(writes) == 4 and writes[2] == writes[3] else "NO")
    )


def _run_failure_child() -> None:
    from memcommit.clipboard import ClipboardError
    from memcommit.commands.shared.context_picker import choose_context

    attempts: list[str] = []

    def fail_copy(text: str) -> None:
        attempts.append(text)
        raise ClipboardError("simulated clipboard unavailable")

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    receipt = choose_context(
        ("alpha", "beta"),
        current="alpha",
        clipboard_writer=fail_copy,
        title="Select a Context · clipboard failure",
    )
    print(
        "FAILURE PICKER CLOSED · NO CONTEXT SWITCH RECEIPT · NO STORE MUTATION"
        if receipt is None
        else f"UNEXPECTED RECEIPT {receipt!r}"
    )
    print(f"FAILED WRITES {len(attempts)} · CLIPBOARD NOT REPLACED")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=12,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child, recorder = _spawn("success")
    try:
        child.expect("semantic clipboard")
        _BASE._settle(child)
        _snapshot(recorder, "01-context-entry")

        child.send("y")
        _BASE._settle(child)
        _snapshot(recorder, "02-context-item-copied")

        child.send("Y")
        _BASE._settle(child)
        _snapshot(recorder, "03-context-visible-branch-copied")

        child.send(DOWN + DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "04-memory-focused")

        child.send("y")
        _BASE._settle(child)
        _snapshot(recorder, "05-memory-y-copied")

        child.send("Y")
        _BASE._settle(child)
        _snapshot(recorder, "06-memory-uppercase-y-copied")

        child.send("q")
        child.expect("MEMORY y/Y IDENTICAL")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-read-only-copy-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("failure")
    try:
        child.expect("clipboard failure")
        _BASE._settle(child)
        child.send("y")
        _BASE._settle(child)
        _snapshot(recorder, "08-copy-failed")

        child.send("q")
        child.expect("CLIPBOARD NOT REPLACED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-failure-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;" in raw
    assert any(
        "7" in codes.split(";") for codes in re.findall("\x1b\\[([0-9;]*)m", raw)
    )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        if sys.argv[2] == "success":
            _run_success_child()
        elif sys.argv[2] == "failure":
            _run_failure_child()
        else:
            raise SystemExit(f"unknown child kind: {sys.argv[2]}")
    else:
        main()
