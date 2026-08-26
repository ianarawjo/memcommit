"""Build a four-page A4 user-study Help reference."""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
import re
import sys


BUNDLED_SITE_PACKAGES = Path(
    "/Users/KimMunyeong/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/lib/python3.12/site-packages"
)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BUNDLED_SITE_PACKAGES))
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
    HELP_COMMON_KEYS,
    HELP_COMMON_LOCATORS,
    HELP_CORE_CONCEPTS,
)


OUTPUT = ROOT / "output/pdf/mem-help-study-reference-a4-four-page.pdf"
PAGE_W, PAGE_H = landscape(A4)
MARGIN_X = 10 * mm
MARGIN_BOTTOM = 10 * mm
HEADER_H = 17 * mm
FOOTER_H = 7 * mm
CONTENT_TOP = PAGE_H - HEADER_H
CONTENT_BOTTOM = MARGIN_BOTTOM + FOOTER_H
CONTENT_H = CONTENT_TOP - CONTENT_BOTTOM

INK = colors.black
SUBTLE = colors.HexColor("#333333")
RULE = colors.HexColor("#777777")

COLUMN_COUNT = 3
COLUMN_GAP = 5 * mm
COLUMN_W = (
    PAGE_W - 2 * MARGIN_X - (COLUMN_COUNT - 1) * COLUMN_GAP
) / COLUMN_COUNT


SECTION = ParagraphStyle(
    "section",
    fontName="Helvetica-Bold",
    fontSize=9.2,
    leading=10.4,
    textColor=INK,
)
PRIMER_LABEL = ParagraphStyle(
    "primer-label",
    fontName="Courier-Bold",
    fontSize=7.5,
    leading=8.5,
    textColor=INK,
)
PRIMER_BODY = ParagraphStyle(
    "primer-body",
    fontName="Helvetica",
    fontSize=7.5,
    leading=9.0,
    textColor=SUBTLE,
)
PRIMER_BODY_TIGHT = ParagraphStyle(
    "primer-body-tight",
    parent=PRIMER_BODY,
    fontSize=7.0,
    leading=8.2,
)
CATEGORY = ParagraphStyle(
    "category",
    fontName="Helvetica-Bold",
    fontSize=8.6,
    leading=9.8,
    textColor=INK,
)
COMMAND = ParagraphStyle(
    "command",
    fontName="Courier-Bold",
    fontSize=8.1,
    leading=9.1,
    textColor=INK,
)
DESCRIPTION = ParagraphStyle(
    "description",
    fontName="Helvetica",
    fontSize=7.4,
    leading=8.75,
    textColor=INK,
)
USE_WHEN = ParagraphStyle(
    "use-when",
    fontName="Helvetica",
    fontSize=7.4,
    leading=8.75,
    textColor=SUBTLE,
)
OPTION_LINE = ParagraphStyle(
    "option-line",
    fontName="Courier",
    fontSize=6.5,
    leading=7.5,
    textColor=SUBTLE,
    leftIndent=2 * mm,
)
ROUTE_LINE = ParagraphStyle(
    "route-line",
    fontName="Helvetica",
    fontSize=6.5,
    leading=7.5,
    textColor=SUBTLE,
    leftIndent=2 * mm,
)


FLAG_PATTERN = re.compile(r"(?<!\w)(--[a-z][a-z0-9-]*|-[a-zA-Z])(?!\w)")

INPUT_ROUTES = {
    "copy": "MEMORY absent -> ERROR; TARGET omitted -> CURRENT",
    "move": "MEMORY absent -> ERROR; TARGET omitted -> CURRENT",
    "merge": "bare TTY -> PICK SOURCE + TARGET; SOURCE only -> TARGET=CURRENT",
    "distill": "bare -> SOURCE=CURRENT + TARGET=CURRENT",
    "elaborate": "bare -> SOURCE=CURRENT + TARGET=CURRENT",
    "update": (
        "bare -> PICK SOURCE + TARGET; --from only -> TARGET=CURRENT; "
        "--to only -> SOURCE=CURRENT"
    ),
    "meld": (
        "bare -> PICK MODE + ENDPOINTS; incoming only -> BASELINE=CURRENT; "
        "--from only -> BASELINE=CURRENT; --into only -> INCOMING=CURRENT"
    ),
    "impact": (
        "directional --from only -> TARGET=CURRENT; "
        "--to only -> SOURCE=CURRENT"
    ),
}


