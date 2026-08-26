"""Capture real directional Meld application paths in isolated 180x52 PTYs."""

from __future__ import annotations

import importlib.util
import io
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
INCOMING_NAME = "test/update/from"
BASELINE_NAME = "test/update/to"

_BASE_PATH = ROOT / "agent-records/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "meld_directional_apply_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


class _SlowDirectionalProvider:
    """Delay the existing deterministic fixture long enough to capture waiting."""

    def __init__(self) -> None:
        from tests.test_meld import DirectionalProvider

        self._delegate = DirectionalProvider()
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        time.sleep(1.8)
        return self._delegate.complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


def _initialize_store(store_root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    if store.context_exists(INCOMING_NAME):
        incoming = store.load_direct(INCOMING_NAME)
        baseline = store.load_direct(BASELINE_NAME)
        return store, incoming, baseline

    incoming = ops.init(INCOMING_NAME)
    ops.add(
        incoming,
        (
            "The parking stairwell remains open; only the vehicle entrance "
            "and exit are closed."
        ),
    )
    ops.add(
        incoming,
        "Students needing an ATM should use the nearby Bank Annex ATM.",
    )
    baseline = ops.init(BASELINE_NAME)
    ops.add(baseline, "The underground-parking stairwell is closed.")
    ops.add(baseline, "The Campus Store remains open during construction.")
    store.create_context(incoming)
    store.create_context(baseline)
    store.set_current(incoming.name)
    return store, incoming, baseline


def _patch_meld_command(store, provider_factory) -> None:
    import memcommit.commands.shared.command_wait as command_wait
    import memcommit.commands.meld.command as meld_command
    import memcommit.commands.shared.session_help as session_help
    import memcommit.interfaces.tui.components.session_help as tui_session_help

    meld_command.MemoryStore = lambda *args, **kwargs: store
    meld_command.connect_codex_chatgpt_provider = provider_factory
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()
    tui_session_help.current_help_entries = lambda: ()


def _run_meld_cli(store, args: list[str]) -> None:
    import click
    import typer

    import memcommit.commands.meld.command as meld_command

    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep the capture in command-group mode."""

    app.command("meld")(meld_command.cmd)
    try:
        app(
            args=["meld", *args],
            prog_name="mem",
            standalone_mode=False,
        )
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _print_durable_verification(store, *, provider_calls: int) -> None:
    baseline = store.load_direct(BASELINE_NAME)
    incoming = store.load_direct(INCOMING_NAME)
    session = store.load_meld_session(baseline.uid)
    checkpoints = store.list_checkpoints(BASELINE_NAME)
    print("\nDURABLE VERIFICATION · DIRECTIONAL MELD")
    print(f"  SESSION STATE · {session.state if session is not None else 'MISSING'}")
    print(f"  PROVIDER CALLS · {provider_calls}")
    print(f"  TARGET CHECKPOINTS · {len(checkpoints)}")
    print(f"  INCOMING MEMORIES · {len(incoming.memories)} · UNCHANGED SOURCE")
    print(f"  TARGET MEMORIES · {len(baseline.memories)}")
    for index, memory in enumerate(baseline.iter_items(), start=1):
        print(f"    {index}. [{memory.uid[:8]}] {memory.content}")
    meld_checkpoint = next(
        (
            checkpoint
            for checkpoint in checkpoints
            if "meld" in checkpoint.get("args", {})
        ),
        None,
    )
    if meld_checkpoint is not None:
        record = meld_checkpoint["args"]["meld"]
        operations = ", ".join(result["operation"] for result in record["results"])
        print(f"  CHECKPOINT EFFECTS · {operations}")


def _run_setup_apply_child(store_root: Path) -> None:
    store, _incoming, _baseline = _initialize_store(store_root)
    provider = _SlowDirectionalProvider()
    _patch_meld_command(store, lambda: provider)
    print("$ mem meld · compact setup to real directional application", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    _run_meld_cli(store, [])
    _print_durable_verification(store, provider_calls=provider.calls)


def _run_prepare_exact_child(store_root: Path) -> None:
    from memcommit.commands.meld.command import render_meld_session
    from memcommit.meld_runtime import execute_meld_start, prepare_meld_start
    from memcommit.meld_start_application import MeldStartRequest

    store, _incoming, baseline = _initialize_store(store_root)
    provider = _SlowDirectionalProvider()
    request = MeldStartRequest(
        mode="DIRECTIONAL",
        left_name=INCOMING_NAME,
        right_name=BASELINE_NAME,
        target_name=BASELINE_NAME,
        left_descendants=False,
        right_descendants=False,
        create_target=False,
    )
    prepared = prepare_meld_start(request, store=store)
    started = execute_meld_start(
        request,
        store=store,
        provider_factory=lambda: provider,
        prepared=prepared,
    )
    print("$ mem meld test/update/from test/update/to · reviewed, not accepted")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(render_meld_session(started.session))
    print("\nEXACT APPLY GATE")
    print("  COMMAND · mem meld test/update/from test/update/to --accept")
    print(f"  SESSION STATE · {started.session.state}")
    print(f"  PROVIDER CALLS · {provider.calls}")
    print(f"  TARGET CHECKPOINTS · {len(store.list_checkpoints(baseline.name))}")
    print(
        f"  TARGET MEMORIES BEFORE · {len(store.load_direct(baseline.name).memories)}"
    )
    for index, memory in enumerate(
        store.load_direct(baseline.name).iter_items(),
        start=1,
    ):
        print(f"    {index}. [{memory.uid[:8]}] {memory.content}")


def _forbidden_provider(counter: dict[str, int]):
    counter["calls"] += 1
    raise AssertionError("Exact Meld Apply must not construct a provider.")


def _run_exact_accept_child(store_root: Path, *, repeated: bool) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    counter = {"calls": 0}
    _patch_meld_command(store, lambda: _forbidden_provider(counter))
    print(
        "$ mem meld test/update/from test/update/to --accept"
        + (" · repeat" if repeated else ""),
        flush=True,
    )
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    _run_meld_cli(
        store,
        [INCOMING_NAME, BASELINE_NAME, "--accept"],
    )
    _print_durable_verification(store, provider_calls=counter["calls"])


def _run_restore_child(store_root: Path, direction: str) -> None:
    from memcommit.commands.shared.restoration_present import render_command_restore_receipt
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    print(f"$ mem {direction}")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    result = store.restore_recent_context_command(direction)
    render_command_restore_receipt(result)
    baseline = store.load_direct(BASELINE_NAME)
    session = store.load_meld_session(baseline.uid)
    print(
        f"{direction.upper()} VERIFICATION · SESSION {session.state} · "
        f"TARGET MEMORIES {len(baseline.memories)} · "
        f"CHECKPOINTS {len(store.list_checkpoints(BASELINE_NAME))}"
    )


def _run_verify_child(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    print("$ mem context test/update/to · read-only reload")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    _print_durable_verification(store, provider_calls=0)


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


def _spawn(kind: str, store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
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


def _capture_setup_apply(store_root: Path) -> None:
    child, recorder = _spawn("setup-apply", store_root)
    try:
        child.expect("NEW MELD")
        _BASE._settle(child)
        _snapshot(recorder, "01-setup-entry")

        child.send("\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "02-directional-mode")

        child.send("\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "03-incoming-source")

        child.send("\t\x1b[C\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "04-horizontal-memory-stop")

        child.send("\x1b[D\x1b[D\x1b[D\x1b[B")
        _BASE._settle(child)
        child.send("\x15" + BASELINE_NAME)
        _BASE._settle(child)
        _snapshot(recorder, "05-baseline-target")

        child.send("\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "06-start-reviewed")

        child.send("\r")
        time.sleep(0.45)
        _BASE._settle(child, seconds=0.2)
        _snapshot(recorder, "07-provider-analysis-pending")

        child.expect("DURABLE VERIFICATION", timeout=30)
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-auto-application-receipt")
        if "CHECKPOINT EFFECTS · EDIT, ADD" not in recorder.getvalue():
            raise RuntimeError(
                "Directional setup did not reach its application receipt:\n"
                + (OUT / "08-auto-application-receipt.txt").read_text(encoding="utf-8")
            )
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_finished(
    kind: str,
    store_root: Path,
    stem: str,
    expected: str,
) -> None:
    child, recorder = _spawn(kind, store_root)
    try:
        child.expect(expected, timeout=30)
        child.expect(pexpect.EOF)
        _snapshot(recorder, stem)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-meld-directional-apply-") as directory:
        root = Path(directory)
        _capture_setup_apply(root / "setup-store")

        exact_store = root / "exact-store"
        _capture_finished(
            "prepare-exact",
            exact_store,
            "09-exact-ready-proposal",
            "EXACT APPLY GATE",
        )
        _capture_finished(
            "accept",
            exact_store,
            "10-exact-accept-receipt",
            "CHECKPOINT EFFECTS .* EDIT, ADD",
        )
        _capture_finished(
            "repeat",
            exact_store,
            "11-idempotent-repeat",
            "prior application recovered; no duplicate write",
        )
        _capture_finished(
            "undo",
            exact_store,
            "12-operation-undo",
            "UNDO VERIFICATION .* READY_TO_APPLY .* TARGET MEMORIES 2",
        )
        _capture_finished(
            "redo",
            exact_store,
            "13-operation-redo",
            "REDO VERIFICATION .* APPLIED .* TARGET MEMORIES 3",
        )
        _capture_finished(
            "verify",
            exact_store,
            "14-read-only-result-verification",
            "CHECKPOINT EFFECTS .* EDIT, ADD",
        )

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")
    plain_captures = tuple(sorted(OUT.glob("[0-9][0-9]-*.txt")))
    if not plain_captures or any(
        "PTY 180 52" not in path.read_text(encoding="utf-8") for path in plain_captures
    ):
        raise RuntimeError("Every capture must verify its 180x52 PTY.")
    setup_raw = "".join(
        (OUT / f"{index:02d}-{stem}.typescript").read_text(encoding="utf-8")
        for index, stem in (
            (1, "setup-entry"),
            (2, "directional-mode"),
            (3, "incoming-source"),
            (4, "horizontal-memory-stop"),
            (5, "baseline-target"),
            (6, "start-reviewed"),
        )
    )
    if "\x1b[?1049h" in setup_raw:
        raise RuntimeError("Compact Meld setup entered an alternate screen buffer.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "setup-apply":
            _run_setup_apply_child(root)
        elif kind == "prepare-exact":
            _run_prepare_exact_child(root)
        elif kind == "accept":
            _run_exact_accept_child(root, repeated=False)
        elif kind == "repeat":
            _run_exact_accept_child(root, repeated=True)
        elif kind == "undo":
            _run_restore_child(root, "undo")
        elif kind == "redo":
            _run_restore_child(root, "redo")
        elif kind == "verify":
            _run_verify_child(root)
        else:
            raise SystemExit(f"unknown child kind: {kind}")
    else:
        main()
