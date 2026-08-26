"""Capture permanent Profile and Study deletion in a real 180x52 color PTY."""

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


def _load_capture_helpers():
    path = (
        ROOT
        / "agent-records" / "docs"
        / "screenshots"
        / "study-full-replay-20260811"
        / "capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location("memcommit_capture_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load shared PTY capture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.COLS = COLS
    module.ROWS = ROWS
    return module


_SETUP_MODE = len(sys.argv) == 4 and sys.argv[1] == "--setup"
_SLOW_CLI_MODE = len(sys.argv) >= 4 and sys.argv[1] == "--slow-cli"
HELPERS = None if (_SETUP_MODE or _SLOW_CLI_MODE) else _load_capture_helpers()


def _environment(home: Path) -> dict[str, str]:
    assert HELPERS is not None
    environment = HELPERS._environment()
    environment["HOME"] = str(home)
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    return environment


def _new_context(*, name: str, content: str):
    from memcommit.context import Context, Memory

    context = Context(uid=str(uuid.uuid4()), name=name)
    context.add(Memory(uid=str(uuid.uuid4()), content=content))
    return context


def _setup(home: Path, *, active_participant: bool) -> None:
    os.environ["HOME"] = str(home)
    from memcommit.profile_config import (
        ProfileEntry,
        ProfileRegistry,
        profile_store_dir,
        virtual_authoring_registry,
    )
    from memcommit.profiles import _write_registry, create_authority_grant
    from memcommit.store import MemoryStore

    authoring = virtual_authoring_registry().active

    def save_fixture(store: MemoryStore, *, name: str, content: str) -> None:
        context = _new_context(name=name, content=content)
        store.save(context)
        store.checkpoint(context, message="Permanent deletion capture")
        store.set_current(name)

    authoring_store = MemoryStore(root=home / ".mem")
    save_fixture(
        authoring_store,
        name="authoring",
        content="Capture authoring memory",
    )
    study_uid = "11111111-1111-4111-8111-111111111111"
    baseline_uid = "22222222-2222-4222-8222-222222222222"
    common = {
        "study_uid": study_uid,
        "study_name": "capture-study",
        "created_at": "2026-08-13T18:00:00+00:00",
        "baseline_sha256": "a" * 64,
        "baseline_profile_uid": baseline_uid,
        "baseline_profile_name": "study-baseline",
    }
    participant = ProfileEntry(
        uid="33333333-3333-4333-8333-333333333333",
        name="capture-participant",
        kind="MANAGED",
        source={"kind": "STUDY_RUN", **common},
    )
    authority = ProfileEntry(
        uid="44444444-4444-4444-8444-444444444444",
        name="capture-granted-memory",
        kind="MANAGED",
        source={"kind": "STUDY_RUN_GRANTED_MEMORY", **common},
    )
    workspace = ProfileEntry(
        uid="55555555-5555-4555-8555-555555555555",
        name="capture-workspace",
        kind="MANAGED",
    )
    workspace_store = MemoryStore(root=profile_store_dir(workspace))
    save_fixture(
        workspace_store,
        name="workspace",
        content="Capture workspace memory",
    )
    participant_store = MemoryStore(root=profile_store_dir(participant))
    save_fixture(
        participant_store,
        name="participant",
        content="Capture participant memory",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    save_fixture(
        authority_store,
        name="source",
        content="Capture granted memory",
    )
    _write_registry(
        ProfileRegistry(
            generation=1,
            active_uid=participant.uid if active_participant else workspace.uid,
            profiles=(authoring, workspace, participant, authority),
        )
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=participant.name,
        resource_name="source",
        attachment_name="participant",
        permissions=("READ",),
    )


def _prepare(home: Path, *, active_participant: bool = False) -> None:
    command = [
        sys.executable,
        str(__file__),
        "--setup",
        str(home),
        "active" if active_participant else "authoring",
    ]
    subprocess.run(
        command,
        cwd=ROOT,
        env=_environment(home),
        check=True,
        text=True,
    )


def _spawn(home: Path, *args: str, slow_delete: bool = False):
    assert HELPERS is not None
    argv = (
        [sys.executable, str(__file__), "--slow-cli", str(home), *args]
        if slow_delete
        else [sys.executable, "-m", "memcommit.cli", *args]
    )
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join(argv)}"
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


def _wait_for(child, recorder, *needles: str, seconds: float = 12.0) -> None:
    assert HELPERS is not None
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        HELPERS._pump(child, recorder, seconds=0.12)
        visible = HELPERS._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return
        if not child.isalive():
            break
    raise RuntimeError(
        "PTY did not reach expected state: "
        + ", ".join(repr(needle) for needle in needles)
        + "\n"
        + HELPERS._visible_text(recorder)
    )


def _assert_color(recorder) -> None:
    if re.search(r"\x1b\[[0-9;:]*m", recorder.getvalue()) is None:
        raise RuntimeError("Interactive PTY stream did not contain ANSI styling.")


def _finish(child, recorder) -> None:
    assert HELPERS is not None
    HELPERS._pump(child, recorder, seconds=10, require_eof=True)


def _capture_read_only(home: Path, stem: str, *expected: str) -> None:
    assert HELPERS is not None
    child, recorder = _spawn(home, "profile", "list")
    _finish(child, recorder)
    raw = recorder.getvalue()
    if not all(value in raw for value in expected):
        raise RuntimeError(f"Read-only verification {stem} missed expected output.")
    HELPERS._snapshot(recorder, stem)


def _capture_study_path(home: Path) -> None:
    _prepare(home)
    child, recorder = _spawn(home, "profile", slow_delete=True)
    _wait_for(child, recorder, "Select a Profile or Study", "STUDY capture-study")
    if "52 180" not in recorder.getvalue():
        raise RuntimeError("Study capture PTY did not verify 52 by 180.")
    _assert_color(recorder)
    HELPERS._snapshot(recorder, "01-study-entry")

    child.send("\x1b[B")
    _wait_for(child, recorder, "D remove Study", "2 active")
    HELPERS._snapshot(recorder, "02-study-header-target")

    child.send("d")
    _wait_for(
        child,
        recorder,
        "PROPOSED COMMAND · NOT RUN",
        "mem profile remove-study capture-study --force",
        "cannot be undone or recovered by mem",
    )
    HELPERS._snapshot(recorder, "03-study-exact-removal-review")

    child.send("\r")
    _wait_for(child, recorder, "Permanently deleting Study .")
    _wait_for(child, recorder, "Permanently deleting Study ..")
    _wait_for(
        child,
        recorder,
        "Permanently deleting Study …",
        "DELETING STORE AND CHECKPOINTS …",
    )
    HELPERS._snapshot(recorder, "04-study-deletion-in-progress")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "Deleted Study 'capture-study' permanently",
        "2 stores/checkpoint histories deleted",
    )
    if not child.isalive():
        raise RuntimeError("Study removal exited instead of reopening the selector.")
    for uid in (
        "33333333-3333-4333-8333-333333333333",
        "44444444-4444-4444-8444-444444444444",
    ):
        if (home / ".mem-profiles" / "stores" / uid).exists():
            raise RuntimeError("Study removal retained a Profile store.")
    HELPERS._snapshot(recorder, "05-study-removal-receipt")
    child.send("q")
    _finish(child, recorder)
    _capture_read_only(
        home,
        "06-study-read-only-verification",
        "* capture-workspace",
        "Deleted Profile tombstones hidden from this list: 2",
    )


