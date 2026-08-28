"""Capture the default transient Compare path in a 180x52 color PTY."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("compare_summary_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = root


def _prepare_store(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    _configure_store(root)
    store = MemoryStore()
    reference = ops.init("capture/reference")
    ops.add(reference, "Keep the proposal concise.")
    ops.add(reference, "Use descriptive headings.")
    peer = ops.init("capture/peer")
    ops.add(peer, "The proposal must be concise.")
    ops.add(peer, "Prefer active voice.")
    store.create_context(reference)
    store.create_context(peer)
    store.set_current(reference.name)
    return store, reference, peer


def _context_digest(store, name: str) -> str:
    return hashlib.sha256(store._context_file(name).read_bytes()).hexdigest()


class _Provider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "compare_summary"
        assert output_schema is not None
        payload = json.loads(prompt.split("COMPARISON SUMMARY PAYLOAD:\n", 1)[1])
        assert payload["ruleset"]["ruleset_version"] == "compact-peer-relation-v3"
        assert payload["length"] == {"limit": 80, "unit": "words"}
        assert all(
            row["role"] == "PRIMARY"
            for frame in payload["frames"]
            for row in frame["memories"]
        )
        reference = [row["id"] for row in payload["frames"][0]["memories"]]
        peer = [row["id"] for row in payload["frames"][1]["memories"]]
        # Keep the real interactive wait shell visible long enough to capture.
        time.sleep(2.5)
        return json.dumps(
            {
                "text": (
                    "Both peers require the proposal to remain concise, but "
                    "the reference additionally asks for descriptive headings "
                    "while the peer prefers active voice."
                ),
                "source_ids": [*reference, *peer],
            }
        )


def _run_child(root: Path) -> None:
    import memcommit.adapters.console.commands.compare.command as compare_command
    from memcommit.adapters.console.entrypoint import app
    from memcommit.application.operations.compare.ledger.store import comparison_analysis_path
    from memcommit.providers.policy import ResolvedProviderPolicy

    store, reference, peer = _prepare_store(root)
    before = {
        name: _context_digest(store, name)
        for name in (reference.name, peer.name)
    }
    provider = _Provider()
    policy = ResolvedProviderPolicy(
        operation="compare_summary",
        mode="PRODUCTION",
        provider_id="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning_effort="none",
        timeout_seconds=600.0,
        source="GLOBAL_DEFAULT",
    )
    compare_command.connect_operation_provider = lambda _operation: (provider, policy)
    analysis_path = comparison_analysis_path(reference.uid, peer.uid, store=store)

    print("$ mem compare capture/reference capture/peer", flush=True)
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    print("PROFILE · ISOLATED CAPTURE STORE · CURRENT capture/reference", flush=True)
    app(
        args=["compare", reference.name, peer.name],
        prog_name="mem",
        standalone_mode=False,
    )
    print("RESULT RETURNED TO CALLER · NO RESIDENT RESULT SCREEN", flush=True)
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")

    after = {
        name: _context_digest(store, name)
        for name in (reference.name, peer.name)
    }
    print("\x1b[38;2;139;213;255;1mCOMPARE SUMMARY · READ-ONLY VERIFICATION\x1b[0m")
    print(f"PTY · {os.get_terminal_size().columns} COLUMNS × {os.get_terminal_size().lines} ROWS")
    print("POLICY · production · gpt-5.6-sol · reasoning none · timeout 600")
    print(f"PROVIDER CALLS · {provider.calls}")
    print(f"REFERENCE DIGEST UNCHANGED · {before[reference.name] == after[reference.name]}")
    print(f"PEER DIGEST UNCHANGED · {before[peer.name] == after[peer.name]}")
    print(f"DEEP ANALYSIS EXISTS · {analysis_path.exists()}")
    print(f"CHECKPOINTS · {len(store.list_checkpoints(reference.name)) + len(store.list_checkpoints(peer.name))}")
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print("\x1b[38;2;139;213;202;1mVERIFICATION COMPLETE · TRANSIENT RESULT\x1b[0m", flush=True)


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


def _spawn(root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(root)],
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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-compare-summary-") as directory:
        child, recorder = _spawn(Path(directory) / ".mem")
        try:
            child.expect("PROFILE .* ISOLATED CAPTURE STORE")
            _BASE._settle(child, seconds=0.7)
            _snapshot(recorder, "01-provider-wait")

            child.expect("CAPTURE GATE .* READ-ONLY VERIFICATION")
            _BASE._settle(child)
            _snapshot(recorder, "02-transient-summary-result")

            child.send("v\r")
            child.expect("VERIFICATION COMPLETE .* TRANSIENT RESULT")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "03-read-only-verification")
        finally:
            if child.isalive():
                child.close(force=True)
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
