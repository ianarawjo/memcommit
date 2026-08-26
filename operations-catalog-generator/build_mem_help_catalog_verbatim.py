"""Build a monochrome A4 catalog from verbatim current Help copy."""

from __future__ import annotations

from html import escape
from pathlib import Path
from collections import Counter
import re
import sys


BUNDLED_SITE_PACKAGES = Path(
    "/Users/KimMunyeong/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/lib/python3.12/site-packages"
)
sys.path.insert(0, str(BUNDLED_SITE_PACKAGES))
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4, landscape  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
from reportlab.platypus import Paragraph  # noqa: E402

from memcommit.help_application import list_operation_help  # noqa: E402
from memcommit.interfaces.tui.operations.help.inventory import (  # noqa: E402
    COMMAND_ANNOTATIONS,
    COMMAND_DISPLAY_ALIASES,
    COMMAND_FORMS,
    HELP_CATEGORY_DESCRIPTIONS,
    HELP_CATEGORY_GROUPS,
)


OUTPUT = ROOT / "output/pdf/mem-help-catalog-a4-verbatim.pdf"

PAGE_W, PAGE_H = landscape(A4)
MARGIN_X = 10 * mm
MARGIN_BOTTOM = 10 * mm
HEADER_H = 17 * mm
FOOTER_H = 7 * mm
COLUMN_COUNT = 4
GAP = 4 * mm
CONTENT_TOP = PAGE_H - HEADER_H
CONTENT_BOTTOM = MARGIN_BOTTOM + FOOTER_H
CONTENT_H = CONTENT_TOP - CONTENT_BOTTOM
COLUMN_W = (
    PAGE_W - 2 * MARGIN_X - (COLUMN_COUNT - 1) * GAP
) / COLUMN_COUNT


CATEGORY = ParagraphStyle(
    "category",
    fontName="Helvetica-Bold",
    fontSize=8.2,
    leading=9.2,
    textColor=colors.black,
    keepWithNext=True,
)
CATEGORY_DESCRIPTION = ParagraphStyle(
    "category-description",
    fontName="Helvetica",
    fontSize=6.5,
    leading=7.7,
    textColor=colors.HexColor("#333333"),
    leftIndent=1.5,
    rightIndent=1.5,
    spaceAfter=4,
    keepWithNext=True,
)
COMMAND = ParagraphStyle(
    "command",
    fontName="Courier-Bold",
    fontSize=7.8,
    leading=8.8,
    textColor=colors.black,
    spaceBefore=1.2,
    spaceAfter=1.1,
    keepWithNext=True,
)
DESCRIPTION = ParagraphStyle(
    "description",
    fontName="Helvetica",
    fontSize=7.0,
    leading=8.35,
    textColor=colors.black,
    leftIndent=0,
    firstLineIndent=0,
    spaceAfter=1.1,
)
USE_WHEN = ParagraphStyle(
    "use-when",
    fontName="Helvetica",
    fontSize=7.0,
    leading=8.35,
    textColor=colors.HexColor("#333333"),
    leftIndent=0,
    firstLineIndent=0,
    borderColor=colors.HexColor("#a0a0a0"),
    borderWidth=0,
    borderPadding=0,
    spaceAfter=2.1,
)
FLAG_COMMAND = ParagraphStyle(
    "flag-command",
    fontName="Courier-Bold",
    fontSize=7.3,
    leading=8.2,
    textColor=colors.black,
)
FLAG_LIST = ParagraphStyle(
    "flag-list",
    fontName="Courier",
    fontSize=6.8,
    leading=7.7,
    textColor=colors.HexColor("#333333"),
    leftIndent=3 * mm,
)

FLAG_COLUMN_GROUPS = (
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

FLAG_PATTERN = re.compile(r"(?<!\w)(--[a-z][a-z0-9-]*|-[a-zA-Z])(?!\w)")


def _page_chrome(pdf: canvas.Canvas, page_number: int) -> None:
    pdf.saveState()
    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.65)
    pdf.line(MARGIN_X, PAGE_H - 12.8 * mm, PAGE_W - MARGIN_X, PAGE_H - 12.8 * mm)
    pdf.line(MARGIN_X, MARGIN_BOTTOM + 4.5 * mm, PAGE_W - MARGIN_X, MARGIN_BOTTOM + 4.5 * mm)

    pdf.setFillColor(colors.black)
    pdf.setFont("Courier-Bold", 15)
    pdf.drawString(MARGIN_X, PAGE_H - 9.0 * mm, "mem help")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(MARGIN_X + 31 * mm, PAGE_H - 8.6 * mm, "COMMAND CATALOG / BY KIND / VERBATIM HELP COPY")

    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(
        MARGIN_X,
        MARGIN_BOTTOM,
        "DESCRIPTION and USE WHEN are reproduced from the current in-package Help catalog.",
    )
    pdf.drawRightString(
        PAGE_W - MARGIN_X,
        MARGIN_BOTTOM,
        f"PAGE {page_number}",
    )
    pdf.restoreState()


