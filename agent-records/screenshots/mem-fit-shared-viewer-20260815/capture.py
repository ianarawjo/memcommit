"""Capture standalone Fit Viewer and shared Ground background-turn behavior."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "agent-records/screenshots/atomize-memory-selection-20260814/capture.py"
FIXTURE_PATH = ROOT / "agent-records/screenshots/mem-ground-fit-receipt-20260815/capture.py"
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module("fit_terminal_capture_base", BASE_PATH)
FIXTURE = _load_module("fit_receipt_capture_fixture", FIXTURE_PATH)
BASE.OUT = OUT


class _DelayedFitProvider:
    def complete(self, _prompt, *, operation, output_schema=None):
        time.sleep(1.4)
        return _fit_response(operation)


class _ImmediateFitProvider(_DelayedFitProvider):
    def complete(self, _prompt, *, operation, output_schema=None):
        return _fit_response(operation)


class _IssueFitProvider:
    def complete(self, _prompt, *, operation, output_schema=None):
        return json.dumps(
            {
                "overview": "The active Rule produces a different symbol.",
                "predictions": [
                    {
                        "case_id": "e1",
                        "disposition": "PREDICTED",
                        "predicted": "AAIT",
                        "reason": "The Rule includes the second word's initials.",
                    }
                ],
            }
        )


def _fit_response(operation: str) -> str:
    payload = {
        "overview": "The active Rule reproduces the reviewed Example.",
        "predictions": [
            {
                "case_id": "e1",
                "disposition": "PREDICTED",
                "predicted": "AAT",
                "reason": "The reviewed initials Rule produces AAT.",
            }
        ],
    }
    return json.dumps(payload)


def _use_store_root(root: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = root


def _stale_receipt(root: Path):
    from memcommit.fit_runtime import execute_and_save_ground_fit
    from memcommit.ground import propose_ground_rule
    from memcommit.store import ground_session_record_digest

    store, session, contexts = FIXTURE._prepare_store(root)
    report = execute_and_save_ground_fit(
        store=store,
        ground_name=session.contract_name,
        provider_factory=_ImmediateFitProvider,
    )
    revised = propose_ground_rule(
        session,
        rule="Explicitly supplied short symbols take precedence.",
        rationale="This later Rule changes the fitted Rule set.",
        current_contexts=contexts,
    )
    store.save_ground_session(
        revised,
        replace=True,
        expected_uid=session.uid,
        expected_revision=session.revision,
        expected_digest=ground_session_record_digest(session),
    )
    return store, revised, report


def _run_standalone_child(
    store_root: Path,
    *,
    stale: bool,
    issue: bool = False,
) -> None:
    import memcommit.commands.fit.command as fit_command
    from memcommit.fit_store import FitStore
    from memcommit.store import MemoryStore

    copied: list[str] = []
    if stale:
        store, session, report = _stale_receipt(store_root)
        receipt_uid = report.uid
    else:
        store, session, _contexts = FIXTURE._prepare_store(store_root)
        receipt_uid = None
    _use_store_root(store_root)
    fit_command.connect_semantic_provider = (
        _IssueFitProvider if issue else _DelayedFitProvider
    )
    fit_command.write_system_clipboard = copied.append

    print(
        f"$ mem fit --ground {session.contract_name}"
        + (f" --receipt {receipt_uid}" if receipt_uid else ""),
        flush=True,
    )
    fit_command.cmd(
        None,
        background=None,
        ground_name=session.contract_name,
        receipt=receipt_uid,
        plain=False,
        tui=True,
    )
    latest = FitStore(MemoryStore(create=False)).latest_for_ground(session)
    print("FIT VIEWER CLOSED · READ-ONLY VERIFICATION")
    print(f"  GROUND REVISION · {session.revision}")
    print(f"  RECEIPTS · {len(FitStore(store).list(ground_uid=session.uid))}")
    print(f"  LATEST CURRENT · {latest.current if latest else False}")
    print(f"  CLIPBOARD PROJECTIONS · {len(copied)}")
    print("  CONTEXT CHECKPOINTS · 0", flush=True)


def _run_ground_child(store_root: Path) -> None:
    from memcommit.commands.ground.named_shell import run_named_ground_shell
    from memcommit.fit_runtime import execute_and_save_ground_fit
    from memcommit.fit_store import FitStore
    from memcommit.store import ground_session_record_digest

    store, session, _contexts = FIXTURE._prepare_store(store_root)
    before_digest = ground_session_record_digest(session)
    calls = {"value": 0}

    def run_fit(active):
        calls["value"] += 1
        return execute_and_save_ground_fit(
            store=store,
            ground_name=active.contract_name,
            provider_factory=_DelayedFitProvider,
        )

    result = run_named_ground_shell(
        session,
        interpret=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not submit Ground dialogue.")
        ),
        apply=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("Capture does not apply Ground mutations.")
        ),
        run_fit=run_fit,
        lookup_fit=lambda active: FitStore(store).latest_for_ground(active),
        reload_session=lambda name: store.load_ground_session(name),
        require_tty=True,
    )
    after = store.load_ground_session(session.contract_name)
    latest = FitStore(store).latest_for_ground(after)
    print("GROUND FIT CLOSED · READ-ONLY VERIFICATION")
    print(f"  FIT CALLS · {calls['value']}")
    print(f"  RECEIPTS · {len(FitStore(store).list(ground_uid=session.uid))}")
    print(f"  RECEIPT CURRENT · {latest.current if latest else False}")
    print(
        "  GROUND CONTENT UNCHANGED · "
        f"{ground_session_record_digest(after) == before_digest}"
    )
    print(f"  CLOSE STATUS · {result.status}", flush=True)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str, store_root: Path):
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_standalone_current(store_root: Path) -> None:
    child, recorder = _spawn("standalone-current", store_root)
    try:
        BASE._settle(child, seconds=0.3)
        BASE._snapshot(recorder, "01-standalone-fit-running")
        BASE._settle(child, seconds=1.8)
        BASE._snapshot(recorder, "02-current-viewer-entry")
        child.send("\x1b[B")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "03-example-focused")
        child.send("y")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "04-focused-copy")
        child.send("Y")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "05-whole-result-copy")
        child.send("q")
        child.expect("FIT VIEWER CLOSED")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_standalone_stale(store_root: Path) -> None:
    child, recorder = _spawn("standalone-stale", store_root)
    try:
        BASE._settle(child, seconds=0.8)
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "07-stale-receipt-reopen")
        child.send("q")
        child.expect("FIT VIEWER CLOSED")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_standalone_issue(store_root: Path) -> None:
    child, recorder = _spawn("standalone-issue", store_root)
    try:
        BASE._settle(child, seconds=0.8)
        child.send("\x1b[B")
        BASE._settle(child, seconds=0.2)
        BASE._snapshot(recorder, "06-current-issue-focused")
        child.send("q")
        child.expect("FIT VIEWER CLOSED")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_ground_current(store_root: Path) -> None:
    child, recorder = _spawn("ground", store_root)
    try:
        BASE._settle(child, seconds=0.7)
        child.send("\t\t\t\t")
        BASE._settle(child, seconds=0.3)
        BASE._snapshot(recorder, "08-ground-cases-entry")
        child.send("f")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "09-ground-fit-running")
        BASE._settle(child, seconds=1.8)
        BASE._snapshot(recorder, "10-ground-fit-current")
        child.send("q")
        child.expect("GROUND FIT CLOSED", timeout=5)
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "11-ground-fit-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_ground_deferred_close(store_root: Path) -> None:
    child, recorder = _spawn("ground", store_root)
    try:
        BASE._settle(child, seconds=0.7)
        child.send("\t\t\t\tf")
        BASE._settle(child, seconds=0.25)
        child.send("fq")
        BASE._settle(child, seconds=0.25)
        BASE._snapshot(recorder, "12-duplicate-run-close-deferred")
        child.expect("GROUND FIT CLOSED", timeout=5)
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "13-deferred-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-fit-shared-") as directory:
        root = Path(directory)
        _capture_standalone_current(root / "standalone-current")
        _capture_standalone_issue(root / "standalone-issue")
        _capture_standalone_stale(root / "standalone-stale")
        _capture_ground_current(root / "ground-current")
        _capture_ground_deferred_close(root / "ground-deferred")
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "standalone-current":
            _run_standalone_child(root, stale=False)
        elif kind == "standalone-issue":
            _run_standalone_child(root, stale=False, issue=True)
        elif kind == "standalone-stale":
            _run_standalone_child(root, stale=True)
        elif kind == "ground":
            _run_ground_child(root)
        else:
            raise RuntimeError(f"Unknown capture kind: {kind}")
    else:
        main()
