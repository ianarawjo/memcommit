"""Capture Embed-shaped Copy and Move workbenches in a real color PTY."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
UP = "\x1b[A"
DOWN = "\x1b[B"

_BASE_PATH = (
    ROOT / "agent-records/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location("memory_transfer_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_store(root: Path) -> None:
    import memcommit.store as store_module

    paths = {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "STATE_FILE": root / "state.json",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }
    for name, value in paths.items():
        setattr(store_module, name, value)


def _initialize(store, *, self_link: bool = False):
    from memcommit.context import Context, Memory, MemoryRef

    archive = Context(
        uid="10000000-0000-4000-8000-000000000001",
        name="archive/decisions",
    )
    archive.add(
        Memory(
            uid="ab120001-0000-4000-8000-000000000001",
            content="Archived decision: bounded recovery needs an owner.",
        )
    )
    archive.add(
        Memory(
            uid="cd340002-0000-4000-8000-000000000002",
            content="Archived decision: verify every operational handoff.",
        )
    )
    inbox = Context(
        uid="10000000-0000-4000-8000-000000000002",
        name="inbox/notes",
    )
    first = Memory(
        uid="9ef031a2-0000-4000-8000-000000000001",
        content="Prefer bounded retries over unbounded recovery loops.",
    )
    second = Memory(
        uid="ea713f91-0000-4000-8000-000000000002",
        content="Operational decisions require an owner.",
    )
    third = Memory(
        uid="ca112233-0000-4000-8000-000000000003",
        content="Document the exact boundary before applying a change.",
    )
    for memory in (first, second, third):
        inbox.add(memory)
    watcher = Context(
        uid="10000000-0000-4000-8000-000000000003",
        name="watchers/live",
    )
    live = MemoryRef(
        uid="de450001-0000-4000-8000-000000000001",
        target_context_uid=inbox.uid,
        target_context_name=inbox.name,
        target_memory_uid=first.uid,
        target=first,
    )
    (archive if self_link else watcher).add(live)
    snapshots = Context(
        uid="10000000-0000-4000-8000-000000000004",
        name="reports/snapshots",
    )
    snapshots.add(
        MemoryRef(
            uid="fa560001-0000-4000-8000-000000000001",
            target_context_uid=inbox.uid,
            target_context_name=inbox.name,
            target_memory_uid=first.uid,
            target=first,
            snapshot_content_sha256=hashlib.sha256(
                first.content.encode("utf-8")
            ).hexdigest(),
        )
    )
    for context in (archive, inbox, snapshots, watcher):
        store.save(context)
    store.set_current(inbox.name)
    return archive, inbox, snapshots, watcher, first


def _verification(store, *, label: str, originals: dict[str, dict]) -> str:
    from memcommit.context import Memory, MemoryRef

    lines = [f"{label} · READ-ONLY STORE VERIFICATION"]
    names = tuple(store.list_context_names())
    for name in names:
        context = store.load_direct(name)
        lines.append(f"CONTEXT · {name}")
        for item in context.iter_items():
            if isinstance(item, Memory):
                lines.append(f"  MEMORY [{item.uid[:8]}] · {item.content}")
            elif isinstance(item, MemoryRef):
                kind = "SNAPSHOT" if item.is_snapshot else "LIVE EMBED"
                lines.append(
                    f"  {kind} [{item.uid[:8]}] · OWNER FIELD "
                    f"{item.target_context_name} · MEMORY [{item.target_memory_uid[:8]}]"
                )
    live_owner = next(
        (
            item
            for name in names
            for item in store.load_direct(name).iter_items()
            if isinstance(item, MemoryRef) and item.is_live
        ),
        None,
    )
    if live_owner is not None:
        resolved = store.load(
            next(
                name
                for name in names
                if live_owner.uid in store.load_direct(name).memories
            )
        ).memories[live_owner.uid]
        assert isinstance(resolved, MemoryRef)
        lines.append(
            "LIVE RESOLVES · "
            + ("YES" if resolved.target is not None else "DANGLING")
        )
    lines.append(
        "ALL CONTEXTS UNCHANGED · "
        + (
            "YES"
            if all(store.load_direct(name).to_dict() == record for name, record in originals.items())
            else "NO"
        )
    )
    lines.append(
        "CHECKPOINTS · "
        + str(sum(len(store.list_checkpoints(name)) for name in names))
    )
    lines.append(f"CURRENT CONTEXT · {store.current_context_name()}")
    return "\n".join(lines)


def _run_child(kind: str, directory: str) -> None:
    import click

    from memcommit.cli import app
    from memcommit.store import MemoryStore, context_record_digest

    root = Path(directory) / ".mem"
    _configure_store(root)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    store = MemoryStore()
    archive, inbox, _snapshots, watcher, _first = _initialize(
        store,
        self_link=kind == "self-link",
    )
    if kind == "locked":
        frozen = store.load_direct(watcher.name)
        store.set_context_write_protection(
            watcher.name,
            protected=True,
            expected_context_uid=frozen.uid,
            expected_context_digest=context_record_digest(frozen),
        )
    originals = {
        name: store.load_direct(name).to_dict() for name in store.list_context_names()
    }
    operation = "copy" if kind == "copy" else "move"
    print(f"CAPTURE PTY · {os.get_terminal_size().columns}x{os.get_terminal_size().lines}")
    print(f"CAPTURE COMMAND · mem {operation}", flush=True)
    exit_code = 0
    try:
        returned = app(prog_name="mem", args=[operation], standalone_mode=False)
    except click.exceptions.Exit as error:
        exit_code = error.exit_code
    else:
        if isinstance(returned, int):
            exit_code = returned
    print(f"COMMAND EXIT · {exit_code}")
    print("CAPTURE PAUSE · press Enter for read-only verification", flush=True)
    sys.stdin.readline()
    print(
        _verification(
            store,
            label=kind.upper(),
            originals=originals,
        ),
        flush=True,
    )
    sys.stdin.readline()


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        }
    )
    return environment


def _spawn(kind: str, directory: str):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, directory],
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


def _capture_copy() -> None:
    with tempfile.TemporaryDirectory(prefix="memcommit-copy-tui-") as directory:
        child, recorder = _spawn("copy", directory)
        try:
            child.expect("MEM COPY")
            _BASE._settle(child)
            _snapshot(recorder, "01-copy-entry")

            child.send(DOWN + "\r" + DOWN + "\r")
            _BASE._settle(child)
            _snapshot(recorder, "02-copy-multiple-source-selected")

            child.send("\t" + UP + "\r")
            _BASE._settle(child)
            _snapshot(recorder, "03-copy-target-selected")

            child.send("\t")
            _BASE._settle(child)
            _snapshot(recorder, "04-copy-position-default")

            child.send(UP)
            _BASE._settle(child)
            _snapshot(recorder, "05-copy-position-hover")

            child.send("\r")
            _BASE._settle(child)
            _snapshot(recorder, "06-copy-position-staged")

            child.send("\t")
            _BASE._settle(child)
            _snapshot(recorder, "07-copy-exact-command")

            child.send("\r")
            child.expect("CAPTURE PAUSE")
            _snapshot(recorder, "08-copy-success-receipt")

            child.send("\r")
            child.expect("CURRENT CONTEXT")
            _snapshot(recorder, "09-copy-read-only-verification")
            child.send("\r")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)


def _move_to_command(child, recorder, *, snapshots: bool) -> None:
    child.send(DOWN + "\r")
    _BASE._settle(child)
    if snapshots:
        _snapshot(recorder, "11-move-source-selected")

    child.send("\t" + UP + "\r")
    _BASE._settle(child)
    if snapshots:
        _snapshot(recorder, "12-move-target-selected")

    child.send("\t" + UP)
    _BASE._settle(child)
    if snapshots:
        _snapshot(recorder, "13-move-position-hover")

    child.send("\r")
    _BASE._settle(child)
    if snapshots:
        _snapshot(recorder, "14-move-position-staged")

    child.send("\t")
    _BASE._settle(child)


def _capture_move() -> None:
    with tempfile.TemporaryDirectory(prefix="memcommit-move-tui-") as directory:
        child, recorder = _spawn("move", directory)
        try:
            child.expect("MEM MOVE")
            _BASE._settle(child)
            _snapshot(recorder, "10-move-entry")
            _move_to_command(child, recorder, snapshots=True)
            _snapshot(recorder, "15-move-exact-command")

            child.send("\r")
            child.expect("CAPTURE PAUSE")
            _snapshot(recorder, "16-move-success-auto-retarget")

            child.send("\r")
            child.expect("CURRENT CONTEXT")
            _snapshot(recorder, "17-move-read-only-verification")
            child.send("\r")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)


def _capture_locked() -> None:
    with tempfile.TemporaryDirectory(prefix="memcommit-move-locked-") as directory:
        child, recorder = _spawn("locked", directory)
        try:
            child.expect("MEM MOVE")
            _BASE._settle(child)
            _move_to_command(child, recorder, snapshots=False)
            child.send("\r")
            child.expect("CAPTURE PAUSE")
            _snapshot(recorder, "18-move-locked-owner-rejected")
            child.send("\r")
            child.expect("CURRENT CONTEXT")
            _snapshot(recorder, "19-move-locked-no-partial-verification")
            child.send("\r")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)


def _capture_self_link() -> None:
    with tempfile.TemporaryDirectory(prefix="memcommit-move-self-link-") as directory:
        child, recorder = _spawn("self-link", directory)
        try:
            child.expect("MEM MOVE")
            _BASE._settle(child)
            _move_to_command(child, recorder, snapshots=False)
            child.send("\r")
            _BASE._settle(child, seconds=0.8)
            _snapshot(recorder, "20-move-self-link-rejected")
            child.send("\x1b")
            child.expect("CAPTURE PAUSE")
            child.send("\r")
            child.expect("CURRENT CONTEXT")
            _snapshot(recorder, "21-move-self-link-no-partial-verification")
            child.send("\r")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)


def _capture_break() -> None:
    with tempfile.TemporaryDirectory(prefix="memcommit-move-break-") as directory:
        child, recorder = _spawn("break", directory)
        try:
            child.expect("MEM MOVE")
            _BASE._settle(child)
            _move_to_command(child, recorder, snapshots=False)
            child.send(
                "\x15inbox/notes:9ef031a --into archive/decisions "
                "--before ab12000 --break-links"
            )
            _BASE._settle(child)
            _snapshot(recorder, "22-move-break-exact-command")

            child.send("\r")
            child.expect("CAPTURE PAUSE")
            _snapshot(recorder, "23-move-break-success")
            child.send("\r")
            child.expect("CURRENT CONTEXT")
            _snapshot(recorder, "24-move-break-dangling-verification")
            child.send("\r")
            child.expect(pexpect.EOF)
        finally:
            if child.isalive():
                child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stale_stem in (
        "03-copy-preserve-selected",
        "04-copy-target-selected",
    ):
        for suffix in (".png", ".txt", ".typescript"):
            (OUT / f"{stale_stem}{suffix}").unlink(missing_ok=True)
    _capture_copy()
    _capture_move()
    _capture_locked()
    _capture_self_link()
    _capture_break()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "CAPTURE PTY · 180x52" in raw
    assert "38;5" in raw or "38;2" in raw
    assert "48;5" in raw or "48;2" in raw
    assert "doesn't support cursor position requests" not in raw
    assert len(tuple(OUT.glob("*.png"))) == 24
    assert "Retargeted 1 live Memory Embed" in (
        OUT / "16-move-success-auto-retarget.txt"
    ).read_text(encoding="utf-8")
    assert "Context 'watchers/live' is locked" in (
        OUT / "18-move-locked-owner-rejected.txt"
    ).read_text(encoding="utf-8")
    assert "self-link" in (
        OUT / "20-move-self-link-rejected.txt"
    ).read_text(encoding="utf-8")
    assert "DANGLING" in (
        OUT / "24-move-break-dangling-verification.txt"
    ).read_text(encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], sys.argv[3])
    else:
        main()
