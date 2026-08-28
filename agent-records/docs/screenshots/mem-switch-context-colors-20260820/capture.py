"""Capture Switch's granted, embedded, and reference Context palette."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SUPPORT_PATH = (
    CAPTURE_DIR.parent / "mem-embed-placement-20260813" / "capture.py"
)

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _load_capture_support():
    spec = importlib.util.spec_from_file_location(
        "mem_switch_context_color_capture_support",
        SUPPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the shared color-PTY renderer.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CAPTURE_DIR = CAPTURE_DIR
    return module


SUPPORT = _load_capture_support()


def _store_snapshot(root: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        count += 1
    return count, digest.hexdigest()


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
    reference = ops.reference_query_context(
        "reference/private-source",
        "30000000-0000-0000-0000-000000000020",
        workspace,
    )
    embedded = ops.init("workspace/embedded-source")
    ops.add(embedded, "Live embedded evidence.")
    ops.embed(embedded, workspace)
    store.save(embedded)
    store.save(workspace)
    store.set_current(workspace.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid="10000000-0000-0000-0000-000000000020",
        name="switch-color-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    shared = ops.init("authority/shared-source")
    ops.add(shared, "Granted evidence remains authority-owned.")
    authority_store.save(shared)

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
        resource_name=shared.name,
        attachment_name=workspace.name,
        public_name="granted/shared-source",
        permissions=("READ",),
        recursive=True,
    )
    return store, workspace, reference, embedded


def _child(directory: Path) -> None:
    home = directory / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    SUPPORT._configure_store(home / ".mem")
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    from memcommit.adapters.console.entrypoint import app

    columns, rows = os.get_terminal_size()
    if (columns, rows) != (COLUMNS, ROWS):
        raise RuntimeError(
            f"Switch capture requires {COLUMNS}x{ROWS}, got {columns}x{rows}."
        )
    store, workspace, reference, embedded = _create_profile()
    before = _store_snapshot(home / ".mem")
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    print("PROFILE · authoring · disposable color fixture", flush=True)
    print(f"CURRENT CONTEXT · {store.current_context_name()}", flush=True)
    app(prog_name="mem", args=["switch"], standalone_mode=False)
    after = _store_snapshot(home / ".mem")

    print("SWITCH CONTEXT COLOR VERIFICATION · READ-ONLY")
    print("COMPLETE PROFILE BYTES UNCHANGED · " + ("YES" if before == after else "NO"))
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print(f"REFERENCE UID · {reference.uid[:8]}")
    print(f"EMBEDDED UID · {embedded.uid[:8]}")
    print(f"VERIFICATION COMMAND · mem show --context {workspace.name}")
    app(
        prog_name="mem",
        args=["show", "--context", workspace.name],
        standalone_mode=False,
    )


def _spawn(environment: dict[str, str], directory: str):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", directory],
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(
        prefix="memcommit-switch-context-colors-"
    ) as directory:
        child = _spawn(environment, directory)
        SUPPORT._wait_for(child, raw, b"Select a Context")
        SUPPORT._render_snapshot("01-switch-entry-grant-visible", bytes(raw))

        child.send(b"m")
        SUPPORT._settle(child, raw)
        SUPPORT._render_snapshot("02-three-context-colors-visible", bytes(raw))

        child.send(b"\x1b[B")
        SUPPORT._settle(child, raw)
        SUPPORT._render_snapshot("03-reference-context-focused", bytes(raw))

        child.send(b"\x1b[B")
        SUPPORT._settle(child, raw)
        SUPPORT._render_snapshot("04-embedded-context-focused", bytes(raw))

        child.send(b"\x1b")
        SUPPORT._wait_for(
            child,
            raw,
            b"COMPLETE PROFILE BYTES UNCHANGED \xc2\xb7 YES",
        )
        deadline = time.monotonic() + 3.0
        while child.isalive() and time.monotonic() < deadline:
            SUPPORT._drain(child, raw)
        SUPPORT._settle(child, raw)
        SUPPORT._render_snapshot("05-cancelled-and-verified", bytes(raw))
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
    required = (
        b"CAPTURE PTY \xc2\xb7 180x52",
        b"GRANT",
        b"reference/private-source",
        b"VIA EMBED",
        b"COMPLETE PROFILE BYTES UNCHANGED \xc2\xb7 YES",
    )
    missing = [value for value in required if value not in stream]
    if missing:
        raise RuntimeError(f"Switch color capture verification missing: {missing!r}")
    # prompt-toolkit's xterm-256color output quantizes the requested semantic
    # RGB values to their nearest stable palette entries in this PTY. Verify
    # those exact emitted foregrounds instead of claiming a true-color stream.
    for ansi_color in (
        rb"38;5;150",  # granted green, requested #a6da95
        rb"38;5;223",  # embedded yellow, requested #eed49f
        rb"38;5;183",  # reference purple, requested #c6a0f6
    ):
        if not re.search(rb"\x1b\[[0-9;]*" + ansi_color, stream):
            raise RuntimeError(
                f"Switch color capture missing ANSI color {ansi_color!r}."
            )


if __name__ == "__main__":
    main()
