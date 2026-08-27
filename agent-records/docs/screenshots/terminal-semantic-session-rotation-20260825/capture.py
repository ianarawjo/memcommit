"""Capture terminal-session rotation launchers and retained Review evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
UP = "\x1b[A"
DOWN = "\x1b[B"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("session_rotation_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _store_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _prepare_atomize_store(root: Path):
    import memcommit.application.ops as ops
    from memcommit.application.operations.atomize.workflow import open_or_create_atomize_workbench
    from memcommit.persistence.store import MemoryStore
    from tests.test_atomize_workbench import AggregateProvider

    store = MemoryStore(root=root)
    context = ops.init("capture/atomize-policy")
    ops.add(context, "Use the same NFC for access.")
    store.save(context)
    store.set_current(context.name)
    provider = AggregateProvider()
    first = open_or_create_atomize_workbench(
        store=store,
        ctx=context,
        provider_factory=lambda: provider,
    )
    first.workbench.record_application(
        output_context_name=context.name,
        checkpoint_uid=str(uuid.uuid4()),
    )
    store.save_atomize_workbench(first.workbench)
    second = open_or_create_atomize_workbench(
        store=store,
        ctx=context,
        provider_factory=lambda: provider,
        refresh=True,
    )
    return store, first.analysis.uid, second.analysis.uid, len(provider.payloads)


def _prepare_meld_store(root: Path):
    import memcommit.application.ops as ops
    from memcommit.application.operations.meld.model import MeldSession, meld_canonical_digest
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=root)
    incoming = ops.init("capture/meld-incoming")
    ops.add(incoming, "Incoming policy uses the reviewed label.")
    baseline = ops.init("capture/meld-baseline")
    ops.add(baseline, "Baseline policy keeps its existing scope.")
    store.save(incoming)
    store.save(baseline)
    store.set_current(baseline.name)
    first = MeldSession.create_directional(incoming, baseline)
    first.start_initial_analysis()
    first.keep_review_only()
    store.save_meld_session(first, expected_session_digest=None)
    second = MeldSession.create_directional(incoming, baseline)
    store.save_meld_session(
        second,
        expected_session_digest=meld_canonical_digest(first.to_dict()),
    )
    return store, first.uid, second.uid


def _ambiguity_report(context, memory, *, suffix: str):
    from memcommit.application.reviewing.quality.findings import AmbiguityFinding, AmbiguityReport

    return AmbiguityReport(
        memory_count=len(context.memories),
        findings=(
            AmbiguityFinding(
                memory=memory,
                interpretation="DOMINANT",
                clarification="REQUIRED",
                ordinary_readings=(
                    f"Use the mechanism reading {suffix}.",
                    f"Use the credential reading {suffix}.",
                ),
                reason="The local antecedent permits two ordinary readings.",
                question="Which local reading should guide later semantic work?",
            ),
        ),
    )


def _prepare_review_store(root: Path):
    import memcommit.application.ops as ops
    from memcommit.application.operations.review.model import create_ambiguity_review
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=root)
    context = ops.init("capture/review-policy")
    first_memory = ops.add(context, "Use the same NFC for access.")
    store.save(context)
    store.set_current(context.name)
    first = create_ambiguity_review(
        context,
        _ambiguity_report(context, first_memory, suffix="from the first frame"),
    )
    first.select_choice(0)
    store.save_review_session(first)

    second_memory = ops.add(context, "Keep the same token for renewal.")
    store.save(context)
    second = create_ambiguity_review(
        context,
        _ambiguity_report(context, second_memory, suffix="from the second frame"),
    )
    store.save_review_session(second)
    return store, first.uid, second.uid


def _patch_command_stores(store) -> None:
    import memcommit.commands.atomize.command as atomize_command
    import memcommit.commands.shared.command_wait as command_wait
    import memcommit.commands.meld.command as meld_command
    import memcommit.commands.review.command as review_command
    import memcommit.commands.shared.session_help as session_help
    import memcommit.adapters.interfaces.tui.components.session_help as tui_session_help

    atomize_command.MemoryStore = lambda *args, **kwargs: store
    meld_command.MemoryStore = lambda *args, **kwargs: store
    review_command.MemoryStore = lambda *args, **kwargs: store

    def reject_provider():
        raise AssertionError("Launcher and retained-review capture must be provider-free.")

    atomize_command.connect_codex_chatgpt_provider = reject_provider
    meld_command.connect_codex_chatgpt_provider = reject_provider
    review_command.connect_codex_chatgpt_provider = reject_provider
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()
    tui_session_help.current_help_entries = lambda: ()


def _run_cli(argv: list[str]) -> None:
    import click
    from memcommit.adapters.console.entrypoint import app

    try:
        app(args=argv, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _run_atomize_child(root: Path) -> None:
    store, retained_uid, active_uid, provider_calls = _prepare_atomize_store(root)
    _patch_command_stores(store)
    before = _store_digest(root)
    print("$ mem atomize --sessions", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}", flush=True)
    _run_cli(["atomize", "--sessions"])
    print("\nATOMIZE NEW FLOW · CANCELLED")
    print(f"  RETAINED TERMINAL UID · {retained_uid}")
    print(f"  ACTIVE REFRESH UID · {active_uid}")
    print(f"  DISTINCT UIDS · {retained_uid != active_uid}")
    print(f"  TERMINAL HISTORY COUNT · {len(store.list_atomize_session_history())}")
    print(f"  ACTIVE ANALYSIS STILL PRESENT · {store.load_atomize_analysis(store.load_direct('capture/atomize-policy').uid) is not None}")
    print(f"  PROVIDER CALLS DURING PREPARATION · {provider_calls}")
    print("  PROVIDER CALLS DURING LAUNCHER · 0")
    print(f"  STORE UNCHANGED BY CANCELLED NEW FLOW · {_store_digest(root) == before}", flush=True)


def _run_meld_child(root: Path) -> None:
    store, retained_uid, active_uid = _prepare_meld_store(root)
    _patch_command_stores(store)
    before = _store_digest(root)
    print("$ mem meld --sessions", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}", flush=True)
    _run_cli(["meld", "--sessions"])
    print("\nMELD NEW FLOW · CANCELLED")
    print(f"  RETAINED TERMINAL UID · {retained_uid}")
    print(f"  ACTIVE NEW UID · {active_uid}")
    print(f"  DISTINCT UIDS · {retained_uid != active_uid}")
    print(f"  TERMINAL HISTORY COUNT · {len(store.list_meld_session_history())}")
    print("  PROVIDER CALLS · 0")
    print(f"  STORE UNCHANGED BY CANCELLED NEW FLOW · {_store_digest(root) == before}", flush=True)


def _run_review_child(root: Path) -> None:
    store, retained_uid, active_uid = _prepare_review_store(root)
    _patch_command_stores(store)
    before = _store_digest(root)
    print("$ mem review", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}", flush=True)
    _run_cli(["review"])
    retained = store.load_review_session_by_uid(retained_uid)
    retained_source = store.load_review_session_source(retained_uid)
    print("\nRETAINED AMBIGUITY REVIEW · READ-ONLY VERIFICATION")
    print(f"  RETAINED UID · {retained_uid}")
    print(f"  ACTIVE UID · {active_uid}")
    print(f"  DISTINCT UIDS · {retained_uid != active_uid}")
    print(f"  RETAINED ANSWERS · {retained.answered_count}/{len(retained.items)}")
    print(f"  RETAINED SOURCE MEMORIES · {len(retained_source.memories)}")
    print(f"  ACTIVE SOURCE MEMORIES · {len(store.load_direct('capture/review-policy').memories)}")
    print("  PROVIDER CALLS · 0")
    print(f"  STORE UNCHANGED BY HISTORY VIEW · {_store_digest(root) == before}", flush=True)


def _run_summary_child(results_path: Path) -> None:
    results = results_path.read_text(encoding="utf-8").splitlines()
    print("\x1b[38;2;139;213;255;1mTERMINAL SESSION ROTATION · VERIFICATION\x1b[0m")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print("PROFILE · ISOLATED CAPTURE STORES")
    print()
    for line in results:
        print(f"\x1b[38;2;139;213;202;1mPASS\x1b[0m · {line}")
    print()
    print("EXACT RETRY · resumes the matching UID without a provider call")
    print("DISTINCT TERMINAL FOLLOW-UP · rotates and retains the prior UID")
    print("SAME-FRAME REANALYSIS · explicit --refresh / --restart / --new")
    print("HISTORICAL REVIEW · immutable source snapshot, read-only by UID")
    print()
    print("\x1b[38;2;166;218;149;1mVERIFICATION COMPLETE · 3/3 OPERATION ADAPTERS\x1b[0m", flush=True)


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
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn(kind: str, path: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(path)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_new_flow(
    *,
    kind: str,
    root: Path,
    title: str,
    setup_title: str,
    stems: tuple[str, str, str, str],
    verification_marker: str,
) -> str:
    child, recorder = _spawn(kind, root)
    try:
        child.expect(title)
        _BASE._settle(child)
        _snapshot(recorder, stems[0])
        child.send(UP)
        _BASE._settle(child)
        _snapshot(recorder, stems[1])
        child.send("\r")
        child.expect(setup_title)
        _BASE._settle(child)
        _snapshot(recorder, stems[2])
        child.send("\x1b")
        child.expect(verification_marker)
        child.expect(pexpect.EOF)
        _snapshot(recorder, stems[3])
        raw = recorder.getvalue()
        if "STORE UNCHANGED BY CANCELLED NEW FLOW · True" not in raw:
            raise RuntimeError(f"{kind} cancelled-New verification failed.")
        return f"{kind.upper()} · retained terminal UID + active UID + cancelled New is non-mutating"
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_review(root: Path) -> str:
    child, recorder = _spawn("review", root)
    try:
        child.expect("MEM REVIEW .* SAVED SESSIONS")
        _BASE._settle(child)
        _snapshot(recorder, "09-review-active-and-retained-entry")
        child.send(DOWN)
        _BASE._settle(child)
        _snapshot(recorder, "10-review-retained-history-focused")
        child.send("\r")
        time.sleep(0.8)
        _BASE._settle(child)
        _snapshot(recorder, "11-review-retained-source-opened")
        child.send("q")
        child.expect("RETAINED AMBIGUITY REVIEW .* READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-review-read-only-verification")
        raw = recorder.getvalue()
        if (
            "STORE UNCHANGED BY HISTORY VIEW · True" not in raw
            or "RETAINED SOURCE MEMORIES · 1" not in raw
            or "ACTIVE SOURCE MEMORIES · 2" not in raw
        ):
            raise RuntimeError("Retained Review verification failed.")
        return "REVIEW AMBIGUITIES · old UID reopens its one-Memory snapshot read-only"
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[str] = []
    with tempfile.TemporaryDirectory(prefix="mem-session-rotation-") as directory:
        temp_root = Path(directory)
        results.append(
            _capture_new_flow(
                kind="atomize",
                root=temp_root / "atomize-store",
                title="MEM ATOMIZE .* SESSIONS",
                setup_title="NEW ATOMIZE",
                stems=(
                    "01-atomize-active-and-retained-entry",
                    "02-atomize-new-focused",
                    "03-atomize-new-setup",
                    "04-atomize-cancel-verification",
                ),
                verification_marker="ATOMIZE NEW FLOW .* CANCELLED",
            )
        )
        results.append(
            _capture_new_flow(
                kind="meld",
                root=temp_root / "meld-store",
                title="MELD SESSIONS .* RECENTLY MODIFIED",
                setup_title="NEW MELD",
                stems=(
                    "05-meld-active-and-retained-entry",
                    "06-meld-new-focused",
                    "07-meld-new-setup",
                    "08-meld-cancel-verification",
                ),
                verification_marker="MELD NEW FLOW .* CANCELLED",
            )
        )
        results.append(_capture_review(temp_root / "review-store"))
        results_path = temp_root / "results.txt"
        results_path.write_text("\n".join(results), encoding="utf-8")
        child, recorder = _spawn("summary", results_path)
        try:
            child.expect("VERIFICATION COMPLETE")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "13-common-rule-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    captures = tuple(sorted(OUT.glob("[0-9][0-9]-*.typescript")))
    if len(captures) != 13:
        raise RuntimeError(f"Expected 13 captures, found {len(captures)}.")
    for path in captures:
        raw = path.read_text(encoding="utf-8")
        if "PTY 180 52" not in raw:
            raise RuntimeError(f"{path.name} did not verify its 180x52 PTY.")
        if "\x1b[" not in raw or ("38;" not in raw and "48;" not in raw):
            raise RuntimeError(f"{path.name} did not preserve ANSI color styles.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        path = Path(sys.argv[3])
        if kind == "atomize":
            _run_atomize_child(path)
        elif kind == "meld":
            _run_meld_child(path)
        elif kind == "review":
            _run_review_child(path)
        elif kind == "summary":
            _run_summary_child(path)
        else:
            raise SystemExit(f"Unknown capture child kind: {kind}")
    else:
        main()
