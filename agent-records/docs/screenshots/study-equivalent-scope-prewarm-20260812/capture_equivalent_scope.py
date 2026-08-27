"""Capture transparent Study scope reuse in isolated copies of the active run."""

from __future__ import annotations

from pathlib import Path
import re
import shlex
import shutil
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
HARNESS = ROOT / "agent-records/docs/screenshots/study-full-replay-20260811"
sys.path.insert(0, str(HARNESS))
import capture_init_study as terminal  # noqa: E402


terminal.OUT = OUT
ROWS = terminal.ROWS
COLS = terminal.COLS

TASK1_PARENT = "task-1/participant"
TASK1_CHILD = TASK1_PARENT + "/construction-updates"
TASK1_TARGET = "task-1/campus-wiki"
TASK3_GUARDRAILS = "task-3/local/guardrails"
TASK3_RULE_PARENT = (
    "task-3/remote/government/healthcare-agent/info-request/"
    "transmission-guidance"
)
TASK3_RULE_CHILD = TASK3_RULE_PARENT + "/public-guidance"


def _launcher(store_root: Path, *, fail_live: str | None = None) -> str:
    root = repr(str(store_root))
    fail = repr(fail_live)
    return f"""
from pathlib import Path
import memcommit.persistence.store as store_module
root = Path({root})
store_module.STORE_DIR = root
store_module.CONTEXTS_DIR = root / 'contexts'
store_module.STATE_FILE = root / 'state.json'
store_module.QUERY_SOURCES_DIR = root / 'query-sources'
store_module.IMPACT_PLAN_FILE = root / 'impact-plan.json'
store_module.STAGED_UPDATE_FILE = root / 'staged-update.json'
store_module.REVIEW_SESSION_FILE = root / 'review-session.json'
store_module.ATOMIZE_ANALYSES_DIR = root / 'atomize-analyses'
store_module.ATOMIZE_WORKBENCHES_DIR = root / 'atomize-workbenches'
store_module.ATOMIZE_GROUNDING_SESSIONS_DIR = root / 'atomize-groundings'
store_module.ATOMIZE_GROUNDING_HISTORY_DIR = root / 'atomize-grounding-history'
store_module.GROUND_SESSIONS_DIR = root / 'ground-sessions'
store_module.MELD_SESSIONS_DIR = root / 'meld-sessions'
fail_live = {fail}
if fail_live == 'directional':
    from memcommit.adapters.console.commands import meld as command
    def stopped(*args, **kwargs):
        raise RuntimeError('capture provider stopper: live Directional analysis required')
    command._assess_and_save = stopped
elif fail_live == 'update':
    from memcommit.adapters.console.commands import update as command
    def stopped(*args, **kwargs):
        raise RuntimeError('capture provider stopper: live Update planning required')
    command._plan_update_with_wait = stopped
from memcommit.adapters.console.entrypoint import app
app()
"""


def _spawn(store_root: Path, *args: str, fail_live: str | None = None):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; exec "
        + shlex.join(
            [
                sys.executable,
                "-c",
                _launcher(store_root, fail_live=fail_live),
                *args,
            ]
        )
    )
    recorder = terminal._Recorder()
    import pexpect

    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=terminal._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _assert_capture(raw: str, required: tuple[str, ...]) -> None:
    screen = terminal.pyte.Screen(COLS, ROWS)
    terminal.pyte.Stream(screen).feed(raw)
    visible = "\n".join(screen.display)
    missing = [text for text in required if text not in raw and text not in visible]
    if missing:
        raise RuntimeError(f"Capture missed expected text: {missing!r}")
    if "52 180" not in raw:
        raise RuntimeError("Capture did not verify the required 180×52 PTY.")
    if re.search(r"\x1b\[[0-9;:]*m", raw) is None:
        raise RuntimeError("Capture stream did not retain ANSI styling.")


def _interactive(
    store_root: Path,
    args: tuple[str, ...],
    *,
    entry: str,
    entry_expected: tuple[str, ...],
    detail: str | None = None,
    detail_keys: str = "\t\x1b[B\r",
    detail_expected: tuple[str, ...] = (),
    close: str,
    close_expected: tuple[str, ...],
) -> None:
    child, recorder = _spawn(store_root, *args)
    try:
        terminal._pump(child, recorder, seconds=4)
        terminal._snapshot(recorder, entry)
        _assert_capture(recorder.getvalue(), entry_expected)
        if detail is not None:
            child.send(detail_keys)
            terminal._pump(child, recorder, seconds=1)
            terminal._snapshot(recorder, detail)
            _assert_capture(recorder.getvalue(), detail_expected)
        child.send("q")
        terminal._pump(child, recorder, seconds=5, require_eof=True)
        terminal._snapshot(recorder, close)
        _assert_capture(recorder.getvalue(), close_expected)
    finally:
        if child.isalive():
            child.close(force=True)


def _read_only(
    store_root: Path,
    args: tuple[str, ...],
    *,
    stem: str,
    expected: tuple[str, ...],
) -> None:
    child, recorder = _spawn(store_root, *args)
    try:
        terminal._pump(child, recorder, seconds=8, require_eof=True)
        _assert_capture(recorder.getvalue(), expected)
        terminal._snapshot(recorder, stem)
    finally:
        if child.isalive():
            child.close(force=True)


