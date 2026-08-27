"""Capture Reference and Edit's shared direct-Memory selector flows."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import shlex
from types import SimpleNamespace
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/direct-memory-selector-actions-20260820"
sys.path.insert(0, str(ROOT / "src"))
COLUMNS = 180
ROWS = 52
UP = "\x1b[A"
DOWN = "\x1b[B"
RIGHT = "\x1b[C"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-add-tui-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("direct_memory_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS
_BASE._BASE.OUT = OUT
_BASE._BASE.COLUMNS = COLUMNS
_BASE._BASE.ROWS = ROWS


def _configure_isolated_store(store_root: Path) -> None:
    _BASE._configure_isolated_store(store_root)

    def empty_navigation(_store):
        return SimpleNamespace(names=(), annotations={})

    import memcommit.adapters.interfaces.tui.operations.edit.adapter as edit_adapter

    edit_adapter.freeze_granted_context_navigation = empty_navigation


def _initialize_reference() -> None:
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "Exact Source wording.")
    target = ops.init("target")
    store.save(source)
    store.save(target)
    store.set_current("target")


def _initialize_edit() -> None:
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    context = ops.init("notes")
    ops.add(context, "Original first line.\nOriginal second line.")
    store.save(context)
    store.set_current("notes")


def _run_child(kind: str) -> None:
    from memcommit.adapters.console.entrypoint import app
    from memcommit.context import Memory, MemoryRef
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(
        prefix="mem-direct-selector-capture-"
    ) as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        if kind.startswith("reference"):
            _initialize_reference()
            app(args=["reference"], prog_name="mem", standalone_mode=False)
            if not kind.endswith("cancel"):
                print("REFERENCE VERIFICATION GATE · PRESS V")
                sys.stdin.read(1)
            store = MemoryStore()
            target = store.load_direct("target")
            snapshots = [
                item for item in target.iter_items() if isinstance(item, MemoryRef)
            ]
            if kind.endswith("cancel"):
                print(
                    "REFERENCE CANCEL VERIFIED · TARGET ITEMS "
                    f"{len(target.memories)} · REFERENCE CHECKPOINTS "
                    f"{sum(item['command'] == 'reference' for item in store.list_checkpoints('target'))}"
                )
            else:
                assert len(snapshots) == 1 and snapshots[0].target is not None
                print(
                    "REFERENCE READ-ONLY VERIFICATION · TARGET SNAPSHOTS 1 · "
                    f"CONTENT {snapshots[0].target.content!r} · SOURCE UNCHANGED"
                )
            return
        _initialize_edit()
        app(args=["edit"], prog_name="mem", standalone_mode=False)
        if not kind.endswith("cancel"):
            print("EDIT VERIFICATION GATE · PRESS V")
            sys.stdin.read(1)
        store = MemoryStore()
        context = store.load_direct("notes")
        memories = [item for item in context.iter_items() if isinstance(item, Memory)]
        checkpoints = [
            item
            for item in store.list_checkpoints("notes")
            if item["command"] == "edit"
        ]
        if kind.endswith("cancel"):
            print(
                "EDIT CANCEL VERIFIED · CONTENT "
                f"{memories[0].content!r} · EDIT CHECKPOINTS {len(checkpoints)}"
            )
        else:
            print(
                "EDIT READ-ONLY VERIFICATION · CONTENT "
                f"{memories[0].content!r} · EDIT CHECKPOINTS {len(checkpoints)}"
            )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_reference() -> None:
    child, recorder = _spawn("reference")
    try:
        child.expect("SNAPSHOT UNIT")
        child.send(RIGHT)
        _BASE._BASE._settle(child)
        _snapshot(recorder, "01-reference-entry")

        child.send("\t")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "02-reference-source-open")

        child.send(DOWN + "\r")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "03-reference-memory-selected")

        child.send("\t")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "04-reference-target")

        child.send("\t")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "05-reference-exact-command")

        child.send("\r")
        child.expect("REFERENCE VERIFICATION GATE")
        _snapshot(recorder, "06-reference-success")

        child.send("v\r")
        child.expect("REFERENCE READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-reference-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("reference-cancel")
    try:
        child.expect("SNAPSHOT UNIT")
        child.send("\x1b")
        child.expect("REFERENCE CANCEL VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-reference-cancel-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_edit() -> None:
    from memcommit.adapters.interfaces.console.text import display_escape_text

    child, recorder = _spawn("edit")
    try:
        child.expect("MEMORY · DIRECTLY OWNED")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "09-edit-entry")

        child.send(DOWN + "\r")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "10-edit-memory-selected")

        original = "Original first line.\nOriginal second line."
        child.send("\t" + "\x7f" * len(original))
        child.send("Revised first line.\rRevised second line.")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "11-edit-multiline-content")

        child.send("\t")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "12-edit-exact-command")

        child.send("\x15mem delete target")
        _BASE._BASE._settle(child)
        _snapshot(recorder, "13-edit-command-invalid")

        review_text = (OUT / "12-edit-exact-command.txt").read_text(
            encoding="utf-8"
        )
        match = re.search(r"mem edit ([0-9a-f-]{36}) ", review_text)
        assert match is not None
        command_content = "Command-authored first line.\nCommand-authored second line."
        command = shlex.join(
            (
                "mem",
                "edit",
                match.group(1),
                display_escape_text(command_content),
                "--context",
                "notes",
            )
        )
        child.send("\x15" + command.removeprefix("mem edit "))
        _BASE._BASE._settle(child)
        _snapshot(recorder, "14-edit-command-updates-content")

        child.send("\r")
        child.expect("EDIT VERIFICATION GATE")
        _snapshot(recorder, "15-edit-success")

        child.send("v\r")
        child.expect("EDIT READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "16-edit-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("edit-cancel")
    try:
        child.expect("MEMORY · DIRECTLY OWNED")
        child.send("\x1b")
        child.expect("EDIT CANCEL VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "17-edit-cancel-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_reference()
    _capture_edit()
    edit_review = (OUT / "12-edit-exact-command.txt").read_text(encoding="utf-8")
    assert "┃ PROPOSED COMMAND ┃" in edit_review
    assert "PRESS ENTER TO APPLY THE REVIEWED EDIT" in edit_review
    assert "TO DO" not in edit_review
    assert "EFFECTS · ONE COMMAND" not in edit_review
    assert "Approval applies only" not in edit_review
    invalid_review = (OUT / "13-edit-command-invalid.txt").read_text(
        encoding="utf-8"
    )
    assert "PROPOSED COMMAND · INVALID" in invalid_review
    assert (
        "Editable Edit commands require MEMORY_SELECTOR CONTENT "
        "--context CONTEXT."
    ) in invalid_review
    assert "mem edit mem delete target" in invalid_review
    assert "FIX THE RED COMMAND BEFORE APPLY" in invalid_review
    assert "Revised first line." in invalid_review
    assert "Revised second line." in invalid_review
    invalid_raw = (OUT / "13-edit-command-invalid.typescript").read_text(
        encoding="utf-8"
    )
    assert any(
        red_ansi in invalid_raw
        for red_ansi in ("38;2;237;135;150", "38;5;210")
    )
    synchronized_review = (
        OUT / "14-edit-command-updates-content.txt"
    ).read_text(encoding="utf-8")
    assert "Command-authored first line." in synchronized_review
    assert "Command-authored second line." in synchronized_review
    assert "PROPOSED COMMAND · INVALID" not in synchronized_review
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "\x1b[" in raw
    assert "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