def _flag_page_chrome(pdf: canvas.Canvas, page_number: int) -> None:
    pdf.saveState()
    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.65)
    pdf.line(MARGIN_X, PAGE_H - 12.8 * mm, PAGE_W - MARGIN_X, PAGE_H - 12.8 * mm)
    pdf.line(MARGIN_X, MARGIN_BOTTOM + 4.5 * mm, PAGE_W - MARGIN_X, MARGIN_BOTTOM + 4.5 * mm)
    pdf.setFillColor(colors.black)
    pdf.setFont("Courier-Bold", 15)
    pdf.drawString(MARGIN_X, PAGE_H - 9.0 * mm, "mem help")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        MARGIN_X + 31 * mm,
        PAGE_H - 8.6 * mm,
        "COMMON FLAGS / FROM AUTHORED COMMAND FORMS",
    )
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(
        MARGIN_X,
        MARGIN_BOTTOM,
        "Up to four flags per command, ranked by repetition in current Help Forms, then authored order.",
    )
    pdf.drawRightString(PAGE_W - MARGIN_X, MARGIN_BOTTOM, f"PAGE {page_number}")
    pdf.restoreState()


def _operation_title(name: str, maturity: str | None) -> str:
    aliases = COMMAND_DISPLAY_ALIASES.get(name, ())
    alias_copy = f" ({'/'.join(aliases)})" if aliases else ""
    annotations = []
    authored = COMMAND_ANNOTATIONS.get(name)
    if authored:
        annotations.append(authored.upper())
    if maturity:
        annotations.append(maturity.upper())
    annotation_copy = "" if not annotations else "  [" + " / ".join(annotations) + "]"
    return f"mem {name}{alias_copy}{annotation_copy}"


def _common_flags(name: str) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    authored_order: list[str] = []
    for form in COMMAND_FORMS.get(name, ()):
        for flag in FLAG_PATTERN.findall(form):
            counts[flag] += 1
            if flag not in authored_order:
                authored_order.append(flag)
    return tuple(
        sorted(
            authored_order,
            key=lambda flag: (-counts[flag], authored_order.index(flag)),
        )[:4]
    )


def _operation_block(operation) -> tuple[Paragraph, ...]:
    return (
        Paragraph(escape(_operation_title(operation.name, operation.maturity)), COMMAND),
        Paragraph(
            f"<b>DESCRIPTION</b>  {escape(operation.summary)}",
            DESCRIPTION,
        ),
        Paragraph(
            f"<b>USE WHEN</b>  {escape(operation.use_when)}",
            USE_WHEN,
        ),
    )


def _paragraph_height(paragraph: Paragraph) -> float:
    _width, height = paragraph.wrap(COLUMN_W, CONTENT_H)
    return height


def _category_height(paragraph: Paragraph) -> float:
    _width, height = paragraph.wrap(COLUMN_W - 3 * mm, CONTENT_H)
    return height + 3 * mm


def _draw_category(
    pdf: canvas.Canvas,
    paragraph: Paragraph,
    *,
    x: float,
    y: float,
) -> float:
    inner_width = COLUMN_W - 3 * mm
    _width, text_height = paragraph.wrap(inner_width, CONTENT_H)
    height = text_height + 3 * mm
    pdf.saveState()
    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.7)
    pdf.rect(x, y - height, COLUMN_W, height, fill=0, stroke=1)
    pdf.restoreState()
    paragraph.drawOn(pdf, x + 1.5 * mm, y - 1.5 * mm - text_height)
    return y - height


def _draw_paragraph(
    pdf: canvas.Canvas,
    paragraph: Paragraph,
    *,
    x: float,
    y: float,
) -> float:
    _width, height = paragraph.wrap(COLUMN_W, CONTENT_H)
    paragraph.drawOn(pdf, x, y - height)
    return y - height


