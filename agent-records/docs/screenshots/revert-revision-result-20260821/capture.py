"""Capture current-scoped Revert and shared complete revision Diff."""

from __future__ import annotations

import hashlib
import io
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
SUPPORT = ROOT / "agent-records/docs/screenshots/distill-elaborate-shared-app-20260815"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SUPPORT))

from capture_support import StreamRecorder, snapshot  # noqa: E402


COLUMNS = 180
ROWS = 52
CONTEXT = "practice/2"
DOWN = "\x1b[B"
RIGHT = "\x1b[C"
SHIFT_TAB = "\x1b[Z"
END = "\x1b[F"
CPR_REQUEST = "\x1b[6n"
CPR_RESPONSE = "\x1b[1;1R"


def _configure_store(store_dir: Path) -> None:
    import memcommit.persistence.store as store_module

    store_module.STORE_DIR = store_dir


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


def _prepare_store(
    store_dir: Path,
    *,
    retain_update_session: bool = True,
) -> tuple[str, tuple[str, ...]]:
    _configure_store(store_dir)
    import memcommit.application.ops as ops
    from memcommit.context import AutoCheckpoint
    from memcommit.application.operations.add.semantic_runtime import (
        append_semantic_memories,
        freeze_semantic_add_target,
    )
    from memcommit.persistence.store import MemoryStore
    from memcommit.application.operations.update.model import plan_update

    store = MemoryStore(root=store_dir)
    context = ops.init(CONTEXT)
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": CONTEXT},
            description=f"Initialized context '{CONTEXT}'",
        ),
    )

    apple, banana, carrot = ops.add_many(
        context,
        ["a is apple", "b is banana", "c is carrot"],
    )
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"memory_uids": [apple.uid, banana.uid, carrot.uid]},
            description="Added the initial practice Memories",
        ),
    )

    # Use Elaborate's actual publication primitive so this evidence cannot
    # accidentally attribute Edit or Remove authority to the semantic Add.
    append_semantic_memories(
        store=store,
        operation="elaborate",
        source_name=CONTEXT,
        target=freeze_semantic_add_target(store, CONTEXT),
        contents=("e is elm", "f is fig", "g is grape"),
        source_bindings=(),
        operation_args={
            "version": 2,
            "mode": "RULES_TO_CASES",
            "verification": "UNVERIFIED",
        },
        description=f"Added 3 Elaborate Cases to '{CONTEXT}'",
    )

    source = ops.init("practice/update-source")
    ops.add(
        source,
        "Change banana to blueberry, retire fig, and add juniper.",
    )
    store.save(source)
    target_context = store.load_direct(CONTEXT)

    class UpdateProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            del operation, output_schema
            payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
            source_id = payload["source"]["memories"][0]["source_id"]
            target_ids = {
                item["content"]: item["target_id"]
                for item in payload["target"]["memories"]
            }
            target_context_id = payload["target"]["contexts"][0]["context_id"]
            return json.dumps(
                {
                    "edits": [
                        {
                            "target_id": target_ids["b is banana"],
                            "new_content": "b is blueberry",
                            "source_ids": [source_id],
                            "reason": "The verified source changes the B example.",
                        }
                    ],
                    "additions": [
                        {
                            "target_context_id": target_context_id,
                            "new_content": "j is juniper",
                            "source_ids": [source_id],
                            "reason": "The verified source adds the J example.",
                        }
                    ],
                    "removals": [
                        {
                            "target_id": target_ids["f is fig"],
                            "source_ids": [source_id],
                            "reason": "The verified source retires the F example.",
                        }
                    ],
                }
            )

    staged = plan_update(
        source,
        target_context,
        UpdateProvider,
        status="staged",
    )
    store.save_staged_update(staged, expected_current=None)
    applied = store.apply_staged_update(staged)
    assert applied.application is not None
    target_checkpoint_uid = next(
        checkpoint.checkpoint_uid
        for checkpoint in applied.application.checkpoints
        if checkpoint.context_name == CONTEXT
    )

    context = store.load_direct(CONTEXT)
    holly, iris = ops.add_many(
        context,
        [
            "h is holly — added after the target revision",
            "i is iris — added after the target revision",
        ],
    )
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"memory_uids": [holly.uid, iris.uid]},
            description="Added two later Memories after the target revision",
        ),
    )
    store.set_current(CONTEXT)
    if not retain_update_session:
        session_path = store.staged_update_file
        assert session_path.is_file() and not session_path.is_symlink()
        # Diff must exercise the ordinary checkpoint-history route under test,
        # not the separate active Update-session browser. The production
        # Update checkpoint and resulting Context remain untouched.
        session_path.unlink()
    return target_checkpoint_uid, tuple(
        checkpoint["uid"] for checkpoint in store.list_checkpoints(CONTEXT)
    )


def _run_revert(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.revert.command import cmd
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(create=False)
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print("COMMAND · mem revert")
    print(f"CURRENT BEFORE · {store.current_context_name()}")
    cmd()


def _run_diff(store_dir: Path) -> None:
    _configure_store(store_dir)
    from memcommit.commands.diff.command import cmd
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(create=False)
    before_current = store.current_context_name()
    before_digest = _store_digest(store_dir)
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"COMMAND · mem diff {CONTEXT}")
    print(f"CURRENT BEFORE · {before_current}")
    cmd(CONTEXT, raw=False, stat=False, verbose=False)
    after = MemoryStore(create=False)
    print(
        "DIFF CLOSED · CURRENT UNCHANGED · "
        f"{after.current_context_name() == before_current}"
    )
    print(f"STORE CONTENT UNCHANGED · {_store_digest(store_dir) == before_digest}")