def _copy_active_store(destination: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.persistence.store import MemoryStore

    source = MemoryStore(create=False).store_dir
    shutil.copytree(source, destination)


def _clear_copied_meld_sessions(store_root: Path) -> None:
    """Remove only session files inside one disposable operation copy."""

    directory = store_root / "meld-sessions"
    if not directory.exists():
        return
    for path in directory.iterdir():
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("Disposable Meld session directory is unsafe.")
        path.unlink()


def _add_wrapper_memory(store_root: Path) -> None:
    from memcommit.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    parent = store.load_direct(TASK1_PARENT)
    parent.add(
        Memory(
            uid=str(uuid.uuid4()),
            content="Capture-only wrapper evidence forces a live miss.",
        )
    )
    store.save(parent)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-equivalent-scope-") as temp:
        temp_root = Path(temp)

        compare_store = temp_root / "compare"
        _copy_active_store(compare_store)
        _interactive(
            compare_store,
            (
                "compare",
                "--from",
                TASK1_PARENT,
                "--to",
                TASK1_TARGET,
                "--reference-descendants",
                "--compared-descendants",
            ),
            entry="01-task1-parent-compare-entry",
            entry_expected=("EQUIVALENT SCOPE PREWARM", "Reference:", "Compared:"),
            detail="02-task1-parent-compare-detail",
            detail_keys="\t\x1b[F" + "\x1b[A" * 50 + "\r",
            detail_expected=("RELATION ·", TASK1_CHILD),
            close="03-task1-parent-compare-close",
            close_expected=("Compare view closed.",),
        )

        update_store = temp_root / "update"
        _copy_active_store(update_store)
        staged = update_store / "staged-update.json"
        if staged.exists():
            staged.unlink()
        _interactive(
            update_store,
            (
                "update",
                "--from",
                TASK1_PARENT,
                "--to",
                TASK1_TARGET,
                "--source-descendants",
                "--target-descendants",
            ),
            entry="04-task1-parent-update-entry",
            entry_expected=("EQUIVALENT SCOPE PREWARM", "Staged update:"),
            detail="05-task1-parent-update-detail",
            detail_expected=("SOURCE", "REASON"),
            close="06-task1-parent-update-close",
            close_expected=("Update remains staged", "no target changes were applied"),
        )

        directional_store = temp_root / "directional"
        _copy_active_store(directional_store)
        _clear_copied_meld_sessions(directional_store)
        _interactive(
            directional_store,
            (
                "meld",
                TASK1_PARENT,
                "--left-descendants",
                "--into",
                TASK1_TARGET,
                "--right-descendants",
            ),
            entry="07-task1-parent-directional-entry",
            entry_expected=("MEM MELD", "DIRECTIONAL", "VIEWER"),
            detail="08-task1-parent-directional-detail",
            detail_expected=("RELATION", "SOURCE"),
            close="09-task1-parent-directional-close",
            close_expected=(
                "ANALYSIS · EQUIVALENT SCOPE PREWARM · PROVIDER NOT CALLED",
            ),
        )
        _read_only(
            directional_store,
            ("show", "--context", TASK1_CHILD),
            stem="10-task1-directional-source-verification",
            expected=(TASK1_CHILD, "Embedded Contexts 7"),
        )

        task3_store = temp_root / "task3"
        _copy_active_store(task3_store)
        _interactive(
            task3_store,
            (
                "compare",
                "--from",
                TASK3_GUARDRAILS,
                "--to",
                TASK3_RULE_CHILD,
                "--reference-descendants",
                "--compared-descendants",
            ),
            entry="11-task3-rule-child-compare-entry",
            entry_expected=("EQUIVALENT SCOPE PREWARM", "Reference:", "Compared:"),
            close="12-task3-rule-child-compare-close",
            close_expected=("Compare view closed.",),
        )

        task3_meld_store = temp_root / "task3-meld"
        _copy_active_store(task3_meld_store)
        _clear_copied_meld_sessions(task3_meld_store)
        task3_result = "task-3/participant/rule-child-equivalent-result"
        _interactive(
            task3_meld_store,
            (
                "meld",
                TASK3_GUARDRAILS,
                TASK3_RULE_CHILD,
                "--left-descendants",
                "--right-descendants",
                "--to",
                task3_result,
            ),
            entry="13-task3-rule-child-symmetric-meld-entry",
            entry_expected=(
                "MEM COMPARE · SYMMETRIC PEERS",
                "EQUIVALENT SCOPE PREWARM",
                "PROVIDER NOT CALLED",
            ),
            detail="14-task3-rule-child-symmetric-meld-detail",
            detail_expected=("SOURCE CLAIMS", TASK3_RULE_CHILD),
            close="15-task3-rule-child-symmetric-meld-close",
            close_expected=("MEM MELD · SYMMETRIC", "State: AWAITING_REPLY"),
        )
        _read_only(
            task3_meld_store,
            ("show", "--context", task3_result),
            stem="16-task3-rule-child-result-verification",
            expected=(task3_result, "Memories 0"),
        )

        miss_store = temp_root / "miss"
        _copy_active_store(miss_store)
        _clear_copied_meld_sessions(miss_store)
        _add_wrapper_memory(miss_store)
        child, recorder = _spawn(
            miss_store,
            "meld",
            TASK1_PARENT,
            "--left-descendants",
            "--into",
            TASK1_TARGET,
            "--right-descendants",
            fail_live="directional",
        )
        try:
            try:
                terminal._pump(child, recorder, seconds=8, require_eof=True)
            except RuntimeError:
                if child.exitstatus != 1:
                    raise
            _assert_capture(
                recorder.getvalue(),
                ("capture provider stopper", "live Directional analysis required"),
            )
            terminal._snapshot(recorder, "17-wrapper-memory-live-miss")
        finally:
            if child.isalive():
                child.close(force=True)


if __name__ == "__main__":
    main()
