"""Capture Distill's shared lowercase/local and uppercase/global previews."""

from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
SUPPORT = ROOT / "agent-records" / "docs" / "screenshots" / "distill-elaborate-shared-app-20260815"
sys.path.insert(0, str(SUPPORT))

from capture_support import StreamRecorder, settle, snapshot  # noqa: E402


OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"


def _configure_store(root: Path):
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = root
    return store_module.MemoryStore(root=root)


def _prepare_store(root: Path):
    import memcommit.application.ops as ops

    store = _configure_store(root)
    cases = ops.init("capture/cases")
    ops.add(cases, "A quiet room supported a careful conversation.")
    ops.add(cases, "A loud room interrupted the same conversation.")
    other = ops.init("capture/other")
    ops.add(other, "This separate Context must appear only after uppercase M.")
    store.create_context(cases)
    store.create_context(other)
    store.set_current(cases.name)
    return store, cases, other


def _run_child(root: Path) -> None:
    from memcommit.adapters.console.entrypoint import app
    from memcommit.adapters.console.commands import distill as command

    store, cases, other = _prepare_store(root)
    before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in (cases, other)
    }
    command.connect_semantic_provider = lambda: (_ for _ in ()).throw(
        AssertionError("Memory preview must not connect a provider.")
    )
    print("$ mem distill capture/cases --tui", flush=True)
    app(
        args=["distill", "capture/cases", "--tui"],
        prog_name="mem",
        standalone_mode=False,
    )
    assert all(
        store._context_file(name).read_bytes() == content
        for name, content in before.items()
    )
    print("$ mem show --context capture/cases", flush=True)
    app(
        args=["show", "--context", "capture/cases"],
        prog_name="mem",
        standalone_mode=False,
    )
    print("$ mem show --context capture/other", flush=True)
    app(
        args=["show", "--context", "capture/other"],
        prog_name="mem",
        standalone_mode=False,
    )
    print(
        "PREVIEW VERIFIED · PROVIDER CALLS 0 · BOTH CONTEXTS UNCHANGED",
        flush=True,
    )


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
    recorder = StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", str(root)],
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
    snapshot(recorder, stem, out=OUT, columns=COLUMNS, rows=ROWS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in OUT.iterdir():
        if path.suffix in {".png", ".txt", ".typescript"}:
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="distill-memory-preview-") as directory:
        child, recorder = _spawn(Path(directory) / ".mem")
        try:
            child.expect("MEM DISTILL")
            settle(child)
            _snapshot(recorder, "01-distill-entry")

            child.send("m")
            child.expect("quiet room")
            settle(child)
            _snapshot(recorder, "02-lowercase-m-this-context")

            child.send("M")
            # The fixed-height Context frame initially keeps the current
            # Context's two rows in view. Move through the shared viewport
            # stops to expose the second Context's newly loaded item.
            child.send(DOWN * 4)
            child.expect("separate Context")
            settle(child)
            _snapshot(recorder, "03-uppercase-m-every-context")

            child.send("q")
            child.expect("PREVIEW VERIFIED")
            child.expect(pexpect.EOF)
            _snapshot(recorder, "04-read-only-verification")
        finally:
            if child.isalive():
                child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "\x1b[" not in raw or "38;" not in raw or "48;" not in raw:
        raise RuntimeError(
            "Capture did not retain foreground and background ANSI styles."
        )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(Path(sys.argv[2]))
    else:
        main()
