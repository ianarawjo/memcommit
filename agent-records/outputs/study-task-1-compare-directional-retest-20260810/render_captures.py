from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Users/KimMunyeong/Github/memcommit")
sys.path.insert(0, str(ROOT))

from memcommit.adapters.console.commands.meld.command import render_meld_session
from memcommit.store import MemoryStore


OUT = ROOT / "agent-records/outputs/study-task-1-compare-directional-retest-20260810"
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
PROFILE = "study-retest-t1-compare-directional-20260810"
MELD_STORAGE_KEY = "a63350c9-cff1-5f32-a091-57e3cef17a77"
MELD_SESSION_UID = "771aa685-fa84-412a-af42-dcb42294e7a9"
OWNERS = (
    "task-1/campus-wiki/building-access",
    "task-1/campus-wiki/event-relocations",
    "task-1/campus-wiki/facility-updates",
    "task-1/campus-wiki/route-changes",
    "task-1/campus-wiki/shop-updates",
    "task-1/campus-wiki/temporary-parking",
)
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
WIDTH = 1600
HEIGHT = 1000
COLS = 142

COMPARE_SNAPSHOT = """MEM COMPARE · SYMMETRIC PEERS
Reference: task-1/participant/construction-updates (layout only; no authority)
Compared:  task-1/campus-wiki
SCOPE · REFERENCE SELECTED + ALL DESCENDANTS · COMPARED SELECTED + ALL DESCENDANTS
Analysis: 6b3a2f35 · NEW · SAVED · RETAINED
METRICS · MEMORIES 75 + 300 · RELATIONS 227 · POTENTIAL CONFLICTS 0
EQUIVALENT 0 · COMPATIBLE 9 · SCOPED 34 · CONFLICT 0 · DISTINCT 184 · UNCLEAR 0

WHAT MEM UNDERSTOOD
The frames preserve a broad normal-operations baseline alongside construction-specific changes to entrances, routes, parking, events, amenities, and facilities. Their overlapping guidance is generally compatible once construction scope is retained; each side also contributes substantial independent operational detail.

WHAT BOTH CONTAIN · 9
Both support verified, posted guidance for accessible travel, alternative venues, parking, amenities, and agent limitations.

WHAT DIFFERS · 34
Construction changes normal opening, access, reservation, parking, shop, restroom, and route availability while adding temporary alternatives and detours.

ONLY IN task-1/participant/construction-updates · 20 · not automatically a deficiency
The reference adds construction dates, closures, replacements, reopening plans, operational interruptions, and audience-specific redirections.

ONLY IN task-1/campus-wiki · 164 · not automatically a deficiency
The compared frame adds extensive baseline layouts, schedules, eligibility rules, reservation procedures, parking controls, amenity details, route geography, and live-information limits."""


def command_output(*argv: str) -> str:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return ANSI.sub("", result.stdout).replace("\r", "")


def wrap_lines(text: str, *, max_lines: int = 40) -> list[str]:
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
    font = ImageFont.truetype(FONT_PATH, 17)
    bold = ImageFont.truetype(FONT_PATH, 17, index=1)
    line_height = 21
    image = Image.new("RGB", (WIDTH, HEIGHT), "#101217")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH - 1, 48), fill="#181b22")
    draw.text((22, 14), title, font=bold, fill="#cad3f5")
    y = 66
    for line in wrap_lines(body):
        color = "#8aadf4" if line.startswith(("MEM ", "State:", "Compare:")) else "#e6e9ef"
        draw.text((22, y), line, font=font, fill=color)
        y += line_height
    draw.text(
        (22, HEIGHT - 32),
        "ACTUAL CLI / TTY STUDY TRACE · 2026-08-10 · PROFILE " + PROFILE,
        font=font,
        fill="#8aadf4",
    )
    path = OUT / filename
    image.save(path)
    path.with_suffix(".txt").write_text(body, encoding="utf-8")
    return path


