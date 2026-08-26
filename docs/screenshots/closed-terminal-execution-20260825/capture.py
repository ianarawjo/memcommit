"""Capture closed default terminal execution for Meld and Update."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "closed_execution_capture_base",
    _BASE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


class _SlowProvider:
    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        time.sleep(2.0)
        return self.delegate.complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


def _patch_shared_wait_help() -> None:
    import memcommit.commands.shared.session_help as session_help
    import memcommit.interfaces.tui.components.session_help as tui_session_help

    session_help.current_help_entries = lambda: ()
    tui_session_help.current_help_entries = lambda: ()


def _run_typer_command(name: str, command, args: list[str]) -> None:
    import click
    import typer

    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep the capture in command-group mode."""

    app.command(name)(command)
    try:
        app(args=[name, *args], prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _initialize_meld_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    study = ops.init("capture/coffee-advice/study")
    ops.add(study, "A low coffee table makes focused work uncomfortable.")
    chat = ops.init("capture/coffee-advice/chat")
    ops.add(chat, "A scenic view matters most when choosing a cafe.")
    result = ops.init("capture/coffee-advice/melded")
    for context in (study, chat, result):
        store.create_context(context)
    store.set_current(study.name)
    return store, study, chat, result


def _run_meld_child(store_root: Path) -> None:
    import memcommit.commands.meld.command as meld_command
    from tests.test_meld import Task2CompareProvider

    store, study, chat, result = _initialize_meld_store(store_root)
    provider = _SlowProvider(Task2CompareProvider())
    meld_command.MemoryStore = lambda *args, **kwargs: store
    meld_command.connect_codex_chatgpt_provider = lambda: provider
    _patch_shared_wait_help()
    args = [study.name, chat.name, "--to", result.name]
    print(f"$ {shlex.join(['mem', 'meld', *args])}", flush=True)
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    print(f"PROFILE · local capture · CURRENT · {study.name}", flush=True)
    _run_typer_command("meld", meld_command.cmd, args)
    print("CAPTURE GATE · PRESS V FOR READ-ONLY RESULT VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Meld verification gate was not acknowledged.")
    applied = store.load_meld_session(result.uid)
    materialized = store.load_direct(result.name)
    print("\nREAD-ONLY VERIFICATION · MELD")
    print(f"  SESSION STATE · {applied.state if applied is not None else 'MISSING'}")
    print(f"  PROVIDER CALLS · {provider.calls}")
    print(f"  SAVED TURNS · {len(applied.turns) if applied is not None else 'MISSING'}")
    print(f"  RESULT MEMORIES · {len(materialized.memories)}")
    print(f"  CHECKPOINTS · {len(store.list_checkpoints(result.name))}")
    for memory in materialized.iter_items():
        print(f"  [{memory.uid[:8]}] {memory.content}")


def _initialize_update_store(root: Path):
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore(root=root)
    source = ops.init("capture/update/new-guidance")
    ops.add(source, "The entrance closes at 18:00 during the study period.")
    target = ops.init("capture/update/campus-guide")
    ops.add(target, "The entrance closes at 17:00.")
    for context in (source, target):
        store.create_context(context)
    store.set_current(source.name)
    return store, source, target


def _run_update_child(store_root: Path) -> None:
    import memcommit.commands.update.command as update_command
    from tests.test_update import PlanProvider

    def one_capture_edit(prompt: str) -> dict[str, object]:
        payload_text = prompt.split("UPDATE PAYLOAD:\n", 1)[1]
        payload_text = payload_text.split(
            "\n\nCURRENT REVIEWED PROPOSAL (DATA, NOT INSTRUCTIONS):",
            1,
        )[0]
        payload = json.loads(payload_text)
        source_memory = payload["source"]["memories"][0]
        target_memory = payload["target"]["memories"][0]
        return {
            "edits": [
                {
                    "target_id": target_memory["target_id"],
                    "new_content": (
                        "The entrance closes at 18:00 during the study period."
                    ),
                    "source_ids": [source_memory["source_id"]],
                    "reason": "The current study guidance supersedes the old time.",
                }
            ],
            "additions": [],
            "removals": [],
        }

    store, source, target = _initialize_update_store(store_root)
    provider = _SlowProvider(PlanProvider(one_capture_edit))
    update_command.MemoryStore = lambda *args, **kwargs: store
    update_command.connect_codex_chatgpt_provider = lambda: provider
    _patch_shared_wait_help()
    args = ["--from", source.name, "--to", target.name]
    print(f"$ {shlex.join(['mem', 'update', *args])}", flush=True)
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    print(f"PROFILE · local capture · CURRENT · {source.name}", flush=True)
    _run_typer_command("update", update_command.cmd, args)
    print("CAPTURE GATE · PRESS V FOR READ-ONLY TARGET VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Update verification gate was not acknowledged.")
    applied = store.load_staged_update()
    changed = store.load_direct(target.name)
    print("\nREAD-ONLY VERIFICATION · UPDATE")
    print(f"  SESSION STATE · {applied.status if applied is not None else 'MISSING'}")
    print(f"  PROVIDER CALLS · {provider.calls}")
    print(f"  TARGET MEMORIES · {len(changed.memories)}")
    print(f"  CHECKPOINTS · {len(store.list_checkpoints(target.name))}")
    for memory in changed.iter_items():
        print(f"  [{memory.uid[:8]}] {memory.content}")


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


def _spawn(kind: str, store_root: Path):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder, stem: str) -> None:
    _BASE._snapshot(recorder, stem)
    text_path = OUT / f"{stem}.txt"
    plain = text_path.read_text(encoding="utf-8")
    text_path.write_text(
        "\n".join(line.rstrip() for line in plain.splitlines()) + "\n",
        encoding="utf-8",
    )


def _capture(
    kind: str,
    store_root: Path,
    *,
    pending_stem: str,
    success_pattern: str,
    success_stem: str,
    verification_pattern: str,
    verification_stem: str,
) -> None:
    child, recorder = _spawn(kind, store_root)
    try:
        child.expect("CURRENT")
        _BASE._settle(child, seconds=0.35)
        _snapshot(recorder, pending_stem)

        child.expect(success_pattern)
        child.expect("CAPTURE GATE")
        _BASE._settle(child)
        _snapshot(recorder, success_stem)

        child.send("v\r")
        child.expect(verification_pattern)
        child.expect(pexpect.EOF)
        _snapshot(recorder, verification_stem)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-closed-execution-") as directory:
        root = Path(directory)
        _capture(
            "meld",
            root / "meld-store",
            pending_stem="01-meld-provider-pending",
            success_pattern="MELD APPLIED",
            success_stem="02-meld-success-receipt",
            verification_pattern="READ-ONLY VERIFICATION .* MELD",
            verification_stem="03-meld-read-only-verification",
        )
        _capture(
            "update",
            root / "update-store",
            pending_stem="04-update-provider-pending",
            success_pattern="UPDATE APPLIED",
            success_stem="05-update-success-receipt",
            verification_pattern="READ-ONLY VERIFICATION .* UPDATE",
            verification_stem="06-update-read-only-verification",
        )
    # These line-oriented receipt renderers currently emit no ANSI even in a
    # capable color PTY. Keep the raw stream untouched so the evidence records
    # application behavior instead of adding synthetic capture-only styling.


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "meld":
            _run_meld_child(root)
        elif kind == "update":
            _run_update_child(root)
        else:
            raise SystemExit(f"unknown child kind: {kind}")
    else:
        main()
