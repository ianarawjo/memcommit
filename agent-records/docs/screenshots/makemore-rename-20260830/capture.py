"""Capture the renamed Makemore execution and legacy-name boundary."""

from __future__ import annotations

import importlib.util
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
    ROOT
    / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("makemore_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


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


def _configure_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = root


def _print_terminal() -> None:
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")


def _operation_app():
    """Compose the real Makemore and Review adapters without unrelated commands."""

    import typer

    from memcommit.adapters.console.commands.makemore.command import cmd as makemore_cmd
    from memcommit.adapters.console.commands.review.command import cmd as review_cmd
    from memcommit.operation_catalog import operation_summary

    app = typer.Typer()
    app.command("makemore", help=operation_summary("makemore"))(makemore_cmd)
    app.command("review")(review_cmd)
    return app


class _MakemoreProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "makemore"
        time.sleep(1.2)
        payload = json.loads(prompt.split("MAKEMORE PAYLOAD:\n", 1)[1])
        assert payload["mode"] == "GOAL_TO_RULES"
        return json.dumps(
            {
                "overview": "The Goal becomes two independently reviewable Rules.",
                "rules": [
                    {
                        "content": "Confirm the exact target before making a change.",
                        "rationale": "This makes the Goal operational for target choice.",
                    },
                    {
                        "content": "Record what changed after the action completes.",
                        "rationale": "This makes the Goal operational for verification.",
                    },
                ],
            }
        )


def _prepare(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    _configure_store(root)
    store = MemoryStore()
    target = ops.init("capture/makemore-target")
    store.create_context(target)
    store.set_current(target.name)
    return store, target


def _success_child(root: Path) -> None:
    import memcommit.adapters.console.commands.makemore.command as command
    from memcommit.persistence.store import context_record_digest

    app = _operation_app()
    store, target = _prepare(root)
    command.connect_semantic_provider = _MakemoreProvider
    before = context_record_digest(store.load_direct(target.name))
    _print_terminal()
    argv = [
        "makemore",
        "--goal",
        "Make careful changes and leave a clear trace.",
        "--number",
        "2",
    ]
    print("$ mem " + " ".join(argv), flush=True)
    app(args=argv, prog_name="mem", standalone_mode=False)

    checkpoint = store.list_checkpoints(target.name)[0]
    print("CAPTURE GATE · PRESS R FOR READ-ONLY REVIEW", flush=True)
    if sys.stdin.readline().strip().lower() != "r":
        raise RuntimeError("Review gate was not acknowledged.")
    print(
        f"\n$ mem review makemore --receipt {checkpoint['uid'][:8]} --snapshot",
        flush=True,
    )
    app(
        args=[
            "review",
            "makemore",
            "--receipt",
            checkpoint["uid"][:8],
            "--snapshot",
        ],
        prog_name="mem",
        standalone_mode=False,
    )

    print("CAPTURE GATE · PRESS V FOR DURABLE VERIFICATION", flush=True)
    if sys.stdin.readline().strip().lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    after = store.load_direct(target.name)
    print("\nDURABLE RESULT VERIFICATION")
    print(f"  CURRENT CONTEXT · {target.name}")
    print(f"  RESULT MEMORIES · {len(after.order)}")
    print(f"  CHECKPOINT COMMAND · {checkpoint['command']}")
    print(f"  CHECKPOINT PAYLOAD · {sorted(checkpoint['args'])}")
    print(f"  PRE-IMAGE CHANGED ONCE · {context_record_digest(after) != before}")
    print("  PROVIDER CALLS · 1", flush=True)


def _vacant_name_child() -> None:
    from typer.testing import CliRunner

    app = _operation_app()
    _print_terminal()
    print("$ mem elaborate --help", flush=True)
    result = CliRunner().invoke(
        app,
        ["elaborate", "--help"],
        color=True,
        prog_name="mem",
    )
    print(result.output, end="", flush=True)
    print(f"LEGACY NAME EXIT CODE · {result.exit_code}", flush=True)


def _spawn(kind: str, root: Path | None = None):
    recorder = _BASE._StreamRecorder()
    argv = [str(Path(__file__).resolve()), "--child", kind]
    if root is not None:
        argv.append(str(root))
    child = pexpect.spawn(
        sys.executable,
        argv,
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_success(root: Path) -> None:
    child, recorder = _spawn("success", root)
    try:
        child.expect("GENERATING REVIEW PROPOSALS")
        _BASE._settle(child, seconds=0.2)
        _BASE._snapshot(recorder, "01-command-entry-and-generation")

        child.expect("CAPTURE GATE .* READ-ONLY REVIEW")
        _BASE._settle(child, seconds=0.2)
        _BASE._snapshot(recorder, "02-success-receipt")

        child.send("r\r")
        child.expect("MEM REVIEW .* MAKEMORE")
        child.expect("CAPTURE GATE .* DURABLE VERIFICATION")
        _BASE._settle(child, seconds=0.2)
        _BASE._snapshot(recorder, "03-read-only-review")

        child.send("v\r")
        child.expect("DURABLE RESULT VERIFICATION")
        child.expect("PROVIDER CALLS .* 1")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "04-durable-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_vacant_name() -> None:
    child, recorder = _spawn("vacant")
    try:
        child.expect("No such command 'elaborate'")
        child.expect("LEGACY NAME EXIT CODE .* 2")
        child.expect(pexpect.EOF)
        _BASE._snapshot(recorder, "05-elaborate-name-vacant")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="makemore-rename-") as directory:
        _capture_success(Path(directory) / "store")
    _capture_vacant_name()
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY streams did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1:3] == ["--child", "success"]:
        if len(sys.argv) != 4:
            raise SystemExit("success child requires STORE_ROOT")
        _success_child(Path(sys.argv[3]))
    elif sys.argv[1:] == ["--child", "vacant"]:
        _vacant_name_child()
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: capture.py [--child success STORE_ROOT|--child vacant]")
