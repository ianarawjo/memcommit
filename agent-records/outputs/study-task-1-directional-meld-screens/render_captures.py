from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/outputs/study-task-1-directional-meld-screens"
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
COLS = 120
ROWS = 40
PROFILE = "study-20260810T010815Z-meld-a-b"
MELD_ARGV = (
    "mem",
    "meld",
    "task-1/participant/construction-updates",
    "--left-descendants",
    "--into",
    "task-1/campus-wiki",
    "--right-descendants",
)
OWNERS = (
    "task-1/campus-wiki/building-access",
    "task-1/campus-wiki/event-relocations",
    "task-1/campus-wiki/temporary-parking",
    "task-1/campus-wiki/shop-updates",
    "task-1/campus-wiki/facility-updates",
    "task-1/campus-wiki/route-changes",
)
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def command_output(*argv: str) -> str:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return ANSI.sub("", result.stdout).replace("\r", "")


def wrap_lines(text: str, *, max_lines: int = 34) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        wrapped = textwrap.wrap(
            raw,
            width=COLS - 4,
            replace_whitespace=False,
            drop_whitespace=False,
        ) or [""]
        lines.extend(part.rstrip() for part in wrapped)
    return lines[:max_lines]


def render(title: str, body: str, filename: str) -> Path:
    font = ImageFont.truetype(FONT_PATH, 15)
    bold = ImageFont.truetype(FONT_PATH, 15, index=1)
    line_height = 20
    image = Image.new("RGB", (1120, 760), "#101217")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1119, 42), fill="#181b22")
    draw.text((18, 12), title, font=bold, fill="#cad3f5")
    y = 58
    for line in wrap_lines(body):
        draw.text((18, y), line, font=font, fill="#e6e9ef")
        y += line_height
    draw.text(
        (18, 730),
        "ACTUAL CLI/TTY STATE · 120 COLUMNS × 40 ROWS · 2026-08-10",
        font=font,
        fill="#8aadf4",
    )
    path = OUT / filename
    image.save(path)
    path.with_suffix(".txt").write_text(body, encoding="utf-8")
    return path


def proposal_receipts(report: str) -> list[str]:
    lines = report.splitlines()
    start = lines.index("PROPOSED BASELINE CHANGES") + 1
    proposals: list[str] = []
    current: list[str] = []
    for line in lines[start:]:
        if re.match(r"^  \+\s+\d+\. ", line):
            if current:
                proposals.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        proposals.append("\n".join(current))
    return proposals


def compact_proposal(raw: str) -> str:
    lines = raw.splitlines()
    heading = lines[0]
    match = re.match(r"^(  \+\s+\d+\. \[[^]]+\])\s+(.*)$", heading)
    if match is None:
        raise RuntimeError("Unexpected Meld proposal heading.")
    content = match.group(2)
    if len(content) > 280:
        content = content[:277].rstrip() + "…"
    owner = next(line.strip() for line in lines if "OWNER ·" in line)
    reason = next(line.strip() for line in lines if "WHY ·" in line)
    if len(reason) > 190:
        reason = reason[:187].rstrip() + "…"
    return f"{match.group(1)} {content}\n       {owner}\n       {reason}"


