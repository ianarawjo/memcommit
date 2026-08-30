"""Capture direct Update's report-local Apply and Esc-cancel paths in a PTY."""

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


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/study-full-replay-20260811/capture_init_study.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "update_report_apply_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


class _Provider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "update planning" or output_schema is None:
            raise AssertionError(operation)
        self.calls += 1
        time.sleep(1.4)
        payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
        source = payload["source"]["memories"][0]
        target = payload["target"]["memories"][0]
        return json.dumps(
            {
                "edits": [
                    {
                        "target_id": target["target_id"],
                        "new_content": (
                            "The south entrance closes at 18:00 during the study period."
                        ),
                        "source_ids": [source["source_id"]],
                        "reason": "The reviewed study guidance supersedes the old time.",
                    }
                ],
                "additions": [],
                "removals": [],
            }
        )


def _initialize_store(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=root)
    source = ops.init("capture/update-review/new-guidance")
    ops.add(source, "The south entrance closes at 18:00 during the study period.")
    target = ops.init("capture/update-review/campus-guide")
    ops.add(target, "The south entrance closes at 17:00.")
    store.create_context(source)
    store.create_context(target)
    store.set_current(source.name)
    return store, source, target


def _run_typer_command(command, args: list[str]) -> None:
    import click
    import typer

    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep the capture in command-group mode."""

    app.command("update")(command)
    try:
        app(args=["update", *args], prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _run_child(store_root: Path) -> None:
    import memcommit.adapters.console.commands.update.command as update_command
    import memcommit.adapters.console.terminal.components.session_help as session_help

    store, source, target = _initialize_store(store_root)
    provider = _Provider()
    update_command.MemoryStore = lambda *args, **kwargs: store
    update_command.connect_codex_chatgpt_provider = lambda: provider
    session_help.current_help_entries = lambda: ()
    args = ["--from", source.name, "--to", target.name]
    print(f"$ {shlex.join(['mem', 'update', *args])}", flush=True)
    print(f"PTY · {os.get_terminal_size().columns}×{os.get_terminal_size().lines}")
    print(f"PROFILE · local capture · CURRENT · {source.name}", flush=True)
    _run_typer_command(update_command.cmd, args)
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
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn(store_root: Path):
    command = (
        f"stty rows {ROWS} cols {COLUMNS}; stty size; "
        f"exec {shlex.join([sys.executable, str(__file__), '--child', str(store_root)])}"
    )
    recorder = _BASE._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _wait_visible(child, recorder, *needles: str, seconds: float = 20.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _BASE._pump(child, recorder, seconds=0.12)
        visible = _BASE._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return
        if not child.isalive():
            break
    raise RuntimeError(
        "PTY did not reach expected state: "
        + ", ".join(repr(item) for item in needles)
        + "\n"
        + _BASE._visible_text(recorder)
    )


def _snapshot(recorder, stem: str) -> None:
    _BASE._snapshot(recorder, stem)
    text_path = OUT / f"{stem}.txt"
    plain = text_path.read_text(encoding="utf-8")
    text_path.write_text(
        "\n".join(line.rstrip() for line in plain.splitlines()) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-update-report-apply-") as temp:
        child, recorder = _spawn(Path(temp) / "store")
        try:
            child.expect("CURRENT")
            _BASE._pump(child, recorder, seconds=0.3)
            _snapshot(recorder, "01-provider-pending")

            _wait_visible(
                child,
                recorder,
                "Staged update",
                "APPLY",
                "Press Esc to cancel",
            )
            _snapshot(recorder, "02-report-apply")

            child.send("\x1b[Z")
            _wait_visible(child, recorder, "APPLY", "Press Esc to cancel")
            _snapshot(recorder, "03-apply-focused-before-cancel")

            child.send("\x1b")
            child.expect("UPDATE CANCELLED", timeout=20)
            child.expect("CAPTURE GATE")
            _BASE._pump(child, recorder, seconds=0.5)
            _snapshot(recorder, "04-cancelled")

            child.send("v\r")
            child.expect("READ-ONLY VERIFICATION .* UPDATE")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "05-cancel-verification")
        finally:
            if child.isalive():
                child.close(force=True)

        child, recorder = _spawn(Path(temp) / "apply-store")
        try:
            _wait_visible(
                child,
                recorder,
                "Staged update",
                "APPLY",
                "Press Esc to cancel",
            )
            child.send("\x1b[Z")
            _BASE._pump(child, recorder, seconds=0.3)
            _snapshot(recorder, "06-apply-selected")

            child.send("\r")
            child.expect("UPDATE APPLIED", timeout=20)
            child.expect("CAPTURE GATE")
            _BASE._pump(child, recorder, seconds=0.5)
            _snapshot(recorder, "07-apply-receipt")

            child.send("v\r")
            child.expect("READ-ONLY VERIFICATION .* UPDATE")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "08-apply-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    raw = (OUT / "02-report-apply.typescript").read_text(encoding="utf-8")
    if "\x1b[" not in raw or "38;2" not in raw:
        raise RuntimeError("Capture did not preserve ANSI true-color output.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(Path(sys.argv[2]))
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("usage: capture.py [--child STORE]")
