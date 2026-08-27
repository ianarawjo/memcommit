"""Capture exact-prewarm or projected Study Compare in a real color PTY."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont
import pexpect
import pyte


ROOT = Path(__file__).resolve().parents[3]
EXACT_OUT = Path(__file__).resolve().parent
PROJECTION_OUT = EXACT_OUT.parent / "study-compare-projection-20260810"
COLS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
REFERENCE = "task-2/advisor1"
COMPARED = "task-2/advisor2"
PROJECTED_REFERENCE = "task-2/advisor1/style"
PROJECTED_COMPARED = "task-2/advisor2/style"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


class _Recorder:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, value: bytes) -> None:
        self.data.extend(value)

    def flush(self) -> None:
        pass


def _run_child(*, projection: bool) -> None:
    from memcommit.adapters.console.entrypoint import app

    argv = [
        "compare",
        "--from",
        PROJECTED_REFERENCE if projection else REFERENCE,
        "--to",
        PROJECTED_COMPARED if projection else COMPARED,
    ]
    if not projection:
        argv.extend(["--reference-descendants", "--compared-descendants"])
    print("$ mem " + " ".join(argv), flush=True)
    app(args=argv, prog_name="mem", standalone_mode=False)
    print("\nCAPTURE GATE · PRESS V FOR READ-ONLY SNAPSHOT", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    print("\n$ mem " + " ".join([*argv, "--snapshot"]), flush=True)
    app(args=[*argv, "--snapshot"], prog_name="mem", standalone_mode=False)
    print("\nREAD-ONLY CONTRACT CHECK", flush=True)
    print(
        f"  PTY · {os.get_terminal_size().columns} columns × "
        f"{os.get_terminal_size().lines} rows"
    )
    print("  PROVIDER CALLS · 0")
    print("  ORIGIN · " + ("PROJECTED PREVIEW" if projection else "EXACT PREWARM"))
    print("  INPUT · " + ("13 + 13 MEMORIES" if projection else "150 + 150 MEMORIES"))


_ANSI_16 = {
    "black": "#000000",
    "red": "#ed8796",
    "green": "#a6da95",
    "brown": "#eed49f",
    "blue": "#8aadf4",
    "magenta": "#c6a0f6",
    "cyan": "#8bd5ca",
    "white": "#cad3f5",
    "brightblack": "#5b6078",
    "brightred": "#ed8796",
    "brightgreen": "#a6da95",
    "brightbrown": "#eed49f",
    "brightblue": "#8aadf4",
    "brightmagenta": "#c6a0f6",
    "brightcyan": "#8bd5ca",
    "brightwhite": "#ffffff",
}


def _color(value: str, *, background: bool) -> str:
    if value == "default":
        return "#101217" if background else "#e6e9ef"
    if len(value) == 6 and all(character in "0123456789abcdef" for character in value):
        return "#" + value
    return _ANSI_16.get(value, "#101217" if background else "#e6e9ef")


def _render(raw: bytes, stem: str, *, output_directory: Path) -> None:
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw.decode("utf-8", errors="replace"))
    regular = ImageFont.truetype(FONT_PATH, 16)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
    cell_width = 10
    cell_height = 21
    margin = 16
    image = Image.new(
        "RGB",
        (margin * 2 + COLS * cell_width, margin * 2 + ROWS * cell_height),
        "#101217",
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLS):
            char = screen.buffer[row][column]
            foreground = _color(char.fg, background=False)
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
            if char.data != " ":
                box_drawing = "\u2500" <= char.data <= "\u259f"
                draw.text(
                    (x, y),
                    char.data,
                    font=bold if char.bold and not box_drawing else regular,
                    fill=foreground,
                )
    output_directory.mkdir(parents=True, exist_ok=True)
    image.save(output_directory / f"{stem}.png")
    (output_directory / f"{stem}.typescript").write_bytes(raw)
    (output_directory / f"{stem}.txt").write_text(
        "\n".join(line.rstrip() for line in screen.display).rstrip() + "\n",
        encoding="utf-8",
    )


def _settle(child: pexpect.spawn, seconds: float = 0.6) -> None:
    try:
        child.expect(b"__MEMCOMMIT_UNREACHABLE_CAPTURE_MARKER__", timeout=seconds)
    except pexpect.TIMEOUT:
        pass


def _capture(*, projection: bool) -> None:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    recorder = _Recorder()
    child = pexpect.spawn(
        sys.executable,
        [
            str(Path(__file__).resolve()),
            "--child",
            *(["--projection"] if projection else []),
        ],
        cwd=str(ROOT),
        env=environment,
        dimensions=(ROWS, COLS),
        encoding=None,
        timeout=15,
    )
    child.logfile_read = recorder
    output_directory = PROJECTION_OUT if projection else EXACT_OUT
    prefix = "projected" if projection else "exact-prewarm"
    try:
        child.expect(b"PROJECTED" if projection else b"EXACT PREWARM")
        child.expect(b"FOCUS VIEWER")
        _settle(child)
        _render(
            bytes(recorder.data),
            f"01-{prefix}-report",
            output_directory=output_directory,
        )

        child.send(b"q")
        child.expect(b"CAPTURE GATE .* READ-ONLY SNAPSHOT")
        _settle(child)
        _render(
            bytes(recorder.data),
            "02-close-receipt",
            output_directory=output_directory,
        )

        child.send(b"v\r")
        child.expect(b"READ-ONLY CONTRACT CHECK")
        child.expect(
            br"INPUT .* 13 \+ 13 MEMORIES"
            if projection
            else br"INPUT .* 150 \+ 150 MEMORIES"
        )
        child.expect(pexpect.EOF)
        _render(
            bytes(recorder.data),
            "03-read-only-verification",
            output_directory=output_directory,
        )
    finally:
        child.close(force=True)
    raw = bytes(recorder.data)
    if b"38;2;" not in raw and b"48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--projection", action="store_true")
    arguments = parser.parse_args()
    if arguments.child:
        _run_child(projection=arguments.projection)
    else:
        _capture(projection=arguments.projection)


if __name__ == "__main__":
    main()
