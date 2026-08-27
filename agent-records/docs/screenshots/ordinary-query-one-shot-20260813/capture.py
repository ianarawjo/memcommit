"""Capture ordinary Query's one-shot answer and host-numbered References."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import sys
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/ordinary-query-one-shot-20260813"
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
DOWN = "\x1b[B"

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


def _evidence():
    from memcommit.application.operations.search.answer_references import FindAnswerEvidence

    return (
        FindAnswerEvidence(
            "m1",
            "task-1/campus-wiki/building-access",
            "memory",
            "11111111-base-access",
            "The main entrance normally closes at 10 p.m.",
        ),
        FindAnswerEvidence(
            "m2",
            "task-1/participant/construction-updates/building-access",
            "memory",
            "22222222-change-access",
            "During construction, general access ends at 5 p.m.",
        ),
        FindAnswerEvidence(
            "m3",
            "task-1/campus-wiki/temporary-parking",
            "memory",
            "33333333-base-parking",
            "The underground garage normally accepts general vehicles.",
        ),
        FindAnswerEvidence(
            "m4",
            "task-1/participant/construction-updates/temporary-parking",
            "memory",
            "44444444-change-parking",
            "During construction, use Outdoor Parking Lot C instead.",
        ),
        FindAnswerEvidence(
            "m5",
            "task-1/campus-wiki/event-relocations",
            "memory",
            "55555555-base-event",
            "The tenth-floor hall normally remains open during recess.",
        ),
        FindAnswerEvidence(
            "m6",
            "task-1/participant/construction-updates/event-relocations",
            "memory",
            "66666666-change-event",
            "During construction, viewing and new reservations stop.",
        ),
        FindAnswerEvidence(
            "m7",
            "task-1/participant",
            "artifact",
            "77777777-comparison",
            "Compare issues: 0. Every reviewed relation is resolved.",
        ),
    )


def _run_child() -> None:
    import json

    from memcommit.commands.query.provider_policy import (
        ORDINARY_QUERY_MODEL,
        ORDINARY_QUERY_REASONING_EFFORT,
    )
    from memcommit.application.operations.query.ordinary_application import OrdinaryQueryResponse
    from memcommit.adapters.interfaces.tui.operations.query import run_query_workbench
    from memcommit.application.operations.query.answer import (
        build_ordinary_query_reference_document,
        complete_ordinary_query_answer,
        prepare_ordinary_query_answer,
    )

    evidence = _evidence()
    calls: list[str] = []

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            calls.append(prompt)
            time.sleep(1.4)
            return json.dumps(
                {
                    "outcome_kind": "ANSWER",
                    "blocks": [
                        {
                            "role": "SUPPORTED_CLAIM",
                            "text": "Access changes from 10 p.m. to 5 p.m. during construction.",
                            "source_aliases": ["m1", "m2"],
                        },
                        {
                            "role": "SUPPORTED_CLAIM",
                            "text": "Parking moves to Lot C, while hall viewing and reservations stop.",
                            "source_aliases": ["m3", "m4", "m5", "m6"],
                        },
                        {
                            "role": "SUPPORTED_CLAIM",
                            "text": "The reviewed comparison reports no unresolved issue; this is bounded to that corpus.",
                            "source_aliases": ["m7"],
                        },
                    ],
                }
            )

    provider = Provider()

    def run_ordinary(request):
        plan = prepare_ordinary_query_answer(request.question, evidence)
        answer = complete_ordinary_query_answer(plan, provider)
        document = build_ordinary_query_reference_document(evidence, answer)
        return OrdinaryQueryResponse(request, document.text, True, document)

    print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
    result = run_query_workbench(
        (
            "task-1",
            "task-1/campus-wiki",
            "task-1/participant",
            "task-1/participant/construction-updates",
        ),
        current_context="task-1",
        initial_context="task-1",
        query_targets=(),
        run_ordinary=run_ordinary,
        run_granted=lambda _request: (_ for _ in ()).throw(AssertionError()),
    )
    all_aliases_exposed = all(
        f'"alias": "m{index}"' in calls[0] for index in range(1, len(evidence) + 1)
    )
    print(
        f"ONE-SHOT VERIFICATION · CALLS {len(calls)} · "
        f"ALL {len(evidence)} ALIASES EXPOSED {all_aliases_exposed} · "
        f"{ORDINARY_QUERY_MODEL} / {ORDINARY_QUERY_REASONING_EFFORT}"
    )
    print(
        "QUERY CLOSED · READ ONLY · NO SESSION SAVE · NO SOURCE MUTATION"
        if result.status == "CLOSED"
        else f"UNEXPECTED QUERY RESULT {result!r}"
    )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
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
                    (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
    _render(recorder.getvalue(), stem)


def _capture() -> None:
    recorder = _StreamRecorder()
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
    child.logfile_read = recorder
    try:
        child.expect("MEM QUERY")
        _settle(child)
        _snapshot(recorder, "01-entry-and-frozen-scope")

        child.send(
            "What representative things differ? Give examples from both sides and check conflicts."
        )
        _settle(child)
        _snapshot(recorder, "02-question-entered")

        child.send("\r")
        child.expect("ANSWER · QUERYING")
        _settle(child, seconds=0.25)
        _snapshot(recorder, "03-one-shot-querying")

        child.expect("Access changes from 10 p.m.")
        _settle(child)
        _snapshot(recorder, "04-answer-with-host-citations")

        child.send(DOWN)
        _settle(child)
        _snapshot(recorder, "05-first-reference-focused")

        child.send(DOWN * 6)
        _settle(child)
        _snapshot(recorder, "06-aggregate-reference-focused")

        child.send("\x03")
        child.expect("ONE-SHOT VERIFICATION")
        child.expect("NO SOURCE MUTATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "07-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
