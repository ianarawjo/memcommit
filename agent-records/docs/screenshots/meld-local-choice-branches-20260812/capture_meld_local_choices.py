"""Capture provider-free Meld choice persistence in a real 180x52 PTY."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
HELPERS = ROOT / "agent-records/docs/screenshots/study-full-replay-20260811"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HELPERS))

import capture_init_study as capture  # noqa: E402


capture.OUT = OUT


def _environment() -> dict[str, str]:
    environment = capture._environment()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return environment


def _spawn_child(store_root: Path, mode: str) -> tuple[pexpect.spawn, object]:
    command = (
        f"stty rows {capture.ROWS} cols {capture.COLS}; stty size; "
        "exec "
        + shlex.join(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--child",
                str(store_root),
                "--mode",
                mode,
            ]
        )
    )
    recorder = capture._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(capture.ROWS, capture.COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _create_fixture(store_root: Path):
    import memcommit.ops as ops
    from memcommit.comparison import ComparisonInput
    from memcommit.comparison_provider import analyze_comparison
    from memcommit.meld import MeldSession
    from memcommit.store import MemoryStore
    from tests.test_meld import Task2CompareProvider

    store = MemoryStore(root=store_root)
    left = ops.init("capture/advisor1")
    ops.add(left, "Budget CAD 20–30 per hour, including travel time.")
    right = ops.init("capture/advisor2")
    ops.add(right, "Pay in cash, by e-transfer, or by gift card.")
    target = ops.init("capture/proposal-workspace")
    for context in (left, right, target):
        store.save(context)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        Task2CompareProvider(),
    )
    session = MeldSession.create_symmetric_from_comparison(analysis, target)
    store.save_meld_session(session, expected_session_digest=None)
    return store, session


def _load_fixture(store_root: Path):
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    target = store.load_direct("capture/proposal-workspace")
    session = store.load_meld_session(target.uid)
    if session is None:
        raise RuntimeError("Captured Meld session is missing.")
    return store, session


def _child(store_root: Path, mode: str) -> None:
    if mode == "open":
        store, session = _create_fixture(store_root)
    else:
        store, session = _load_fixture(store_root)
    if mode == "verify":
        branches = store.load_meld_choice_branches(session)
        print("MELD LOCAL CHOICE BRANCHES · READ-ONLY")
        print(f"SESSION · {session.uid}")
        print(f"ASSESSMENT · {branches.assessment_digest}")
        print(f"SAVED CHOICES · {len(branches.branches)}")
        print(json.dumps(branches.to_dict(), indent=2, ensure_ascii=False))
        print("PROVIDER CALLS · 0")
        return

    from memcommit.commands.meld.command import _run_interactive

    def provider_factory():
        raise RuntimeError("A local Meld choice must not connect a provider.")

    _run_interactive(
        store=store,
        session=session,
        provider_factory=provider_factory,
    )
    branches = store.load_meld_choice_branches(session)
    print(f"LOCAL CHOICE SAVE RECEIPT · {len(branches.branches)} SAVED")
    print("PROVIDER CALLS · 0")


def _wait_for(child, recorder, expected: str, *, seconds: float = 10.0) -> str:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        capture._pump(child, recorder, seconds=0.05)
        visible = capture._visible_text(recorder)
        if expected in visible:
            return visible
        time.sleep(0.05)
    raise RuntimeError(
        f"Timed out waiting for {expected!r}. Visible: {visible[-2000:]!r}"
    )


def _capture_interaction(store_root: Path, *, reopen: bool) -> None:
    mode = "reopen" if reopen else "open"
    child, recorder = _spawn_child(store_root, mode)
    try:
        _wait_for(child, recorder, "capture/proposal-workspace · CURRENT TARGET")
        capture._pump(child, recorder, seconds=0.4)
        if not reopen:
            capture._snapshot(recorder, "01-initial-assessment")

        child.send("\t\x1b[B\r")
        capture._pump(child, recorder, seconds=0.7)
        _wait_for(child, recorder, "SOURCE CLAIMS")
        capture._snapshot(
            recorder,
            "05-reopened-choice-restored" if reopen else "02-issue-detail",
        )
        if not reopen:
            child.send("\t\r")
            capture._pump(child, recorder, seconds=0.7)
            visible = capture._visible_text(recorder)
            if "✓" not in visible:
                raise RuntimeError("The first Meld option was not selected.")
            capture._snapshot(recorder, "03-choice-selected")
        child.send("q")
        capture._pump(child, recorder, seconds=20, require_eof=True)
        raw = recorder.getvalue()
        expected = "1 SAVED"
        if expected not in raw or "PROVIDER CALLS · 0" not in raw:
            raise RuntimeError("Local choice save receipt is incomplete.")
        if not reopen:
            capture._snapshot(recorder, "04-choice-save-receipt")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_verification(store_root: Path) -> None:
    child, recorder = _spawn_child(store_root, "verify")
    capture._pump(child, recorder, seconds=20, require_eof=True)
    raw = recorder.getvalue()
    for value in ("SAVED CHOICES · 1", '"option_uid"', "PROVIDER CALLS · 0"):
        if value not in raw:
            raise RuntimeError(f"Choice verification missed {value!r}.")
    capture._snapshot(recorder, "06-read-only-choice-verification")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-meld-choice-capture-") as raw:
        store_root = Path(raw) / "store"
        _capture_interaction(store_root, reopen=False)
        _capture_interaction(store_root, reopen=True)
        _capture_verification(store_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", type=Path)
    parser.add_argument("--mode", choices=("open", "reopen", "verify"))
    arguments = parser.parse_args()
    if arguments.child is not None:
        if arguments.mode is None:
            raise SystemExit("--mode is required with --child")
        _child(arguments.child, arguments.mode)
    else:
        main()
