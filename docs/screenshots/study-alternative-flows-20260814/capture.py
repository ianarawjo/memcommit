"""Exercise Branch/Merge, Add, and Delete alternatives in an isolated Study."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = Path(os.environ.get("MEMCOMMIT_CAPTURE_SOURCE_ROOT", ROOT)).resolve()
CAPTURE_HOME = os.environ.get("MEMCOMMIT_CAPTURE_HOME")
OUT = ROOT / "docs/screenshots/study-alternative-flows-20260814"
FIXTURE_ROOT = ROOT / "outputs/study-fixtures"

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_tty_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = SOURCE_ROOT
_BASE.OUT = OUT


def _environment() -> dict[str, str]:
    if not CAPTURE_HOME:
        raise RuntimeError("MEMCOMMIT_CAPTURE_HOME must name an isolated HOME.")
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(SOURCE_ROOT / "src"),
            "HOME": CAPTURE_HOME,
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _run(executable: str, *arguments: str) -> str:
    completed = subprocess.run(
        (executable, *arguments),
        cwd=SOURCE_ROOT,
        env=_environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"mem {' '.join(arguments)} failed ({completed.returncode}):\n"
            + completed.stdout
        )
    return completed.stdout


def _spawn(
    executable: str,
    arguments: tuple[str, ...],
    *,
    following: tuple[tuple[str, ...], ...] = (),
) -> tuple[object, object]:
    commands = [shlex.join((executable, *arguments))]
    commands.extend(shlex.join((executable, *command)) for command in following)
    command = (
        f"stty rows {_BASE.ROWS} cols {_BASE.COLUMNS}; stty size; "
        + "; ".join(commands)
    )
    recorder = _BASE._Recorder()
    child = _BASE.pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(SOURCE_ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(_BASE.ROWS, _BASE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _finish(child, recorder, stem: str) -> str:
    child.expect(_BASE.pexpect.EOF, timeout=20)
    screen = _BASE._snapshot(recorder, stem)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus, screen)
    return screen


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    if not FIXTURE_ROOT.is_dir():
        raise RuntimeError(f"Study fixtures are unavailable: {FIXTURE_ROOT}")
    OUT.mkdir(parents=True, exist_ok=True)

    _run(executable, "profile", "import-study", "--from", str(FIXTURE_ROOT))
    _run(executable, "init-study", "study-alternative-flow-audit-20260814")
    _run(executable, "switch", "task-2/participant/proposal-workspace")

    branch_one, branch_one_recorder = _spawn(executable, ("branch",))
    _BASE._pump(branch_one, seconds=0.8)
    entry = _BASE._snapshot(branch_one_recorder, "01-task2-branch-source")
    assert "MEM BRANCH" in entry
    assert "task-2/participant/proposal-workspace" in entry
    assert "task-2/advisor1" not in entry
    assert "task-2/advisor2" not in entry

    branch_one.send("\t")
    _BASE._pump(branch_one, seconds=0.4)
    scope = _BASE._snapshot(branch_one_recorder, "02-task2-branch-range")
    assert "THIS CONTEXT ONLY" in scope

    branch_one.send("\t")
    _BASE._pump(branch_one, seconds=0.4)
    destination = _BASE._snapshot(branch_one_recorder, "03-task2-branch-destination")
    assert "proposal-workspace/branch" in destination
    assert "EXACT NEW CONTEXT NAME" in destination

    branch_one.send("\t")
    _BASE._pump(branch_one, seconds=0.4)
    apply_review = _BASE._snapshot(branch_one_recorder, "04-task2-branch-apply")
    assert "PRESS ENTER TO APPLY" in apply_review

    branch_one.send("\r")
    receipt = _finish(branch_one, branch_one_recorder, "05-task2-branch-one-receipt")
    assert "Branched 'task-2/participant/proposal-workspace'" in receipt
    assert "proposal-workspace/branch' and switched" in receipt
    _BASE._assert_color(branch_one_recorder.getvalue())

    advisor_one_merge = _run(executable, "merge", "task-2/advisor1")
    assert "added nothing new" in advisor_one_merge
    _run(executable, "switch", "task-2/participant/proposal-workspace")

    branch_two, branch_two_recorder = _spawn(executable, ("branch",))
    _BASE._pump(branch_two, seconds=0.8)
    second_entry = _BASE._snapshot(branch_two_recorder, "06-task2-second-branch")
    assert "proposal-workspace/branch-2" in second_entry
    branch_two.send("\t\t\t\r")
    second_receipt = _finish(
        branch_two,
        branch_two_recorder,
        "07-task2-branch-two-receipt",
    )
    assert "proposal-workspace/branch-2' and switched" in second_receipt
    _BASE._assert_color(branch_two_recorder.getvalue())

    merge_flow, merge_recorder = _spawn(
        executable,
        ("merge", "task-2/advisor2"),
        following=(
            (
                "merge",
                "task-2/participant/proposal-workspace/branch",
            ),
            ("status", "--short"),
        ),
    )
    merge_verification = _finish(
        merge_flow,
        merge_recorder,
        "08-task2-merge-verification",
    )
    assert merge_verification.count("added nothing new") == 2
    assert re.search(r"branch-2 \[OWNED\] .* Memories 0", merge_verification)

    _run(executable, "switch", "task-1/participant/construction-updates")
    add_flow, add_recorder = _spawn(
        executable,
        (
            "add",
            "--memory",
            "TASK FLOW AUDIT ADD ONE",
            "--memory",
            "TASK FLOW AUDIT ADD TWO",
            "--context",
            "task-1/campus-wiki",
        ),
    )
    add_receipt = _finish(add_flow, add_recorder, "09-task1-batch-add-receipt")
    assert "Added 2 Memories to 'task-1/campus-wiki'" in add_receipt

    _run(executable, "switch", "task-3/local/personal-memory")
    delete_flow, delete_recorder = _spawn(executable, ("delete",))
    _BASE._pump(delete_flow, seconds=0.8)
    delete_entry = _BASE._snapshot(
        delete_recorder,
        "10-task3-delete-entry",
    )
    assert "Delete or Remove" in delete_entry
    assert "task-3/local/personal-memory" in delete_entry
    delete_flow.send("q")
    delete_cancel = _finish(
        delete_flow,
        delete_recorder,
        "11-task3-delete-cancel",
    )
    assert "Deletion cancelled" in delete_cancel
    _BASE._assert_color(delete_recorder.getvalue())

    status_flow, status_recorder = _spawn(
        executable,
        ("status", "--short"),
    )
    task_three_status = _finish(
        status_flow,
        status_recorder,
        "12-task3-read-only-verification",
    )
    assert re.search(
        r"personal-memory \[OWNED\] .* Memories 0 .* Embedded Contexts 3",
        task_three_status,
    )


if __name__ == "__main__":
    main()