def _capture_profile_path(home: Path) -> None:
    _prepare(home)
    child, recorder = _spawn(home, "profile", slow_delete=True)
    _wait_for(child, recorder, "Select a Profile or Study", "STUDY capture-study")
    _assert_color(recorder)

    child.send("\x1b[Ad")
    _wait_for(child, recorder, "fixed authoring Profile cannot be removed")
    HELPERS._snapshot(recorder, "07-fixed-authoring-removal-blocked")

    child.send("\x1b[B\x1b[B\x1b[B")
    _wait_for(child, recorder, "D remove Profile", "Participant · capture-participant")
    HELPERS._snapshot(recorder, "08-profile-child-target")

    child.send("d")
    _wait_for(
        child,
        recorder,
        "PROPOSED COMMAND · NOT RUN",
        "mem profile remove capture-participant --force",
        "cannot be undone or recovered by mem",
    )
    HELPERS._snapshot(recorder, "09-profile-exact-removal-review")

    child.send("a")
    _wait_for(child, recorder, "Permanently deleting Profile .")
    _wait_for(child, recorder, "Permanently deleting Profile ..")
    _wait_for(
        child,
        recorder,
        "Permanently deleting Profile …",
        "DELETING STORE AND CHECKPOINTS …",
    )
    HELPERS._snapshot(recorder, "10-profile-deletion-in-progress")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "Deleted Profile 'capture-participant' permanently",
        "store/checkpoints deleted",
        "›   Granted memory · capture-granted-memory",
    )
    if not child.isalive():
        raise RuntimeError("Profile removal exited instead of reopening the selector.")
    participant_store = (
        home / ".mem-profiles" / "stores" / "33333333-3333-4333-8333-333333333333"
    )
    authority_store = (
        home / ".mem-profiles" / "stores" / "44444444-4444-4444-8444-444444444444"
    )
    if participant_store.exists() or not authority_store.is_dir():
        raise RuntimeError("Child removal did not preserve the exact sibling scope.")
    HELPERS._snapshot(recorder, "11-profile-removal-receipt")
    child.send("q")
    _finish(child, recorder)
    _capture_read_only(
        home,
        "12-profile-read-only-verification",
        "capture-study  STUDY",
        "1 removed",
        "profile=capture-granted-memory",
        "Deleted Profile tombstones hidden from this list: 1",
    )


