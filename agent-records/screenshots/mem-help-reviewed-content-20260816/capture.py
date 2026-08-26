"""Capture reviewed Help wording and typed details in a real color PTY."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-help-reviewed-content-20260816"

_BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


@dataclass(frozen=True)
class CaptureTarget:
    stem: str
    category_tabs: int
    row_downs: int
    expanded: bool
    expected: tuple[str, ...]


@dataclass(frozen=True)
class LanguageCaptureTarget:
    code: str
    right_moves: int
    expected: str


TARGETS = (
    CaptureTarget(
        "01-search",
        2,
        1,
        True,
        ("mem search", "without obvious keyword overlap"),
    ),
    CaptureTarget(
        "02-merge",
        3,
        5,
        True,
        ("mem merge", "MERGE BOUNDARY", "EXACT MATCH"),
    ),
    CaptureTarget(
        "03-dedup",
        3,
        6,
        True,
        ("mem dedup", "delete the rest on Apply"),
    ),
    CaptureTarget(
        "04-atomize",
        4,
        0,
        True,
        ("mem atomize", "ATOMIZE ROUTES", "--EVALUATE"),
    ),
    CaptureTarget(
        "05-distill",
        4,
        1,
        True,
        ("mem distill", "DISTILL OR ATOMIZE", "condition propositions"),
    ),
    CaptureTarget(
        "06-elaborate",
        4,
        2,
        True,
        ("mem elaborate", "abstract Goal, Rule, or condition"),
    ),
    CaptureTarget(
        "07-translate",
        4,
        3,
        True,
        ("mem translate", "MATERIALIZATION ROUTES", "--SAVE-AS"),
    ),
    CaptureTarget(
        "08-resolve",
        4,
        5,
        True,
        ("mem resolve", "bounded direct-Memory", "FLOW"),
    ),
    CaptureTarget(
        "09-meld",
        4,
        7,
        True,
        ("mem meld", "INCOMING -> EXISTING TARGET"),
    ),
    CaptureTarget(
        "10-sever",
        4,
        8,
        True,
        ("mem sever", "selecting, transforming, or excluding"),
    ),
    CaptureTarget(
        "11-audit",
        5,
        4,
        True,
        ("mem audit", "saved Audit report"),
    ),
    CaptureTarget(
        "12-impact",
        5,
        5,
        True,
        ("mem impact", "INVOCATION", "DIRECTIONAL UPDATE"),
    ),
    CaptureTarget(
        "13-review",
        5,
        6,
        True,
        ("mem review", "saved semantic artifact"),
    ),
    CaptureTarget(
        "14-fit",
        5,
        7,
        True,
        ("mem fit", "YES, MAY, OR NO", "multiple entrances"),
    ),
    CaptureTarget(
        "15-check-conformance",
        5,
        8,
        True,
        ("mem check-conformance", "FIT OR CONFORMANCE", "condition propositions"),
    ),
    CaptureTarget(
        "16-ground",
        6,
        0,
        True,
        ("mem ground", "Develop an abstract idea", "Ground workspace Contexts"),
    ),
    CaptureTarget(
        "17-log",
        7,
        0,
        True,
        ("mem log", "LOG ROUTES", "MEMORY LINEAGE"),
    ),
    CaptureTarget(
        "18-diff",
        7,
        1,
        True,
        ("mem diff", "Context checkpoint or active Update -> diff report"),
    ),
    CaptureTarget(
        "19-undo",
        7,
        5,
        True,
        ("mem undo", "most recent recorded command as one unit"),
    ),
    CaptureTarget(
        "20-revert",
        7,
        7,
        True,
        ("mem revert", "REVERT ROUTES", "EXACT CHECKPOINT"),
    ),
    CaptureTarget(
        "21-profile",
        8,
        0,
        True,
        ("mem profile", "PROFILE MANAGEMENT", "mem profile remove"),
    ),
    CaptureTarget(
        "22-provider",
        10,
        1,
        True,
        ("mem provider", "PROVIDER ACTIONS", "strict-schema"),
    ),
    CaptureTarget(
        "23-config",
        10,
        3,
        True,
        ("mem config", "(legacy)", "stored global configuration"),
    ),
    CaptureTarget(
        "24-eval",
        10,
        5,
        True,
        ("mem eval", "(legacy)", "EVALUATION SCOPE", "remains future work."),
    ),
)

LANGUAGE_TARGETS = (
    LanguageCaptureTarget("EN", 0, "basic record unit"),
    LanguageCaptureTarget("FR", 1, "unité d’enregistrement de base stockée"),
    LanguageCaptureTarget("ZH", 2, "存储在 Context 中"),
    LanguageCaptureTarget("KO", 3, "Context 안에 저장되며"),
    LanguageCaptureTarget("MN", 4, "Context дотор хадгалагдаж"),
)

_CATEGORY_ROW_COUNTS = {2: 4, 3: 7, 4: 9, 5: 9, 6: 1, 7: 8, 8: 2, 10: 6}
_LANGUAGE_OPERATION_PAGE_COUNT = 7


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _capture_target(executable: str, target: CaptureTarget, *, compact: bool) -> None:
    if compact:
        _BASE.COLUMNS = 100
        _BASE.ROWS = 30
        viewport = "compact"
    else:
        _BASE.COLUMNS = 180
        _BASE.ROWS = 52
        viewport = "wide"

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.55)
    child.send("\t" * target.category_tabs)
    _BASE._pump(child, seconds=0.15)
    # First visit the category's final row, then return to the requested row.
    # This settles the vertical viewport around the selected category even when
    # Tab initially brings its first row in at the bottom edge of the terminal.
    final_row = _CATEGORY_ROW_COUNTS[target.category_tabs] - 1
    child.send("\x1b[B" * final_row)
    _BASE._pump(child, seconds=0.15)
    child.send("\x1b[A" * (final_row - target.row_downs))
    _BASE._pump(child, seconds=0.15)
    if target.expanded:
        # Right opens the operation and focuses its first Form. Retaining that
        # focus keeps the newly revealed detail within the viewport.
        child.send("\x1b[C")
    _BASE._pump(child, seconds=0.5)

    plain = _BASE._snapshot(recorder, f"{target.stem}-{viewport}")
    normalized = " ".join(plain.split())
    for expected in target.expected:
        assert expected in normalized, (target.stem, viewport, expected, plain)

    raw = recorder.getvalue()
    expected_size = "30 100" if compact else "52 180"
    assert expected_size in raw
    assert _BASE.re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert _BASE.re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    _close(child)


def _capture_language(
    executable: str,
    target: LanguageCaptureTarget,
    *,
    compact: bool,
) -> None:
    if compact:
        _BASE.COLUMNS = 100
        _BASE.ROWS = 30
        viewport = "compact"
    else:
        _BASE.COLUMNS = 180
        _BASE.ROWS = 52
        viewport = "wide"

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.55)
    # Commands start focused. Two reverse Tab steps reach VIEW and then the
    # process-local LANGUAGE selector without changing any study data.
    child.send("\x1b[Z\x1b[Z")
    child.send("\x1b[C" * target.right_moves)
    _BASE._pump(child, seconds=0.5)

    stem = f"{25 + target.right_moves:02d}-language-{target.code.lower()}-{viewport}"
    plain = _BASE._snapshot(recorder, stem)
    normalized = " ".join(plain.split())
    assert "HELP LANGUAGE" in normalized
    assert f"✓ {target.code}" in normalized
    assert target.expected in normalized, (target.code, viewport, plain)

    raw = recorder.getvalue()
    expected_size = "30 100" if compact else "52 180"
    assert expected_size in raw
    assert _BASE.re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert _BASE.re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    _close(child)


def _write_language_operation_sheet(
    target: LanguageCaptureTarget,
    *,
    viewport: str,
    page_stems: list[str],
) -> None:
    """Compose full-resolution PTY pages without replacing their evidence."""

    pages = [Image.open(OUT / f"{stem}.png") for stem in page_stems]
    try:
        page_width, page_height = pages[0].size
        columns = 2
        rows = (len(pages) + columns - 1) // columns
        label_height = 30
        sheet = Image.new(
            "RGB",
            (page_width * columns, (page_height + label_height) * rows),
            "#101217",
        )
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.truetype(_BASE.FONT_PATH, 18, index=1)
        for index, page in enumerate(pages):
            column = index % columns
            row = index // columns
            x = column * page_width
            y = row * (page_height + label_height)
            draw.text(
                (x + 16, y + 4),
                (
                    f"{target.code} · OPERATIONS "
                    f"{index + 1}/{len(page_stems)} · {viewport.upper()}"
                ),
                font=font,
                fill="#cad3f5",
            )
            sheet.paste(page, (x, y + label_height))
        start = 30 + target.right_moves * _LANGUAGE_OPERATION_PAGE_COUNT
        end = start + _LANGUAGE_OPERATION_PAGE_COUNT - 1
        sheet.save(
            OUT
            / (
                f"{start:02d}-{end:02d}-language-{target.code.lower()}-"
                f"operations-all-{viewport}.png"
            )
        )
    finally:
        for page in pages:
            page.close()


def _capture_language_operation_pages(
    executable: str,
    target: LanguageCaptureTarget,
    *,
    compact: bool,
) -> None:
    if compact:
        _BASE.COLUMNS = 100
        _BASE.ROWS = 30
        viewport = "compact"
    else:
        _BASE.COLUMNS = 180
        _BASE.ROWS = 52
        viewport = "wide"

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.55)
    child.send("\x1b[Z\x1b[Z")
    child.send("\x1b[C" * target.right_moves)
    # Language -> View -> operation list, then freeze the first list position.
    child.send("\t\t\x1b[H")
    _BASE._pump(child, seconds=0.35)

    page_stems: list[str] = []
    for page in range(1, _LANGUAGE_OPERATION_PAGE_COUNT + 1):
        # Help advances ten semantic rows and clamps the final page to the last
        # operation. Adjacent 180x52 captures therefore overlap rather than
        # leaving an undocumented category boundary between them.
        child.send("\x1b[6~")
        _BASE._pump(child, seconds=0.35)
        number = (
            30
            + target.right_moves * _LANGUAGE_OPERATION_PAGE_COUNT
            + page
            - 1
        )
        stem = (
            f"{number:02d}-language-{target.code.lower()}-operations-"
            f"{page:02d}-{viewport}"
        )
        plain = _BASE._snapshot(recorder, stem)
        normalized = " ".join(plain.split())
        assert "HELP LANGUAGE" in normalized
        assert f"✓ {target.code}" in normalized
        assert "mem " in normalized
        if page == _LANGUAGE_OPERATION_PAGE_COUNT:
            assert "mem eval" in normalized
        page_stems.append(stem)

    raw = recorder.getvalue()
    expected_size = "30 100" if compact else "52 180"
    assert expected_size in raw
    assert _BASE.re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert _BASE.re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    _close(child)
    _write_language_operation_sheet(
        target,
        viewport=viewport,
        page_stems=page_stems,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--viewport", choices=("wide", "compact", "both"), default="both"
    )
    parser.add_argument(
        "--captures",
        choices=("operations", "languages", "language-pages", "both"),
        default="both",
    )
    parser.add_argument(
        "--start",
        default=TARGETS[0].stem,
        choices=tuple(target.stem for target in TARGETS),
    )
    args = parser.parse_args()
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)
    targets = TARGETS[
        next(i for i, target in enumerate(TARGETS) if target.stem == args.start) :
    ]
    viewports = {
        "wide": (False,),
        "compact": (True,),
        "both": (False, True),
    }[args.viewport]
    for compact in viewports:
        if args.captures in {"operations", "both"}:
            for target in targets:
                _capture_target(executable, target, compact=compact)
        if args.captures in {"languages", "both"}:
            for target in LANGUAGE_TARGETS:
                _capture_language(executable, target, compact=compact)
        if args.captures == "language-pages":
            for target in LANGUAGE_TARGETS:
                _capture_language_operation_pages(
                    executable,
                    target,
                    compact=compact,
                )


if __name__ == "__main__":
    main()
