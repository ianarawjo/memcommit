"""Capture current-scoped full-screen Diff history in a real color PTY."""

from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time
import uuid

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SUPPORT = ROOT / "docs/screenshots/distill-elaborate-shared-app-20260815"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SUPPORT))

from capture_support import StreamRecorder, snapshot  # noqa: E402


COLUMNS = 180
ROWS = 52
DOWN = "\x1b[B"
CPR_REQUEST = "\x1b[6n"
CPR_RESPONSE = "\x1b[1;1R"
CURRENT = "practice/current"
EXPLICIT = "practice/unrelated"


def _fixture_uid(index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"memcommit-large-diff-{index}"))


def _large_diff_session():
    from memcommit.update import (
        AddOperation,
        ContextFingerprint,
        EditOperation,
        RemoveOperation,
        UpdateSession,
    )

    target_uid = _fixture_uid(1000)
    source_uid = _fixture_uid(1001)
    operations = []
    for index in range(1, 51):
        operations.append(
            EditOperation(
                owner_context_uid=target_uid,
                owner_context_name="task-1/participant",
                memory_uid=_fixture_uid(index),
                old_content=f"Rule {index:03d}: previous participant guidance.",
                new_content=f"Rule {index:03d}: revised participant guidance.",
                source_refs=(),
                reason="Align this Task 1 rule with the reviewed source.",
            )
        )
    for index in range(51, 101):
        operations.append(
            AddOperation(
                owner_context_uid=target_uid,
                owner_context_name="task-1/participant",
                memory_uid=_fixture_uid(index),
                new_content=f"Rule {index:03d}: newly reviewed participant guidance.",
                source_refs=(),
                reason="Add the reviewed Task 1 guidance.",
            )
        )
    for index in range(101, 151):
        operations.append(
            RemoveOperation(
                owner_context_uid=target_uid,
                owner_context_name="task-1/participant",
                memory_uid=_fixture_uid(index),
                old_content=f"Rule {index:03d}: obsolete participant guidance.",
                source_refs=(),
                reason="Remove superseded Task 1 guidance.",
            )
        )
    fingerprint = "0" * 64
    return UpdateSession(
        uid=_fixture_uid(2000),
        status="staged",
        created_at="2026-08-20T09:30:00-04:00",
        source_uid=source_uid,
        source_name="task-1/authority",
        source_digest=fingerprint,
        source_contexts=(
            ContextFingerprint(source_uid, "task-1/authority", fingerprint),
        ),
        target_uid=target_uid,
        target_name="task-1/participant",
        target_digest=fingerprint,
        target_contexts=(
            ContextFingerprint(target_uid, "task-1/participant", fingerprint),
        ),
        operations=tuple(operations),
    )


def _configure_store(store_dir: Path) -> None:
    import memcommit.store as store_module

    store_module.STORE_DIR = store_dir


def _run_fixture_command(*arguments: str) -> None:
    from typer.testing import CliRunner

    from memcommit.cli import app

    result = CliRunner().invoke(app, list(arguments))
    if result.exit_code != 0:
        raise RuntimeError(
            f"Fixture command failed ({shlex.join(('mem', *arguments))}): "
            f"{result.output}"
        )


def _prepare_store(store_dir: Path) -> tuple[int, int, str]:
    _configure_store(store_dir)
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    from memcommit.store import MemoryStore

    _run_fixture_command("init", CURRENT)
    _run_fixture_command("add", "The east entrance closes at 18:00.")
    store = MemoryStore(create=False)
    first_uid = next(iter(store.load_direct(CURRENT).memories))
    _run_fixture_command(
        "edit",
        first_uid,
        "The east entrance closes at 19:00.",
    )
    _run_fixture_command("add", "Visitor parking moved to Lot C.")
    _run_fixture_command("remove", first_uid)
    _run_fixture_command("add", "Use the south entrance after 18:00.")

    _run_fixture_command("init", EXPLICIT)
    _run_fixture_command("add", "This unrelated Context stays outside bare Diff.")
    _run_fixture_command("switch", CURRENT)

    current_checkpoints = len(store.list_checkpoints(CURRENT))
    explicit_checkpoints = len(store.list_checkpoints(EXPLICIT))
    return current_checkpoints, explicit_checkpoints, _store_digest(store_dir)


