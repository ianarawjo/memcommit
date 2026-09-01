"""Capture compact exact-Memory Reference setup and durable verification."""

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
spec = importlib.util.spec_from_file_location(
    "reference_compact_capture_base", BASE_PATH
)
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
    ops.add(workspace, "Participant-owned Target note remains independently owned.")
    store.save(workspace)
    store.set_current(workspace.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid="10000000-0000-0000-0000-000000000053",
        name="reference-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memory = ops.add(source, "Retain this exact READ-granted version.")
    authority_store.save(source)

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
    )
    return store, workspace, source, memory, grant


def _child(directory: Path) -> None:
    home = directory / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    base._configure_store(home / ".mem")
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    import typer

    from memcommit.adapters.console.commands.reference.command import (
        cmd as reference_command,
    )
    from memcommit.adapters.console.commands.show.command import cmd as show_command
    from memcommit.core.context import MemoryRef

    # Register the real command adapters in a focused group so unrelated
    # in-progress command-package imports cannot prevent this Reference record.
    app = typer.Typer()
    app.command("reference")(reference_command)
    app.command("show")(show_command)

    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    store, workspace, source, memory, grant = _create_profile()
    app(prog_name="mem", args=["reference"], standalone_mode=False)
    print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
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
        f"MEMORY {memory.uid[:8]} · REFERENCE {reference.uid[:8]} · "
        f"GRANT {reference.granted_source.grant_uid[:8]} · "
        "READ ONLY SNAPSHOT",
        flush=True,
    )


def _spawn(environment: dict[str, str], directory: str):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", directory],
        cwd=str(REPOSITORY_ROOT),
        env=environment,
        dimensions=(base.ROWS, base.COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture(environment: dict[str, str]) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(
        prefix="memcommit-reference-compact-"
    ) as directory:
        child = _spawn(environment, directory)
        base._wait_for(child, raw, b"NEW REFERENCE")
        base._render_snapshot("01-entry-target-context", bytes(raw))

        child.send(b"\x1b[B")
        base._settle(child, raw)
        base._render_snapshot("02-exact-memory-owner", bytes(raw))

        child.send(b"\r\r")
        base._settle(child, raw)
        base._render_snapshot("03-exact-memory-choices", bytes(raw))

        child.send(b"\r")
        base._settle(child, raw)
        base._render_snapshot("04-exact-memory-selected", bytes(raw))

        child.send(b"\x1b[B")
        base._settle(child, raw)
        base._render_snapshot("05-proposed-command-enter", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CAPTURE PAUSE")
        base._render_snapshot("06-success-receipt", bytes(raw))

        child.send(b"\r")
        base._wait_for(child, raw, b"CAPTURE RETAINED VERIFIED")
        base._render_snapshot("07-read-only-verification", bytes(raw))
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
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(SOURCE_ROOT),
        }
    )
    stream = _capture(environment)
    captures = tuple(sorted(CAPTURE_DIR.glob("[0-9][0-9]-*.txt")))
    if len(captures) != 7 or any(
        "CAPTURE PTY · 180x52" not in path.read_text(encoding="utf-8")
        for path in captures
    ):
        raise RuntimeError("Every Reference capture must verify its 180x52 PTY.")
    if b"\x1b[" not in stream or not re.search(rb"\x1b\[[0-9;]*38;", stream):
        raise RuntimeError("Capture did not preserve expected ANSI colors.")
    if b"\x1b[?1049h" in stream:
        raise RuntimeError("Compact Reference entered an alternate screen buffer.")

    entry = (CAPTURE_DIR / "01-entry-target-context.txt").read_text(encoding="utf-8")
    if (
        "PROPOSED COMMAND · INVALID" not in entry
        or "SOURCE MEMORY" not in entry
        or "BROWSE CONTEXT" not in entry
        or "CHOOSE MEMORY" not in entry
    ):
        raise RuntimeError("Initial Reference row did not explain its two actions.")
    choices = (CAPTURE_DIR / "03-exact-memory-choices.txt").read_text(encoding="utf-8")
    if (
        not any(
            "[memory " in line
            and "Retain this exact READ-granted version." in line
            for line in choices.splitlines()
        )
        or any(line.strip().startswith("MEMORY ·") for line in choices.splitlines())
        or "WHOLE CONTEXT" in choices
    ):
        raise RuntimeError("Exact-Memory choices exposed a whole-Context route.")
    command = (CAPTURE_DIR / "05-proposed-command-enter.txt").read_text(
        encoding="utf-8"
    )
    selected = (CAPTURE_DIR / "04-exact-memory-selected.txt").read_text(
        encoding="utf-8"
    )
    if (
        not re.search(
            r"shared/source:[0-9a-f]{8}-[0-9a-f-]{27}",
            selected,
        )
        or "BROWSE CONTEXT" not in selected
        or "CHOOSE MEMORY" not in selected
        or "PROPOSED COMMAND · ENTER TO PROCEED" not in command
        or "mem reference" not in command
        or "--from shared/source --into workspace" not in command
        or "RUN EXACT REFERENCE COMMAND" in command
    ):
        raise RuntimeError("Reference command approval did not match compact design.")
    receipt = (CAPTURE_DIR / "06-success-receipt.txt").read_text(encoding="utf-8")
    if "Referenced snapshot" not in receipt or "from 'shared/source'" not in receipt:
        raise RuntimeError("Reference success receipt was not visible after Apply.")


if __name__ == "__main__":
    main()
