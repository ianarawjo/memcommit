"""Capture Delete/Undo/Redo receipts from a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

import pexpect


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SUPPORT_PATH = (
    CAPTURE_DIR.parent / "mem-embed-placement-20260813" / "capture.py"
)
PROMPT = b"KimMunyeong@MacBook-Pro-3 memcommit % "


def _load_capture_support():
    spec = importlib.util.spec_from_file_location(
        "delete_undo_redo_capture_support",
        SUPPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the shared color-PTY renderer.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CAPTURE_DIR = CAPTURE_DIR
    return module


SUPPORT = _load_capture_support()


def _environment(store_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_CAPTURE_STORE": str(store_root),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _seed(environment: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, str(CAPTURE_DIR / "seed_capture.py")],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
    )


def _spawn(environment: dict[str, str]):
    return pexpect.spawn(
        "/bin/zsh",
        ["-f"],
        cwd=str(REPOSITORY_ROOT),
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _command(child, command: str) -> bytes:
    raw = bytearray()
    child.send(command.encode("utf-8") + b"\r")
    SUPPORT._wait_for(child, raw, PROMPT)
    return bytes(raw)


def _clear(child) -> None:
    _command(child, "clear")


def _capture(environment: dict[str, str]) -> dict[str, bytes]:
    child = _spawn(environment)
    startup = bytearray()
    SUPPORT._wait_for(child, startup, b"% ")
    cli_path = shlex.quote(str(CAPTURE_DIR / "capture_cli.py"))
    setup = (
        f"function mem {{ {shlex.quote(sys.executable)} {cli_path} \"$@\"; }}; "
        "PROMPT='KimMunyeong@MacBook-Pro-3 memcommit %% '"
    )
    _command(child, setup)

    _clear(child)
    entry = _command(
        child,
        "printf 'LIVE COLOR PTY · '; stty size; "
        "printf 'CURRENT CONTEXT · '; mem pwd",
    )
    entry += _command(child, "mem show")

    captures = {"01-initial-state": entry}
    for stem, command in (
        ("02-delete-receipt", "mem delete b925d6bf"),
        ("03-undo-receipt", "mem undo"),
        ("04-redo-receipt", "mem redo"),
        ("05-final-verification", "mem show"),
    ):
        _clear(child)
        captures[stem] = _command(child, command)

    child.send(b"exit\r")
    child.close()
    return captures


def _verify(captures: dict[str, bytes], store_root: Path) -> None:
    initial = captures["01-initial-state"]
    deleted = captures["02-delete-receipt"]
    undone = captures["03-undo-receipt"]
    redone = captures["04-redo-receipt"]
    final = captures["05-final-verification"]

    required = {
        "initial PTY dimensions": (initial, b"LIVE COLOR PTY \xc2\xb7 52 180"),
        "initial Memory": (initial, b"dfadfadfadfasf"),
        "delete command": (deleted, b"mem delete b925d6bf"),
        "delete green status": (deleted, b"\x1b[32mRemoved [b925d6bf] "),
        "delete red content": (deleted, b"\x1b[31mdfadfadfadfasf"),
        "undo compact selector": (
            undone,
            b"mem remove b925d6bf --context practice/2",
        ),
        "undo green status": (undone, b"\x1b[32mUndid command: "),
        "undo green addition": (undone, b"\x1b[32m+ 1 added"),
        "redo compact selector": (
            redone,
            b"mem remove b925d6bf --context practice/2",
        ),
        "redo green status": (redone, b"\x1b[32mRedid command: "),
        "redo red removal": (redone, b"\x1b[31m- 1 removed"),
        "final empty state": (final, b"(no items)"),
    }
    missing = [label for label, (stream, value) in required.items() if value not in stream]
    if missing:
        raise RuntimeError("Capture verification missing: " + ", ".join(missing))

    full_uid = b"b925d6bf-aec7-4de5-a432-7cf627d72628"
    if full_uid in undone or full_uid in redone:
        raise RuntimeError("Compact Undo/Redo receipt leaked the full Memory UID.")
    if not re.search(rb"\x1b\[[0-9;]*3[12]m", deleted + undone + redone):
        raise RuntimeError("Capture did not preserve expected ANSI foregrounds.")

    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    if store.current_context_name() != "practice/2":
        raise RuntimeError("Capture changed the current Context unexpectedly.")
    if store.load_current().memories:
        raise RuntimeError("Final read-only verification found a remaining Memory.")


def main() -> None:
    with tempfile.TemporaryDirectory(
        prefix="memcommit-delete-undo-redo-receipts-"
    ) as directory:
        store_root = Path(directory) / "store"
        environment = _environment(store_root)
        _seed(environment)
        captures = _capture(environment)
        for stem, stream in captures.items():
            SUPPORT._render_snapshot(stem, stream)
        _verify(captures, store_root)


if __name__ == "__main__":
    main()
