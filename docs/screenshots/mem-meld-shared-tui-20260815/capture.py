"""Capture Meld's shared setup and relocated session screen in 180x52 PTYs."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "meld_shared_tui_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    incoming = ops.init("capture/incoming")
    incoming_focus = ops.add(
        incoming,
        "Only the south vehicle entrance closes during construction.",
    )
    ops.add(incoming, "Pedestrian access remains open through the north entrance.")
    baseline = ops.init("capture/baseline")
    ops.add(baseline, "The south entrance is closed during construction.")
    ops.add(baseline, "The north entrance remains open.")
    empty_result = ops.init("capture/empty-result")
    for context in (incoming, baseline, empty_result):
        store.create_context(context)
    store.set_current(incoming.name)
    return store, incoming, baseline, empty_result, incoming_focus


def _run_setup_child(store_root: Path, *, directional: bool) -> None:
    from memcommit.commands.meld_setup import choose_meld_setup

    store, incoming, baseline, empty_result, incoming_focus = _prepare_store(store_root)
    before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in (incoming, baseline, empty_result)
    }
    label = "DIRECTIONAL" if directional else "SYMMETRIC NEW RESULT"
    print(f"$ mem meld --sessions -> New Meld · {label}", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    receipt = choose_meld_setup(store)
    if receipt is None:
        raise RuntimeError("Meld setup unexpectedly cancelled.")
    print("\nMELD SETUP RECEIPT · PROCESS-LOCAL · NOT RUN")
    print(f"  MODE · {receipt.mode}")
    print(
        "  A · "
        f"{receipt.left_name} · DESCENDANTS={receipt.left_descendants} · "
        f"MEMORY={receipt.left_memory_uid}"
    )
    print(
        "  B · "
        f"{receipt.right_name} · DESCENDANTS={receipt.right_descendants} · "
        f"MEMORY={receipt.right_memory_uid}"
    )
    print(f"  C · {receipt.target_name} · CREATE={receipt.create_target} · NOT CREATED")
    print(
        "  EXPECTED A MEMORY · "
        f"{incoming_focus.uid} · MATCH={receipt.left_memory_uid == incoming_focus.uid}"
    )
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    print("\nREAD-ONLY SETUP VERIFICATION")
    print(f"  CURRENT CONTEXT · {store.current_context_name()}")
    print(
        "  EXISTING CONTEXT BYTES UNCHANGED · "
        f"{all(store._context_file(name).read_bytes() == value for name, value in before.items())}"
    )
    print(
        "  RESULT EXISTS · "
        f"{receipt.target_name in store.list_context_names() if receipt.target_name else False}"
    )
    print(
        "  CONTEXT CHECKPOINTS · "
        f"{sum(len(store.list_checkpoints(name)) for name in before)}"
    )
    print("  MELD SESSIONS · 0")
    print("  PROVIDER CALLS · 0", flush=True)


def _run_session_child(store_root: Path) -> None:
    import memcommit.ops as ops
    from memcommit.comparison import ComparisonInput
    from memcommit.comparison_provider import analyze_comparison
    from memcommit.interfaces.tui.operations.meld.screen import run_meld_shell
    from memcommit.meld import MeldSession
    from memcommit.store import MemoryStore
    from tests.test_meld import Task2CompareProvider

    store = MemoryStore(root=store_root)
    left = ops.init("capture/advisor-a")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("capture/advisor-b")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("capture/result")
    for context in (left, right, target):
        store.create_context(context)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(analysis, target)
    store.save_meld_session(session, expected_session_digest=None)
    before = store._context_file(target.name).read_bytes()
    print("$ mem meld · reopen saved session through relocated TUI adapter", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    action = run_meld_shell(session)
    print("\nMELD SESSION VIEW CLOSED · READ-ONLY")
    print("  ADAPTER · memcommit.interfaces.tui.operations.meld.screen.run_meld_shell")
    print(f"  RETURNED ACTION · {action!r}")
    print(f"  SESSION STATE · {session.state}")
    print(
        f"  TARGET BYTES UNCHANGED · {store._context_file(target.name).read_bytes() == before}"
    )
    print(f"  TARGET MEMORIES · {len(store.load_direct(target.name).memories)}")
    print("  PROVIDER CALLS · 0", flush=True)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            # pexpect's PTY records bytes but does not answer terminal CPR.
            # Disable that probe so its timeout warning is not misattributed
            # to the inline application layout under test.
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT),
        }
    )
    return environment


def _spawn(kind: str, store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
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


def _capture_symmetric(store_root: Path) -> None:
    child, recorder = _spawn("symmetric", store_root)
    try:
        child.expect("NEW MELD")
        _BASE._settle(child)
        _snapshot(recorder, "01-symmetric-mode-entry")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02-symmetric-peer-a")

        child.send("\x15capture/")
        _BASE._settle(child)
        _snapshot(recorder, "02a-symmetric-context-matches")

        child.send("\x15capture/incoming")
        _BASE._settle(child)
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "02b-symmetric-browse-trigger")

        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "02c-symmetric-all-allowed-contexts")

        child.send("\x1b")
        _BASE._settle(child)
        child.send("\t\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-symmetric-peer-b")

        child.send("\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "04-new-result-name-entry")

        child.send("capture/new-result")
        _BASE._settle(child)
        _snapshot(recorder, "05-new-result-name-unconfirmed")

        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "06-symmetric-setup-reviewed")

        child.send("\r")
        child.expect("MELD SETUP RECEIPT")
        child.expect("CAPTURE GATE")
        _BASE._settle(child)
        _snapshot(recorder, "07-symmetric-setup-receipt")

        child.send("v\r")
        child.expect("READ-ONLY SETUP VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-symmetric-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_directional(store_root: Path) -> None:
    child, recorder = _spawn("directional", store_root)
    try:
        child.expect("NEW MELD")
        _BASE._settle(child)
        child.send("\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "09-directional-mode-selected")

        child.send("\t\t\t\t\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "09a-directional-memory-choices")

        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "10-directional-incoming-memory")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "11-directional-baseline")

        child.send("\t\t\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "12-directional-baseline-descendants")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "13-directional-memory-disabled")

        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "14-directional-setup-reviewed")

        child.send("\r")
        child.expect("MELD SETUP RECEIPT")
        child.expect("CAPTURE GATE")
        _BASE._settle(child)
        _snapshot(recorder, "15-directional-setup-receipt")

        child.send("v\r")
        child.expect("READ-ONLY SETUP VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "16-directional-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_session(store_root: Path) -> None:
    child, recorder = _spawn("session", store_root)
    try:
        child.expect("capture/result")
        _BASE._settle(child)
        _snapshot(recorder, "17-relocated-session-entry")

        child.send("\t\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "18-relocated-session-issue-detail")

        child.send("\t\r")
        _BASE._settle(child)
        _snapshot(recorder, "19-relocated-session-choice")

        child.send("q")
        child.expect("MELD SESSION VIEW CLOSED")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "20-relocated-session-read-only-receipt")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-meld-shared-tui-") as directory:
        root = Path(directory)
        _capture_symmetric(root / "symmetric-store")
        _capture_directional(root / "directional-store")
        _capture_session(root / "session-store")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    setup_raw = "".join(
        (OUT / name).read_text(encoding="utf-8")
        for name in (
            "08-symmetric-read-only-verification.typescript",
            "16-directional-read-only-verification.typescript",
        )
    )
    if "\x1b[?1049h" in setup_raw:
        raise RuntimeError("Compact Meld setup entered an alternate screen buffer.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "symmetric":
            _run_setup_child(root, directional=False)
        elif kind == "directional":
            _run_setup_child(root, directional=True)
        elif kind == "session":
            _run_session_child(root)
        else:
            raise SystemExit(f"unknown child kind: {kind}")
    else:
        main()
