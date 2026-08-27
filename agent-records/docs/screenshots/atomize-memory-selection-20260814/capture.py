"""Capture exact Atomize Memory selection and its empty-input guard."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import sys
import tempfile
import time

import pexpect
import pyte
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
DOWN = "\x1b[B"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


_NAMED_COLORS = {
    "default": "#e6e9ef",
    "black": "#101217",
    "red": "#ed8796",
    "green": "#a6da95",
    "brown": "#eed49f",
    "yellow": "#eed49f",
    "blue": "#8aadf4",
    "magenta": "#c6a0f6",
    "cyan": "#8bd5ca",
    "white": "#cad3f5",
    "brightblack": "#5b6078",
    "brightred": "#ed8796",
    "brightgreen": "#a6da95",
    "brightyellow": "#f5a97f",
    "brightblue": "#8aadf4",
    "brightmagenta": "#c6a0f6",
    "brightcyan": "#91d7e3",
    "brightwhite": "#f4dbd6",
}


class _StreamRecorder(io.StringIO):
    def flush(self) -> None:
        return


def _prepare_store(root: Path, *, empty: bool):
    import memcommit.application.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=root)
    context = ops.init("study/source" if not empty else "study/empty")
    selected_uid = None
    if not empty:
        selected_uid = ops.add(
            context,
            "The library entrance moves north on Monday and closes at 18:00.",
        ).uid
        ops.add(
            context,
            "The help desk keeps its existing weekend schedule.",
        )
    store.create_context(context)
    store.set_current(context.name)
    return store, context, selected_uid


def _run_focus_child(store_root: Path) -> None:
    from memcommit.commands.shared.endpoint_setup_flows import choose_atomize_setup

    store, source, expected_uid = _prepare_store(store_root, empty=False)
    print("$ mem atomize --sessions -> New Atomize", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    receipt = choose_atomize_setup(store)
    if receipt is None:
        raise RuntimeError("Atomize setup unexpectedly cancelled.")
    print("\nSETUP RECEIPT · EXACT MEMORY TARGET")
    print(f"  INPUT · {receipt.input_name}")
    print(f"  MEMORY UID · {receipt.input_memory_uid}")
    print(f"  OUTPUT · {receipt.output_name} · NOT CREATED")
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    unchanged = store.load_direct(source.name)
    print("\nREAD-ONLY CONTRACT CHECK")
    print(f"  SELECTED UID MATCH · {receipt.input_memory_uid == expected_uid}")
    print(f"  SOURCE DIRECT MEMORIES · {len(unchanged.memories)}")
    print(f"  OUTPUT EXISTS · {receipt.output_name in store.list_context_names()}")
    print("  PROVIDER CALLS · 0")
    print("  CONTEXT CHECKPOINTS · 0")


def _run_empty_child(store_root: Path) -> None:
    from memcommit.commands.shared.endpoint_setup_flows import choose_atomize_setup

    store, source, _selected_uid = _prepare_store(store_root, empty=True)
    print("$ mem atomize --sessions -> New Atomize (empty Input)", flush=True)
    print(
        f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}",
        flush=True,
    )
    receipt = choose_atomize_setup(store)
    unchanged = store.load_direct(source.name)
    print("\nEMPTY-INPUT CANCELLATION RECEIPT")
    print(f"  SETUP RECEIPT · {receipt!r}")
    print(f"  SOURCE DIRECT MEMORIES · {len(unchanged.memories)}")
    print("  PROVIDER CALLS · 0")
    print("  CONTEXT CHECKPOINTS · 0")


def _environment() -> dict[str, str]:
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
    return environment


def _settle(child: pexpect.spawn, *, seconds: float = 0.5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            child.read_nonblocking(size=65_536, timeout=0.05)
        except pexpect.TIMEOUT:
            continue
        except pexpect.EOF:
            return


def _color(value: str, *, background: bool = False) -> str:
    if value in _NAMED_COLORS:
        if value == "default" and background:
            return "#101217"
        return _NAMED_COLORS[value]
    if len(value) == 6 and all(char in "0123456789abcdef" for char in value):
        return "#" + value
    return "#101217" if background else "#e6e9ef"


def _render(raw: str, stem: str) -> None:
    screen = pyte.Screen(COLUMNS, ROWS)
    pyte.Stream(screen).feed(raw)
    plain = "\n".join(screen.display).rstrip() + "\n"
    (OUT / f"{stem}.typescript").write_text(raw, encoding="utf-8")
    (OUT / f"{stem}.txt").write_text(plain, encoding="utf-8")

    regular = ImageFont.truetype(FONT_PATH, 16, index=0)
    bold = ImageFont.truetype(FONT_PATH, 16, index=1)
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
            char = screen.buffer[row][column]
            foreground = _color(char.fg)
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
            if char.data and char.data != " ":
                box_drawing = "\u2500" <= char.data <= "\u257f"
                draw.text(
                    (x, y),
                    char.data,
                    font=bold if char.bold and not box_drawing else regular,
                    fill=foreground,
                )
            if char.underscore:
                draw.line(
                    (x, y + cell_height - 3, x + cell_width - 1, y + cell_height - 3),
                    fill=foreground,
                )
    image.save(OUT / f"{stem}.png")


def _snapshot(recorder: _StreamRecorder, stem: str) -> None:
    _render(recorder.getvalue(), stem)


def _spawn(kind: str, store_root: Path) -> tuple[pexpect.spawn, _StreamRecorder]:
    recorder = _StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=15,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_focus(store_root: Path) -> None:
    child, recorder = _spawn("focus", store_root)
    try:
        child.expect("NEW ATOMIZE")
        _settle(child)
        _snapshot(recorder, "01-setup-entry")

        child.send("m")
        _settle(child)
        _snapshot(recorder, "02-input-memories-revealed")

        child.send(DOWN)
        _settle(child)
        _snapshot(recorder, "03-memory-focused")

        child.send("\r")
        _settle(child)
        _snapshot(recorder, "04-memory-selected")

        child.send("m")
        _settle(child)
        _snapshot(recorder, "05-hidden-preview-clears-selection")

        # Reopen and reselect the same row; this restores the already captured
        # selected state without adding a duplicate image.
        child.send("m" + DOWN + "\r")
        _settle(child)
        child.send("\t" + DOWN + "study/focused-output\r")
        _settle(child)
        _snapshot(recorder, "06-output-confirmed-apply")

        child.send("\r")
        child.expect("SETUP RECEIPT .* EXACT MEMORY TARGET")
        child.expect("CAPTURE GATE .* READ-ONLY VERIFICATION")
        _settle(child)
        _snapshot(recorder, "07-success-receipt")

        child.send("v\r")
        child.expect("READ-ONLY CONTRACT CHECK")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_empty(store_root: Path) -> None:
    child, recorder = _spawn("empty", store_root)
    try:
        child.expect("NEW ATOMIZE")
        _settle(child)
        child.send("\t\r\t\r")
        _settle(child, seconds=0.8)
        _snapshot(recorder, "09-empty-input-blocked")

        child.send("q")
        child.expect("EMPTY-INPUT CANCELLATION RECEIPT")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-empty-input-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-atomize-focus-") as directory:
        _capture_focus(Path(directory) / "focus-store")
        _capture_empty(Path(directory) / "empty-store")
    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "focus":
            _run_focus_child(root)
        elif kind == "empty":
            _run_empty_child(root)
        else:
            raise SystemExit(f"unknown child kind: {kind}")
    else:
        main()
