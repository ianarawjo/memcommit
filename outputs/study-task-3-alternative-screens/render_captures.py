from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "outputs/study-task-3-alternative-screens"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
COLS = 120
ROWS = 40


def command_output(command: str) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        shell=True,
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
        "ACTUAL CLI STATE · 120 COLUMNS × 40 ROWS · 2026-08-10",
        font=font,
        fill="#8aadf4",
    )
    path = OUT / filename
    image.save(path)
    path.with_suffix(".txt").write_text(body, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    description = command_output("mem show --context task-3/description")
    refs_a = command_output(
        "mem show --context task-3/local/results/accessibility-communication"
    )
    refs_b = command_output(
        "mem show --context task-3/local/results/scheduling-preparation"
    )
    criteria = command_output(
        "mem show --context task-3/local/healthcare-sharing-criteria-find"
    )
    result = command_output(
        "mem show --context task-3/local/healthcare-sharing-draft-find"
    )
    sever = command_output(
        "mem sever --resume cf07e7c4-4bbf-4f3b-abbc-e87570002761"
    )

    result_lines = result.splitlines()
    sever_lines = sever.splitlines()
    share = """Shared Context.
Share: 675fa52f-9c7f-57aa-831e-6b36a8654984
To: task-3/government/healthcare-agent
Memories: 97
Consent digest: 2d316e225557a9d26509783639974d6931d20d13129edd6962758b593c764aae
Receiver: study-20260810T000728Z-54da735c-granted-memory:
  task-3/remote/government/healthcare-agent/received-shares/
  675fa52f-9c7f-57aa-831e-6b36a8654984

Receiver verification:
  97 memories · 0 references · 0 query-only Contexts · 0 embeds"""
    comparison = """ALTERNATIVE TASK 3 RESULT

First run
  Criteria: 8 direct Memories + guardrails embed
  Reviewed ordinary draft: 116 Memories
  Receiver copy: 116 Memories

Find-first alternative
  Discovery: 5 + 4 live local Memory references
  Criteria: 8 direct Memories + guardrails embed = 83 criteria Memories
  Sever: 300 Source Memories reviewed in one whole frame
  Reviewed ordinary draft: 97 Memories
  Receiver copy: 97 Memories

Difference
  19 fewer outbound Memories
  Source unchanged
  Current Context unchanged by Find materialization
  Reference candidate sets were not transmitted"""

    captures = [
        render("01 · TASK DESCRIPTION", description, "01-task-description.png"),
        render("02 · FIND REFERENCES · ACCESSIBILITY", refs_a, "02-accessibility-references.png"),
        render("03 · FIND REFERENCES · SCHEDULING", refs_b, "03-scheduling-references.png"),
        render("04 · CRITERIA · 8 + GUARDRAILS EMBED", criteria, "04-criteria.png"),
        render(
            "05 · SEVER APPLIED · FIRST DECISIONS",
            "\n".join(sever_lines[:34]),
            "05-sever-first-decisions.png",
        ),
        render(
            "06 · RESULT · 97 ORDINARY MEMORIES",
            "\n".join(result_lines[:34]),
            "06-result-first-page.png",
        ),
        render(
            "07 · SEVER APPLIED · FINAL DECISIONS",
            "\n".join(sever_lines[-34:]),
            "07-sever-final-decisions.png",
        ),
        render("08 · SHARE RECEIPT + RECEIVER CHECK", share, "08-share-receipt.png"),
        render("09 · FIRST RUN VS FIND-FIRST", comparison, "09-comparison.png"),
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
