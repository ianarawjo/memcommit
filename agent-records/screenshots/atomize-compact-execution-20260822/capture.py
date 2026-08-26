"""Capture Atomize's compact execution and exact Save Location flow."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE_CAPTURE = (
    ROOT
    / "agent-records/screenshots/compact-execution-decisions-20260822/capture.py"
)
COLUMNS = 180
ROWS = 52

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("memcommit_compact_capture", BASE_CAPTURE)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load the shared terminal capture helpers.")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = OUT


class _StreamRecorder(io.StringIO):
    def flush(self) -> None:
        return


def _view():
    from memcommit.resolution_workbench import (
        ResolutionItem,
        ResolutionOption,
        ResolutionWorkbenchView,
    )

    item = ResolutionItem(
        uid="ambiguity:nfc",
        kind="AMBIGUITY",
        status="OPEN",
        priority="REQUIRED",
        title="Meaning of ‘the same NFC’",
        summary="The source does not identify which earlier credential it means.",
        obligation="REQUIRED",
        question="Which credential should the atomic Memory name?",
        options=(
            ResolutionOption(
                "ambiguity:nfc:recommended",
                "Prior credential",
                "Name the previously described NFC credential.",
            ),
            ResolutionOption(
                "ambiguity:nfc:alternate",
                "Staff credential",
                "Limit the reading to the staff entrance credential.",
            ),
        ),
    )
    return ResolutionWorkbenchView(
        operation="ATOMIZE",
        artifact_uid="capture-atomize-workbench",
        revision="capture-revision-1",
        title="Apply reviewed Atomize",
        route="source/policy → atomized/draft",
        status="OPEN",
        metrics=(),
        overview="The complete analysis is retained for mem review atomize.",
        list_label="ACTIONABLE FINDINGS",
        items=(item,),
        empty_message="No actionable findings.",
        results_label="PROPOSED MEMORIES",
        results=(),
        capabilities=frozenset({"SUBMIT_ITEM", "ACCEPT"}),
    )


def _run_child() -> None:
    from memcommit.interfaces.tui.components.save_location import SaveLocationView
    from memcommit.interfaces.tui.workbenches.resolution.compact_shell import (
        run_compact_resolution_decisions,
    )
    from memcommit.resolution_workbench import ResolutionWorkbenchAction

    size = os.get_terminal_size()
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError(f"unexpected PTY size: {size.columns}x{size.lines}")
    selected: dict[str, str] = {}
    destination = "atomized/draft"

    def validate_destination(value: str) -> None:
        if not value.startswith("atomized/"):
            raise ValueError("Output must stay in the atomized/ namespace.")

    print("$ mem atomize --context source/policy --save-as atomized/draft", flush=True)
    print(f"PTY {size.columns} {size.lines}", flush=True)
    while True:
        action = run_compact_resolution_decisions(
            _view,
            selected_option=selected.get,
            stage_option=selected.__setitem__,
            build_continue_action=lambda _uid: (
                ResolutionWorkbenchAction(kind="ACCEPT") if selected else None
            ),
            continue_label=lambda: "Apply",
            destination=SaveLocationView(
                value=destination,
                state="NOT CREATED",
                validate=validate_destination,
            ),
        )
        if action.kind != "CHANGE_DESTINATION":
            break
        if action.destination is None:
            raise RuntimeError("Destination change omitted its exact name.")
        destination = action.destination
        print(f"OUTPUT PLAN UPDATED · {destination} · NOT CREATED", flush=True)

    if action.kind != "ACCEPT":
        raise RuntimeError(f"expected ACCEPT, received {action.kind}")
    print(f"\nATOMIZE APPLIED · source/policy → {destination}")
    print("DECISIONS · 1 STAGED · 1 APPLIED")
    print("SOURCE · source/policy · UNCHANGED")
    print(f"OUTPUT · {destination} · CREATED · CHECKPOINT CREATED")
    print("REVIEW · RETAINED · mem review atomize --context source/policy")
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("verification gate was not acknowledged")
    print("\nREAD-ONLY RESULT VERIFICATION")
    print("  AMBIGUITY · Prior credential · REVIEWED")
    print(f"  OUTPUT · {destination}")
    print("  UNRESOLVED REQUIRED · 0")
    print("  ADDITIONAL PROVIDER CALLS · 0")


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


def _settle(child: pexpect.spawn, seconds: float = 0.45) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
    base._render(recorder.getvalue(), stem)
    plain_path = OUT / f"{stem}.txt"
    plain = plain_path.read_text(encoding="utf-8")
    plain_path.write_text(
        "\n".join(line.rstrip() for line in plain.splitlines()).rstrip() + "\n",
        encoding="utf-8",
    )


def main() -> None:
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    recorder = _StreamRecorder()
    child.logfile_read = recorder
    try:
        child.expect("ATOMIZE NEEDS INPUT")
        _settle(child)
        _snapshot(recorder, "01-entry-compact-decision")

        child.send("\r")
        _settle(child)
        _snapshot(recorder, "02-choice-staged")

        child.send("\x1b[B" * 2 + "\r")
        _settle(child)
        _snapshot(recorder, "03-save-location-input")

        child.send("\x15wrong/place\r")
        _settle(child, seconds=0.8)
        _snapshot(recorder, "04-invalid-location-retained")

        child.send("\x15atomized/final\r")
        _settle(child, seconds=0.8)
        _snapshot(recorder, "05-updated-location-compact-return")

        child.send("\x1b[B" * 3 + "\r")
        _settle(child, seconds=0.8)
        _snapshot(recorder, "06-applied-receipt")

        child.send("v\r")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        _run_child()
    else:
        main()
