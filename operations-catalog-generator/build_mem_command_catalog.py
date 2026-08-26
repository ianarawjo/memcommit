"""Build a one-page A4 participant command catalog from current Help groups."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output/pdf/mem-command-catalog-a4-sample.pdf"

INK = HexColor("#1e2030")
MUTED = HexColor("#5b6078")
RULE = HexColor("#b8c0d9")
PAPER = HexColor("#fbfcff")
PANEL = HexColor("#f2f5fb")
BLUE = HexColor("#4f7fc9")
BLUE_DARK = HexColor("#315a9a")
BLUE_PALE = HexColor("#dfeaf8")
TEAL = HexColor("#338e86")
YELLOW = HexColor("#9b741d")
LAVENDER = HexColor("#7063a8")

COMMAND_DISPLAY_ALIASES = {
    "delete": ("remove",),
    "list": ("ls",),
}

HELP_CATEGORY_GROUPS = (
    (
        "BROWSE & NAVIGATE",
        ("status", "pwd", "contexts", "list", "show", "switch", "checkout", "rename"),
    ),
    (
        "CREATE, COPY & CONNECT",
        ("init", "add", "copy", "branch", "import", "reference", "embed"),
    ),
    ("SEARCH & EXPLAIN", ("find", "search", "query", "summarize")),
    (
        "DETERMINISTIC CONTENT CHANGES",
        ("edit", "move", "replace", "chunk", "delete", "clear", "merge", "dedup"),
    ),
    (
        "SEMANTIC TRANSFORMATIONS",
        (
            "atomize",
            "distill",
            "elaborate",
            "translate",
            "forget",
            "resolve",
            "dedun",
            "update",
            "meld",
            "sever",
        ),
    ),
    (
        "CHECK, COMPARE & REVIEW",
        (
            "compare",
            "find-duplicates",
            "find-redundancies",
            "find-ambiguities",
            "find-conflicts",
            "audit",
            "impact",
            "review",
            "fit",
            "check-conformance",
        ),
    ),
    ("GROUND WORKBENCH", ("ground",)),
    (
        "HISTORY & RECOVERY",
        ("log", "diff", "trace", "rationale", "checkpoint", "undo", "redo", "revert"),
    ),
    ("PROFILES", ("profile",)),
    ("SHARING & PROTECTION", ("share", "lock", "unlock")),
    (
        "SYSTEM & STUDY TOOLS",
        ("help", "provider", "shell-init", "config", "init-study", "eval"),
    ),
)

HELP_CATEGORY_DESCRIPTIONS = {
    "BROWSE & NAVIGATE": ("NO LLM",),
    "CREATE, COPY & CONNECT": ("NO LLM",),
    "SEARCH & EXPLAIN": ("MIXED",),
    "DETERMINISTIC CONTENT CHANGES": ("NO LLM",),
    "SEMANTIC TRANSFORMATIONS": ("LLM-BASED",),
    "CHECK, COMPARE & REVIEW": ("MIXED",),
    "GROUND WORKBENCH": ("LLM-BASED",),
    "HISTORY & RECOVERY": ("MIXED",),
    "PROFILES": ("NO LLM",),
    "SHARING & PROTECTION": ("NO LLM",),
    "SYSTEM & STUDY TOOLS": (None,),
}


SHORT = {
    "status": "current Context overview",
    "pwd": "current Context name",
    "contexts": "available Context catalog",
    "list": "direct items and children",
    "show": "inspect a Memory or Context",
    "switch": "choose the active Context",
    "checkout": "Git-style switch or branch",
    "rename": "rename a Context subtree",
    "init": "create an empty Context",
    "add": "add one or more Memories",
    "copy": "copy directly owned Memories",
    "branch": "copy a Context as a branch",
    "import": "import a clean baseline",
    "reference": "create an immutable snapshot",
    "embed": "create a live ownership link",
    "find": "find exact text or regex",
    "search": "semantic Memory retrieval",
    "query": "answer from Context knowledge",
    "summarize": "LLM Context overview",
    "edit": "replace Memory content",
    "move": "move directly owned Memories",
    "replace": "literal or regex substitution",
    "chunk": "mechanical Memory splitting",
    "delete": "remove a Context or item",
    "clear": "empty Context contents",
    "merge": "deterministic Source into Target",
    "dedup": "remove exact duplicates",
    "atomize": "split into atomic Memories",
    "distill": "derive higher-level Rules",
    "elaborate": "expand an abstract proposition",
    "translate": "save a translated view",
    "forget": "keep, edit, or drop by instruction",
    "resolve": "repair incompatibilities",
    "dedun": "resolve semantic redundancies",
    "update": "reconcile Source into Target",
    "meld": "semantic Context incorporation",
    "sever": "derive a filtered Result",
    "compare": "semantic two-Context comparison",
    "find-duplicates": "report exact duplicates",
    "find-redundancies": "report semantic redundancy",
    "find-ambiguities": "report ambiguous Memories",
    "find-conflicts": "report conflicting Memories",
    "audit": "combined quality checks",
    "impact": "preview operation effects",
    "review": "inspect saved evidence or report",
    "fit": "judge joint compatibility",
    "check-conformance": "test Examples against Rules",
    "ground": "shape Goal, Rules, and Examples",
    "log": "search recorded history",
    "diff": "checkpoint or Update changes",
    "trace": "trace Memory lineage",
    "rationale": "explain Memory provenance",
    "checkpoint": "save a recovery point",
    "undo": "reverse the latest command",
    "redo": "replay an undone command",
    "revert": "restore a selected checkpoint",
    "profile": "manage Profile stores",
    "share": "deliver a grant-backed Context",
    "lock": "block writes",
    "unlock": "restore writes",
    "help": "interactive command browser",
    "provider": "choose a semantic provider",
    "shell-init": "print shell integration",
    "config": "global configuration",
    "init-study": "create an isolated study pair",
    "eval": "run evaluation campaigns",
}

ANNOTATION = {
    "config": "LEGACY",
    "eval": "LEGACY",
    "ground": "PARTIAL",
    "import": "PARTIAL",
    "provider": "PARTIAL",
    "translate": "PARTIAL",
}

COLUMN_GROUPS = (
    ("BROWSE & NAVIGATE", "CREATE, COPY & CONNECT", "SEARCH & EXPLAIN"),
    (
        "DETERMINISTIC CONTENT CHANGES",
        "SEMANTIC TRANSFORMATIONS",
        "GROUND WORKBENCH",
    ),
    (
        "CHECK, COMPARE & REVIEW",
        "HISTORY & RECOVERY",
        "PROFILES",
        "SHARING & PROTECTION",
        "SYSTEM & STUDY TOOLS",
    ),
)


def _fit_text(text: str, font: str, size: float, width: float) -> str:
    if stringWidth(text, font, size) <= width:
        return text
    suffix = "..."
    candidate = text
    while candidate and stringWidth(candidate + suffix, font, size) > width:
        candidate = candidate[:-1]
    return candidate.rstrip() + suffix


def _badge_color(execution: str | None):
    if execution == "NO LLM":
        return TEAL
    if execution == "LLM-BASED":
        return LAVENDER
    if execution == "MIXED":
        return YELLOW
    return MUTED


def _draw_category(
    pdf: canvas.Canvas,
    *,
    title: str,
    commands: tuple[str, ...],
    x: float,
    y: float,
    width: float,
) -> float:
    execution = HELP_CATEGORY_DESCRIPTIONS[title][0]
    header_h = 6.2 * mm
    row_h = 4.25 * mm
    height = header_h + len(commands) * row_h + 1.2 * mm

    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(RULE)
    pdf.roundRect(x, y - height, width, height, 2.2 * mm, fill=1, stroke=1)

    pdf.setFillColor(BLUE_PALE)
    pdf.roundRect(
        x,
        y - header_h,
        width,
        header_h,
        2.2 * mm,
        fill=1,
        stroke=0,
    )
    pdf.setFillColor(BLUE_PALE)
    pdf.rect(x, y - header_h, width, 2.2 * mm, fill=1, stroke=0)

    pdf.setFillColor(BLUE_DARK)
    pdf.setFont("Helvetica-Bold", 7.6)
    pdf.drawString(x + 2.2 * mm, y - 4.15 * mm, title)

    if execution:
        badge = execution
        badge_size = 6.2
        badge_w = stringWidth(badge, "Helvetica-Bold", badge_size) + 3.2 * mm
        badge_x = x + width - badge_w - 1.7 * mm
        pdf.setFillColor(_badge_color(execution))
        pdf.roundRect(
            badge_x,
            y - 4.95 * mm,
            badge_w,
            3.7 * mm,
            1.7 * mm,
            fill=1,
            stroke=0,
        )
        pdf.setFillColor(PAPER)
        pdf.setFont("Helvetica-Bold", badge_size)
        pdf.drawCentredString(
            badge_x + badge_w / 2,
            y - 3.98 * mm,
            badge,
        )

    command_x = x + 2.2 * mm
    description_x = x + 37.0 * mm
    description_w = width - (description_x - x) - 2.0 * mm
    baseline = y - header_h - 3.35 * mm
    for command in commands:
        aliases = COMMAND_DISPLAY_ALIASES.get(command, ())
        alias_text = f" ({'/'.join(aliases)})" if aliases else ""
        command_text = f"mem {command}{alias_text}"
        pdf.setFillColor(INK)
        pdf.setFont("Courier-Bold", 7.15)
        pdf.drawString(command_x, baseline, command_text)

        annotation = ANNOTATION.get(command)
        description = SHORT[command]
        if annotation:
            description = f"{description} [{annotation}]"
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7.0)
        pdf.drawString(
            description_x,
            baseline,
            _fit_text(description, "Helvetica", 7.0, description_w),
        )
        baseline -= row_h

    return y - height


def _draw_reference_box(
    pdf: canvas.Canvas,
    *,
    title: str,
    rows: tuple[tuple[str, str], ...],
    x: float,
    y: float,
    width: float,
) -> float:
    header_h = 5.6 * mm
    row_h = 4.2 * mm
    height = header_h + len(rows) * row_h + 1.0 * mm
    pdf.setFillColor(PAPER)
    pdf.setStrokeColor(RULE)
    pdf.roundRect(x, y - height, width, height, 2.0 * mm, fill=1, stroke=1)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 7.6)
    pdf.drawString(x + 2.2 * mm, y - 3.9 * mm, title)

    baseline = y - header_h - 3.2 * mm
    for key, meaning in rows:
        pdf.setFillColor(BLUE_DARK)
        pdf.setFont("Courier-Bold", 7.0)
        pdf.drawString(x + 2.2 * mm, baseline, key)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7.0)
        pdf.drawString(x + 23.5 * mm, baseline, meaning)
        baseline -= row_h
    return y - height


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = landscape(A4)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(page_w, page_h))
    pdf.setTitle("MemCommit participant command catalog - A4 sample")
    pdf.setAuthor("MemCommit")
    pdf.setSubject("One-page BY KIND command reference for user-study participants")

    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    margin_x = 9.5 * mm
    header_y = page_h - 9.0 * mm
    pdf.setFillColor(INK)
    pdf.setFont("Courier-Bold", 18)
    pdf.drawString(margin_x, header_y, "mem help")

    title_x = margin_x + 36.0 * mm
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(title_x, header_y + 0.4 * mm, "PARTICIPANT COMMAND CATALOG")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(
        title_x,
        header_y - 4.2 * mm,
        "BY KIND  /  66 COMMANDS  /  QUICK REFERENCE  /  A4 LANDSCAPE",
    )

    badge_w = 31 * mm
    pdf.setFillColor(BLUE)
    pdf.roundRect(
        page_w - margin_x - badge_w,
        header_y - 4.9 * mm,
        badge_w,
        8.7 * mm,
        2.0 * mm,
        fill=1,
        stroke=0,
    )
    pdf.setFillColor(PAPER)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawCentredString(
        page_w - margin_x - badge_w / 2,
        header_y - 1.55 * mm,
        "STUDY REFERENCE",
    )

    rule_y = page_h - 23.0 * mm
    pdf.setStrokeColor(BLUE)
    pdf.setLineWidth(1.2)
    pdf.line(margin_x, rule_y, page_w - margin_x, rule_y)

    group_by_title = dict(HELP_CATEGORY_GROUPS)
    gap = 4.0 * mm
    content_w = page_w - 2 * margin_x
    column_w = (content_w - 2 * gap) / 3
    column_top = rule_y - 4.0 * mm
    column_xs = (
        margin_x,
        margin_x + column_w + gap,
        margin_x + 2 * (column_w + gap),
    )

    endings: list[float] = []
    for column_index, titles in enumerate(COLUMN_GROUPS):
        y = column_top
        for title in titles:
            y = _draw_category(
                pdf,
                title=title,
                commands=group_by_title[title],
                x=column_xs[column_index],
                y=y,
                width=column_w,
            )
            y -= 2.2 * mm
        endings.append(y)

    _draw_reference_box(
        pdf,
        title="COMMON LOCATORS",
        rows=(
            ("NAME", "canonical Context name"),
            (".", "current Context snapshot"),
            ("..", "parent of current snapshot"),
            ("./CHILD", "relative child path"),
            ("../PATH", "relative parent path"),
            ("UID", "Memory UID or prefix"),
            ("CONTEXT:UID", "qualified Memory locator"),
        ),
        x=column_xs[0],
        y=endings[0],
        width=column_w,
    )

    _draw_reference_box(
        pdf,
        title="HELP KEYS",
        rows=(
            ("UP / DOWN", "move through rows"),
            ("LEFT / RIGHT", "change view or expand"),
            ("TAB", "move to next kind"),
            ("ENTER", "open command forms"),
            ("H", "open full Help"),
            ("Q / ESC", "close Help"),
        ),
        x=column_xs[1],
        y=endings[1],
        width=column_w,
    )

    footer_y = 5.0 * mm
    pdf.setStrokeColor(RULE)
    pdf.setLineWidth(0.5)
    pdf.line(margin_x, footer_y + 3.2 * mm, page_w - margin_x, footer_y + 3.2 * mm)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 6.8)
    pdf.drawString(
        margin_x,
        footer_y,
        "Participant aid sample - descriptions are intentionally compact; command behavior remains authoritative in mem help.",
    )
    pdf.drawRightString(
        page_w - margin_x,
        footer_y,
        "MemCommit / BY KIND / one-page study catalog",
    )

    pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    build()
