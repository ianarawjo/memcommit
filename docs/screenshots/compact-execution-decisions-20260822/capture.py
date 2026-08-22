"""Capture the compact execution-decision surface and its terminal receipts."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
LEFT = "\x1b[D"
RIGHT = "\x1b[C"
DOWN = "\x1b[B"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


_NAMED_COLORS = {
    "default": "#e6e9ef",
    "black": "#101217",
    "red": "#ed8796",
    "green": "#a6da95",
    "brown": "#eed49f",
    "yellow": "#eed49f",
    "blue": "#8aadf4",
    "magenta": "#c6a0f6",
    "cyan": "#8bd5ca",
    "white": "#cad3f5",
    "brightblack": "#5b6078",
    "brightred": "#ed8796",
    "brightgreen": "#a6da95",
    "brightyellow": "#f5a97f",
    "brightblue": "#8aadf4",
    "brightmagenta": "#c6a0f6",
    "brightcyan": "#91d7e3",
    "brightwhite": "#f4dbd6",
}


class _StreamRecorder(io.StringIO):
    def flush(self) -> None:
        return


def _item(uid: str, title: str, question: str, first: str, second: str):
    from memcommit.resolution_workbench import ResolutionItem, ResolutionOption

    return ResolutionItem(
        uid=uid,
        kind="CONFLICT",
        status="OPEN",
        priority="REQUIRED",
        title=title,
        summary=question,
        obligation="REQUIRED",
        question=question,
        options=(
            ResolutionOption(
                f"{uid}:recommended",
                "A",
                first,
            ),
            ResolutionOption(f"{uid}:b", "B", second),
            ResolutionOption(
                f"{uid}:both",
                "Preserve both",
                "Retain both readings with their exact scopes.",
            ),
        ),
    )


def _view():
    from memcommit.resolution_workbench import ResolutionWorkbenchView

    return ResolutionWorkbenchView(
        operation="MELD",
        artifact_uid="capture-meld-session",
        revision="capture-revision-1",
        title="Resolve Meld",
        route="advisor-a + advisor-b → policy",
        status="OPEN",
        metrics=(),
        overview="The complete source-linked report is retained for Review.",
        list_label="CONFLICTS",
        items=(
            _item(
                "retention",
                "Retention period",
                "Which retention period should the policy use?",
                "Keep records for 30 days.",
                "Keep records for 90 days.",
            ),
            _item(
                "access",
                "Access window",
                "Which access window should the policy use?",
                "Allow access during staffed hours.",
                "Allow access at any time.",
            ),
        ),
        empty_message="No conflicts.",
        results_label="PROPOSED CHANGES",
        results=(),
        capabilities=frozenset({"SUBMIT_ALL", "DEFER", "ACCEPT"}),
    )


def _run_child(kind: str) -> None:
    from memcommit.exact_command_review import ExactCommandReview
    from memcommit.interfaces.tui.workbenches.resolution.compact_shell import (
        run_compact_resolution_decisions,
    )
    from memcommit.resolution_workbench import ResolutionWorkbenchAction

    size = os.get_terminal_size()
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError(f"unexpected PTY size: {size.columns}x{size.lines}")
    selected: dict[str, str] = {}

    def continue_action(_focused_uid: str | None):
        if set(selected) != {"retention", "access"}:
            return None
        return ResolutionWorkbenchAction(kind="ACCEPT")

    def command_review(action: ResolutionWorkbenchAction):
        argv = (
            ("mem", "meld", "advisor-a", "advisor-b", "policy", "--accept")
            if action.kind == "ACCEPT"
            else (
                "mem",
                "meld",
                "advisor-a",
                "advisor-b",
                "policy",
                "--defer-all",
            )
        )
        effects = (
            (
                "Apply the two staged judgments to the exact saved Meld proposal.",
                "Source Contexts remain unchanged; the target receives one checkpoint.",
            )
            if action.kind == "ACCEPT"
            else (
                "Keep the saved Meld report for later Review without applying it.",
                "All Source and target Contexts remain unchanged.",
            )
        )
        return ExactCommandReview(argv=argv, effects=effects)

    print("$ mem meld advisor-a advisor-b policy", flush=True)
    print(f"PTY {size.columns} {size.lines}", flush=True)
    action = run_compact_resolution_decisions(
        _view,
        selected_option=selected.get,
        stage_option=selected.__setitem__,
        build_continue_action=continue_action,
        build_simple_action=lambda action_kind: ResolutionWorkbenchAction(
            kind=action_kind
        ),
        continue_label=lambda: "Apply staged judgments",
        turn_command_review=command_review,
    )
    if kind == "success":
        if action.kind != "ACCEPT":
            raise RuntimeError(f"expected ACCEPT, received {action.kind}")
        print("\nMELD APPLIED · SYMMETRIC · policy")
        print("JUDGMENTS · 2 STAGED · 2 APPLIED")
        print("SOURCE · advisor-a + advisor-b · UNCHANGED")
        print("TARGET · policy · CHECKPOINT CREATED")
        print("REPORT · RETAINED · mem review meld --session capture-meld-session")
        print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
        if sys.stdin.read(1).lower() != "v":
            raise RuntimeError("verification gate was not acknowledged")
        print("\nREAD-ONLY RESULT VERIFICATION")
        print("  RETENTION · Preserve both · REVIEWED")
        print("  ACCESS · Allow access at any time · REVIEWED")
        print("  REPORT AVAILABLE · YES")
        print("  UNRESOLVED REQUIRED · 0")
        print("  ADDITIONAL PROVIDER CALLS · 0")
    else:
        if action.kind != "DEFER":
            raise RuntimeError(f"expected DEFER, received {action.kind}")
        print("\nMELD DEFERRED · SYMMETRIC · policy")
        print("SESSION · capture-meld-session · RETAINED")
        print("SOURCE · UNCHANGED")
        print("TARGET · UNCHANGED · NO CHECKPOINT")
        print("REPORT · mem review meld --session capture-meld-session")


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


def _settle(child: pexpect.spawn, *, seconds: float = 0.45) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return


def _color(value: str, *, background: bool = False) -> str:
    if value in _NAMED_COLORS:
        if value == "default" and background:
            return "#101217"
        return _NAMED_COLORS[value]
    if len(value) == 6 and all(char in "0123456789abcdef" for char in value):
        return "#" + value
    return "#101217" if background else "#e6e9ef"


def _render(raw: str, stem: str) -> None:
    screen = pyte.Screen(COLUMNS, ROWS)
    pyte.Stream(screen).feed(raw)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (OUT / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (OUT / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    cell_width = math.ceil(regular.getlength("M"))
    cell_height = 21
    margin = 16
    image = Image.new(
        "RGB",
        (margin * 2 + COLUMNS * cell_width, margin * 2 + ROWS * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLUMNS):
            char = screen.buffer[row][column]
            foreground = _color(char.fg)
            background = _color(char.bg, background=True)
            if char.reverse:
                foreground, background = background, foreground
            x = margin + column * cell_width
            y = margin + row * cell_height
            if background != "#101217":
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=background,
                )
            if char.data and char.data != " ":
                box_drawing = "\u2500" <= char.data <= "\u257f"
                draw.text(
                    (x, y),
                    char.data,
                    font=bold if char.bold and not box_drawing else regular,
                    fill=foreground,
                )
            if char.underscore:
                draw.line(
                    (
                        x,
                        y + cell_height - 3,
                        x + cell_width - 1,
                        y + cell_height - 3,
                    ),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
    _render(recorder.getvalue(), stem)


def _spawn(kind: str) -> tuple[pexpect.spawn, _StreamRecorder]:
    recorder = _StreamRecorder()
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


def _capture_success() -> None:
    child, recorder = _spawn("success")
    try:
        child.expect("MELD NEEDS INPUT")
        _settle(child)
        _snapshot(recorder, "01-entry-first-conflict")

        child.send(RIGHT)
        _settle(child)
        _snapshot(recorder, "02-right-second-conflict")

        child.send(DOWN)
        _settle(child)
        _snapshot(recorder, "03-down-second-choice")

        child.send("\r")
        _settle(child)
        _snapshot(recorder, "04-enter-stages-second-choice")

        child.send(LEFT)
        _settle(child)
        _snapshot(recorder, "05-left-returns-first-conflict")

        child.send("3")
        _settle(child)
        _snapshot(recorder, "06-number-stages-preserve-both")

        child.send("a")
        child.expect("RUN EXACT COMMAND")
        _settle(child)
        _snapshot(recorder, "07-one-continue-exact-review")

        child.send("\r")
        child.expect("CAPTURE GATE .* READ-ONLY VERIFICATION")
        _settle(child)
        _snapshot(recorder, "08-applied-receipt")

        child.send("v\r")
        child.expect("ADDITIONAL PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "09-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_defer() -> None:
    child, recorder = _spawn("defer")
    try:
        child.expect("MELD NEEDS INPUT")
        _settle(child)
        child.send("d")
        child.expect("RUN EXACT COMMAND")
        _settle(child)
        _snapshot(recorder, "10-defer-exact-review")

        child.send("\r")
        child.expect("TARGET .* UNCHANGED .* NO CHECKPOINT")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "11-deferred-receipt")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-compact-decisions-"):
        _capture_success()
        _capture_defer()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
