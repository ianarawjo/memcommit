"""Capture Profile rename from its picker and combined Help entry."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52

sys.path.insert(0, str(ROOT / "src"))


def _load_capture_helpers():
    path = (
        ROOT
        / "docs"
        / "screenshots"
        / "study-full-replay-20260811"
        / "capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location("profile_rename_capture_helpers", path)
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
    return environment


def _save_fixture(store, *, name: str, content: str) -> None:
    from memcommit.context import Context, Memory

    context = Context(uid=str(uuid.uuid4()), name=name)
    context.add(Memory(uid=str(uuid.uuid4()), content=content))
    store.save(context)
    store.checkpoint(context, message="Profile rename capture")
    store.set_current(name)


def _prepare(home: Path) -> tuple[str, Path]:
    os.environ["HOME"] = str(home)
    from memcommit.profile_config import (
        ProfileEntry,
        ProfileRegistry,
        profile_store_dir,
        virtual_authoring_registry,
    )
    from memcommit.profiles import _write_registry
    from memcommit.store import MemoryStore

    authoring = virtual_authoring_registry().active
    _save_fixture(
        MemoryStore(root=home / ".mem"),
        name="authoring-notes",
        content="Authoring capture Memory.",
    )
    workspace = ProfileEntry(
        uid="11111111-1111-4111-8111-111111111111",
        name="capture-workspace",
        kind="MANAGED",
    )
    sibling = ProfileEntry(
        uid="22222222-2222-4222-8222-222222222222",
        name="capture-sibling",
        kind="MANAGED",
    )
    workspace_root = profile_store_dir(workspace)
    _save_fixture(
        MemoryStore(root=workspace_root),
        name="workspace/context",
        content="Workspace capture Memory.",
    )
    _save_fixture(
        MemoryStore(root=profile_store_dir(sibling)),
        name="sibling/context",
        content="Sibling capture Memory.",
    )
    _write_registry(
        ProfileRegistry(
            generation=1,
            active_uid=workspace.uid,
            profiles=(authoring, workspace, sibling),
        )
    )
    return workspace.uid, workspace_root


def _spawn(home: Path, *args: str):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([sys.executable, '-m', 'memcommit.cli', *args])}"
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
        HELPERS._pump(child, recorder, seconds=0.12)
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
    HELPERS._pump(child, recorder, seconds=10, require_eof=True)


def _assert_color_and_size(recorder) -> None:
    raw = recorder.getvalue()
    if "52 180" not in raw:
        raise RuntimeError("Capture PTY did not verify 52 by 180.")
    if re.search(r"\x1b\[[0-9;:]*m", raw) is None:
        raise RuntimeError("Interactive PTY stream did not contain ANSI styling.")


def _capture_profile_flow(home: Path, uid: str, store_root: Path) -> None:
    child, recorder = _spawn(home, "profile")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "capture-workspace",
        "Enter use  R rename  D remove Profile",
    )
    _assert_color_and_size(recorder)
    HELPERS._snapshot(recorder, "01-profile-picker-entry")

    child.send("r")
    _wait_for(child, recorder, "Rename Profile capture-workspace", "NOT APPLIED")
    HELPERS._snapshot(recorder, "02-rename-name-input")

    child.send("\x15capture/invalid\r")
    _wait_for(child, recorder, "Profile name must be one 1-64 character segment")
    HELPERS._snapshot(recorder, "03-invalid-name-refused")

    child.send("\x15capture-renamed")
    visible = _wait_for(child, recorder, "capture-renamed")
    if "Profile name must be one 1-64 character segment" in visible:
        raise RuntimeError("Corrected Profile name retained a stale validation error.")
    HELPERS._snapshot(recorder, "04-corrected-exact-name")

    child.send("\r")
    _wait_for(
        child,
        recorder,
        "PROPOSED COMMAND · NOT RUN",
        "mem profile rename capture-workspace capture-renamed",
        "Profile UID, store, Contexts, Memories, and Grants stay unchanged",
    )
    HELPERS._snapshot(recorder, "05-exact-rename-review")

    child.send("a")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "Renamed Profile 'capture-workspace' to 'capture-renamed'",
        "capture-renamed",
        "CURRENT",
    )
    HELPERS._snapshot(recorder, "06-rename-success-receipt")

    child.send("\x1b[Ar")
    _wait_for(child, recorder, "fixed authoring Profile cannot be renamed")
    HELPERS._snapshot(recorder, "07-fixed-profile-rename-blocked")
    child.send("q")
    _finish(child, recorder)

    from memcommit.profile_config import load_profile_registry, profile_store_dir

    registry = load_profile_registry()
    renamed = registry.by_name("capture-renamed")
    if renamed is None or renamed.uid != uid or registry.active_uid != uid:
        raise RuntimeError("Profile rename did not preserve the selected identity.")
    if profile_store_dir(renamed) != store_root:
        raise RuntimeError("Profile rename changed the managed store path.")

    verify_child, verify_recorder = _spawn(home, "profile", "list")
    _finish(verify_child, verify_recorder)
    visible = HELPERS._visible_text(verify_recorder)
    if "capture-renamed" not in visible or "capture-workspace" in visible:
        raise RuntimeError("Read-only Profile list did not verify the rename.")
    HELPERS._snapshot(verify_recorder, "08-read-only-profile-verification")


def _capture_combined_help(home: Path) -> None:
    import click
    from typer.main import get_command

    from memcommit.cli import app
    from memcommit.commands.help_inventory.command import (
        _ordered_help_entries,
        command_entries,
    )

    root = get_command(app)
    context = click.Context(root)
    rename_index = next(
        index
        for index, entry in enumerate(
            _ordered_help_entries(command_entries(context), by_kind=False)
        )
        if entry.name == "rename"
    )
    child, recorder = _spawn(home, "help")
    _wait_for(child, recorder, "CORE CONCEPTS")
    # Move the focused command list to its A-Z projection, then locate Rename
    # without coupling the capture to unrelated category ordering.
    child.send("\t\x1b[C\t")
    _wait_for(child, recorder, "[ ✓ A–Z ]")
    child.send("\x1b[H")
    for _ in range(rename_index):
        child.send("\x1b[B")
        HELPERS._pump(child, recorder, seconds=0.08)
    child.send("\x1b[C")
    _wait_for(child, recorder, "FORM 1 · mem rename [new_name]")
    child.send("\x1b[B\x1b[B\x1b[B")
    _wait_for(
        child,
        recorder,
        "▾ mem rename",
        "FORM 1 · mem rename [new_name]",
        "FORM 2 · mem rename [profile_name] [new_name]",
        "FORM 3 · mem profile rename [new_name]",
        "FORM 4 · mem profile rename [profile_name] [new_name]",
    )
    _assert_color_and_size(recorder)
    HELPERS._snapshot(recorder, "09-combined-rename-help")
    child.send("q")
    _finish(child, recorder)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-profile-rename-capture-") as temp:
        home = Path(temp)
        uid, store_root = _prepare(home)
        _capture_profile_flow(home, uid, store_root)
        _capture_combined_help(home)

        direct = subprocess.run(
            [sys.executable, "-m", "memcommit.cli", "rename", "capture-sibling", "sibling-renamed"],
            cwd=ROOT,
            env=_environment(home),
            text=True,
            capture_output=True,
            check=False,
        )
        if direct.returncode != 0 or "Renamed Profile 'capture-sibling'" not in direct.stdout:
            raise RuntimeError("Top-level mem rename did not share Profile semantics.")


if __name__ == "__main__":
    main()
