"""Capture Grant-backed Embed through a real 180x52 color PTY."""

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
    / "docs"
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
    guide = ops.init("guide")
    ops.add(guide, "Opening proposal note.")
    ops.add(guide, "Closing proposal note.")
    archive = ops.init("archive")
    ops.add(archive, "Owned archive remains a second local Child option.")
    for context in (guide, archive):
        store.save(context)
    store.set_current(guide.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid="10000000-0000-0000-0000-000000000014",
        name="advisor-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    advisor = ops.init("advisor")
    advice = ops.add(advisor, "Use evidence from the live advisor Context.")
    private = ops.init("advisor/private")
    ops.add(private, "This query-only note must not be embedded or displayed.")
    ops.embed(private, advisor)
    authority_store.save(private)
    authority_store.save(advisor)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n")
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=advisor.name,
        attachment_name=guide.name,
        public_name=advisor.name,
        permissions=("READ", "EMBED"),
        recursive=True,
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=private.name,
        attachment_name=guide.name,
        public_name=private.name,
        permissions=("QUERY",),
        recursive=True,
    )
    return store, guide, advisor, advice


def _child(directory: Path) -> None:
    home = directory / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    base._configure_store(home / ".mem")
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    from memcommit.cli import app

    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    store, guide, advisor, advice = _create_profile(home)
    app(prog_name="mem", args=["embed"], standalone_mode=False)
    print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
    input()
    print("CAPTURE VERIFICATION COMMAND · mem ls -R guide")
    app(prog_name="mem", args=["ls", "-R", "guide"], standalone_mode=False)
    raw = store.load_direct(guide.name).to_dict()["memories"][advisor.uid]
    print(f"LINK TYPE · {raw['type']}")
    print(f"LINK GRANT · {str(raw['grant_uid'])[:8]}")
    print(
        "LINK CONTENT CACHED · "
        + ("YES" if advice.content in json.dumps(raw) else "NO")
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
    with tempfile.TemporaryDirectory(prefix="memcommit-granted-embed-") as directory:
        child = _spawn(environment, directory)
        base._wait_for(child, raw, b"MEM EMBED")
        base._render_snapshot("01-entry-granted-source", bytes(raw))

        child.send(b"\x1b[C\x1b[B\r")
        base._settle(child, raw)
        base._render_snapshot("02-query-override-blocked", bytes(raw))

        child.send(b"\x1b[A\r\t")
        base._settle(child, raw)
        base._render_snapshot("03-owned-target", bytes(raw))

        child.send(b"\t")
        base._settle(child, raw)
        base._render_snapshot("04-placement-default", bytes(raw))

        child.send(b"\x1b[A\r")
        base._settle(child, raw)
        base._render_snapshot("05-gap-staged", bytes(raw))

        child.send(b"\t")
        base._settle(child, raw)
        base._render_snapshot("06-exact-command", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CAPTURE PAUSE")
        base._render_snapshot("07-success-receipt", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, "List · guide".encode())
        child.send(b"AM")
        base._settle(child, raw)
        base._render_snapshot("08-read-only-verification", bytes(raw))
        child.send(b"q")
        base._wait_for(child, raw, b"CURRENT CONTEXT")
        base._render_snapshot("09-link-receipt", bytes(raw))
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