def _verify_revert(
    store_dir: Path,
    target_uid: str,
    original_uids: tuple[str, ...],
) -> None:
    _configure_store(store_dir)
    from memcommit.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(create=False)
    context = store.load_direct(CONTEXT)
    contents = [
        item.content for item in context.iter_items() if isinstance(item, Memory)
    ]
    retained = {checkpoint["uid"] for checkpoint in store.list_checkpoints(CONTEXT)}
    print("READ-ONLY REVERT VERIFICATION")
    print("LIVE COLOR PTY", *reversed(os.get_terminal_size()))
    print(f"Current Context: {store.current_context_name()}")
    print(f"Restored checkpoint retained: {target_uid in retained}")
    print(f"Keep-all history retained: {set(original_uids).issubset(retained)}")
    print(f"Result Memories: {contents}")
    print(
        "COMPLETE TARGET RESULT VERIFIED: "
        f"{contents == ['a is apple', 'b is blueberry', 'c is carrot', 'e is elm', 'g is grape', 'j is juniper']}"
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
    seconds: float = 0.6,
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


def _capture_revert(
    store_dir: Path,
    target_uid: str,
    original_uids: tuple[str, ...],
) -> str:
    child, recorder = _spawn("--revert", str(store_dir))
    try:
        child.expect(f"REVERT · {CONTEXT}")
        child.expect("FOCUS ITEMS")
        _pump(child, recorder)
        _snapshot(recorder, "01-current-history-entry")

        child.send(DOWN)
        _pump(child, recorder)
        _snapshot(recorder, "02-target-complete-result")

        child.send(SHIFT_TAB)
        _pump(child, recorder)
        _snapshot(recorder, "03-revision-viewer-focused")

        child.send(END)
        _pump(child, recorder)
        _snapshot(recorder, "04-complete-result-end")

        child.send("\r\r")
        _pump(child, recorder)
        _snapshot(recorder, "05-exact-revision-staged")

        child.send(RIGHT)
        _pump(child, recorder)
        _snapshot(recorder, "06-keep-all-policy")

        child.send("\r")
        _pump(child, recorder)
        _snapshot(recorder, "07-exact-apply")

        child.send("\r")
        child.expect("Reverted Context")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-success-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    verify, verify_recorder = _spawn(
        "--verify-revert",
        str(store_dir),
        target_uid,
        *original_uids,
    )
    try:
        verify.expect("COMPLETE TARGET RESULT VERIFIED: True")
        verify.expect(pexpect.EOF)
        _snapshot(verify_recorder, "09-read-only-revert-verification")
    finally:
        if verify.isalive():
            verify.close(force=True)
    return recorder.getvalue() + verify_recorder.getvalue()


def _capture_diff(store_dir: Path) -> str:
    child, recorder = _spawn("--diff", str(store_dir))
    try:
        child.expect(f"DIFF · {CONTEXT}")
        child.expect("FOCUS ITEMS")
        child.send(DOWN)
        _pump(child, recorder)
        _snapshot(recorder, "10-diff-shared-revision-result")

        child.send(SHIFT_TAB + END)
        _pump(child, recorder)
        _snapshot(recorder, "11-diff-complete-result-end")

        child.send("q")
        child.expect("DIFF CLOSED · CURRENT UNCHANGED · True")
        child.expect("STORE CONTENT UNCHANGED · True")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-diff-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)
    return recorder.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-revert-revision-") as temp:
        base = Path(temp)
        revert_store = base / "revert-store"
        diff_store = base / "diff-store"
        target_uid, original_uids = _prepare_store(revert_store)
        _prepare_store(diff_store, retain_update_session=False)
        revert_raw = _capture_revert(revert_store, target_uid, original_uids)
        diff_raw = _capture_diff(diff_store)

    combined = revert_raw + diff_raw
    assert "52 180" in combined
    assert "SELECT A CONTEXT" not in combined
    assert "REVISION DIFF" in combined
    assert "RESTORE IMPACT" not in combined
    assert "REMOVED BY REVISION" not in combined
    assert "38;" in combined and "48;" in combined
    assert "38;2;237;135;150;1m - " in combined
    assert "38;2;166;218;149;1m + " in combined
    assert "\x1b[?1049h" in combined and "\x1b[?1049l" in combined
    expected_plain = {
        "02-target-complete-result.txt": "4 kept · 1 added · 1 edited · 1 removed",
        "03-revision-viewer-focused.txt": "FOCUS VIEWER",
        "04-complete-result-end.txt": "ITEM 7/7",
        "05-exact-revision-staged.txt": "FOCUS HISTORY",
        "06-keep-all-policy.txt": "✓ KEEP ALL",
        "07-exact-apply.txt": "FOCUS APPLY",
        "10-diff-shared-revision-result.txt": "4 kept · 1 added · 1 edited · 1 removed",
        "11-diff-complete-result-end.txt": "ITEM 7/7",
    }
    for filename, expected in expected_plain.items():
        assert expected in (OUT / filename).read_text(encoding="utf-8")
    for filename in (
        "02-target-complete-result.txt",
        "10-diff-shared-revision-result.txt",
    ):
        rendered = (OUT / filename).read_text(encoding="utf-8")
        assert "  [KEEP]" in rendered
        assert "- [EDIT]" in rendered
        assert "+ [EDIT]" in rendered
        assert "- [REMOVE]" in rendered
        assert "+ [ADD]" in rendered


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments[:1] == ["--revert"]:
        _run_revert(Path(arguments[1]))
    elif arguments[:1] == ["--diff"]:
        _run_diff(Path(arguments[1]))
    elif arguments[:1] == ["--verify-revert"]:
        _verify_revert(
            Path(arguments[1]),
            arguments[2],
            tuple(arguments[3:]),
        )
    else:
        main()
