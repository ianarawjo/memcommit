"""Capture Result-free, descendant-aware Sever in a 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "sever_endpoint_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    for name, value in {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "STATE_FILE": root / "state.json",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }.items():
        setattr(store_module, name, value)


def _prepare_store(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    _configure_store(root)
    store = MemoryStore()
    contexts = []
    for name, memory in (
        ("capture/reference", "Reference policy is reviewed."),
        ("capture/peer", "Peer policy supplies comparison evidence."),
        ("capture/criteria", "Keep only policy-relevant claims."),
        ("capture/target", "Target policy is the writable baseline."),
    ):
        context = ops.init(name)
        ops.add(context, memory)
        store.create_context(context)
        contexts.append(context)
    store.set_current(contexts[0].name)
    return store


def _store_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class _Provider:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        from memcommit.application.operations.sever.provider import (
            SEVER_PAYLOAD_MARKER,
        )

        assert operation == "sever_context"
        payload = json.loads(prompt.split(SEVER_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        time.sleep(0.8)
        criterion_id = payload["criteria"]["memories"][0]["memory_id"]
        candidates = []
        for index, memory in enumerate(payload["source"]["memories"]):
            candidates.append(
                {
                    "source_memory_id": memory["memory_id"],
                    "decision": "KEEP_SUMMARY" if index == 0 else "FORGET",
                    "proposed_content": (
                        "Step-free access is needed for appointments."
                        if index == 0
                        else ""
                    ),
                    "rationale": (
                        "Keep the accessibility need and remove the obsolete code."
                    ),
                    "criterion_memory_ids": [criterion_id],
                }
            )
        return json.dumps(
            {
                "overview": (
                    "The Source contains an accessibility need and an obsolete code."
                ),
                "application_summary": {
                    "text": (
                        "Accessibility guidance was retained while the obsolete "
                        "entry code was forgotten."
                    ),
                    "source_memory_ids": [
                        payload["source"]["memories"][0]["memory_id"]
                    ],
                    "criterion_memory_ids": [criterion_id],
                },
                "candidates": candidates,
            }
        )


def _run_child(store_root: Path) -> None:
    import click
    import memcommit.application.capabilities.ops as ops
    from memcommit.adapters.console.entrypoint import app
    import memcommit.adapters.console.commands.sever.command as sever_command
    from memcommit.application.operations.sever.session_store import SeverSessionStore

    store = _prepare_store(store_root)
    source = store.load_direct("capture/reference")
    source_memory = next(source.iter_items())
    source.replace(
        type(source_memory)(
            uid=source_memory.uid,
            content="I need a step-free entrance for appointments.",
        )
    )
    store.save(source)
    child_source = ops.init("capture/reference/old-access")
    ops.add(child_source, "The old entry code is 2468.")
    store.create_context(child_source)
    child_criteria = ops.init("capture/criteria/accessibility")
    ops.add(
        child_criteria,
        "Keep accessibility guidance and forget obsolete entry codes.",
    )
    store.create_context(child_criteria)
    store.set_current(source.name)

    source_uid = source.uid
    child_source_uid = child_source.uid
    provider = _Provider()
    sever_command.connect_codex_chatgpt_provider = lambda: provider

    print("$ mem sever", flush=True)
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} COLUMNS × {size.lines} ROWS", flush=True)
    app(args=["sever"], prog_name="mem", standalone_mode=False)
    print(
        "\n\x1b[38;2;139;213;202;1mPRESS V · VERIFY SOURCE OWNERS\x1b[0m",
        flush=True,
    )

    sys.stdin.readline()
    root_after = store.load_direct("capture/reference")
    child_after = store.load_direct("capture/reference/old-access")
    session = SeverSessionStore(store).list()[0]
    application = session.application
    if application is None:
        raise AssertionError("Captured Sever session was not applied.")
    root_checkpoints = store.list_checkpoints(root_after.name)
    child_checkpoints = store.list_checkpoints(child_after.name)
    print("\x1b[2J\x1b[H", end="")
    print("\x1b[38;2;139;213;255;1mSEVER · IN-PLACE OWNER VERIFICATION\x1b[0m")
    print(f"PTY · {size.columns} COLUMNS × {size.lines} ROWS")
    print("PROFILE · ISOLATED EXPLICIT STORE · HOST GRANTS EXCLUDED")
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print()
    print(f"SOURCE ROOT · {root_after.name}")
    print(f"  SAME CONTEXT UID · {root_after.uid == source_uid}")
    print(f"  MEMORY · {next(root_after.iter_items()).content}")
    print(f"  SEVER CHECKPOINTS · {len(root_checkpoints)}")
    print(f"SOURCE DESCENDANT · {child_after.name}")
    print(f"  SAME CONTEXT UID · {child_after.uid == child_source_uid}")
    print(f"  MEMORY COUNT · {len(child_after.memories)}")
    print(f"  SEVER CHECKPOINTS · {len(child_checkpoints)}")
    print()
    print(f"PROVIDER CALLS · {len(provider.payloads)}")
    print(
        "SOURCE MEMORIES IN ONE TURN · "
        f"{len(provider.payloads[0]['source']['memories'])}"
    )
    print(
        "CRITERIA MEMORIES IN ONE TURN · "
        f"{len(provider.payloads[0]['criteria']['memories'])}"
    )
    print(f"OWNER CHECKPOINT RECEIPTS · {len(application.checkpoints)}")
    print("RESULT CONTEXT · NOT SELECTED OR CREATED")
    print(
        "\x1b[38;2;139;213;202;1m"
        "VERIFICATION COMPLETE · BOTH OWNERS STAY IN PLACE\x1b[0m"
    )
    print("PRESS C · CAPTURE CANCEL BRANCH", flush=True)

    sys.stdin.readline()
    before_cancel = _store_digest(store_root)
    print("\x1b[2J\x1b[H", end="")
    print("$ mem sever  # cancel branch", flush=True)
    try:
        app(args=["sever"], prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise
    print(f"CANCEL STORE UNCHANGED · {_store_digest(store_root) == before_cancel}")
    print("CANCEL VERIFICATION · NO NEW SESSION OR CHECKPOINT", flush=True)


def _spawn(store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    environment = _BASE._environment()
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _settle(child: pexpect.spawn) -> None:
    _BASE._settle(child, seconds=0.35)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".txt", ".typescript"):
        for path in OUT.glob(f"[0-9][0-9]-*{suffix}"):
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="sever-shared-endpoint-") as directory:
        child, recorder = _spawn(Path(directory) / ".mem")
        try:
            child.expect("NEW SEVER")
            _settle(child)
            _snapshot(recorder, "01-entry")

            child.send("\t\t ")
            _settle(child)
            _snapshot(recorder, "02-source-root-only")

            child.send("\t\r")
            child.expect("MEMORY · SOURCE")
            _settle(child)
            _snapshot(recorder, "03-source-memory-preview")

            child.send("\x1b")
            child.send("\x1b[Z ")
            _settle(child)
            _snapshot(recorder, "04-source-descendants")

            child.send("\x1b[B\t\r")
            child.expect("CONTEXTS · CRITERIA")
            _settle(child)
            _snapshot(recorder, "05-criteria-browse")

            child.send("\x1b\x1b[Z\x15capture/criteria\t\t\t\t")
            _settle(child)
            _snapshot(recorder, "06-two-role-start-review")

            child.send("\r")
            child.expect("SEVER APPLIED")
            child.expect("PRESS V")
            _settle(child)
            _snapshot(recorder, "07-in-place-success-receipt")

            child.send("v\r")
            child.expect("VERIFICATION COMPLETE")
            child.expect("PRESS C")
            _settle(child)
            _snapshot(recorder, "08-owner-verification")

            child.send("c\r")
            child.expect("NEW SEVER")
            child.send("\x1b")
            child.expect("CANCEL VERIFICATION")
            _settle(child)
            _snapshot(recorder, "09-cancelled-no-mutation")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)

    raw = recorder.getvalue()
    if "\x1b[38;2" not in raw and "\x1b[48;2" not in raw:
        raise AssertionError("Capture stream did not contain expected true-color ANSI.")
    for marker in (
        "CONTEXTS · 2 UPDATED IN PLACE",
        "SOURCE MEMORIES IN ONE TURN · 2",
        "CRITERIA MEMORIES IN ONE TURN · 2",
        "OWNER CHECKPOINT RECEIPTS · 2",
        "RESULT CONTEXT · NOT SELECTED OR CREATED",
        "CANCEL STORE UNCHANGED · True",
    ):
        if marker not in raw:
            raise AssertionError(f"Missing Sever capture marker: {marker}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