def _capture_active_blocks(home: Path) -> None:
    _prepare(home, active_participant=True)
    child, recorder = _spawn(home, "profile")
    _wait_for(child, recorder, "CURRENT", "Participant · capture-participant")
    _assert_color(recorder)

    child.send("d")
    _wait_for(child, recorder, "CURRENT Profile cannot be removed")
    HELPERS._snapshot(recorder, "13-active-profile-removal-blocked")

    child.send("\x1b[A")
    _wait_for(child, recorder, "D remove Study")
    child.send("d")
    _wait_for(child, recorder, "Study contains CURRENT Profile")
    HELPERS._snapshot(recorder, "14-active-study-removal-blocked")
    child.send("q")
    _finish(child, recorder)
    _capture_read_only(
        home,
        "15-blocked-read-only-verification",
        "* Participant",
        "profile=capture-participant",
        "profile=capture-granted-memory",
    )


def _run_direct_cli(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "memcommit.cli", *args],
        cwd=ROOT,
        env=_environment(home),
        check=False,
        text=True,
        capture_output=True,
    )


def _run_slow_cli(home: Path, args: list[str]) -> None:
    """Delay only capture-process deletion so every shared busy frame appears."""

    os.environ["HOME"] = str(home)
    from memcommit.commands import profile as profile_command
    from memcommit.cli import app

    original_profile = profile_command.remove_profile
    original_study = profile_command.remove_study

    def slow_profile(*profile_args, **profile_kwargs):
        time.sleep(1.4)
        return original_profile(*profile_args, **profile_kwargs)

    def slow_study(*study_args, **study_kwargs):
        time.sleep(1.4)
        return original_study(*study_args, **study_kwargs)

    profile_command.remove_profile = slow_profile
    profile_command.remove_study = slow_study
    app(args=args, prog_name="mem")


def _verify_direct_cli(profile_home: Path, study_home: Path) -> None:
    _prepare(profile_home)
    profile_result = _run_direct_cli(
        profile_home,
        "profile",
        "remove",
        "capture-granted-memory",
        "--force",
    )
    if profile_result.returncode != 0 or not all(
        text in profile_result.stdout
        for text in (
            "Permanently deleted Profile 'capture-granted-memory'",
            "Deleted store and all checkpoints",
            "Connected Grants removed: 1",
        )
    ):
        raise RuntimeError("Direct Profile deletion CLI failed its receipt contract.")
    profile_store = (
        profile_home
        / ".mem-profiles"
        / "stores"
        / "44444444-4444-4444-8444-444444444444"
    )
    if profile_store.exists():
        raise RuntimeError("Direct Profile deletion CLI retained its store.")

    _prepare(study_home)
    study_result = _run_direct_cli(
        study_home,
        "profile",
        "remove-study",
        "capture-study",
        "--force",
    )
    if study_result.returncode != 0 or not all(
        text in study_result.stdout
        for text in (
            "Permanently deleted Study 'capture-study' Profile stores",
            "checkpoint histories deleted: 2",
            "Connected Grants removed: 1",
        )
    ):
        raise RuntimeError("Direct Study deletion CLI failed its receipt contract.")
    if any(
        (
            study_home
            / ".mem-profiles"
            / "stores"
            / uid
        ).exists()
        for uid in (
            "33333333-3333-4333-8333-333333333333",
            "44444444-4444-4444-8444-444444444444",
        )
    ):
        raise RuntimeError("Direct Study deletion CLI retained a member store.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-profile-removal-capture-") as root:
        capture_root = Path(root)
        _capture_study_path(capture_root / "study")
        _capture_profile_path(capture_root / "profile")
        _capture_active_blocks(capture_root / "blocked")
        _verify_direct_cli(
            capture_root / "direct-profile",
            capture_root / "direct-study",
        )


if __name__ == "__main__":
    if _SETUP_MODE:
        _setup(Path(sys.argv[2]), active_participant=sys.argv[3] == "active")
    elif _SLOW_CLI_MODE:
        _run_slow_cli(Path(sys.argv[2]), sys.argv[3:])
    else:
        main()
