"""Capture an exact recursive granted-Context Reference in a real color PTY."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile


CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
BASE_PATH = (
    REPOSITORY_ROOT
    / "agent-records"
    / "docs"
    / "screenshots"
    / "mem-embed-placement-20260813"
    / "capture.py"
)
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
spec = importlib.util.spec_from_file_location("reference_capture_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Reference capture base is unavailable.")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.CAPTURE_DIR = CAPTURE_DIR


def _create_profile():
    import memcommit.application.capabilities.ops as ops
    from memcommit.application.operations.profile.config import (
        AUTHORING_PROFILE_NAME,
        AUTHORING_PROFILE_UID,
        ProfileEntry,
        ProfileRegistry,
        profile_registry_file,
        profile_store_dir,
    )
    from memcommit.application.operations.profile.model import create_authority_grant
    from memcommit.persistence.store import MemoryStore

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
        uid="10000000-0000-0000-0000-000000000043",
        name="reference-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    root_memory = ops.add(source, "Retain the readable root version.")
    child = ops.init("authority/source/child")
    child_memory = ops.add(child, "Retain the readable lexical descendant.")
    embedded = ops.init("authority/source/embedded")
    embedded_memory = ops.add(embedded, "Retain the readable embedded Context.")
    ops.embed(embedded, source)
    for context in (child, embedded, source):
        authority_store.save(context)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=source.name,
        attachment_name=workspace.name,
        public_name="shared/source",
        permissions=("READ",),
        recursive=True,
    )
    return (
        store,
        authority_store,
        workspace,
        source,
        root_memory,
        child_memory,
        embedded_memory,
        grant,
    )


def _contents(context) -> tuple[str, ...]:
    from memcommit.core.context import Context, Memory

    found: list[str] = []
    visited: set[str] = set()

    def visit(current: Context) -> None:
        if current.uid in visited:
            return
        visited.add(current.uid)
        for item in current.iter_items():
            if isinstance(item, Memory):
                found.append(item.content)
            elif isinstance(item, Context):
                visit(item)

    visit(context)
    return tuple(found)


def _child(directory: Path) -> None:
    home = directory / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    base._configure_store(home / ".mem")
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    import memcommit.application.capabilities.ops as ops
    from memcommit.adapters.console.entrypoint import app
    from memcommit.application.capabilities.context_snapshot import ContextSnapshotRef
    from memcommit.application.operations.profile.model import update_authority_grant

    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    (
        store,
        authority_store,
        workspace,
        source,
        root_memory,
        child_memory,
        embedded_memory,
        grant,
    ) = _create_profile()
    app(prog_name="mem", args=["reference"], standalone_mode=False)
    print("CAPTURE PAUSE · press Enter for retained snapshot verification", flush=True)
    input()

    target = store.load_direct(workspace.name)
    references = tuple(
        item for item in target.iter_items() if isinstance(item, ContextSnapshotRef)
    )
    assert len(references) == 1
    reference = references[0]
    expected = {
        root_memory.content,
        child_memory.content,
        embedded_memory.content,
    }
    assert set(_contents(reference)) == expected
    assert {
        item.public_name for item in reference.granted_sources
    } == {
        "shared/source",
        "shared/source/child",
        "shared/source/embedded",
    }
    assert {item.grant_uid for item in reference.granted_sources} == {grant.uid}

    changed = authority_store.load_for_update(source.name)
    ops.add(changed, "Authority changed after the frozen Reference.")
    authority_store.save(changed)
    update_authority_grant(grant.uid, permissions=("QUERY",))

    retained = store.load(workspace.name).memories[reference.uid]
    assert isinstance(retained, ContextSnapshotRef)
    assert set(_contents(retained)) == expected
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
        "CAPTURE RETAINED VERIFIED · SOURCE shared/source · "
        f"GRANT {grant.uid[:8]} NOW QUERY ONLY · CONTEXTS "
        f"{len(reference.snapshot_package['contexts'])} · "
        "READ ONLY SNAPSHOT · AUTHORITY CHANGE NOT FOLLOWED",
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
        prefix="memcommit-granted-context-reference-"
    ) as directory:
        child = _spawn(environment, directory)
        base._wait_for(child, raw, b"MEM REFERENCE")
        base._render_snapshot("01-entry-granted-context", bytes(raw))

        child.send(b"\t\r")
        base._settle(child, raw)
        base._render_snapshot("02-granted-context-source-selected", bytes(raw))

        child.send(b"\t\x1b[C")
        base._settle(child, raw)
        base._render_snapshot("03-recursive-scope", bytes(raw))

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
