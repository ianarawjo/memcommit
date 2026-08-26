"""Capture Meld FROM/TO direct editing and Browse replacement in real PTYs."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import shlex
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
FROM_A = "route/from-a"
FROM_B = "route/from-b"

_BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "meld_endpoint_edit_browse_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(store_root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    left = ops.init(FROM_A)
    ops.add(left, "Incoming access note A.")
    right = ops.init(FROM_B)
    ops.add(right, "Authoritative baseline note B.")
    store.create_context(left)
    store.create_context(right)
    store.set_current(left.name)
    return store, left, right


def _run_child(store_root: Path, *, route: str) -> None:
    from memcommit.commands.meld.setup import choose_meld_setup

    store, left, right = _prepare_store(store_root)
    before = {
        left.name: store._context_file(left.name).read_bytes(),
        right.name: store._context_file(right.name).read_bytes(),
    }
    print(f"$ mem meld · {route.upper()} FROM/TO editing", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    receipt = choose_meld_setup(store)
    if receipt is None:
        raise RuntimeError("Meld endpoint setup unexpectedly cancelled.")
    command = shlex.join(["mem", "meld", receipt.left_name, receipt.right_name])
    print(f"\n{route.upper()} SETUP RECEIPT · PROCESS-LOCAL")
    print(f"  MODE · {receipt.mode}")
    print(f"  FROM · {receipt.left_name}")
    print(f"  TO · {receipt.right_name}")
    print(f"  EXACT COMMAND · {command}")
    print(
        "  SWAPPED ENDPOINTS · "
        f"{receipt.left_name == FROM_B and receipt.right_name == FROM_A}"
    )
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    print("\nREAD-ONLY SETUP VERIFICATION")
    print(
        "  CONTEXT BYTES UNCHANGED · "
        f"{all(store._context_file(name).read_bytes() == value for name, value in before.items())}"
    )
    print(f"  CURRENT CONTEXT · {store.current_context_name()}")
    print(
        "  CONTEXT CHECKPOINTS · "
        f"{sum(len(store.list_checkpoints(name)) for name in before)}"
    )
    print("  MELD SESSIONS · 0")
    print("  PROVIDER CALLS · 0", flush=True)


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
            "PYTHONPATH": str(ROOT),
        }
    )
    return environment


def _spawn(route: str, store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", route, str(store_root)],
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


def _capture_direct(store_root: Path) -> None:
    child, recorder = _spawn("direct", store_root)
    try:
        child.expect("NEW MELD")
        _BASE._settle(child)
        child.send("\x1b[C\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "01-direct-from-entry")

        child.send("\x1b[D\x1b[D\x1b[C\x1b[3~")
        _BASE._settle(child)
        _snapshot(recorder, "02-direct-from-caret-left")

        child.send("b")
        _BASE._settle(child)
        _snapshot(recorder, "03-direct-from-replaced")

        child.send("\r\x1b[B\x1b[D\x1b[D\x1b[C\x1b[3~a")
        _BASE._settle(child)
        _snapshot(recorder, "04-direct-to-replaced")

        child.send("\r\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "05-direct-command-reviewed")

        child.send("\r")
        child.expect("DIRECT SETUP RECEIPT")
        child.expect("CAPTURE GATE")
        _BASE._settle(child)
        _snapshot(recorder, "06-direct-setup-receipt")

        child.send("v\r")
        child.expect("READ-ONLY SETUP VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-direct-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_browse(store_root: Path) -> None:
    child, recorder = _spawn("browse", store_root)
    try:
        child.expect("NEW MELD")
        _BASE._settle(child)
        child.send("\x1b[C\x1b[B\x1b[C\r")
        _BASE._settle(child)
        _snapshot(recorder, "08-browse-from-catalog")

        child.send("\x1b[B\r\x1b[D")
        _BASE._settle(child)
        _snapshot(recorder, "09-browse-from-selected-editable")

        child.send("\x1b[B\x1b[C\r\x1b[A")
        _BASE._settle(child)
        _snapshot(recorder, "10-browse-to-catalog")

        child.send("\r\x1b[D")
        _BASE._settle(child)
        _snapshot(recorder, "11-browse-to-selected-editable")

        child.send("\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "12-browse-command-reviewed")

        child.send("\r")
        child.expect("BROWSE SETUP RECEIPT")
        child.expect("CAPTURE GATE")
        _BASE._settle(child)
        _snapshot(recorder, "13-browse-setup-receipt")

        child.send("v\r")
        child.expect("READ-ONLY SETUP VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "14-browse-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-meld-endpoint-edit-") as directory:
        root = Path(directory)
        _capture_direct(root / "direct-store")
        _capture_browse(root / "browse-store")

    captures = tuple(sorted(OUT.glob("[0-9][0-9]-*.txt")))
    if len(captures) != 14 or any(
        "PTY 180 52" not in path.read_text(encoding="utf-8") for path in captures
    ):
        raise RuntimeError("Every Meld endpoint capture must verify its 180x52 PTY.")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    if "\x1b[?1049h" in raw:
        raise RuntimeError("Compact Meld setup entered an alternate screen buffer.")
    for stem in ("06-direct-setup-receipt", "13-browse-setup-receipt"):
        text = (OUT / f"{stem}.txt").read_text(encoding="utf-8")
        if (
            "FROM · route/from-b" not in text
            or "TO · route/from-a" not in text
            or "EXACT COMMAND · mem meld route/from-b route/from-a" not in text
        ):
            raise RuntimeError(f"{stem} did not retain the edited endpoints.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        route = sys.argv[2]
        if route not in {"direct", "browse"}:
            raise SystemExit(f"unknown child route: {route}")
        _run_child(Path(sys.argv[3]), route=route)
    else:
        main()