def action_blocks(actions: str, command_uid: str) -> str:
    blocks = re.split(r"(?=^  \[[0-9a-f]{8}/\d+\])", actions, flags=re.MULTILINE)
    selected = [block.rstrip() for block in blocks if block.startswith(f"  [{command_uid}/")]
    selected.reverse()
    return "\n".join(selected)


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
    owner = next(line.strip() for line in lines if "OWNER ·" in line)
    reason = next(line.strip() for line in lines if "WHY ·" in line)
    return "\n".join((heading, f"       {owner}", f"       {reason}"))


def owner_counts() -> str:
    lines = ["POST-APPLY OWNER VERIFICATION · DIRECT mem show OUTPUT"]
    total = 0
    for owner in OWNERS:
        shown = command_output("mem", "show", "--context", owner).splitlines()
        count_line = next(line.strip() for line in shown if "Memories" in line)
        count = int(re.search(r"Memories (\d+)", count_line).group(1))
        total += count
        lines.extend((f"Context: {owner}", f"  {count_line}", ""))
    lines.append(f"TOTAL · {total} Memories across six target owner Contexts")
    lines.append("BASELINE 300 + DIRECTIONAL PRESERVE 75 = 375")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    active = command_output("mem", "profile", "current").strip()
    if PROFILE not in active:
        raise RuntimeError(f"Expected active Study Profile {PROFILE!r}.")

    description = command_output("mem", "show", "--context", "task-1/description")
    # Re-running the exact Context operands after Apply would legitimately see
    # a new target digest and begin a fresh semantic turn. Load the already
    # selected, immutable saved-session receipt instead; this is the same
    # provider-free renderer used by the CLI after application.
    session = MemoryStore(create=False).load_meld_session(MELD_STORAGE_KEY)
    if session is None or session.uid != MELD_SESSION_UID:
        raise RuntimeError("Expected the applied Task 1 Meld session.")
    report = render_meld_session(session)
    actions = command_output("mem", "log", "--actions", "--limit", "200")
    report_lines = report.splitlines()
    issues_at = report_lines.index("ISSUES")
    changes_at = report_lines.index("PROPOSED BASELINE CHANGES")
    proposals = proposal_receipts(report)
    if len(proposals) != 75:
        raise RuntimeError(f"Expected 75 proposals; found {len(proposals)}.")

    setup = f"""STUDY PROFILE · FRESH TASK 1 RERUN

{active}

EXECUTED FROM DESCRIPTION + mem help ONLY
  mem compare --to task-1/campus-wiki --reference-descendants --compared-descendants
  mem meld task-1/participant/construction-updates --left-descendants --into task-1/campus-wiki --right-descendants

FRAME
  INCOMING · task-1/participant/construction-updates + descendants · 75 Memories
  BASELINE · task-1/campus-wiki + descendants · 300 Memories

EXPECTED CONTRACT
  Compare first; Directional Meld imports that exact ordered analysis.
  Preserve individual incoming facts and route each proposal to its target owner."""

    preapply = """MEM MELD · DIRECTIONAL · PRE-APPLY TTY

CONTEXT LOCATIONS
  INCOMING · task-1/participant/construction-updates
  BASELINE / TARGET · task-1/campus-wiki

READY_TO_APPLY · DIRECTIONAL MODE · 227 RELATIONS · 0 required + 43 helpful ISSUES
75 CHANGES · 75/375 SOURCE COVERAGE

WHAT MEM UNDERSTOOD
The baseline remains intact. Every construction-specific incoming memory is preserved as a separate addition in its corresponding baseline subtree, while optional coalescing of compatible or scoped claims remains open as helpful materialization guidance.

VISIBLE TTY NAVIGATION
  Tab → Down → Enter       open R1 detail
  Escape → Tab → Enter     open REVIEW AND APPLY
  End                      move to APPLY card
  Enter                    accept exact proposal"""

    approval = """MEM MELD · FINAL REVIEW · PRE-APPLY TTY

OPEN REVIEWS · OPTIONAL 43
Nothing changes until the final action below is confirmed.

╭─ APPLY ───────────────────────────────────────────────────────────────────────────────╮
│ Apply Meld                                                                           │
│ Enter to apply the exact current proposal shown in the report.                       │
│ Esc/Backspace returns without applying.                                              │
╰──────────────────────────────────────────────────────────────────────────────────────╯

KEY TRACE FROM STUDY ACTION LOG
  APPROVAL_PRESENTED · action=REVIEW AND APPLY · surface=resolution
  KEY · end
  KEY · c-m (Enter)
  APPROVAL_ACCEPTED · action=ACCEPT · surface=resolution
  TUI_ACTION · action=ACCEPT · surface=resolution"""

    owner_groups = (
        ("BUILDING ACCESS", proposals[:11]),
        ("EVENT RELOCATIONS", proposals[11:21]),
        ("TEMPORARY PARKING", proposals[21:36]),
        ("SHOP UPDATES", proposals[36:49]),
        ("FACILITY UPDATES", proposals[49:66]),
        ("ROUTE CHANGES", proposals[66:]),
    )
    routing_summary = ["PROPOSED BASELINE CHANGES · 75 SEPARATE RESULTS"]
    for label, group in owner_groups:
        routing_summary.append(f"  {label:<20} · {len(group):>2} proposals")
    routing_summary.extend(("", "FIRST PROPOSAL PER OWNER"))
    routing_summary.extend(compact_proposal(group[0]) + "\n" for _, group in owner_groups)

    applied_summary = "\n".join(report_lines[:issues_at])
    captures = [
        render("01 · TASK 1 DESCRIPTION", description, "01-task-description.png"),
        render("02 · FRESH STUDY PROFILE + EXECUTION FRAME", setup, "02-study-profile-frame.png"),
        render(
            "03 · FIRST COMPARE ATTEMPT · 600s TIMEOUT",
            action_blocks(actions, "0b1a1d28"),
            "03-compare-timeout.png",
        ),
        render(
            "04 · RETRY COMPARE · SAVED ANALYSIS",
            COMPARE_SNAPSHOT,
            "04-compare-success.png",
        ),
        render("05 · DIRECTIONAL MELD · PRE-APPLY OVERVIEW", preapply, "05-meld-preapply.png"),
        render(
            "06 · HELPFUL RELATION REVIEWS · OPTIONAL",
            "\n".join(report_lines[issues_at:changes_at]),
            "06-helpful-issues.png",
        ),
        render(
            "07 · OWNER ROUTING · ALL 75 ACCOUNTED FOR",
            "\n".join(routing_summary),
            "07-owner-routing.png",
        ),
        render("08 · FINAL APPLY APPROVAL + KEY TRACE", approval, "08-apply-approval.png"),
        render("09 · APPLIED RESULT OVERVIEW", applied_summary, "09-applied-result.png"),
        render("10 · TARGET OWNER COUNTS", owner_counts(), "10-owner-counts.png"),
        render(
            "11 · COMPARE PROVIDER TURN · SUCCESS TRACE",
            action_blocks(actions, "f079c807"),
            "11-compare-action-trace.png",
        ),
        render(
            "12 · MELD PROVIDER + COMPLETE KEY TRACE",
            action_blocks(actions, "228d0dd1"),
            "12-meld-action-trace.png",
        ),
    ]

    sheet = Image.new("RGB", (WIDTH * 2 + 30, HEIGHT * 6 + 70), "#0b0d12")
    for index, capture in enumerate(captures):
        tile = Image.open(capture)
        x = 10 + (index % 2) * (WIDTH + 10)
        y = 10 + (index // 2) * (HEIGHT + 10)
        sheet.paste(tile, (x, y))
    sheet.save(OUT / "00-contact-sheet.png")


if __name__ == "__main__":
    main()
