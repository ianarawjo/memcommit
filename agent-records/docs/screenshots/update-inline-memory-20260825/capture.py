"""Capture Update inline-Memory grammar and its typo-safe boundary."""

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
TARGET_NAME = "capture/fruit-rules"
CONTENT = "want to make all the last word as fruits"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "update_inline_memory_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


class _InlineUpdateProvider:
    def __init__(self, *, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "update planning"
        assert output_schema is not None
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        payload_text = prompt.split("UPDATE PAYLOAD:\n", 1)[1]
        payload = json.loads(payload_text)
        source = payload["source"]["memories"][0]
        target = payload["target"]["memories"][0]
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target["target_id"],
                        "new_content": "Make every final word a fruit.",
                        "source_ids": [source["source_id"]],
                        "reason": "The inline source supplies the reviewed rule.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def _initialize_store(store_root: Path):
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root)
    if not store.context_exists(TARGET_NAME):
        target = ops.init(TARGET_NAME)
        ops.add(target, "Make every final word an animal.")
        store.save(target)
        store.set_current(target.name)
    return store


def _patch_update_command(store, provider_factory) -> None:
    import memcommit.adapters.console.commands.shared.command_wait as command_wait
    import memcommit.adapters.console.commands.shared.session_help as session_help
    import memcommit.adapters.console.commands.update.command as update_command
    import memcommit.adapters.interfaces.tui.components.session_help as tui_session_help

    update_command.MemoryStore = lambda *args, **kwargs: store
    update_command.connect_codex_chatgpt_provider = provider_factory
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()
    tui_session_help.current_help_entries = lambda: ()


def _run_update_cli(args: list[str]) -> int:
    import click

    from memcommit.adapters.console.entrypoint import app

    try:
        result = app(prog_name="mem", args=["update", *args], standalone_mode=False)
    except click.exceptions.Exit as error:
        return error.exit_code
    return result if isinstance(result, int) else 0


def _verification(store, *, provider_calls: int) -> None:
    target = store.load_direct(TARGET_NAME)
    session = store.load_staged_update()
    print("\nDURABLE VERIFICATION · INLINE-MEMORY UPDATE")
    print(f"  SESSION STATE · {session.status if session is not None else 'MISSING'}")
    print(
        "  SESSION SCHEMA · "
        f"{session.to_dict()['schema_version'] if session is not None else 'MISSING'}"
    )
    print(f"  PROVIDER CALLS · {provider_calls}")
    print(f"  TARGET CHECKPOINTS · {len(store.list_checkpoints(TARGET_NAME))}")
    print(f"  CONTEXT NAMES · {', '.join(store.list_context_names())}")
    print(
        "  INLINE UPDATE CONTEXT EXISTS · "
        f"{session.source_name in store.list_context_names() if session else False}"
    )
    print(f"  TARGET MEMORY · {next(target.iter_items()).content!r}")
    if session is not None:
        print(f"  RETAINED INLINE CONTENT · {session.inline_source_content!r}")


def _run_start_child(store_root: Path) -> None:
    store = _initialize_store(store_root)
    provider = _InlineUpdateProvider(delay=1.8)
    _patch_update_command(store, lambda: provider)
    command = ["--from", CONTENT, "--to", TARGET_NAME]
    print(f"$ {shlex.join(['mem', 'update', *command])}", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(f"TTY FLAGS · stdin={sys.stdin.isatty()} stdout={sys.stdout.isatty()}")
    print(f"CURRENT TARGET · {TARGET_NAME}", flush=True)
    exit_code = _run_update_cli(command)
    print(f"COMMAND EXIT · {exit_code}")
    _verification(store, provider_calls=provider.calls)


def _forbidden_provider(counter: dict[str, int]):
    counter["calls"] += 1
    raise AssertionError("An exact applied Update must not call the provider again.")


def _run_repeat_child(store_root: Path) -> None:
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    counter = {"calls": 0}
    _patch_update_command(store, lambda: _forbidden_provider(counter))
    command = [CONTENT, "--to", TARGET_NAME]
    print(f"$ {shlex.join(['mem', 'update', *command])}", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(f"TTY FLAGS · stdin={sys.stdin.isatty()} stdout={sys.stdout.isatty()}")
    exit_code = _run_update_cli(command)
    print(f"COMMAND EXIT · {exit_code}")
    _verification(store, provider_calls=counter["calls"])


def _run_typo_child(store_root: Path) -> None:
    store = _initialize_store(store_root)
    provider = _InlineUpdateProvider()
    _patch_update_command(store, lambda: provider)
    command = ["--from", "practice/rulse", "--to", TARGET_NAME]
    print(f"$ {shlex.join(['mem', 'update', *command])}", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    print(f"TTY FLAGS · stdin={sys.stdin.isatty()} stdout={sys.stdout.isatty()}")
    before = store._context_file(TARGET_NAME).read_bytes()
    exit_code = _run_update_cli(command)
    print("TYPO-SAFE VERIFICATION")
    print(f"  COMMAND EXIT · {exit_code}")
    print(f"  PROVIDER CALLS · {provider.calls}")
    print(
        "  TARGET BYTES UNCHANGED · "
        f"{store._context_file(TARGET_NAME).read_bytes() == before}"
    )
    print(f"  STAGED UPDATE · {store.load_staged_update()!r}", flush=True)


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


def _capture_start(store_root: Path) -> None:
    child, recorder = _spawn("start", store_root)
    try:
        child.expect("CURRENT TARGET")
        time.sleep(0.45)
        _BASE._settle(child, seconds=0.2)
        _snapshot(recorder, "01-inline-source-provider-pending")
        child.expect("DURABLE VERIFICATION", timeout=30)
        child.expect(pexpect.EOF)
        _snapshot(recorder, "02-applied-receipt-and-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_finished(kind: str, store_root: Path, stem: str, expected: str) -> None:
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
    with tempfile.TemporaryDirectory(prefix="mem-update-inline-memory-") as directory:
        root = Path(directory)
        applied_store = root / "applied-store"
        _capture_start(applied_store)
        _capture_finished(
            "repeat",
            applied_store,
            "03-positional-resume-provider-free",
            "DURABLE VERIFICATION",
        )
        _capture_finished(
            "typo",
            root / "typo-store",
            "04-portable-context-typo-rejected",
            "TYPO-SAFE VERIFICATION",
        )

    for path in (*OUT.glob("*.txt"), *OUT.glob("*.typescript")):
        payload = re.sub(br"\r+\n", b"\n", path.read_bytes())
        path.write_bytes(re.sub(rb"[ \t]+(?=\n|$)", b"", payload))
    captures = tuple(sorted(OUT.glob("[0-9][0-9]-*.typescript")))
    if len(captures) != 4 or any(
        "PTY 180 52" not in path.read_text(encoding="utf-8") for path in captures
    ):
        raise RuntimeError("Every capture must verify its 180x52 PTY.")
    if any(
        "TTY FLAGS · stdin=True stdout=True" not in path.read_text(encoding="utf-8")
        for path in captures
    ):
        raise RuntimeError("Every child must verify real TTY input and output.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "start":
            _run_start_child(root)
        elif kind == "repeat":
            _run_repeat_child(root)
        elif kind == "typo":
            _run_typo_child(root)
        else:
            raise SystemExit(f"unknown child kind: {kind}")
    else:
        main()
