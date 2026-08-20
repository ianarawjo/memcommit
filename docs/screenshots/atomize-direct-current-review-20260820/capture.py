"""Capture bare current-Context Atomize and applied read-only Review."""

from __future__ import annotations

import click
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect
import typer


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52


def _helpers():
    path = ROOT / "docs/screenshots/study-full-replay-20260811/capture_init_study.py"
    spec = importlib.util.spec_from_file_location("atomize_direct_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load PTY capture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.COLS = COLS
    module.ROWS = ROWS
    return module


HELPERS = _helpers()


def _environment() -> dict[str, str]:
    environment = HELPERS._environment()
    environment["PYTHONPATH"] = str(ROOT)
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    return environment


def _spawn(mode: str, store_root: Path):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([sys.executable, str(__file__), '--child', mode, str(store_root)])}"
    )
    recorder = HELPERS._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _wait(child, recorder, *needles: str, seconds: float = 15.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        HELPERS._pump(child, recorder, seconds=0.1)
        visible = HELPERS._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return
        if not child.isalive():
            break
    raise RuntimeError(
        f"PTY did not reach {needles!r}:\n{HELPERS._visible_text(recorder)}"
    )


class _Provider:
    """Produce four deterministic two-child splits without network access."""

    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "impact_atomize" or output_schema is None:
            raise AssertionError(operation)
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        memories = payload["memories"]
        source_ids = [memory["candidate_id"] for memory in memories]
        items = []
        for memory in memories:
            first, second = memory["content"].split(" | ", 1)
            items.append(
                {
                    "candidate_id": memory["candidate_id"],
                    "classification": "COMPOSITE",
                    "reason_codes": ["A01_ONE_FOCUS", "A04_SOURCE_GROUNDED"],
                    "children": [
                        {"content": first, "source_spans": [first]},
                        {"content": second, "source_spans": [second]},
                    ],
                    "reason": "The source contains two independently revisable claims.",
                }
            )
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "Each source records two independent claims.",
                        "source_ids": source_ids,
                    },
                    "changed": {
                        "text": "Each source is split into its two recorded claims.",
                        "source_ids": source_ids,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": items,
                "quality_issues": [],
            }
        )


def _initialize(store) -> None:
    import memcommit.ops as ops

    if store.context_exists("atomize/direct-current"):
        return
    context = ops.init("atomize/direct-current")
    for content in (
        (
            "The Main Building entrance accepts a physical NFC card. | "
            "Mobile-app authentication is not accepted at that entrance."
        ),
        (
            "The staff entrance uses the same physical NFC card. | "
            "Staff should not rely on mobile-app authentication."
        ),
        (
            "The library opens at 10:00 on weekends. | "
            "The research desk closes at 16:00."
        ),
        (
            "The north elevator serves floors one through four. | "
            "The fifth floor requires the south elevator."
        ),
    ):
        ops.add(context, content)
    store.save(context)
    store.set_current(context.name)


def _invoke(store, argv: list[str]) -> None:
    import memcommit.commands.atomize as atomize_command
    import memcommit.commands.command_wait as command_wait
    import memcommit.commands.review as review_command
    import memcommit.commands.session_help as session_help
    import memcommit.interfaces.tui.components.session_help as session_help_component

    atomize_command.MemoryStore = lambda *args, **kwargs: store
    review_command.MemoryStore = lambda *args, **kwargs: store
    atomize_command.connect_codex_chatgpt_provider = lambda: _Provider()
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()
    session_help_component.current_help_entries = lambda: ()
    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep this capture in command-group mode."""

    app.command("atomize")(atomize_command.cmd)
    app.command("review")(review_command.cmd)
    try:
        app(args=argv, prog_name="mem", standalone_mode=False)
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _child_apply(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    _invoke(store, ["atomize"])
    context = store.load_direct("atomize/direct-current")
    analysis = store.load_atomize_analysis(context.uid)
    workbench = store.load_atomize_workbench(analysis)
    print(
        "DIRECT APPLY VERIFIED · MEMORIES",
        len(context.memories),
        "· CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
        "· RECEIPT",
        workbench is not None and workbench.application is not None,
    )


def _child_review(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    _invoke(store, ["review", "atomize"])
    context = store.load_direct("atomize/direct-current")
    print(
        "READ-ONLY REVIEW CLOSED · CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
    )


def _child_verify(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    _invoke(store, ["review", "atomize", "--snapshot"])
    context = store.load_direct("atomize/direct-current")
    analysis = store.load_atomize_analysis(context.uid)
    workbench = store.load_atomize_workbench(analysis)
    print(
        "READ-ONLY VERIFICATION · MEMORIES",
        len(context.memories),
        "· CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
        "· RECEIPT",
        workbench is not None and workbench.application is not None,
    )


def _run_child(mode: str, store_root: Path) -> None:
    {
        "apply": _child_apply,
        "review": _child_review,
        "verify": _child_verify,
    }[mode](store_root)


def _capture_finished(mode: str, root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn(mode, root)
    HELPERS._pump(child, recorder, seconds=25, require_eof=True)
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-atomize-direct-") as directory:
        root = Path(directory) / ".mem"
        _capture_finished(
            "apply",
            root,
            "01-direct-apply-receipt",
            "DIRECT APPLY VERIFIED · MEMORIES 8 · CHECKPOINTS 1 · RECEIPT True",
        )

        child, recorder = _spawn("review", root)
        _wait(
            child,
            recorder,
            "RESULT · atomize · atomize/direct-current",
            "READ ONLY · APPLIED",
        )
        HELPERS._snapshot(recorder, "02-applied-review-entry")
        child.send("\t\x1b[B\r")
        _wait(child, recorder, "SOURCE MEMORY", "PROPOSED CHILDREN")
        HELPERS._snapshot(recorder, "03-applied-split-detail")
        child.send("q")
        try:
            HELPERS._pump(child, recorder, seconds=8, require_eof=True)
        except RuntimeError:
            child.send("\x1b\x1b")
            HELPERS._pump(child, recorder, seconds=8, require_eof=True)
        if "READ-ONLY REVIEW CLOSED · CHECKPOINTS 1" not in recorder.getvalue():
            raise RuntimeError("Applied Review did not close read-only.")

        _capture_finished(
            "verify",
            root,
            "04-read-only-verification",
            "READ-ONLY VERIFICATION · MEMORIES 8 · CHECKPOINTS 1 · RECEIPT True",
        )

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "52 180" not in raw or "\x1b[" not in raw or "38;2" not in raw:
        raise RuntimeError("Capture did not preserve the required true-color PTY.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
