"""Capture recorded and legacy Branch provenance through a real color PTY."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-trace-branch-provenance-20260821"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("trace_branch_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _isolate_store(root: Path) -> None:
    import memcommit.store as store_module

    store_dir = root / ".mem"
    # Commands construct a fresh MemoryStore, so redirect the compatibility
    # root before any command runs instead of depending on the active Profile.
    store_module.STORE_DIR = store_dir


def _store_digest() -> str:
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    digest = hashlib.sha256()
    for path in sorted(
        (value for value in store.store_dir.rglob("*") if value.is_file()),
        key=lambda value: str(value),
    ):
        digest.update(str(path.relative_to(store.store_dir)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _prepare_recorded_branch() -> tuple[str, str, str]:
    from typer.testing import CliRunner

    from memcommit.cli import _checkout, app
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    runner = CliRunner()
    initialized = runner.invoke(app, ["init", "practice/1"])
    assert initialized.exit_code == 0, initialized.output
    added = runner.invoke(app, ["add", "a is apple"])
    assert added.exit_code == 0, added.output
    source = MemoryStore().load_current_direct()
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))

    print("COMMAND · mem checkout -b practice/2")
    # Exercise the Git-style public route itself. It delegates to the same
    # Branch application boundary used by `mem branch`.
    _checkout("practice/2", b=True, direct=False, recursive=False)

    store = MemoryStore()
    target = store.load_current_direct()
    copied = next(item for item in target.iter_items() if isinstance(item, Memory))
    assert target.name == "practice/2"
    assert copied.uid != memory.uid and copied.content == memory.content
    checkpoint = next(
        entry
        for entry in store.list_checkpoints(target.name)
        if entry["command"] == "branch"
    )
    [lineage] = checkpoint["args"]["memory_lineage"]["edges"]
    assert lineage["source_memory_uid"] == memory.uid
    assert lineage["target_memory_uid"] == copied.uid
    print(
        f"RECORDED · BRANCH CHECKPOINT [{checkpoint['uid'][:8]}] · "
        f"MEMORY [{memory.uid[:8]}] → [{copied.uid[:8]}] · "
        "practice/1 → practice/2 · FRESH UID + LINEAGE"
    )
    return memory.uid, copied.uid, target.uid


def _prepare_legacy_copy() -> str:
    from typer.testing import CliRunner

    from memcommit.cli import app
    from memcommit.context import Context, Memory
    from memcommit.store import MemoryStore

    runner = CliRunner()
    initialized = runner.invoke(app, ["init", "legacy/source"])
    assert initialized.exit_code == 0, initialized.output
    added = runner.invoke(app, ["add", "legacy inherited fact"])
    assert added.exit_code == 0, added.output
    store = MemoryStore()
    source = store.load_current_direct()
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))
    # Model a receipt-free pre-lineage store explicitly. New Branch cannot
    # create this same-UID shape, but Trace must keep it readable and uncertain.
    target = Context(uid="legacy-target-context", name="legacy/target")
    target.add(Memory(uid=memory.uid, content=memory.content))
    store.save(target)
    target_checkpoints = store._checkpoints_dir(target.name)
    target_checkpoints.mkdir(parents=True, exist_ok=True)
    for path in store._checkpoints_dir(source.name).glob("*.json"):
        shutil.copy2(path, target_checkpoints / path.name)
    store.set_current("practice/2")
    return memory.uid


def _run_child() -> None:
    from memcommit.commands import trace

    with tempfile.TemporaryDirectory(prefix="memcommit-trace-branch-") as temp:
        _isolate_store(Path(temp))
        source_memory_uid, target_memory_uid, target_uid = _prepare_recorded_branch()
        legacy_uid = _prepare_legacy_copy()
        before = _store_digest()
        print(
            "PTY · "
            f"os.get_terminal_size={os.get_terminal_size().columns}×"
            f"{os.get_terminal_size().lines} · stty={subprocess.check_output(['stty', 'size'], text=True).strip()}"
        )
        print("PRESS T · OPEN RECORDED BRANCH TRACE (READ ONLY)")
        input()

        trace.cmd(
            selector=target_memory_uid,
            context_name="practice/2",
            tui=True,
        )
        assert _store_digest() == before
        print(
            f"TRACE CLOSED · SOURCE [{source_memory_uid[:8]}] · "
            f"TARGET [{target_memory_uid[:8]}] · CONTEXT practice/2 "
            f"[{target_uid[:8]}] · STORE DIGEST UNCHANGED"
        )
        print("PRESS L · VERIFY RECEIPT-FREE LEGACY LIMIT")
        input()

        print("\x1b[2J\x1b[H", end="")
        print("COMMAND · mem trace --context legacy/target --plain " + legacy_uid[:8])
        trace.cmd(
            selector=legacy_uid,
            context_name="legacy/target",
            plain=True,
        )
        assert _store_digest() == before
        print("LEGACY VERIFIED · ONE OWNER WARNING · NO FABRICATED BRANCH EVENT")


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
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
    for pattern in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(pattern):
            path.unlink()

    child, recorder = _spawn()
    try:
        child.expect("PRESS T · OPEN RECORDED BRANCH TRACE")
        _BASE._settle(child)
        _snapshot(recorder, "01-checkout-branch-receipt")

        child.send("t\r")
        child.expect("TRACE REPORT")
        _BASE._settle(child)
        _snapshot(recorder, "02-recorded-branch-trace")

        child.send("q")
        child.expect("TRACE CLOSED")
        _BASE._settle(child)
        _snapshot(recorder, "03-read-only-verification")

        child.send("l\r")
        child.expect("LEGACY VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-legacy-receipt-limit")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    plain = "\n".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.txt"))
    normalized = " ".join(plain.split())
    assert "os.get_terminal_size=180×52 · stty=52 180" in normalized
    assert "COMMAND · mem checkout -b practice/2" in plain
    assert "practice/1 → practice/2 · Memory content unchanged" in plain
    assert "Source Context: practice/1" in plain
    assert "Target Context: practice/2" in plain
    assert "STORE DIGEST UNCHANGED" in plain
    assert normalized.count("branch creation event was not recorded") == 1
    assert "ONE OWNER WARNING · NO FABRICATED BRANCH EVENT" in plain
    # Foreground and focused-frame background ANSI styles prove that these are
    # color-capable PTY captures rather than NO_COLOR text renders.
    assert re.search(r"\x1b\[[0-9;]*38;", raw)
    assert re.search(r"\x1b\[[0-9;]*48;", raw)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT))
        _run_child()
    else:
        main()