def _draw_flag_appendix(
    pdf: canvas.Canvas,
    *,
    page_number: int,
) -> None:
    _flag_page_chrome(pdf, page_number)
    group_by_title = dict(HELP_CATEGORY_GROUPS)
    appendix_gap = 5 * mm
    appendix_columns = 3
    appendix_width = (
        PAGE_W - 2 * MARGIN_X - (appendix_columns - 1) * appendix_gap
    ) / appendix_columns

    for column_index, titles in enumerate(FLAG_COLUMN_GROUPS):
        x = MARGIN_X + column_index * (appendix_width + appendix_gap)
        y = CONTENT_TOP - 1.5 * mm
        for title in titles:
            rows = [
                (name, _common_flags(name))
                for name in group_by_title[title]
                if _common_flags(name)
            ]
            if not rows:
                continue
            title_paragraph = Paragraph(escape(title), CATEGORY)
            _width, title_text_height = title_paragraph.wrap(
                appendix_width - 3 * mm,
                CONTENT_H,
            )
            title_height = title_text_height + 3 * mm
            pdf.saveState()
            pdf.setStrokeColor(colors.black)
            pdf.setLineWidth(0.7)
            pdf.rect(x, y - title_height, appendix_width, title_height, fill=0, stroke=1)
            pdf.restoreState()
            title_paragraph.drawOn(
                pdf,
                x + 1.5 * mm,
                y - 1.5 * mm - title_text_height,
            )
            y -= title_height + 1.0 * mm

            for name, flags in rows:
                command = Paragraph(escape(f"mem {name}"), FLAG_COMMAND)
                flag_list = Paragraph(escape("  ".join(flags)), FLAG_LIST)
                _width, command_height = command.wrap(appendix_width, CONTENT_H)
                _width, flags_height = flag_list.wrap(appendix_width, CONTENT_H)
                command.drawOn(pdf, x, y - command_height)
                y -= command_height
                flag_list.drawOn(pdf, x, y - flags_height)
                y -= flags_height + 0.5 * mm
            y -= 0.8 * mm


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(PAGE_W, PAGE_H))
    pdf.setTitle("MemCommit Help command catalog - verbatim")
    pdf.setAuthor("MemCommit")
    pdf.setSubject(
        "User-study command reference using unchanged Help descriptions and use cases"
    )
    operations = {operation.name: operation for operation in list_operation_help()}
    page_number = 1
    column_index = 0
    x = MARGIN_X
    y = CONTENT_TOP - 1.5 * mm
    _page_chrome(pdf, page_number)

    def next_column() -> None:
        nonlocal page_number, column_index, x, y
        column_index += 1
        if column_index >= COLUMN_COUNT:
            pdf.showPage()
            page_number += 1
            column_index = 0
            _page_chrome(pdf, page_number)
        x = MARGIN_X + column_index * (COLUMN_W + GAP)
        y = CONTENT_TOP - 1.5 * mm

    for title, names in HELP_CATEGORY_GROUPS:
        execution, _description = HELP_CATEGORY_DESCRIPTIONS[title]
        execution_copy = f" / {execution}" if execution else ""
        title_copy = title + execution_copy
        category_paragraph = Paragraph(escape(title_copy), CATEGORY)
        first_block = _operation_block(operations[names[0]])
        category_height = (
            _category_height(category_paragraph)
            + sum(_paragraph_height(item) for item in first_block)
            + 1.3 * mm
        )
        if y - category_height < CONTENT_BOTTOM:
            next_column()
        y = _draw_category(pdf, category_paragraph, x=x, y=y)
        y -= 0.8 * mm

        for index, name in enumerate(names):
            block = _operation_block(operations[name])
            block_height = sum(_paragraph_height(item) for item in block) + 0.6 * mm
            if y - block_height < CONTENT_BOTTOM:
                next_column()
                continuation = Paragraph(escape(title_copy + " / CONTINUED"), CATEGORY)
                y = _draw_category(pdf, continuation, x=x, y=y)
                y -= 0.8 * mm
            for paragraph in block:
                y = _draw_paragraph(pdf, paragraph, x=x, y=y)
            y -= 0.6 * mm

    pdf.showPage()
    _draw_flag_appendix(pdf, page_number=page_number + 1)
    pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    build()
