"""Capture Sever's shared Endpoint Setup migration in a 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import click
import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/semantic-bare-entry-routing-20260822/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "sever_endpoint_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS
_BASE._BASE.OUT = OUT
_BASE._BASE.COLUMNS = COLUMNS
_BASE._BASE.ROWS = ROWS


def _run_child(store_root: Path) -> None:
    from memcommit.adapters.console.entrypoint import app
    import memcommit.commands.sever.command as sever_command
    from memcommit.providers.subscription import QueryProviderError
    from memcommit.application.operations.sever.session_store import SeverSessionStore

    store = _BASE._prepare_store(store_root)
    before_digest = _BASE._store_digest(store_root)
    before_checkpoints = sum(
        len(store.list_checkpoints(name)) for name in store.list_context_names()
    )
    provider_boundaries: list[tuple[str, str, str]] = []

    def block_after_setup(**kwargs):
        provider_boundaries.append(
            (
                kwargs["source_name"],
                kwargs["criteria_name"],
                kwargs["output_name"],
            )
        )
        raise QueryProviderError(
            "capture provider intentionally blocked after the reviewed setup receipt"
        )

    sever_command._start_analysis = block_after_setup
    print("$ mem sever", flush=True)
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} COLUMNS × {size.lines} ROWS", flush=True)
    exit_code = 0
    try:
        app(args=["sever"], prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        exit_code = error.exit_code
    if len(provider_boundaries) != 1:
        raise AssertionError("The capture guard should stop after one setup receipt.")
    print("\n\x1b[38;2;237;135;150;1mSEVER FAILURE RECEIPT · EXPECTED\x1b[0m")
    print(f"EXIT CODE · {exit_code or 1}")
    print("SETUP RECEIPT CROSSED · True")
    source, criteria, output = provider_boundaries[0]
    print(f"SOURCE · {source} · THIS CONTEXT ONLY")
    print(f"CRITERIA · {criteria} · INCLUDE DESCENDANTS")
    print(f"OUTPUT · {output} · SELF-SAVE")
    print("PROVIDER CONNECTION · BLOCKED BY CAPTURE GUARD")
    print("SESSION · NOT CREATED")
    print("PRESS V · READ-ONLY VERIFICATION", flush=True)

    sys.stdin.read(1)
    after_checkpoints = sum(
        len(store.list_checkpoints(name)) for name in store.list_context_names()
    )
    print("\x1b[2J\x1b[H", end="")
    print("\x1b[38;2;139;213;255;1mSEVER SETUP · READ-ONLY VERIFICATION\x1b[0m")
    print(f"PTY · {size.columns} COLUMNS × {size.lines} ROWS")
    print("PROFILE · ISOLATED EXPLICIT STORE · HOST GRANTS EXCLUDED")
    print(f"CURRENT CONTEXT · {store.current_context_name()}")
    print()
    print(
        f"STORE DIGEST UNCHANGED · {_BASE._store_digest(store_root) == before_digest}"
    )
    print(f"CHECKPOINT COUNT UNCHANGED · {after_checkpoints == before_checkpoints}")
    print(f"SEVER SESSION COUNT · {len(SeverSessionStore(store).list())}")
    print(f"SETUP RECEIPTS · {len(provider_boundaries)}")
    print("ACTUAL PROVIDER CALLS · 0")
    print()
    print(
        "\x1b[38;2;139;213;202;1mVERIFICATION COMPLETE · NO DURABLE MUTATION\x1b[0m",
        flush=True,
    )


def _spawn(store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._BASE._StreamRecorder()
    environment = _BASE._environment()
    # pexpect preserves PTY dimensions and ANSI color but does not answer a
    # terminal cursor-position query; suppress only that irrelevant probe.
    environment["PROMPT_TOOLKIT_NO_CPR"] = "1"
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(store_root)],
        cwd=str(ROOT),
        env=environment,
        encoding="utf-8",
        codec_errors="replace",
        timeout=25,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _settle(child: pexpect.spawn) -> None:
    _BASE._BASE._settle(child, seconds=0.35)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sever-shared-endpoint-") as directory:
        child, recorder = _spawn(Path(directory) / ".mem")
        try:
            child.expect("NEW SEVER")
            _settle(child)
            _snapshot(recorder, "01-entry")

            # Source exact-name input -> Browse -> descendant range; Space
            # narrows Source while Criteria retains its independent default.
            child.send("\t\t ")
            _settle(child)
            _snapshot(recorder, "02-source-exact-range")

            # Move to Source's Memory control and open its lazy read-only rows.
            child.send("\t\r")
            child.expect("MEMORY · SOURCE")
            _settle(child)
            _snapshot(recorder, "03-source-memory-preview")

            # Close preview, move to Criteria Browse, and show the complete
            # frozen allowed catalog without changing durable state.
            child.send("\x1b")
            child.send("\x1b[B\t\r")
            child.expect("CONTEXTS · CRITERIA")
            _settle(child)
            _snapshot(recorder, "04-criteria-browse")

            # Keep the checked Criteria, move to Result, enter exact Source for
            # self-save, and arrive at the rebuilt START command.
            child.send("\r\x1b[B")
            child.send("\x15capture/reference\r")
            child.expect("COMMAND · RUNNABLE")
            _settle(child)
            _snapshot(recorder, "05-exact-start-review")

            child.send("\r")
            child.expect("SEVER FAILURE RECEIPT")
            child.expect("PRESS V")
            _settle(child)
            _snapshot(recorder, "06-guarded-failure-receipt")

            child.send("v\r")
            child.expect("VERIFICATION COMPLETE")
            _settle(child)
            _snapshot(recorder, "07-read-only-verification")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)

    raw = recorder.getvalue()
    if "\x1b[38;2" not in raw and "\x1b[48;2" not in raw:
        raise AssertionError("Capture stream did not contain expected true-color ANSI.")
    if not all(
        marker in raw
        for marker in (
            "STORE DIGEST UNCHANGED · True",
            "CHECKPOINT COUNT UNCHANGED · True",
            "SEVER SESSION COUNT · 0",
            "ACTUAL PROVIDER CALLS · 0",
        )
    ):
        raise AssertionError("Sever setup verification did not remain mutation-free.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    else:
        main()