def _page_chrome(
    pdf: canvas.Canvas,
    *,
    page_number: int,
    heading: str,
    footer: str,
) -> None:
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.65)
    pdf.line(MARGIN_X, PAGE_H - 12.8 * mm, PAGE_W - MARGIN_X, PAGE_H - 12.8 * mm)
    pdf.line(MARGIN_X, MARGIN_BOTTOM + 4.5 * mm, PAGE_W - MARGIN_X, MARGIN_BOTTOM + 4.5 * mm)
    pdf.setFillColor(INK)
    pdf.setFont("Courier-Bold", 15)
    pdf.drawString(MARGIN_X, PAGE_H - 9.0 * mm, "mem help")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(MARGIN_X + 31 * mm, PAGE_H - 8.6 * mm, heading)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(MARGIN_X, MARGIN_BOTTOM, footer)
    pdf.drawRightString(PAGE_W - MARGIN_X, MARGIN_BOTTOM, f"PAGE {page_number} / 4")
    pdf.restoreState()


def _draw_rule_title(
    pdf: canvas.Canvas,
    *,
    text: str,
    x: float,
    y: float,
    width: float,
    style: ParagraphStyle = SECTION,
) -> float:
    paragraph = Paragraph(escape(text), style)
    inner_width = width - 3 * mm
    _wrapped_width, text_height = paragraph.wrap(inner_width, CONTENT_H)
    height = text_height + 3 * mm
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.7)
    pdf.rect(x, y - height, width, height, fill=0, stroke=1)
    pdf.restoreState()
    paragraph.drawOn(pdf, x + 1.5 * mm, y - 1.5 * mm - text_height)
    return y - height


def _draw_labeled_rows(
    pdf: canvas.Canvas,
    *,
    rows: tuple[tuple[str, str], ...],
    x: float,
    y: float,
    width: float,
    label_width: float,
    body_style: ParagraphStyle = PRIMER_BODY,
    gap_after: float = 1.5 * mm,
) -> float:
    for label, body in rows:
        label_paragraph = Paragraph(escape(label), PRIMER_LABEL)
        body_paragraph = Paragraph(escape(body), body_style)
        _w, label_height = label_paragraph.wrap(label_width, CONTENT_H)
        _w, body_height = body_paragraph.wrap(width - label_width, CONTENT_H)
        height = max(label_height, body_height)
        label_paragraph.drawOn(pdf, x, y - label_height)
        body_paragraph.drawOn(pdf, x + label_width, y - body_height)
        y -= height + gap_after
    return y


