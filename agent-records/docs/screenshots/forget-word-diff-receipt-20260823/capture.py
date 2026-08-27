"""Capture the applied Forget word-diff receipt in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
CONTEXT_NAME = "capture/forget-word-diff"
INSTRUCTION = "Forget the obsolete desk location and normalize the merge wording."
REMOVED_UID = "10000000-0000-0000-0000-000000000001"
EDITED_UID = "20000000-0000-0000-0000-000000000002"
KEPT_UID = "30000000-0000-0000-0000-000000000003"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "forget_receipt_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


class _ForgetProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "forget"
        self.calls += 1
        messages = json.loads(prompt.split("FORGET CHAT MESSAGES:\n", 1)[1])
        payload = json.loads(messages[1]["content"].split("FORGET PAYLOAD:\n", 1)[1])
        candidates = []
        for source in payload["source"]["memories"]:
            content = source["content"]
            if content.startswith("The service desk"):
                decision = "DELETE"
                proposed = ""
            elif "similar claims" in content:
                decision = "EDIT"
                proposed = "Keep the merge rule for equivalent claims."
            else:
                decision = "KEEP"
                proposed = content
            candidates.append(
                {
                    "source_memory_id": source["item_id"],
                    "decision": decision,
                    "proposed_content": proposed,
                    "rationale": "The deterministic capture applies the instruction.",
                    "criterion_item_ids": ["k1"],
                }
            )
        return json.dumps(
            {
                "overview": "One obsolete location is removed and one rule is normalized.",
                "candidates": candidates,
            }
        )


def _initialize_store(store_root: Path):
    import memcommit.application.ops as ops
    from memcommit.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    context = ops.init(CONTEXT_NAME)
    context.add(
        Memory(
            uid=REMOVED_UID,
            content="The service desk was beside the west entrance.",
        )
    )
    context.add(
        Memory(
            uid=EDITED_UID,
            content="Keep the merge rule for similar claims.",
        )
    )
    context.add(
        Memory(
            uid=KEPT_UID,
            content="Never discard a unique general rule as a duplicate.",
        )
    )
    store.create_context(context)
    store.set_current(context.name)
    return store


def _run_forget_cli(store, provider: _ForgetProvider) -> None:
    import click
    import typer

    import memcommit.adapters.console.commands.forget.command as forget_command

    forget_command.MemoryStore = lambda *args, **kwargs: store
    forget_command.connect_codex_chatgpt_provider = lambda: provider
    # Exercise the explicit CLI application route while stdout remains a real
    # color PTY, so the receipt itself—not a synthetic renderer—owns the bytes.
    forget_command._interactive_terminal = lambda: False

    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep the capture in command-group mode."""

    app.command("forget")(forget_command.cmd)
    try:
        app(
            args=["forget", INSTRUCTION, "--context", CONTEXT_NAME],
            prog_name="mem",
            standalone_mode=False,
        )
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _run_child(store_root: Path) -> None:
    store = _initialize_store(store_root)
    provider = _ForgetProvider()
    print(f'$ mem forget "{INSTRUCTION}" --context {CONTEXT_NAME}', flush=True)
    size = os.get_terminal_size()
    print(f"PTY {size.columns} {size.lines}", flush=True)
    _run_forget_cli(store, provider)
    print("CAPTURE GATE · PRESS V FOR DURABLE VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")

    current = store.load_direct(CONTEXT_NAME)
    checkpoints = store.list_checkpoints(CONTEXT_NAME)
    print("\nDURABLE VERIFICATION · FORGET WORD DIFF")
    print(f"  REMOVED UID ABSENT · {REMOVED_UID not in current.memories}")
    print(f"  EDITED CONTENT · {current.memories[EDITED_UID].content}")
    print(f"  KEPT CONTENT · {current.memories[KEPT_UID].content}")
    print(f"  DIRECT MEMORIES · {len(current.memories)}")
    print(f"  FORGET CHECKPOINTS · {len(checkpoints)}")
    print(f"  PROVIDER CALLS · {provider.calls}")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn(store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
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
    with tempfile.TemporaryDirectory(prefix="mem-forget-word-diff-") as directory:
        child, recorder = _spawn(Path(directory) / "store")
        try:
            child.expect("CAPTURE GATE .* DURABLE VERIFICATION")
            _BASE._settle(child)
            _snapshot(recorder, "01-applied-receipt")

            child.send("v\r")
            child.expect("PROVIDER CALLS .* 1")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "02-durable-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    captures = tuple(sorted(OUT.glob("[0-9][0-9]-*.typescript")))
    if len(captures) != 2 or any(
        "PTY 180 52" not in path.read_text(encoding="utf-8") for path in captures
    ):
        raise RuntimeError("Every Forget receipt capture must verify its 180x52 PTY.")
    raw = captures[0].read_text(encoding="utf-8")
    codes = re.findall("\x1b\\[([0-9;]*)m", raw)
    if not any(code.startswith("38;2;237;135;150") for code in codes):
        raise RuntimeError("Forget receipt did not emit the shared REMOVE red.")
    if not any(code.startswith("38;2;166;218;149") for code in codes):
        raise RuntimeError("Forget receipt did not emit the shared EDIT green.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
