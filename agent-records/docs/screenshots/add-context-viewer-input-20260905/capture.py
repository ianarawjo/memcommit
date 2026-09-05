"""Capture the actual Add entry, Context choice, scrolling, input, and saves."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "add_capture_support",
    ROOT / "agent-records/docs/screenshots/compact-add-init-input-20260904/capture.py",
)
assert spec is not None and spec.loader is not None
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
support._BASE.OUT = OUT


def snap(recorder, stem):
    screen = support._BASE._screen(recorder.getvalue())
    for row, line in enumerate(screen.display):
        if "MEM ADD" in line:
            start = line.index("MEM ADD")
            colors = {
                screen.buffer[row][column].fg
                for column in range(start, start + len("MEM ADD"))
            }
            assert len(colors) == 1
    support._snapshot(recorder, stem)


def main():
    with tempfile.TemporaryDirectory(prefix="mem-add-viewer-capture-") as temporary:
        home = Path(temporary)
        support._run_setup(home, "init", "project")
        support._run_setup(home, "init", "notes")
        support._run_setup(
            home,
            "add",
            "--to",
            "project",
            *[f"Existing Memory {index:02d}." for index in range(1, 16)],
        )
        child, recorder = support._spawn(home, "add")
        try:
            support._wait_visible(child, recorder, "Enter add")
            snap(recorder, "01-entry")
            child.send("\t\r")
            support._wait_visible(child, recorder, "Enter select")
            snap(recorder, "02-context-browser")
            child.send("\x1b[B\r")
            support._wait_visible(child, recorder, "Existing Memory 01.")
            snap(recorder, "03-context-selected")
            child.send("\t\x1b[6~")
            support._wait_visible(child, recorder, "Existing Memory 15.")
            snap(recorder, "04-viewer-scrolled")
            child.send("\tA new single-line Memory.")
            support._wait_visible(child, recorder, "A new single-line Memory.")
            snap(recorder, "05-input-ready")
            child.send("\x1b[200~Rejected first line.\nRejected second line.\x1b[201~")
            support._wait_visible(child, recorder, "Paste one Memory on a single line.")
            visible = "\n".join(support._BASE._screen(recorder.getvalue()).display)
            assert "A new single-line Memory." in visible
            assert "Rejected first line." not in visible
            assert "Rejected second line." not in visible
            snap(recorder, "05a-multiline-paste-rejected")
            child.send("\r")
            support._wait_visible(child, recorder, "Added [")
            snap(recorder, "06-added-ready-for-next")
            child.send("\x1b")
            support._wait_visible(child, recorder, "Added 1 Memory to 'project'.")
            support._finish(child)
            snap(recorder, "07-close-receipt")
        finally:
            if child.isalive():
                child.close(force=True)
        raw = recorder.getvalue()
        assert "52 180" in raw
        assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw)
        assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw)
        child, recorder = support._spawn(home, "show", "project", "--direct")
        support._wait_visible(child, recorder, "A new single-line Memory.")
        support._finish(child)
        snap(recorder, "08-read-only-verification")

        support._run_setup(home, "init", "temporary")
        support._run_setup(home, "add", "Existing temporary Memory.")
        child, recorder = support._spawn(home, "add")
        support._wait_visible(child, recorder, "Existing temporary Memory.")
        snap(recorder, "09-failure-path-entry")
        child.send("Keep this input after failure.")
        support._wait_visible(child, recorder, "Keep this input after failure.")
        snap(recorder, "10-failure-path-input")
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from memcommit.persistence.store import MemoryStore; MemoryStore().delete('temporary')",
            ],
            cwd=ROOT,
            env=support._environment(home),
            check=True,
        )
        child.send("\r")
        support._wait_visible(child, recorder, "Add failed")
        snap(recorder, "11-failed-add-input-retained")
        child.send("\x1b")
        support._wait_visible(child, recorder, "Add cancelled")
        support._finish(child)
        snap(recorder, "12-failure-path-close")
        child, recorder = support._spawn(home, "show", "temporary", "--direct")
        support._wait_visible(child, recorder, "Error:")
        support._BASE._pump(child, seconds=0.3)
        child.close()
        assert child.exitstatus == 1
        snap(recorder, "13-failure-read-only-verification")


if __name__ == "__main__":
    main()
