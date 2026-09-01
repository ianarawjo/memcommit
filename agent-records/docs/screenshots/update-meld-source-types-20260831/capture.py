"""Capture Update and Meld Source Type setup flows in a 180x52 color PTY."""

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


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
KOREAN_FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
RIGHT = "\x1b[C"
DOWN = "\x1b[B"
TAB = "\t"
ENTER = "\r"

if str(ROOT / "src") not in sys.path:
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


def _prepare_store(root: Path):
    import memcommit.application.capabilities.ops as ops
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(root=root)
    source = ops.init("practice/coffee/source")
    first = ops.add(source, "Use 18 grams of coffee for the baseline recipe.")
    second = ops.add(source, "Keep the water temperature near 94 C.")
    target = ops.init("practice/coffee/target")
    target_memory = ops.add(target, "The current recipe uses a 1:15 ratio.")
    result = ops.init("practice/coffee/result")
    for context in (source, target, result):
        store.create_context(context)
    store.set_current(target.name)
    memories = {
        source.name: (
            (first.uid, first.content),
            (second.uid, second.content),
        ),
        target.name: ((target_memory.uid, target_memory.content),),
        result.name: (),
    }
    before = {
        context.name: store._context_file(context.name).read_bytes()
        for context in (source, target, result)
    }
    return store, memories, before


def _memory_loader(memories):
    from memcommit.adapters.console.terminal.components.endpoint_setup import (
        EndpointSetupMemory,
    )

    def load(role_uid: str, context_name: str):
        return tuple(
            EndpointSetupMemory(context_name, uid, content)
            for uid, content in memories[context_name]
        )

    return load


def _verification(store, before) -> None:
    unchanged = all(
        store._context_file(name).read_bytes() == content
        for name, content in before.items()
    )
    print("READ-ONLY SETUP VERIFICATION")
    print(f"  CONTEXT BYTES UNCHANGED · {unchanged}")
    print(f"  CURRENT CONTEXT · {store.current_context_name()}")
    print(
        "  CONTEXT CHECKPOINTS · "
        f"{sum(len(store.list_checkpoints(name)) for name in before)}"
    )
    print("  PROVIDER CALLS · 0", flush=True)


