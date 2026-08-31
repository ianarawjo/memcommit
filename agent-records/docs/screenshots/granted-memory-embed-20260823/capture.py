"""Capture granted direct-Memory Embed through a real 180x52 color PTY."""

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
    / "agent-records" / "docs"
    / "screenshots"
    / "mem-embed-placement-20260813"
    / "capture.py"
)
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
spec = importlib.util.spec_from_file_location("embed_capture_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Embed capture base is unavailable.")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.CAPTURE_DIR = CAPTURE_DIR


def _create_profile(home: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.application.operations.profiles.profile.config import (
        AUTHORING_PROFILE_NAME,
        AUTHORING_PROFILE_UID,
        ProfileEntry,
        ProfileRegistry,
        profile_registry_file,
        profile_store_dir,
    )
    from memcommit.application.operations.profiles.profile.model import create_authority_grant
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    guide = ops.init("guide")
    opening = ops.add(guide, "Owned opening marker in the local Target.")
    closing = ops.add(guide, "Owned closing marker in the local Target.")
    store.save(guide)
    store.set_current(guide.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid="10000000-0000-0000-0000-000000000823",
        name="advisor-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("private-advice")
    advice = ops.add(source, "Original live guidance from the authority.")
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
        attachment_name=guide.name,
        public_name="advisor",
        permissions=("READ", "EMBED"),
    )
    return store, authority_store, guide, opening, closing, source, advice, grant


def _child(directory: Path) -> None:
    home = directory / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    base._configure_store(home / ".mem")
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    from memcommit.adapters.console.entrypoint import app
    from memcommit.core.context import Memory

    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    (
        store,
        authority_store,
        guide,
        _opening,
        _closing,
        source,
        advice,
        grant,
    ) = _create_profile(home)
    app(prog_name="mem", args=["embed"], standalone_mode=False)

    print("CAPTURE PAUSE · press Enter for live read-only verification", flush=True)
    input()
    updated = authority_store.load_direct(source.name)
    updated.replace(
        Memory(
            uid=advice.uid,
            content="UPDATED live guidance loaded after the Embed completed.",
        )
    )
    authority_store.save(updated)
    print("AUTHORITY UPDATE · same Memory UID, new content")
    print("CAPTURE VERIFICATION COMMAND · mem ls -R guide")
    app(prog_name="mem", args=["ls", "-R", guide.name], standalone_mode=False)

    print("CAPTURE LINK PAUSE · press Enter for raw link verification", flush=True)
    input()
    direct = store.load_direct(guide.name)
    raw = next(
        item
        for item in direct.to_dict()["memories"].values()
        if item["type"] == "granted_memory_ref"
    )
    print(f"LINK TYPE · {raw['type']}")
    print(f"LINK GRANT · {raw['grant_source']['grant_uid'][:8]}")
    print(
        "LINK CONTENT CACHED · "
        + ("YES" if advice.content in json.dumps(raw) else "NO")
    )
    print(
        f"GRANT MATCH · {'YES' if raw['grant_source']['grant_uid'] == grant.uid else 'NO'}"
    )
    print(f"CURRENT CONTEXT · {store.current_context_name()}")


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
        prefix="memcommit-granted-memory-embed-"
    ) as directory:
        child = _spawn(environment, directory)
        base._wait_for(child, raw, b"MEM EMBED")
        base._render_snapshot("01-entry", bytes(raw))

        child.send(b"\x1b[C")
        base._settle(child, raw)
        base._render_snapshot("02-memory-mode", bytes(raw))

        child.send(b"\t\x1b[A\r")
        base._settle(child, raw)
        base._render_snapshot("03-granted-source", bytes(raw))

        child.send(b"\x1b[B")
        base._settle(child, raw)
        base._render_snapshot("04-granted-memory-focus", bytes(raw))

        child.send(b"\r")
        base._settle(child, raw)
        base._render_snapshot("05-granted-memory-selected", bytes(raw))

        child.send(b"\t")
        base._settle(child, raw)
        base._render_snapshot("06-local-target", bytes(raw))

        child.send(b"\t\x1b[A\r")
        base._settle(child, raw)
        base._render_snapshot("07-gap-staged", bytes(raw))

        child.send(b"\t")
        base._settle(child, raw)
        base._render_snapshot("08-exact-qualified-command", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CAPTURE PAUSE")
        base._render_snapshot("09-success-receipt", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CAPTURE LINK PAUSE")
        base._render_snapshot("10-live-read-only-verification", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CURRENT CONTEXT")
        base._render_snapshot("11-content-free-link-receipt", bytes(raw))
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
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    stream = _capture(environment)
    if b"\x1b[" not in stream or not re.search(rb"\x1b\[[0-9;]*38;", stream):
        raise RuntimeError("Capture did not preserve expected ANSI colors.")
    if b"CAPTURE PTY \xc2\xb7 180x52" not in stream:
        raise RuntimeError("Capture child did not verify the 180x52 PTY.")

    source_text = (CAPTURE_DIR / "03-granted-source.txt").read_text()
    if not all(label in source_text for label in ("GRANT", "READ", "EMBED")):
        raise RuntimeError("Granted Memory Source capabilities were not visible.")
    command_text = (CAPTURE_DIR / "08-exact-qualified-command.txt").read_text()
    if "mem embed advisor:" not in command_text or " --from advisor" in command_text:
        raise RuntimeError("Granted Memory command was not owner-qualified.")
    verification_text = (CAPTURE_DIR / "10-live-read-only-verification.txt").read_text()
    if "UPDATED live guidance" not in verification_text:
        raise RuntimeError("Read-only verification did not reload the live value.")


if __name__ == "__main__":
    main()
