"""Build a large-type US Letter user-study Help reference."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
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
from reportlab.lib.pagesizes import landscape, letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
from reportlab.platypus import Flowable, Paragraph, Table, TableStyle  # noqa: E402

from memcommit.help_application import list_operation_help  # noqa: E402
from memcommit.cli import app as CLI_APP  # noqa: E402
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


OUTPUT = ROOT / "output/pdf/mem-help-study-reference-letter-color-index.pdf"
PAGE_W, PAGE_H = landscape(letter)
MARGIN_X = 0.48 * inch
MARGIN_BOTTOM = 0.42 * inch
HEADER_H = 0.66 * inch
FOOTER_H = 0.28 * inch
CONTENT_TOP = PAGE_H - HEADER_H
CONTENT_BOTTOM = MARGIN_BOTTOM + FOOTER_H
CONTENT_H = CONTENT_TOP - CONTENT_BOTTOM

# Leave the physical top-left corner clear for a diagonal staple without
# spending vertical space that the large-type catalog needs for its body.
HEADER_STAPLE_INSET_X = 0.25 * inch
HEADER_TITLE_Y_OFFSET = 0.43 * inch
HEADER_RULE_Y_OFFSET = 0.56 * inch

INK = colors.black
SUBTLE = colors.HexColor("#333333")

COLUMN_COUNT = 2
COLUMN_GAP = 0.30 * inch
COLUMN_W = (
    PAGE_W - 2 * MARGIN_X - (COLUMN_COUNT - 1) * COLUMN_GAP
) / COLUMN_COUNT

SECTION = ParagraphStyle(
    "section",
    fontName="Helvetica-Bold",
    fontSize=13,
    leading=15,
    textColor=INK,
)
LABEL = ParagraphStyle(
    "label",
    fontName="Courier-Bold",
    fontSize=11,
    leading=13.2,
    textColor=INK,
)
BODY = ParagraphStyle(
    "body",
    fontName="Helvetica",
    fontSize=11,
    leading=13.2,
    textColor=INK,
)
BODY_SUBTLE = ParagraphStyle(
    "body-subtle",
    parent=BODY,
    textColor=SUBTLE,
)
CATEGORY = ParagraphStyle(
    "category",
    fontName="Helvetica-Bold",
    fontSize=13,
    leading=15,
    textColor=INK,
)
COMMAND = ParagraphStyle(
    "command",
    fontName="Courier-Bold",
    fontSize=15,
    leading=17,
    textColor=INK,
)
OPTION = ParagraphStyle(
    "option",
    fontName="Courier",
    fontSize=11,
    leading=13.2,
    leftIndent=0.10 * inch,
    textColor=SUBTLE,
)
ROUTE = ParagraphStyle(
    "route",
    fontName="Helvetica",
    fontSize=11,
    leading=13.2,
    leftIndent=0.10 * inch,
    textColor=SUBTLE,
)
INDEX_COMMANDS = ParagraphStyle(
    "index-commands",
    fontName="Courier",
    fontSize=11,
    leading=13.2,
    textColor=INK,
)

CATEGORY_PALETTE = (
    "#3F6FA9",
    "#16858C",
    "#A35D2D",
    "#4F7E4B",
    "#76599B",
    "#A64F68",
    "#8A6A32",
    "#556C82",
    "#34796F",
    "#8B527A",
    "#666666",
)
CATEGORY_COLORS = {
    title: colors.HexColor(color)
    for (title, _names), color in zip(HELP_CATEGORY_GROUPS, CATEGORY_PALETTE)
}

COMMAND_STRIPE_W = 0.07 * inch

# The printed handout is scoped to operations participants may use in the
# study. Ground has its own mediated workflow, Provider is setup chrome, and
# legacy operations are intentionally left discoverable only in live Help.
STUDY_EXCLUDED_OPERATION_NAMES = frozenset(
    {
        "ground",
        "provider",
        "import",
        "translate",
        "shell-init",
        "init-study",
    }
)


@dataclass(frozen=True)
class OperationBlock:
    heading: Paragraph
    body: tuple[Flowable, ...]
    color: colors.Color


FLAG_PATTERN = re.compile(r"(?<!\w)(--[a-z][a-z0-9-]*|-[a-zA-Z])(?!\w)")

# Keep only authored epilogs whose omission changes a participant-visible
# behavior. Routine positional spellings are already covered by Common Inputs
# and the omission primer, leaving room for higher-value distinctions.
STUDY_NOTE_OPERATION_NAMES = frozenset({"show", "sever"})

COMMAND_NOTES = {
    command.name: command.epilog
    for command in CLI_APP.registered_commands
    if command.name in STUDY_NOTE_OPERATION_NAMES and command.epilog
}

# Operation choice is a study task in its own right. Each comparison is keyed
# by a nearby command, then grouped with the other comparisons at the bottom of
# that command's catalog page.
LOCAL_COMPARISONS = {
    "embed": (
        "REFERENCE",
        "Frozen snapshot; later Source changes do not follow.",
        "CREATE, COPY & CONNECT",
        "EMBED",
        "Live connection; the Target follows later Source changes.",
        "CREATE, COPY & CONNECT",
    ),
    "search": (
        "FIND",
        "Exact text or regular-expression matching.",
        "SEARCH & EXPLAIN",
        "SEARCH",
        "Semantic ranking by meaning and context.",
        "SEARCH & EXPLAIN",
    ),
    "chunk": (
        "CHUNK",
        "Mechanical split at existing boundaries.",
        "DETERMINISTIC CONTENT CHANGES",
        "ATOMIZE",
        "Semantic separation into independently reviewable propositions.",
        "SEMANTIC TRANSFORMATIONS",
    ),
    "merge": (
        "MERGE",
        "Deterministic structural union; no synthesis.",
        "DETERMINISTIC CONTENT CHANGES",
        "MELD",
        "Semantic reconciliation of overlap or conflict; may synthesize.",
        "SEMANTIC TRANSFORMATIONS",
    ),
    "dedup": (
        "DEDUP",
        "Remove exact matches within the same role.",
        "DETERMINISTIC CONTENT CHANGES",
        "DEDUN",
        "Remove exact matches plus semantic redundancy.",
        "SEMANTIC TRANSFORMATIONS",
    ),
    "elaborate": (
        "DISTILL",
        "Concrete Cases or Examples to a higher-level Rule.",
        "SEMANTIC TRANSFORMATIONS",
        "ELABORATE",
        "Abstract Rule or Goal to concrete candidates.",
        "SEMANTIC TRANSFORMATIONS",
    ),
    "meld": (
        "UPDATE",
        "Revise an existing Target from verified Source changes, then Apply the reviewed plan atomically.",
        "SEMANTIC TRANSFORMATIONS",
        "MELD",
        "Closer to a semantic merge: reconcile overlap and conflicts into a Baseline or separate Result, with synthesis when needed.",
        "SEMANTIC TRANSFORMATIONS",
    ),
    "audit": (
        "AUDIT",
        "Run duplicate/redundancy, ambiguity, conflict, and optional conformance together.",
        "CHECK, COMPARE & REVIEW",
        "INDIVIDUAL CHECKS",
        "Use one find-* or check-conformance operation when only one issue class matters.",
        "CHECK, COMPARE & REVIEW",
    ),
    "check-conformance": (
        "FIT",
        "Ask whether one set is jointly compatible.",
        "CHECK, COMPARE & REVIEW",
        "CHECK-CONFORMANCE",
        "Ask whether subjects follow stated Rules. Neither operation establishes external truth.",
        "CHECK, COMPARE & REVIEW",
    ),
    "rationale": (
        "TRACE",
        "Follow recorded lineage step by step.",
        "HISTORY & RECOVERY",
        "RATIONALE",
        "Read a contextual origin and lifecycle summary in one paragraph.",
        "HISTORY & RECOVERY",
    ),
}

# Offsets are relative to the first catalog page. The builder verifies that
# every anchor still lands on its assigned page so Help-copy changes cannot
# silently separate a bottom comparison from the commands it explains.
CATALOG_PAGE_COMPARISON_ANCHORS = {
    1: ("embed",),
    2: ("search",),
    3: ("merge", "dedup", "chunk"),
    4: ("elaborate",),
    5: ("meld",),
    6: ("audit", "check-conformance"),
    7: ("rationale",),
}

# These compact operands keep the handout useful without reproducing every
# authored Form. They name the value a participant supplies; brackets mark an
# input that can be omitted because the TTY or current Context can resolve it.
COMMON_ARGUMENTS = {
    "list": ("[CONTEXT]",),
    "show": ("[TARGET]",),
    "switch": ("[CONTEXT]",),
    "checkout": ("[CONTEXT]",),
    "rename": ("OLD_CONTEXT", "NEW_CONTEXT"),
    "init": ("[CONTEXT]",),
    "add": ('"MEMORY"',),
    "copy": ("UID...",),
    "branch": ("NEW_CONTEXT",),
    "reference": ("SOURCE",),
    "embed": ("SOURCE",),
    "find": ('"TEXT"',),
    "search": ('"QUERY"',),
    "query": ('"QUESTION"',),
    "summarize": ("[CONTEXT]",),
    "edit": ("UID", '"NEW_CONTENT"'),
    "move": ("UID...",),
    "replace": ('"TEXT"', '"REPLACEMENT"'),
    "chunk": ("[TARGET]",),
    "delete": ("ITEM",),
    "clear": ("[CONTEXT]",),
    "merge": ("SOURCE", "[TARGET]"),
    "dedup": ("[CONTEXT]",),
    "atomize": ("[TARGET]",),
    "forget": ('"INSTRUCTION"',),
    "resolve": ("[CONTEXT]", "[UID]"),
    "dedun": ("[CONTEXT]",),
    "update": ("SOURCE", "TARGET"),
    "meld": ("LEFT", "RIGHT", "[RESULT]"),
    "sever": ("SOURCE", "CRITERIA", "[RESULT]"),
    "compare": ("PEER", "[PEER]"),
    "find-duplicates": ("[CONTEXT]",),
    "find-redundancies": ("[CONTEXT]",),
    "find-ambiguities": ("[CONTEXT]",),
    "find-conflicts": ("[CONTEXT]",),
    "audit": ("[CONTEXT]",),
    "impact": ("OPERATION",),
    "fit": ('"PROPOSITION"...',),
    "check-conformance": ("TARGET",),
    "log": ('"QUERY"',),
    "diff": ("[CONTEXT]",),
    "trace": ("MEMORY",),
    "rationale": ("MEMORY",),
    "checkpoint": ('"MESSAGE"',),
    "revert": ("[CHECKPOINT]",),
    "profile": ("[PROFILE]",),
    "share": ("[SOURCE]",),
    "lock": ("[TARGET]",),
    "unlock": ("[TARGET]",),
    "shell-init": ("[SHELL]",),
    "init-study": ("[PROFILE]",),
}

# Endpoint and criterion flags carry more task meaning than flags that merely
# recur across many authored Forms, so they lead the compact input line.
PREFERRED_FLAGS = {
    "add": ("--context", "--memory", "--input"),
    "copy": ("--from", "--to", "--into", "--memory"),
    "branch": ("--from", "-r"),
    "reference": ("--from", "--to", "--into", "--recursive"),
    "embed": ("--from", "--to", "--into", "--before"),
    "find": ("--context", "-r", "-a", "--regex"),
    "search": ("--context", "-r", "-a", "--descendants"),
    "query": ("--context", "-r", "-a", "--language"),
    "edit": ("--context", "--input"),
    "move": ("--from", "--to", "--into", "--memory"),
    "replace": ("--context", "--regex", "--delete-match"),
    "merge": ("--from", "--to", "--into", "--recursive"),
    "distill": ("--from", "--to", "--goal", "-r"),
    "elaborate": ("--from", "--to", "--rule", "--goal"),
    "forget": ("--context",),
    "update": ("--from", "--to", "-r", "--sessions"),
    "meld": ("--from", "--to", "--into", "--memory"),
    "sever": ("--from", "--against", "--to", "--criteria"),
    "impact": ("--from", "--to", "--context", "--sessions"),
    "check-conformance": ("--against", "--ground", "--rule"),
}

LEGEND_ROWS = (
    ("REQUIRED", "The semantic role must be resolved before execution."),
    ("TUI", "Omission opens an interactive chooser in a TTY."),
    ("CURRENT", "Omission resolves that endpoint to the current Context."),
    ("ERROR", "Omission stops instead of inventing an input."),
    ("OPTIONAL", "A modifier changes otherwise complete default behavior."),
    ("CONDITIONAL", "Required only in a particular Form or mode."),
)

OMISSION_ROWS = (
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


def _page_chrome(
    pdf: canvas.Canvas,
    *,
    page_number: int,
    total_pages: int,
    heading: str,
) -> None:
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.7)
    pdf.line(
        MARGIN_X,
        PAGE_H - HEADER_RULE_Y_OFFSET,
        PAGE_W - MARGIN_X,
        PAGE_H - HEADER_RULE_Y_OFFSET,
    )
    pdf.line(MARGIN_X, MARGIN_BOTTOM + 0.19 * inch, PAGE_W - MARGIN_X, MARGIN_BOTTOM + 0.19 * inch)
    pdf.setFillColor(INK)
    pdf.setFont("Courier-Bold", 17)
    pdf.drawString(
        MARGIN_X + HEADER_STAPLE_INSET_X,
        PAGE_H - HEADER_TITLE_Y_OFFSET,
        "mem help",
    )
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        MARGIN_X + HEADER_STAPLE_INSET_X + 1.43 * inch,
        PAGE_H - (HEADER_TITLE_Y_OFFSET - 0.01 * inch),
        heading,
    )
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(
        PAGE_W - MARGIN_X,
        MARGIN_BOTTOM,
        f"PAGE {page_number} / {total_pages}",
    )
    pdf.restoreState()


def _paragraph_height(flowable: Flowable, width: float = COLUMN_W) -> float:
    return flowable.wrap(width, CONTENT_H)[1]


def _draw_paragraph(
    pdf: canvas.Canvas,
    paragraph: Flowable,
    *,
    x: float,
    y: float,
    width: float = COLUMN_W,
) -> float:
    height = _paragraph_height(paragraph, width)
    paragraph.drawOn(pdf, x, y - height)
    return y - height


def _draw_section(
    pdf: canvas.Canvas,
    *,
    text: str,
    x: float,
    y: float,
    color: colors.Color | None = None,
) -> float:
    style = SECTION
    if color is not None:
        style = ParagraphStyle(
            f"section-{text}",
            parent=SECTION,
            textColor=colors.white,
        )
    paragraph = Paragraph(escape(text), style)
    text_height = _paragraph_height(paragraph, COLUMN_W - 0.20 * inch)
    height = text_height + 0.16 * inch
    pdf.saveState()
    pdf.setStrokeColor(color or INK)
    if color is not None:
        pdf.setFillColor(color)
    pdf.setLineWidth(0.7)
    pdf.rect(x, y - height, COLUMN_W, height, fill=int(color is not None), stroke=1)
    pdf.restoreState()
    paragraph.drawOn(
        pdf,
        x + 0.10 * inch,
        y - 0.08 * inch - text_height,
    )
    return y - height


def _draw_rows(
    pdf: canvas.Canvas,
    *,
    rows: tuple[tuple[str, str], ...],
    x: float,
    y: float,
    label_width: float,
    gap: float = 0.08 * inch,
) -> float:
    for label, body in rows:
        label_paragraph = Paragraph(escape(label), LABEL)
        body_paragraph = Paragraph(escape(body), BODY)
        label_height = _paragraph_height(label_paragraph, label_width)
        body_height = _paragraph_height(body_paragraph, COLUMN_W - label_width)
        height = max(label_height, body_height)
        label_paragraph.drawOn(pdf, x, y - label_height)
        body_paragraph.drawOn(pdf, x + label_width, y - body_height)
        y -= height + gap
    return y


def _page_range(pages: set[int] | None) -> str:
    if not pages:
        return "P. --"
    ordered = sorted(pages)
    if len(ordered) == 1:
        return f"P. {ordered[0]}"
    return f"P. {ordered[0]}-{ordered[-1]}"


def _study_category_groups() -> tuple[tuple[str, tuple[str, ...]], ...]:
    operations = {operation.name: operation for operation in list_operation_help()}
    groups: list[tuple[str, tuple[str, ...]]] = []
    for title, names in HELP_CATEGORY_GROUPS:
        included = tuple(
            name
            for name in names
            if name not in STUDY_EXCLUDED_OPERATION_NAMES
            and (operations[name].maturity or "").lower() != "legacy"
            and (COMMAND_ANNOTATIONS.get(name) or "").lower() != "legacy"
        )
        if included:
            groups.append((title, included))
    return tuple(groups)


def _draw_help_guide(pdf: canvas.Canvas, *, x: float, bottom: float) -> None:
    width = COLUMN_W
    padding = 0.12 * inch
    title = Paragraph("USING HELP", SECTION)
    bare_command = Paragraph("mem help", COMMAND)
    bare_description = Paragraph(
        "Enter the interactive command browser and open syntax help.",
        BODY_SUBTLE,
    )
    request_command = Paragraph('mem help "WHAT YOU WANT TO DO"', COMMAND)
    request_description = Paragraph(
        "Describe the action in your own words to see three candidate operations.",
        BODY_SUBTLE,
    )
    paragraphs = (
        title,
        bare_command,
        bare_description,
        request_command,
        request_description,
    )
    gaps = (0.08, 0.02, 0.12, 0.02)
    inner_width = width - 2 * padding
    heights = [_paragraph_height(paragraph, inner_width) for paragraph in paragraphs]
    height = sum(heights) + sum(gaps) * inch + 2 * padding
    top = bottom + height

    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.7)
    pdf.rect(x, bottom, width, height, fill=0, stroke=1)
    pdf.restoreState()

    y = top - padding
    for index, (paragraph, paragraph_height) in enumerate(zip(paragraphs, heights)):
        paragraph.drawOn(pdf, x + padding, y - paragraph_height)
        y -= paragraph_height
        if index < len(gaps):
            y -= gaps[index] * inch


def _draw_quick_index(
    pdf: canvas.Canvas,
    *,
    total_pages: int,
    category_pages: dict[str, set[int]] | None,
) -> None:
    _page_chrome(
        pdf,
        page_number=1,
        total_pages=total_pages,
        heading="CATEGORY INDEX / USING HELP",
    )
    index_top = CONTENT_TOP - 0.05 * inch
    study_groups = _study_category_groups()
    category_groups = (study_groups[:6], study_groups[6:])
    for column_index, groups in enumerate(category_groups):
        x = MARGIN_X + column_index * (COLUMN_W + COLUMN_GAP)
        y = index_top
        for title, names in groups:
            execution, _description = HELP_CATEGORY_DESCRIPTIONS[title]
            page_copy = _page_range(None if category_pages is None else category_pages.get(title))
            heading = title + (f" / {execution}" if execution else "") + f"    {page_copy}"
            y = _draw_section(
                pdf,
                text=heading,
                x=x,
                y=y,
                color=CATEGORY_COLORS[title],
            )
            y -= 0.06 * inch
            command_copy = " / ".join(f"mem {name}" for name in names)
            paragraph = Paragraph(escape(command_copy), INDEX_COMMANDS)
            y = _draw_paragraph(pdf, paragraph, x=x, y=y)
            y -= 0.11 * inch
        if column_index == 1:
            guide_bottom = CONTENT_BOTTOM + 0.04 * inch
            _draw_help_guide(pdf, x=x, bottom=guide_bottom)
        if y < CONTENT_BOTTOM:
            raise RuntimeError(f"Quick index overflowed column {column_index + 1}.")


def _draw_primer_page(
    pdf: canvas.Canvas,
    *,
    page_number: int,
    total_pages: int,
    left: tuple[str, tuple[tuple[str, str], ...], float],
    right: tuple[str, tuple[tuple[str, str], ...], float],
) -> None:
    _page_chrome(
        pdf,
        page_number=page_number,
        total_pages=total_pages,
        heading="PRIMER / LOCATORS / INPUT RESOLUTION / KEYS",
    )
    for column_index, (title, rows, label_width) in enumerate((left, right)):
        x = MARGIN_X + column_index * (COLUMN_W + COLUMN_GAP)
        y = _draw_section(pdf, text=title, x=x, y=CONTENT_TOP - 0.05 * inch)
        y -= 0.12 * inch
        _draw_rows(
            pdf,
            rows=rows,
            x=x,
            y=y,
            label_width=label_width,
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


def _ranked_flags(name: str, *, limit: int = 4) -> tuple[str, ...]:
    counts: Counter[str] = Counter()
    authored_order: list[str] = []
    for form in COMMAND_FORMS.get(name, ()):
        for flag in FLAG_PATTERN.findall(form):
            counts[flag] += 1
            if flag not in authored_order:
                authored_order.append(flag)
    preferred = PREFERRED_FLAGS.get(name, ())
    return tuple(
        sorted(
            authored_order,
            key=lambda flag: (
                preferred.index(flag) if flag in preferred else len(preferred),
                -counts[flag],
                authored_order.index(flag),
            ),
        )[:limit]
    )


def _common_inputs(name: str) -> tuple[str, ...]:
    arguments = COMMON_ARGUMENTS.get(name, ())
    max_tokens = 6 if name in {"meld", "sever", "update"} else 5 if arguments else 4
    flags = _ranked_flags(name, limit=max(0, max_tokens - len(arguments)))
    return arguments + flags


def _page_comparisons_table(anchor_names: tuple[str, ...]) -> Table:
    full_width = PAGE_W - 2 * MARGIN_X
    cell_style = ParagraphStyle(
        "page-comparison-cell",
        parent=BODY,
        fontSize=11,
        leading=13.2,
        spaceAfter=0,
    )
    heading_style = ParagraphStyle(
        "page-comparison-heading",
        parent=BODY,
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=11,
        textColor=colors.HexColor("#666666"),
        spaceAfter=0,
    )
    rows: list[list[Paragraph | str]] = [
        [Paragraph("DISTINCTIONS", heading_style), ""]
    ]
    for anchor_name in anchor_names:
        (
            left_name,
            left_text,
            left_category,
            right_name,
            right_text,
            right_category,
        ) = LOCAL_COMPARISONS[anchor_name]
        left_color = CATEGORY_COLORS[left_category]
        right_color = CATEGORY_COLORS[right_category]
        left = Paragraph(
            f'<font name="Courier-Bold" color="{left_color.hexval()}">'
            f"{escape(left_name)}</font>&nbsp;&nbsp;{escape(left_text)}",
            cell_style,
        )
        right = Paragraph(
            f'<font name="Courier-Bold" color="{right_color.hexval()}">'
            f"{escape(right_name)}</font>&nbsp;&nbsp;{escape(right_text)}",
            cell_style,
        )
        rows.append([left, right])
    table = Table(
        rows,
        colWidths=(full_width / 2, full_width / 2),
        hAlign="LEFT",
    )
    styles = [
        ("SPAN", (0, 0), (1, 0)),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#8A8A8A")),
        ("LINEBEFORE", (1, 1), (1, -1), 0.55, colors.HexColor("#8A8A8A")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]
    for row_index in range(2, len(rows)):
        styles.append(
            ("LINEABOVE", (0, row_index), (-1, row_index), 0.4, colors.HexColor("#B0B0B0"))
        )
    table.setStyle(TableStyle(styles))
    return table


def _operation_block(operation, *, color: colors.Color) -> OperationBlock:
    command_style = ParagraphStyle(
        f"command-{operation.name}",
        parent=COMMAND,
        textColor=color,
        leftIndent=0.05 * inch,
    )
    meta_style = ParagraphStyle(
        f"meta-{operation.name}",
        parent=OPTION,
        leftIndent=0.05 * inch,
        textColor=INK,
    )
    note_style = ParagraphStyle(
        f"note-{operation.name}",
        parent=ROUTE,
        leftIndent=0.05 * inch,
    )
    label = (
        '<font name="Helvetica-Bold" size="10" color="#666666">{}</font>'
    )
    rows = [
        Paragraph(
            f"{label.format('DESCRIPTION')}&nbsp;&nbsp;{escape(operation.summary)}",
            BODY,
        ),
        Paragraph(
            f"{label.format('USE WHEN')}&nbsp;&nbsp;{escape(operation.use_when)}",
            BODY_SUBTLE,
        ),
    ]
    common_inputs = _common_inputs(operation.name)
    if common_inputs:
        rows.append(
            Paragraph(
                f"{label.format('COMMON INPUTS')}&nbsp;&nbsp;"
                f"{escape('  '.join(common_inputs))}",
                meta_style,
            )
        )
    note = COMMAND_NOTES.get(operation.name)
    if note:
        rows.append(
            Paragraph(
                f"<b>NOTE</b>  {escape(note)}",
                note_style,
            )
        )
    return OperationBlock(
        heading=Paragraph(
            escape(_operation_title(operation.name, operation.maturity)),
            command_style,
        ),
        body=tuple(rows),
        color=color,
    )


def _operation_block_height(block: OperationBlock) -> float:
    heading_height = _paragraph_height(block.heading, COLUMN_W - COMMAND_STRIPE_W)
    return heading_height + sum(_paragraph_height(item) for item in block.body)


def _draw_operation_block(
    pdf: canvas.Canvas,
    block: OperationBlock,
    *,
    x: float,
    y: float,
) -> float:
    heading_width = COLUMN_W - COMMAND_STRIPE_W
    heading_height = _paragraph_height(block.heading, heading_width)
    pdf.saveState()
    pdf.setFillColor(block.color)
    pdf.rect(
        x,
        y - heading_height,
        COMMAND_STRIPE_W,
        heading_height,
        fill=1,
        stroke=0,
    )
    pdf.restoreState()
    block.heading.drawOn(pdf, x + COMMAND_STRIPE_W, y - heading_height)
    y -= heading_height + 0.04 * inch
    for paragraph in block.body:
        y = _draw_paragraph(pdf, paragraph, x=x, y=y)
    return y


def _draw_catalog(
    pdf: canvas.Canvas,
    *,
    first_page: int,
    total_pages: int,
) -> tuple[int, dict[str, set[int]]]:
    operations = {operation.name: operation for operation in list_operation_help()}
    category_pages: dict[str, set[int]] = {}
    operation_pages: dict[str, int] = {}
    page_number = first_page
    column_index = 0
    x = MARGIN_X
    y = CONTENT_TOP - 0.05 * inch
    full_width = PAGE_W - 2 * MARGIN_X
    comparison_tables = {
        first_page + offset: _page_comparisons_table(anchor_names)
        for offset, anchor_names in CATALOG_PAGE_COMPARISON_ANCHORS.items()
    }
    comparison_heights = {
        page: _paragraph_height(table, full_width)
        for page, table in comparison_tables.items()
    }

    def page_content_bottom() -> float:
        height = comparison_heights.get(page_number)
        if height is None:
            return CONTENT_BOTTOM
        return CONTENT_BOTTOM + height + 0.10 * inch

    def finish_page() -> None:
        table = comparison_tables.get(page_number)
        if table is None:
            return
        table.wrap(full_width, CONTENT_H)
        table.drawOn(pdf, MARGIN_X, CONTENT_BOTTOM)

    def begin_page() -> None:
        _page_chrome(
            pdf,
            page_number=page_number,
            total_pages=total_pages,
            heading="COMMAND CATALOG / VERBATIM COPY + COMMON INPUTS",
        )

    begin_page()

    def next_column() -> None:
        nonlocal page_number, column_index, x, y
        column_index += 1
        if column_index >= COLUMN_COUNT:
            finish_page()
            pdf.showPage()
            page_number += 1
            column_index = 0
            begin_page()
        x = MARGIN_X + column_index * (COLUMN_W + COLUMN_GAP)
        y = CONTENT_TOP - 0.05 * inch

    def draw_category(text: str, *, color: colors.Color) -> None:
        nonlocal y
        y = _draw_section(pdf, text=text, x=x, y=y, color=color)
        y -= 0.08 * inch

    for title, names in _study_category_groups():
        execution, _description = HELP_CATEGORY_DESCRIPTIONS[title]
        title_copy = title + (f" / {execution}" if execution else "")
        category_color = CATEGORY_COLORS[title]
        if title == "SEARCH & EXPLAIN" and page_number == first_page + 1:
            next_column()
        first_block = _operation_block(operations[names[0]], color=category_color)
        needed = (
            _paragraph_height(Paragraph(escape(title_copy), CATEGORY), COLUMN_W - 0.20 * inch)
            + 0.24 * inch
            + _operation_block_height(first_block)
            + 0.18 * inch
        )
        if y - needed < page_content_bottom():
            next_column()
        category_pages.setdefault(title, set()).add(page_number)
        draw_category(title_copy, color=category_color)

        for name in names:
            block = _operation_block(operations[name], color=category_color)
            block_height = _operation_block_height(block) + 0.18 * inch
            if y - block_height < page_content_bottom():
                next_column()
                category_pages[title].add(page_number)
                draw_category(title_copy + " / CONTINUED", color=category_color)
            operation_pages[name] = page_number
            y = _draw_operation_block(pdf, block, x=x, y=y)
            y -= 0.18 * inch

    finish_page()
    anchor_mismatches = []
    for offset, anchor_names in CATALOG_PAGE_COMPARISON_ANCHORS.items():
        expected_page = first_page + offset
        for anchor_name in anchor_names:
            actual_page = operation_pages.get(anchor_name)
            if actual_page != expected_page:
                anchor_mismatches.append(
                    f"{anchor_name!r}: page {actual_page}, expected {expected_page}"
                )
    if anchor_mismatches:
        raise RuntimeError(
            "Comparison anchors moved: " + "; ".join(anchor_mismatches)
        )
    return page_number, category_pages


def _render(
    path: Path,
    total_pages: int,
    *,
    index_category_pages: dict[str, set[int]] | None = None,
) -> tuple[int, dict[str, set[int]]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
    pdf.setTitle("MemCommit Help study reference - Letter color index")
    pdf.setAuthor("MemCommit")
    pdf.setSubject(
        "Letter user-study reference with large type, category colors, a quick index, and exact Help copy"
    )

    _draw_quick_index(
        pdf,
        total_pages=total_pages,
        category_pages=index_category_pages,
    )
    pdf.showPage()
    _draw_primer_page(
        pdf,
        page_number=2,
        total_pages=total_pages,
        left=("CORE CONCEPTS", HELP_CORE_CONCEPTS, 1.05 * inch),
        right=("COMMON LOCATORS", HELP_COMMON_LOCATORS, 1.25 * inch),
    )
    pdf.showPage()
    _draw_primer_page(
        pdf,
        page_number=3,
        total_pages=total_pages,
        left=("COMMON KEYS", HELP_COMMON_KEYS, 1.30 * inch),
        right=("INPUT RESOLUTION + OMISSION", LEGEND_ROWS + OMISSION_ROWS, 1.35 * inch),
    )
    pdf.showPage()
    final_page, category_pages = _draw_catalog(
        pdf,
        first_page=4,
        total_pages=total_pages,
    )
    pdf.showPage()
    pdf.save()
    return final_page, category_pages


def build() -> int:
    preflight = ROOT / "tmp/pdfs/mem-help-letter-large-preflight.pdf"
    total_pages, category_pages = _render(preflight, total_pages=99)
    final_pages, final_category_pages = _render(
        OUTPUT,
        total_pages=total_pages,
        index_category_pages=category_pages,
    )
    if final_pages != total_pages:
        raise RuntimeError(
            f"Layout changed between preflight ({total_pages}) and final ({final_pages})."
        )
    if final_category_pages != category_pages:
        raise RuntimeError("Category page ranges changed between preflight and final.")
    return total_pages


if __name__ == "__main__":
    print(build())
