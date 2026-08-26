"""Capture an exact granted-Memory Reference through a real color PTY."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile


CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BASE_PATH = (
    REPOSITORY_ROOT
    / "agent-records"
    / "screenshots"
    / "mem-embed-placement-20260813"
    / "capture.py"
)
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
spec = importlib.util.spec_from_file_location("reference_capture_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Reference capture base is unavailable.")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.CAPTURE_DIR = CAPTURE_DIR


def _create_profile():
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
    ops.add(workspace, "Participant-owned target note.")
    store.save(workspace)
    store.set_current(workspace.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid="10000000-0000-0000-0000-000000000035",
        name="reference-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memory = ops.add(source, "Retain this exact export-authorized version.")
    authority_store.save(source)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=source.name,
        attachment_name=workspace.name,
        public_name="shared/source",
        permissions=("READ", "DERIVE", "EXPORT", "SAVE_ANALYSIS"),
    )
    return store, workspace, source, memory, grant


def _child(directory: Path) -> None:
    home = directory / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    base._configure_store(home / ".mem")
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    from memcommit.cli import app
    from memcommit.context import MemoryRef

    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    store, workspace, source, memory, grant = _create_profile()
    app(prog_name="mem", args=["reference"], standalone_mode=False)
    print("CAPTURE PAUSE · press Enter for read-only retained verification", flush=True)
    input()

    target = store.load_direct(workspace.name)
    references = tuple(
        item
        for item in target.iter_items()
        if isinstance(item, MemoryRef) and item.is_snapshot
    )
    assert len(references) == 1
    reference = references[0]
    assert reference.target is not None
    assert reference.target.content == memory.content
    assert reference.target_context_uid == source.uid
    assert reference.target_context_name == "shared/source"
    assert reference.granted_source is not None
    assert reference.granted_source.grant_uid == grant.uid

    print(
        "CAPTURE VERIFICATION COMMAND · "
        f"mem show {reference.uid[:8]} --context {workspace.name}",
        flush=True,
    )
    app(
        prog_name="mem",
        args=["show", reference.uid[:8], "--context", workspace.name],
        standalone_mode=False,
    )
    print(
        "CAPTURE RETAINED VERIFIED · "
        f"SOURCE {reference.target_context_name} · "
        f"GRANT {reference.granted_source.grant_uid[:8]} · "
        f"AUTHORITY CONTEXT {reference.granted_source.authority_context_name} · "
        "READ ONLY SNAPSHOT",
        flush=True,
    )


def _spawn(environment: dict[str, str], directory: str):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", directory],
        env=environment,
        dimensions=(base.ROWS, base.COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(
        prefix="memcommit-granted-reference-"
    ) as directory:
        child = _spawn(environment, directory)
        base._wait_for(child, raw, b"MEM REFERENCE")
        base._render_snapshot("01-entry-context-unit", bytes(raw))

        child.send(b"\x1b[C")
        base._settle(child, raw)
        base._render_snapshot("02-memory-unit-grant-source", bytes(raw))

        child.send(b"\t\x1b[B\r")
        base._settle(child, raw)
        base._render_snapshot("03-granted-source-memory-selected", bytes(raw))

        child.send(b"\t")
        base._settle(child, raw)
        base._render_snapshot("04-local-target", bytes(raw))

        child.send(b"\t")
        base._settle(child, raw)
        base._render_snapshot("05-exact-command-approval", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CAPTURE PAUSE")
        base._render_snapshot("06-success-receipt", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CAPTURE RETAINED VERIFIED")
        base._render_snapshot("07-read-only-retained-verification", bytes(raw))
        child.close()
    return bytes(raw)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    arguments = parser.parse_args()
    if arguments.child:
        _child(Path(arguments.child))
        return

    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment["TERM"] = "xterm-256color"
    environment["COLORTERM"] = "truecolor"
    stream = _capture(environment)
    if b"\x1b[" not in stream or not re.search(rb"\x1b\[[0-9;]*38;", stream):
        raise RuntimeError("Capture did not preserve expected ANSI colors.")
    if b"CAPTURE PTY \xc2\xb7 180x52" not in stream:
        raise RuntimeError("Capture child did not verify the 180x52 PTY.")


if __name__ == "__main__":
    main()