def _draw_primer_page(pdf: canvas.Canvas) -> None:
    _page_chrome(
        pdf,
        page_number=1,
        heading="PRIMER / LOCATORS / INPUT RESOLUTION / KEYS",
        footer="Read semantic requirements separately from optional CLI spellings.",
    )
    xs = [MARGIN_X + index * (COLUMN_W + COLUMN_GAP) for index in range(3)]
    top = CONTENT_TOP - 1.5 * mm

    y = _draw_rule_title(pdf, text="CORE CONCEPTS", x=xs[0], y=top, width=COLUMN_W)
    y -= 1.5 * mm
    y = _draw_labeled_rows(
        pdf,
        rows=HELP_CORE_CONCEPTS,
        x=xs[0],
        y=y,
        width=COLUMN_W,
        label_width=20 * mm,
        body_style=PRIMER_BODY_TIGHT,
        gap_after=1.2 * mm,
    )

    y = _draw_rule_title(pdf, text="COMMON LOCATORS", x=xs[1], y=top, width=COLUMN_W)
    y -= 1.5 * mm
    y = _draw_labeled_rows(
        pdf,
        rows=HELP_COMMON_LOCATORS,
        x=xs[1],
        y=y,
        width=COLUMN_W,
        label_width=25 * mm,
        body_style=PRIMER_BODY_TIGHT,
        gap_after=1.2 * mm,
    )
    y -= 1.0 * mm
    y = _draw_rule_title(pdf, text="INPUT RESOLUTION LEGEND", x=xs[1], y=y, width=COLUMN_W)
    y -= 1.5 * mm
    y = _draw_labeled_rows(
        pdf,
        rows=(
            ("REQUIRED", "The semantic role must be resolved before execution."),
            ("TUI", "Omission opens an interactive chooser in a TTY."),
            ("CURRENT", "Omission resolves that endpoint to the current Context."),
            ("ERROR", "Omission stops instead of inventing an input."),
            ("OPTIONAL", "A modifier changes otherwise complete default behavior."),
            ("CONDITIONAL", "Required only in a particular Form or mode."),
        ),
        x=xs[1],
        y=y,
        width=COLUMN_W,
        label_width=25 * mm,
        body_style=PRIMER_BODY_TIGHT,
        gap_after=1.2 * mm,
    )

    y = _draw_rule_title(pdf, text="COMMON KEYS", x=xs[2], y=top, width=COLUMN_W)
    y -= 1.5 * mm
    y = _draw_labeled_rows(
        pdf,
        rows=HELP_COMMON_KEYS,
        x=xs[2],
        y=y,
        width=COLUMN_W,
        label_width=28 * mm,
        body_style=PRIMER_BODY_TIGHT,
        gap_after=1.1 * mm,
    )
    y -= 1.0 * mm
    y = _draw_rule_title(pdf, text="OMISSION EXAMPLES", x=xs[2], y=y, width=COLUMN_W)
    y -= 1.5 * mm
    examples = (
        ("mem update", "TUI picks SOURCE and TARGET."),
        ("--from SOURCE", "TARGET becomes CURRENT."),
        ("--to TARGET", "SOURCE becomes CURRENT."),
        ("mem distill", "SOURCE and TARGET both become CURRENT."),
        ("mem merge", "TTY picks SOURCE, TARGET, and reach."),
        ("merge SOURCE", "TARGET becomes CURRENT."),
        ("copy UID", "TARGET becomes CURRENT."),
        ("mem copy", "Missing MEMORY causes ERROR."),
        ("move UID", "TARGET becomes CURRENT."),
        ("mem move", "Missing MEMORY causes ERROR."),
    )
    _draw_labeled_rows(
        pdf,
        rows=examples,
        x=xs[2],
        y=y,
        width=COLUMN_W,
        label_width=30 * mm,
        body_style=PRIMER_BODY_TIGHT,
        gap_after=1.0 * mm,
    )


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


def _ranked_flags(name: str, *, limit: int = 3) -> tuple[str, ...]:
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
        )[:limit]
    )


def _common_option_copy(name: str) -> str | None:
    flags = _ranked_flags(name)
    if not flags:
        return None
    # COMMAND_FORMS describe complete invocations, so a positional operand can
    # appear immediately after a boolean flag. Showing only the authored flag
    # token avoids falsely presenting that operand as the flag's value.
    return "  ".join(flags)


def _paragraph_height(paragraph: Paragraph, width: float = COLUMN_W) -> float:
    _w, height = paragraph.wrap(width, CONTENT_H)
    return height


def _draw_paragraph(
    pdf: canvas.Canvas,
    paragraph: Paragraph,
    *,
    x: float,
    y: float,
    width: float = COLUMN_W,
) -> float:
    _w, height = paragraph.wrap(width, CONTENT_H)
    paragraph.drawOn(pdf, x, y - height)
    return y - height