def _run_update_child(store_root: Path, *, inline: bool) -> None:
    from memcommit.adapters.console.commands.update.workbench import (
        UpdateEndpointSetup,
        choose_update_endpoint_setup,
    )

    store, memories, before = _prepare_store(store_root)
    setup = UpdateEndpointSetup(
        names=tuple(memories),
        source_name="practice/coffee/source",
        target_name="practice/coffee/target",
        current_context="practice/coffee/target",
        inline_target_names=frozenset(memories),
    )
    print("$ mem update", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    selected = choose_update_endpoint_setup(
        setup,
        memory_loader=_memory_loader(memories),
    )
    if not inline:
        print(f"\nCANCELLED STORED-MEMORY TRACE · {selected!r}", flush=True)
        _verification(store, before)
        return
    print(f"\nTYPED UPDATE SETUP RECEIPT · {selected!r}")
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    _verification(store, before)


def _run_meld_child(store_root: Path, *, inline: bool) -> None:
    from memcommit.adapters.console.commands.meld.endpoint_setup import (
        MeldTuiSetup,
        choose_meld_endpoint_setup,
    )

    store, memories, before = _prepare_store(store_root)
    setup = MeldTuiSetup(
        names=tuple(memories),
        left_name="practice/coffee/source",
        right_name="practice/coffee/target",
        eligible_target_names=frozenset({"practice/coffee/result"}),
        current_context="practice/coffee/target",
        inline_baseline_names=frozenset(memories),
    )
    print("$ mem meld", flush=True)
    print(f"PTY {os.get_terminal_size().columns} {os.get_terminal_size().lines}")
    selected = choose_meld_endpoint_setup(
        setup,
        memory_loader=_memory_loader(memories),
        new_name_validator=lambda _name: None,
    )
    if not inline:
        print(f"\nCANCELLED STORED-MEMORY TRACE · {selected!r}", flush=True)
        _verification(store, before)
        return
    print(f"\nTYPED MELD SETUP RECEIPT · {selected!r}")
    print("CAPTURE GATE · PRESS V FOR READ-ONLY VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Verification gate was not acknowledged.")
    _verification(store, before)


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
    korean = ImageFont.truetype(KOREAN_FONT_PATH, 20, index=0)
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
                    font=(
                        korean
                        if "\uac00" <= char.data <= "\ud7a3"
                        else bold
                        if char.bold and not box_drawing
                        else regular
                    ),
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
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _capture_update_stored(store_root: Path) -> None:
    child, recorder = _spawn("update-stored", store_root)
    try:
        child.expect("NEW UPDATE")
        _settle(child)
        _snapshot(recorder, "01-update-entry-context")
        child.send(RIGHT + TAB * 3 + ENTER * 2)
        _settle(child)
        _snapshot(recorder, "02-update-stored-memory-selected")
        child.send("\x1b")
        child.expect("CANCELLED STORED-MEMORY TRACE")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_update_inline(store_root: Path) -> None:
    child, recorder = _spawn("update-inline", store_root)
    try:
        child.expect("NEW UPDATE")
        _settle(child)
        child.send(RIGHT * 2)
        _settle(child)
        _snapshot(recorder, "03-update-inline-empty-invalid")
        child.send(TAB + "나는 자연인이다" + DOWN * 2)
        _settle(child)
        _snapshot(recorder, "04-update-inline-exact-command")
        child.send(ENTER)
        child.expect("TYPED UPDATE SETUP RECEIPT")
        child.expect("CAPTURE GATE")
        _settle(child)
        _snapshot(recorder, "05-update-inline-setup-receipt")
        child.send("v\r")
        child.expect("READ-ONLY SETUP VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "06-update-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_meld_stored(store_root: Path) -> None:
    child, recorder = _spawn("meld-stored", store_root)
    try:
        child.expect("NEW MELD")
        _settle(child)
        _snapshot(recorder, "07-meld-symmetric-context-peers")
        child.send(RIGHT)
        _settle(child)
        _snapshot(recorder, "08-meld-directional-context-source")
        child.send(TAB + RIGHT + TAB * 3 + ENTER * 2)
        _settle(child)
        _snapshot(recorder, "09-meld-stored-memory-selected")
        child.send("\x1b")
        child.expect("CANCELLED STORED-MEMORY TRACE")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_meld_inline(store_root: Path) -> None:
    child, recorder = _spawn("meld-inline", store_root)
    try:
        child.expect("NEW MELD")
        _settle(child)
        child.send(RIGHT + TAB + RIGHT * 2)
        _settle(child)
        _snapshot(recorder, "10-meld-inline-empty-invalid")
        child.send(TAB + "keep this exact distinction" + DOWN * 2)
        _settle(child)
        _snapshot(recorder, "11-meld-inline-exact-command")
        child.send(ENTER)
        child.expect("TYPED MELD SETUP RECEIPT")
        child.expect("CAPTURE GATE")
        _settle(child)
        _snapshot(recorder, "12-meld-inline-setup-receipt")
        child.send("v\r")
        child.expect("READ-ONLY SETUP VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "13-meld-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".txt", ".typescript"):
        for path in OUT.glob(f"*{suffix}"):
            path.unlink()
    with tempfile.TemporaryDirectory(prefix="source-type-capture-") as directory:
        root = Path(directory)
        _capture_update_stored(root / "update-stored")
        _capture_update_inline(root / "update-inline")
        _capture_meld_stored(root / "meld-stored")
        _capture_meld_inline(root / "meld-inline")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError("PTY stream did not contain expected true-color ANSI.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        kind = sys.argv[2]
        root = Path(sys.argv[3])
        if kind == "update-stored":
            _run_update_child(root, inline=False)
        elif kind == "update-inline":
            _run_update_child(root, inline=True)
        elif kind == "meld-stored":
            _run_meld_child(root, inline=False)
        elif kind == "meld-inline":
            _run_meld_child(root, inline=True)
        else:
            raise SystemExit(f"unknown child kind: {kind}")
    else:
        main()
