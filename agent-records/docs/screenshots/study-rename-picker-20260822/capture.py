"""Capture stable-identity Study rename in the Profile picker."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
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
        / "agent-records" / "docs"
        / "screenshots"
        / "study-full-replay-20260811"
        / "capture_init_study.py"
    )
    spec = importlib.util.spec_from_file_location("study_rename_capture_helpers", path)
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
    store.checkpoint(context, message="Study rename capture")
    store.set_current(name)


def _prepare(home: Path) -> tuple[str, tuple[str, str], tuple[Path, Path]]:
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
    study_uid = "11111111-1111-4111-8111-111111111111"
    common_source: dict[str, object] = {
        "study_uid": study_uid,
        "study_name": "capture-study",
        "created_at": "2026-08-22T12:00:00+00:00",
        "baseline_sha256": "a" * 64,
        "baseline_profile_uid": "22222222-2222-4222-8222-222222222222",
        "baseline_profile_name": "study-baseline",
    }
    participant = ProfileEntry(
        uid="33333333-3333-4333-8333-333333333333",
        name="participant-one",
        kind="MANAGED",
        source={"kind": "STUDY_RUN", **common_source},
    )
    authority = ProfileEntry(
        uid="44444444-4444-4444-8444-444444444444",
        name="participant-one-granted-memory",
        kind="MANAGED",
        source={"kind": "STUDY_RUN_GRANTED_MEMORY", **common_source},
    )
    participant_root = profile_store_dir(participant)
    authority_root = profile_store_dir(authority)
    _save_fixture(
        MemoryStore(root=participant_root),
        name="practice",
        content="Participant capture Memory.",
    )
    _save_fixture(
        MemoryStore(root=authority_root),
        name="granted-memory/source",
        content="Granted-memory capture Memory.",
    )
    _write_registry(
        ProfileRegistry(
            generation=1,
            active_uid=authoring.uid,
            profiles=(authoring, participant, authority),
        )
    )
    return (
        study_uid,
        (participant.uid, authority.uid),
        (participant_root, authority_root),
    )


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


def _assert_color_and_size(recorder) -> None:
    raw = recorder.getvalue()
    if "52 180" not in raw:
        raise RuntimeError("Capture PTY did not verify 52 by 180.")
    if re.search(r"\x1b\[[0-9;:]*m", raw) is None:
        raise RuntimeError("Interactive PTY stream did not contain ANSI styling.")


def _finish(child, recorder) -> None:
    HELPERS._pump(child, recorder, seconds=10, require_eof=True)


def _capture_flow(home: Path) -> None:
    child, recorder = _spawn(home, "profile")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "STUDY capture-study",
        "participant-one",
    )
    _assert_color_and_size(recorder)
    HELPERS._snapshot(recorder, "01-picker-entry")

    child.send("\x1b[B")
    _wait_for(child, recorder, "› STUDY capture-study", "R rename  D remove Study")
    HELPERS._snapshot(recorder, "02-study-header-target")

    child.send("r")
    _wait_for(child, recorder, "Rename Study capture-study", "NEW STUDY NAME")
    child.send("\x15capture-renamed")
    _wait_for(child, recorder, "capture-renamed", "Enter review exact command")
    HELPERS._snapshot(recorder, "03-study-name-input")

    child.send("\r")
    _wait_for(
        child,
        recorder,
        "PROPOSED COMMAND · NOT RUN",
        "mem profile rename-study capture-study capture-renamed",
        "Keep both member Profile display names unchanged",
    )
    HELPERS._snapshot(recorder, "04-exact-rename-review")

    child.send("a")
    _wait_for(
        child,
        recorder,
        "Select a Profile or Study",
        "STUDY capture-renamed",
        "Renamed Study 'capture-study' to 'capture-renamed'",
        "participant-one",
    )
    HELPERS._snapshot(recorder, "05-rename-success-receipt")
    child.send("q")
    _finish(child, recorder)

    verify_child, verify_recorder = _spawn(home, "profile", "list")
    _finish(verify_child, verify_recorder)
    visible = HELPERS._visible_text(verify_recorder)
    if (
        "capture-renamed  STUDY" not in visible
        or "capture-study  STUDY" in visible
        or "profile=participant-one " not in visible
        or "profile=participant-one-granted-memory " not in visible
    ):
        raise RuntimeError("Read-only Profile list did not verify the Study rename.")
    HELPERS._snapshot(verify_recorder, "06-read-only-verification")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-study-rename-capture-") as temp:
        home = Path(temp)
        study_uid, profile_uids, roots = _prepare(home)
        before = tuple(
            path.read_bytes()
            for root in roots
            for path in sorted(root.rglob("*"))
            if path.is_file()
        )
        _capture_flow(home)

        from memcommit.profile_config import load_profile_registry, profile_store_dir
        from memcommit.profiles import study_run_profile_pairs

        registry = load_profile_registry()
        pair = study_run_profile_pairs(registry.profiles)[0]
        if pair.uid != study_uid or pair.name != "capture-renamed":
            raise RuntimeError("Study rename did not preserve the selected identity.")
        if (pair.participant.uid, pair.authority.uid) != profile_uids:
            raise RuntimeError("Study rename changed member Profile identity.")
        if (
            profile_store_dir(pair.participant),
            profile_store_dir(pair.authority),
        ) != roots:
            raise RuntimeError("Study rename changed a member store path.")
        after = tuple(
            path.read_bytes()
            for root in roots
            for path in sorted(root.rglob("*"))
            if path.is_file()
        )
        if after != before:
            raise RuntimeError("Study rename changed member store contents.")


if __name__ == "__main__":
    main()