def _store_digest(store_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in store_dir.rglob("*") if candidate.is_file()
    ):
        digest.update(str(path.relative_to(store_dir)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _run_diff(store_dir: Path, context_name: str | None) -> None:
    _configure_store(store_dir)
    from memcommit.commands.diff.command import cmd
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    before_current = store.current_context_name()
    before_digest = _store_digest(store_dir)
    shown_command = "mem diff" + (f" {context_name}" if context_name else "")
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"COMMAND · {shown_command}")
    print(f"CURRENT BEFORE · {before_current}")
    cmd(context_name, raw=False, stat=False, verbose=False)
    after_store = MemoryStore(create=False)
    print(
        "DIFF CLOSED · CURRENT UNCHANGED · "
        f"{after_store.current_context_name() == before_current}"
    )
    print(f"STORE CONTENT UNCHANGED · {_store_digest(store_dir) == before_digest}")


def _run_large_diff() -> None:
    from memcommit.commands.update.checkpoint_history import (
        choose_update_checkpoint_at_location,
    )

    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print("LARGE DIFF FIXTURE · 150 CHANGES · 50 EDIT + 50 ADD + 50 REMOVE")
    choose_update_checkpoint_at_location(
        _large_diff_session(),
        "task-1/participant",
        title="DIFF",
    )
    print("LARGE DIFF CLOSED · READ ONLY")


def _verify(
    store_dir: Path,
    current_checkpoints: int,
    explicit_checkpoints: int,
    fixture_digest: str,
) -> None:
    _configure_store(store_dir)
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    print("READ-ONLY DIFF VERIFICATION")
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"Current Context: {store.current_context_name()}")
    print(
        "Current checkpoint count unchanged: "
        f"{len(store.list_checkpoints(CURRENT)) == current_checkpoints}"
    )
    print(
        "Explicit checkpoint count unchanged: "
        f"{len(store.list_checkpoints(EXPLICIT)) == explicit_checkpoints}"
    )
    print(
        f"Complete Store digest unchanged: {_store_digest(store_dir) == fixture_digest}"
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PYTHONPATH": os.pathsep.join(
                (str(ROOT / "src"), environment.get("PYTHONPATH", ""))
            ),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(*args: str) -> tuple[pexpect.spawn, StreamRecorder]:
    command = (
        f"stty rows {ROWS} cols {COLUMNS}; stty size; "
        f"exec {shlex.join([sys.executable, str(Path(__file__).resolve()), *args])}"
    )
    recorder = StreamRecorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _pump(
    child: pexpect.spawn,
    recorder: io.StringIO,
    *,
    seconds: float = 0.5,
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            return
        query_count = recorder.getvalue().count(CPR_REQUEST)
        while child._mem_cpr_responses < query_count:
            child.send(CPR_RESPONSE)
            child._mem_cpr_responses += 1


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    snapshot(recorder, stem, out=OUT, columns=COLUMNS, rows=ROWS)


def _capture_current(store_dir: Path) -> str:
    child, recorder = _spawn("--diff", str(store_dir), "--current")
    try:
        child.expect(f"DIFF · {CURRENT}")
        child.expect("FOCUS ITEMS")
        _pump(child, recorder)
        _snapshot(recorder, "01-current-entry")

        child.send(DOWN)
        _pump(child, recorder)
        _snapshot(recorder, "02-checkpoint-navigation")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "03-viewer-focus")

        child.send("q")
        child.expect("DIFF CLOSED")
        child.expect("STORE CONTENT UNCHANGED · True")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "04-current-close-receipt")
    finally:
        if child.isalive():
            child.close(force=True)
    return recorder.getvalue()


def _capture_explicit(store_dir: Path) -> str:
    child, recorder = _spawn("--diff", str(store_dir), "--explicit")
    try:
        child.expect(f"DIFF · {EXPLICIT}")
        child.expect("FOCUS ITEMS")
        _pump(child, recorder)
        _snapshot(recorder, "05-explicit-context-entry")
        child.send("q")
        child.expect("CURRENT UNCHANGED · True")
        child.expect("STORE CONTENT UNCHANGED · True")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-explicit-close-receipt")
    finally:
        if child.isalive():
            child.close(force=True)
    return recorder.getvalue()


def _capture_verification(
    store_dir: Path,
    current_checkpoints: int,
    explicit_checkpoints: int,
    fixture_digest: str,
) -> str:
    child, recorder = _spawn(
        "--verify",
        str(store_dir),
        str(current_checkpoints),
        str(explicit_checkpoints),
        fixture_digest,
    )
    try:
        child.expect("Complete Store digest unchanged: True")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)
    return recorder.getvalue()


def _capture_large_diff() -> str:
    child, recorder = _spawn("--large")
    try:
        child.expect("150 target Memory changes")
        child.expect("FOCUS ITEMS")
        _pump(child, recorder)
        _snapshot(recorder, "08-large-diff-entry")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "09-large-diff-viewer-focus")

        child.send("\x1b[F")
        _pump(child, recorder)
        _snapshot(recorder, "10-large-diff-end-position")

        child.send("q")
        child.expect("LARGE DIFF CLOSED · READ ONLY")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "11-large-diff-close-receipt")
    finally:
        if child.isalive():
            child.close(force=True)
    return recorder.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-diff-fullscreen-") as temporary:
        store_dir = Path(temporary) / ".mem"
        current_count, explicit_count, fixture_digest = _prepare_store(store_dir)
        current_raw = _capture_current(store_dir)
        explicit_raw = _capture_explicit(store_dir)
        verification_raw = _capture_verification(
            store_dir,
            current_count,
            explicit_count,
            fixture_digest,
        )
    large_diff_raw = _capture_large_diff()

    combined = current_raw + explicit_raw
    assert "52 180" in combined and "52 180" in verification_raw
    assert "SELECT A CONTEXT" not in combined
    assert "practice/unrelated" not in current_raw
    assert "\x1b[?1049h" in combined
    assert "\x1b[?1049l" in combined
    assert "\x1b[" in combined
    assert "CHANGE 1/150" in large_diff_raw
    large_entry = (OUT / "08-large-diff-entry.txt").read_text(encoding="utf-8")
    large_viewer = (OUT / "09-large-diff-viewer-focus.txt").read_text(encoding="utf-8")
    large_end = (OUT / "10-large-diff-end-position.txt").read_text(encoding="utf-8")
    assert len(large_entry.rstrip().splitlines()) == ROWS
    assert len(large_viewer.rstrip().splitlines()) == ROWS
    assert len(large_end.rstrip().splitlines()) == ROWS
    assert "CHANGE 150/150" in large_end
    assert "\x1b[?1049h" in large_diff_raw
    assert "\x1b[?1049l" in large_diff_raw


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments[:1] == ["--diff"]:
        target_store = Path(arguments[1])
        _run_diff(
            target_store,
            EXPLICIT if arguments[2:] == ["--explicit"] else None,
        )
    elif arguments[:1] == ["--verify"]:
        _verify(
            Path(arguments[1]),
            int(arguments[2]),
            int(arguments[3]),
            arguments[4],
        )
    elif arguments == ["--large"]:
        _run_large_diff()
    else:
        main()