def _operation_block(operation) -> tuple[Paragraph, ...]:
    rows = [
        Paragraph(escape(_operation_title(operation.name, operation.maturity)), COMMAND),
        Paragraph(f"<b>DESCRIPTION</b>  {escape(operation.summary)}", DESCRIPTION),
        Paragraph(f"<b>USE WHEN</b>  {escape(operation.use_when)}", USE_WHEN),
    ]
    options = _common_option_copy(operation.name)
    if options:
        rows.append(
            Paragraph(
                f"<b>COMMON OPTIONS</b>  {escape(options)}",
                OPTION_LINE,
            )
        )
    route = INPUT_ROUTES.get(operation.name)
    if route:
        rows.append(
            Paragraph(
                f"<b>INPUT ROUTE</b>  {escape(route)}",
                ROUTE_LINE,
            )
        )
    return tuple(rows)


def _category_height(text: str) -> float:
    paragraph = Paragraph(escape(text), CATEGORY)
    _w, text_height = paragraph.wrap(COLUMN_W - 3 * mm, CONTENT_H)
    return text_height + 3 * mm


def _draw_category(pdf: canvas.Canvas, *, text: str, x: float, y: float) -> float:
    paragraph = Paragraph(escape(text), CATEGORY)
    _w, text_height = paragraph.wrap(COLUMN_W - 3 * mm, CONTENT_H)
    height = text_height + 3 * mm
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.7)
    pdf.rect(x, y - height, COLUMN_W, height, fill=0, stroke=1)
    pdf.restoreState()
    paragraph.drawOn(pdf, x + 1.5 * mm, y - 1.5 * mm - text_height)
    return y - height


def _draw_catalog_pages(pdf: canvas.Canvas) -> int:
    operations = {operation.name: operation for operation in list_operation_help()}
    page_number = 2
    column_index = 0
    x = MARGIN_X
    y = CONTENT_TOP - 1.5 * mm

    def begin_page() -> None:
        _page_chrome(
            pdf,
            page_number=page_number,
            heading="COMMAND CATALOG / VERBATIM COPY + COMMON OPTIONS",
            footer=(
                "COMMON OPTIONS are frequent authored spellings, not proof that the semantic input is optional."
            ),
        )

    begin_page()

    def next_column() -> None:
        nonlocal page_number, column_index, x, y
        column_index += 1
        if column_index >= COLUMN_COUNT:
            pdf.showPage()
            page_number += 1
            column_index = 0
            begin_page()
        x = MARGIN_X + column_index * (COLUMN_W + COLUMN_GAP)
        y = CONTENT_TOP - 1.5 * mm

    for title, names in HELP_CATEGORY_GROUPS:
        execution, _description = HELP_CATEGORY_DESCRIPTIONS[title]
        execution_copy = f" / {execution}" if execution else ""
        title_copy = title + execution_copy
        first_block = _operation_block(operations[names[0]])
        needed = (
            _category_height(title_copy)
            + sum(_paragraph_height(item) for item in first_block)
            + 1.7 * mm
        )
        if y - needed < CONTENT_BOTTOM:
            next_column()
        y = _draw_category(pdf, text=title_copy, x=x, y=y)
        y -= 0.8 * mm

        for name in names:
            block = _operation_block(operations[name])
            block_height = sum(_paragraph_height(item) for item in block) + 0.8 * mm
            if y - block_height < CONTENT_BOTTOM:
                next_column()
                y = _draw_category(
                    pdf,
                    text=title_copy + " / CONTINUED",
                    x=x,
                    y=y,
                )
                y -= 0.8 * mm
            for paragraph in block:
                y = _draw_paragraph(pdf, paragraph, x=x, y=y)
            y -= 0.8 * mm

    return page_number


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=(PAGE_W, PAGE_H))
    pdf.setTitle("MemCommit Help study reference - four page")
    pdf.setAuthor("MemCommit")
    pdf.setSubject(
        "Four-page user-study reference with exact Help copy, concepts, keys, and common options"
    )

    _draw_primer_page(pdf)
    pdf.showPage()
    final_page = _draw_catalog_pages(pdf)
    if final_page != 4:
        raise RuntimeError(f"Catalog layout produced {final_page} pages instead of 4.")
    pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    build()
