"""Capture repeated flagless Remove choices in one real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import time

import pexpect


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SUPPORT_PATH = (
    CAPTURE_DIR.parent / "mem-embed-placement-20260813" / "capture.py"
)


def _load_capture_support():
    spec = importlib.util.spec_from_file_location(
        "remove_continuous_capture_support",
        SUPPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the shared color-PTY renderer.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CAPTURE_DIR = CAPTURE_DIR
    return module


SUPPORT = _load_capture_support()


def _configure_store(root: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = root


def _seed_store():
    import memcommit.ops as ops
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore()
    context = ops.init("curation/inbox")
    for uid, content in (
        ("11111111-1111-4111-8111-111111111111", "Remove the expired draft."),
        ("22222222-2222-4222-8222-222222222222", "Remove the duplicate note."),
        ("33333333-3333-4333-8333-333333333333", "Keep the reviewed summary."),
    ):
        context.add(Memory(uid=uid, content=content))
    store.create_context(context)
    store.set_current(context.name)
    return store, context


def _child(store_root: Path) -> None:
    from memcommit.cli import app

    _configure_store(store_root)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    columns, rows = os.get_terminal_size()
    print(f"CAPTURE PTY · {columns}x{rows}", flush=True)
    store, context = _seed_store()
    print(f"CURRENT CONTEXT · {context.name}", flush=True)
    app(
        prog_name="mem",
        args=["remove"],
        standalone_mode=False,
    )

    remaining = store.load_direct(context.name)
    checkpoints = store.list_checkpoints(context.name)
    print("REMOVE SESSION CLOSED · ESC", flush=True)
    print(
        "REMOVE CHECKPOINTS · "
        + " → ".join(entry["command"] for entry in reversed(checkpoints[:2])),
        flush=True,
    )
    print(
        "DURABLE STATE · "
        f"{len(remaining.memories)} Memory remains · two deletions committed",
        flush=True,
    )
    print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
    input()
    print("READ-ONLY VERIFICATION COMMAND · mem show --context curation/inbox")
    app(
        prog_name="mem",
        args=["show", "--context", context.name],
        standalone_mode=False,
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _settle(child, raw: bytearray, *, delay: float = 0.7) -> None:
    time.sleep(delay)
    while True:
        try:
            raw.extend(child.read_nonblocking(size=65536, timeout=0.03))
        except (pexpect.TIMEOUT, pexpect.EOF):
            return


def _wait_for(
    child,
    raw: bytearray,
    marker: bytes,
    *,
    timeout: float = 8.0,
) -> None:
    deadline = time.monotonic() + timeout
    while marker not in raw:
        if time.monotonic() >= deadline:
            tail = bytes(raw[-12000:]).decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Timed out waiting for {marker!r}. Recent PTY stream:\n{tail}"
            )
        try:
            raw.extend(child.read_nonblocking(size=65536, timeout=0.1))
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            break
    _settle(child, raw, delay=0.2)


def _screen(stem: str, raw: bytearray) -> str:
    SUPPORT._render_snapshot(stem, bytes(raw))
    return (CAPTURE_DIR / f"{stem}.txt").read_text(encoding="utf-8")


def _capture(store_root: Path) -> tuple[dict[str, str], bytes]:
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
        cwd=str(REPOSITORY_ROOT),
        env=_environment(),
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )
    raw = bytearray()
    _wait_for(child, raw, b"Delete or Remove")
    screens = {"01-session-entry": _screen("01-session-entry", raw)}

    child.send(b"\x1b[B")
    _settle(child, raw)
    screens["02-first-item-focused"] = _screen("02-first-item-focused", raw)

    child.send(b"\r")
    _settle(child, raw)
    screens["03-first-removed-next-focused"] = _screen(
        "03-first-removed-next-focused",
        raw,
    )

    child.send(b"\r")
    _settle(child, raw)
    screens["04-second-removed-next-focused"] = _screen(
        "04-second-removed-next-focused",
        raw,
    )

    child.send(b"\x1b")
    _wait_for(child, raw, b"REMOVE SESSION CLOSED")
    screens["05-esc-close-receipts"] = _screen("05-esc-close-receipts", raw)

    child.send(b"\r")
    while child.isalive():
        try:
            raw.extend(child.read_nonblocking(size=65536, timeout=0.2))
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            break
    child.close()
    screens["06-read-only-verification"] = _screen(
        "06-read-only-verification",
        raw,
    )
    if child.exitstatus != 0:
        raise RuntimeError(
            f"Capture child failed: exit={child.exitstatus}, signal={child.signalstatus}"
        )
    return screens, bytes(raw)


def _verify(screens: dict[str, str], raw: bytes, store_root: Path) -> None:
    entry = screens["01-session-entry"]
    first = screens["02-first-item-focused"]
    after_first = screens["03-first-removed-next-focused"]
    after_second = screens["04-second-removed-next-focused"]
    closed = screens["05-esc-close-receipts"]
    verified = screens["06-read-only-verification"]

    required = {
        "entry title": (entry, "Delete or Remove · SELECT A CONTEXT OR DIRECT ITEM"),
        "close footer": (entry, "Esc/q close"),
        "first target focus": (first, "› [memory 11111111] Remove the expired draft."),
        "next target focus": (
            after_first,
            "› [memory 22222222] Remove the duplicate note.",
        ),
        "first footer receipt": (
            after_first,
            'REMOVED · memory [11111111]: "Remove the expired draft."',
        ),
        "surviving peer after first deletion": (after_first, "[memory 33333333]"),
        "final target focus": (
            after_second,
            "› [memory 33333333] Keep the reviewed summary.",
        ),
        "second footer receipt": (
            after_second,
            'REMOVED · memory [22222222]: "Remove the duplicate note."',
        ),
        "close receipt": (closed, "REMOVE SESSION CLOSED · ESC"),
        "two checkpoints": (closed, "REMOVE CHECKPOINTS · remove → remove"),
        "read-only command": (
            verified,
            "READ-ONLY VERIFICATION COMMAND · mem show --context curation/inbox",
        ),
        "remaining Memory": (verified, "Keep the reviewed summary."),
    }
    missing = [label for label, (screen, value) in required.items() if value not in screen]
    if missing:
        raise RuntimeError("Capture verification missing: " + ", ".join(missing))
    if "CAPTURE PTY · 180x52".encode() not in raw:
        raise RuntimeError("Capture did not verify the live 180x52 PTY.")
    if (
        "[memory 11111111]" in after_first
        or "[memory 22222222]" in after_second
    ):
        raise RuntimeError("A deleted Memory remained visible after picker refresh.")
    if not re.search(rb"\x1b\[[0-9;]*38;5;", raw):
        raise RuntimeError("Capture did not preserve the expected ANSI foregrounds.")
    if b"\x1b[0;38;5;210;1m REMOVED" not in raw:
        raise RuntimeError("The footer did not use the semantic remove color.")
    first_footer_raw = (
        CAPTURE_DIR / "03-first-removed-next-focused.typescript"
    ).read_bytes()
    removed_index = first_footer_raw.rfind(b"REMOVED")
    content_index = first_footer_raw.find(b"Remove the", removed_index)
    reset_index = first_footer_raw.find(b"\x1b[0m", removed_index)
    if not removed_index < content_index < reset_index:
        raise RuntimeError("The removed Memory detail did not retain REMOVE color.")
    if raw.count(b"\x1b[?1049h") != 1 or raw.count(b"\x1b[?1049l") != 1:
        raise RuntimeError("Remove reopened the full-screen picker application.")
    if b"\x1b[32mRemoved [" in raw:
        raise RuntimeError("Remove emitted a separate normal-buffer success receipt.")

    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    remaining = store.load_direct("curation/inbox")
    if tuple(remaining.memories) != ("33333333-3333-4333-8333-333333333333",):
        raise RuntimeError("Read-only verification found an unexpected final state.")
    if [entry["command"] for entry in store.list_checkpoints("curation/inbox")[:2]] != [
        "remove",
        "remove",
    ]:
        raise RuntimeError("The session did not retain per-selection checkpoints.")


def main() -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="memcommit-remove-continuous-session-"
    ) as directory:
        store_root = Path(directory) / "store"
        screens, raw = _capture(store_root)
        _verify(screens, raw, store_root)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _child(Path(sys.argv[2]))
    else:
        main()
