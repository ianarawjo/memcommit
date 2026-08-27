"""Capture positional and explicit endpoint routes in real 180x52 PTYs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Literal

import click
import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("context_positional_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_store(store_root: Path) -> None:
    import memcommit.store as store_module

    paths = {
        "STORE_DIR": store_root,
        "CONTEXTS_DIR": store_root / "contexts",
        "QUERY_SOURCES_DIR": store_root / "query-sources",
        "STATE_FILE": store_root / "state.json",
        "IMPACT_PLAN_FILE": store_root / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_root / "staged-update.json",
        "REVIEW_SESSION_FILE": store_root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": store_root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": store_root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, path in paths.items():
        setattr(store_module, name, path)


class _CompareProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "compare_contexts"
        from memcommit.comparison_provider import COMPARISON_PAYLOAD_MARKER

        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        reference_id = payload["frames"][0]["memories"][0]["memory_id"]
        compared_id = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "Both peers describe a review window with different bounds.",
                "reports": {
                    "both": "",
                    "differences": "Reference says seven days; peer says fourteen days.",
                    "reference_only": "",
                    "compared_only": "",
                },
                "relations": [
                    {
                        "relation_key": "review-window",
                        "reference_memory_ids": [reference_id],
                        "compared_memory_ids": [compared_id],
                        "kind": "CONFLICT",
                        "status": "UNRESOLVED",
                        "summary": "The supported review windows differ.",
                        "reason": "Neither equal-authority peer can silently win by order.",
                    }
                ],
                "issues": [
                    {
                        "issue_key": "review-window",
                        "relation_keys": ["review-window"],
                        "priority": "REQUIRED",
                        "title": "Review window",
                        "question": "Which reviewed window should later work preserve?",
                        "why_it_matters": "Peer order cannot establish authority.",
                        "options": [
                            {
                                "label": "Retain both windows",
                                "text": "Preserve both peer-supported windows.",
                            },
                            {
                                "label": "Keep scoped alternatives",
                                "text": "Keep each window with its source scope.",
                            },
                        ],
                    }
                ],
            }
        )


class _SeverProvider:
    calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        type(self).calls += 1
        assert operation == "sever_context"
        from memcommit.sever_provider import SEVER_PAYLOAD_MARKER

        payload = json.loads(prompt.split(SEVER_PAYLOAD_MARKER, 1)[1])
        source_id = payload["source"]["memories"][0]["memory_id"]
        criterion_id = payload["criteria"]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "The local Result should retain only the access need.",
                "application_summary": {
                    "text": "The access need was retained in a minimized form.",
                    "source_memory_ids": [source_id],
                    "criterion_memory_ids": [criterion_id],
                },
                "candidates": [
                    {
                        "source_memory_id": source_id,
                        "decision": "KEEP_SUMMARY",
                        "proposed_content": "Needs step-free access.",
                        "rationale": "The criterion retains necessary access information.",
                        "criterion_memory_ids": [criterion_id],
                    }
                ],
            }
        )


def _invoke(argv: list[str]) -> int:
    from memcommit.cli import app

    print("$ mem " + " ".join(argv), flush=True)
    try:
        result = app(args=argv, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        return error.exit_code
    return result if isinstance(result, int) else 0


def _context(store, name: str, content: str):
    import memcommit.application.ops as ops

    context = ops.init(name)
    ops.add(context, content)
    store.create_context(context)
    return context


def _run_help(operation: str) -> None:
    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    exit_code = _invoke([operation, "-h"])
    print(f"HELP EXIT · {exit_code}")


def _run_merge() -> None:
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    store = MemoryStore()
    shared_uid = "00000000-0000-4000-8000-000000000001"
    source = _context(
        store,
        "capture/merge/source",
        "Source-only structural addition.",
    )
    source.add(Memory(uid=shared_uid, content="Source says the library closes at 6."))
    store.save(source, expected_context_digest=source._store_digest)
    target = _context(
        store,
        "capture/merge/target",
        "Target-only retained fact.",
    )
    target.add(Memory(uid=shared_uid, content="Target says the library closes at 5."))
    store.save(target, expected_context_digest=target._store_digest)
    store.set_current(target.name)

    exit_code = _invoke(["merge"])
    merged = store.load_direct(target.name)
    print(
        "MERGE VERIFICATION · "
        f"EXIT {exit_code} · CURRENT {store.current_context_name()} · "
        f"TARGET MEMORIES {len(tuple(merged.iter_items()))} · "
        f"CHECKPOINTS {len(store.list_checkpoints(target.name))}",
        flush=True,
    )


def _run_compare() -> None:
    from memcommit.commands import compare as compare_command
    from memcommit.comparison_store import comparison_analyses_dir
    from memcommit.store import MemoryStore

    store = MemoryStore()
    reference = _context(
        store,
        "capture/compare/reference",
        "Review publication within seven days.",
    )
    peer = _context(
        store,
        "capture/compare/peer",
        "Review publication within fourteen days.",
    )
    _context(store, "capture/orientation", "Current orientation marker.")
    store.set_current("capture/orientation")
    compare_command.connect_codex_chatgpt_provider = lambda: _CompareProvider()

    exit_code = _invoke(["compare", reference.name, peer.name, "--snapshot"])
    print("COMPARE REPORT PAUSE", flush=True)
    sys.stdin.readline()
    saved_count = len(tuple(comparison_analyses_dir(store).glob("*.json")))
    print(
        "COMPARE VERIFICATION · "
        f"EXIT {exit_code} · CURRENT {store.current_context_name()} · "
        f"SAVED {saved_count}",
        flush=True,
    )


def _run_sever(*, mode: Literal["SELF_DEFAULT", "OTHER_SAVE"]) -> None:
    from memcommit.commands import sever as sever_command
    from memcommit.store import MemoryStore

    store = MemoryStore()
    _context(store, "capture/sever", "Namespace marker.")
    source = _context(
        store,
        "capture/sever/source",
        "I need a step-free entrance.",
    )
    criteria = _context(
        store,
        "capture/sever/criteria",
        "Retain only necessary access information.",
    )
    _context(store, "capture/orientation", "Current orientation marker.")
    store.set_current("capture/orientation")
    source_uid = source.uid
    source_memory_uid = next(iter(source.memories))
    source_before = source.to_dict()
    _SeverProvider.calls = 0
    sever_command.connect_codex_chatgpt_provider = lambda: _SeverProvider()

    argv = ["sever", source.name, criteria.name]
    if mode == "OTHER_SAVE":
        argv.extend(("capture/sever/result", "--accept"))
    exit_code = _invoke(argv)
    if mode == "SELF_DEFAULT":
        print("SEVER RECEIPT PAUSE", flush=True)
        sys.stdin.readline()
    source_after = store.load_direct(source.name)
    source_memory_uids = tuple(source_after.memories)
    print(
        ("SELF-SAVE" if mode == "SELF_DEFAULT" else "OTHER-SAVE")
        + " VERIFICATION · "
        f"EXIT {exit_code} · CURRENT {store.current_context_name()} · "
        f"SOURCE UID PRESERVED {source_after.uid == source_uid} · "
        f"MEMORY UID PRESERVED {source_memory_uids == (source_memory_uid,)} · "
        f"SOURCE MEMORIES {len(tuple(source_after.iter_items()))} · "
        f"SOURCE CHANGED {source_after.to_dict() != source_before} · "
        f"OTHER RESULT {store.context_exists('capture/sever/result')} · "
        f"CHECKPOINTS {len(store.list_checkpoints(source.name))} · "
        f"PROVIDER CALLS {_SeverProvider.calls}",
        flush=True,
    )


def _run_child(kind: str) -> None:
    with tempfile.TemporaryDirectory(prefix="mem-context-positional-") as directory:
        _configure_store(Path(directory) / ".mem")
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        if kind.startswith("help-"):
            _run_help(kind.removeprefix("help-"))
        elif kind == "merge":
            _run_merge()
        elif kind == "compare":
            _run_compare()
        elif kind == "sever":
            _run_sever(mode="SELF_DEFAULT")
        elif kind == "sever-other":
            _run_sever(mode="OTHER_SAVE")
        else:
            raise SystemExit(f"unknown child kind: {kind}")


def _environment() -> dict[str, str]:
    environment = _BASE._environment()
    environment.update(
        {
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, object]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_help(kind: str, stem: str) -> None:
    child, recorder = _spawn("help-" + kind)
    try:
        child.expect("HELP EXIT · 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, stem)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_merge() -> None:
    child, recorder = _spawn("merge")
    try:
        child.expect("NEW MERGE")
        child.send("\t\t\t\r")
        child.expect("MERGE REVIEW")
        _BASE._settle(child, seconds=0.6)
        _snapshot(recorder, "04-merge-positional-conflict")

        child.send("\t\r")
        _BASE._settle(child, seconds=0.6)
        _snapshot(recorder, "05-merge-positional-exact-review")
        review_text = (OUT / "05-merge-positional-exact-review.txt").read_text()
        if "capture/merge/source capture/merge/target" not in review_text:
            raise RuntimeError("Merge exact review did not show positional endpoints.")

        child.send("\r")
        _BASE._settle(child, seconds=0.9)
        _snapshot(recorder, "06-merge-positional-success")
        child.send("\r")
        child.expect("MERGE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-merge-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_compare() -> None:
    child, recorder = _spawn("compare")
    try:
        child.expect("COMPARE REPORT PAUSE")
        _BASE._settle(child, seconds=0.6)
        _snapshot(recorder, "08-compare-positional-report")
        child.send("\r")
        child.expect("COMPARE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-compare-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_sever() -> None:
    child, recorder = _spawn("sever")
    try:
        child.expect("SEVER RECEIPT PAUSE")
        _BASE._settle(child, seconds=0.5)
        _snapshot(recorder, "10-sever-default-self-save-receipt")
        child.send("\r")
        child.expect("SELF-SAVE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "11-sever-self-save-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("sever-other")
    try:
        child.expect("OTHER-SAVE VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-sever-other-save-receipt-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_help("merge", "01-merge-help")
    _capture_help("compare", "02-compare-help")
    _capture_help("sever", "03-sever-help")
    _capture_merge()
    _capture_compare()
    _capture_sever()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2" not in raw and "38;5" not in raw:
        raise RuntimeError("Capture set contains no color foreground ANSI.")
    if "48;2" not in raw and "48;5" not in raw:
        raise RuntimeError("Capture set contains no color background ANSI.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    arguments = parser.parse_args()
    if arguments.child:
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(arguments.child)
    else:
        _capture()


if __name__ == "__main__":
    main()
