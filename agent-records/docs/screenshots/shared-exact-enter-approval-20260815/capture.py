"""Capture focused Enter approval and cross-pane no-op Ground paths."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import os
from pathlib import Path
import sys

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "agent-records/docs/screenshots/ordinary-query-one-shot-20260813/capture.py"
SPEC = importlib.util.spec_from_file_location("terminal_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.OUT = OUT
ROWS = 52
COLUMNS = 180

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _run_blank_child() -> None:
    from memcommit.adapters.console.commands.ground.shell import run_ground_shell
    from tests.test_ground_shell import proposal

    applied = []

    def apply(value):
        applied.append(value)
        return "blank command applied"

    result = run_ground_shell(
        interpret=proposal,
        apply=apply,
        background_interpretation=False,
        require_tty=True,
    )
    if len(applied) != 1 or result.status != "APPLIED":
        raise RuntimeError("Blank Ground did not apply exactly once.")
    print("BLANK APPLY RECEIPT · blank command applied", flush=True)
    print(
        "READ-ONLY VERIFICATION · APPLIED 1 · "
        f"GROUND {result.proposal.ground_name}",
        flush=True,
    )


def _run_named_child() -> None:
    from memcommit.adapters.console.commands.ground.named_shell import run_named_ground_shell
    from memcommit.application.operations.ground.model import create_ground_session
    from tests.test_ground_named_shell import proposal

    session = create_ground_session(
        "enter-approval-capture",
        goal="Verify the focused exact-command approval boundary.",
    )
    applied = []

    def apply(current, frozen):
        applied.append(frozen.review.argv)
        return replace(current, revision=current.revision + 1), "named command applied"

    result = run_named_ground_shell(
        session,
        interpret=lambda current, text, _source: proposal(current, text),
        apply=apply,
        require_tty=True,
    )
    if len(applied) != 1 or result.session.revision != 1:
        raise RuntimeError("Named Ground did not apply exactly once.")
    print("NAMED APPLY RECEIPT · named command applied", flush=True)
    print(
        "READ-ONLY VERIFICATION · APPLIED 1 · "
        f"GROUND REV {result.session.revision}",
        flush=True,
    )


def _run_import_child() -> None:
    from memcommit.adapters.console.terminal.components.command_editor.approval import approve_exact_command
    from memcommit.adapters.console.terminal.components.command_editor import CommandReview

    approved = approve_exact_command(
        CommandReview(
            argv=(
                "mem",
                "import",
                "memory",
                "20000000-0000-4000-8000-000000000002",
                "--from-profile",
                "source-profile",
                "--context",
                "source/root/child",
                "--into",
                "destination",
            ),
            effects=(
                "Destination Context: destination",
                "Memory: append one exact source Memory",
            ),
        ),
        title="MEM IMPORT · MEMORY · FINAL APPROVAL",
        require_tty=True,
    )
    if not approved:
        raise RuntimeError("Import exact-command review was not approved.")
    print("IMPORT APPROVAL RECEIPT · APPROVED TRUE", flush=True)
    print(
        "READ-ONLY VERIFICATION · REVIEW RETURNED TRUE · "
        "NO IMPORT CALLBACK IN CAPTURE",
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


def _spawn(kind: str):
    recorder = BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_blank() -> None:
    child, recorder = _spawn("blank")
    try:
        child.expect("MEM GROUND · WORKING · NOT SAVED")
        BASE._settle(child)
        BASE._snapshot(recorder, "01-blank-entry")

        child.send("Review the exact creation command.\r")
        child.expect("Enter apply")
        BASE._settle(child)
        BASE._snapshot(recorder, "02-blank-exact-review")

        child.send("\t\r")
        BASE._settle(child)
        BASE._snapshot(recorder, "03-blank-other-pane-enter-no-op")

        child.send("\x1b[Z\r")
        child.expect("BLANK APPLY RECEIPT")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "04-blank-success-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_named() -> None:
    child, recorder = _spawn("named")
    try:
        child.expect("MEM GROUND · enter-approval-capture")
        BASE._settle(child)
        BASE._snapshot(recorder, "05-named-entry")

        child.send("Add one reviewed Rule.\r")
        child.expect("Enter apply")
        BASE._settle(child)
        BASE._snapshot(recorder, "06-named-exact-review")

        child.send("\t\r")
        BASE._settle(child)
        BASE._snapshot(recorder, "07-named-other-pane-enter-no-op")

        child.send("\x1b[Z")
        BASE._settle(child, seconds=0.3)
        child.send("\r")
        BASE._settle(child)
        BASE._snapshot(recorder, "08-named-success")

        child.send("\x03")
        child.expect("NAMED APPLY RECEIPT")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "09-named-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_import() -> None:
    child, recorder = _spawn("import")
    try:
        child.expect("MEM IMPORT · MEMORY · FINAL APPROVAL")
        BASE._settle(child)
        BASE._snapshot(recorder, "10-import-exact-review")

        child.send("\r")
        child.expect("IMPORT APPROVAL RECEIPT")
        child.expect("READ-ONLY VERIFICATION")
        child.expect(pexpect.EOF)
        BASE._snapshot(recorder, "11-import-approval-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_blank()
    _capture_named()
    _capture_import()
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain true-color ANSI styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        if sys.argv[2] == "blank":
            _run_blank_child()
        elif sys.argv[2] == "named":
            _run_named_child()
        elif sys.argv[2] == "import":
            _run_import_child()
        else:
            raise ValueError(f"Unknown child kind: {sys.argv[2]}")
    else:
        main()
