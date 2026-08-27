"""Capture Ctrl-C cancellation across affected interactive commands."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SUPPORT_PATH = CAPTURE_DIR.parent / "mem-embed-placement-20260813" / "capture.py"

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _load_capture_support():
    spec = importlib.util.spec_from_file_location(
        "memcommit_interrupt_capture_support",
        SUPPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the shared color-PTY renderer.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CAPTURE_DIR = CAPTURE_DIR
    return module


SUPPORT = _load_capture_support()

MODES = {
    "add": (("add",), b"MEM ADD"),
    "edit": (("edit",), b"MEM EDIT"),
    "embed": (("embed",), b"MEM EMBED"),
    "reference": (("reference",), b"MEM REFERENCE"),
    "atomize": (("atomize", "--sessions"), b"Add new Atomize session"),
    "help": (("help",), b"Q/Esc close"),
}


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


def _create_store():
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    alpha = ops.init("alpha")
    ops.add(alpha, "Alpha remains available as a secondary Context.")
    beta = ops.init("beta")
    ops.add(beta, "First beta Memory remains unchanged after cancellation.")
    ops.add(beta, "Second beta Memory remains unchanged after cancellation.")
    child = ops.init("beta/child")
    ops.add(child, "The child Context also remains unchanged.")
    for context in (alpha, beta, child):
        store.save(context)
    store.set_current(beta.name)
    return store


def _child(directory: Path, *, mode: str) -> None:
    from memcommit.adapters.console.entrypoint import app

    home = directory / "home"
    home.mkdir()
    os.environ["HOME"] = str(home)
    SUPPORT._configure_store(home / ".mem")
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    columns, rows = os.get_terminal_size()
    if (columns, rows) != (COLUMNS, ROWS):
        raise RuntimeError(
            f"Interrupt capture requires {COLUMNS}x{ROWS}, got {columns}x{rows}."
        )
    store = _create_store()
    before = _store_snapshot(home / ".mem")
    argv, _marker = MODES[mode]
    command = "mem " + " ".join(argv)
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    print("PROFILE · disposable authoring fixture", flush=True)
    print(f"CURRENT CONTEXT · {store.current_context_name()}", flush=True)
    print(f"COMMAND · {command}", flush=True)
    app(prog_name="mem", args=list(argv), standalone_mode=False)

    after = _store_snapshot(home / ".mem")
    print("CTRL-C CANCELLATION VERIFICATION · READ-ONLY")
    print(f"COMMAND RETURNED · {command}")
    print("CTRL-C CLOSED THE ACTIVE TUI · YES")
    print("COMPLETE STORE UNCHANGED · " + ("YES" if before == after else "NO"))
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print("VERIFICATION COMMAND · mem show --context beta")
    app(
        prog_name="mem",
        args=["show", "--context", "beta"],
        standalone_mode=False,
    )


def _spawn(environment: dict[str, str], directory: str, *, mode: str):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", directory, "--mode", mode],
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _capture_mode(
    environment: dict[str, str],
    *,
    mode: str,
    index: int,
) -> bytes:
    raw = bytearray()
    with tempfile.TemporaryDirectory(
        prefix=f"memcommit-{mode}-interrupt-"
    ) as directory:
        child = _spawn(environment, directory, mode=mode)
        _argv, marker = MODES[mode]
        SUPPORT._wait_for(child, raw, marker)
        if mode == "atomize":
            child.send(b"\r")
            SUPPORT._wait_for(child, raw, b"NEW ATOMIZE")
        SUPPORT._render_snapshot(f"{index:02d}-{mode}-entry", bytes(raw))

        child.send(b"\x03")
        SUPPORT._wait_for(child, raw, b"COMPLETE STORE UNCHANGED \xc2\xb7 YES")
        SUPPORT._wait_for(child, raw, b"Second beta Memory")
        SUPPORT._render_snapshot(f"{index + 1:02d}-{mode}-ctrl-c-cancelled", bytes(raw))
        child.close()
    return bytes(raw)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    parser.add_argument("--mode", choices=tuple(MODES), default="add")
    arguments = parser.parse_args()
    if arguments.child:
        _child(Path(arguments.child), mode=arguments.mode)
        return

    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment["TERM"] = "xterm-256color"
    environment["COLORTERM"] = "truecolor"
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"

    streams = []
    for index, mode in enumerate(MODES, start=0):
        streams.append(
            _capture_mode(
                environment,
                mode=mode,
                index=index * 2 + 1,
            )
        )
    combined = b"".join(streams)
    if b"\x1b[" not in combined or not re.search(rb"\x1b\[[0-9;]*38;", combined):
        raise RuntimeError("Capture did not preserve expected ANSI color styles.")
    if any(b"CAPTURE PTY \xc2\xb7 180x52" not in stream for stream in streams):
        raise RuntimeError("A capture child did not verify the 180x52 PTY.")
    if combined.count(b"COMPLETE STORE UNCHANGED \xc2\xb7 YES") != len(MODES):
        raise RuntimeError("A Ctrl-C path changed or failed to verify the Store.")
    help_text = (CAPTURE_DIR / "11-help-entry.txt").read_text(encoding="utf-8")
    if "Q/Esc close" not in help_text:
        raise RuntimeError("Help entry did not render the real close keys.")


if __name__ == "__main__":
    main()