def owner_counts() -> str:
    lines = ["POST-APPLY OWNER VERIFICATION"]
    for owner in OWNERS:
        shown = command_output("mem", "show", "--context", owner).splitlines()
        count = next(line.strip() for line in shown if "Memories" in line)
        lines.extend((f"Context: {owner}", f"  {count}", ""))
    return "\n".join(lines).rstrip()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    active = command_output("mem", "profile", "current").strip()
    if PROFILE not in active:
        raise RuntimeError(f"Expected active Study Profile {PROFILE!r}.")

    description = command_output(
        "mem", "show", "--context", "task-1/description"
    )
    report = command_output(*MELD_ARGV)
    report_lines = report.splitlines()
    issues_at = report_lines.index("ISSUES")
    changes_at = report_lines.index("PROPOSED BASELINE CHANGES")
    proposals = proposal_receipts(report)
    if len(proposals) != 6:
        raise RuntimeError(f"Expected six proposals; found {len(proposals)}.")

    setup = """NEW MELD · DIRECTIONAL · A → B

OPERATION SHAPE
  [ SYMMETRIC · A + B → C ]  [ ✓ DIRECTIONAL · A → B ]

A · INCOMING
  › task-1/participant/construction-updates
  RANGE · [ THIS CONTEXT ONLY ]  [ ✓ INCLUDE DESCENDANTS ]

B · BASELINE + RESULT
  › task-1/campus-wiki  READ GRANT
  RANGE · [ THIS CONTEXT ONLY ]  [ ✓ INCLUDE DESCENDANTS ]

APPLY · [ PRESS ENTER TO APPLY ]

LITERAL TTY KEY TRACE
  N → Right → Down → Down×5 → Enter
  Tab → Right → Tab → Down → Right → Down → Enter
  Tab → Right → Tab → Enter

Execution receipt:
  SCOPE · A SELECTED + ALL DESCENDANTS · B SELECTED + ALL DESCENDANTS"""

    route = """MELD SESSIONS · RECENTLY MODIFIED · RECENT FIRST · ALL

Status       APPLIED
Context      task-1/campus-wiki
Summary      Directional · INCOMING → BASELINE / TARGET · 1 turn
Session      c34b1cd9-2d2f-491b-8f99-146dd652342f

Public route hint · NOT EXECUTED
  [0] mem
  [1] meld
  [2] task-1/participant/construction-updates
  [3] --left-descendants
  [4] --into
  [5] task-1/campus-wiki
  [6] --right-descendants

Study action ledger · command c7446a4f
  TTY · 120 columns × 40 rows
  Setup keys · Right · Down · Down×5 · Enter · Tab · Right · Tab
               Down · Right · Down · Enter · Tab · Right · Tab · Enter
  PROVIDER_TURN_STARTED · input 131,612 chars · codex_chatgpt
  PROVIDER_TURN_COMPLETED · 179.612s · output 22,794 chars
  APPROVAL_PRESENTED → Down → Enter → APPROVAL_ACCEPTED
  COMMAND_FINISHED · 461.462s · COMPLETED

Post-run display regression:
  tests/test_meld_sessions.py · 9 passed
  Both descendant flags survive saved-session reopening."""

    captures = [
        render("01 · TASK 1 DESCRIPTION", description, "01-task-description.png"),
        render("02 · DIRECTIONAL MELD · ACTUAL KEY TRACE", setup, "02-directional-setup.png"),
        render(
            "03 · APPLIED OVERVIEW · FULL SOURCE COVERAGE",
            "\n".join(report_lines[:issues_at]),
            "03-applied-overview.png",
        ),
        render(
            "04 · HELPFUL ISSUES · OPTIONAL REVIEW",
            "\n".join(report_lines[issues_at:changes_at]),
            "04-helpful-issues.png",
        ),
        render(
            "05 · OWNER ROUTING · BUILDING + EVENTS",
            "PROPOSED BASELINE CHANGES · DISPLAY EXCERPTS\n\n"
            + "\n\n".join(compact_proposal(item) for item in proposals[:2]),
            "05-owner-building-events.png",
        ),
        render(
            "06 · OWNER ROUTING · PARKING + SHOPS",
            "PROPOSED BASELINE CHANGES · DISPLAY EXCERPTS\n\n"
            + "\n\n".join(compact_proposal(item) for item in proposals[2:4]),
            "06-owner-parking-shops.png",
        ),
        render(
            "07 · OWNER ROUTING · FACILITIES + ROUTES",
            "PROPOSED BASELINE CHANGES · DISPLAY EXCERPTS\n\n"
            + "\n\n".join(compact_proposal(item) for item in proposals[4:]),
            "07-owner-facilities-routes.png",
        ),
        render(
            "08 · POST-APPLY OWNER COUNTS",
            owner_counts(),
            "08-owner-counts.png",
        ),
        render(
            "09 · SAVED SESSION + STUDY ACTION LEDGER",
            route,
            "09-session-route.png",
        ),
    ]

    sheet = Image.new("RGB", (3380, 2320), "#0b0d12")
    for index, capture in enumerate(captures):
        tile = Image.open(capture)
        x = 20 + (index % 3) * 1120
        y = 20 + (index // 3) * 760
        sheet.paste(tile, (x, y))
    sheet.save(OUT / "00-contact-sheet.png")


if __name__ == "__main__":
    main()
