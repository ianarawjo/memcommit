"""Capture empty Profile creation, selection, and first Context initialization."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52

sys.path.insert(0, str(ROOT / "src"))


def _load_capture_helpers():
    path = (
        ROOT
        / "agent-records" / "docs"
        / "screenshots"
        / "study-full-replay-20260811"
        / "capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location("profile_create_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load shared PTY capture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.COLS = COLS
    module.ROWS = ROWS
    return module


HELPERS = _load_capture_helpers()


def _environment(home: Path) -> dict[str, str]:
    environment = HELPERS._environment()
    environment["HOME"] = str(home)
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    environment.pop("NO_COLOR", None)
    environment["TERM"] = "xterm-256color"
    environment["COLORTERM"] = "truecolor"
    return environment


def _prepare(home: Path) -> None:
    os.environ["HOME"] = str(home)
    from memcommit.application import ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=home / ".mem")
    context = ops.init("authoring-notes")
    store.save(context)
    store.set_current(context.name)


def _spawn(home: Path, *args: str):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([sys.executable, '-m', 'memcommit.adapters.console.entrypoint', *args])}"
    )
    recorder = HELPERS._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _wait_for(child, recorder, *needles: str, seconds: float = 12.0) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            HELPERS._pump(child, recorder, seconds=0.12)
        except RuntimeError as error:
            raise RuntimeError(
                str(error) + "\n" + HELPERS._visible_text(recorder)
            ) from error
        visible = HELPERS._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return visible
        if not child.isalive():
            break
    raise RuntimeError(
        "PTY did not reach expected state: "
        + ", ".join(repr(needle) for needle in needles)
        + "\n"
        + HELPERS._visible_text(recorder)
    )


def _finish(child, recorder) -> None:
    if not child.isalive():
        return
    HELPERS._pump(child, recorder, seconds=10, require_eof=True)


def _assert_color_and_size(recorder) -> None:
    raw = recorder.getvalue()
    if "52 180" not in raw:
        raise RuntimeError("Capture PTY did not verify 52 by 180.")
    if re.search(r"\x1b\[[0-9;:]*m", raw) is None:
        raise RuntimeError("Interactive PTY stream did not contain ANSI styling.")
    if "38;2;138;173;244" not in raw:
        raise RuntimeError("Profile create action did not use the shared blue role.")
    if re.search(r"\x1b\[(?:[0-9:]+;)*7(?:;[0-9:]+)*m", raw) is None:
        raise RuntimeError("Focused Profile row did not retain its reverse background.")


def _capture_profile_flow(home: Path) -> None:
    child, recorder = _spawn(home, "profile")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "authoring",
        "N new Profile",
    )
    _assert_color_and_size(recorder)
    HELPERS._snapshot(recorder, "01-profile-picker-entry")

    child.send("n")
    _wait_for(
        child,
        recorder,
        "Create an empty Profile",
        "NEW PROFILE NAME",
        "NOT CREATED",
    )
    HELPERS._snapshot(recorder, "02-empty-profile-name-input")

    child.send("capture/invalid\r")
    _wait_for(
        child,
        recorder,
        "Profile name must be one 1-64 character segment",
        "NOT CREATED",
    )
    HELPERS._snapshot(recorder, "03-invalid-profile-name-refused")

    child.send("\x15capture-empty")
    visible = _wait_for(child, recorder, "capture-empty", "Enter review exact command")
    if "Profile name must be one 1-64 character segment" in visible:
        raise RuntimeError("Corrected Profile name retained a stale validation error.")
    HELPERS._snapshot(recorder, "04-exact-profile-name-entered")

    child.send("\r")
    _wait_for(
        child,
        recorder,
        "PROPOSED COMMAND · NOT RUN",
        "mem profile create capture-empty",
        "Keep the current Profile selected",
    )
    HELPERS._snapshot(recorder, "05-exact-create-review")

    child.send("a")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "Created empty Profile 'capture-empty'",
        "capture-empty",
        "Contexts 0 owned + 0 granted",
    )
    HELPERS._snapshot(recorder, "06-create-success-new-row-focused")

    child.send("\r")
    _wait_for(
        child,
        recorder,
        "Selected profile 'capture-empty'",
        "Current Context: (none)",
    )
    _finish(child, recorder)
    HELPERS._snapshot(recorder, "07-new-profile-selected")

    empty_child, empty_recorder = _spawn(home, "profile", "current")
    _finish(empty_child, empty_recorder)
    empty_visible = HELPERS._visible_text(empty_recorder)
    if "Profile: capture-empty" not in empty_visible or "Current Context: (none)" not in empty_visible:
        raise RuntimeError("Read-only current Profile did not verify the empty store.")
    HELPERS._snapshot(empty_recorder, "08-empty-profile-read-only-verification")

    init_child, init_recorder = _spawn(home, "init", "inbox")
    _finish(init_child, init_recorder)
    if "Initialized context 'inbox'." not in HELPERS._visible_text(init_recorder):
        raise RuntimeError("First Context initialization did not complete.")
    HELPERS._snapshot(init_recorder, "09-first-context-created")

    verify_child, verify_recorder = _spawn(home, "profile", "current")
    _finish(verify_child, verify_recorder)
    visible = HELPERS._visible_text(verify_recorder)
    if "Profile: capture-empty" not in visible or "Current Context: inbox" not in visible:
        raise RuntimeError("Final read-only Profile state did not match the flow.")
    HELPERS._snapshot(verify_recorder, "10-final-read-only-verification")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-profile-create-capture-") as temp:
        home = Path(temp)
        _prepare(home)
        _capture_profile_flow(home)


if __name__ == "__main__":
    main()
