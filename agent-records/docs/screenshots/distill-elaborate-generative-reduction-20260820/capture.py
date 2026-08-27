"""Capture live café Distill/Elaborate Impact results in real 180x52 PTYs."""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
LATIN_FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
KOREAN_FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("generative_reduction_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "src/memcommit/application/evaluation/fixtures/distill_elaborate.json").read_text(
            encoding="utf-8"
        )
    )


def _prepare_store(root: Path, operation: str):
    import memcommit.application.ops as ops
    import memcommit.store as store_module
    from memcommit.store import MemoryStore

    store_module.STORE_DIR = root
    store = MemoryStore()
    data = _fixture()
    cafe = next(
        family
        for family in data["reference_families"]
        if family["id"] == "cafe-order"
    )
    source_name = f"calibration/cafe/{'examples' if operation == 'distill' else 'rules'}"
    target_name = f"calibration/cafe/{'distilled-rules' if operation == 'distill' else 'generated-examples'}"
    values = cafe[
        "example_memories"
        if operation == "distill"
        else "rule_memories"
    ]
    assert isinstance(values, list) and all(isinstance(value, str) for value in values)
    source = ops.init(source_name)
    target = ops.init(target_name)
    for value in values:
        ops.add(source, value)
    if operation == "elaborate":
        # Existing destination content is a distinct run-specific ambient
        # example; the seven source Rules remain the complete Rule evidence.
        ops.add(target, cafe["example_memories"][0])
    store.create_context(source)
    store.create_context(target)
    store.set_current(target.name)
    return store, source, target


def _child(operation: str, root: Path) -> None:
    from memcommit.cli import app
    from memcommit.store import context_record_digest

    store, source, target = _prepare_store(root, operation)
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")
    argv = [
        "impact",
        operation,
        "--from",
        source.name,
        "--to",
        target.name,
    ]
    if operation == "distill":
        argv.append("--direct")
    else:
        argv.extend(("--as", "rules"))
    print("$ mem " + " ".join(argv), flush=True)
    source_digest = context_record_digest(store.load_direct(source.name))
    target_digest = context_record_digest(store.load_direct(target.name))
    app(args=argv, prog_name="mem", standalone_mode=False)
    print("\nREAD-ONLY LIVE PROVIDER VERIFICATION")
    print(f"  SOURCE DIRECT MEMORIES · {len(store.load_direct(source.name).order)}")
    print(f"  TARGET DIRECT MEMORIES · {len(store.load_direct(target.name).order)}")
    print(
        "  SOURCE DIGEST UNCHANGED · "
        f"{context_record_digest(store.load_direct(source.name)) == source_digest}"
    )
    print(
        "  TARGET DIGEST UNCHANGED · "
        f"{context_record_digest(store.load_direct(target.name)) == target_digest}"
    )
    print(f"  TARGET CHECKPOINTS · {len(store.list_checkpoints(target.name))}")
    print("  PROVIDER · CONFIGURED LIVE SEMANTIC PROVIDER", flush=True)


def _spawn(operation: str, root: Path):
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", operation, str(root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=300,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _hangul(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x1100 <= codepoint <= 0x11FF
        or 0x3130 <= codepoint <= 0x318F
        or 0xAC00 <= codepoint <= 0xD7AF
    )


def _render(raw: str, stem: str) -> None:
    """Replay one real PTY stream with a Hangul-capable font fallback."""

    screen = pyte.Screen(COLUMNS, ROWS)
    pyte.Stream(screen).feed(raw)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (OUT / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (OUT / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(LATIN_FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(LATIN_FONT_PATH, 16, index=1)
    korean = ImageFont.truetype(KOREAN_FONT_PATH, 16, index=0)
    korean_bold = ImageFont.truetype(KOREAN_FONT_PATH, 16, index=6)
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
            character = screen.buffer[row][column]
            foreground = _BASE._color(character.fg)
            background = _BASE._color(character.bg, background=True)
            if character.reverse:
                foreground, background = background, foreground
            x = margin + column * cell_width
            y = margin + row * cell_height
            if background != "#101217":
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=background,
                )
            if character.data and character.data != " ":
                if _hangul(character.data):
                    font = korean_bold if character.bold else korean
                else:
                    box_drawing = "\u2500" <= character.data <= "\u257f"
                    font = bold if character.bold and not box_drawing else regular
                draw.text((x, y), character.data, font=font, fill=foreground)
            if character.underscore:
                draw.line(
                    (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _snapshot(recorder, stem: str) -> None:
    _render(recorder.getvalue(), stem)


def _capture(
    operation: str,
    root: Path,
    number: int,
    *,
    inspect_first: bool,
) -> None:
    child, recorder = _spawn(operation, root)
    try:
        # Semantic colors insert ANSI bytes inside the title and status text.
        # The shared unstyled footer is the reliable live-screen boundary.
        child.expect("Enter inspect")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, f"{number:02d}-{operation}-live-result")

        verification_number = number + 1
        if inspect_first:
            # The session starts on the complete Viewer report. Move into Items,
            # select the first proposal after the REPORT row, then inspect it.
            child.send("\t")
            _BASE._settle(child, seconds=0.2)
            child.send(_BASE.DOWN)
            _BASE._settle(child, seconds=0.2)
            child.send("\r")
            _BASE._settle(child, seconds=0.8)
            _snapshot(
                recorder,
                f"{number + 1:02d}-{operation}-first-proposal-detail",
            )
            verification_number += 1

        child.send("q")
        child.expect("READ-ONLY LIVE PROVIDER VERIFICATION")
        child.expect("TARGET CHECKPOINTS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(
            recorder,
            f"{verification_number:02d}-{operation}-read-only-verification",
        )
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-cafe-live-impact-") as directory:
        root = Path(directory)
        _capture("distill", root / "distill", 1, inspect_first=False)
        _capture("elaborate", root / "elaborate", 3, inspect_first=True)
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY streams did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
