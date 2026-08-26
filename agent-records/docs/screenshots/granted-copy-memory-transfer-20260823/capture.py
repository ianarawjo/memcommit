"""Capture granted Copy's role-separated Memory-transfer TUI in a color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
UP = "\x1b[A"
DOWN = "\x1b[B"
RIGHT = "\x1b[C"

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("granted_copy_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _initialize() -> tuple[str, str, str]:
    import memcommit.ops as ops
    from memcommit.profile_config import (
        AUTHORING_PROFILE_NAME,
        AUTHORING_PROFILE_UID,
        ProfileEntry,
        ProfileRegistry,
        profile_registry_file,
        profile_store_dir,
    )
    from memcommit.profiles import create_authority_grant
    from memcommit.store import MemoryStore

    store = MemoryStore()
    workspace = ops.init("workspace")
    local_source = ops.init("local-source")
    ops.add(local_source, "Locally owned comparison Source.")
    target = ops.init("target")
    marker = ops.add(target, "Target ordering marker.")
    for context in (workspace, local_source, target):
        store.save(context)
    store.set_current(workspace.name)

    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="copy-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memory = ops.add(source, "Export-authorized guidance from the authority.")
    authority_store.save(source)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source.name,
        attachment_name=workspace.name,
        public_name="shared/source",
        permissions=("READ", "DERIVE", "EXPORT", "SAVE_ANALYSIS"),
    )
    return memory.uid, marker.uid, source.uid


def _run_child() -> None:
    with tempfile.TemporaryDirectory(prefix="mem-granted-copy-capture-") as directory:
        # Store and Profile roots are fixed when their modules are imported, so
        # isolate HOME before importing any memcommit module in this process.
        os.environ["HOME"] = directory
        source_memory_uid, marker_uid, source_context_uid = _initialize()

        from memcommit.cli import app
        from memcommit.context import Memory
        from memcommit.profile_config import load_profile_registry, profile_store_dir
        from memcommit.store import MemoryStore

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app(args=["copy"], prog_name="mem", standalone_mode=False)

        print("COPY VERIFICATION GATE · PRESS V")
        sys.stdin.read(1)
        store = MemoryStore()
        target = store.load_direct("target")
        copied = tuple(
            item
            for item in target.iter_items()
            if isinstance(item, Memory)
            and item.content == "Export-authorized guidance from the authority."
        )
        registry = load_profile_registry()
        authority = registry.by_name("copy-authority")
        assert authority is not None
        source = MemoryStore(root=profile_store_dir(authority)).load_direct(
            "authority/source"
        )
        checkpoints = tuple(
            item for item in store.list_checkpoints("target") if item["command"] == "copy"
        )
        assert len(copied) == 1
        assert source.uid == source_context_uid
        assert source_memory_uid in source.memories
        assert target.ordered_uids()[1] == marker_uid
        assert len(checkpoints) == 1
        print(
            "COPY READ-ONLY VERIFICATION · TARGET COPIES 1 · "
            "AUTHORITY SOURCE UNCHANGED 1 · COPY CHECKPOINTS 1 · "
            f"CONTENT {copied[0].content!r}"
        )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".txt", ".typescript"):
        for path in OUT.glob(f"*{suffix}"):
            path.unlink()

    child, recorder = _spawn()
    try:
        child.expect("MEM COPY · DIRECT MEMORIES")
        _BASE._settle(child)
        _snapshot(recorder, "01-entry")

        # Current workspace → public hierarchy root → granted direct Source.
        child.send(UP + UP + RIGHT)
        _BASE._settle(child)
        _snapshot(recorder, "02-granted-source-open")

        child.send(DOWN + "\r")
        _BASE._settle(child)
        _snapshot(recorder, "03-granted-memory-selected")

        child.send("\t" + UP + "\r")
        _BASE._settle(child)
        _snapshot(recorder, "04-local-target-selected")

        child.send("\t" + UP + "\r")
        _BASE._settle(child)
        _snapshot(recorder, "05-target-gap-selected")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "06-exact-approval")

        child.send("\r")
        child.expect("COPY VERIFICATION GATE")
        _snapshot(recorder, "07-copy-success")

        child.send("v\r")
        child.expect("COPY READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    entry = (OUT / "01-entry.txt").read_text(encoding="utf-8")
    source = (OUT / "02-granted-source-open.txt").read_text(encoding="utf-8")
    selected = (OUT / "03-granted-memory-selected.txt").read_text(
        encoding="utf-8"
    )
    target = (OUT / "04-local-target-selected.txt").read_text(encoding="utf-8")
    gap = (OUT / "05-target-gap-selected.txt").read_text(encoding="utf-8")
    approval = (OUT / "06-exact-approval.txt").read_text(encoding="utf-8")
    receipt = (OUT / "07-copy-success.txt").read_text(encoding="utf-8")
    verification = (OUT / "08-read-only-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "GRANTED SOURCES REQUIRE EXPLICIT PUBLIC OWNERS" in entry
    assert "shared/source" in source and "COPY + RETAIN" in source
    assert "Export-authorized guidance" in selected
    assert "INTO + POSITION" in target and "target" in target
    assert "Target ordering marker" in gap
    assert "shared/source:" in approval
    assert "--into target" in approval and "--before" in approval
    assert "COPIED" in receipt and "'shared/source'" in receipt
    assert "COPY READ-ONLY VERIFICATION" in verification
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "\x1b[" in raw
    assert "38;2;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
