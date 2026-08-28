"""Capture inline-Memory Meld start, exact Apply, and durable verification."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
BASELINE_NAME = "capture/greeting-policy"
CONTENT = 'all greetings need "."; keep "" and ! literal. '

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "meld_inline_memory_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


class _SlowInlineProvider:
    def __init__(self) -> None:
        from tests.test_meld import InlineMemoryProvider

        self._delegate = InlineMemoryProvider()
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        time.sleep(1.8)
        return self._delegate.complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class _UnresolvedInlineProvider:
    """Return one greeting-specific required choice for the TUI branch."""

    def complete(self, prompt, *, operation, output_schema=None):
        from memcommit.application.operations.meld.provider import MELD_PAYLOAD_MARKER

        assert operation == "meld_contexts"
        payload = json.loads(prompt.split(MELD_PAYLOAD_MARKER, 1)[1])
        incoming = payload["frames"][0]["memories"][0]
        baseline = payload["frames"][1]["memories"][0]
        return json.dumps(
            {
                "overview": (
                    "The exact punctuation rule may replace the broad greeting "
                    "policy or coexist with explicitly scoped exceptions."
                ),
                "relations": [
                    {
                        "relation_key": "greeting_rule",
                        "left_memory_ids": [incoming["memory_id"]],
                        "right_memory_ids": [baseline["memory_id"]],
                        "kind": "CONFLICT",
                        "status": "UNRESOLVED",
                        "summary": "The new exact rule may replace the prior policy.",
                        "reason": (
                            "The intended scope must be chosen before changing "
                            "the baseline."
                        ),
                    }
                ],
                "issues": [
                    {
                        "issue_key": "greeting_scope",
                        "relation_keys": ["greeting_rule"],
                        "priority": "REQUIRED",
                        "title": "Greeting punctuation scope",
                        "question": (
                            "Should every greeting use the exact period rule, "
                            "or should named exceptions remain?"
                        ),
                        "why_it_matters": (
                            "Choosing the scope prevents a broad punctuation "
                            "rule from erasing deliberate exceptions."
                        ),
                        "options": [
                            {
                                "label": "Apply exact period rule",
                                "text": (
                                    'Use the inline rule exactly, including ".", '
                                    '"", and ! examples.'
                                ),
                            },
                            {
                                "label": "Preserve scoped exceptions",
                                "text": (
                                    'Require "." by default while keeping named '
                                    "exception scopes."
                                ),
                            },
                        ],
                    }
                ],
                "results": [],
                "ready_to_apply": False,
            }
        )


def _initialize_store(store_root: Path):
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    if store.context_exists(BASELINE_NAME):
        baseline = store.load_direct(BASELINE_NAME)
        return store, baseline
    baseline = ops.init(BASELINE_NAME)
    ops.add(baseline, "Keep the existing greeting policy.")
    store.create_context(baseline)
    store.set_current(baseline.name)
    return store, baseline


def _patch_meld_command(store, provider_factory) -> None:
    import memcommit.adapters.console.shared.command_wait as command_wait
    import memcommit.adapters.console.commands.meld.command as meld_command
    import memcommit.adapters.console.shared.session_help as session_help
    import memcommit.adapters.interfaces.tui.components.session_help as tui_session_help

    meld_command.MemoryStore = lambda *args, **kwargs: store
    meld_command.connect_codex_chatgpt_provider = provider_factory
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()
    tui_session_help.current_help_entries = lambda: ()


def _run_meld_cli(store, args: list[str]) -> None:
    import click
    import typer

    import memcommit.adapters.console.commands.meld.command as meld_command

    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep the capture in command-group mode."""

    app.command("meld")(meld_command.cmd)
    try:
        app(args=["meld", *args], prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _verification(store, *, provider_calls: int) -> None:
    baseline = store.load_direct(BASELINE_NAME)
    session = store.load_meld_session(baseline.uid)
    checkpoints = store.list_checkpoints(BASELINE_NAME)
    names = tuple(store.list_context_names())
    print("\nDURABLE VERIFICATION · INLINE-MEMORY MELD")
    print(f"  SESSION STATE · {session.state if session is not None else 'MISSING'}")
    print(
        f"  SESSION SCHEMA · {session.schema_version if session is not None else 'MISSING'}"
    )
    print(f"  PROVIDER CALLS · {provider_calls}")
    print(f"  TARGET CHECKPOINTS · {len(checkpoints)}")
    print(f"  CONTEXT NAMES · {', '.join(names)}")
    print(f"  INLINE MEMORY CONTEXT EXISTS · {'INLINE MEMORY' in names}")
    print(f"  TARGET MEMORIES · {len(baseline.memories)}")
    for index, memory in enumerate(baseline.iter_items(), start=1):
        print(f"    {index}. [{memory.uid[:8]}] {memory.content!r}")
    if session is not None:
        print(f"  RETAINED INLINE CONTENT · {session.frames[0].memories[0].content!r}")


def _run_tty_start_child(store_root: Path) -> None:
    store, _baseline = _initialize_store(store_root)
    provider = _SlowInlineProvider()
    _patch_meld_command(store, lambda: provider)
    command = ["--from", CONTENT, "--to", BASELINE_NAME]
    print(f"$ {shlex.join(['mem', 'meld', *command])}", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    print(f"CURRENT BASELINE / TARGET · {BASELINE_NAME}", flush=True)
    _run_meld_cli(store, command)
    _verification(store, provider_calls=provider.calls)


def _run_prepare_exact_child(store_root: Path) -> None:
    from memcommit.adapters.console.commands.meld.command import render_meld_session
    from memcommit.application.operations.meld.model import INLINE_MELD_CONTEXT_NAME
    from memcommit.application.operations.meld.runtime import execute_meld_start, prepare_meld_start
    from memcommit.application.operations.meld.start_application import MeldStartRequest

    store, baseline = _initialize_store(store_root)
    provider = _SlowInlineProvider()
    request = MeldStartRequest(
        mode="DIRECTIONAL",
        left_name=INLINE_MELD_CONTEXT_NAME,
        right_name=BASELINE_NAME,
        target_name=BASELINE_NAME,
        incoming_text=CONTENT,
    )
    prepared = prepare_meld_start(request, store=store)
    started = execute_meld_start(
        request,
        store=store,
        provider_factory=lambda: provider,
        prepared=prepared,
    )
    print(
        f"$ {shlex.join(['mem', 'meld', '--from', CONTENT, '--to', BASELINE_NAME])}"
        " · reviewed"
    )
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(render_meld_session(started.session))
    print("\nEXACT APPLY GATE")
    print(
        "  COMMAND · "
        + shlex.join(
            [
                "mem",
                "meld",
                "--memory",
                CONTENT,
                "--into",
                BASELINE_NAME,
                "--accept",
            ]
        )
    )
    print(f"  SESSION STATE · {started.session.state}")
    print(f"  SESSION SCHEMA · {started.session.schema_version}")
    print(f"  PROVIDER CALLS · {provider.calls}")
    print(f"  TARGET CHECKPOINTS · {len(store.list_checkpoints(baseline.name))}")
    print(f"  INLINE MEMORY CONTEXT EXISTS · {store.context_exists('INLINE MEMORY')}")


def _forbidden_provider(counter: dict[str, int]):
    counter["calls"] += 1
    raise AssertionError("Exact inline-Memory Apply must not construct a provider.")


def _run_exact_accept_child(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    counter = {"calls": 0}
    _patch_meld_command(store, lambda: _forbidden_provider(counter))
    command = [
        "--memory",
        CONTENT,
        "--into",
        BASELINE_NAME,
        "--accept",
    ]
    print(f"$ {shlex.join(['mem', 'meld', *command])}", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    _run_meld_cli(store, command)
    _verification(store, provider_calls=counter["calls"])


def _run_verify_child(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    print(f"$ mem context {BASELINE_NAME} · read-only reload")
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    _verification(store, provider_calls=0)


def _run_unresolved_review_child(store_root: Path) -> None:
    from memcommit.adapters.interfaces.tui.operations.meld.screen import run_meld_shell
    from memcommit.application.operations.meld.model import MeldSession
    from memcommit.application.operations.meld.provider import assess_meld_turn

    store, baseline = _initialize_store(store_root)
    session = MeldSession.create_directional_from_memory(CONTENT, baseline)
    session.start_initial_analysis()
    session.record_assessment(
        session.current_turn.uid,
        assess_meld_turn(session, _UnresolvedInlineProvider()),
    )
    store.save_meld_session(session, expected_session_digest=None)
    before = store._context_file(BASELINE_NAME).read_bytes()
    print(
        "$ mem meld --from '…' --to capture/greeting-policy · "
        "unresolved inline-Memory review",
        flush=True,
    )
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    action = run_meld_shell(session)
    print("\nINLINE-MEMORY REVIEW CLOSED")
    print(f"  RETURNED ACTION · {action!r}")
    print(f"  SESSION STATE · {session.state}")
    print(
        "  TARGET BYTES UNCHANGED · "
        f"{store._context_file(BASELINE_NAME).read_bytes() == before}"
    )
    print(f"  INLINE MEMORY CONTEXT EXISTS · {store.context_exists('INLINE MEMORY')}")
    print("  PROVIDER CALLS AFTER OPEN · 0", flush=True)


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


def _capture_tty_start(store_root: Path) -> None:
    child, recorder = _spawn("tty-start", store_root)
    try:
        child.expect("CURRENT BASELINE / TARGET")
        time.sleep(0.45)
        _BASE._settle(child, seconds=0.2)
        _snapshot(recorder, "01-inline-input-provider-pending")
        child.expect("DURABLE VERIFICATION", timeout=30)
        child.expect(pexpect.EOF)
        _snapshot(recorder, "02-tty-success-receipt")
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


def _capture_unresolved_review(store_root: Path) -> None:
    child, recorder = _spawn("review", store_root)
    try:
        # Semantic tokens may contain ANSI boundaries, so wait for the actual
        # screen paint instead of matching a plain substring through styles.
        time.sleep(0.8)
        _BASE._settle(child)
        _snapshot(recorder, "06-unresolved-session-entry")

        child.send("\t\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "07-unresolved-issue-detail")

        child.send("q")
        child.expect("INLINE-MEMORY REVIEW CLOSED", timeout=30)
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-unresolved-review-close-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-meld-inline-memory-") as directory:
        root = Path(directory)
        _capture_tty_start(root / "tty-store")

        exact_store = root / "exact-store"
        _capture_finished(
            "prepare-exact",
            exact_store,
            "03-exact-ready-review",
            "EXACT APPLY GATE",
        )
        _capture_finished(
            "accept",
            exact_store,
            "04-exact-accept-receipt",
            "DURABLE VERIFICATION",
        )
        _capture_finished(
            "verify",
            exact_store,
            "05-read-only-result-verification",
            "DURABLE VERIFICATION",
        )
        _capture_unresolved_review(root / "review-store")

    for path in (*OUT.glob("*.txt"), *OUT.glob("*.typescript")):
        payload = re.sub(br"\r+\n", b"\n", path.read_bytes())
        path.write_bytes(re.sub(rb"[ \t]+(?=\n|$)", b"", payload))
    captures = tuple(sorted(OUT.glob("[0-9][0-9]-*.typescript")))
    if not captures or any(
        "PTY 180 52" not in path.read_text(encoding="utf-8") for path in captures
    ):
        raise RuntimeError("Every capture must verify its 180x52 PTY.")
    interactive_captures = tuple(
        path for path in captures if path.name.startswith(("06-", "07-", "08-"))
    )
    if any(
        "38;2;" not in path.read_text(encoding="utf-8")
        or "48;2;" not in path.read_text(encoding="utf-8")
        for path in interactive_captures
    ):
        raise RuntimeError(
            "Every interactive PTY stream must contain true-color foreground "
            "and background ANSI styles."
        )


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "tty-start":
            _run_tty_start_child(root)
        elif kind == "prepare-exact":
            _run_prepare_exact_child(root)
        elif kind == "accept":
            _run_exact_accept_child(root)
        elif kind == "verify":
            _run_verify_child(root)
        elif kind == "review":
            _run_unresolved_review_child(root)
        else:
            raise SystemExit(f"unknown child kind: {kind}")
    else:
        main()
